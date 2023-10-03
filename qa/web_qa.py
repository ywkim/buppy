"""Tool for load HTML files and QA."""
import asyncio
# from playwright import Page, Frame
import logging
from typing import Any, List, Optional, Type

from langchain.callbacks.manager import (AsyncCallbackManagerForToolRun,
                                         CallbackManagerForToolRun)
from langchain.chains.question_answering import load_qa_chain
from langchain.docstore.document import Document
from langchain.document_loaders.base import BaseLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.tools.base import BaseTool, ToolException
from openai.error import OpenAIError
from pydantic import BaseModel, Field

from qa.utils import get_max_tokens

logger = logging.getLogger(__name__)


def sync_process_frame(frame) -> str:
    scripts = frame.locator("script")
    scripts.evaluate_all("scripts => scripts.forEach(script => script.remove())")

    frame_text = frame.inner_text("body")
    title = frame.title()

    if title:
        return f"# {title}\n\n{frame_text}"

    return frame_text


async def async_process_frame(frame) -> str:
    scripts = frame.locator("script")
    await scripts.evaluate_all("scripts => scripts.forEach(script => script.remove())")

    frame_text = await frame.inner_text("body")
    title = await frame.title()

    if title:
        return f"# {title}\n\n{frame_text}"

    return frame_text


class PlaywrightURLLoader(BaseLoader):
    """Loader that uses Playwright and to load a page and unstructured to load the html.
    This is useful for loading pages that require javascript to render.

    Attributes:
        urls (List[str]): List of URLs to load.
        continue_on_failure (bool): If True, continue loading other URLs on failure.
        headless (bool): If True, the browser will run in headless mode.
    """

    def __init__(
        self,
        urls: List[str],
        continue_on_failure: bool = True,
        headless: bool = True,
        remove_selectors: Optional[List[str]] = None,
    ):
        """Load a list of URLs using Playwright and unstructured."""
        try:
            import playwright  # noqa:F401
        except ImportError:
            raise ImportError(
                "playwright package not found, please install it with "
                "`pip install playwright`"
            )

        try:
            import unstructured  # noqa:F401
        except ImportError:
            raise ValueError(
                "unstructured package not found, please install it with "
                "`pip install unstructured`"
            )

        self.urls = urls
        self.continue_on_failure = continue_on_failure
        self.headless = headless
        self.remove_selectors = remove_selectors

    def sync_evaluate_page(self, page):
        """Process a page and return the text content.
        This method can be overridden to apply custom logic.
        """
        print(f"Frames: {len(page.frames)}")
        return "\n\n".join(sync_process_frame(frame) for frame in page.frames)

    async def async_evaluate_page(self, page):
        """Process a page asynchronously and return the text content.
        This method can be overridden to apply custom logic.
        """
        print(f"Frames: {len(page.frames)}")
        frame_texts = await asyncio.gather(
            *(async_process_frame(frame) for frame in page.frames)
        )
        return "\n\n".join(frame_texts)

    def load(self) -> List[Document]:
        """Load the specified URLs using Playwright and create Document instances.

        Returns:
            List[Document]: A list of Document instances with loaded content.
        """
        from playwright.sync_api import sync_playwright
        from unstructured.partition.html import partition_html

        docs: List[Document] = list()

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            for url in self.urls:
                try:
                    page = browser.new_page()
                    page.goto(url)
                    text = self.sync_evaluate_page(page)
                    metadata = {"source": url}
                    docs.append(Document(page_content=text, metadata=metadata))
                except Exception as e:
                    if self.continue_on_failure:
                        logger.error(
                            f"Error fetching or processing {url}, exception: {e}"
                        )
                    else:
                        raise e
            browser.close()
        return docs

    async def aload(self) -> List[Document]:
        """Load the specified URLs with Playwright and create Documents asynchronously.
        Use this function when in a jupyter notebook environment.

        Returns:
            List[Document]: A list of Document instances with loaded content.
        """
        from playwright.async_api import async_playwright
        from unstructured.partition.html import partition_html

        docs: List[Document] = list()

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            for url in self.urls:
                try:
                    page = await browser.new_page()
                    await page.goto(url)
                    text = await self.async_evaluate_page(page)
                    metadata = {"source": url}
                    docs.append(Document(page_content=text, metadata=metadata))
                except Exception as e:
                    if self.continue_on_failure:
                        logger.error(
                            f"Error fetching or processing {url}, exception: {e}"
                        )
                    else:
                        raise e
            await browser.close()
        return docs


class WebQASchema(BaseModel):
    question: str = Field(description="should be a question on response content")
    urls: List[str] = Field(description="should be a list of strings")


class WebQA(BaseTool):
    """Tool for load HTML files and QA."""

    name = "ask_webpage"
    description = "Use this when you need to answer questions about specific webpages"
    args_schema: Type[WebQASchema] = WebQASchema
    llm: Any = Field()
    embeddings: Any = Field()

    def _run(
        self,
        question: str,
        urls: List[str],
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Use the tool."""
        print(f"WebQA question: {question}, urls: {urls}, llm: {self.llm.model_name}")
        try:
            loader = PlaywrightURLLoader(urls)
            splitter = self._create_splitter()

            docs = loader.load_and_split(splitter)
            self._print_documents(docs)

            chain = load_qa_chain(self.llm, chain_type="refine")
            answer = chain.arun(input_documents=docs, question=question)
            return answer
        except OpenAIError as e:
            print(e)
            raise ToolException() from e
        except IOError as e:
            raise ToolException() from e

    async def _arun(
        self,
        question: str,
        urls: List[str],
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> str:
        """Use the tool asynchronously."""
        print(f"WebQA question: {question}, urls: {urls}, llm: {self.llm.model_name}")
        try:
            loader = PlaywrightURLLoader(urls)
            splitter = self._create_splitter()

            docs = await loader.aload()
            docs = splitter.split_documents(docs)
            self._print_documents(docs)

            chain = load_qa_chain(self.llm, chain_type="refine")
            answer = await chain.arun(input_documents=docs, question=question)
            return answer
        except OpenAIError as e:
            print(e)
            raise ToolException() from e
        except IOError as e:
            raise ToolException() from e

    def _create_splitter(self):
        max_token = get_max_tokens(self.llm.model_name)
        chunk_size = int(max_token * 0.9)
        chunk_overlap = int(chunk_size * 0.2)
        length_function = self.llm.get_num_tokens
        return RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=length_function,
        )

    def _print_documents(self, docs):
        print(f"< ======= docs (total: {len(docs)}) ======= >")
        for i, doc in enumerate(docs):
            print(f"\n[Document {i}]\n")
            print(doc)

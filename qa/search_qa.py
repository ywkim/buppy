"""Tool that calls SerpAPI and QA.
"""
from typing import Any, Optional, Type

from langchain.callbacks.manager import (
    AsyncCallbackManagerForToolRun,
    CallbackManagerForToolRun,
)
from langchain.embeddings import OpenAIEmbeddings
from langchain.indexes import VectorstoreIndexCreator
from langchain.tools import BaseTool
from langchain.tools.base import ToolException
from openai.error import OpenAIError
from pydantic import BaseModel, Field

from qa.serp_loader import SerpAPILoader


class SearchQASchema(BaseModel):
    question: str = Field(description="should be a question on Google search results")
    query: str = Field(
        description="should be a Google search query. You can use anything that you would use in a regular Google search."
    )


class SearchQA(BaseTool):
    name = "search_qa"
    description = "Useful for when you need to answer questions about current events"
    args_schema: Type[SearchQASchema] = SearchQASchema
    llm: Any = Field()
    serp: Any = Field()
    embeddings: OpenAIEmbeddings = Field()

    def _run(
        self,
        question: str,
        query: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Use the tool."""
        print("SearchQA Tool")
        print(f"Question: {question}")
        print(f"Query: {query}")
        try:
            loader = SerpAPILoader(query, self.serp)
            index = VectorstoreIndexCreator(embedding=self.embeddings).from_loaders(
                [loader]
            )
            answer = index.query(question=question, llm=self.llm)
            return answer
        except OpenAIError as e:
            print(e)
            raise ToolException() from e
        except IOError as e:
            raise ToolException() from e

    async def _arun(
        self,
        question: str,
        query: str,
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> str:
        """Use the tool asynchronously."""
        return self._run(question, query)

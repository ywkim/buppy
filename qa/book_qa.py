"""Tool for load book files and QA."""
import logging
import os
from typing import Any, List, Optional, Type

import pinecone
from git.exc import GitError
from langchain.callbacks.manager import (AsyncCallbackManagerForToolRun,
                                         CallbackManagerForToolRun)
from langchain.chains import RetrievalQA
from langchain.document_loaders import GitLoader, WebBaseLoader
from langchain.indexes import VectorstoreIndexCreator
from langchain.requests import TextRequestsWrapper
from langchain.tools.base import BaseTool, ToolException
from langchain.vectorstores import Pinecone
from openai.error import OpenAIError
from pinecone.core.exceptions import PineconeException
from pydantic import BaseModel, Field


class BookQASchema(BaseModel):
    question: str = Field(
        description="should be a question on the document. Since the questions are answered by other LLMs, it is good to include details about your specific task. And Since this LLM has no history, you should include everything in your question."
    )
    book_id: str = Field(description="should be the book_id of the document")


class BookQA(BaseTool):
    """Tool for load books and QA."""

    name = "book_qa"
    description = "Use this when you need to answer questions about specific book or document."  # Both book_id and question must be provided.
    args_schema: Type[BookQASchema] = BookQASchema
    llm: Any = Field()
    embeddings: Any = Field()
    pinecone_index: str

    def _run(
        self,
        question: str,
        book_id: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Use the tool."""
        print("BookQA")
        try:
            index = pinecone.Index(self.pinecone_index)
            namespaces = index.describe_index_stats()["namespaces"]
            if book_id not in namespaces:
                raise ToolException(f"Invalid book_id: {book_id}")
            if namespaces[book_id]["vector_count"] == 0:
                raise ToolException(f"Namespace {book_id} is empty")

            db = Pinecone.from_existing_index(
                self.pinecone_index, self.embeddings, namespace=book_id
            )
            retriever = db.as_retriever()

            matched_docs = retriever.get_relevant_documents(question)
            print(f"Matched docs: {len(matched_docs)}")
            for i, d in enumerate(matched_docs):
                print(f"\n[Document {i}]\n")
                print(d.page_content)

            # Note that the content may contain OCR errors, so you must correct and interpret the errors.
            qa = RetrievalQA.from_chain_type(llm=self.llm, retriever=retriever)
            answer = qa.run(question)
            return answer
        except PineconeException as e:
            print(e)
            raise ToolException() from e
        except OpenAIError as e:
            print(e)
            raise ToolException() from e

    async def _arun(
        self,
        question: str,
        book_id: str,
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> str:
        """Use the tool asynchronously."""
        return self._run(question, book_id)

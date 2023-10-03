"""Tool for load files from a Git repository and QA."""
import logging
import os
from typing import Any, List, Optional, Type

import pinecone
from git.exc import GitError
from langchain.callbacks.manager import (
    AsyncCallbackManagerForToolRun,
    CallbackManagerForToolRun,
)
from langchain.chains import RetrievalQA
from langchain.document_loaders import GitLoader, WebBaseLoader
from langchain.indexes import VectorstoreIndexCreator
from langchain.requests import TextRequestsWrapper
from langchain.tools.base import BaseTool, ToolException
from langchain.vectorstores import Pinecone
from openai.error import OpenAIError
from pinecone.core.exceptions import PineconeException
from pydantic import BaseModel, Field


class GitQASchema(BaseModel):
    question: str = Field(
        description="should be a question on source code. Since the questions are answered by other LLMs, it is good to include specific tasks. And since this LLM has no history, you should include everything in your question. If the task is complex, it is better to split it up into several requests."
    )
    sha: str = Field(
        description="should be a 40 byte hex version of 20 byte binary sha(hash)"
    )


class GitQA(BaseTool):
    """Tool for load files from a Git repository and QA."""

    name = "git_qa"
    description = "Use this when you need to answer questions about specific Git repository. A hash of the repository's default branch must be provided."
    args_schema: Type[GitQASchema] = GitQASchema
    llm: Any = Field()
    embeddings: Any = Field()
    pinecone_index: str

    def _run(
        self,
        question: str,
        sha: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Use the tool."""
        print("GitQA")
        try:
            index = pinecone.Index(self.pinecone_index)
            namespaces = index.describe_index_stats()["namespaces"]
            if sha not in namespaces:
                raise ToolException(f"Invalid sha: {sha}")
            vector_count = namespaces[sha]["vector_count"]
            if vector_count == 0:
                raise ToolException(f"Namespace {sha} is empty")
            print(vector_count)

            db = Pinecone.from_existing_index(
                self.pinecone_index, self.embeddings, namespace=sha
            )
            retriever = db.as_retriever()

            matched_docs = retriever.get_relevant_documents(question)
            print(f"Matched docs: {len(matched_docs)}")
            for i, d in enumerate(matched_docs):
                print(f"\n[Document {i}]\n")
                print(d.page_content)

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
        url: str,
        branch: str,
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> str:
        """Use the tool asynchronously."""
        return ""

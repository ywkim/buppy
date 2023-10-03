import json
import logging
from typing import Any, List, Union

from langchain.docstore.document import Document
from langchain.document_loaders.base import BaseLoader
from langchain.utilities import SerpAPIWrapper
from serpapi import GoogleSearch

logger = logging.getLogger(__name__)


class SerpAPILoader(BaseLoader):
    """Load search results using SerpAPI."""

    def __init__(self, search_query: str, serp):
        """Initialize with query and API key."""
        self.search_query = search_query
        self.serp = serp

    @staticmethod
    def _process_response(res: dict) -> Union[dict, List[Any], str]:
        """Process response from SerpAPI."""
        if "error" in res:
            raise ValueError(f"Got error from SerpAPI: {res['error']}")
        response_types = [
            "answer_box",
            "sports_results",
            "shopping_results",
            "knowledge_graph",
            "organic_results",
        ]
        for response_type in response_types:
            if response_type in res:
                return res[response_type]
        return "No good search result found"

    def load(self) -> List[Document]:
        """Load search results using SerpAPI."""
        response_dict = self.serp.results(self.search_query)
        processed_response = self._process_response(response_dict)
        page_content = json.dumps(processed_response)
        metadata = {"source": "SerpAPI"}
        return [Document(page_content=page_content, metadata=metadata)]

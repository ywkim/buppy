import argparse
import configparser
import logging
import uuid

from langchain.document_loaders import PyPDFLoader
from langchain.llms import OpenAI
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.vectorstores import Chroma

from index_builder import IndexBuilder
from utils import get_max_tokens

logger = logging.getLogger(__name__)


class BookIndexBuilder(IndexBuilder):
    def __init__(
        self, index_name, pinecone_api_key, pinecone_env, openai_api_key, llm, filename
    ):
        super().__init__(index_name, pinecone_api_key, pinecone_env, openai_api_key)
        self.llm = llm
        self.filename = filename
        self._namespace = str(uuid.uuid4())

    def load_documents(self):
        print("Loading PDF...")
        loader = PyPDFLoader(self.filename)

        max_token = get_max_tokens(self.llm.model_name)
        chunk_size = int(max_token * 0.9)
        chunk_overlap = int(chunk_size * 0.2)
        length_function = self.llm.get_num_tokens

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=length_function,
        )

        self.pages = loader.load_and_split(splitter)
        print(f"Total Pages: {len(self.pages)}")
        print("First page:")
        print(self.pages[0])

    @property
    def namespace(self):
        return self._namespace

    def create_db(self):
        print("Creating Local Vector DB")
        return Chroma.from_documents(self.pages, self.embeddings)


def main():
    parser = argparse.ArgumentParser(
        description="Builds an index for a given PDF file."
    )
    parser.add_argument("filename", type=str, help="Path to the PDF file")

    args = parser.parse_args()

    config = configparser.ConfigParser()
    config.read("config.ini")

    llm = OpenAI(
        model=config.get("settings", "tool_llm_model"),
        temperature=0,
        openai_api_key=config.get("api", "openai_api_key"),
    )

    indexer = BookIndexBuilder(
        config.get("settings", "pinecone_index"),
        config.get("api", "pinecone_api_key"),
        config.get("api", "pinecone_env"),
        config.get("api", "openai_api_key"),
        llm,
        args.filename,
    )
    indexer.run()


if __name__ == "__main__":
    main()
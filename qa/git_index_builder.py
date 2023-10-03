import argparse
import configparser
import glob
import logging
import os
import time
import uuid

from git import Repo
from index_builder import IndexBuilder
from langchain.document_loaders import GitLoader
from langchain.vectorstores import Chroma
from openai.error import APIError, RateLimitError
from tqdm.auto import tqdm

from main import DEFAULT_CONFIG

logger = logging.getLogger(__name__)


class GitIndexBuilder(IndexBuilder):
    def __init__(
        self,
        index_name,
        pinecone_api_key,
        pinecone_env,
        openai_api_key,
        repo_name,
        branch,
    ):
        super().__init__(index_name, pinecone_api_key, pinecone_env, openai_api_key)
        self.repo_path = f"/Users/ywkim/repos/{repo_name}"
        self.repo_name = repo_name
        self.branch = branch
        self.doc_path = f"/Users/ywkim/docs/{repo_name}"
        self.db_path = f"/Users/ywkim/db/{repo_name}"

    def load_documents(self):
        if not os.path.exists(self.repo_path):
            clone_url = f"https://github.com/{self.repo_name}"
        else:
            clone_url = None
        self.loader = GitLoader(
            repo_path=self.repo_path, clone_url=clone_url, branch=self.branch
        )
        self.dump_documents()

    def dump_documents(self):
        if not os.path.exists(self.doc_path):
            documents = self.loader.load()
            os.makedirs(self.doc_path, exist_ok=True)

            text_splitter = CharacterTextSplitter(chunk_size=1000, chunk_overlap=0)
            documents = text_splitter.split_documents(documents)

            for doc in tqdm(documents):
                text = doc.page_content
                metadata = doc.metadata
                doc_id = str(uuid.uuid4())
                with open(f"{self.doc_path}/{doc_id}.json", "w") as doc_file:
                    json.dump({**metadata, text_field: text}, doc_file)

    @property
    def namespace(self):
        repo = Repo(self.repo_path)
        print("Hash:")
        print(repo.head.object.hexsha)
        namespace = repo.head.object.hexsha
        return namespace

    def create_db(self):
        name = self.repo_path

        if not os.path.exists(self.db_path):
            db = Chroma(name, self.embeddings, persist_directory=self.db_path)
            db.persist()
        else:
            db = Chroma(
                persist_directory=self.db_path, embedding_function=self.embeddings
            )

        self.add_texts_to_db(db)

        db.persist()
        return db

    def add_texts_to_db(self, db):
        texts = []
        metadatas = []
        ids = []

        try:
            with open(f"{self.doc_path}/.ignore") as ignore_file:
                ignore_ids = [line.strip() for line in ignore_file.readlines()]
        except FileNotFoundError:
            ignore_ids = []

        print("Ignores:")
        print(ignore_ids)

        for file_path in tqdm(glob.glob(f"{self.doc_path}/*.json")):
            filename = os.path.basename(file_path)
            doc_id = os.path.splitext(filename)[0]
            result = db.get([doc_id])
            if doc_id in result["ids"]:
                print(f"Embedding exist: {doc_id}")
                continue
            if doc_id in ignore_ids:
                print(f"Ignore: {doc_id}")
                continue
            with open(file_path) as doc_file:
                try:
                    data = json.load(doc_file)
                except:
                    print(doc_file)
                    raise
                text = data.pop(text_field)
                texts.append(text)
                metadatas.append(data)
                ids.append(doc_id)

        batch_size = 16

        for i in tqdm(range(0, len(texts), batch_size)):
            try:
                # set end position of batch
                i_end = min(i + batch_size, len(texts))

                db.add_texts(
                    texts=texts[i:i_end], metadatas=metadatas[i:i_end], ids=ids[i:i_end]
                )

                time.sleep(5)  # Rate Limit
            except (APIError, ValueError) as e:
                logger.error(e)
                with open(f"{self.doc_path}/.ignore", "a") as ignore_file:
                    for doc_id in ids[i:i_end]:
                        ignore_file.write(f"{doc_id}\n")
                time.sleep(10)  # Rate Limit
            except RateLimitError as e:
                logger.error(e)
                break


def main():
    parser = argparse.ArgumentParser(description="Git Index Builder")
    parser.add_argument("repo_name", type=str, help="Name of the repository")
    parser.add_argument(
        "--branch", type=str, default="main", help="Branch of the repository"
    )

    args = parser.parse_args()

    config = configparser.ConfigParser()
    config.read_dict(DEFAULT_CONFIG)
    config.read("config.ini")

    indexer = GitIndexBuilder(
        config.get("settings", "pinecone_index"),
        config.get("api", "pinecone_api_key"),
        config.get("api", "pinecone_env"),
        config.get("api", "openai_api_key"),
        args.repo_name,
        args.branch,
    )
    indexer.run()


if __name__ == "__main__":
    main()

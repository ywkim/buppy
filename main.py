import argparse
import asyncio
import configparser
import json
import logging
import os
from typing import Optional

import pinecone
from langchain.agents import AgentExecutor, AgentType, initialize_agent
from langchain.chat_models import ChatOpenAI
from langchain.embeddings import OpenAIEmbeddings
from langchain.memory import ConversationBufferMemory
from langchain.prompts import MessagesPlaceholder
from langchain.schema import SystemMessage
from langchain.utilities import SerpAPIWrapper
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from slack_bolt.async_app import AsyncApp

from qa.book_qa import BookQA
from qa.git_qa import GitQA
from qa.search_qa import SearchQA
from qa.web_qa import WebQA

DEFAULT_CONFIG = {
    "settings": {
        "chat_model": "gpt-4",
        "system_prompt": "You are a helpful assistant.",
        "temperature": "0",
    },
}

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def load_config_from_file(config_file: str) -> configparser.ConfigParser:
    config = configparser.ConfigParser()
    config.read_dict(DEFAULT_CONFIG)
    config.read(config_file)
    return config


def load_config_from_env_vars():
    env_config = {
        "api": {
            "openai_api_key": os.environ.get("OPENAI_API_KEY"),
            "serpapi_api_key": os.environ.get("SERPAPI_API_KEY"),
            "pinecone_api_key": os.environ.get("PINECONE_API_KEY"),
            "pinecone_env": os.environ.get("PINECONE_ENV"),
            "slack_bot_token": os.environ.get("SLACK_BOT_TOKEN"),
            "slack_app_token": os.environ.get("SLACK_APP_TOKEN"),
        },
        "settings": {
            "chat_model": os.environ.get(
                "CHAT_MODEL", DEFAULT_CONFIG["settings"]["chat_model"]
            ),
            "system_prompt": os.environ.get(
                "SYSTEM_PROMPT", DEFAULT_CONFIG["settings"]["system_prompt"]
            ),
            "temperature": os.environ.get(
                "TEMPERATURE", DEFAULT_CONFIG["settings"]["temperature"]
            ),
            "pinecone_index": os.environ.get("PINECONE_INDEX"),
        },
    }
    config = configparser.ConfigParser()
    config.read_dict(env_config)
    return config


def load_config(config_file: Optional[str] = None) -> configparser.ConfigParser:
    """Load configuration from a given file and fall back to environment variables if the file does not exist."""
    if config_file:
        if os.path.exists(config_file):
            return load_config_from_file(config_file)
        raise FileNotFoundError(f"Config file {config_file} does not exist.")

    if os.path.exists("config.ini"):
        return load_config_from_file("config.ini")

    # If no config file provided, load config from environment variables
    return load_config_from_env_vars()


def load_tools(config: configparser.ConfigParser):
    llm = ChatOpenAI(
        model=config.get("settings", "chat_model"),
        temperature=0,
        openai_api_key=config.get("api", "openai_api_key"),
    )  # type: ignore
    serp = SerpAPIWrapper(serpapi_api_key=config.get("api", "serpapi_api_key"))  # type: ignore
    embeddings = OpenAIEmbeddings(
        openai_api_key=config.get("api", "openai_api_key"), disallowed_special=()
    )  # type: ignore
    pinecone_index = config.get("settings", "pinecone_index")
    pinecone.init(
        api_key=config.get("api", "pinecone_api_key"),
        environment=config.get("api", "pinecone_env"),
    )
    return [
        SearchQA(llm=llm, serp=serp, embeddings=embeddings),
        WebQA(llm=llm, embeddings=embeddings, handle_tool_error=True),
        GitQA(
            llm=llm,
            embeddings=embeddings,
            pinecone_index=pinecone_index,
            handle_tool_error=True,
        ),
        BookQA(
            llm=llm,
            embeddings=embeddings,
            pinecone_index=pinecone_index,
            handle_tool_error=True,
        ),
    ]


def init_agent_with_tools(config: configparser.ConfigParser) -> AgentExecutor:
    system_prompt = SystemMessage(content=config.get("settings", "system_prompt"))
    agent_kwargs = {
        "extra_prompt_messages": [MessagesPlaceholder(variable_name="memory")],
        "system_message": system_prompt,
    }
    memory = ConversationBufferMemory(memory_key="memory", return_messages=True)
    chat = ChatOpenAI(
        model=config.get("settings", "chat_model"),
        temperature=float(config.get("settings", "temperature")),
        openai_api_key=config.get("api", "openai_api_key"),
    )  # type: ignore
    tools = load_tools(config)
    agent = initialize_agent(
        tools,
        chat,
        agent=AgentType.OPENAI_FUNCTIONS,
        verbose=True,
        agent_kwargs=agent_kwargs,
        memory=memory,
    )
    return agent


def register_events_and_commands(
    app: AsyncApp, config: configparser.ConfigParser
) -> None:
    @app.command("/ask")
    async def handle_command(ack, body, say):
        # Acknowledge the command request right away
        await ack()
        # Provide an immediate response to indicate the question is being processed
        await say("Processing your question, please wait...")

        question = body.get("text", "")
        logging.info("Received a question: %s", question)
        response = await ask_question_to_agent(question, config)
        logging.info("Generated response: %s", response)
        # include the question in the reply
        await say(f"Question: {question}\nAnswer: {response}")

    @app.event("message")
    async def handle_message_events(body, logger):
        logger.info(body)


async def ask_question_to_agent(message: str, config):
    """Pass the message to the agent and get an answer."""
    agent = init_agent_with_tools(config)
    return await agent.arun(message)


async def process_messages_from_file(file_path, config):
    agent = init_agent_with_tools(config)
    with open(file_path, "r", encoding="utf-8") as message_file:
        messages = json.load(message_file)
        for message in messages:
            response_message = await agent.arun(message)
            print(response_message)


async def main():
    logging.info("Starting bot")

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config_file",
        help="Path to the configuration file. If no path is provided, will try to load from `config.ini` and environmental variables.",
    )
    parser.add_argument(
        "--message_file",
        help="Path to a JSON file containing messages to process.",
    )
    args = parser.parse_args()

    config = load_config(args.config_file)

    if args.message_file is not None:
        await process_messages_from_file(args.message_file, config)
    else:
        try:
            slack_bot_token = config.get("api", "slack_bot_token")
            slack_app_token = config.get("api", "slack_app_token")
        except configparser.NoOptionError as e:
            logging.error(
                "Configuration error: %s. Please provide the required api keys either in a config file or as environment variables.",
                e,
            )
            raise SystemExit from e

        logging.info("Initializing AsyncApp and SocketModeHandler")
        app = AsyncApp(token=slack_bot_token)
        handler = AsyncSocketModeHandler(app, slack_app_token)

        logging.info("Registering event and command handlers")
        register_events_and_commands(app, config)

        logging.info("Starting SocketModeHandler")
        await handler.start_async()


if __name__ == "__main__":
    asyncio.run(main())

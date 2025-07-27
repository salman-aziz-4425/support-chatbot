import logging
import os
from autogen_core import EVENT_LOGGER_NAME

from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_ext.models.anthropic import AnthropicChatCompletionClient
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import StructuredMessage
from autogen_core.models import UserMessage
import asyncio


anthropic_api_key= os.getenv("ANTHROPIC_API_KEY")

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(EVENT_LOGGER_NAME)
logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.INFO)

print(anthropic_api_key)

openai_client= AnthropicChatCompletionClient(
    model= "claude-3-5-sonnet-20240620",
    api_key= "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",
)



async def web_search(query: str) -> str:
    """Find information on the web"""
    return "AutoGen is a programming framework for building multi-agent applications."


assistant_agent= AssistantAgent(
    name= "Assistant",
    model_client= openai_client,
    system_message= "You are a helpful assistant.",
    tools=[web_search],
    model_client_stream=True,
)


async def main():
    user_message= UserMessage(content="Find information on AutoGen", source="user")
    # response=await assistant_agent.run_stream(user_message,
    #                                           tools=[web_search],
    #                                           system_message= "You are a helpful assistant.",
    #                                           )
    result = await assistant_agent.run(task=user_message)
    print(result.messages)
    async for message in result:
        print(message)
    # print(result)
    # print(response.content)


if __name__ == "__main__":
    asyncio.run(main())
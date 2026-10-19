"""
LangChain agent builder and LLM factory for the WhatsApp business bot.
Supports both Google Gemini and DeepSeek via a single configuration switch.
"""
import os
import logging
from langchain_core.language_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_classic.agents import AgentExecutor, create_tool_calling_agent

from config import settings
from tools import ALL_TOOLS

logger = logging.getLogger(__name__)

# Ensure API keys are in environment
if settings.google_api_key:
    os.environ["GOOGLE_API_KEY"] = settings.google_api_key


def get_chat_llm(temperature: float = 0.7) -> BaseChatModel:
    """
    Return the configured chat LLM based on settings.llm_provider.

    "gemini"   → ChatGoogleGenerativeAI
    "deepseek" → ChatOpenAI pointed at DeepSeek's OpenAI-compatible endpoint
    """
    provider = settings.llm_provider.lower()

    if provider == "deepseek":
        if not settings.deepseek_api_key:
            raise ValueError("DEEPSEEK_API_KEY is not set but llm_provider='deepseek'")

        return ChatOpenAI(
            model=settings.deepseek_model,
            temperature=temperature,
            openai_api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
        )

    # Default: Google Gemini
    return ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        temperature=temperature,
    )


def build_agent(system_prompt: str) -> AgentExecutor:
    """
    Build a LangChain tool-calling agent with the given system prompt.
    Returns an AgentExecutor ready to invoke.
    """
    llm = get_chat_llm(temperature=0.7)

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])

    agent = create_tool_calling_agent(llm, ALL_TOOLS, prompt)
    executor = AgentExecutor(
        agent=agent,
        tools=ALL_TOOLS,
        verbose=False,
        handle_parsing_errors=True,
        max_iterations=5,
    )
    return executor


def extract_text_response(raw_output) -> str:
    """
    Extract plain text from an LLM output.
    Models may return structured content blocks instead of a plain string.
    """
    if isinstance(raw_output, str):
        return raw_output
    if isinstance(raw_output, list):
        parts = []
        for block in raw_output:
            if isinstance(block, dict) and "text" in block:
                parts.append(block["text"])
            elif isinstance(block, str):
                parts.append(block)
        return "\n".join(parts) if parts else str(raw_output)
    return str(raw_output)

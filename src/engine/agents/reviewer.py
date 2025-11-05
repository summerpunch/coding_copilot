from typing import Literal

from langchain.agents.middleware import ToolRetryMiddleware
from langchain_core.messages import AIMessage
from langgraph.constants import END
from langgraph.types import Command
from src.engine.agents.llm_factory import llm_factory, AgentConfig
from src.engine.agents.supervisor import CopilotState
from src.engine.prompts import template
from langchain.agents import create_agent
from src.engine.tools.search import glob_search, grep_search
from src.engine.tools.file_ops import read_file
from src.engine.tools.shell import bash_execute
import logging
import os
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


async def reviewer_node(state: CopilotState) -> Command[
    Literal[
        "__end__"
    ]]:
    logger.info("Starting Reviewer Agent - 代码质量审查")
    messages = state["messages"]
    prompt = template.get_local_prompt("reviewer_prompt")
    reviewer_tools = [
        read_file,
        grep_search,
        glob_search,
        bash_execute
    ]
    agent = create_agent(
        model=llm_factory.factory(
            AgentConfig(
                model=os.getenv("reviewer_llm_model", "claude-haiku-4-5-20251001")
            )
        ),
        tools=reviewer_tools,
        system_prompt=prompt,
        middleware=[
            ToolRetryMiddleware(
                max_retries=3,  # 最多重试3次
                backoff_factor=2.0,  # 指数退避倍数
                initial_delay=1.0,  # 初始延迟1秒
                max_delay=60.0,  # 最大延迟60秒
                jitter=True,  # 添加随机抖动(±25%)
            )
        ]
    )
    await agent.ainvoke({"messages": messages})
    messages = state.get("messages", [])
    messages.append(AIMessage(
        name="analyzer_agent",
        content="已完成,状态为completed"
    ))
    return Command(
        goto=END,
        update={"messages": messages}
    )

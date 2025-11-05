from typing import Literal, Callable

from langchain.agents.middleware import HumanInTheLoopMiddleware, ToolRetryMiddleware
from langchain_core.messages import AIMessage
from langgraph.constants import END
from langgraph.types import Command
from src.engine.prompts import template
from langchain.agents import create_agent
from src.engine.agents.llm_factory import llm_factory, AgentConfig
from src.engine.agents.supervisor import CopilotState
from src.engine.tools.shell import bash_execute
from src.engine.tools.search import glob_search, grep_search
from src.engine.tools.file_ops import read_file, write_file, edit_file
import logging
import os
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


async def executor_node(state: CopilotState) -> Command[
    Literal[
        "__end__"
    ]]:
    logger.info("Starting Executor Agent - 精确代码执行")
    messages = state["messages"]
    prompt = template.get_local_prompt("executor_prompt")
    executor_tools = [
        bash_execute,
        read_file,
        write_file,
        edit_file,
        glob_search,
        grep_search,
    ]
    agent = create_agent(
        model=llm_factory.factory(
            AgentConfig(
                model=os.getenv("executor_llm_model", "claude-haiku-4-5-20251001")
            )
        ),
        tools=executor_tools,
        system_prompt=prompt,
        middleware=[
            HumanInTheLoopMiddleware(
                interrupt_on={"write_file": True, "edit_file": True},
                description_prefix="📝 文件操作需要批准",
            ),
            ToolRetryMiddleware(
                max_retries=3,  # 最多重试3次
                backoff_factor=2.0,  # 指数退避倍数
                initial_delay=1.0,  # 初始延迟1秒
                max_delay=60.0,  # 最大延迟60秒
                jitter=True,  # 添加随机抖动(±25%)
            )
        ]
    )
    logger.info("Invoking Executor Agent...")
    await agent.ainvoke({"messages": messages}, config=config)
    messages = state.get("messages", [])
    messages.append(AIMessage(
        name="analyzer_agent",
        content="已完成,状态为completed"
    ))
    return Command(
        goto=END,
        update={"messages": messages}
    )


async def executor_yolo_node(state: CopilotState) -> Command[
    Literal[
        "__end__"
    ]]:
    logger.info("Starting Executor Agent - 精确代码执行")
    messages = state["messages"]
    prompt = template.get_local_prompt("executor_best_practice")
    executor_tools = [
        bash_execute,
        read_file,
        write_file,
        edit_file,
        glob_search,
        grep_search,
    ]
    agent = create_agent(
        model=llm_factory.factory(
            AgentConfig(
                model=os.getenv("executor_llm_model", "claude-haiku-4-5-20251001")
            )
        ),
        tools=executor_tools,
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
    logger.info("Invoking Executor Agent...")
    await agent.ainvoke({"messages": messages}, config=config)
    messages = state.get("messages", [])
    messages.append(AIMessage(
        name="analyzer_agent",
        content="已完成,状态为completed"
    ))
    return Command(
        goto=END,
        update={"messages": messages}
    )

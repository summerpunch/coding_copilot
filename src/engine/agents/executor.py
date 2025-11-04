from typing import Literal, Callable

from langchain.agents.middleware import HumanInTheLoopMiddleware, ToolRetryMiddleware
from langchain_core.runnables import RunnableConfig
from langgraph.constants import END
from langgraph.types import Command, interrupt
from src.engine.prompts import template
from langchain.agents import create_agent
from src.engine.agents.llm_factory import llm_factory, AgentConfig
from src.engine.agents.supervisor import CopilotState
from src.engine.tools.shell import bash_execute
from src.engine.tools.search import glob_search, grep_search
from src.engine.tools.file_ops import read_file, write_file, edit_file
import logging

logger = logging.getLogger(__name__)


async def executor_node(state: CopilotState, config: RunnableConfig) -> Command[
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
        model=llm_factory.factory(AgentConfig()),
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
    response = await agent.ainvoke({"messages": messages}, config=config)
    logger.info("Executor Agent completed")
    return Command(
        goto=END,
    )


async def executor_yolo_node(state: CopilotState, config: RunnableConfig) -> Command[
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
        model=llm_factory.factory(AgentConfig()),
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
    response = await agent.ainvoke({"messages": messages}, config=config)
    logger.info("Executor Agent completed")
    return Command(
        goto=END,
    )

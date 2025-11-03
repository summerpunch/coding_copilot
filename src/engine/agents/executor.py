from typing import Literal

from langchain.agents.middleware import HumanInTheLoopMiddleware
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
            )
        ]
    )
    logger.info("Invoking Executor Agent...")
    response = await agent.ainvoke({"messages": messages}, config=config)
    logger.info("Executor Agent completed")
    return Command(
        goto=END,
    )

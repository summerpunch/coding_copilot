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
    """
    Executor Agent Node - Executes code changes precisely and safely.

    Tools (WRITE ACCESS):
    - read_file: Read files (for verification before/after changes)
    - write_file: Create new files (requires approval)
    - edit_file: Modify existing files (requires approval)
    - bash_execute: Run shell commands
    - grep_search: Verify changes were applied
    - glob_search: Find files for verification
    - write_todos: Update progress tracking (TODO: add this tool)

    Human-in-the-Loop middleware requires approval for write_file and edit_file
    to ensure safety of file modifications.
    """
    logger.info("start executor node")
    messages = state["messages"]

    prompt = template.get_local_prompt("executor_prompt")
    # Executor tools: Full WRITE access with safety gates
    executor_tools = [
        bash_execute,
        read_file,
        write_file,
        edit_file,
        glob_search,
        grep_search,
        # write_todos,  # TODO: Add once implemented
    ]

    agent = create_agent(
        model=llm_factory.factory(AgentConfig()),
        tools=executor_tools,
        system_prompt=prompt,
        middleware=[
            HumanInTheLoopMiddleware(
                interrupt_on={"write_file": True, "edit_file": True},
                description_prefix="Tool execution pending approval",
            )
        ])

    response = await agent.ainvoke({"messages": messages})

    # TODO: Extract execution result and update state
    return Command(
        goto=END,
    )

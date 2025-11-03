from typing import Literal
from langgraph.constants import END
from langgraph.types import Command
from src.engine.agents.llm_factory import llm_factory, AgentConfig
from src.engine.agents.supervisor import CopilotState
from src.engine.prompts import template
from langchain.agents import create_agent
from src.engine.tools.search import glob_search, grep_search
from src.engine.tools.file_ops import read_file, write_file, edit_file
from src.engine.tools.shell import bash_execute
import logging

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
        model=llm_factory.factory(AgentConfig()),
        tools=reviewer_tools,
        system_prompt=prompt
    )
    logger.info("Invoking Reviewer Agent...")
    response = await agent.ainvoke({"messages": messages})
    logger.info("Reviewer Agent completed")
    return Command(
        goto=END,
    )

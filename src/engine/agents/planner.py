from typing import Literal
from langgraph.constants import END
from langgraph.types import Command
from src.engine.agents.llm_factory import llm_factory, AgentConfig
from src.engine.agents.supervisor import CopilotState
from src.engine.prompts import template
from langchain.agents import create_agent
from src.engine.tools.search import glob_search, grep_search
from src.engine.tools.file_ops import read_file
# TODO: Import write_todos tool once created


async def planner_node(state: CopilotState) -> Command[
    Literal[
        "__end__"
    ]]:
    """
    Planner Agent Node - Creates strategic plans for complex tasks.

    Tools:
    - read_file: Read files to understand current implementation
    - grep_search: Search for code patterns
    - glob_search: Find files matching patterns
    - write_todos: Create todo list for progress tracking (TODO: add this tool)

    The Planner is READ-ONLY and focuses on strategic planning.
    """
    messages = state["messages"]
    planner_prompt = template.get_local_prompt("planner_prompt")

    # Planner tools: READ-ONLY + todo tracking
    planner_tools = [
        read_file,
        grep_search,
        glob_search,
        # write_todos,  # TODO: Add once implemented
    ]

    agent = create_agent(
        model=llm_factory.factory(AgentConfig()),
        tools=planner_tools,
        system_prompt=planner_prompt
    )
    response = await agent.ainvoke({"messages": messages})

    # TODO: Extract plan from response and update state
    # state["plan"] = extract_plan(response)
    # state["current_stage"] = "analyzing"

    return Command(
        goto=END,
    )

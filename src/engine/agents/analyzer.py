from typing import Literal
from langgraph.constants import END
from langgraph.types import Command
from src.engine.agents.llm_factory import llm_factory, AgentConfig
from src.engine.agents.supervisor import CopilotState
from src.engine.prompts import template
from langchain.agents import create_agent
from src.engine.tools.search import glob_search, grep_search
from src.engine.tools.file_ops import read_file


async def analyzer_node(state: CopilotState) -> Command[
    Literal[
        "__end__"
    ]]:
    """
    Analyzer Agent Node - Analyzes code and designs detailed solutions.

    Tools (READ-ONLY):
    - read_file: Read file contents
    - grep_search: Search for code patterns across codebase
    - glob_search: Find files matching patterns

    The Analyzer is strictly READ-ONLY and focuses on understanding
    and designing solutions, not executing them.
    """
    messages = state["messages"]
    prompt = template.get_local_prompt("analyzer_prompt")

    # Analyzer tools: READ-ONLY access only
    analyzer_tools = [
        read_file,
        grep_search,
        glob_search,
    ]

    agent = create_agent(
        model=llm_factory.factory(AgentConfig()),
        tools=analyzer_tools,
        system_prompt=prompt
    )
    response = await agent.ainvoke({"messages": messages})

    # TODO: Extract analysis and solution from response and update state
    # state["analysis"] = extract_analysis(response)
    # state["current_stage"] = "executing"

    return Command(
        goto=END,
    )

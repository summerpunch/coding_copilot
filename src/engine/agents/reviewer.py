from typing import Literal
from langgraph.constants import END
from langgraph.types import Command
from src.engine.agents.llm_factory import llm_factory, AgentConfig
from src.engine.agents.supervisor import CopilotState
from src.engine.prompts import template
from langchain.agents import create_agent
from src.engine.tools.search import glob_search, grep_search
from src.engine.tools.file_ops import read_file
from src.engine.tools.shell import bash_execute


async def reviewer_node(state: CopilotState) -> Command[
    Literal[
        "__end__"
    ]]:
    """
    Reviewer Agent Node - Reviews code quality and runs automated checks.

    Tools (READ-ONLY + VERIFICATION):
    - read_file: Read modified files to review code
    - grep_search: Search for patterns to verify changes
    - glob_search: Find related files
    - bash_execute: Run automated tools (linters, tests, security scans)

    The Reviewer is READ-ONLY (cannot modify files) but can run verification
    commands to check code quality, run tests, and scan for security issues.
    """
    messages = state["messages"]
    prompt = template.get_local_prompt("reviewer_prompt")

    # Reviewer tools: READ-ONLY + ability to run verification commands
    reviewer_tools = [
        read_file,
        grep_search,
        glob_search,
        bash_execute,  # Critical for running linters, tests, security scans
    ]

    agent = create_agent(
        model=llm_factory.factory(AgentConfig()),
        tools=reviewer_tools,
        system_prompt=prompt
    )
    response = await agent.ainvoke({"messages": messages})

    # TODO: Extract review feedback and update state
    # state["review_feedback"] = extract_review_feedback(response)
    # if review_feedback["approved"]:
    #     state["current_stage"] = "complete"
    #     state["is_complete"] = True
    # else:
    #     state["current_stage"] = "executing"  # Route back to Executor
    #     state["retry_count"] += 1

    return Command(
        goto=END,
    )

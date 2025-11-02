from typing import Literal
from langgraph.constants import END
from langgraph.types import Command
from src.engine.agents.llm_factory import llm_factory, AgentConfig
from src.engine.agents.supervisor import CopilotState
from src.engine.prompts import template
from langchain.agents import create_agent
from src.engine.tools.search import glob_search, grep_search
from src.engine.tools.file_ops import read_file


async def reviewer_node(state: CopilotState) -> Command[
    Literal[
        "__end__"
    ]]:
    messages = state["messages"]
    prompt = template.get_local_prompt("reviewer_prompt")
    agent = create_agent(
        model=llm_factory.factory(AgentConfig()),
        tools=[read_file, grep_search, glob_search],
        system_prompt=prompt
    )
    response = await agent.ainvoke({"messages": messages})
    return Command(
        goto=END,
    )

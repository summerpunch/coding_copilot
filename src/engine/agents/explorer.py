from typing import Literal

from langgraph.constants import END
from langgraph.types import Command
from src.engine.agents.supervisor import CopilotState
from src.engine.prompts import template
from langchain.agents import create_agent
from src.engine.agents.llm_factory import llm_factory, AgentConfig
from src.engine.tools.search import glob_search, grep_search
from src.engine.tools.file_ops import read_file

async def explorer_node(state: CopilotState) -> Command[
    Literal[
        "__end__"
    ]]:
    messages = state["messages"]
    prompt = template.get_local_prompt("explorer_prompt")
    agent = create_agent(
        model=llm_factory.factory(AgentConfig()),
        tools=[read_file, glob_search, grep_search],
        system_prompt=prompt
    )
    response = await agent.ainvoke({"messages": messages})
    return Command(
        goto=END,
    )

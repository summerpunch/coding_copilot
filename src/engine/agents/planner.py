from typing import Literal
from langgraph.constants import END
from langgraph.types import Command
from src.engine.agents.llm_factory import llm_factory, AgentConfig
from src.engine.agents.supervisor import CopilotState
from src.engine.prompts import template
from langchain.agents import create_agent


async def planner_node(state: CopilotState) -> Command[
    Literal[
        "__end__"
    ]]:
    messages = state["messages"]
    planner_prompt = template.get_local_prompt("planner_prompt")
    agent = create_agent(
        model=llm_factory.factory(AgentConfig()),
        tools=[],
        system_prompt=planner_prompt
    )
    response = await agent.ainvoke({"messages": messages})
    return Command(
        goto=END,
    )

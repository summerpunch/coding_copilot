from typing import Literal

from langchain.agents.middleware import ToolRetryMiddleware
from langgraph.constants import END
from langgraph.types import Command
from src.engine.agents.llm_factory import llm_factory, AgentConfig
from src.engine.agents.supervisor import CopilotState
from src.engine.prompts import template
from langchain.agents import create_agent
from src.engine.tools.search import glob_search, grep_search
from src.engine.tools.file_ops import read_file
from src.engine.mcp import mcp_client


async def planner_node(state: CopilotState) -> Command[
    Literal[
        "__end__"
    ]]:
    messages = state["messages"]
    planner_prompt = template.get_local_prompt("planner_prompt")

    web_search_tools = await mcp_client.get_tools('web_search')
    planner_tools = [
        read_file,
        grep_search,
        glob_search,
    ]

    if web_search_tools:
        planner_tools.extend(web_search_tools)

    agent = create_agent(
        model=llm_factory.factory(AgentConfig()),
        tools=planner_tools,
        system_prompt=planner_prompt,
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
    response = await agent.ainvoke({"messages": messages})
    return Command(
        goto=END,
    )

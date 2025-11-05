from typing import Literal
import logging

from langchain.agents.middleware import ToolRetryMiddleware
from langchain_core.messages import AIMessage
from langgraph.constants import END
from langgraph.types import Command
from src.engine.agents.llm_factory import llm_factory, AgentConfig
from src.engine.agents.supervisor import CopilotState
from src.engine.prompts import template
from langchain.agents import create_agent
from src.engine.tools.search import glob_search, grep_search
from src.engine.tools.file_ops import read_file, write_file, edit_file
from src.engine.tools.todos import write_todos
from src.engine.tools.shell import bash_execute
from src.engine.mcp import mcp_client

logger = logging.getLogger(__name__)


async def planner_node(state: CopilotState) -> Command[
    Literal[
        "__end__"
    ]]:
    """
    Plan 模式的核心节点 - 负责规划任务并逐项执行

    工作流程：
    1. 分析用户任务，创建 todo 列表
    2. 逐项执行 todos
    3. 每完成一项更新状态
    4. 所有 todo 完成后结束
    """
    logger.info("Starting Planner Agent - Plan 模式任务规划与执行")
    messages = state["messages"]
    planner_prompt = template.get_local_prompt("planner_prompt")

    # Plan 模式需要完整的工具集：分析 + 执行
    web_search_tools = await mcp_client.get_tools('web_search')
    planner_tools = [
        # 分析工具
        read_file,
        grep_search,
        glob_search,
        # 执行工具
        write_file,
        edit_file,
        bash_execute,
        # Todo 管理工具
        write_todos,
    ]

    if web_search_tools:
        planner_tools.extend(web_search_tools)

    agent = create_agent(
        model=llm_factory.factory(AgentConfig()),
        tools=planner_tools,
        system_prompt=planner_prompt,
        middleware=[
            ToolRetryMiddleware(
                max_retries=3,
                backoff_factor=2.0,
                initial_delay=1.0,
                max_delay=60.0,
                jitter=True,
            )
        ]
    )

    logger.info("Invoking Planner Agent...")
    response = await agent.ainvoke({"messages": messages})
    logger.info("Planner Agent completed")

    return Command(
        goto=END,
    )

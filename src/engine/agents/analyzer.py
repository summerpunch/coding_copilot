from typing import Literal
from langgraph.constants import END
from langgraph.types import Command
from src.engine.agents.llm_factory import llm_factory, AgentConfig
from src.engine.agents.supervisor import CopilotState
from src.engine.prompts import template
from langchain.agents import create_agent
from src.engine.tools.search import glob_search, grep_search
from src.engine.tools.file_ops import read_file
import logging

logger = logging.getLogger(__name__)

async def analyzer_node(state: CopilotState) -> Command[
    Literal[
        "__end__"
    ]]:
    logger.info("Starting Analyzer Agent - 代码分析与方案设计")
    messages = state["messages"]
    prompt = template.get_local_prompt("analyzer_prompt")
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
    logger.info("Invoking Analyzer Agent...")
    response = await agent.ainvoke({"messages": messages})
    logger.info("Analyzer Agent completed")
    return Command(
        goto=END,
    )

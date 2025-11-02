from typing import Literal

from langchain.agents.middleware import HumanInTheLoopMiddleware
from langgraph.constants import END
from langgraph.types import Command
from src.engine.prompts import template
from langchain.agents import create_agent
from src.engine.agents.llm_factory import llm_factory, AgentConfig

from src.engine.agents.supervisor import CopilotState
from src.engine.tools.shell import bash_execute
from src.engine.tools.search import glob_search, grep_search
from src.engine.tools.file_ops import read_file, write_file, edit_file


async def executor_node(state: CopilotState) -> Command[
    Literal[
        "__end__"
    ]]:
    messages = state["messages"]
    prompt = template.get_local_prompt("executor_prompt")
    agent = create_agent(
        model=llm_factory.factory(AgentConfig()),
        tools=[
            bash_execute,
            read_file,
            write_file,
            edit_file,
            glob_search,
            grep_search
        ],
        middleware=[
            HumanInTheLoopMiddleware(
                tool_configs={
                    "write_file": {
                        "require_approval": True,
                        "description": "文件写入操作需要批准",
                    },
                    "edit_file": {
                        "require_approval": True,
                        "description": "文件编辑操作需要批准",
                    },
                },
                message_prefix="工具执行等待批准",
            ),
        ],
        system_prompt=prompt
    )
    response = await agent.ainvoke({"messages": messages})
    return Command(
        goto=END,
    )

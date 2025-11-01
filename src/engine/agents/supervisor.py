from langchain.agents import AgentState, create_agent
from typing import (
    Annotated
)
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph_sdk.schema import Context

from src.engine.agents.llm_factory import llm_factory, AgentConfig
from langgraph.constants import START
from langgraph.graph import StateGraph
from langgraph_supervisor import create_supervisor
import os
import asyncio
import threading

_thread_lock = threading.Lock()
_async_lock = asyncio.Lock()


async def get_supervisor_instance():
    async with _async_lock:
        with _thread_lock:
            if supervisor_graph.get_graph():
                return supervisor_graph.get_graph()
            db_path = os.path.join(os.getcwd(), "copilot_checkpoints.sqlite")
            _checkpointer_ctx = AsyncSqliteSaver.from_conn_string(db_path)
            supervisor_graph.checkpointer_ctx = _checkpointer_ctx
            _checkpointer = await _checkpointer_ctx.__aenter__()
            supervisor_graph.checkpointer = _checkpointer
            graph = initializer_supervisor_graph(checkpointer=_checkpointer)
            supervisor_graph.graph = graph
            return graph


class SupervisorGraph:
    def __init__(self):
        self.checkpointer = None
        self.checkpointer_ctx = None
        self.graph = None

    def get_checkpointer(self) -> str:
        return self.checkpointer

    def get_checkpointer_ctx(self) -> str:
        return self.checkpointer_ctx

    def get_graph(self) -> str:
        return self.graph


def initializer_supervisor_graph(checkpointer: AsyncSqliteSaver):
    llm = llm_factory.factory(AgentConfig())
    planner = initializer_planner_graph(checkpointer=checkpointer)
    executor = initializer_executor_graph(checkpointer=checkpointer)
    explorer = initializer_explorer_graph(checkpointer=checkpointer)
    supervisor = create_supervisor(
        model=llm,
        agents=[
            planner,
            executor,
            explorer,
        ],
        prompt="",
        tools=[],
        add_handoff_back_messages=False
    )
    return supervisor.compile(
        checkpointer=checkpointer
    )


def initializer_planner_graph(checkpointer=None):
    builder = StateGraph(CopilotState)
    from src.engine.agents.planner import planner_node
    builder.add_edge(START, "planner_node")
    builder.add_node("planner_node", planner_node)
    return builder.compile(name="planner_agent",
                           checkpointer=checkpointer)


def initializer_executor_graph(checkpointer=None):
    builder = StateGraph(CopilotState)
    from src.engine.agents.executor import executor_node
    builder.add_edge(START, "executor_node")
    builder.add_node("executor_node", executor_node)
    return builder.compile(name="executor_agent",
                           checkpointer=checkpointer)


def initializer_explorer_graph(checkpointer=None):
    builder = StateGraph(CopilotState)
    from src.engine.agents.explorer import explorer_node
    builder.add_edge(START, "explorer_node")
    builder.add_node("explorer_node", explorer_node)
    return builder.compile(name="explorer_agent",
                           checkpointer=checkpointer)


class CopilotState(AgentState):
    thread_id: Annotated[str, lambda x, y: y]


supervisor_graph = SupervisorGraph()

if __name__ == "__main__":
    print(1)
    # print(initializer_supervisor_graph().get_graph(xray=True).draw_mermaid())
    messages = [
        HumanMessage(content="用一句话解释量子计算是什么。")
    ]
    agent = create_agent(
        model=llm_factory.factory(AgentConfig()),
        tools=[],
    )
    # {"messages": [{"role": "user", "content": "用一句话解释量子计算是什么"}]},

    # ✅ 同步流式输出
    for chunk in agent.stream(
            {"messages": [{"role": "user", "content": "用一句话解释量子计算是什么"}]},
            context=Context(user_role="expert")
    ):
        print(chunk)

from langchain.agents import AgentState, create_agent
from typing import (
    Annotated
)
from langchain_core.messages import HumanMessage
from langgraph_sdk.schema import Context

from src.engine.agents.llm_factory import llm_factory, AgentConfig
from langgraph.constants import START
from langgraph.graph import StateGraph
from langgraph.checkpoint.memory import InMemorySaver
from langgraph_supervisor import create_supervisor

def initializer_supervisor_graph():
    checkpointer = InMemorySaver()
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


if __name__ == "__main__":
    print(1)
    print(initializer_supervisor_graph().get_graph(xray=True).draw_mermaid())
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

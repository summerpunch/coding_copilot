from typing import (
    Annotated, Optional, Literal
)
from langchain.agents.middleware import SummarizationMiddleware, ToolRetryMiddleware
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.pregel import Pregel

from src.engine.prompts import template
from src.engine.agents.llm_factory import llm_factory, AgentConfig
from langgraph.constants import START, END
from langgraph.graph import StateGraph, add_messages, MessagesState
from src.engine.agents.supervisor_sdk.supervisor import create_supervisor
import os
import asyncio
import threading
from src.engine.mcp import mcp_client

_thread_lock = threading.Lock()
_async_lock = asyncio.Lock()


async def get_supervisor_instance(mode: str):
    async with _async_lock:
        with _thread_lock:
            if mode == 'edit':
                if supervisor_graph.get_edit_graph():
                    return supervisor_graph.get_edit_graph()
                if supervisor_graph.checkpointer is None:
                    await initializer_checkpointer()
                graph = await initializer_supervisor_graph(checkpointer=supervisor_graph.checkpointer)
                supervisor_graph.edit_graph = graph
                return graph
            if mode == 'plan':
                if supervisor_graph.get_plan_graph():
                    return supervisor_graph.get_plan_graph()
                if supervisor_graph.checkpointer is None:
                    await initializer_checkpointer()
                graph = await initializer_supervisor_plan_graph(checkpointer=supervisor_graph.checkpointer)
                supervisor_graph.plan_graph = graph
                return graph
            if mode == 'yolo':
                if supervisor_graph.get_yolo_graph():
                    return supervisor_graph.get_yolo_graph()
                if supervisor_graph.checkpointer is None:
                    await initializer_checkpointer()
                graph = await initializer_supervisor_graph(checkpointer=supervisor_graph.checkpointer, mode=mode)
                supervisor_graph.yolo_graph = graph
                return graph


class SupervisorGraph:
    def __init__(self):
        self.checkpointer = None
        self.checkpointer_ctx = None
        self.edit_graph = None
        self.plan_graph = None
        self.yolo_graph = None

    def get_checkpointer(self) -> str:
        return self.checkpointer

    def get_checkpointer_ctx(self) -> str:
        return self.checkpointer_ctx

    def get_edit_graph(self):
        return self.edit_graph

    def get_plan_graph(self):
        return self.plan_graph

    def get_yolo_graph(self):
        return self.yolo_graph


async def initializer_checkpointer():
    db_path = os.path.join(os.getcwd(), "copilot_checkpoints.sqlite")
    _checkpointer_ctx = AsyncSqliteSaver.from_conn_string(db_path)
    supervisor_graph.checkpointer_ctx = _checkpointer_ctx
    _checkpointer = await _checkpointer_ctx.__aenter__()
    supervisor_graph.checkpointer = _checkpointer


async def initializer_supervisor_plan_graph(checkpointer: Optional[AsyncSqliteSaver] = None):
    return await initializer_supervisor(agents=[
        initializer_planner_graph(checkpointer=checkpointer),
        initializer_executor_graph(checkpointer=checkpointer),
        initializer_analyzer_graph(checkpointer=checkpointer),
        initializer_reviewer_graph(checkpointer=checkpointer),
    ], checkpointer=checkpointer)


async def initializer_supervisor_graph(checkpointer: Optional[AsyncSqliteSaver] = None, mode: str = 'edit'):
    return await initializer_supervisor(agents=[
        initializer_executor_graph(checkpointer=checkpointer, mode=mode),
        initializer_analyzer_graph(checkpointer=checkpointer),
        initializer_reviewer_graph(checkpointer=checkpointer),
    ], checkpointer=checkpointer)


async def initializer_supervisor(agents: list[Pregel], checkpointer: Optional[AsyncSqliteSaver] = None):
    llm = llm_factory.factory(AgentConfig())
    supervisor_prompt = template.get_local_prompt("supervisor_prompt")
    web_search_tools = await mcp_client.get_tools('web_search')
    supervisor = create_supervisor(
        model=llm,
        agents=agents,
        prompt=supervisor_prompt,
        tools=web_search_tools,
        output_mode="full_history",
        middleware=[
            SummarizationMiddleware(
                model=llm,
                max_tokens_before_summary=10000,  # 25k tokens 触发消息压缩
                messages_to_keep=40  # 保留最近 40 条消息
            ),
            ToolRetryMiddleware(
                max_retries=3,  # 最多重试3次
                backoff_factor=2.0,  # 指数退避倍数
                initial_delay=1.0,  # 初始延迟1秒
                max_delay=60.0,  # 最大延迟60秒
                jitter=True,  # 添加随机抖动(±25%)
            ),
        ],
        add_handoff_messages=True,
        add_handoff_back_messages=True
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


def initializer_executor_graph(checkpointer=None, mode: str = 'edit'):
    builder = StateGraph(CopilotState)
    builder.add_edge(START, "executor_node")
    if mode and mode == 'yolo':
        from src.engine.agents.executor import executor_yolo_node
        builder.add_node("executor_node", executor_yolo_node)
    else:
        from src.engine.agents.executor import executor_node
        builder.add_node("executor_node", executor_node)
    return builder.compile(name="executor_agent",
                           checkpointer=checkpointer)


def initializer_analyzer_graph(checkpointer=None):
    builder = StateGraph(CopilotState)
    from src.engine.agents.analyzer import analyzer_node
    builder.add_edge(START, "analyzer_node")
    builder.add_node("analyzer_node", analyzer_node)
    return builder.compile(name="analyzer_agent",
                           checkpointer=checkpointer)


def initializer_reviewer_graph(checkpointer=None):
    builder = StateGraph(CopilotState)
    from src.engine.agents.reviewer import reviewer_node
    builder.add_edge(START, "reviewer_node")
    builder.add_node("reviewer_node", reviewer_node)
    return builder.compile(name="reviewer_agent",
                           checkpointer=checkpointer)


class CopilotState(MessagesState):
    """
    Complete state structure for Copilot workflow.

    Supports two execution modes:
    1. Standard Mode: Supervisor → Analyzer → Executor → Reviewer
    2. Planner Mode: Supervisor → Planner → Analyzer → Executor → Reviewer
    """
    # Core conversation state
    # user_input: str
    # has_all_allowed: Annotated[bool, lambda x, y: y] = False
    # thread_id: Annotated[str, lambda x, y: y] = ''

    # Execution mode control
    # planner_mode: bool  # True = use Planner, False = direct to Analyzer
    # current_stage: Literal[
    #     "init",  # Initial state
    #     "planning",  # Planner is creating high-level plan
    #     "analyzing",  # Analyzer is analyzing and designing solution
    #     "executing",  # Executor is applying changes
    #     "reviewing",  # Reviewer is checking code
    #     "complete",  # Task completed successfully
    #     "failed"  # Task failed
    # ]
    #
    # # Agent outputs and intermediate results
    # plan: Optional[dict]  # From Planner: {"steps": [...], "complexity": "simple|medium|complex"}
    # analysis: Optional[dict]  # From Analyzer: {"problem": "...", "solution": {...}, "changes": [...]}
    # execution_result: Optional[dict]  # From Executor: {"files_changed": [...], "success": bool}
    # review_feedback: Optional[dict]  # From Reviewer: {"approved": bool, "issues": [...], "suggestions": [...]}
    #
    # # Todo tracking (for Planner mode)
    # todos: Annotated[list[dict], lambda x, y: y if y else x]  # List of todo items with status
    # current_step: Optional[int]  # Current step index in plan
    #
    # # Routing and control flow
    # next_agent: Optional[str]  # Which agent to route to next
    # is_complete: bool  # Whether the entire workflow is complete
    # requires_approval: bool  # Whether human approval is needed
    #
    # # Error handling
    # error_message: Optional[str]  # Error information if something fails
    # retry_count: int  # Number of retries attempted
    #
    # # Context and metadata
    # task_type: Optional[Literal["simple", "complex", "refactor", "debug", "feature"]]
    # risk_level: Optional[Literal["low", "medium", "high"]]  # For determining approval requirements


supervisor_graph = SupervisorGraph()

if __name__ == "__main__":
    print(initializer_supervisor_graph().get_graph(xray=True).draw_mermaid())

from typing import (
    Annotated, Optional, Literal
)
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from src.engine.prompts import template
from src.engine.agents.llm_factory import llm_factory, AgentConfig
from langgraph.constants import START, END
from langgraph.graph import StateGraph, add_messages, MessagesState
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


def initializer_supervisor_graph(checkpointer: Optional[AsyncSqliteSaver] = None):
    llm = llm_factory.factory(AgentConfig())
    planner = initializer_planner_graph(checkpointer=checkpointer)
    executor = initializer_executor_graph(checkpointer=checkpointer)
    analyzer = initializer_analyzer_graph(checkpointer=checkpointer)
    reviewer = initializer_reviewer_graph(checkpointer=checkpointer)

    supervisor_prompt = template.get_local_prompt("supervisor_prompt")

    supervisor = create_supervisor(
        model=llm,
        agents=[
            planner,
            executor,
            analyzer,
            reviewer,
        ],
        prompt=supervisor_prompt,
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


class SessionAutoApprove:
    def __init__(self):
        self._session_auto_approve = {}

    def clear_auto_approve(self, thread_id: str):
        del self._session_auto_approve[thread_id]

    def has_auto_approve(self, thread_id: str):
        return self._session_auto_approve.get(thread_id, False)

    def set_auto_approve(self, thread_id: str):
        self._session_auto_approve[thread_id] = True


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
session_auto_approve = SessionAutoApprove()

if __name__ == "__main__":
    print(initializer_supervisor_graph().get_graph(xray=True).draw_mermaid())

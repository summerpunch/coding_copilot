from typing import Dict, Any, Optional

from langchain_core.messages import ToolMessage

skip = [
    'call_model',
    'agent',
    'tools',
    'Prompt',
    'post_model_hook',
    'post_model_hook_router',
    'post_model_hook_func',
    'RunnableSequence',
    'ChatPromptTemplate',
    'should_continue',
    'ChatLiteLLMRouter',
    'StrOutputParser']

async def get_run_id(event: Dict[str, Any]) -> str:
    return await get_value("run_id", event)

async def get_value(key: str, event: Dict[str, Any]) -> str:
    return str(event.get(key, ""))

async def execute(event: Dict[str, Any], thread_id: str) -> Optional[list[str]]:
    name = event.get("name", "")
    if name in skip:
        return None
    event_type = event.get("event", "")
    run_id = await get_run_id(event)
    event_type = event.get("event", "")
    metadata = event.get("metadata", {}).get("langgraph_node")
    match event_type:
        case "on_chat_model_stream":
            text = event.get("data")["chunk"].text
            if text:
                return [text]
        case "on_tool_end":
            return await on_tool_copilot(event)

async def on_tool_copilot(event: Dict[str, Any]) -> Optional[list[str]]:
    output_value = event.get("data", {}).get("output")
    if isinstance(output_value, ToolMessage):
        output_value = output_value.content
    return [output_value]

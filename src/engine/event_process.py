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
    return await get_value(key="run_id", event=event)


async def get_name(event: Dict[str, Any]) -> str:
    return await get_value(key="name", event=event)


async def get_value(key: str, event: Dict[str, Any]) -> str:
    return str(event.get(key, ""))


async def execute(event: Dict[str, Any], thread_id: str) -> Optional[list[str]]:
    name = await get_name(event)
    if name in skip:
        return None
    print(event)
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
        case "on_chain_stream":
            return await on_chain_stream_copilot(event)


async def on_chain_stream_copilot(event: Dict[str, Any]) -> Optional[list[str]]:
    name = await get_name(event)
    if 'LangGraph' == name:
        data = event.get('data', {}).get('chunk', {}).get('__interrupt__', [])
        if data and isinstance(data, tuple):
            first_value = data[0].value
            review_configs = first_value.get('review_configs', [])
            if review_configs and isinstance(review_configs, list):
                first_review = review_configs[0]
                action_name = first_review.get('action_name')
                allowed_decisions = first_review.get('allowed_decisions', [])
                allowed_decisions.append('auto_approve')
                return [review_configs[0]]
                # return [{'allowed_decisions': allowed_decisions, "action_name": action_name}]


async def on_tool_copilot(event: Dict[str, Any]) -> Optional[list[str]]:
    name = await get_name(event)
    if 'transfer_to_' in name:
        return None
    output_value = event.get("data", {}).get("output")
    if isinstance(output_value, ToolMessage):
        output_value = output_value.content
    return [output_value]

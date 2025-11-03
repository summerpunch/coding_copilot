import json

from fastapi import APIRouter, Form
from sse_starlette import EventSourceResponse

from src.engine.chat import run_agent

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/")
async def chat(
        thread_id: str = Form(..., description="线程ID"),
        message: str = Form(..., description="message")
):
    async def event_agent_generator():
        async for event in run_agent(
                thread_id=thread_id,
                message=message
        ):
            yield json.dumps({"type": "data", "data": event}, ensure_ascii=False)

    return EventSourceResponse(
        event_agent_generator(),
        media_type="text/event-stream",
        sep="\n",
    )

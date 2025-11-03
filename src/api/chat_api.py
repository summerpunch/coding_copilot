import json

from fastapi import APIRouter, Form
from sse_starlette import EventSourceResponse

from src.engine.chat import run_agent

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/")
async def chat(
        thread_id: str = Form(..., description="线程ID"),
        message: str = Form(..., description="message"),
        decisions_type: str = Form(None, description="decisions_type")
):
    async def event_agent_generator():
        async for event in run_agent(
                thread_id=thread_id,
                message=message,
                decisions_type=decisions_type
        ):
            yield json.dumps({"type": "data", "data": event}, ensure_ascii=False)

    return EventSourceResponse(
        event_agent_generator(),
        media_type="text/event-stream",
        sep="\n",
    )

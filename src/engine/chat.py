import logging
import asyncio
from src.engine import event_process
from src.engine.agents import supervisor

logger = logging.getLogger(__name__)

async def run_agent(
        message: str,
        thread_id: str,
):
    logger.info(f"thread_id:{thread_id}, 准备开始执行工作流，用户输入: {message}")
    config = {
        "configurable": {
            "thread_id": thread_id,
        }
    }

    async def builder_param():
        return {
            "messages": [message],
            "thread_id": thread_id,
        }

    graph = supervisor.get_supervisor_instance()
    async for event in graph.astream_events(
            await builder_param(),
            config=config
    ):
        process_result = await event_process.execute(event=event, thread_id=thread_id)
        if process_result:
            for result in process_result:
                yield result

async def main2():
    async for output in run_agent("用一句话解释量子计算是什么", "111"):
        print(output)


if __name__ == "__main__":
    asyncio.run(main2())

import logging
import asyncio

from src.engine import event_process
from src.engine.agents import supervisor
from langgraph.types import Command

logger = logging.getLogger(__name__)

mapping_map = {
    '1': 'approve',
    '2': 'reject',
}


async def run_agent(
        message: str,
        thread_id: str,
        mode: str = "edit",
):
    """Run the supervisor agent with the given message.

    Args:
        message: User's input message
        thread_id: Thread ID for session management
        mode: Operating mode - "edit" (default) or "plan"
    """
    # print(f"thread_id:{thread_id}, mode:{mode}, 准备开始执行工作流，用户输入: {message}")
    logger.info(f"thread_id:{thread_id}, mode:{mode}, 准备开始执行工作流，用户输入: {message}")
    config = {
        "configurable": {
            "thread_id": thread_id,
        },
        "recursion_limit": 50,
    }

    async def builder_param():
        if await has_interrupt(graph, thread_id):
            return Command(
                resume={
                    'decisions': [
                        {
                            'type': mapping_map.get(message, 'reject'),
                        }
                    ]
                },
                update={
                    'thread_id': thread_id,
                }
            )
        return {
            "messages": [message],
        }

    graph = await supervisor.get_supervisor_instance(mode=mode)
    async for event in graph.astream_events(
            await builder_param(),
            config=config
    ):
        process_result = await event_process.execute(event=event, thread_id=thread_id)
        if process_result:
            for result in process_result:
                yield result


async def has_interrupt(graph, thread_id):
    try:
        config = {"configurable": {"thread_id": thread_id}}
        state = await graph.aget_state(config)
        if state.interrupts:
            return True
        return False
    except Exception as e:
        logger.error(f"检查线程中断状态时出错: {e}")
        return False


async def main2():
    async for output in run_agent("用一句话解释量子计算是什么", "111"):
        print(output)


if __name__ == "__main__":
    asyncio.run(main2())

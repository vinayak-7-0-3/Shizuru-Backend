import asyncio
from typing import Callable, Awaitable, Any

class AsyncQueueProcessor:
    def __init__(self, handler: Callable[[Any], Awaitable[None]], rate_limit: float = 10.0):
        """
        Args:
            handler: The async function to process each item
            rate_limit: Maximum items per second (default 10)
        """
        self.queue = asyncio.Queue()
        self.handler = handler
        self.processing_task = None
        self.rate_limit = rate_limit
        self.delay = 1.0 / rate_limit if rate_limit > 0 else 0

    def start(self):
        if not self.processing_task or self.processing_task.done():
            self.processing_task = asyncio.create_task(self._process())

    async def _process(self):
        while True:
            item = await self.queue.get()
            if item is None:
                break  # stop signal
            try:
                await self.handler(item)
            except Exception as e:
                print(f"Error processing item: {e}")
            self.queue.task_done()
            
            # Rate limiting delay
            if self.delay > 0:
                await asyncio.sleep(self.delay)

    async def add_item(self, item: Any):
        await self.queue.put(item)
        self.start()

    async def add_items(self, items: list[Any]):
        for item in items:
            await self.add_item(item)

    async def stop(self):
        await self.queue.put(None)
        if self.processing_task:
            await self.processing_task

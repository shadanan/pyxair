import asyncio
from collections import namedtuple
from .client import XAir
from .scanner import XAirScanner

XAirTask = namedtuple("XAirTask", ["xinfo", "xair", "task"])


class XAirTaskManager:
    def __init__(self):
        self._xairs = {}

    def get_xair(self, xinfo):
        return self._xairs[xinfo].xair

    def list_xairs(self):
        return list(self._xairs)

    async def start(self):
        scanner = XAirScanner()
        with scanner.subscribe() as queue:
            asyncio.create_task(scanner.start())
            while True:
                xinfos = await queue.get()

                for xinfo in list(self._xairs):
                    if xinfo not in xinfos:
                        task = self._xairs[xinfo].task
                        del self._xairs[xinfo]
                        task.cancel()
                        await task

                for xinfo in xinfos:
                    if xinfo not in self._xairs:
                        xair = XAir(xinfo)
                        xair_task = asyncio.create_task(xair.start())
                        self._xairs[xinfo] = XAirTask(xinfo, xair, xair_task)

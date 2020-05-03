import asyncio
import contextlib
import logging
from collections import namedtuple
from .client import XAir
from .scanner import XAirScanner

logger = logging.getLogger("pyxair")
XAirTask = namedtuple("XAirTask", ["xinfo", "xair", "task"])


class XAirTaskManager:
    def __init__(self):
        self._xairs = {}
        self._scanner = XAirScanner()
        self._subscriptions = set()

    def get_xair(self, xinfo):
        return self._xairs[xinfo].xair

    def list_xairs(self):
        return list(self._xairs.keys())

    @contextlib.contextmanager
    def subscribe(self):
        try:
            queue = asyncio.Queue()
            self._subscriptions.add(queue)
            logger.info("Subscribed: %s", queue)
            yield queue
        finally:
            self._subscriptions.remove(queue)
            logger.info("Unsubscribed: %s", queue)

    def _notify(self):
        logger.info("XAirs: %s", self._xairs)
        for queue in self._subscriptions:
            queue.put_nowait(self.list_xairs())

    async def start(self):
        with self._scanner.subscribe() as queue:
            scanner_task = asyncio.create_task(self._scanner.start())
            while True:
                notify = False
                try:
                    xinfos = await queue.get()
                except asyncio.CancelledError:
                    tasks = [scanner_task] + [t.task for t in self._xairs.values()]
                    for task in tasks:
                        task.cancel()
                    await asyncio.gather(*tasks)
                    break

                for xinfo in list(self._xairs):
                    if xinfo not in xinfos:
                        task = self._xairs[xinfo].task
                        del self._xairs[xinfo]
                        task.cancel()
                        await task
                        notify = True

                for xinfo in xinfos:
                    if xinfo not in self._xairs:
                        xair = XAir(xinfo)
                        xair_task = asyncio.create_task(xair.start())
                        self._xairs[xinfo] = XAirTask(xinfo, xair, xair_task)
                        notify = True

                if notify:
                    self._notify()

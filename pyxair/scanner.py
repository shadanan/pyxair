import asyncio
import contextlib
import logging
import socket
from datetime import datetime, timedelta
from .osc import encode, decode, OscMessage, XInfo
from .task import XAirTask

logger = logging.getLogger(__name__)


class XAirScanner:
    def __init__(self, connect=False, timeout=30):
        self._connect = connect
        self._timeout = timeout
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, True)
        self._sock.setblocking(False)
        self._xinfos = {}
        self._previous_xinfos = set()
        self._subscriptions = set()

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
        current_xinfos = self.list()
        if current_xinfos != self._previous_xinfos:
            logger.info("XInfos: %s", current_xinfos)
            for queue in self._subscriptions:
                queue.put_nowait(current_xinfos)
        self._previous_xinfos = current_xinfos

    def get(self, xinfo):
        return self._xinfos[xinfo].get_xair()

    def list(self):
        return set(self._xinfos.keys())

    async def start(self, broadcast_period=10):
        loop = asyncio.get_running_loop()

        async def refresh():
            xinfo = OscMessage("/xinfo", [])
            while True:
                stale_xinfos = {
                    stale_xinfo
                    for stale_xinfo, xair_task in self._xinfos.items()
                    if xair_task.is_stale()
                }
                for stale_xinfo in stale_xinfos:
                    if self._connect:
                        await self._xinfos[stale_xinfo].cancel()
                    del self._xinfos[stale_xinfo]
                    self._notify()
                logger.debug("Broadcasting: %s", xinfo)
                self._sock.sendto(encode(xinfo), ("<broadcast>", 10024))
                await asyncio.sleep(broadcast_period)

        def receive():
            dgram, server = self._sock.recvfrom(512)
            args = decode(dgram).arguments
            xinfo = XInfo(server[0], server[1], args[1], args[2], args[3])
            logger.debug("Detected: %s", xinfo)
            if xinfo not in self._xinfos:
                self._xinfos[xinfo] = XAirTask(xinfo, self._connect)
            else:
                self._xinfos[xinfo].refresh()
            self._notify()

        refresh_task = loop.create_task(refresh())
        loop.add_reader(self._sock, receive)
        try:
            await refresh_task
        except asyncio.CancelledError:
            pass


async def auto_detect() -> XInfo:
    monitor = XAirScanner()
    with monitor.subscribe() as queue:
        task = asyncio.create_task(monitor.start())
        while True:
            xinfos = await queue.get()
            if len(xinfos) > 0:
                break
        task.cancel()
        await task
        return xinfos.pop()


if __name__ == "__main__":
    logging.basicConfig(
        format="%(asctime)s - (%(name)s)[%(levelname)s] - %(message)s",
        level=logging.DEBUG,
    )

    from .client import XAir

    async def start():
        xair = XAir(await auto_detect())
        xair.enable_meter(2)
        await xair.start()

    asyncio.run(start())

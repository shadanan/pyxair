import asyncio
import contextlib
import logging
import socket
import struct
from collections import defaultdict, namedtuple
from datetime import datetime, timedelta
from typing import Any, Awaitable, Callable, List, Set

from .osc import OscMessage, decode, encode

logger = logging.getLogger(__name__)


class XAir:
    def __init__(self, xinfo):
        self._xinfo = xinfo
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setblocking(False)
        self._cache = {}
        self._meters = {}
        self._subscriptions = set()

    @contextlib.contextmanager
    def subscribe(self, meters=True):
        try:
            queue = asyncio.Queue()
            self._subscriptions.add((queue, meters))
            logger.debug("Subscribed (meters=%s): %s", meters, queue)
            yield queue
        finally:
            self._subscriptions.remove((queue, meters))
            logger.debug("Unsubscribed (meters=%s): %s", meters, queue)

    async def get(self, address, timeout=1) -> OscMessage:
        if address in self._cache:
            return self._cache[address]
        with self.subscribe(meters=False) as queue:
            self._send(OscMessage(address, []))
            attempt = 0
            while True:
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=timeout)
                    if message.address == address:
                        logger.info("Get: %s", message)
                        return message
                except asyncio.TimeoutError:
                    attempt += 1
                    logger.log(
                        logging.WARN if attempt < 3 else logging.ERROR,
                        "Failed to Get (timeout=%ds, attempt=%d/3): %s",
                        timeout,
                        attempt,
                        address,
                    )
                    if attempt < 3:
                        self._send(OscMessage(address, []))
                    else:
                        raise

    def put(self, address, arguments):
        message = OscMessage(address, arguments)
        logger.info("Put: %s", message)
        self._cache[address] = message
        self._send(message)

    def enable_meter(self, id, channel=None):
        logger.info("Enabled Meter: %d (%s)", id, channel)
        self._meters[(id, channel)] = [f"/meters/{id}"]
        if channel is not None:
            self._meters[(id, channel)].append(channel)

    def disable_meter(self, id, channel=None):
        logger.info("Disabled Meter: %d (%s)", id, channel)
        del self._meters[(id, channel)]

    async def start(self):
        logger.info("Monitoring: %s", self._xinfo)
        loop = asyncio.get_running_loop()

        async def refresh():
            while True:
                self._send(OscMessage("/xremote", []))
                for arguments in self._meters.values():
                    self._send(OscMessage("/meters", arguments))
                await asyncio.sleep(8)

        async def cache():
            with self.subscribe(meters=False) as queue:
                while True:
                    message = await queue.get()
                    self._cache[message.address] = message

        def receive():
            message = decode(self._sock.recv(512))
            if message.address.startswith("/meters/"):
                data = message.arguments[0]
                message = OscMessage(
                    message.address,
                    struct.unpack(f"<{struct.unpack('<i', data[0:4])[0]}h", data[4:]),
                )
            else:
                logger.info("Received: %s", message)
            self._notify(message)

        refresh_task = asyncio.create_task(refresh())
        cache_task = asyncio.create_task(cache())
        loop.add_reader(self._sock, receive)
        try:
            await asyncio.gather(refresh_task, cache_task)
        except asyncio.CancelledError:
            pass

    def _send(self, message: OscMessage):
        logger.debug("Sending: %s", message)
        self._sock.sendto(encode(message), (self._xinfo.ip, self._xinfo.port))

    def _notify(self, message: OscMessage):
        for queue, meters in self._subscriptions:
            if meters or not message.address.startswith("/meters/"):
                queue.put_nowait(message)

    def __repr__(self):
        return f"XAir({repr(self._xinfo)})"

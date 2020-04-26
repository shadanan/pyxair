import asyncio
import contextlib
import logging
import socket
import struct
import pythonosc.osc_message
import pythonosc.osc_message_builder
from collections import defaultdict, namedtuple
from datetime import datetime, timedelta
from typing import Any, Awaitable, Callable, List, Set


logger = logging.getLogger("pyxair")


class MeterLoggingFilter(logging.Filter):
    def __init__(self):
        self.last_log_time = datetime.min
        self.meter_counters = defaultdict(int)

    def filter(self, record):
        if record.msg == "Received: %s":
            message = record.args[0]
            if message.address.startswith("/meters/"):
                self.meter_counters[message.address] += 1
                now = datetime.now()
                if now - self.last_log_time > timedelta(seconds=10):
                    self.last_log_time = now
                    logger.debug(
                        "Received: %d OscMessages for %s",
                        self.meter_counters[message.address],
                        message.address,
                    )
                return False
        return True


logger.addFilter(MeterLoggingFilter())


OscMessage = namedtuple("OscMessage", ["address", "arguments"])
XInfo = namedtuple("XInfo", ["ip", "port", "name", "model", "version"])


def encode(osc_message):
    builder = pythonosc.osc_message_builder.OscMessageBuilder(osc_message.address)
    for arg in osc_message.arguments:
        builder.add_arg(arg)
    return builder.build().dgram


def decode(dgram):
    message = pythonosc.osc_message.OscMessage(dgram)
    return OscMessage(message.address, message.params)


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
            logger.info("Subscribed (meters=%s): %s", meters, queue)
            yield queue
        finally:
            self._subscriptions.remove((queue, meters))
            logger.info("Unsubscribed (meters=%s): %s", meters, queue)

    async def get(self, address) -> OscMessage:
        await asyncio.sleep(0)
        if address in self._cache:
            return self._cache[address]
        with self.subscribe(meters=False) as queue:
            self._send(OscMessage(address, []))
            while True:
                message = await queue.get()
                if message.address == address:
                    logger.info("Get: %s", message)
                    return message

    def put(self, address, arguments):
        message = OscMessage(address, arguments)
        logger.info("Put: %s", message)
        self._send(message)
        self._notify(message)

    def enable_meter(self, id, channel=None):
        logger.info("Enabled Meter: %d (%s)", id, channel)
        self._meters[(id, channel)] = [f"/meters/{id}"]
        if channel is not None:
            self._meters[(id, channel)].append(channel)

    def disable_meter(self, id, channel=None):
        logger.info("Disabled Meter: %d (%s)", id, channel)
        del self._meters[(id, channel)]

    async def monitor(self):
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
                    struct.unpack(f"<{struct.unpack('<i', data[0:4])[0]}h", data[4:],),
                )
            else:
                logger.info("Received: %s", message)
            self._notify(message)

        refresh_task = loop.create_task(refresh())
        cache_task = loop.create_task(cache())
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


def auto_detect(timeout=3) -> XInfo:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, True)
    sock.settimeout(timeout)

    sock.sendto(encode(OscMessage("/xinfo", [])), ("<broadcast>", 10024))

    try:
        dgram, server = sock.recvfrom(512)
        args = decode(dgram).arguments
        xinfo = XInfo(server[0], server[1], args[1], args[2], args[3])
        logger.debug("Detected: %s", xinfo)
        return xinfo
    finally:
        sock.close()


if __name__ == "__main__":
    logging.basicConfig(
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s", level=logging.INFO,
    )
    xair = XAir(auto_detect())
    xair.enable_meter(2)
    asyncio.run(xair.monitor())

import asyncio
import contextlib
import logging
import socket
import pythonosc.osc_message
import pythonosc.osc_message_builder
from collections import namedtuple
from typing import Any, List, Set


logger = logging.getLogger("pyxair")
logger.setLevel(logging.DEBUG)
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


class XAirPubSub:
    def __init__(self, xinfo):
        self.xinfo = xinfo
        self.subscriptions = set()
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setblocking(False)

    def publish(self, osc_message):
        logger.debug("Sending: %s", osc_message)
        self.sock.sendto(encode(osc_message), (self.xinfo.ip, self.xinfo.port))

    @contextlib.contextmanager
    def subscribe(self):
        try:
            queue = asyncio.Queue()
            self.subscriptions.add(queue)
            yield queue
        finally:
            self.subscriptions.remove(queue)

    async def monitor(self):
        logger.debug("Subscribing to events from %s", self.xinfo)

        async def xremote():
            while True:
                self.publish(OscMessage("/xremote", []))
                await asyncio.sleep(8)

        async def receive():
            while True:
                loop = asyncio.get_running_loop()
                message = decode(await loop.sock_recv(self.sock, 512))
                logger.debug("Received: %s", message)
                for queue in self.subscriptions:
                    await queue.put(message)

        xremote_task = asyncio.create_task(xremote())
        receive_task = asyncio.create_task(receive())
        try:
            await asyncio.gather(xremote_task, receive_task)
        except asyncio.CancelledError:
            pass

    def __repr__(self):
        return f"XAirPubSub({repr(self.xinfo)})"


class XAirCacheClient:
    def __init__(self, pubsub: XAirPubSub):
        self.pubsub = pubsub
        self.cache = {}
        self.cv = asyncio.Condition()

    async def get(self, address):
        if address not in self.cache:
            self.pubsub.publish(OscMessage(address, []))
        async with self.cv:
            while address not in self.cache:
                await self.cv.wait()
            return self.cache[address]

    async def set(self, address, arguments):
        osc_message = OscMessage(address, arguments)
        self.pubsub.publish(osc_message)
        async with self.cv:
            self.cache[osc_message.address] = osc_message
            self.cv.notify()

    async def monitor(self):
        with self.pubsub.subscribe() as queue:
            while True:
                response = await queue.get()
                async with self.cv:
                    self.cache[response.address] = response
                    self.cv.notify()

    def __repr__(self):
        return f"XAirClient({repr(self.pubsub)})"


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
    logging.basicConfig(level=logging.DEBUG)
    pubsub = XAirPubSub(auto_detect())
    asyncio.run(pubsub.monitor())

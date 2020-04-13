import asyncio
import logging
import socket
import pythonosc.osc_message
import pythonosc.osc_message_builder
from collections import namedtuple
from typing import Any, Awaitable, Callable, List, Set


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

    async def publish(self, message: OscMessage):
        logger.debug("Sending: %s", message)
        self.sock.sendto(encode(message), (self.xinfo.ip, self.xinfo.port))

    def subscribe(self, callback: Callable[[OscMessage], Awaitable[None]]):
        self.subscriptions.add(callback)

    async def notify(self, message: OscMessage):
        for callback in self.subscriptions:
            await callback(message)

    async def monitor(self):
        logger.debug("Subscribing to events from %s", self.xinfo)

        async def xremote():
            while True:
                await self.publish(OscMessage("/xremote", []))
                await asyncio.sleep(8)

        async def receive():
            while True:
                loop = asyncio.get_running_loop()
                message = decode(await loop.sock_recv(self.sock, 512))
                logger.debug("Received: %s", message)
                await self.notify(message)

        xremote_task = asyncio.create_task(xremote())
        receive_task = asyncio.create_task(receive())
        try:
            await asyncio.gather(xremote_task, receive_task)
        except asyncio.CancelledError:
            pass

    def __repr__(self):
        return f"XAirPubSub({repr(self.xinfo)})"


class XAirClient:
    def __init__(self, pubsub: XAirPubSub):
        self.pubsub = pubsub
        self.cache = {}
        self.cv = asyncio.Condition()
        self.pubsub.subscribe(self.callback)

    async def get(self, address):
        if address not in self.cache:
            await self.pubsub.publish(OscMessage(address, []))
        async with self.cv:
            while address not in self.cache:
                await self.cv.wait()
            return self.cache[address]

    async def set(self, address, arguments):
        message = OscMessage(address, arguments)
        await self.pubsub.publish(message)
        await self.pubsub.notify(message)

    async def callback(self, message: OscMessage):
        async with self.cv:
            self.cache[message.address] = message
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
    xair = XAirClient(pubsub)
    asyncio.run(pubsub.monitor())
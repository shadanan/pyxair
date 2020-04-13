import asyncio
import contextlib
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


class XAir:
    def __init__(self, xinfo):
        self.xinfo = xinfo
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setblocking(False)
        self.cache = {}
        self.cv = asyncio.Condition()
        self.callbacks = set()
        self.add_callback(self.callback)
        self.subscriptions = set()

    def add_callback(self, callback: Callable[[OscMessage], Awaitable[None]]):
        self.callbacks.add(callback)

    @contextlib.contextmanager
    def subscribe(self):
        try:
            queue = asyncio.Queue()
            self.subscriptions.add(queue)
            yield queue
        finally:
            self.subscriptions.remove(queue)

    async def get(self, address) -> OscMessage:
        if address not in self.cache:
            self.send(OscMessage(address, []))
        async with self.cv:
            while address not in self.cache:
                await self.cv.wait()
            return self.cache[address]

    async def put(self, address, arguments):
        message = OscMessage(address, arguments)
        self.send(message)
        await self.notify(message)

    async def callback(self, message: OscMessage):
        async with self.cv:
            self.cache[message.address] = message
            self.cv.notify()

    async def notify(self, message: OscMessage):
        for callback in self.callbacks:
            await callback(message)
        for queue in self.subscriptions:
            await queue.put(message)

    async def monitor(self):
        logger.debug("Subscribing to events from %s", self.xinfo)

        async def xremote():
            while True:
                self.send(OscMessage("/xremote", []))
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

    def send(self, message: OscMessage):
        logger.debug("Sending: %s", message)
        self.sock.sendto(encode(message), (self.xinfo.ip, self.xinfo.port))

    def __repr__(self):
        return f"XAir({repr(self.xinfo)})"


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
    xair = XAir(auto_detect())
    asyncio.run(xair.monitor())

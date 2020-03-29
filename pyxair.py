import asyncio
import logging
import socket
import pythonosc.osc_message
import pythonosc.osc_message_builder
from collections import namedtuple
from typing import Any, List


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
        self.subscribed = False
        self.cache = {}
        self.cv = asyncio.Condition()
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setblocking(False)

    async def subscribe(self):
        logger.debug("Subscribing to events from %s", self.xinfo)
        self.subscribed = True

        async def xremote():
            while True:
                self.send(OscMessage("/xremote", []))
                await asyncio.sleep(8)

        async def receive():
            while True:
                await self.receive()

        xremote_task = asyncio.create_task(xremote())
        receive_task = asyncio.create_task(receive())
        try:
            await asyncio.gather(xremote_task, receive_task)
        except asyncio.CancelledError:
            pass

        self.subscribed = False

    async def get(self, address):
        if not self.subscribed or address not in self.cache:
            self.send(OscMessage(address, []))
            self.cache.pop(address, None)
            asyncio.create_task(self.receive())
        async with self.cv:
            while address not in self.cache:
                await self.cv.wait()
            return self.cache[address]

    async def set(self, address, arguments):
        osc_message = OscMessage(address, arguments)
        self.send(osc_message)
        async with self.cv:
            self.cache[osc_message.address] = osc_message
            self.cv.notify()

    def send(self, osc_message):
        logger.debug("Sending: %s", osc_message)
        self.sock.sendto(encode(osc_message), (self.xinfo.ip, self.xinfo.port))

    async def receive(self):
        loop = asyncio.get_running_loop()
        response = decode(await loop.sock_recv(self.sock, 512))
        logger.debug("Received: %s", response)
        async with self.cv:
            self.cache[response.address] = response
            self.cv.notify()
        return response

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


def auto_connect():
    return XAir(auto_detect())


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    x_air = auto_connect()
    asyncio.run(x_air.subscribe())

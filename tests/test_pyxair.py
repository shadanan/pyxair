import asyncio
import pytest
import socket
from pyxair import encode, decode, OscMessage, XAir, XInfo


class XAirFake:
    def __init__(self, address):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(address)

    def send(self, msg):
        self.sock.sendto(encode(msg), self.addr)

    def recv(self):
        data, addr = self.sock.recvfrom(512)
        self.addr = addr
        return decode(data)


@pytest.fixture
def server():
    return XAirFake(("localhost", 0))


@pytest.fixture
def xair(server):
    yield XAir(
        XInfo(
            ip="localhost",
            port=server.sock.getsockname()[1],
            name="XR18-00-00-00",
            model="XR18",
            version="1.17",
        )
    )


@pytest.mark.asyncio
async def test_send_encodes_osc_and_sends_message(xair, server, event_loop):
    xair.send(OscMessage("/lr/mix/on", [0]))
    actual = server.recv()
    assert actual == OscMessage("/lr/mix/on", [0])


@pytest.mark.asyncio
async def test_put(xair, server, event_loop):
    task = event_loop.create_task(xair.monitor())
    await asyncio.sleep(0.01)
    message = server.recv()
    assert message == OscMessage("/xremote", [])
    await xair.put("/lr/mix/on", [1])
    message = server.recv()
    assert message == OscMessage("/lr/mix/on", [1])
    task.cancel()


@pytest.mark.asyncio
async def test_get(xair, server, event_loop):
    task = event_loop.create_task(xair.monitor())
    await asyncio.sleep(0.01)
    message = server.recv()
    assert message == OscMessage("/xremote", [])
    get_task = event_loop.create_task(xair.get("/lr/mix/on"))
    await asyncio.sleep(0.1)
    message = server.recv()
    assert message == OscMessage("/lr/mix/on", [])
    server.send(OscMessage("/lr/mix/on", [1]))
    message = await get_task
    assert message == OscMessage("/lr/mix/on", [1])
    task.cancel()

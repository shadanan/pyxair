import asyncio
import pytest
import socket
from pyxair import encode, decode, OscMessage, XAir, XInfo


class XAirServerProtocol(asyncio.DatagramProtocol):
    def __init__(self):
        self.messages = []
        self.settings = {}

    def put(self, setting):
        self.settings[setting.address] = setting

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        message = decode(data)
        self.messages.append(message)
        if message == OscMessage("/lr/mix/on", []):
            self.transport.sendto(encode(self.settings[message.address]), addr)


@pytest.fixture
async def datagram_endpoint(event_loop):
    transport, protocol = await event_loop.create_datagram_endpoint(
        XAirServerProtocol, ("localhost", 0)
    )
    yield transport, protocol
    transport.close()


@pytest.fixture
def transport(datagram_endpoint):
    return datagram_endpoint[0]


@pytest.fixture
def server(datagram_endpoint):
    return datagram_endpoint[1]


@pytest.fixture
async def xair(transport, event_loop):
    xair = XAir(
        XInfo(
            ip="localhost",
            port=transport._sock.getsockname()[1],
            name="XR18-00-00-00",
            model="XR18",
            version="1.17",
        )
    )
    task = event_loop.create_task(xair.monitor())
    yield xair
    task.cancel()
    await task


async def step():
    await asyncio.sleep(0.01)


@pytest.mark.asyncio
async def test_put_sends_message_to_xair(xair, server, event_loop):
    xair.put("/lr/mix/on", [1])
    await step()
    message = server.messages[1]
    assert message == OscMessage("/lr/mix/on", [1])


@pytest.mark.asyncio
async def test_get_retrieves_value_from_xair(xair, server, event_loop):
    server.put(OscMessage("/lr/mix/on", [0]))
    message = await xair.get("/lr/mix/on")
    assert message == OscMessage("/lr/mix/on", [0])


@pytest.mark.asyncio
async def test_enable_meter_sends_meters_command(transport, server, event_loop):
    xair = XAir(
        XInfo(
            ip="localhost",
            port=transport._sock.getsockname()[1],
            name="XR18-00-00-00",
            model="XR18",
            version="1.17",
        )
    )
    xair.enable_meter(2)
    task = event_loop.create_task(xair.monitor())

    await step()
    assert OscMessage("/meters", ["/meters/2"]) in server.messages

    task.cancel()
    await task


if __name__ == "__main__":
    pass

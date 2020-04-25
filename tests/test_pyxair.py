import asyncio
import logging
import pytest
import socket
from pyxair import encode, decode, OscMessage, XAir, XInfo
import types
from typing import Any, Tuple


def xsend(sock: socket.socket, msg: OscMessage, addr):
    sock.sendto(encode(msg), addr)


def xrecv(sock: socket.socket) -> Tuple[OscMessage, Any]:
    data, addr = sock.recvfrom(512)
    return decode(data), addr


@pytest.fixture
def sock():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("localhost", 0))
    return sock


@pytest.fixture
def xair(sock: socket.socket):
    yield XAir(
        XInfo(
            ip="localhost",
            port=sock.getsockname()[1],
            name="XR18-00-00-00",
            model="XR18",
            version="1.17",
        )
    )


@pytest.mark.asyncio
async def test_send_encodes_osc_and_sends_message(
    xair: XAir, sock: socket.socket, event_loop: asyncio.AbstractEventLoop
):
    xair.send(OscMessage("/lr/mix/on", [0]))
    actual = decode(sock.recv(512))
    assert actual == OscMessage("/lr/mix/on", [0])


@pytest.mark.asyncio
async def test_put_sends_osc_message_to_xair(
    xair: XAir, sock: socket.socket, event_loop: asyncio.AbstractEventLoop
):
    task = event_loop.create_task(xair.monitor())
    await asyncio.sleep(0.01)
    message, _ = xrecv(sock)
    assert message == OscMessage("/xremote", [])
    await xair.put("/lr/mix/on", [1])
    message, _ = xrecv(sock)
    assert message == OscMessage("/lr/mix/on", [1])
    task.cancel()


@pytest.mark.asyncio
async def test_get(
    xair: XAir, sock: socket.socket, event_loop: asyncio.AbstractEventLoop
):
    task = event_loop.create_task(xair.monitor())
    await asyncio.sleep(0.01)
    message, _ = xrecv(sock)
    assert message == OscMessage("/xremote", [])
    get_task = event_loop.create_task(xair.get("/lr/mix/on"))
    await asyncio.sleep(0.1)
    message, addr = xrecv(sock)
    assert message == OscMessage("/lr/mix/on", [])
    xsend(sock, OscMessage("/lr/mix/on", [1]), addr)
    message = await get_task
    assert message == OscMessage("/lr/mix/on", [1])
    task.cancel()

import asyncio
import pytest
import socket
from pyxair import encode, OscMessage, XAirTaskManager


@pytest.mark.asyncio
async def test_functional():
    manager = XAirTaskManager()
    manager_task = asyncio.create_task(manager.start())

    with manager.subscribe() as queue:
        while True:
            xinfos = await queue.get()
            if len(xinfos) > 0:
                xinfo = xinfos[0]
                break

    assert xinfo.model == "XR18"

    xair = manager.get_xair(xinfo)

    resp = await xair.get("/status")
    assert resp.arguments[0] == "active"

    xair.put("/lr/mix/on", [1])
    resp = await xair.get("/lr/mix/on")
    assert resp.arguments[0] == 1

    xair.put("/lr/mix/on", [0])
    resp = await xair.get("/lr/mix/on")
    assert resp.arguments[0] == 0

    with xair.subscribe() as queue:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.sendto(encode(OscMessage("/lr/mix/on", [1])), (xinfo.ip, xinfo.port))
        sock.close()

        resp = await queue.get()
        assert resp == OscMessage("/lr/mix/on", [1])

    manager_task.cancel()
    await manager_task

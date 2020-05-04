import asyncio
import socket

import pytest

import pyxair


@pytest.fixture
def coro_mocker(mocker, monkeypatch):
    def _mock_coro(patch):
        mock = mocker.Mock()

        async def _coro(*args, **kwargs):
            return mock(*args, **kwargs)

        monkeypatch.setattr(patch, _coro)

        return mock

    return _mock_coro


@pytest.fixture
def mock_sleep(coro_mocker):
    mock_sleep = coro_mocker("pyxair.scanner.asyncio.sleep")
    return mock_sleep


@pytest.fixture
def scanner(mocker):
    mocker.patch("pyxair.scanner.socket.socket")
    return pyxair.scanner.XAirScanner()


@pytest.fixture
def mock_socket(scanner):
    return scanner._sock


@pytest.mark.asyncio
async def test_scanner_sends_broadcast_messages(mock_socket, mock_sleep):
    mock_sleep.side_effect = [Exception("break while loop")]

    with pytest.raises(Exception, match="break while loop"):
        scanner = pyxair.scanner.XAirScanner()
        await scanner.start()

    mock_socket.sendto.assert_called_once_with(
        pyxair.encode(pyxair.OscMessage("/xinfo", [])), ("<broadcast>", 10024)
    )

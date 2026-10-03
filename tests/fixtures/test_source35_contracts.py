"""Generated controls for internal async sockets and fixture isolation."""
import asyncio
import json
import socket
import subprocess
import sys
from pathlib import Path

import pytest


def test_internal_socketpair_supports_asyncio_wakeup():
    left, right = socket.socketpair()
    try:
        left.send(b"synthetic")
        assert right.recv(9) == b"synthetic"
        with pytest.raises(pytest.fail.Exception, match="offline suite"):
            left.connect(("127.0.0.1", 1))
    finally:
        left.close()
        right.close()
    loop = asyncio.new_event_loop()
    try:
        result = loop.create_future()
        loop.call_soon_threadsafe(result.set_result, 17)
        assert loop.run_until_complete(result) == 17
    finally:
        loop.close()


@pytest.mark.parametrize("address", [("127.0.0.1", 1), ("192.0.2.1", 443)])
def test_ordinary_connections_remain_blocked(address):
    with socket.socket() as client:
        for method in ("connect", "connect_ex"):
            with pytest.raises(pytest.fail.Exception, match="offline suite"):
                getattr(client, method)(address)


@pytest.mark.parametrize("method", ["send", "sendall", "sendto"])
def test_unregistered_socket_sends_remain_blocked(method):
    with socket.socket() as client:
        with pytest.raises(pytest.fail.Exception, match="offline suite"):
            getattr(client, method)(b"synthetic")


def test_consumer_fixture_import_survives_tracker_import():
    tools = Path(__file__).resolve().parents[2] / "tools"
    script = (
        "import sys; from pathlib import Path; sys.path.insert(0, sys.argv[1]); "
        "import track_forward; import make_fixtures; "
        "assert Path(make_fixtures.__file__).resolve().parent == Path(sys.argv[1]); "
        "assert callable(make_fixtures.tracking_scenarios)"
    )
    result = subprocess.run([sys.executable, "-I", "-c", script, str(tools)],
                            capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stderr


def test_fixture_cli_exports_every_declared_basename(tmp_path):
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run([sys.executable, "-I", str(root / "tools/make_fixtures.py"),
                             "--out", str(tmp_path)],
                            capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stderr
    declared = json.loads((root / ".dataclass.json").read_text(encoding="utf-8"))["fixture"]
    assert declared
    for relative in declared:
        assert (tmp_path / Path(relative).name).read_bytes() == (root / relative).read_bytes()

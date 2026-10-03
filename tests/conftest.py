"""Keep the ordinary unit suite offline, including collection and swallowed errors."""
import importlib
import importlib.util
import socket
import urllib.request
from weakref import WeakSet

import pytest


def _deny_network(*args, **kwargs):
    pytest.fail("offline suite attempted an unmocked network operation", pytrace=False)


def pytest_configure(config):
    patch = pytest.MonkeyPatch()
    config._smallcap_network_patch = patch
    config._smallcap_network_targets = []

    def block(owner, method, label, replacement=_deny_network):
        patch.setattr(owner, method, replacement)
        config._smallcap_network_targets.append((owner, method, label, replacement))

    original_connect = socket.socket.connect
    original_send = socket.socket.send
    internal_pairs = WeakSet()

    def internal_socketpair(family=socket.AF_INET, type=socket.SOCK_STREAM, proto=0):
        """Build only an internal pair; never exempt ordinary loopback connections."""
        if family not in (socket.AF_INET, socket.AF_INET6) or type != socket.SOCK_STREAM or proto != 0:
            raise ValueError("offline internal socketpair requires an IP stream")
        address = "127.0.0.1" if family == socket.AF_INET else "::1"
        client, server = None, None
        try:
            with socket.socket(family, type, proto) as listener:
                listener.settimeout(5)
                listener.bind((address, 0))
                listener.listen(1)
                client = socket.socket(family, type, proto)
                client.settimeout(5)
                original_connect(client, listener.getsockname())
                server, peer = listener.accept()
                if peer != client.getsockname():
                    raise OSError("internal socketpair peer mismatch")
            client.setblocking(True)
            server.setblocking(True)
            internal_pairs.update((client, server))
            return client, server
        except BaseException:
            if client is not None:
                client.close()
            if server is not None:
                server.close()
            raise

    def send(sock=None, *args, **kwargs):
        if sock in internal_pairs:
            return original_send(sock, *args, **kwargs)
        return _deny_network()

    patch.setattr(socket, "socketpair", internal_socketpair)

    for method in ("connect", "connect_ex", "sendall", "sendto"):
        block(socket.socket, method, "socket.socket." + method)
    block(socket.socket, "send", "socket.socket.send", send)
    if hasattr(socket.socket, "sendmsg"):
        block(socket.socket, "sendmsg", "socket.socket.sendmsg")
    for method in ("create_connection", "getaddrinfo"):
        block(socket, method, "socket." + method)
    block(urllib.request.OpenerDirector, "open", "urllib.request.OpenerDirector.open")

    transports = (
        ("requests.sessions", "Session", ("request", "send")),
        ("httpx", "Client", ("request", "send")),
        ("httpx", "AsyncClient", ("request", "send")),
        ("curl_cffi.requests", "Session", ("request",)),
        ("curl_cffi.requests", "AsyncSession", ("request",)),
        ("curl_cffi", "Curl", ("perform",)),
        ("curl_cffi", "AsyncCurl", ("add_handle",)),
    )
    for module_name, class_name, methods in transports:
        package = module_name.split(".", 1)[0]
        if importlib.util.find_spec(package) is None:
            continue
        module = importlib.import_module(module_name)
        owner = getattr(module, class_name)
        for method in methods:
            block(owner, method, module_name + "." + class_name + "." + method)


def pytest_unconfigure(config):
    patch = getattr(config, "_smallcap_network_patch", None)
    if patch is not None:
        patch.undo()


@pytest.fixture
def offline_network_targets(request):
    targets = request.config._smallcap_network_targets
    assert targets
    for owner, method, label, replacement in targets:
        assert getattr(owner, method) is replacement, label
    return tuple((label, getattr(owner, method)) for owner, method, label, _ in targets)

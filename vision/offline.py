"""Deny network access in the isolated processing process."""

from contextlib import contextmanager
import os
import socket
from unittest.mock import patch


def configure_offline() -> None:
    for name in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_HUB_DISABLE_TELEMETRY", "DO_NOT_TRACK"):
        os.environ[name] = "1"
    os.environ["TOKENIZERS_PARALLELISM"] = "false"


def _deny(*args, **kwargs):
    raise RuntimeError("Network access is disabled during local processing.")


@contextmanager
def network_disabled():
    configure_offline()
    # The service runs one analyzer at a time in a dedicated subprocess.
    with patch.object(socket.socket, "connect", _deny), \
         patch.object(socket.socket, "connect_ex", _deny), \
         patch.object(socket, "getaddrinfo", _deny), \
         patch.object(socket, "create_connection", _deny), \
         patch.object(socket.socket, "sendto", _deny):
        yield

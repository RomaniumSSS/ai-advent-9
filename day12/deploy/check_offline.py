"""Проверка подготовленного кеша: сеть и реальный клиент запрещены."""
import socket
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
with patch.object(socket.socket, "connect", side_effect=AssertionError("сеть запрещена")):
    import tiktoken
    import base_agent
    with patch.object(base_agent, "get_client", side_effect=AssertionError("API запрещён")):
        assert tiktoken.get_encoding("o200k_base").encode("Офлайн проверка")
print("ok: o200k_base работает без сети")

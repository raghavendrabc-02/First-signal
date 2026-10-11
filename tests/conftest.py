import os
import socket

import pytest

# These must be set before any app module is imported: app modules read them
# at import time, and load_dotenv() never overrides variables that already
# exist, so the real values in .env are ignored during tests.
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["GEMINI_API_KEY"] = "test-dummy-gemini-key"
os.environ["TELEGRAM_BOT_TOKEN"] = ""
os.environ["TELEGRAM_CHAT_ID"] = ""

from app.database.connection import engine  # noqa: E402


if engine.url.get_backend_name() != "sqlite":
    pytest.exit(
        "Refusing to run tests: the database engine is not SQLite",
        returncode=2,
    )


class NetworkAccessBlocked(RuntimeError):
    pass


class PostgresConnectionBlocked(RuntimeError):
    pass


def _block_postgres(*args, **kwargs):
    raise PostgresConnectionBlocked(
        "Tests must not open PostgreSQL connections"
    )


# PostgreSQL drivers open connections in C (libpq), bypassing the Python
# socket guard below, so their connect functions are blocked directly. This is
# installed at import time so it also covers collection and session fixtures.
# "postgresql://" URLs use psycopg2; "postgresql+psycopg://" uses psycopg 3.
import psycopg  # noqa: E402
import psycopg2  # noqa: E402

psycopg2.connect = _block_postgres
psycopg.connect = _block_postgres
psycopg.Connection.connect = classmethod(_block_postgres)
psycopg.AsyncConnection.connect = classmethod(_block_postgres)


def _block_network(*args, **kwargs):
    raise NetworkAccessBlocked(
        "Tests must not open network connections (database, Gemini or Telegram)"
    )


_original_connect = socket.socket.connect
_original_connect_ex = socket.socket.connect_ex


def _guarded_connect(sock, address):
    if sock.family == socket.AF_UNIX:
        return _original_connect(sock, address)
    _block_network()


def _guarded_connect_ex(sock, address):
    if sock.family == socket.AF_UNIX:
        return _original_connect_ex(sock, address)
    _block_network()


@pytest.fixture(autouse=True)
def block_network_access(monkeypatch):
    monkeypatch.setattr(socket.socket, "connect", _guarded_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", _guarded_connect_ex)
    monkeypatch.setattr(socket, "create_connection", _block_network)
    monkeypatch.setattr(socket, "getaddrinfo", _block_network)

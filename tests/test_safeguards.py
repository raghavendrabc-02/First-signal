import asyncio
import socket

import psycopg
import psycopg2
import pytest
from sqlalchemy import create_engine, text

from app.database.connection import engine
from app.services import ai_service, telegram_service

# Unroutable documentation address (RFC 5737): never a real database, even if
# a guard were missing.
UNROUTABLE_POSTGRES = "user:password@203.0.113.1:1/db"


def test_app_engine_uses_isolated_sqlite_with_pre_ping():
    assert engine.url.get_backend_name() == "sqlite"
    assert engine.pool._pre_ping is True


def test_app_engine_pre_ping_does_not_break_queries():
    with engine.connect() as connection:
        assert connection.execute(text("SELECT 1")).scalar() == 1


def test_test_credentials_are_dummies():
    assert ai_service.GEMINI_API_KEY == "test-dummy-gemini-key"
    assert telegram_service.TELEGRAM_BOT_TOKEN == ""
    assert telegram_service.TELEGRAM_CHAT_ID == ""


@pytest.mark.parametrize(
    "connect",
    [
        lambda: psycopg2.connect(f"postgresql://{UNROUTABLE_POSTGRES}"),
        lambda: psycopg.connect(f"postgresql://{UNROUTABLE_POSTGRES}"),
        lambda: psycopg.Connection.connect(f"postgresql://{UNROUTABLE_POSTGRES}"),
    ],
)
def test_postgres_driver_connections_are_blocked(connect):
    with pytest.raises(RuntimeError, match="must not open PostgreSQL connections"):
        connect()


@pytest.mark.parametrize("scheme", ["postgresql", "postgresql+psycopg2", "postgresql+psycopg"])
def test_sqlalchemy_postgres_engines_cannot_connect(scheme):
    postgres_engine = create_engine(
        f"{scheme}://{UNROUTABLE_POSTGRES}", pool_pre_ping=True
    )

    try:
        with pytest.raises(RuntimeError, match="must not open PostgreSQL connections"):
            postgres_engine.connect()
    finally:
        postgres_engine.dispose()


@pytest.mark.parametrize(
    "connect",
    [
        lambda: socket.create_connection(("api.telegram.org", 443), timeout=1),
        lambda: socket.getaddrinfo("generativelanguage.googleapis.com", 443),
        lambda: socket.socket().connect(("203.0.113.1", 5432)),
    ],
)
def test_outbound_network_connections_are_blocked(connect):
    with pytest.raises(RuntimeError, match="must not open network connections"):
        connect()


def test_unmocked_telegram_send_is_refused():
    with pytest.raises(RuntimeError, match="not configured"):
        asyncio.run(telegram_service.send_telegram_message("test"))


def test_unmocked_gemini_call_cannot_reach_api():
    with pytest.raises(RuntimeError, match="must not open network connections"):
        ai_service._generate_ai_response("test")

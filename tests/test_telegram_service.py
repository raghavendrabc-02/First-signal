import asyncio
from unittest.mock import patch

import httpx
import pytest

from app.services import telegram_service

FAKE_TOKEN = "123456:SECRET-TOKEN"


def _send_with_transport(handler):
    transport = httpx.MockTransport(handler)
    real_client = httpx.AsyncClient

    with patch.object(telegram_service, "TELEGRAM_BOT_TOKEN", FAKE_TOKEN), patch.object(
        telegram_service, "TELEGRAM_CHAT_ID", "42"
    ), patch.object(
        telegram_service.httpx,
        "AsyncClient",
        lambda **kwargs: real_client(transport=transport, **kwargs),
    ):
        return asyncio.run(telegram_service.send_telegram_message("hello"))


def test_send_telegram_message_returns_response_when_ok():
    result = _send_with_transport(
        lambda request: httpx.Response(
            200, json={"ok": True, "result": {"message_id": 7}}
        )
    )

    assert result["result"]["message_id"] == 7


def test_send_telegram_message_raises_when_ok_is_false():
    with pytest.raises(RuntimeError, match="chat not found"):
        _send_with_transport(
            lambda request: httpx.Response(
                200, json={"ok": False, "description": "Bad Request: chat not found"}
            )
        )


def test_send_telegram_message_raises_on_http_error_without_leaking_token():
    with pytest.raises(RuntimeError) as error_info:
        _send_with_transport(
            lambda request: httpx.Response(
                401, json={"ok": False, "description": "Unauthorized"}
            )
        )

    assert "HTTP 401" in str(error_info.value)
    assert FAKE_TOKEN not in str(error_info.value)


def test_send_telegram_message_network_error_does_not_leak_token():
    def handler(request):
        raise httpx.ConnectError(f"failed {request.url}")

    with pytest.raises(RuntimeError) as error_info:
        _send_with_transport(handler)

    assert FAKE_TOKEN not in str(error_info.value)
    assert error_info.value.__cause__ is None


def test_send_telegram_message_accepts_ok_response_without_message_id():
    result = _send_with_transport(lambda request: httpx.Response(200, json={"ok": True}))

    assert result == {"ok": True}


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, text="<html>Bad Gateway</html>"),
        httpx.Response(200, json=["ok", True]),
        httpx.Response(200, json={"result": {"message_id": 1}}),
        httpx.Response(200, json={"ok": "true"}),
        httpx.Response(502, text="Bad Gateway"),
        httpx.Response(429, json={"ok": False, "description": "Too Many Requests"}),
    ],
)
def test_send_telegram_message_rejects_failed_or_malformed_responses(response):
    with pytest.raises(RuntimeError, match="Telegram sendMessage failed"):
        _send_with_transport(lambda request: response)

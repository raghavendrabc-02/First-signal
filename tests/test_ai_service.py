import asyncio
from unittest.mock import AsyncMock, patch

from google.genai import errors

from app.services import ai_service
from app.services.ai_service import (
    FALLBACK_MODEL,
    PRIMARY_MODEL,
    _generate_ai_response,
    generate_ai_response,
)


def _server_error():
    return errors.ServerError(
        503, {"error": {"code": 503, "message": "busy", "status": "UNAVAILABLE"}}
    )


def _quota_error():
    return errors.ClientError(
        429, {"error": {"code": 429, "message": "quota", "status": "RESOURCE_EXHAUSTED"}}
    )


def _bad_request_error():
    return errors.ClientError(
        400, {"error": {"code": 400, "message": "bad", "status": "INVALID_ARGUMENT"}}
    )


def _run(side_effect):
    with patch.object(ai_service.asyncio, "sleep", new=AsyncMock()), patch(
        "app.services.ai_service._generate_ai_response",
        side_effect=side_effect,
    ) as mock_generate:
        result = asyncio.run(generate_ai_response("Test prompt"))

    models = [call.args[1] for call in mock_generate.call_args_list]
    return result, models


def test_ai_service_success():
    with patch(
        "app.services.ai_service.genai.Client"
    ) as mock_client:

        mock_client.return_value.models.generate_content.return_value.text = (
            "Test AI response"
        )

        result = _generate_ai_response("Test prompt")

        assert result == "Test AI response"


def test_ai_service_empty_response_returns_none():
    with patch(
        "app.services.ai_service.genai.Client"
    ) as mock_client:

        mock_client.return_value.models.generate_content.return_value.text = ""

        assert _generate_ai_response("Test prompt") is None


def test_ai_service_retries_after_transient_failure():
    result, models = _run([_server_error(), "Recovered response"])

    assert result == "Recovered response"
    assert models == [PRIMARY_MODEL, PRIMARY_MODEL]


def test_ai_service_falls_back_after_repeated_transient_failures():
    result, models = _run(
        [_server_error(), _server_error(), _server_error(), "Fallback response"]
    )

    assert result == "Fallback response"
    assert models == [PRIMARY_MODEL] * 3 + [FALLBACK_MODEL]


def test_ai_service_falls_back_immediately_on_quota_error():
    result, models = _run([_quota_error(), "Fallback response"])

    assert result == "Fallback response"
    assert models == [PRIMARY_MODEL, FALLBACK_MODEL]


def test_ai_service_returns_none_when_fallback_fails():
    result, models = _run([_quota_error(), _quota_error()])

    assert result is None
    assert models == [PRIMARY_MODEL, FALLBACK_MODEL]


def test_ai_service_does_not_retry_non_transient_errors():
    result, models = _run([_bad_request_error()])

    assert result is None
    assert models == [PRIMARY_MODEL]


def test_ai_service_does_not_retry_empty_response():
    result, models = _run([None])

    assert result is None
    assert models == [PRIMARY_MODEL]

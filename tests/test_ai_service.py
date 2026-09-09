from unittest.mock import patch

from app.services.ai_service import _generate_ai_response


def test_ai_service_success():
    with patch(
        "app.services.ai_service.genai.Client"
    ) as mock_client:

        mock_client.return_value.models.generate_content.return_value.text = (
            "Test AI response"
        )

        result = _generate_ai_response("Test prompt")

        assert result == "Test AI response"

import asyncio

from app.services.ai_service import generate_ai_response


def test_ai_service_retries_after_failure():
    with patch(
        "app.services.ai_service._generate_ai_response",
        side_effect=[None, "Recovered response"],
    ) as mock_generate:

        result = asyncio.run(
            generate_ai_response("Test prompt")
        )

        assert result == "Recovered response"
        assert mock_generate.call_count == 2
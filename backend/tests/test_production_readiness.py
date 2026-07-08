import logging

import pytest
from starlette.requests import Request

from app.core.config import Settings
from app.main import global_exception_handler


def test_default_generation_model_is_gemini_25_flash() -> None:
    isolated_settings = Settings(_env_file=None)

    assert isolated_settings.generation_model == "gemini-2.5-flash"


@pytest.mark.asyncio
async def test_global_handler_logs_safe_metadata_without_exposing_details(
    caplog: pytest.LogCaptureFixture,
) -> None:
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/chat",
            "headers": [],
            "query_string": b"",
            "server": ("testserver", 80),
            "client": ("testclient", 50000),
            "scheme": "http",
        }
    )

    with caplog.at_level(logging.ERROR):
        response = await global_exception_handler(
            request, RuntimeError("secret provider detail")
        )

    assert response.status_code == 500
    assert response.body == b'{"detail":"An unexpected error occurred."}'
    logs = "\n".join(record.getMessage() for record in caplog.records)
    assert "method=POST" in logs
    assert "path=/api/chat" in logs
    assert "secret provider detail" not in logs

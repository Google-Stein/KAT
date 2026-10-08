"""Actual SDK exceptions map to safe, portable API and audit failures."""

from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from openai import (
    APIConnectionError,
    APIResponseValidationError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    NotFoundError,
    RateLimitError,
)

from kat_core.app import create_app
from kat_core.config import CoreConfig
from kat_core.errors import ProviderErrorCode
from kat_core.provider import classify_openai_error

PRIVATE = "sk-secret_private_payload_conversation"
REQUEST = httpx.Request("POST", "https://api.openai.com/v1/responses")


@pytest.mark.parametrize(
    "exception,code",
    [
        (
            AuthenticationError(
                PRIVATE, response=httpx.Response(401, request=REQUEST), body={"message": PRIVATE}
            ),
            ProviderErrorCode.AUTHENTICATION,
        ),
        (
            NotFoundError(PRIVATE, response=httpx.Response(404, request=REQUEST), body={}),
            ProviderErrorCode.MODEL_UNAVAILABLE,
        ),
        (
            BadRequestError(
                PRIVATE,
                response=httpx.Response(400, request=REQUEST),
                body={"code": "model_not_found"},
            ),
            ProviderErrorCode.MODEL_UNAVAILABLE,
        ),
        (
            RateLimitError(
                PRIVATE,
                response=httpx.Response(429, request=REQUEST),
                body={"error": {"code": "insufficient_quota", "message": PRIVATE}},
            ),
            ProviderErrorCode.QUOTA,
        ),
        (
            RateLimitError(
                PRIVATE, response=httpx.Response(429, request=REQUEST), body={"message": PRIVATE}
            ),
            ProviderErrorCode.RATE_LIMITED,
        ),
        (APITimeoutError(REQUEST), ProviderErrorCode.TIMEOUT),
        (APIConnectionError(message=PRIVATE, request=REQUEST), ProviderErrorCode.NETWORK),
        (
            APIResponseValidationError(
                response=httpx.Response(200, request=REQUEST), body={"message": PRIVATE}
            ),
            ProviderErrorCode.MALFORMED_RESPONSE,
        ),
        (RuntimeError(PRIVATE), ProviderErrorCode.FAILED),
    ],
)
def test_error_response_and_audit_are_sanitized(
    exception: Exception, code: ProviderErrorCode, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    failure = classify_openai_error(exception)
    assert failure.code == code

    class FailedRuntime:
        ready = True

        async def respond(self, *args: object) -> str:
            raise failure

    token = "test-token-for-provider-errors-at-least-32"
    app = create_app(CoreConfig(data_dir=tmp_path, api_token=token), runtime=FailedRuntime())
    with TestClient(
        app, base_url="http://127.0.0.1", headers={"Authorization": f"Bearer {token}"}
    ) as client:
        session = client.post("/sessions", json={}).json()["id"]
        response = client.post(f"/sessions/{session}/messages", json={"content": "Hello"})
        assert response.status_code == failure.status_code
        assert response.json()["error"]["code"] == code.value
        audit = client.get("/audit")
        assert audit.json()[0]["details"]["code"] == code.value
        assert PRIVATE not in response.text + audit.text + caplog.text

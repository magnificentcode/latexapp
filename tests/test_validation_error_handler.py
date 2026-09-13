import asyncio
import json

from fastapi.exceptions import RequestValidationError

from app.main import validation_exception_handler


def _handle(exc):
    # No pytest-asyncio in this project's dependencies — run the coroutine
    # directly instead, rather than pulling in a plugin for four tests.
    return asyncio.run(validation_exception_handler(None, exc))


def _make_error(**overrides):
    error = {
        "type": "value_error",
        "loc": ("body", "content"),
        "msg": "Value error, Document content exceeds the 10MB size limit.",
        "input": "a" * 1000,  # stands in for a real oversized payload
        "ctx": {"error": ValueError("Document content exceeds the 10MB size limit.")},
        "url": "https://errors.pydantic.dev/2.5/v/value_error",
    }
    error.update(overrides)
    return error


class _FakeValidationError(RequestValidationError):
    """RequestValidationError normally wraps a real pydantic ValidationError;
    building errors by hand here keeps the test independent of triggering
    an actual FastAPI request/response cycle (no httpx dependency needed)."""

    def __init__(self, errors):
        self._errors = errors
        super().__init__(errors)

    def errors(self):
        return self._errors


def test_input_field_is_stripped_from_the_response():
    exc = _FakeValidationError([_make_error()])
    response = _handle(exc)
    body = json.loads(response.body)
    assert "input" not in body["detail"][0]


def test_the_useful_error_fields_are_preserved():
    exc = _FakeValidationError([_make_error()])
    response = _handle(exc)
    body = json.loads(response.body)
    error = body["detail"][0]
    assert error["msg"] == "Value error, Document content exceeds the 10MB size limit."
    assert error["type"] == "value_error"
    assert error["loc"] == ["body", "content"]


def test_response_status_is_422():
    exc = _FakeValidationError([_make_error()])
    response = _handle(exc)
    assert response.status_code == 422


def test_response_body_does_not_scale_with_input_size():
    tiny_error = _make_error(input="x")
    huge_error = _make_error(input="x" * 10_000_000)

    tiny_response = _handle(_FakeValidationError([tiny_error]))
    huge_response = _handle(_FakeValidationError([huge_error]))

    # Both had their "input" stripped, so a 10MB rejected payload shouldn't
    # produce a meaningfully larger response than a 1-byte one.
    assert len(huge_response.body) < len(tiny_response.body) + 100


def test_multiple_errors_are_all_sanitized():
    exc = _FakeValidationError([_make_error(), _make_error(loc=("body", "title"))])
    response = _handle(exc)
    body = json.loads(response.body)
    assert len(body["detail"]) == 2
    assert all("input" not in error for error in body["detail"])

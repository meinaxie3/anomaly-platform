"""Tests for HttpWriter — httpx.Client is mocked, no network needed."""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from ap_schemas import MetricEvent
from load_gen.writer import HttpWriter


def _make_event(value: float = 42.0) -> MetricEvent:
    return MetricEvent(
        service="payment-api",
        metric="cpu_percent",
        value=value,
        timestamp=datetime(2024, 1, 1, 12, 0, tzinfo=UTC),
    )


def _mock_response(status_code: int = 202) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.is_success = 200 <= status_code < 300
    resp.text = ""
    resp.raise_for_status = MagicMock()
    return resp


def _patch_client(post_mock: MagicMock):  # type: ignore[no-untyped-def]
    """
    Patch httpx.Client so that HttpWriter's `self._client = httpx.Client(...)`
    returns an object whose .post is post_mock.
    """
    patcher = patch("load_gen.writer.httpx.Client")
    mock_cls = patcher.start()
    # HttpWriter stores `self._client = httpx.Client(...)` — that is mock_cls.return_value
    instance = mock_cls.return_value
    instance.post = post_mock
    instance.close = MagicMock()
    return patcher, instance


def test_http_writer_posts_single_batch_when_below_threshold() -> None:
    mock_post = MagicMock(return_value=_mock_response(202))
    patcher, _ = _patch_client(mock_post)
    try:
        with HttpWriter("http://localhost:8001", batch_size=200) as writer:
            for i in range(5):
                writer.write(_make_event(float(i)))
        # 5 events < batch_size=200 so only exit flush fires
        mock_post.assert_called_once()
        assert writer.count == 5
    finally:
        patcher.stop()


def test_http_writer_posts_in_multiple_batches() -> None:
    mock_post = MagicMock(return_value=_mock_response(202))
    patcher, _ = _patch_client(mock_post)
    try:
        with HttpWriter("http://localhost:8001", batch_size=3) as writer:
            for i in range(10):
                writer.write(_make_event(float(i)))
        # 10 events / batch_size=3: flushes at 3, 6, 9 + exit flush (1 remaining) = 4 calls
        assert mock_post.call_count == 4
        assert writer.count == 10
    finally:
        patcher.stop()


def test_http_writer_logs_warning_on_4xx_and_does_not_raise() -> None:
    mock_post = MagicMock(return_value=_mock_response(422))
    patcher, _ = _patch_client(mock_post)
    try:
        with HttpWriter("http://localhost:8001", batch_size=200) as writer:
            writer.write(_make_event())
        assert writer.count == 0
        assert writer.errors == 1
    finally:
        patcher.stop()


def test_http_writer_raises_on_5xx() -> None:
    resp = _mock_response(500)
    resp.raise_for_status = MagicMock(side_effect=Exception("server error"))
    mock_post = MagicMock(return_value=resp)
    patcher, _ = _patch_client(mock_post)
    try:
        with (
            pytest.raises(Exception, match="server error"),
            HttpWriter("http://localhost:8001", batch_size=200) as writer,
        ):
            writer.write(_make_event())
    finally:
        patcher.stop()


def test_http_writer_count_reflects_successful_events_only() -> None:
    responses = [_mock_response(202), _mock_response(422)]
    mock_post = MagicMock(side_effect=responses)
    patcher, _ = _patch_client(mock_post)
    try:
        with HttpWriter("http://localhost:8001", batch_size=1) as writer:
            writer.write(_make_event(1.0))  # flushes immediately (batch_size=1) -> 202
            writer.write(_make_event(2.0))  # flushes immediately -> 422
        assert writer.count == 1
        assert writer.errors == 1
    finally:
        patcher.stop()

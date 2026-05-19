"""Unit tests for the consumer's inference scoring hook."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from ap_schemas import MetricEvent
from consumer.worker import _score_batch


def _events(n: int = 3) -> list[MetricEvent]:
    return [
        MetricEvent(
            service="payment-api",
            metric="cpu_percent",
            value=float(i),
            timestamp=datetime.now(tz=UTC),
        )
        for i in range(n)
    ]


@pytest.mark.asyncio
async def test_score_batch_returns_anomaly_count_on_success() -> None:
    anomaly_response = [{"anomaly_id": "x", "score": -0.3}]
    mock_resp = MagicMock()
    mock_resp.is_success = True
    mock_resp.json.return_value = anomaly_response

    with patch("consumer.worker.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        count = await _score_batch(_events(3), "http://localhost:8002", timeout=5.0)

    assert count == 1


@pytest.mark.asyncio
async def test_score_batch_continues_on_timeout() -> None:
    with patch("consumer.worker.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timed out"))
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        # Must not raise — returns 0 gracefully
        count = await _score_batch(_events(), "http://localhost:8002", timeout=1.0)

    assert count == 0


@pytest.mark.asyncio
async def test_score_batch_continues_on_500_error() -> None:
    mock_resp = MagicMock()
    mock_resp.is_success = False
    mock_resp.status_code = 500

    with patch("consumer.worker.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        count = await _score_batch(_events(), "http://localhost:8002", timeout=5.0)

    assert count == 0


@pytest.mark.asyncio
async def test_score_batch_continues_on_connection_error() -> None:
    with patch("consumer.worker.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=Exception("connection refused"))
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        count = await _score_batch(_events(), "http://localhost:8002", timeout=5.0)

    assert count == 0

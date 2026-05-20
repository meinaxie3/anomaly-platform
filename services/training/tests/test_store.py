"""Unit tests for ModelStore — all S3 calls are mocked."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from training.store import ModelStore


def _make_store() -> tuple[ModelStore, MagicMock]:
    """Return a (store, mock_client) pair with boto3 patched out."""
    with patch("training.store.boto3.client") as mock_boto3_client:
        mock_client = MagicMock()
        mock_boto3_client.return_value = mock_client
        store = ModelStore(
            endpoint="http://localhost:9000",
            access_key="minio",
            secret_key="minio123",
            bucket="models",
        )
    store._client = mock_client  # keep the mock after __init__
    return store, mock_client


def test_ensure_bucket_creates_when_missing() -> None:
    store, mock_client = _make_store()
    from botocore.exceptions import ClientError

    mock_client.head_bucket.side_effect = ClientError(
        {"Error": {"Code": "404", "Message": "Not Found"}}, "HeadBucket"
    )
    store.ensure_bucket()
    mock_client.create_bucket.assert_called_once_with(Bucket="models")


def test_ensure_bucket_noop_when_exists() -> None:
    store, mock_client = _make_store()
    mock_client.head_bucket.return_value = {}
    store.ensure_bucket()
    mock_client.create_bucket.assert_not_called()


def test_upload_calls_put_object_and_returns_key() -> None:
    store, mock_client = _make_store()
    data = b"fake-model-bytes"
    key = "models/payment-api/cpu_percent/abc123.joblib"
    result = store.upload(key, data)
    assert result == key
    mock_client.put_object.assert_called_once()
    call_kwargs = mock_client.put_object.call_args.kwargs
    assert call_kwargs["Bucket"] == "models"
    assert call_kwargs["Key"] == key


def test_download_returns_body_bytes() -> None:
    store, mock_client = _make_store()
    expected = b"model-artifact"
    mock_client.get_object.return_value = {"Body": MagicMock(read=lambda: expected)}
    result = store.download("models/svc/metric/id.joblib")
    assert result == expected


def test_artifact_key_format() -> None:
    key = ModelStore.artifact_key("payment-api", "cpu_percent", "abc-123")
    assert key == "models/payment-api/cpu_percent/abc-123.joblib"


def test_list_keys_aggregates_pages() -> None:
    store, mock_client = _make_store()
    paginator = MagicMock()
    paginator.paginate.return_value = [
        {"Contents": [{"Key": "models/a/b/1.joblib"}, {"Key": "models/a/b/2.joblib"}]},
        {"Contents": [{"Key": "models/a/b/3.joblib"}]},
    ]
    mock_client.get_paginator.return_value = paginator
    keys = store.list_keys(prefix="models/a/b")
    assert len(keys) == 3
    assert "models/a/b/1.joblib" in keys

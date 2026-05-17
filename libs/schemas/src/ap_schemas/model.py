from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ModelMetadata(BaseModel):
    """Versioned training artifact record written by the training job."""

    model_id: UUID = Field(default_factory=uuid4)
    service: str
    metric: str
    algorithm: str = Field(description="E.g. 'isolation_forest'")

    trained_at: datetime
    window_start: datetime
    window_end: datetime

    n_samples: int = Field(description="Number of training data points used")
    fit_seconds: float = Field(description="Wall-clock time to fit the model")

    # Holdout evaluation scores (0.0–1.0); -1.0 signals not available
    eval_precision: float = -1.0
    eval_recall: float = -1.0
    eval_f1: float = -1.0

    artifact_path: str = Field(description="MinIO object key, e.g. models/svc/metric/id.joblib")
    is_current: bool = False

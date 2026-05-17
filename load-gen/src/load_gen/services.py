"""
Baseline SignalConfig catalog — one entry per service x metric.

Five synthetic microservices that together look like a realistic
production system. Values are tuned so normal behaviour is believable
and anomalies are clearly detectable.
"""

from ap_schemas import MetricType

from load_gen.signal import SignalConfig

SERVICES: dict[str, dict[str, SignalConfig]] = {
    # High-traffic payment processor — CPU and latency sensitive.
    "payment-api": {
        MetricType.CPU_PERCENT: SignalConfig(
            base=42, daily_amp=0.35, weekly_amp=0.20, noise_std=3.5
        ),
        MetricType.MEMORY_PERCENT: SignalConfig(
            base=58, daily_amp=0.08, weekly_amp=0.05, noise_std=1.5, max_val=100
        ),
        MetricType.REQUEST_RATE: SignalConfig(
            base=120, daily_amp=0.55, weekly_amp=0.30, noise_std=8.0
        ),
        MetricType.LATENCY_P50: SignalConfig(
            base=45, daily_amp=0.25, weekly_amp=0.10, noise_std=4.0
        ),
        MetricType.LATENCY_P95: SignalConfig(
            base=120, daily_amp=0.30, weekly_amp=0.10, noise_std=12.0
        ),
        MetricType.LATENCY_P99: SignalConfig(
            base=280, daily_amp=0.35, weekly_amp=0.12, noise_std=28.0
        ),
        MetricType.ERROR_RATE: SignalConfig(
            base=0.005, daily_amp=0.20, weekly_amp=0.10, noise_std=0.001, max_val=1.0
        ),
    },
    # Authentication service — bursty, error rate spikes on auth failures.
    "auth-service": {
        MetricType.CPU_PERCENT: SignalConfig(
            base=28, daily_amp=0.30, weekly_amp=0.15, noise_std=2.5
        ),
        MetricType.MEMORY_PERCENT: SignalConfig(
            base=45, daily_amp=0.06, weekly_amp=0.04, noise_std=1.2, max_val=100
        ),
        MetricType.REQUEST_RATE: SignalConfig(
            base=80, daily_amp=0.50, weekly_amp=0.25, noise_std=5.0
        ),
        MetricType.LATENCY_P50: SignalConfig(
            base=30, daily_amp=0.20, weekly_amp=0.08, noise_std=3.0
        ),
        MetricType.LATENCY_P95: SignalConfig(
            base=85, daily_amp=0.25, weekly_amp=0.08, noise_std=8.0
        ),
        MetricType.LATENCY_P99: SignalConfig(
            base=180, daily_amp=0.30, weekly_amp=0.10, noise_std=18.0
        ),
        MetricType.ERROR_RATE: SignalConfig(
            base=0.003, daily_amp=0.15, weekly_amp=0.08, noise_std=0.0008, max_val=1.0
        ),
    },
    # Inventory database — steady load, memory grows with query volume.
    "inventory-db": {
        MetricType.CPU_PERCENT: SignalConfig(
            base=22, daily_amp=0.20, weekly_amp=0.10, noise_std=2.0
        ),
        MetricType.MEMORY_PERCENT: SignalConfig(
            base=72, daily_amp=0.05, weekly_amp=0.03, noise_std=1.0, max_val=100
        ),
        MetricType.REQUEST_RATE: SignalConfig(
            base=35, daily_amp=0.40, weekly_amp=0.20, noise_std=3.0
        ),
        MetricType.LATENCY_P50: SignalConfig(
            base=8, daily_amp=0.15, weekly_amp=0.05, noise_std=1.0
        ),
        MetricType.LATENCY_P95: SignalConfig(
            base=22, daily_amp=0.18, weekly_amp=0.05, noise_std=3.0
        ),
        MetricType.LATENCY_P99: SignalConfig(
            base=55, daily_amp=0.22, weekly_amp=0.07, noise_std=7.0
        ),
        MetricType.ERROR_RATE: SignalConfig(
            base=0.001, daily_amp=0.10, weekly_amp=0.05, noise_std=0.0003, max_val=1.0
        ),
    },
    # Notification service — low throughput, occasional latency spikes.
    "notification-service": {
        MetricType.CPU_PERCENT: SignalConfig(
            base=15, daily_amp=0.25, weekly_amp=0.12, noise_std=2.0
        ),
        MetricType.MEMORY_PERCENT: SignalConfig(
            base=38, daily_amp=0.07, weekly_amp=0.04, noise_std=1.2, max_val=100
        ),
        MetricType.REQUEST_RATE: SignalConfig(
            base=20, daily_amp=0.45, weekly_amp=0.22, noise_std=2.5
        ),
        MetricType.LATENCY_P50: SignalConfig(
            base=60, daily_amp=0.20, weekly_amp=0.08, noise_std=6.0
        ),
        MetricType.LATENCY_P95: SignalConfig(
            base=180, daily_amp=0.25, weekly_amp=0.08, noise_std=18.0
        ),
        MetricType.LATENCY_P99: SignalConfig(
            base=420, daily_amp=0.30, weekly_amp=0.10, noise_std=40.0
        ),
        MetricType.ERROR_RATE: SignalConfig(
            base=0.008, daily_amp=0.18, weekly_amp=0.08, noise_std=0.002, max_val=1.0
        ),
    },
    # API gateway — highest request rate, aggregates all upstream traffic.
    "api-gateway": {
        MetricType.CPU_PERCENT: SignalConfig(
            base=55, daily_amp=0.40, weekly_amp=0.22, noise_std=4.0
        ),
        MetricType.MEMORY_PERCENT: SignalConfig(
            base=48, daily_amp=0.06, weekly_amp=0.03, noise_std=1.5, max_val=100
        ),
        MetricType.REQUEST_RATE: SignalConfig(
            base=380, daily_amp=0.60, weekly_amp=0.35, noise_std=20.0
        ),
        MetricType.LATENCY_P50: SignalConfig(
            base=25, daily_amp=0.22, weekly_amp=0.08, noise_std=3.0
        ),
        MetricType.LATENCY_P95: SignalConfig(
            base=70, daily_amp=0.28, weekly_amp=0.09, noise_std=8.0
        ),
        MetricType.LATENCY_P99: SignalConfig(
            base=160, daily_amp=0.32, weekly_amp=0.10, noise_std=18.0
        ),
        MetricType.ERROR_RATE: SignalConfig(
            base=0.006, daily_amp=0.22, weekly_amp=0.10, noise_std=0.0012, max_val=1.0
        ),
    },
}

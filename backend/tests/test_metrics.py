"""Unit tests for Prometheus metrics definitions."""
from app.metrics import JOBS_COMPLETED, JOBS_SUBMITTED, PROVISION_DURATION, _prometheus_available


def test_metrics_module_loads():
    assert JOBS_SUBMITTED is not None
    assert JOBS_COMPLETED is not None
    assert PROVISION_DURATION is not None


def test_jobs_submitted_labels():
    if not _prometheus_available:
        return
    assert "environment" in JOBS_SUBMITTED._labelnames


def test_jobs_completed_labels():
    if not _prometheus_available:
        return
    assert "status" in JOBS_COMPLETED._labelnames
    assert "environment" in JOBS_COMPLETED._labelnames


def test_provision_duration_labels():
    if not _prometheus_available:
        return
    assert "environment" in PROVISION_DURATION._labelnames


def test_metrics_increment_no_error():
    JOBS_SUBMITTED.labels(environment="test_metrics").inc()
    JOBS_COMPLETED.labels(status="succeeded", environment="test_metrics").inc()
    JOBS_COMPLETED.labels(status="failed", environment="test_metrics").inc()
    PROVISION_DURATION.labels(environment="test_metrics").observe(12.5)


def test_prometheus_available_flag_is_bool():
    assert isinstance(_prometheus_available, bool)

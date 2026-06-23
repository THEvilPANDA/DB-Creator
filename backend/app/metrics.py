"""Prometheus metrics for DB Creator.

If prometheus_client is not installed, all metrics are no-ops so unit tests
and the rest of the app continue to work without the dependency.
Run `pip install -r requirements.txt` to enable the /metrics endpoint.
"""
try:
    from prometheus_client import Counter, Histogram

    JOBS_SUBMITTED = Counter(
        "dbcreator_jobs_submitted_total",
        "Total provisioning jobs submitted",
        ["environment"],
    )

    JOBS_COMPLETED = Counter(
        "dbcreator_jobs_completed_total",
        "Total provisioning jobs completed by outcome",
        ["status", "environment"],
    )

    PROVISION_DURATION = Histogram(
        "dbcreator_provisioning_duration_seconds",
        "Time from provisioning start to completion",
        ["environment"],
        buckets=[1, 2, 5, 10, 30, 60, 120, 300],
    )

    _prometheus_available = True

except ImportError:  # pragma: no cover

    class _Stub:
        _labelnames = ()

        def labels(self, **_):
            return self

        def inc(self, _amount=1):
            pass

        def observe(self, _value):
            pass

    JOBS_SUBMITTED = _Stub()  # type: ignore[assignment]
    JOBS_COMPLETED = _Stub()  # type: ignore[assignment]
    PROVISION_DURATION = _Stub()  # type: ignore[assignment]
    _prometheus_available = False

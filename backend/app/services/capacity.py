from app.models.server import Server
from app.services.provisioner.base import CapacityMetrics


class CapacityService:
    def is_accepting_jobs(self, server: Server, metrics: CapacityMetrics) -> bool:
        return metrics.health != "critical" and server.is_active

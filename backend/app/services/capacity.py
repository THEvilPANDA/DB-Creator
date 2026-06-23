from app.models.server import Server
from app.services.provisioner.base import CapacityMetrics


class CapacityService:
    def is_accepting_jobs(self, server: Server, metrics: CapacityMetrics) -> bool:
        if not server.is_active:
            return False
        if metrics.health == "critical":
            return False
        # Gate on connection count — reject if active connections exceed 90% of max
        if server.max_connections and metrics.active_connections >= server.max_connections * 0.9:
            return False
        return True

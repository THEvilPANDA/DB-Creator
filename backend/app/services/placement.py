from typing import Literal, Optional

from app.models.server import Server

PlacementStrategy = Literal["manual", "least_dbs", "round_robin", "environment_default"]


class PlacementService:
    def select(
        self,
        servers: list[Server],
        strategy: PlacementStrategy = "environment_default",
        db_counts: Optional[dict[int, int]] = None,
        environment: Optional[str] = None,
    ) -> Optional[Server]:
        active = [s for s in servers if s.is_active and not s.is_deleted]
        if not active:
            return None

        if strategy == "environment_default":
            # Prefer servers matching the target environment; fall back to any active
            env_match = [s for s in active if s.environment == environment] if environment else active
            pool = env_match if env_match else active
            return pool[0]

        if strategy == "least_dbs" and db_counts:
            return min(active, key=lambda s: db_counts.get(s.id, 0))

        if strategy == "round_robin":
            return active[0]

        # manual — caller must provide server_id explicitly
        return None

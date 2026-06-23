from typing import Literal, Optional

from app.models.server import Server

PlacementStrategy = Literal["manual", "least_dbs", "round_robin"]


class PlacementService:
    def select(
        self,
        servers: list[Server],
        strategy: PlacementStrategy = "least_dbs",
        db_counts: Optional[dict[int, int]] = None,
    ) -> Optional[Server]:
        active = [s for s in servers if s.is_active and not s.is_deleted]
        if not active:
            return None
        if strategy == "round_robin":
            return active[0]
        if strategy == "least_dbs" and db_counts:
            return min(active, key=lambda s: db_counts.get(s.id, 0))
        return active[0]

_auto_approved_envs: set[str] = {"development", "staging"}


def get_auto_approved_environments() -> list[str]:
    return sorted(_auto_approved_envs)


def set_auto_approved_environments(envs: list[str]) -> None:
    global _auto_approved_envs
    _auto_approved_envs = {e.lower().strip() for e in envs if e.strip()}


class ApprovalService:
    def is_auto_approved(self, environment: str) -> bool:
        return environment.lower() in _auto_approved_envs

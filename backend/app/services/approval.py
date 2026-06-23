AUTO_APPROVED_ENVIRONMENTS = {"development", "staging"}


class ApprovalService:
    def is_auto_approved(self, environment: str) -> bool:
        return environment.lower() in AUTO_APPROVED_ENVIRONMENTS

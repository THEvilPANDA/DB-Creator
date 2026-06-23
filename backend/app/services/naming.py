import re


class NamingService:
    def resolve(self, pattern: str, **kwargs: str) -> str:
        result = pattern
        for key, value in kwargs.items():
            result = result.replace(f"{{{key}}}", value)
        return result

    def validate_name(self, name: str, reserved: list[str]) -> None:
        if name.lower() in [r.lower() for r in reserved]:
            raise ValueError(f"'{name}' is a reserved name")
        if not re.match(r"^[a-z][a-z0-9_]{0,62}$", name):
            raise ValueError(
                f"'{name}' is invalid: must start with a letter, "
                "contain only lowercase letters, digits, and underscores, "
                "and be at most 63 characters"
            )

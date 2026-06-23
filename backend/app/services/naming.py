import re
from collections.abc import Awaitable, Callable
from typing import Optional


class NamingService:
    def resolve(self, pattern: str, **kwargs: str) -> str:
        """Substitute {placeholder} tokens in a pattern string."""
        result = pattern
        for key, value in kwargs.items():
            result = result.replace(f"{{{key}}}", value)
        return result

    def apply_profile(self, profile: object, context: dict[str, str]) -> str:
        """Resolve pattern and apply prefix/suffix from a NamingProfile."""
        raw = self.resolve(getattr(profile, "pattern", ""), **context)
        sep_val = getattr(profile, "separator", None)
        sep = "_" if sep_val is None else sep_val
        parts: list[str] = []
        if prefix := getattr(profile, "prefix", None):
            parts.append(prefix)
        parts.append(raw)
        if suffix := getattr(profile, "suffix", None):
            parts.append(suffix)
        return sep.join(parts)

    def validate_name(self, name: str, reserved: list[str]) -> None:
        """Raise ValueError if name is reserved or fails the PostgreSQL identifier rules."""
        if name.lower() in [r.lower() for r in reserved]:
            raise ValueError(f"'{name}' is a reserved name")
        if not re.match(r"^[a-z][a-z0-9_]{0,62}$", name):
            raise ValueError(
                f"'{name}' is invalid: must start with a lowercase letter, "
                "contain only lowercase letters, digits, and underscores, "
                "and be at most 63 characters"
            )

    async def generate(
        self,
        profile: object,
        context: dict[str, str],
        check_exists: Optional[Callable[[str], Awaitable[bool]]] = None,
    ) -> str:
        """
        Resolve pattern, validate, and optionally detect/resolve name collisions.

        If allow_collision=False and check_exists is provided, appends _1, _2, …
        until a unique name is found (up to 99 attempts).
        """
        name = self.apply_profile(profile, context)
        reserved: list[str] = getattr(profile, "reserved_names", None) or []
        self.validate_name(name, reserved)

        allow_collision: bool = getattr(profile, "allow_collision", True)
        if not allow_collision and check_exists and await check_exists(name):
            sep = getattr(profile, "separator", "_") or "_"
            for i in range(1, 100):
                candidate = f"{name}{sep}{i}"
                try:
                    self.validate_name(candidate, reserved)
                except ValueError:
                    continue
                if not await check_exists(candidate):
                    name = candidate
                    break
            else:
                raise ValueError(
                    f"Cannot generate a unique name from pattern '{getattr(profile, 'pattern', '')}' "
                    "after 99 attempts"
                )

        return name

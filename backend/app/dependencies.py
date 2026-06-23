from fastapi import Request


def get_arq(request: Request):
    """Return the Arq Redis pool from app state, or None if Redis is unavailable."""
    return getattr(request.app.state, "arq", None)

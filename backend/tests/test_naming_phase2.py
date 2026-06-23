"""Unit tests for Phase 2 naming enhancements."""
import pytest

from app.services.naming import NamingService


class _Profile:
    """Minimal naming profile stub for testing."""
    def __init__(self, pattern, prefix=None, suffix=None, separator="_",
                 reserved_names=None, allow_collision=False):
        self.pattern = pattern
        self.prefix = prefix
        self.suffix = suffix
        self.separator = separator
        self.reserved_names = reserved_names or []
        self.allow_collision = allow_collision


@pytest.fixture
def svc():
    return NamingService()


def test_apply_profile_no_affixes(svc):
    p = _Profile("{environment}_{owner}_{db_name}")
    result = svc.apply_profile(p, {"environment": "dev", "owner": "alice", "db_name": "myapp"})
    assert result == "dev_alice_myapp"


def test_apply_profile_with_prefix(svc):
    p = _Profile("{db_name}", prefix="acme")
    result = svc.apply_profile(p, {"db_name": "orders"})
    assert result == "acme_orders"


def test_apply_profile_with_suffix(svc):
    p = _Profile("{db_name}", suffix="v2")
    result = svc.apply_profile(p, {"db_name": "orders"})
    assert result == "orders_v2"


def test_apply_profile_prefix_and_suffix(svc):
    p = _Profile("{db_name}", prefix="acme", suffix="prod")
    result = svc.apply_profile(p, {"db_name": "orders"})
    assert result == "acme_orders_prod"


def test_apply_profile_custom_separator(svc):
    p = _Profile("{environment}{db_name}", prefix="co", separator="")
    result = svc.apply_profile(p, {"environment": "dev", "db_name": "api"})
    assert result == "codevapi"


@pytest.mark.asyncio
async def test_generate_no_collision(svc):
    p = _Profile("{environment}_{db_name}")
    name = await svc.generate(p, {"environment": "dev", "db_name": "myapp"})
    assert name == "dev_myapp"


@pytest.mark.asyncio
async def test_generate_detects_collision_and_increments(svc):
    existing = {"dev_myapp"}

    async def check(n):
        return n in existing

    p = _Profile("{environment}_{db_name}", allow_collision=False)
    name = await svc.generate(p, {"environment": "dev", "db_name": "myapp"}, check_exists=check)
    assert name == "dev_myapp_1"


@pytest.mark.asyncio
async def test_generate_multiple_collisions(svc):
    existing = {"dev_myapp", "dev_myapp_1", "dev_myapp_2"}

    async def check(n):
        return n in existing

    p = _Profile("{environment}_{db_name}", allow_collision=False)
    name = await svc.generate(p, {"environment": "dev", "db_name": "myapp"}, check_exists=check)
    assert name == "dev_myapp_3"


@pytest.mark.asyncio
async def test_generate_skips_collision_check_when_allow_collision(svc):
    async def check(_n):
        return True  # everything "exists"

    p = _Profile("{db_name}", allow_collision=True)
    name = await svc.generate(p, {"db_name": "shared"}, check_exists=check)
    assert name == "shared"


@pytest.mark.asyncio
async def test_generate_reserved_name_raises(svc):
    p = _Profile("{db_name}", reserved_names=["postgres"])
    with pytest.raises(ValueError, match="reserved"):
        await svc.generate(p, {"db_name": "postgres"})


@pytest.mark.asyncio
async def test_generate_invalid_name_raises(svc):
    p = _Profile("{db_name}")
    with pytest.raises(ValueError):
        await svc.generate(p, {"db_name": "123invalid"})

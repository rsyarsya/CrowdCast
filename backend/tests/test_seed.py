import pytest
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import verify_password
from app.models import CrowdRecord, CrowdStatus, User, UserRole
from app.scripts.seed import seed

pytestmark = pytest.mark.anyio


async def test_seed_loads_simulation_and_is_idempotent(
    db_session: AsyncSession,
) -> None:
    settings = get_settings().model_copy(
        update={
            "FIRST_SUPERUSER_EMAIL": "admin@crowdcast.test",
            "FIRST_SUPERUSER_PASSWORD": SecretStr("rahasia-admin"),
        }
    )

    first = await seed(db_session, settings)
    second = await seed(db_session, settings)

    assert (first.cameras, first.crowd_records, first.admin_created) == (1, 3, True)
    assert (second.cameras, second.crowd_records, second.admin_created) == (1, 3, False)

    statuses = (
        await db_session.scalars(
            select(CrowdRecord.crowd_status).order_by(CrowdRecord.timestamp)
        )
    ).all()
    assert statuses == [CrowdStatus.SEPI, CrowdStatus.NORMAL, CrowdStatus.RAMAI]

    admin = (await db_session.execute(select(User))).scalar_one()
    assert admin.role is UserRole.ADMIN
    assert verify_password("rahasia-admin", admin.hashed_password)


async def test_seed_skips_admin_without_credentials(db_session: AsyncSession) -> None:
    settings = get_settings().model_copy(
        update={"FIRST_SUPERUSER_EMAIL": None, "FIRST_SUPERUSER_PASSWORD": None}
    )
    result = await seed(db_session, settings)
    assert result.admin_created is False
    assert await db_session.scalar(select(User.id)) is None

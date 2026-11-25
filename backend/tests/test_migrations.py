from alembic import command

from tests.conftest import alembic_config


def test_models_match_latest_migration() -> None:
    """Fails when a model changed without a new Alembic migration."""
    command.check(alembic_config())


def test_migrations_downgrade_and_upgrade_cleanly() -> None:
    config = alembic_config()
    command.downgrade(config, "base")
    command.upgrade(config, "head")

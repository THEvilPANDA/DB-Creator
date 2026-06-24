from app.services.provisioner.postgresql import PostgreSQLProvisioner


class PgvectorProvisioner(PostgreSQLProvisioner):
    """PostgreSQL provisioner that always enables the vector extension."""

    async def enable_extensions(self, db_name: str, extensions: list[str]) -> None:
        # Prepend 'vector'; deduplicate while preserving remaining order
        exts = ["vector"] + [e for e in extensions if e != "vector"]
        await super().enable_extensions(db_name, exts)

"""Generate IaC snippets (YAML + Terraform) after a database is provisioned."""
from datetime import datetime, timezone


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def generate_yaml(
    db_name: str,
    db_user: str,
    host: str,
    port: int,
    environment: str,
    engine: str = "postgresql",
) -> str:
    return f"""\
# DB Creator — Generated {_stamp()}
# Environment: {environment}
database:
  name: {db_name}
  user: {db_user}
  host: {host}
  port: {port}
  environment: {environment}
  engine: {engine}

# Environment variables (set DB_PASSWORD via your secret manager):
# DB_HOST={host}
# DB_PORT={port}
# DB_NAME={db_name}
# DB_USER={db_user}
# DB_PASSWORD=<from secret manager>
# DATABASE_URL=postgresql://{db_user}:${{DB_PASSWORD}}@{host}:{port}/{db_name}
"""


def generate_terraform(
    db_name: str,
    db_user: str,
    host: str,
    port: int,
) -> str:
    res = db_name.replace("-", "_")
    return f"""\
# DB Creator — Generated {_stamp()}
# Requires: terraform-provider-postgresql (https://registry.terraform.io/providers/cyrilgdn/postgresql)

variable "{db_user}_password" {{
  description = "Password for role {db_user}"
  type        = string
  sensitive   = true
}}

resource "postgresql_role" "{db_user}" {{
  name     = "{db_user}"
  login    = true
  password = var.{db_user}_password
}}

resource "postgresql_database" "{res}" {{
  name  = "{db_name}"
  owner = postgresql_role.{db_user}.name

  lifecycle {{
    prevent_destroy = true
  }}
}}

resource "postgresql_grant" "{res}_connect" {{
  database    = postgresql_database.{res}.name
  role        = postgresql_role.{db_user}.name
  object_type = "database"
  privileges  = ["CONNECT", "CREATE"]
}}
"""

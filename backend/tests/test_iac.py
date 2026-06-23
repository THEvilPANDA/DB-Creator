"""Unit tests for IaC snippet generation."""
from app.services.iac import generate_terraform, generate_yaml


def test_yaml_contains_key_fields():
    out = generate_yaml("myapp_db", "myapp_db_user", "db.example.com", 5432, "production")
    assert "myapp_db" in out
    assert "myapp_db_user" in out
    assert "db.example.com" in out
    assert "5432" in out
    assert "production" in out
    assert "DB_NAME=myapp_db" in out
    assert "DB_USER=myapp_db_user" in out


def test_yaml_includes_connection_url():
    out = generate_yaml("orders", "orders_user", "localhost", 5432, "staging")
    assert "postgresql://orders_user:" in out
    assert "@localhost:5432/orders" in out


def test_terraform_contains_resources():
    out = generate_terraform("myapp_db", "myapp_db_user", "db.example.com", 5432)
    assert 'resource "postgresql_database"' in out
    assert 'resource "postgresql_role"' in out
    assert 'resource "postgresql_grant"' in out
    assert "myapp_db" in out
    assert "myapp_db_user" in out
    assert "prevent_destroy" in out


def test_terraform_resource_name_sanitizes_hyphens():
    out = generate_terraform("my-app-db", "my_app_db_user", "localhost", 5432)
    assert '"my_app_db"' in out


def test_yaml_and_terraform_both_generated():
    yaml = generate_yaml("db1", "db1_user", "host", 5432, "dev")
    tf = generate_terraform("db1", "db1_user", "host", 5432)
    assert yaml
    assert tf
    assert yaml != tf

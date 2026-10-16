"""Logical database types and their SQL compatibility family."""


def is_postgres_compatible(database_type: str) -> bool:
    return database_type.lower() in {"postgres", "postgresql", "kingbase"}


def sql_dialect(database_type: str) -> str:
    return "postgres" if is_postgres_compatible(database_type) else database_type.lower()

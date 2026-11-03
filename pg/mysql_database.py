"""MySQL connection settings for Railway and local development."""

import os
from pathlib import Path
from urllib.parse import unquote, urlparse

import mysql.connector
from dotenv import load_dotenv
from mysql.connector import MySQLConnection

load_dotenv(Path(__file__).with_name(".env"))


def get_connection() -> MySQLConnection:
    """Connect using Railway URL variables or Railway/standard MySQL variables.

    MYSQL_PUBLIC_URL is preferred for a desktop client outside Railway.
    A local pg/.env file is loaded without overriding existing environment values.
    """
    database_url = os.getenv("MYSQL_PUBLIC_URL") or os.getenv("MYSQL_URL")
    if database_url:
        parsed = urlparse(database_url)
        if parsed.scheme not in ("mysql", "mysql+mysqlconnector"):
            raise RuntimeError("MySQL URL must use the mysql:// scheme")
        if not parsed.hostname or not parsed.username or parsed.password is None:
            raise RuntimeError("MySQL URL must include username, password, and host")
        database = unquote(parsed.path.lstrip("/"))
        if not database:
            raise RuntimeError("MySQL URL must include a database name")
        settings = {
            "host": parsed.hostname,
            "port": parsed.port or 3306,
            "user": unquote(parsed.username),
            "password": unquote(parsed.password),
            "database": database,
        }
    else:
        settings = {
            "host": os.getenv("MYSQLHOST") or os.getenv("MYSQL_HOST"),
            "port": os.getenv("MYSQLPORT") or os.getenv("MYSQL_PORT") or "3306",
            "user": os.getenv("MYSQLUSER") or os.getenv("MYSQL_USER"),
            "password": os.getenv("MYSQLPASSWORD") or os.getenv("MYSQL_PASSWORD"),
            "database": os.getenv("MYSQLDATABASE") or os.getenv("MYSQL_DATABASE"),
        }
        missing = [
            name
            for name, value in (
                ("MYSQLHOST", settings["host"]),
                ("MYSQLUSER", settings["user"]),
                ("MYSQLPASSWORD", settings["password"]),
                ("MYSQLDATABASE", settings["database"]),
            )
            if not value
        ]
        if missing:
            raise RuntimeError(
                "Missing MySQL settings. Set MYSQL_PUBLIC_URL or configure: "
                + ", ".join(missing)
            )
        settings["port"] = int(settings["port"])

    return mysql.connector.connect(
        **settings,
        connection_timeout=10,
        charset="utf8mb4",
    )

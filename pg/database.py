"""Railway MySQL storage for detection results and tray names."""

from contextlib import contextmanager
from datetime import datetime
import hashlib
import hmac
import re
import secrets

import mysql.connector
from mysql_database import get_connection

PASSWORD_HASH_ITERATIONS = 600_000


class AccountAlreadyExistsError(ValueError):
    """Raised when a username or email is already registered."""


@contextmanager
def _db():
    """Commit on success and always close the cursor and connection."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        yield cursor
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


def init_db() -> None:
    """Create the application tables if they do not exist."""
    with _db() as cursor:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(50) NOT NULL UNIQUE,
                email VARCHAR(255) NOT NULL UNIQUE,
                password_hash VARCHAR(255) NOT NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS detections (
                detection_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
                user_id INT NULL,
                timestamp DATETIME NOT NULL,
                tray_name VARCHAR(255) NOT NULL,
                full_count INT NOT NULL DEFAULT 0,
                stage2_count INT NOT NULL DEFAULT 0,
                stage3_count INT NOT NULL DEFAULT 0,
                stage4_count INT NOT NULL DEFAULT 0,
                avg_length DOUBLE NOT NULL DEFAULT 0,
                avg_weight DOUBLE NOT NULL DEFAULT 0,
                confidence DOUBLE NULL,
                fps DOUBLE NULL,
                recommendation TEXT NOT NULL,
                KEY idx_detections_user_id (user_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        cursor.execute("SHOW COLUMNS FROM detections LIKE 'user_id'")
        if cursor.fetchone() is None:
            cursor.execute("""
                ALTER TABLE detections
                ADD COLUMN user_id INT NULL,
                ADD KEY idx_detections_user_id (user_id)
            """)
        cursor.execute("SHOW COLUMNS FROM detections LIKE 'detection_id'")
        if cursor.fetchone() is None:
            cursor.execute("SHOW COLUMNS FROM detections LIKE 'id'")
            if cursor.fetchone() is not None:
                cursor.execute("""
                    ALTER TABLE detections
                    CHANGE COLUMN id detection_id BIGINT UNSIGNED
                    NOT NULL AUTO_INCREMENT
                """)
        cursor.execute("SHOW COLUMNS FROM detections LIKE 'tray_name'")
        if cursor.fetchone() is None:
            cursor.execute("SHOW COLUMNS FROM detections LIKE 'tray'")
            if cursor.fetchone() is not None:
                cursor.execute("""
                    ALTER TABLE detections
                    CHANGE COLUMN tray tray_name VARCHAR(255) NOT NULL
                """)
            else:
                cursor.execute("""
                    ALTER TABLE detections
                    ADD COLUMN tray_name VARCHAR(255) NOT NULL DEFAULT ''
            """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tray (
                tray_id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                tray_name VARCHAR(255) NOT NULL,
                KEY fk_tray_user (user_id),
                CONSTRAINT fk_tray_user_id FOREIGN KEY (user_id)
                    REFERENCES users (user_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)


def _hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PASSWORD_HASH_ITERATIONS,
    )
    return (
        f"pbkdf2_sha256${PASSWORD_HASH_ITERATIONS}"
        f"${salt.hex()}${password_hash.hex()}"
    )


def _verify_password(password: str, encoded_hash: str) -> bool:
    try:
        algorithm, iterations, salt_hex, expected_hex = encoded_hash.split("$")
        if algorithm != "pbkdf2_sha256" or int(iterations) != PASSWORD_HASH_ITERATIONS:
            return False
        salt = bytes.fromhex(salt_hex)
        expected_hash = bytes.fromhex(expected_hex)
    except (ValueError, TypeError):
        return False

    actual_hash = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PASSWORD_HASH_ITERATIONS
    )
    return hmac.compare_digest(actual_hash, expected_hash)


def create_user(username: str, email: str, password: str) -> int:
    """Create an account with a salted, one-way password hash."""
    username = username.strip()
    email = email.strip().lower()
    if not re.fullmatch(r"[A-Za-z0-9_]{3,50}", username):
        raise ValueError("Username must be 3-50 characters and contain only a-z, 0-9, or _.")
    if len(email) > 254 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise ValueError("Please enter a valid email address.")
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters long.")

    try:
        with _db() as cursor:
            cursor.execute(
                """INSERT INTO users (username, email, password_hash)
                   VALUES (%s, %s, %s)""",
                (username, email, _hash_password(password)),
            )
            user_id = cursor.lastrowid
    except mysql.connector.IntegrityError as error:
        if error.errno == 1062:
            raise AccountAlreadyExistsError(
                "This username or email is already registered."
            ) from error
        raise
    if user_id is None:
        raise RuntimeError("MySQL did not return an ID for the created account")
    return user_id


def authenticate_user(identifier: str, password: str) -> tuple[int, str] | None:
    """Authenticate by username or email; return user_id and username."""
    with _db() as cursor:
        cursor.execute(
            """SELECT user_id, username, password_hash FROM users
               WHERE username = %s OR email = %s
               LIMIT 2""",
            (identifier, identifier),
        )
        rows = cursor.fetchall()

        if len(rows) != 1 or not _verify_password(
            password, rows[0]["password_hash"]
        ):
            return None
        return rows[0]["user_id"], rows[0]["username"]


def reset_db() -> None:
    """Delete all application rows while keeping the MySQL tables intact."""
    with _db() as cursor:
        cursor.execute("DELETE FROM detections")
        cursor.execute("DELETE FROM tray")


def add_detection(tray: str, result: dict, user_id: int | None = None) -> int:
    """Save a detection and return its new row ID."""
    if user_id is None:
        raise ValueError("Please log in before saving detection results.")
    with _db() as cursor:
        cursor.execute(
            "SELECT tray_id FROM tray WHERE user_id = %s AND tray_name = %s LIMIT 1",
            (user_id, tray),
        )
        if cursor.fetchone() is None:
            raise ValueError("This tray was not found in your account.")
        cursor.execute(
            """INSERT INTO detections
                    (user_id, timestamp, tray_name, full_count, stage2_count,
                     stage3_count, stage4_count, avg_length, avg_weight,
                     confidence, fps, recommendation)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                user_id,
                datetime.now(),
                tray,
                result.get("full", 0),
                result.get("stage2", 0),
                result.get("stage3", 0),
                result.get("stage4", 0),
                result.get("avg_length", 0.0),
                result.get("avg_weight", 0.0),
                result.get("confidence"),
                result.get("fps"),
                result.get("recommendation", ""),
            ),
        )
        if cursor.lastrowid is None:
            raise RuntimeError("MySQL did not return an ID for the saved detection")
        return cursor.lastrowid


def get_history(user_id: int, limit: int = 200) -> list[dict]:
    """Return the newest detection rows for one user."""
    with _db() as cursor:
        cursor.execute(
            "SELECT * FROM detections WHERE user_id = %s "
            "ORDER BY detection_id DESC LIMIT %s",
            (user_id, limit),
        )
        return cursor.fetchall()


def get_new_detections(after_id: int = 0) -> list[dict]:
    """Return detection rows newer than after_id, oldest first."""
    with _db() as cursor:
        cursor.execute(
            "SELECT * FROM detections WHERE detection_id > %s "
            "ORDER BY detection_id ASC",
            (after_id,),
        )
        return cursor.fetchall()


def get_trays(user_id: int | None = None) -> list[str]:
    """Return only tray names owned by the specified user."""
    if user_id is None:
        return []
    with _db() as cursor:
        cursor.execute(
            "SELECT tray_name FROM tray WHERE user_id = %s ORDER BY tray_id",
            (user_id,),
        )
        return [row["tray_name"] for row in cursor.fetchall()]


def add_tray(name: str, user_id: int | None = None) -> None:
    """Register a tray under its owner unless that owner already has it."""
    if user_id is None:
        raise ValueError("Please log in before adding a tray.")
    with _db() as cursor:
        cursor.execute(
            "SELECT tray_id FROM tray WHERE user_id = %s AND tray_name = %s LIMIT 1",
            (user_id, name),
        )
        if cursor.fetchone() is not None:
            return
        cursor.execute(
            "INSERT INTO tray (user_id, tray_name) VALUES (%s, %s)",
            (user_id, name),
        )

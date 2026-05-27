from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from config import DB_PATH
from storage import get_connection

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
PASSWORD_MIN_LENGTH = 8
PASSWORD_ITERATIONS = 120_000
SESSION_DAYS = 14


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def normalize_email(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip().lower()


def is_valid_email(email: str) -> bool:
    return bool(EMAIL_RE.fullmatch(email))


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PASSWORD_ITERATIONS,
    )
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, iterations, salt_hex, digest_hex = stored_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt_hex),
            int(iterations),
        )
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (TypeError, ValueError):
        return False


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def public_user(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "email": row["email"],
        "created_at": row["created_at"],
    }


def create_session(connection: sqlite3.Connection, user_id: int) -> dict[str, str]:
    token = secrets.token_urlsafe(32)
    created_at = utc_now_iso()
    expires_at = (datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS)).isoformat(timespec="seconds")
    connection.execute(
        """
        INSERT INTO sessions (token_hash, user_id, created_at, expires_at)
        VALUES (?, ?, ?, ?)
        """,
        (token_hash(token), user_id, created_at, expires_at),
    )
    return {"token": token, "expires_at": expires_at}


def signup_user(body: dict[str, Any], db_path: Path = DB_PATH) -> tuple[dict[str, Any], int]:
    email = normalize_email(body.get("email"))
    password = body.get("password")
    if not is_valid_email(email):
        return {"error": "invalid_email"}, 400
    if not isinstance(password, str) or len(password) < PASSWORD_MIN_LENGTH:
        return {"error": "weak_password", "min_length": PASSWORD_MIN_LENGTH}, 400

    timestamp = utc_now_iso()
    with closing(get_connection(db_path)) as connection:
        try:
            cursor = connection.execute(
                """
                INSERT INTO users (email, password_hash, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                (email, hash_password(password), timestamp, timestamp),
            )
        except sqlite3.IntegrityError:
            return {"error": "email_exists"}, 409

        user_id = int(cursor.lastrowid)
        session = create_session(connection, user_id)
        user = connection.execute(
            "SELECT id, email, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        connection.commit()

    assert user is not None
    return {"user": public_user(user), **session}, 201


def login_user(body: dict[str, Any], db_path: Path = DB_PATH) -> tuple[dict[str, Any], int]:
    email = normalize_email(body.get("email"))
    password = body.get("password")
    if not is_valid_email(email) or not isinstance(password, str):
        return {"error": "invalid_credentials"}, 401

    with closing(get_connection(db_path)) as connection:
        user = connection.execute(
            "SELECT id, email, password_hash, created_at FROM users WHERE email = ?",
            (email,),
        ).fetchone()
        if user is None or not verify_password(password, user["password_hash"]):
            return {"error": "invalid_credentials"}, 401

        timestamp = utc_now_iso()
        connection.execute(
            "UPDATE users SET last_login_at = ?, updated_at = ? WHERE id = ?",
            (timestamp, timestamp, user["id"]),
        )
        session = create_session(connection, int(user["id"]))
        connection.commit()

    return {"user": public_user(user), **session}, 200


def bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return token.strip()


def user_from_token(token: str | None, db_path: Path = DB_PATH) -> dict[str, Any] | None:
    if not token:
        return None
    now = utc_now_iso()
    with closing(get_connection(db_path)) as connection:
        row = connection.execute(
            """
            SELECT users.id, users.email, users.created_at
            FROM sessions
            JOIN users ON users.id = sessions.user_id
            WHERE sessions.token_hash = ? AND sessions.expires_at > ?
            """,
            (token_hash(token), now),
        ).fetchone()
    return public_user(row) if row else None


def user_from_authorization(authorization: str | None, db_path: Path = DB_PATH) -> dict[str, Any] | None:
    return user_from_token(bearer_token(authorization), db_path=db_path)


def logout_token(token: str | None, db_path: Path = DB_PATH) -> None:
    if not token:
        return
    with closing(get_connection(db_path)) as connection:
        connection.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash(token),))
        connection.commit()

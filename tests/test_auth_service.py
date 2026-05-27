from __future__ import annotations

import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from services.auth_service import (
    login_user,
    logout_token,
    signup_user,
    user_from_token,
    verify_password,
)
from storage import get_connection, init_db


class AuthServiceTests(unittest.TestCase):
    def test_signup_creates_email_account_and_session(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "whystock-auth-test.db"
            init_db(db_path)

            payload, status = signup_user(
                {"email": "USER@example.com", "password": "password123"},
                db_path=db_path,
            )

            self.assertEqual(status, 201)
            self.assertEqual(payload["user"]["email"], "user@example.com")
            self.assertIn("token", payload)
            self.assertEqual(user_from_token(payload["token"], db_path=db_path)["email"], "user@example.com")

            with closing(get_connection(db_path)) as connection:
                row = connection.execute("SELECT password_hash FROM users WHERE email = ?", ("user@example.com",)).fetchone()

            self.assertIsNotNone(row)
            assert row is not None
            self.assertNotEqual(row["password_hash"], "password123")
            self.assertTrue(verify_password("password123", row["password_hash"]))

    def test_signup_rejects_non_email_identifier(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "whystock-auth-test.db"
            init_db(db_path)

            payload, status = signup_user(
                {"email": "not-an-email", "password": "password123"},
                db_path=db_path,
            )

            self.assertEqual(status, 400)
            self.assertEqual(payload["error"], "invalid_email")

    def test_duplicate_email_and_invalid_login_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "whystock-auth-test.db"
            init_db(db_path)
            signup_user({"email": "user@example.com", "password": "password123"}, db_path=db_path)

            duplicate_payload, duplicate_status = signup_user(
                {"email": "USER@example.com", "password": "password123"},
                db_path=db_path,
            )
            invalid_payload, invalid_status = login_user(
                {"email": "user@example.com", "password": "wrong-password"},
                db_path=db_path,
            )

            self.assertEqual(duplicate_status, 409)
            self.assertEqual(duplicate_payload["error"], "email_exists")
            self.assertEqual(invalid_status, 401)
            self.assertEqual(invalid_payload["error"], "invalid_credentials")

    def test_login_and_logout_session(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "whystock-auth-test.db"
            init_db(db_path)
            signup_user({"email": "user@example.com", "password": "password123"}, db_path=db_path)

            payload, status = login_user(
                {"email": "user@example.com", "password": "password123"},
                db_path=db_path,
            )

            self.assertEqual(status, 200)
            self.assertEqual(user_from_token(payload["token"], db_path=db_path)["email"], "user@example.com")

            logout_token(payload["token"], db_path=db_path)

            self.assertIsNone(user_from_token(payload["token"], db_path=db_path))


if __name__ == "__main__":
    unittest.main()

"""Password hashing and signed auth token helpers."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone


def _b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("utf-8")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}".encode("utf-8"))


def hash_password(password: str, *, iterations: int = 120_000) -> str:
    salt = secrets.token_hex(16)
    derived = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations,
    )
    return f"pbkdf2_sha256${iterations}${salt}${derived.hex()}"


def verify_password(password: str, stored_hash: str | None) -> bool:
    if not stored_hash:
        return False
    try:
        algorithm, raw_iterations, salt, expected_hash = stored_hash.split("$", 3)
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    derived = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        int(raw_iterations),
    )
    return hmac.compare_digest(derived.hex(), expected_hash)


def create_access_token(payload: dict[str, object], secret_key: str, expires_minutes: int) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    exp = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
    token_payload = {**payload, "exp": int(exp.timestamp())}
    encoded_header = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    encoded_payload = _b64url_encode(json.dumps(token_payload, separators=(",", ":")).encode("utf-8"))
    message = f"{encoded_header}.{encoded_payload}".encode("utf-8")
    signature = hmac.new(secret_key.encode("utf-8"), message, hashlib.sha256).digest()
    return f"{encoded_header}.{encoded_payload}.{_b64url_encode(signature)}"


def decode_access_token(token: str, secret_key: str) -> dict[str, object] | None:
    try:
        encoded_header, encoded_payload, encoded_signature = token.split(".", 2)
    except ValueError:
        return None
    message = f"{encoded_header}.{encoded_payload}".encode("utf-8")
    expected_signature = hmac.new(secret_key.encode("utf-8"), message, hashlib.sha256).digest()
    if not hmac.compare_digest(_b64url_encode(expected_signature), encoded_signature):
        return None
    try:
        payload = json.loads(_b64url_decode(encoded_payload).decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
        return None
    exp = payload.get("exp")
    if not isinstance(exp, int):
        return None
    if datetime.now(timezone.utc).timestamp() > exp:
        return None
    return payload
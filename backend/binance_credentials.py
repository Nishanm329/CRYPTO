"""
Storage for the user's (encrypted) Binance API credentials.

This app has no database wired up — every other piece of persisted state
(track_record.py, bot_engine.py) lives in a local JSON file, so credentials
follow the same pattern rather than standing up SQLAlchemy just for this.
The API key/secret values themselves are Fernet-encrypted at rest via
crypto_utils.py; only the encrypted blobs ever touch disk.
"""
import json
import os
from datetime import datetime
from typing import Optional

CREDS_FILE = os.path.join(os.path.dirname(__file__), "binance_credentials.json")


def _load() -> Optional[dict]:
    if not os.path.exists(CREDS_FILE):
        return None
    try:
        with open(CREDS_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return None


def _save(data: Optional[dict]) -> None:
    tmp = CREDS_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f)
    os.replace(tmp, CREDS_FILE)
    try:
        os.chmod(CREDS_FILE, 0o600)
    except Exception:
        pass


def get_credentials() -> Optional[dict]:
    return _load()


def store_credentials(api_key_encrypted: str, api_secret_encrypted: str, key_hash: str) -> dict:
    existing = _load()
    now = datetime.utcnow().isoformat()
    data = {
        "api_key_encrypted": api_key_encrypted,
        "api_secret_encrypted": api_secret_encrypted,
        "key_hash": key_hash,
        "validation_status": "UNVERIFIED",
        "created_at": existing["created_at"] if existing else now,
        "last_validated_at": None,
    }
    _save(data)
    return data


def update_validation_status(is_valid: bool) -> Optional[dict]:
    data = _load()
    if data is None:
        return None
    data["validation_status"] = "VERIFIED" if is_valid else "INVALID"
    data["last_validated_at"] = datetime.utcnow().isoformat()
    _save(data)
    return data


def delete_credentials() -> None:
    if os.path.exists(CREDS_FILE):
        os.remove(CREDS_FILE)

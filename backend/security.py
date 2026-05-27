"""API key authentication and authorization."""

import os
import hashlib
import hmac
from typing import Optional
from datetime import datetime, timedelta
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from models import UserPreferencesDB
from db import SessionLocal
from logging_config import get_logger

logger = get_logger(__name__)


class APIKeyManager:
    """Manage API keys and quotas."""

    # Valid API keys loaded from environment
    # Format: API_KEYS=key1:user1,key2:user2
    VALID_KEYS: dict = {}

    @classmethod
    def load_keys(cls) -> None:
        """Load API keys from environment variables."""
        keys_str = os.getenv("API_KEYS", "demo-key-public:demo-user")
        cls.VALID_KEYS = {}

        for entry in keys_str.split(","):
            if ":" in entry:
                api_key, user_id = entry.split(":", 1)
                cls.VALID_KEYS[api_key.strip()] = user_id.strip()

        logger.info(
            f"Loaded {len(cls.VALID_KEYS)} API keys",
            action="api_keys_loaded",
            count=len(cls.VALID_KEYS),
        )

    @classmethod
    def verify_api_key(cls, api_key: str) -> Optional[str]:
        """
        Verify API key and return associated user_id.

        Args:
            api_key: API key from Authorization header

        Returns:
            user_id if valid, None otherwise
        """
        if not cls.VALID_KEYS:
            cls.load_keys()

        user_id = cls.VALID_KEYS.get(api_key)
        if user_id:
            logger.debug(
                f"API key verified for user {user_id}",
                action="api_key_verified",
                user_id=user_id,
            )
        else:
            logger.warning(
                "Invalid API key attempt",
                action="invalid_api_key",
                key_hash=hashlib.sha256(api_key.encode()).hexdigest()[:8],
            )

        return user_id


class QuotaManager:
    """Manage per-API-key rate limits and quotas."""

    # In-memory quotas (in production, use Redis)
    # Format: {user_id: {"requests_today": N, "reset_at": datetime}}
    QUOTAS: dict = {}

    # Quota tiers (requests per day)
    TIERS = {
        "demo": 100,      # Free tier
        "pro": 1000,      # Pro tier
        "enterprise": 10000,  # Enterprise tier
    }

    @classmethod
    def get_tier(cls, user_id: str) -> str:
        """Determine user tier. MVP: hardcoded, later use subscription service."""
        # TODO: Query subscription table when available
        if user_id.startswith("pro_"):
            return "pro"
        elif user_id.startswith("enterprise_"):
            return "enterprise"
        return "demo"

    @classmethod
    def get_quota(cls, user_id: str) -> int:
        """Get daily quota for user."""
        tier = cls.get_tier(user_id)
        return cls.TIERS.get(tier, cls.TIERS["demo"])

    @classmethod
    def check_quota(cls, user_id: str) -> dict:
        """
        Check if user has remaining quota.

        Returns:
            {
                "remaining": int,
                "limit": int,
                "reset_at": ISO timestamp,
                "exceeded": bool
            }
        """
        now = datetime.utcnow()
        quota_limit = cls.get_quota(user_id)

        # Initialize or reset quota
        if user_id not in cls.QUOTAS:
            cls.QUOTAS[user_id] = {
                "requests_today": 0,
                "reset_at": now + timedelta(days=1),
            }
        elif now >= cls.QUOTAS[user_id]["reset_at"]:
            # Reset daily quota
            cls.QUOTAS[user_id] = {
                "requests_today": 0,
                "reset_at": now + timedelta(days=1),
            }

        quota_entry = cls.QUOTAS[user_id]
        remaining = quota_limit - quota_entry["requests_today"]
        exceeded = remaining <= 0

        return {
            "remaining": max(0, remaining),
            "limit": quota_limit,
            "reset_at": quota_entry["reset_at"].isoformat(),
            "exceeded": exceeded,
        }

    @classmethod
    def increment_quota(cls, user_id: str) -> None:
        """Increment request count for user."""
        quota_info = cls.check_quota(user_id)
        if user_id in cls.QUOTAS:
            cls.QUOTAS[user_id]["requests_today"] += 1

    @classmethod
    def enforce_quota(cls, user_id: str) -> None:
        """Raise exception if quota exceeded."""
        quota_info = cls.check_quota(user_id)
        if quota_info["exceeded"]:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": "Daily quota exceeded",
                    "limit": quota_info["limit"],
                    "reset_at": quota_info["reset_at"],
                },
            )


def get_api_key_from_header(authorization: Optional[str]) -> str:
    """
    Extract API key from Authorization header.

    Expected format: "Bearer {api_key}"
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    parts = authorization.split(" ")
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Invalid Authorization header format. Use: "Bearer {api_key}"',
            headers={"WWW-Authenticate": "Bearer"},
        )

    return parts[1]


def authenticate_request(authorization: Optional[str]) -> tuple[str, dict]:
    """
    Authenticate request and return user_id + quota info.

    Args:
        authorization: Authorization header value

    Returns:
        (user_id, quota_info)

    Raises:
        HTTPException: If authentication fails or quota exceeded
    """
    api_key = get_api_key_from_header(authorization)
    user_id = APIKeyManager.verify_api_key(api_key)

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check quota before allowing request
    QuotaManager.enforce_quota(user_id)

    # Increment quota counter
    quota_info = QuotaManager.check_quota(user_id)
    QuotaManager.increment_quota(user_id)

    # Update last_used timestamp in database
    try:
        db = SessionLocal()
        user_prefs = db.query(UserPreferencesDB).filter(
            UserPreferencesDB.user_id == user_id
        ).first()
        if user_prefs:
            user_prefs.api_key_last_used = datetime.utcnow()
            db.commit()
        db.close()
    except Exception as e:
        logger.warning(
            f"Failed to update API key last_used: {e}",
            action="update_last_used_failed",
            user_id=user_id,
        )

    return user_id, quota_info

"""
Cryptographic utilities for securing sensitive data like API keys.
Uses Fernet (symmetric encryption) for at-rest encryption.
"""

import os
from cryptography.fernet import Fernet
from logging_config import get_logger

logger = get_logger(__name__)

# Master encryption key (should be loaded from environment in production)
# In MVP, we generate a key and store it locally
MASTER_KEY_PATH = ".env.crypto"


def _get_or_create_master_key() -> bytes:
    """
    Get or create the master encryption key.
    In production, this would be stored in a secure key management service (AWS KMS, etc).
    """
    if os.path.exists(MASTER_KEY_PATH):
        with open(MASTER_KEY_PATH, "rb") as f:
            return f.read()
    else:
        # Generate new key
        key = Fernet.generate_key()
        # Store it locally (in production, use AWS KMS or similar)
        try:
            with open(MASTER_KEY_PATH, "wb") as f:
                f.write(key)
            # Make file read-only for security
            os.chmod(MASTER_KEY_PATH, 0o600)
            logger.info("Master encryption key created", action="master_key_created")
        except Exception as e:
            logger.error(f"Failed to save master key: {e}", action="master_key_creation_failed")
        return key


def encrypt_api_key(api_key: str) -> str:
    """
    Encrypt an API key using Fernet symmetric encryption.
    Returns the encrypted key as a URL-safe base64 string.
    """
    try:
        master_key = _get_or_create_master_key()
        cipher = Fernet(master_key)
        encrypted = cipher.encrypt(api_key.encode())
        return encrypted.decode()  # Return as string for storage
    except Exception as e:
        logger.error(f"Encryption failed: {e}", action="encryption_failed")
        raise ValueError("Failed to encrypt API key")


def decrypt_api_key(encrypted_key: str) -> str:
    """
    Decrypt an API key using Fernet symmetric encryption.
    """
    try:
        master_key = _get_or_create_master_key()
        cipher = Fernet(master_key)
        decrypted = cipher.decrypt(encrypted_key.encode())
        return decrypted.decode()
    except Exception as e:
        logger.error(f"Decryption failed: {e}", action="decryption_failed")
        raise ValueError("Failed to decrypt API key")


def hash_api_key(api_key: str) -> str:
    """
    Hash an API key for identification/lookup purposes (without storing the actual key).
    Uses SHA256 (one-way hash).
    """
    import hashlib
    return hashlib.sha256(api_key.encode()).hexdigest()


class APIKeyVault:
    """
    Manages secure storage and retrieval of API keys.
    In MVP, stores encrypted keys in memory/database.
    In production, would use AWS Secrets Manager or similar.
    """

    @staticmethod
    def store_credentials(user_id: str, api_key: str, api_secret: str) -> dict:
        """
        Store encrypted API credentials for a user.

        Returns:
            Dict with encryption metadata for verification
        """
        try:
            encrypted_key = encrypt_api_key(api_key)
            encrypted_secret = encrypt_api_key(api_secret)

            logger.info(
                f"Credentials encrypted for user {user_id}",
                action="credentials_encrypted",
                user_id=user_id,
            )

            return {
                "api_key_encrypted": encrypted_key,
                "api_secret_encrypted": encrypted_secret,
                "key_hash": hash_api_key(api_key),  # For verification
            }
        except Exception as e:
            logger.error(
                f"Failed to store credentials: {e}",
                action="credentials_storage_failed",
                user_id=user_id,
            )
            raise

    @staticmethod
    def retrieve_credentials(encrypted_key: str, encrypted_secret: str) -> tuple:
        """
        Retrieve decrypted API credentials.

        Returns:
            Tuple of (api_key, api_secret)
        """
        try:
            api_key = decrypt_api_key(encrypted_key)
            api_secret = decrypt_api_key(encrypted_secret)
            return (api_key, api_secret)
        except Exception as e:
            logger.error(
                f"Failed to retrieve credentials: {e}",
                action="credentials_retrieval_failed",
            )
            raise

    @staticmethod
    def verify_key_integrity(api_key: str, key_hash: str) -> bool:
        """
        Verify that an API key matches its stored hash.
        Used for validation without decrypting the stored key.
        """
        current_hash = hash_api_key(api_key)
        return current_hash == key_hash

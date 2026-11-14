
import os

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from django.db import models


def get_bank_encryption_key():
    """Return the primary bank encryption key as bytes."""

    key = os.environ.get("BANK_ENCRYPTION_KEY")

    if not key:
        raise RuntimeError(
            "BANK_ENCRYPTION_KEY environment variable is not set."
        )

    return key.encode()


def get_bank_encryption_keys():
    """Return the primary and previous Fernet encryption keys."""

    primary_key = get_bank_encryption_key().decode()
    old_keys = os.environ.get("BANK_ENCRYPTION_OLD_KEYS", "")

    keys = [primary_key]

    if old_keys.strip():
        keys.extend(
            key.strip()
            for key in old_keys.split(",")
            if key.strip()
        )

    try:
        return [Fernet(key.encode()) for key in keys]
    except (TypeError, ValueError) as exc:
        raise RuntimeError(
            "Bank encryption configuration contains an invalid Fernet key."
        ) from exc


def get_bank_cipher():
    """Return a MultiFernet instance using the primary key first."""

    return MultiFernet(get_bank_encryption_keys())


def encrypt_bank_data(value):
    """Encrypt a bank data value using the primary key."""

    if value in (None, ""):
        return value

    cipher = get_bank_cipher()
    return cipher.encrypt(str(value).encode()).decode()


def decrypt_bank_data(value):
    """Decrypt bank data using the primary or a previous key."""

    if value in (None, ""):
        return value

    cipher = get_bank_cipher()

    try:
        return cipher.decrypt(value.encode()).decode()
    except InvalidToken as exc:
        raise ValueError(
            "Unable to decrypt bank data."
        ) from exc


class EncryptedCharField(models.CharField):
    """Store a CharField encrypted in the database."""

    def get_prep_value(self, value):
        """Encrypt plaintext before storing it in the database."""

        value = super().get_prep_value(value)

        if value in (None, ""):
            return value

        return encrypt_bank_data(value)

    def from_db_value(self, value, expression, connection):
        """Decrypt the value when it is loaded from the database."""

        if value in (None, ""):
            return value

        return decrypt_bank_data(value)

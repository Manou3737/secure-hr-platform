import os

from cryptography.fernet import Fernet, InvalidToken
from django.db import models


def get_bank_encryption_key():
    """Return the encryption key used for sensitive bank data."""

    key = os.environ.get("BANK_ENCRYPTION_KEY")

    if not key:
        raise RuntimeError(
            "BANK_ENCRYPTION_KEY environment variable is not set."
        )

    return key.encode()


def encrypt_bank_data(value):
    """Encrypt a bank data value."""

    if value in (None, ""):
        return value

    cipher = Fernet(get_bank_encryption_key())
    return cipher.encrypt(str(value).encode()).decode()


def decrypt_bank_data(value):
    """Decrypt a bank data value."""

    if value in (None, ""):
        return value

    cipher = Fernet(get_bank_encryption_key())

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

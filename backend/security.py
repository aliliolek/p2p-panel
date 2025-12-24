from cryptography.fernet import Fernet

from config import settings


_fernet = Fernet(settings.encryption_key)


def encrypt_secret(secret: str) -> str:
    return _fernet.encrypt(secret.encode("utf-8")).decode("utf-8")


def decrypt_secret(encrypted_value: str) -> str:
    return _fernet.decrypt(encrypted_value.encode("utf-8")).decode("utf-8")

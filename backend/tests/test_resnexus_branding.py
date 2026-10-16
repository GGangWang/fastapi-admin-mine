"""Current encryption supports master-key rotation."""
from cryptography.fernet import Fernet

from app.config.setting import settings
from app.utils.crypto_util import CryptoUtil


def test_resnexus_encrypts_and_decrypts_rotated_keys(monkeypatch):
    class FreshCrypto(CryptoUtil):
        _cache_signature = None
        _fernets = []

    monkeypatch.setattr(settings, "SECRET_KEY", "branding-test-signing-secret")
    monkeypatch.setattr(settings, "DATA_ENCRYPTION_KEY", "branding-test-old-master")
    monkeypatch.setattr(settings, "DATA_ENCRYPTION_OLD_KEYS", "")
    new_token = FreshCrypto.encrypt("persisted-storage-password")
    assert Fernet(FreshCrypto._derive_key(settings.DATA_ENCRYPTION_KEY)).decrypt(new_token.encode()) == b"persisted-storage-password"
    monkeypatch.setattr(settings, "DATA_ENCRYPTION_KEY", "branding-test-new-master")
    monkeypatch.setattr(settings, "DATA_ENCRYPTION_OLD_KEYS", "branding-test-old-master")
    assert FreshCrypto.decrypt(new_token) == "persisted-storage-password"

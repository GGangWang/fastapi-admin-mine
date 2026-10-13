"""Brand migration must not invalidate secrets encrypted by prior releases."""
from cryptography.fernet import Fernet

from app.common.legacy_identifiers import LEGACY_KDF_INFO
from app.config.setting import settings
from app.utils.crypto_util import CryptoUtil


def test_resnexus_decrypts_old_hkdf_ciphertext_and_rotated_keys(monkeypatch):
    class FreshCrypto(CryptoUtil):
        _cache_signature = None
        _fernets = []

    monkeypatch.setattr(settings, "SECRET_KEY", "branding-test-signing-secret")
    monkeypatch.setattr(settings, "DATA_ENCRYPTION_KEY", "branding-test-old-master")
    monkeypatch.setattr(settings, "DATA_ENCRYPTION_OLD_KEYS", "")
    old_key = FreshCrypto._derive_key(settings.DATA_ENCRYPTION_KEY, LEGACY_KDF_INFO)
    old_token = Fernet(old_key).encrypt(b"persisted-storage-password").decode()
    assert FreshCrypto.decrypt(old_token) == "persisted-storage-password"
    new_token = FreshCrypto.encrypt("persisted-storage-password")
    assert Fernet(FreshCrypto._derive_key(settings.DATA_ENCRYPTION_KEY)).decrypt(new_token.encode()) == b"persisted-storage-password"
    monkeypatch.setattr(settings, "DATA_ENCRYPTION_KEY", "branding-test-new-master")
    monkeypatch.setattr(settings, "DATA_ENCRYPTION_OLD_KEYS", "branding-test-old-master")
    assert FreshCrypto.decrypt(old_token) == "persisted-storage-password"
    assert FreshCrypto.decrypt(new_token) == "persisted-storage-password"

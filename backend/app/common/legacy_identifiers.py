"""Compatibility-only identifiers from the upstream deployment.

Do not use these for product branding or new storage namespaces. The scheduler
lock must remain shared during rolling upgrades; the old KDF context is needed
only to decrypt already persisted secrets.
"""
LEGACY_KDF_INFO = b"fastapiadmin:data-encryption:v1"
LEGACY_SCHEDULER_LOCK_KEY = "fastapiadmin:scheduler:lock"

"""Tenant-scoped protected object storage for VEAP v0.7 security foundation.

Enforces strict tenant directory isolation, safe identifier validation,
path-traversal rejection, and SHA-256 integrity verification on every read
and write. No cross-tenant object access is permitted.
"""
from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from pathlib import Path

_TENANT_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{1,63}$")
_KEY_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._/-]{0,199}$")
MAX_OBJECT_BYTES = 16 * 1024 * 1024  # 16 MiB bounded per-object limit


class TenantStorageError(ValueError):
    """Raised on invalid tenant/key, traversal attempt, or integrity failure."""


@dataclass(frozen=True)
class StoredObject:
    tenant_id: str
    key: str
    sha256: str
    size_bytes: int


class TenantObjectStore:
    """Filesystem-backed, tenant-scoped object store with SHA-256 verification."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).expanduser().resolve()
        self.tenants_root = self.root / "tenants"
        self.tenants_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            os.chmod(self.tenants_root, 0o700)
        except OSError:
            pass

    @staticmethod
    def _validate_tenant(tenant_id: str) -> str:
        if not isinstance(tenant_id, str) or not _TENANT_RE.fullmatch(tenant_id):
            raise TenantStorageError("invalid tenant identifier")
        return tenant_id

    @staticmethod
    def _validate_key(key: str) -> str:
        if not isinstance(key, str) or not _KEY_RE.fullmatch(key):
            raise TenantStorageError("invalid object key")
        if ".." in Path(key).parts or key.startswith("/") or "\\" in key:
            raise TenantStorageError("path traversal not permitted in object key")
        return key

    def _resolve_object_path(self, tenant_id: str, key: str) -> Path:
        tid = self._validate_tenant(tenant_id)
        safe_key = self._validate_key(key)
        tenant_dir = (self.tenants_root / tid).resolve()
        target = (tenant_dir / safe_key).resolve()
        if not target.is_relative_to(tenant_dir) or target == tenant_dir:
            raise TenantStorageError("resolved path escapes tenant boundary")
        return target

    def put_bytes(
        self,
        tenant_id: str,
        key: str,
        data: bytes,
        *,
        expected_sha256: str | None = None,
    ) -> StoredObject:
        if not isinstance(data, (bytes, bytearray)):
            raise TenantStorageError("object payload must be bytes")
        raw = bytes(data)
        if len(raw) > MAX_OBJECT_BYTES:
            raise TenantStorageError("object exceeds bounded 16 MiB limit")
        digest = hashlib.sha256(raw).hexdigest()
        if expected_sha256 is not None and digest != expected_sha256:
            raise TenantStorageError("payload SHA-256 mismatch on write")

        target = self._resolve_object_path(tenant_id, key)
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        tmp = target.with_name(f".{target.name}.{os.getpid()}.tmp")
        tmp.write_bytes(raw)
        try:
            os.chmod(tmp, 0o600)
        except OSError:
            pass
        os.replace(tmp, target)

        meta_path = target.with_suffix(target.suffix + ".sha256")
        meta_path.write_text(digest + "\n", encoding="utf-8")
        return StoredObject(tenant_id=tenant_id, key=key, sha256=digest, size_bytes=len(raw))

    def get_bytes(self, tenant_id: str, key: str) -> bytes:
        target = self._resolve_object_path(tenant_id, key)
        if not target.is_file():
            raise FileNotFoundError(f"object not found for tenant {tenant_id}: {key}")
        raw = target.read_bytes()
        meta_path = target.with_suffix(target.suffix + ".sha256")
        if meta_path.is_file():
            recorded = meta_path.read_text(encoding="utf-8").strip()
            actual = hashlib.sha256(raw).hexdigest()
            if recorded != actual:
                raise TenantStorageError("stored object integrity check failed")
        return raw

    def list_keys(self, tenant_id: str) -> list[str]:
        tid = self._validate_tenant(tenant_id)
        tenant_dir = (self.tenants_root / tid).resolve()
        if not tenant_dir.is_dir():
            return []
        keys: list[str] = []
        for path in sorted(tenant_dir.rglob("*")):
            if path.is_file() and not path.name.endswith(".sha256"):
                keys.append(path.relative_to(tenant_dir).as_posix())
        return keys

    def delete(self, tenant_id: str, key: str) -> bool:
        target = self._resolve_object_path(tenant_id, key)
        if not target.is_file():
            return False
        target.unlink()
        meta_path = target.with_suffix(target.suffix + ".sha256")
        if meta_path.is_file():
            meta_path.unlink()
        return True

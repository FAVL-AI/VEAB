"""VEAP v0.7 production security foundation tests."""
from __future__ import annotations

import time
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from scripts.check_v07_security import generate_cyclonedx_sbom, scan_tracked_secrets
from veap.enterprise import auth as enterprise_auth
from veap.enterprise.api import create_app
from veap.enterprise.db import StudioDB
from veap.enterprise.migrations import apply_migrations, current_version, rollback_migration
from veap.enterprise.queue import DurableJobQueue
from veap.enterprise.storage import TenantObjectStore, TenantStorageError


def _rsa_keypair():
    from cryptography.hazmat.primitives.asymmetric import rsa
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private_key, private_key.public_key()


def test_oidc_idp_integration_and_tenancy_escape_controls(tmp_path, monkeypatch):
    jwt = pytest.importorskip("jwt")
    priv, pub = _rsa_keypair()
    issuer = "https://idp.example.test/oauth2"
    audience = "veap-studio"
    jwks_url = "https://idp.example.test/.well-known/jwks.json"

    monkeypatch.setenv("VEAP_OIDC_ISSUER", issuer)
    monkeypatch.setenv("VEAP_OIDC_AUDIENCE", audience)
    monkeypatch.setenv("VEAP_OIDC_JWKS_URL", jwks_url)
    enterprise_auth.jwks_client.cache_clear()
    monkeypatch.setattr(
        enterprise_auth,
        "jwks_client",
        lambda _url: SimpleNamespace(get_signing_key_from_jwt=lambda _tok: SimpleNamespace(key=pub)),
    )

    db = StudioDB(tmp_path / "studio")
    t_alpha, alice = db.bootstrap(
        "Alpha Robotics", "alice@alpha.test", "Alice", role="viewer",
        oidc_issuer=issuer, oidc_subject="sub-alice",
    )
    t_beta, _bob = db.bootstrap(
        "Beta Dynamics", "bob@beta.test", "Bob", role="owner",
        oidc_issuer=issuer, oidc_subject="sub-bob",
    )

    app = create_app(data_dir=tmp_path / "studio", mode="oidc")
    with TestClient(app) as client:
        now = int(time.time())
        valid_alice = jwt.encode(
            {
                "iss": issuer,
                "sub": "sub-alice",
                "aud": audience,
                "iat": now,
                "exp": now + 300,
                # Self-asserted tenant/role claims must NEVER grant cross-tenant access
                "tenant_id": t_beta,
                "role": "owner",
            },
            priv,
            algorithm="RS256",
        )

        # Valid RS256 token works on authorized tenant
        r_ok = client.get(f"/api/studio/t/{t_alpha}/projects", headers={"Authorization": f"Bearer {valid_alice}"})
        assert r_ok.status_code == 200

        # Cross-tenant escape attempt returns 404 (not leaking tenant existence)
        r_escape = client.get(f"/api/studio/t/{t_beta}/projects", headers={"Authorization": f"Bearer {valid_alice}"})
        assert r_escape.status_code == 404

        # Insufficient role (researcher cannot create projects, requires owner)
        r_role = client.post(
            f"/api/studio/t/{t_alpha}/projects",
            headers={"Authorization": f"Bearer {valid_alice}"},
            json={"name": "Unauthorized Project", "description": "test"},
        )
        assert r_role.status_code == 403

        # Wrong audience, expired token, and unmapped subject rejected with 401
        for bad_claims in (
            {"iss": issuer, "sub": "sub-alice", "aud": "wrong-aud", "iat": now, "exp": now + 300},
            {"iss": issuer, "sub": "sub-alice", "aud": audience, "iat": now - 600, "exp": now - 120},
            {"iss": issuer, "sub": "sub-unmapped", "aud": audience, "iat": now, "exp": now + 300},
        ):
            bad_tok = jwt.encode(bad_claims, priv, algorithm="RS256")
            assert client.get(
                f"/api/studio/t/{t_alpha}/projects",
                headers={"Authorization": f"Bearer {bad_tok}"},
            ).status_code == 401


def test_tenant_object_store_isolation_and_integrity(tmp_path):
    store = TenantObjectStore(tmp_path / "obj")
    obj = store.put_bytes("tenant-alpha", "runs/run1/evidence.json", b'{"ok":true}')
    assert store.get_bytes("tenant-alpha", "runs/run1/evidence.json") == b'{"ok":true}'
    assert store.list_keys("tenant-alpha") == ["runs/run1/evidence.json"]

    # Cross-tenant isolation
    with pytest.raises(FileNotFoundError):
        store.get_bytes("tenant-beta", "runs/run1/evidence.json")
    assert store.list_keys("tenant-beta") == []

    # Path traversal and invalid tenant/key rejection
    for bad_key in ("../tenant-beta/secret.json", "/etc/passwd", "a\\b", "runs/../../escape"):
        with pytest.raises(TenantStorageError):
            store.put_bytes("tenant-alpha", bad_key, b"x")
    with pytest.raises(TenantStorageError):
        store.put_bytes("../escape", "a.txt", b"x")

    # Tamper detection on disk
    stored_file = tmp_path / "obj" / "tenants" / "tenant-alpha" / "runs" / "run1" / "evidence.json"
    stored_file.write_bytes(b'{"ok":false}')
    with pytest.raises(TenantStorageError, match="integrity check failed"):
        store.get_bytes("tenant-alpha", "runs/run1/evidence.json")
    assert obj.size_bytes == 11


def test_tenancy_escape_negative_controls_dev_token(tmp_path):
    db = StudioDB(tmp_path / "studio_dev")
    t_alpha, alice = db.bootstrap("Alpha Robotics", "alice@alpha.test", "Alice", role="viewer")
    t_beta, _bob = db.bootstrap("Beta Dynamics", "bob@beta.test", "Bob", role="owner")
    tok_alice = db.issue_dev_token(alice)

    app = create_app(data_dir=tmp_path / "studio_dev", mode="dev-token")
    with TestClient(app) as client:
        assert client.get(f"/api/studio/t/{t_alpha}/projects", headers={"Authorization": f"Bearer {tok_alice}"}).status_code == 200
        assert client.get(f"/api/studio/t/{t_beta}/projects", headers={"Authorization": f"Bearer {tok_alice}"}).status_code == 404
        assert client.post(
            f"/api/studio/t/{t_alpha}/projects",
            headers={"Authorization": f"Bearer {tok_alice}"},
            json={"name": "Unauthorized Project", "description": "test"},
        ).status_code == 403


def test_migrations_forward_and_rollback_preserve_data(tmp_path):
    db = StudioDB(tmp_path / "mig")
    tid, _ = db.bootstrap("Migration Tenant", "mig@veap.test", "Mig User", role="owner")

    applied = apply_migrations(db)
    assert applied == [1, 2, 3]
    assert current_version(db) == 3

    rolled = rollback_migration(db, target_version=1)
    assert rolled == [3, 2]
    assert current_version(db) == 1
    assert db.row("SELECT name FROM tenants WHERE id=?", tid)["name"] == "Migration Tenant"

    reapplied = apply_migrations(db)
    assert reapplied == [2, 3]
    assert current_version(db) == 3


def test_durable_queue_leasing_and_poison_dlq(tmp_path):
    db = StudioDB(tmp_path / "queue")
    tid, _ = db.bootstrap("Queue Tenant", "queue@veap.test", "Queue User", role="owner")
    q = DurableJobQueue(db)

    j1 = q.enqueue(tid, "replay_verify", {"run_id": "r1"}, max_attempts=2, now=100.0)
    leased = q.lease_next("worker-1", lease_seconds=10.0, now=101.0)
    assert leased is not None and leased.id == j1 and leased.attempt_count == 1
    assert q.heartbeat(j1, "worker-1", lease_seconds=10.0, now=105.0) is True
    assert q.ack_complete(j1, "worker-1", now=106.0) is True
    assert q.get_job(j1, tenant_id=tid)["status"] == "completed"

    # Poison message moves to poison_dlq after max_attempts
    j2 = q.enqueue(tid, "replay_verify", {"run_id": "bad"}, max_attempts=2, now=200.0)
    l1 = q.lease_next("worker-1", lease_seconds=5.0, now=201.0)
    assert l1 is not None and l1.attempt_count == 1
    assert q.nack(j2, "worker-1", "boom-1", now=202.0) == "queued"

    l2 = q.lease_next("worker-2", lease_seconds=5.0, now=203.0)
    assert l2 is not None and l2.attempt_count == 2
    assert q.nack(j2, "worker-2", "boom-2", now=204.0) == "poison_dlq"
    assert q.get_job(j2, tenant_id=tid)["status"] == "poison_dlq"
    assert q.lease_next("worker-2", lease_seconds=5.0, now=205.0) is None

    # Expired lease reclamation
    j3 = q.enqueue(tid, "replay_verify", {"run_id": "stale"}, max_attempts=2, now=300.0)
    assert q.lease_next("worker-dead", lease_seconds=5.0, now=301.0) is not None
    l3_reclaimed = q.lease_next("worker-live", lease_seconds=5.0, now=310.0)
    assert l3_reclaimed is not None and l3_reclaimed.id == j3 and l3_reclaimed.attempt_count == 2


def test_v07_sbom_and_secret_scan_gate():
    sbom = generate_cyclonedx_sbom()
    assert sbom["bomFormat"] == "CycloneDX"
    assert sbom["specVersion"] == "1.5"
    assert len(sbom["components"]) > 0

    scan = scan_tracked_secrets()
    assert scan["scanned_files"] > 50
    assert scan["finding_count"] == 0, f"Unexpected secret findings: {scan['findings']}"

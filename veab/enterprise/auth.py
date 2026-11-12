"""Identity is independent of tenant choice; membership is always server-side.

Two mutually exclusive modes:
- dev-token: high-entropy hashed personal tokens for loopback-only pilots.
- oidc: verified RS256 access tokens from a configured issuer, with local identity bindings.
No user can self-assert their role or tenant through a request or JWT claim.
"""
from __future__ import annotations
import os
from dataclasses import dataclass
from functools import lru_cache
from fastapi import HTTPException, Request
from .db import StudioDB


@dataclass(frozen=True)
class Identity:
    id: str
    email: str
    name: str


def check_deployment_config(mode: str, *, docs_only: bool = False) -> None:
    if mode not in ('dev-token', 'oidc'):
        raise RuntimeError('VEAB_STUDIO_AUTH_MODE must be dev-token or oidc')
    if mode == 'oidc':
        missing=[k for k in ('VEAB_OIDC_ISSUER','VEAB_OIDC_AUDIENCE','VEAB_OIDC_JWKS_URL') if not os.getenv(k)]
        if missing:
            raise RuntimeError('OIDC mode requires '+', '.join(missing))
        try:
            import jwt  # noqa
        except ImportError as exc:
            raise RuntimeError('Install the [enterprise] dependencies for OIDC validation') from exc
    if mode == 'dev-token' and os.getenv('VEAB_STUDIO_ALLOW_REMOTE') == '1':
        raise RuntimeError('Developer tokens must not be exposed to remote networks')


@lru_cache(maxsize=4)
def jwks_client(url: str):
    import jwt
    if not url.startswith('https://'):
        raise RuntimeError('OIDC JWKS_URL must use HTTPS')
    return jwt.PyJWKClient(url, cache_keys=True, lifespan=300)


def authenticate(request: Request) -> Identity:
    db: StudioDB = request.app.state.studio_db
    mode: str = request.app.state.auth_mode
    header=request.headers.get('Authorization','')
    if not header.startswith('Bearer ') or len(header) > 10000:
        raise HTTPException(401,'Bearer token required',headers={'WWW-Authenticate':'Bearer'})
    token=header[7:]
    result=None
    if mode=='dev-token':
        result=db.principal_for_dev_token(token)
    else:
        try:
            import jwt
            issuer=os.environ['VEAB_OIDC_ISSUER']
            key=jwks_client(os.environ['VEAB_OIDC_JWKS_URL']).get_signing_key_from_jwt(token).key
            claims=jwt.decode(token,key,algorithms=['RS256'],issuer=issuer,
                              audience=os.environ['VEAB_OIDC_AUDIENCE'],leeway=30,
                              options={'require':['iss','sub','aud','exp','iat']})
            result=db.principal_for_oidc(claims['iss'],claims['sub'])
        except Exception:
            result=None
    if result is None:
        raise HTTPException(401,'Invalid, expired, or unmapped token',headers={'WWW-Authenticate':'Bearer'})
    return Identity(result['id'],result['email'],result['name'])


def authorize(db: StudioDB, tenant_id: str, principal_id: str, allowed: set[str]) -> str:
    role=db.member_role(tenant_id,principal_id)
    if role is None:
        # Avoid indicating whether the tenant even exists.
        raise HTTPException(404,'Tenant not found')
    if role not in allowed:
        raise HTTPException(403,'Permission denied for this role')
    return role

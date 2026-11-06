from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Callable

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class Principal:
    subject: str
    tenant_id: str
    username: str
    display_name: str
    roles: frozenset[str]

    @property
    def audit_actor(self) -> str:
        return f"{self.username} [oid:{self.subject}]"


@lru_cache(maxsize=8)
def _jwks_client(tenant_id: str) -> PyJWKClient:
    return PyJWKClient(
        f"https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys",
        cache_keys=True,
        lifespan=3600,
    )


def get_current_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> Principal:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A valid Entra ID bearer token is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    tenant_id = os.getenv("HELPDESK_ENTRA_TENANT_ID", "").strip()
    api_client_id = os.getenv("HELPDESK_ENTRA_API_CLIENT_ID", "").strip()
    if not tenant_id or not api_client_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Entra ID authentication is not configured for this environment.",
        )

    token = credentials.credentials
    try:
        header = jwt.get_unverified_header(token)
        if header.get("alg") != "RS256" or not header.get("kid"):
            raise HTTPException(status_code=401, detail="Unsupported token signing method.")
        signing_key = _jwks_client(tenant_id).get_signing_key_from_jwt(token).key
        claims = jwt.decode(
            token,
            signing_key,
            algorithms=["RS256"],
            audience=api_client_id,
            issuer=f"https://login.microsoftonline.com/{tenant_id}/v2.0",
            leeway=60,
            options={"require": ["exp", "iss", "aud", "tid", "oid"]},
        )
    except jwt.PyJWKClientConnectionError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to reach Entra ID signing keys.",
        ) from exc
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="The bearer token is invalid or expired.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    if claims.get("tid") != tenant_id:
        raise HTTPException(status_code=401, detail="Token tenant does not match this API.")
    subject = claims.get("oid")
    if not isinstance(subject, str) or not subject.strip():
        raise HTTPException(status_code=401, detail="Token is missing a valid user object ID.")

    raw_roles = claims.get("roles", [])
    if not isinstance(raw_roles, list) or any(not isinstance(role, str) for role in raw_roles):
        raise HTTPException(status_code=403, detail="Token contains an invalid roles claim.")

    username = claims.get("preferred_username") or claims.get("upn") or subject
    display_name = claims.get("name") or username
    return Principal(
        subject=subject,
        tenant_id=tenant_id,
        username=str(username),
        display_name=str(display_name),
        roles=frozenset(raw_roles),
    )


def require_roles(*allowed_roles: str) -> Callable:
    def dependency(principal: Principal = Depends(get_current_principal)) -> Principal:
        if not principal.roles.intersection(allowed_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your Entra ID application role does not permit this operation.",
            )
        return principal

    return dependency

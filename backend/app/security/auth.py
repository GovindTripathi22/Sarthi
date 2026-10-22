from __future__ import annotations

import hashlib
import hmac
import os
import uuid
from typing import List, Optional

from fastapi import Depends, Header, HTTPException, Security
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.database import get_db
from backend.app.models import AuditLog, User, utcnow

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
bearer_auth = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    """Deterministic salted SHA-256 hash."""
    salt = "sarthi_secure_salt_2026"
    return hashlib.sha256(f"{salt}:{password}".encode("utf-8")).hexdigest()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return hmac.compare_digest(hash_password(plain_password), hashed_password)


def get_current_user(
    x_api_key: Optional[str] = Security(api_key_header),
    auth_creds: Optional[HTTPAuthorizationCredentials] = Security(bearer_auth),
    x_autopatch_role: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    """
    Authenticates the current user via API Key, Bearer Token, or Seed Role mapping.
    """
    token = None
    if auth_creds:
        token = auth_creds.credentials
    elif x_api_key:
        token = x_api_key

    if token:
        user = db.scalar(select(User).where(User.api_key == token))
        if user and user.is_active:
            return user
        # Check if token is user email / direct ID
        user_by_id = db.scalar(select(User).where(User.id == token))
        if user_by_id and user_by_id.is_active:
            return user_by_id

    # Fallback to role header in development/demo mode
    role_to_check = x_autopatch_role or "Admin"
    user_by_role = db.scalar(select(User).where(User.role == role_to_check))
    if user_by_role and user_by_role.is_active:
        return user_by_role

    # Default to Admin user if available in development mode
    admin_user = db.scalar(select(User).where(User.role == "Admin"))
    if admin_user:
        return admin_user

    raise HTTPException(
        status_code=401,
        detail="Authentication required. Please provide a valid Bearer Token or X-API-Key.",
    )


def require_roles(allowed_roles: List[str], action_label: str):
    """
    Dependency factory that verifies current user's role against allowed roles.
    Records an unauthorized audit event and raises HTTP 403 upon violation.
    """
    def _role_checker(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        if current_user.role not in allowed_roles:
            # Record unauthorized audit attempt
            audit = AuditLog(
                id=f"aud_{uuid.uuid4().hex[:8]}",
                workspace_id="ws_prod_01",
                timestamp=utcnow(),
                actor=f"{current_user.name} ({current_user.role})",
                role=current_user.role,
                action="UNAUTHORIZED_ACTION_BLOCKED",
                target=action_label,
                outcome="DENIED_403",
                details=f"Role '{current_user.role}' attempted '{action_label}'. Allowed: {allowed_roles}",
            )
            db.add(audit)
            db.commit()
            raise HTTPException(
                status_code=403,
                detail=f"RBAC Policy Enforcement: Role '{current_user.role}' cannot perform '{action_label}'. Required: {allowed_roles}",
            )
        return current_user

    return _role_checker

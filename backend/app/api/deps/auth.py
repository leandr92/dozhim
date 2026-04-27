from fastapi import Header, HTTPException, status


def require_bearer_token(authorization: str | None = Header(default=None, alias="Authorization")) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer token is required",
        )
    return authorization.removeprefix("Bearer ").strip()


def get_current_role(x_role: str | None = Header(default=None, alias="X-Role")) -> str:
    role = (x_role or "operator").strip().lower()
    if role not in {"operator", "admin", "viewer"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "FORBIDDEN_ROLE",
                "message": "Недопустимая роль",
                "details": {"role": role},
                "retryable": False,
                "severity": "warning",
            },
        )
    return role


def require_roles(*allowed_roles: str):
    allowed = {r.strip().lower() for r in allowed_roles}

    def _check(role: str = Header(default=None, alias="X-Role")) -> str:
        current = get_current_role(role)
        if current not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "FORBIDDEN",
                    "message": "Недостаточно прав для выполнения операции",
                    "details": {"role": current, "allowed_roles": sorted(list(allowed))},
                    "retryable": False,
                    "severity": "warning",
                },
            )
        return current

    return _check

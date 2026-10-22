from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse
from fastapi import HTTPException

from backend.app.config import settings

# Sensitive cloud metadata endpoints
METADATA_IPS = {"169.254.169.254", "fd00:ec2::254"}


def validate_upstream_url(url: str, allow_local_override: bool | None = None) -> None:
    """
    Validate that an upstream URL is safe from SSRF attacks.
    Blocks private networks, cloud metadata services, invalid protocols, and path escapes.
    """
    if not url:
        raise HTTPException(status_code=400, detail="Upstream base URL cannot be empty.")

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid protocol scheme '{parsed.scheme}'. Only http:// and https:// are permitted.",
        )

    hostname = parsed.hostname
    if not hostname:
        raise HTTPException(status_code=400, detail="Invalid host specified in upstream URL.")

    # Check path traversal
    if ".." in parsed.path:
        raise HTTPException(status_code=400, detail="Path traversal ('..') detected in upstream URL.")

    allow_local = allow_local_override if allow_local_override is not None else settings.allow_local_proxy
    if allow_local and hostname in ("localhost", "127.0.0.1", "::1", "testserver"):
        return

    # Check if host is an explicit IP address or resolve DNS
    try:
        addr_info = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        if allow_local:
            # In local/test mode, permit mock and development hostnames
            return
        raise HTTPException(
            status_code=502,
            detail=f"Unable to resolve upstream hostname '{hostname}': {exc}",
        )

    for item in addr_info:
        ip_str = item[4][0]
        if ip_str in METADATA_IPS:
            raise HTTPException(
                status_code=403,
                detail="Access to Cloud Metadata Service (169.254.169.254) is strictly prohibited.",
            )
        try:
            ip_obj = ipaddress.ip_address(ip_str)
            if not allow_local:
                if (
                    ip_obj.is_private
                    or ip_obj.is_loopback
                    or ip_obj.is_link_local
                    or ip_obj.is_multicast
                    or ip_obj.is_reserved
                ):
                    raise HTTPException(
                        status_code=403,
                        detail=f"SSRF Protection: Access to private/loopback/link-local address '{ip_str}' is forbidden in production mode.",
                    )
        except ValueError:
            continue

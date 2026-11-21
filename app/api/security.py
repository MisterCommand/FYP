import base64
import binascii
import hmac
import ipaddress
import os

from fastapi import Request
from fastapi.responses import JSONResponse


def is_loopback(host):
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def policy():
    token = os.environ.get("EVENTLENS_API_TOKEN", "")
    if token and not token.strip():
        raise ValueError("EVENTLENS_API_TOKEN must not be whitespace")
    return token, os.environ.get("EVENTLENS_ALLOW_UNAUTHENTICATED") == "1"


def check_bindings():
    token, allow = policy()
    for variable in ("API_HOST", "WEB_HOST"):
        host = os.environ.get(variable) or "127.0.0.1"
        if not is_loopback(host) and not (token or allow):
            raise ValueError(f"{variable} is non-loopback: set EVENTLENS_API_TOKEN or explicitly "
                             "opt out with EVENTLENS_ALLOW_UNAUTHENTICATED=1")


def supplied_token(authorization):
    scheme, _, value = authorization.partition(" ")
    if scheme.lower() == "bearer":
        return value
    if scheme.lower() == "basic":
        try:
            username, _, password = base64.b64decode(value, validate=True).decode("utf-8").partition(":")
            return password if username == "eventlens" else ""
        except (ValueError, binascii.Error, UnicodeDecodeError):
            return ""
    return ""


async def protect_api(request: Request, call_next):
    token, allow = policy()
    if token:
        supplied = supplied_token(request.headers.get("authorization", ""))
        if not hmac.compare_digest(supplied.encode(), token.encode()):
            return JSONResponse({"detail": "API authentication required"}, status_code=401,
                headers={"WWW-Authenticate": 'Basic realm="EventLens", charset="UTF-8"',
                         "Cache-Control": "no-store"})
    elif not allow and (request.client is None or not is_loopback(request.client.host)
                        or not is_loopback(request.url.hostname or "")):
        return JSONResponse({"detail": "Remote API access requires EVENTLENS_API_TOKEN or an explicit opt-out"},
                            status_code=403, headers={"Cache-Control": "no-store"})
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    return response


if __name__ == "__main__":
    try:
        check_bindings()
    except ValueError as error:
        raise SystemExit(str(error))

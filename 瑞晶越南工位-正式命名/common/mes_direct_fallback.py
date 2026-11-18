# -*- coding: utf-8 -*-
"""Shared MES transport failover for every station entry point.

Order of service selection:
    local deputy (127.0.0.1:8765), then 192.168.6.155:8080,
    then 192.168.6.122:8080.

For a request already aimed at one MES host, only the other MES host is
tried after a connection failure. HTTP application errors are not retried on
another server because they are responses, not connectivity failures.
"""
from __future__ import annotations

import os
import urllib.error
import urllib.request
from urllib.parse import urlsplit, urlunsplit


PRIMARY = os.environ.get("MES_PRIMARY_URL", "http://192.168.6.155:8080").rstrip("/")
BACKUP = os.environ.get("MES_BACKUP_URL", "http://192.168.6.122:8080").rstrip("/")
_installed = False


def _is_local_deputy(url: str) -> bool:
    parsed = urlsplit(url)
    return (parsed.hostname or "").lower() in {"127.0.0.1", "localhost"} and (parsed.port or 80) == 8765


def _mes_base(url: str):
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower()
    port = parsed.port or 80
    if port != 8080:
        return None
    if host == "192.168.6.155":
        return PRIMARY
    if host == "192.168.6.122":
        return BACKUP
    return None


def _direct_url(url: str, base: str) -> str:
    parsed = urlsplit(url)
    target = urlsplit(base)
    return urlunsplit((target.scheme, target.netloc, parsed.path, parsed.query, parsed.fragment))


def _clone_request(request, url: str):
    if not isinstance(request, urllib.request.Request):
        return url
    headers = dict(request.header_items())
    headers["X-Direct-MES-Failover"] = "1"
    return urllib.request.Request(
        url,
        data=request.data,
        headers=headers,
        origin_req_host=request.origin_req_host,
        unverifiable=request.unverifiable,
        method=request.get_method(),
    )


def _connection_failure(exc: BaseException) -> bool:
    # Do not hide a real MES response such as HTTP 400/409/500.
    return isinstance(exc, (urllib.error.URLError, OSError, TimeoutError)) and not isinstance(exc, urllib.error.HTTPError)


def install() -> None:
    global _installed
    if _installed:
        return
    _installed = True
    original = urllib.request.urlopen

    def urlopen(request, *args, **kwargs):
        raw_url = request.full_url if isinstance(request, urllib.request.Request) else str(request)
        local = _is_local_deputy(raw_url)
        current = _mes_base(raw_url)
        if not local and current is None:
            return original(request, *args, **kwargs)

        if local:
            candidates = [request, _clone_request(request, _direct_url(raw_url, PRIMARY)),
                          _clone_request(request, _direct_url(raw_url, BACKUP))]
        elif current == PRIMARY:
            candidates = [request, _clone_request(request, _direct_url(raw_url, BACKUP))]
        else:
            candidates = [request, _clone_request(request, _direct_url(raw_url, PRIMARY))]

        last = None
        for candidate in candidates:
            try:
                return original(candidate, *args, **kwargs)
            except Exception as exc:
                if not _connection_failure(exc):
                    raise
                last = exc
        if last is not None:
            raise last
        raise urllib.error.URLError("No MES endpoint configured")

    urllib.request.urlopen = urlopen


__all__ = ["PRIMARY", "BACKUP", "install"]

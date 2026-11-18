# -*- coding: utf-8 -*-
"""Shared MES transport failover bundled into every station executable."""
from __future__ import annotations

import os
import urllib.error
import urllib.request
from urllib.parse import urlsplit, urlunsplit

PRIMARY = os.environ.get("MES_PRIMARY_URL", "http://192.168.6.155:8080").rstrip("/")
BACKUP = os.environ.get("MES_BACKUP_URL", "http://192.168.6.122:8080").rstrip("/")
_installed = False


def _local(url):
    p = urlsplit(url)
    return (p.hostname or "").lower() in {"127.0.0.1", "localhost"} and (p.port or 80) == 8765


def _mes_base(url):
    p = urlsplit(url)
    host, port = (p.hostname or "").lower(), p.port or 80
    if port != 8080:
        return None
    if host == "192.168.6.155":
        return PRIMARY
    if host == "192.168.6.122":
        return BACKUP
    return None


def _direct(url, base):
    p, b = urlsplit(url), urlsplit(base)
    return urlunsplit((b.scheme, b.netloc, p.path, p.query, p.fragment))


def _clone(request, url):
    if not isinstance(request, urllib.request.Request):
        return url
    headers = dict(request.header_items())
    headers["X-Direct-MES-Failover"] = "1"
    return urllib.request.Request(
        url, data=request.data, headers=headers,
        origin_req_host=request.origin_req_host,
        unverifiable=request.unverifiable, method=request.get_method(),
    )


def _retryable(exc):
    return (isinstance(exc, (urllib.error.URLError, OSError, TimeoutError))
            and not isinstance(exc, urllib.error.HTTPError))


def install():
    global _installed
    if _installed:
        return
    _installed = True
    original = urllib.request.urlopen

    def urlopen(request, *args, **kwargs):
        raw = request.full_url if isinstance(request, urllib.request.Request) else str(request)
        current = _mes_base(raw)
        if not _local(raw) and current is None:
            return original(request, *args, **kwargs)
        if _local(raw):
            candidates = [request, _clone(request, _direct(raw, PRIMARY)), _clone(request, _direct(raw, BACKUP))]
        elif current == PRIMARY:
            candidates = [request, _clone(request, _direct(raw, BACKUP))]
        else:
            candidates = [request, _clone(request, _direct(raw, PRIMARY))]
        last = None
        for candidate in candidates:
            try:
                return original(candidate, *args, **kwargs)
            except Exception as exc:
                if not _retryable(exc):
                    raise
                last = exc
        raise last

    urllib.request.urlopen = urlopen


__all__ = ["PRIMARY", "BACKUP", "install"]

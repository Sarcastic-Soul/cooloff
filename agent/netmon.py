"""Counts the bytes this process really sends over the network to AWS, by patching botocore's HTTP send.

It is a measurement of our own process (not a drawing): every request body that leaves through boto3 or Strands is
counted. Each request is tagged with the current purpose ("agent" for the parent's own instruction, "voice" for the
Bedrock texts written after red). Calls to localhost (the Decider server) are not counted as outside traffic.
"""
from __future__ import annotations

import contextlib
import contextvars
import threading
import time
from urllib.parse import urlparse

import botocore.httpsession

_tag: contextvars.ContextVar[str] = contextvars.ContextVar("net_tag", default="other")
_lock = threading.Lock()
records: list[dict] = []
_installed = False


@contextlib.contextmanager
def tag(name: str):
    token = _tag.set(name)
    try:
        yield
    finally:
        _tag.reset(token)


def install() -> None:
    global _installed
    if _installed:
        return
    original = botocore.httpsession.URLLib3Session.send

    def send(self, request):
        host = urlparse(request.url).hostname or ""
        body = request.body
        size = len(body) if isinstance(body, (bytes, str)) else 0
        size += sum(len(k) + len(str(v)) for k, v in request.headers.items())
        if host not in ("127.0.0.1", "localhost"):
            with _lock:
                records.append({"t": time.time(), "host": host, "bytes_out": size, "tag": _tag.get()})
        return original(self, request)

    botocore.httpsession.URLLib3Session.send = send
    _installed = True


def total(tag_name: str | None = None) -> int:
    with _lock:
        return sum(r["bytes_out"] for r in records if tag_name is None or r["tag"] == tag_name)


def reset() -> None:
    with _lock:
        records.clear()

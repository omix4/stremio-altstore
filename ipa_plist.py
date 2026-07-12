#!/usr/bin/env python3
"""
ipa_plist.py — shared HTTP-Range IPA Info.plist extractor

Used by both stremio-updater.py and scripts/verify_bundle_ids.py so the
zip/plist parsing logic exists in exactly one place.
"""

from __future__ import annotations

import plistlib
import struct
import urllib.error
import urllib.request
import zlib
from typing import NamedTuple, Optional

USER_AGENT = "stremio-altstore/ipa_plist/1.0"


class HttpResp(NamedTuple):
    status: Optional[int]
    headers: dict
    body: Optional[bytes]


def http_request(url: str, *, method: str = "GET", headers: Optional[dict] = None,
                 timeout: int = 15) -> HttpResp:
    h = {"User-Agent": USER_AGENT}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return HttpResp(r.status, dict(r.headers), r.read())
    except urllib.error.HTTPError as e:
        return HttpResp(e.code, dict(e.headers or {}), None)
    except Exception:
        return HttpResp(None, {}, None)


def _u16(b: bytes, o: int) -> int:
    return struct.unpack_from("<H", b, o)[0]


def _u32(b: bytes, o: int) -> int:
    return struct.unpack_from("<I", b, o)[0]


def get_main_app_info_plist(ipa_url: str) -> dict:
    """
    Parses the main app's Info.plist from an IPA URL.
    Only the main app's Info.plist is read (framework and appex entries are excluded).
    Method: only the ZIP End-of-Central-Directory and Central Directory sections are
    fetched via HTTP Range; the relevant payload is then downloaded.
    Typical download: < 100 KB.

    Returns: {"ok": True, "plist": {...}, "name": "Payload/..."}
         or {"ok": False, "error": "..."}
    """
    head = http_request(ipa_url, method="HEAD")
    if head.status != 200:
        return {"ok": False, "error": f"HEAD {head.status}"}
    total = int(head.headers.get("Content-Length") or 0)
    if total <= 0:
        return {"ok": False, "error": "no Content-Length"}

    # 1) Find the EOCD record at the end of the ZIP
    tail_size = 64 * 1024 + 22
    start = max(0, total - tail_size)
    tail = http_request(ipa_url, headers={"Range": f"bytes={start}-{total - 1}"})
    if tail.status not in (200, 206) or not tail.body:
        return {"ok": False, "error": "EOCD fetch"}
    eocd_off = tail.body.rfind(b"PK\x05\x06")
    if eocd_off < 0:
        return {"ok": False, "error": "EOCD signature not found"}
    cd_offset = _u32(tail.body, eocd_off + 16)

    # 2) Read the central directory (max 1 MB)
    cd_limit = min(total - cd_offset, 1024 * 1024)
    cd = http_request(ipa_url, headers={"Range": f"bytes={cd_offset}-{cd_offset + cd_limit - 1}"})
    if cd.status not in (200, 206) or not cd.body:
        return {"ok": False, "error": "CD fetch"}

    # 3) Collect all ".app/Info.plist" entries, pick the main app
    entries: list[tuple[str, int, int, int]] = []
    pos = 0
    while pos < len(cd.body) - 46:
        if cd.body[pos:pos + 4] != b"PK\x01\x02":
            pos += 1
            continue
        name_len = _u16(cd.body, pos + 28)
        extra_len = _u16(cd.body, pos + 30)
        comment_len = _u16(cd.body, pos + 32)
        local_off = _u32(cd.body, pos + 42)
        comp_size = _u32(cd.body, pos + 20)
        method = _u16(cd.body, pos + 10)
        name = cd.body[pos + 46:pos + 46 + name_len].decode("utf-8", errors="ignore")
        if name.endswith("/Info.plist"):
            entries.append((name, local_off, comp_size, method))
        pos += 46 + name_len + extra_len + comment_len

    if not entries:
        return {"ok": False, "error": "no Info.plist entry"}

    apps = [e for e in entries
            if ".app/Info.plist" in e[0]
            and "/Frameworks/" not in e[0]
            and ".appex/" not in e[0]]
    if not apps:
        return {"ok": False, "error": "no .app/Info.plist entry"}
    apps.sort(key=lambda e: len(e[0]))  # shortest path = main app
    name, local_off, comp_size, method = apps[0]

    # 4) Read filename+extra lengths from the local file header
    lfh = http_request(ipa_url, headers={"Range": f"bytes={local_off}-{local_off + 1023}"})
    if lfh.status not in (200, 206) or not lfh.body or lfh.body[:4] != b"PK\x03\x04":
        return {"ok": False, "error": "LFH fetch"}
    fname_len = _u16(lfh.body, 26)
    extra_len = _u16(lfh.body, 28)
    data_start = local_off + 30 + fname_len + extra_len

    # 5) Fetch the compressed payload
    payload = http_request(ipa_url, headers={"Range": f"bytes={data_start}-{data_start + comp_size - 1}"})
    if payload.status not in (200, 206) or not payload.body:
        return {"ok": False, "error": "payload fetch"}

    if method == 8:
        try:
            raw = zlib.decompress(payload.body, -15)
        except zlib.error as e:
            return {"ok": False, "error": f"decompress: {e}"}
    elif method == 0:
        raw = payload.body
    else:
        return {"ok": False, "error": f"unsupported method {method}"}

    # 6) Parse the plist (XML or binary — plistlib supports both)
    try:
        return {"ok": True, "plist": plistlib.loads(raw), "name": name}
    except Exception as e:
        return {"ok": False, "error": f"plist parse: {e}"}

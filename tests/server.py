#!/usr/bin/env python3
"""
Test server for the green-books viewer suite.

Serves a prepared COPY of the repo (built by tests/run.sh, never the live
working tree) as static files, plus a fake IIIF Image API v2 level-0 service
at /iiif/2/9990001/ so a viewer deep link resolves entirely locally — no
network access to NYPL needed. Test images are synthesized on the fly at any
requested size (deterministic checkerboard/gradient with colored corner
markers), so there is no static image fixture.

Usage: server.py SITE_DIR [PORT]

Control endpoints:
  GET /_control/delay?ms=N   delay every subsequent /iiif/2/ response by N ms
                             (simulates a cold/slow NYPL load); ms=0 clears it
  GET /_control/log          dump the request log
"""
import http.server
import os
import re
import socketserver
import struct
import sys
import threading
import time
import zlib
from urllib.parse import urlparse, parse_qs

if len(sys.argv) < 2:
    sys.exit("usage: server.py SITE_DIR [PORT]")
SITE_DIR = os.path.abspath(sys.argv[1])
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 8765

STATE = {"delay_ms": 0}
STATE_LOCK = threading.Lock()

IMAGE_ID = "9990001"
FULL_W, FULL_H = 2000, 3000

_png_cache = {}
_png_cache_lock = threading.Lock()

REQUEST_LOG = []
REQUEST_LOG_LOCK = threading.Lock()


def make_png_bytes(w, h):
    """Synthesize a distinctive RGB PNG of the given size (pure stdlib)."""
    key = (w, h)
    with _png_cache_lock:
        if key in _png_cache:
            return _png_cache[key]

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xffffffff)

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)  # 8-bit RGB
    raw = bytearray()
    for y in range(h):
        raw.append(0)  # filter type 0 (none) for this scanline
        for x in range(w):
            cb = 40 if ((x // 50) + (y // 50)) % 2 == 0 else 200
            r = (cb + (x * 255 // max(w, 1))) % 256
            g = (cb + (y * 255 // max(h, 1))) % 256
            b = 180
            m = max(4, min(w, h) // 10)
            if x < m and y < m:
                r, g, b = 255, 0, 0       # top-left red
            elif x > w - m and y < m:
                r, g, b = 0, 255, 0       # top-right green
            elif x < m and y > h - m:
                r, g, b = 0, 0, 255       # bottom-left blue
            elif x > w - m and y > h - m:
                r, g, b = 255, 255, 0     # bottom-right yellow
            raw += bytes((r, g, b))
    idat = chunk(b"IDAT", zlib.compress(bytes(raw), 4))
    iend = chunk(b"IEND", b"")
    data = sig + chunk(b"IHDR", ihdr) + idat + iend
    with _png_cache_lock:
        _png_cache[key] = data
    return data


def parse_size(size_str, full_w, full_h):
    """Parse an IIIF Image API 'size' path segment into (w, h)."""
    s = size_str
    if s in ("max", "full"):
        return full_w, full_h
    s2 = s[1:] if s.startswith("^") else s
    s2 = s2[1:] if s2.startswith("!") else s2
    m = re.match(r"^(\d+)?,(\d+)?$", s2)
    if m:
        w, h = m.group(1), m.group(2)
        if w and h:
            return int(w), int(h)
        if w:
            wi = int(w)
            return wi, max(1, round(full_h * wi / full_w))
        if h:
            hi = int(h)
            return max(1, round(full_w * hi / full_h)), hi
    m = re.match(r"^pct:([\d.]+)$", s2)
    if m:
        pct = float(m.group(1)) / 100.0
        return max(1, round(full_w * pct)), max(1, round(full_h * pct))
    return full_w, full_h


INFO_JSON_TEMPLATE = """{{
  "@context": "http://iiif.io/api/image/2/context.json",
  "@id": "http://127.0.0.1:{port}/iiif/2/{image_id}",
  "protocol": "http://iiif.io/api/image",
  "width": {w},
  "height": {h},
  "profile": ["http://iiif.io/api/image/2/level0.json"],
  "sizes": [
    {{"width": 250, "height": 375}},
    {{"width": 500, "height": 750}},
    {{"width": 1000, "height": 1500}},
    {{"width": 2000, "height": 3000}}
  ]
}}"""


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=SITE_DIR, **kwargs)

    def log_message(self, fmt, *args):
        line = "%s - %s" % (self.address_string(), fmt % args)
        with REQUEST_LOG_LOCK:
            REQUEST_LOG.append(line)
        sys.stderr.write(line + "\n")

    def _svc_prefix(self):
        return "/iiif/2/%s/" % IMAGE_ID

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/_control/delay":
            qs = parse_qs(parsed.query)
            ms = int(qs.get("ms", ["0"])[0])
            with STATE_LOCK:
                STATE["delay_ms"] = ms
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(("delay set to %d ms\n" % ms).encode())
            return

        if path == "/_control/log":
            with REQUEST_LOG_LOCK:
                body = "\n".join(REQUEST_LOG).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(body)
            return

        if path == "/iiif/2/%s/info.json" % IMAGE_ID:
            self._maybe_delay()
            body = INFO_JSON_TEMPLATE.format(port=PORT, image_id=IMAGE_ID, w=FULL_W, h=FULL_H).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        prefix = self._svc_prefix()
        if path.startswith(prefix):
            self._maybe_delay()
            # Standard IIIF Image API request path: {region}/{size}/{rotation}/{quality}.{format}
            # The fake service is level0 (region should always be "full"), but
            # OpenSeadragon occasionally probes other region/size combos while
            # sizing its initial view — serve *something* sane for any of them
            # rather than 404ing, so the viewer doesn't stall.
            rest = path[len(prefix):]
            parts = rest.split("/")
            size_str = parts[1] if len(parts) > 1 else "max"
            w, h = parse_size(size_str, FULL_W, FULL_H)
            data = make_png_bytes(w, h)
            self.send_response(200)
            # Real bytes are PNG; browsers sniff actual image content, so the
            # declared .jpg extension in the URL doesn't need to match.
            self.send_header("Content-Type", "image/png")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return

        return super().do_GET()

    def _maybe_delay(self):
        with STATE_LOCK:
            ms = STATE["delay_ms"]
        if ms > 0:
            time.sleep(ms / 1000.0)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


class ThreadingServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


if __name__ == "__main__":
    srv = ThreadingServer(("127.0.0.1", PORT), Handler)
    print("Serving on http://127.0.0.1:%d (site dir: %s)" % (PORT, SITE_DIR), flush=True)
    srv.serve_forever()

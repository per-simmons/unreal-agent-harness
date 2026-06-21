#!/usr/bin/env python3
"""Decode a CaptureViewport tool-result .txt (huge base64) into a PNG.
Usage: python3 decode_capture.py <tool-result.txt> <out.png>
Handles either {"returnValue":{"image":{"data":"..."}}} or {"image":{"data":...}} or {"data":...}.
"""
import sys, json, base64, re

src, out = sys.argv[1], sys.argv[2]
raw = open(src).read().strip()
data = None
# Try JSON parse first
try:
    obj = json.loads(raw)
    def find_data(o):
        if isinstance(o, dict):
            if "data" in o and isinstance(o["data"], str) and len(o["data"]) > 1000:
                return o["data"]
            for v in o.values():
                r = find_data(v)
                if r: return r
        return None
    data = find_data(obj)
except Exception:
    pass
if not data:
    # regex fallback for "data":"<base64>"
    m = re.search(r'"data"\s*:\s*"([A-Za-z0-9+/=]{1000,})"', raw)
    if m: data = m.group(1)
if not data:
    print("NO IMAGE DATA FOUND"); sys.exit(1)
png = base64.b64decode(data)
open(out, "wb").write(png)
print(f"wrote {out} ({len(png)} bytes)")

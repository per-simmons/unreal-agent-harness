"""Decode the latest CaptureViewport tool-result .txt to a PNG.
Usage: python3 _decode_capture.py <tool-result.txt> <out.png>
"""
import json, base64, sys
d = json.load(open(sys.argv[1]))
rv = d['returnValue']
open(sys.argv[2], 'wb').write(base64.b64decode(rv['image']['data']))
print('cam', rv['cameraLocation'], rv['cameraRotation'], 'fov', rv.get('cameraFOV'))
print('wrote', sys.argv[2])

"""Exercise the running local stack through Nginx with a generated PNG."""

import json
import sys
import time
import uuid
from io import BytesIO
from urllib.request import Request, urlopen

from PIL import Image


base_url = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080").rstrip("/")
with urlopen(base_url, timeout=10) as response:
    assert b"<html" in response.read().lower(), "Frontend not served by Nginx"

buffer = BytesIO()
with Image.new("RGB", (600, 400), "blue") as image:
    image.save(buffer, format="PNG")
original = buffer.getvalue()
boundary = uuid.uuid4().hex
body = (
    f'--{boundary}\r\nContent-Disposition: form-data; name="file"; '
    'filename="smoke-test.png"\r\nContent-Type: image/png\r\n\r\n'
).encode() + original + f"\r\n--{boundary}--\r\n".encode()
request = Request(
    f"{base_url}/api/images/upload", data=body,
    headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
)
with urlopen(request, timeout=10) as response:
    record = json.load(response)

deadline = time.monotonic() + 45
while time.monotonic() < deadline:
    with urlopen(f"{base_url}/api/images/{record['id']}", timeout=10) as response:
        record = json.load(response)
    if record["status"] == "completed":
        break
    if record["status"] == "failed":
        raise AssertionError(f"Worker failed to process image {record['id']}")
    time.sleep(1)
else:
    raise AssertionError("Image processing did not finish within 45 seconds")

assert (record["width"], record["height"]) == (600, 400)
with urlopen(f"{base_url}/api/images/{record['id']}/file", timeout=10) as response:
    assert response.read() == original, "Original bytes changed"
with urlopen(f"{base_url}/api/images/{record['id']}/thumbnail", timeout=10) as response:
    assert response.headers["Content-Type"] == "image/png"
    with Image.open(BytesIO(response.read())) as thumbnail:
        assert thumbnail.size == (300, 200), thumbnail.size
print(f"PASS: frontend, upload, Redis worker, PostgreSQL, original and thumbnail (image {record['id']})")

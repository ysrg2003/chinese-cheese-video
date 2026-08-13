from __future__ import annotations

import io
import json
import os
import time
from pathlib import Path

import requests
from PIL import Image, ImageDraw

BASE_URL = os.getenv("CHATGPT_VISUAL_API_BASE", "https://yousefsg-chatgpt-api.hf.space").rstrip("/")
API_KEY = os.getenv("CHATGPT_VISUAL_API_KEY", "").strip()
OUT = Path(os.getenv("REFERENCE_EDIT_SMOKE_DIR", "reference-edit-smoke"))
OUT.mkdir(parents=True, exist_ok=True)

if not API_KEY:
    raise SystemExit("CHATGPT_VISUAL_API_KEY is required")

width, height = 768, 1365
reference = Image.new("RGB", (width, height), "#f5e6ca")
draw = ImageDraw.Draw(reference)
draw.rounded_rectangle((55, 250, width - 55, 1130), radius=24, fill="#c9914f", outline="#6e4129", width=8)
for column in range(9):
    x = 95 + column * 72
    draw.line((x, 290, x, 1090), fill="#6e4129", width=3)
for row in range(10):
    y = 290 + row * 88
    draw.line((95, y, width - 95, y), fill="#6e4129", width=3)
draw.rectangle((95, 642, width - 95, 730), fill="#99b6bd", outline="#e1f5f5", width=4)
draw.text((width // 2 - 105, 675), "REFERENCE RIVER", fill="#294c59")
reference_path = OUT / "reference.png"
reference.save(reference_path, format="PNG")

mask = Image.new("RGBA", (width, height), (255, 255, 255, 255))
mask_draw = ImageDraw.Draw(mask)
mask_draw.rectangle((95, 642, width - 95, 730), fill=(0, 0, 0, 0))
mask_path = OUT / "mask.png"
mask.save(mask_path, format="PNG")

headers = {"Authorization": f"Bearer {API_KEY}"}
prompt = (
    "Edit only the transparent masked region; preserve everything outside it exactly. "
    "Add a subtle flat cool-blue flowing-water texture inside the existing rectangular river band. "
    "Do not add text, objects, a new board, a landscape, or any changed geometry."
)
with reference_path.open("rb") as reference_file, mask_path.open("rb") as mask_file:
    created = requests.post(
        f"{BASE_URL}/v1/visual-assets/reference-edits",
        headers=headers,
        files={
            "reference": (reference_path.name, reference_file, "image/png"),
            "mask": (mask_path.name, mask_file, "image/png"),
        },
        data={"prompt": prompt, "preserve_outside_mask": "true"},
        timeout=60,
    )
created.raise_for_status()
job_id = created.json()["job_id"]

deadline = time.monotonic() + 900
status_payload = {}
while time.monotonic() < deadline:
    status_response = requests.get(f"{BASE_URL}/v1/visual-assets/reference-edits/{job_id}", headers=headers, timeout=30)
    status_response.raise_for_status()
    status_payload = status_response.json()
    if status_payload.get("status") == "done":
        break
    if status_payload.get("status") == "error":
        raise SystemExit(json.dumps({"job_id": job_id, "status": status_payload}, ensure_ascii=False))
    time.sleep(5)
else:
    raise TimeoutError(f"reference edit smoke timed out: {job_id}")

downloaded = requests.get(f"{BASE_URL}/v1/visual-assets/reference-edits/{job_id}/download", headers=headers, timeout=120)
downloaded.raise_for_status()
output_path = OUT / "edited.png"
output_path.write_bytes(downloaded.content)
with Image.open(output_path) as edited:
    edited = edited.convert("RGB")
    with Image.open(reference_path) as original:
        original = original.convert("RGB")
        with Image.open(mask_path) as mask_image:
            alpha = mask_image.convert("RGBA").getchannel("A")
        outside_equal = True
        for y in range(height):
            for x in range(width):
                if alpha.getpixel((x, y)) == 255 and edited.getpixel((x, y)) != original.getpixel((x, y)):
                    outside_equal = False
                    break
            if not outside_equal:
                break

result = {
    "status": "passed" if outside_equal else "failed_outside_mask_changed",
    "job_id": job_id,
    "service_status": status_payload,
    "outside_mask_exact_match": outside_equal,
    "reference": str(reference_path),
    "mask": str(mask_path),
    "edited": str(output_path),
}
(Path(OUT) / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({key: value for key, value in result.items() if key not in {"service_status"}}, ensure_ascii=False))
if not outside_equal:
    raise SystemExit(2)

from __future__ import annotations

import json
import re
import subprocess
from copy import deepcopy
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

WIDTH = 1280
HEIGHT = 720


def _font(size: int, bold: bool = True, cjk: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = []
    if cjk:
        candidates.extend([
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
        ])
    candidates.extend([
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ])
    for path in candidates:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size=size)
            except OSError:
                continue
    return ImageFont.load_default()


def _render_clean_board_frame(job: dict[str, Any], frame_path: Path) -> None:
    frame_path.parent.mkdir(parents=True, exist_ok=True)
    clean_job = deepcopy(job)
    clean_job.update({
        "referenceMode": True,
        "audioSrc": "",
        "narration": "",
        "moves": [],
        "captions": [],
        "narrationSegments": [],
        "visualStoryboard": [],
        "durationInSeconds": 2.0,
    })
    props_path = frame_path.with_suffix(".job.json")
    props_path.write_text(json.dumps(clean_job, ensure_ascii=False), encoding="utf-8")
    command = [
        "npx", "remotion", "still", "src/index.tsx", "XiangqiComposition",
        str(frame_path), f"--props={props_path}", "--frame=24", "--image-format=png", "--log=error",
    ]
    completed = subprocess.run(command, cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True)
    if completed.returncode != 0 or not frame_path.exists():
        raise RuntimeError(f"Clean board thumbnail frame render failed: {completed.stderr[-1000:]}")


def _extract_frame(video_path: str | Path, frame_path: Path) -> None:
    frame_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg", "-y", "-i", str(video_path), "-vf", "select=eq(n\\,30)",
        "-frames:v", "1", "-q:v", "2", str(frame_path),
    ]
    completed = subprocess.run(command, capture_output=True, text=True)
    if completed.returncode != 0 or not frame_path.exists():
        fallback = ["ffmpeg", "-y", "-ss", "00:00:03", "-i", str(video_path), "-frames:v", "1", "-q:v", "2", str(frame_path)]
        subprocess.run(fallback, check=True, capture_output=True, text=True)


def _fit_cover(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    return ImageOps.fit(image.convert("RGB"), size, method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))


def _fit_contain(image: Image.Image, max_size: tuple[int, int]) -> Image.Image:
    copy = image.copy().convert("RGB")
    copy.thumbnail(max_size, Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", max_size, (13, 20, 36))
    canvas.paste(copy, ((max_size[0] - copy.width) // 2, (max_size[1] - copy.height) // 2))
    return canvas


def _headline(title: str, language: str = "en") -> str:
    clean = re.sub(r"\s*\|.*$", "", str(title or "Xiangqi Lesson")).strip()
    clean = re.sub(r"^Trending Xiangqi:\s*", "", clean, flags=re.I)
    if language == "zh":
        clean = re.sub(r"\s*｜.*$", "", clean).strip()
    words = clean.split()
    if len(words) > 7:
        words = words[:7]
    if language == "zh":
        return clean[:24]
    if len(words) <= 3:
        return " ".join(words).upper()
    midpoint = max(2, len(words) // 2)
    return " ".join(words[:midpoint]).upper() + "\n" + " ".join(words[midpoint:]).upper()


def _fit_headline_font(draw: ImageDraw.ImageDraw, text: str, base_size: int, max_width: int, cjk: bool) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    size = base_size
    while size >= 34:
        candidate = _font(size, bold=True, cjk=cjk)
        widths = [draw.textbbox((0, 0), line, font=candidate)[2] for line in text.split("\\n")]
        if max(widths or [0]) <= max_width:
            return candidate
        size -= 2
    return _font(34, bold=True, cjk=cjk)


def _build_thumbnail(frame: Image.Image, title: str, language: str, output_path: Path) -> Path:
    # Source-controlled layout is intentional here: the board and exact headline
    # must remain reliable, while the extracted frame supplies the video-specific focal point.
    background = _fit_cover(frame, (WIDTH, HEIGHT)).filter(ImageFilter.GaussianBlur(radius=18))
    background = Image.blend(background, Image.new("RGB", (WIDTH, HEIGHT), (7, 15, 31)), 0.56)
    canvas = background.convert("RGB")
    draw = ImageDraw.Draw(canvas)

    # Brand rail and warm Xiangqi accent.
    draw.rectangle((0, 0, 26, HEIGHT), fill=(231, 175, 67))
    draw.rectangle((62, 54, 410, 98), fill=(231, 175, 67))
    brand_font = _font(24, bold=True)
    draw.text((80, 63), "XIANGQI LAB", font=brand_font, fill=(10, 19, 35))

    panel = Image.new("RGBA", (590, 480), (7, 15, 31, 214))
    panel = panel.filter(ImageFilter.GaussianBlur(radius=0.3))
    canvas.paste(panel, (60, 150), panel)
    draw = ImageDraw.Draw(canvas)
    headline = _headline(title, language)
    headline_font = _fit_headline_font(draw, headline, 68 if language == "en" else 60, 520, language == "zh")
    draw.multiline_text((92, 198), headline, font=headline_font, fill=(255, 255, 249), spacing=10, stroke_width=2, stroke_fill=(6, 12, 24))
    label_font = _font(26, bold=True, cjk=language == "zh")
    label = "CHINESE CHESS" if language == "en" else "中国象棋"
    draw.rounded_rectangle((92, 505, 330, 555), radius=14, fill=(192, 52, 48))
    draw.text((112, 516), label, font=label_font, fill=(255, 255, 255))

    # Keep the video-specific board/scene visible in a crisp card on the right.
    card = _fit_contain(frame, (470, 630))
    card_x, card_y = 735, 45
    shadow = Image.new("RGBA", (card.width + 24, card.height + 24), (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    shadow_draw.rounded_rectangle((12, 12, card.width + 12, card.height + 12), radius=22, fill=(0, 0, 0, 150))
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=10))
    canvas.paste(shadow, (card_x - 12, card_y - 2), shadow)
    card_mask = Image.new("L", card.size, 0)
    ImageDraw.Draw(card_mask).rounded_rectangle((0, 0, card.width - 1, card.height - 1), radius=22, fill=255)
    canvas.paste(card, (card_x, card_y), card_mask)
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle((card_x, card_y, card_x + card.width, card_y + card.height), radius=22, outline=(231, 175, 67), width=5)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    quality = 90
    while quality >= 65:
        canvas.save(output_path, format="JPEG", quality=quality, optimize=True, progressive=True)
        if output_path.stat().st_size <= 2_000_000:
            return output_path
        quality -= 5
    raise RuntimeError(f"Thumbnail is larger than YouTube's 2MB upload limit: {output_path.stat().st_size}")


def validate_thumbnail_assets(assets: dict[str, Any]) -> list[str]:
    """Return blocking defects for the English thumbnail before any YouTube mutation."""
    errors: list[str] = []
    for key in ("english",):
        raw_path = assets.get(key) if isinstance(assets, dict) else None
        if not raw_path:
            errors.append(f"thumbnail asset missing: {key}")
            continue
        path = Path(raw_path)
        if not path.is_file():
            errors.append(f"thumbnail file missing: {key}: {path}")
            continue
        if path.suffix.lower() not in {".jpg", ".jpeg"}:
            errors.append(f"thumbnail is not JPEG: {key}: {path}")
        if path.stat().st_size > 2_000_000:
            errors.append(f"thumbnail exceeds 2MB: {key}: {path.stat().st_size}")
        try:
            with Image.open(path) as image:
                if image.size != (WIDTH, HEIGHT):
                    errors.append(f"thumbnail dimensions invalid: {key}: {image.size}")
                if image.format not in {"JPEG", "MPO"}:
                    errors.append(f"thumbnail format invalid: {key}: {image.format}")
                image.verify()
        except Exception as exc:
            errors.append(f"thumbnail unreadable: {key}: {exc}")
    return errors


def generate_thumbnail_assets(video_path: str | Path, job: dict[str, Any], output_dir: str | Path, zh_title: str | None = None) -> dict[str, Any]:
    """Generate the single English thumbnail used by the channel.

    ``zh_title`` remains an ignored compatibility argument for callers from
    older jobs; localized thumbnails are intentionally not generated or
    validated because the channel policy is English-thumbnail-only.
    """
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    frame_path = output / "clean_board.png"
    _render_clean_board_frame(job, frame_path)
    frame = Image.open(frame_path).convert("RGB")
    en_path = _build_thumbnail(frame, str(job.get("title") or "Xiangqi Lesson"), "en", output / "thumbnail_en.jpg")
    return {
        "default": str(en_path),
        "english": str(en_path),
        "width": WIDTH,
        "height": HEIGHT,
        "max_bytes": 2_000_000,
        "default_language": "en",
        "localized_thumbnail_status": "disabled_by_policy",
    }

#!/usr/bin/env python3
"""
AI Story Video Generator - Flask Backend
Uses NVIDIA NIM free APIs (build.nvidia.com) to generate videos from story text.

Usage:
    python video_server.py
    Then open http://localhost:5000 in your browser.
"""

__version__ = "1.0.0"

import base64
import contextlib
import io
import json
import os
import random
import re
import threading
import time
import traceback
import uuid
from datetime import datetime
from pathlib import Path

import numpy as np
from flask import Flask, jsonify, request, send_file, send_from_directory
from flask_cors import CORS

# ── Try imports ──────────────────────────────────────────────────────────────
try:
    import requests
    REQUESTS_OK = True
except ImportError:
    REQUESTS_OK = False

try:
    from openai import OpenAI
    OPENAI_OK = True
except ImportError:
    OPENAI_OK = False

try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_OK = True
except ImportError:
    PIL_OK = False

try:
    from moviepy import VideoClip, concatenate_videoclips
    from moviepy.video.fx import FadeIn, FadeOut
    MOVIEPY_OK = True
except ImportError:
    MOVIEPY_OK = False

try:
    import truststore
    truststore.inject_into_ssl()  # use OS cert store — fixes SSL on Windows
except ImportError:
    pass

# ── App setup ─────────────────────────────────────────────────────────────────
app = Flask(__name__, static_folder=None)
CORS(app)

WORK_DIR = Path(__file__).parent / "output"
WORK_DIR.mkdir(exist_ok=True)

# In-memory job tracker (restored from disk on startup)
jobs: dict[str, dict] = {}


def _save_job(job_id: str) -> None:
    """Persist job metadata so re-downloads survive server restarts."""
    job = jobs.get(job_id)
    if not job:
        return
    job_dir = WORK_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    # Keep only last 200 log lines to limit file size
    meta = {**job, "log": job.get("log", [])[-200:]}
    with contextlib.suppress(OSError):
        (job_dir / "job.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )


def _load_jobs() -> None:
    """Restore completed/errored jobs from disk on server startup."""
    if not WORK_DIR.exists():
        return
    for job_dir in WORK_DIR.iterdir():
        if not job_dir.is_dir():
            continue
        meta_file = job_dir / "job.json"
        if meta_file.exists():
            with contextlib.suppress(Exception):
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
                job_id = job_dir.name
                if job_id not in jobs:
                    jobs[job_id] = meta


_load_jobs()  # restore persisted jobs at import time (works under WSGI too)

# ── Backend i18n ───────────────────────────────────────────────────────────────
_backend_msgs: dict[str, str] = {}


def _load_backend_locale() -> None:
    global _backend_msgs
    lang = "zh-TW"
    cfg_path = Path(__file__).parent / "config.json"
    with contextlib.suppress(Exception):
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        lang = cfg.get("lang", "zh-TW")
    locale_path = Path(__file__).parent / "locales" / f"backend-{lang}.json"
    if not locale_path.exists():
        locale_path = Path(__file__).parent / "locales" / "backend-zh-TW.json"
    with contextlib.suppress(Exception):
        _backend_msgs = json.loads(locale_path.read_text(encoding="utf-8"))


def msg(key: str, **kwargs) -> str:
    """Look up a backend locale string and format it with kwargs."""
    template = _backend_msgs.get(key, key)
    return template.format(**kwargs) if kwargs else template


_load_backend_locale()

# ── NVIDIA NIM endpoints ───────────────────────────────────────────────────────
NIM_LLM_BASE = "https://integrate.api.nvidia.com/v1"
NIM_IMAGE_URL = "https://ai.api.nvidia.com/v1/genai/black-forest-labs/flux.1-dev"
NIM_IMAGE_FAST = "https://ai.api.nvidia.com/v1/genai/black-forest-labs/flux.1-schnell"

# ── Art style prompt prefixes ──────────────────────────────────────────────────
STYLE_PREFIXES: dict[str, str] = {
    "ink":        "Chinese traditional ink wash painting,",
    "oil":        "oil painting in classical Chinese style,",
    "ukiyoe":     "Japanese ukiyo-e woodblock print,",
    "watercolor":  "soft watercolor painting,",
    "pixel":      "pixel art, 16-bit retro style,",
}
DEFAULT_STYLE = "ink"

# ── Default scenes (大鬧天宮) ─────────────────────────────────────────────────
DEFAULT_SCENES = [
    {
        "title": "龍宮取寶",
        "subtitle": "如意金箍棒，重達三萬六千斤",
        "image_prompt": "Chinese traditional ink wash painting, Sun Wukong the Monkey King in the underwater Dragon Palace, ancient Chinese palace architecture, holding a glowing golden staff, dramatic lighting rays through water, monochrome ink painting on white rice paper, masterpiece, highly detailed"
    },
    {
        "title": "自封齊天大聖",
        "subtitle": "大聖威名，震懾四方",
        "image_prompt": "Chinese traditional ink wash painting, Sun Wukong standing triumphant on a mountain peak, dramatic clouds swirling around, golden headband, staff raised to sky, armies of monkeys below, monochrome ink on rice paper, epic composition, Chinese landscape style"
    },
    {
        "title": "蟠桃園盜桃",
        "subtitle": "偷食仙桃，擾亂蟠桃盛會",
        "image_prompt": "Chinese traditional ink wash painting, magical peach garden in heaven, Sun Wukong eating celestial peaches among blossoming trees, fairies fleeing, soft ink wash strokes, heavenly mist, monochrome painting, traditional Chinese art style, ethereal atmosphere"
    },
    {
        "title": "八卦爐煉丹",
        "subtitle": "七七四十九天，煉就火眼金睛",
        "image_prompt": "Chinese traditional ink wash painting, Taishang Laojun eight trigrams alchemy furnace, flames and smoke billowing, ancient Taoist symbols, dramatic dark ink tones, powerful energy lines, Chinese mythology art style, monochrome ink wash, mystical atmosphere"
    },
    {
        "title": "大鬧凌霄殿",
        "subtitle": "威震天宮，諸神束手無策",
        "image_prompt": "Chinese traditional ink wash painting, Sun Wukong fighting alone in the heavenly palace, golden staff sweeping across celestial warriors, magnificent palace architecture crumbling, ink splatter battle scene, dynamic brushstrokes, monochrome ink wash painting, epic action"
    },
    {
        "title": "如來降伏",
        "subtitle": "五行山下，壓五百年",
        "image_prompt": "Chinese traditional ink wash painting, Buddha's enormous divine hand descending from golden clouds, Five Elements Mountain forming to trap Sun Wukong below, vast serene landscape, spiritual rays of light, monochrome ink wash with subtle gold accents, awe-inspiring composition"
    }
]

# ── Helpers ────────────────────────────────────────────────────────────────────
def _safe_filename(text: str, max_len: int = 20) -> str:
    """Strip filesystem-unsafe chars; keep CJK and ASCII word characters."""
    return re.sub(r'[^\w一-鿿]', '', text)[:max_len] or "video"


def find_chinese_font(size: int):
    """Find a usable Chinese font and return ImageFont."""
    font_paths = [
        "C:/Windows/Fonts/msyh.ttc",       # Microsoft YaHei (Win)
        "C:/Windows/Fonts/msjh.ttc",        # Microsoft JhengHei
        "C:/Windows/Fonts/simsun.ttc",      # SimSun (Win)
        "C:/Windows/Fonts/simhei.ttf",      # SimHei (Win)
        "C:/Windows/Fonts/STFANGSO.TTF",    # STFangsong
        "/System/Library/Fonts/PingFang.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/noto/NotoSansCJK-Regular.ttc",
    ]
    if not PIL_OK:
        return None
    for fp in font_paths:
        if os.path.exists(fp):
            try:
                return ImageFont.truetype(fp, size)
            except Exception:
                continue
    try:
        return ImageFont.load_default()
    except Exception:
        return None


# ── Image generation ───────────────────────────────────────────────────────────
def generate_image(prompt: str, api_key: str, scene_idx: int,
                   img_dir: Path, fast_mode: bool = False) -> Path:
    """Generate one scene image via NVIDIA NIM FLUX API."""
    out_path = img_dir / f"scene_{scene_idx:02d}.png"

    url = NIM_IMAGE_FAST if fast_mode else NIM_IMAGE_URL
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    # Both dev and schnell endpoints only accept prompt/width/height/seed.
    # num_inference_steps and guidance are forbidden by the NIM API.
    # allowed height/width values: 768, 832, 896, 960, 1024, 1088, 1152, 1216, 1280, 1344
    payload: dict = {
        "prompt": prompt,
        "width": 1344,
        "height": 768,
        "seed": 100 + scene_idx,
    }

    last_exc: Exception = RuntimeError("unreachable")
    for attempt in range(3):
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=120)  # type: ignore[arg-type]
            if not resp.ok:
                raise requests.HTTPError(
                    f"{resp.status_code} {resp.reason} — {resp.text[:600]}", response=resp
                )
            data = resp.json()
            if "artifacts" in data and data["artifacts"]:
                img_bytes = base64.b64decode(data["artifacts"][0]["base64"])
                img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
                img = img.resize((1280, 720), Image.Resampling.LANCZOS)
                img.save(out_path, "PNG")
                return out_path
            raise ValueError(f"Unexpected response: {json.dumps(data)[:200]}")
        except requests.Timeout as exc:
            last_exc = exc
            if attempt < 2:
                time.sleep(5)  # brief pause before retry
        except requests.HTTPError as exc:
            raise  # non-timeout HTTP errors are not retryable
    raise last_exc


def make_placeholder(scene_idx: int, title: str, img_dir: Path) -> Path:
    """Create a gradient placeholder image with scene title when API is unavailable."""
    out_path = img_dir / f"scene_{scene_idx:02d}.png"
    iw, ih = 1280, 720

    # Parchment-tone gradient palette — each scene gets a distinct hue
    palette = [
        ((235, 228, 210), (180, 165, 140)),
        ((210, 225, 230), (150, 170, 185)),
        ((225, 215, 225), (170, 155, 175)),
        ((215, 230, 215), (155, 175, 155)),
        ((235, 220, 205), (185, 160, 135)),
        ((210, 210, 230), (150, 150, 185)),
    ]
    c1, c2 = palette[scene_idx % len(palette)]

    arr = np.zeros((ih, iw, 3), dtype=np.uint8)
    for y in range(ih):
        t = y / ih
        arr[y] = [int(c1[i] * (1 - t) + c2[i] * t) for i in range(3)]
    img = Image.fromarray(arr)
    draw = ImageDraw.Draw(img)

    rng = random.Random(scene_idx * 42)
    for _ in range(6):
        x1 = rng.randint(80, iw - 80)
        y1 = rng.randint(60, ih - 60)
        x2 = x1 + rng.randint(-200, 200)
        y2 = y1 + rng.randint(-100, 100)
        alpha = rng.randint(20, 55)
        draw.line([(x1, y1), (x2, y2)], fill=(80, 60, 40, alpha), width=rng.randint(2, 8))

    draw.rectangle([18, 18, iw - 18, ih - 18], outline=(120, 100, 80), width=3)
    draw.rectangle([28, 28, iw - 28, ih - 28], outline=(160, 140, 110), width=1)

    badge_txt = f"Scene {scene_idx + 1}"
    draw.rectangle([42, 42, 160, 78], fill=(80, 60, 40))
    try:
        font_badge = ImageFont.load_default(size=20)
        draw.text((50, 50), badge_txt, font=font_badge, fill=(240, 225, 190))
    except TypeError:
        draw.text((50, 52), badge_txt, fill=(240, 225, 190))

    font_title = find_chinese_font(68)
    label = title if title else f"Scene {scene_idx + 1}"

    if font_title:
        draw.text((iw // 2, ih // 2 - 30), label, font=font_title,
                  fill=(60, 40, 20), anchor="mm")
    else:
        # No Chinese font — draw a fallback banner
        draw.rectangle([iw // 2 - 220, ih // 2 - 55, iw // 2 + 220, ih // 2 + 55],
                       fill=(60, 40, 20, 200))
        try:
            font_scene = ImageFont.load_default(size=28)
            draw.text((iw // 2, ih // 2 - 15), f"[ Scene {scene_idx + 1} ]",
                      font=font_scene, fill=(240, 225, 190), anchor="mm")
            draw.text((iw // 2, ih // 2 + 20), "(AI image will replace this)",
                      font=ImageFont.load_default(size=16),
                      fill=(200, 185, 155), anchor="mm")
        except TypeError:
            draw.text((iw // 2 - 80, ih // 2 - 10), f"Scene {scene_idx + 1}",
                      fill=(240, 225, 190))

    try:
        font_note = ImageFont.load_default(size=14)
        draw.text((iw // 2, ih - 40), "[ Placeholder – NVIDIA NIM image will be generated here ]",
                  font=font_note, fill=(120, 100, 80), anchor="mm")
    except TypeError:
        pass

    img.save(out_path, "PNG")
    return out_path


# ── Subtitle overlay ───────────────────────────────────────────────────────────
def add_subtitle_to_image(img_path: Path, title: str, subtitle: str) -> Path:
    """Bake subtitle into a copy of the image."""
    out_path = img_path.parent / (img_path.stem + "_sub.png")
    img = Image.open(img_path).convert("RGBA")
    w, h = img.size

    # Semi-transparent bottom bar
    overlay = Image.new("RGBA", (w, 160), (0, 0, 0, 170))
    img.paste(overlay, (0, h - 160), overlay)

    draw = ImageDraw.Draw(img)
    font_title = find_chinese_font(52) or ImageFont.load_default()
    font_sub   = find_chinese_font(34) or ImageFont.load_default()

    draw.text((w // 2, h - 120), title,    font=font_title, fill=(255, 220, 120, 255), anchor="mm")
    draw.text((w // 2, h - 52),  subtitle, font=font_sub,   fill=(240, 240, 240, 230), anchor="mm")

    img_rgb = img.convert("RGB")
    img_rgb.save(out_path, "PNG")
    return out_path


# ── Video assembly ─────────────────────────────────────────────────────────────
def build_video(image_paths: list[Path],
                output_path: Path, duration: float = 5.0):
    """Assemble images into MP4 with Ken Burns zoom + fade transitions (moviepy 2.x)."""

    if not image_paths:
        raise ValueError("image_paths is empty — no frames to assemble")

    def make_ken_burns(img_array, total_dur, fps=24,
                       zoom_start=1.0, zoom_end=1.1):
        h, w = img_array.shape[:2]
        pil_img = Image.fromarray(img_array)  # created once; reused every frame

        def frame_fn(t):
            progress = t / total_dur
            zoom = zoom_start + (zoom_end - zoom_start) * progress
            nw, nh = int(w * zoom), int(h * zoom)
            frame = pil_img.resize((nw, nh), Image.Resampling.LANCZOS)
            left = (nw - w) // 2
            top  = (nh - h) // 2
            return np.array(frame.crop((left, top, left + w, top + h)))

        return VideoClip(frame_fn, duration=total_dur).with_fps(fps)

    clips = []
    for img_path in image_paths:
        arr = np.array(Image.open(img_path).convert("RGB").resize((1280, 720)))
        clip = make_ken_burns(arr, duration)
        clip = clip.with_effects([FadeIn(0.4), FadeOut(0.4)])
        clips.append(clip)

    final = concatenate_videoclips(clips, method="compose")
    final.write_videofile(
        str(output_path),
        fps=24,
        codec="libx264",
        audio=False,
        preset="ultrafast",
        logger=None
    )
    final.close()


# ── LLM scene breakdown ────────────────────────────────────────────────────────
def llm_generate_scenes(story_text: str, api_key: str, num_scenes: int = 6,
                        style_prefix: str = STYLE_PREFIXES[DEFAULT_STYLE]) -> list[dict]:
    """Use NVIDIA NIM LLM to produce scene JSON from story."""
    client = OpenAI(base_url=NIM_LLM_BASE, api_key=api_key)

    system = (
        "You are a film storyboard artist specialising in Chinese classical literature. "
        "Return ONLY valid JSON, no markdown fences."
    )
    user = f"""Break this story into {num_scenes} visual scenes for a short video.

Story:
{story_text}

Return a JSON object with key "scenes" containing an array of {num_scenes} objects, each with:
- "title": 4-6 Chinese characters (scene name)
- "subtitle": 10-20 Chinese characters (key narrative moment)
- "image_prompt": English prompt for FLUX.1 image generation, always start with "{style_prefix}" and describe the scene vividly

Example format:
{{"scenes": [{{"title": "龍宮取寶", "subtitle": "如意金箍棒威震四海", "image_prompt": "{style_prefix} ..."}}]}}"""

    resp = client.chat.completions.create(
        model="meta/llama-3.3-70b-instruct",
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": user}],
        temperature=0.7,
        max_tokens=2048
    )
    raw = (resp.choices[0].message.content or "").strip()
    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = "\n".join(raw.split("\n")[1:])
    if raw.endswith("```"):
        raw = "\n".join(raw.split("\n")[:-1])

    data = json.loads(raw)
    scenes: list[dict] = data.get("scenes", data) if isinstance(data, dict) else data
    return scenes[:num_scenes]


# ── Background job runner ──────────────────────────────────────────────────────
def run_job(job_id: str, api_key: str, story_text: str,
            num_scenes: int, use_llm: bool, fast_mode: bool,
            scene_duration: float = 5.0, style: str = DEFAULT_STYLE):
    """
    Background worker that drives the full video generation pipeline.

    Runs in a daemon thread. Writes progress/log to jobs[job_id] so
    the /api/status endpoint can stream updates to the frontend.

    Steps:
        1. Scene breakdown — LLM or built-in default scenes
        2. Image generation — NVIDIA NIM FLUX.1 or placeholder
        3. Video assembly  — Ken Burns zoom + fade via moviepy

    Args:
        job_id:         Unique job identifier (stored in global `jobs` dict).
        api_key:        NVIDIA NIM API key (Bearer token).
        story_text:     Source story for scene breakdown / default fallback.
        num_scenes:     How many scenes to generate (1–12).
        use_llm:        Whether to call LLaMA for scene breakdown.
        fast_mode:      If True use FLUX.1-schnell (10 steps) instead of dev (25).
        scene_duration: Seconds per scene clip (1–15, default 5).
    """

    def update(step, msg, pct=None):
        """Append a log line and optionally update progress percentage."""
        ts = datetime.now().strftime("%H:%M:%S")
        jobs[job_id]["log"].append(f"[{ts}] [{step}] {msg}")
        if pct is not None:
            jobs[job_id]["progress"] = pct
        jobs[job_id]["last_msg"] = msg

    try:
        jobs[job_id]["status"] = "running"
        job_dir = WORK_DIR / job_id
        img_dir = job_dir / "frames"
        job_dir.mkdir(parents=True, exist_ok=True)
        img_dir.mkdir(exist_ok=True)

        # ── Step 1: generate scene list ──────────────────────────────────────
        style_prefix = STYLE_PREFIXES.get(style, STYLE_PREFIXES[DEFAULT_STYLE])
        update("1/3", msg("step1.start"), 5)
        if use_llm and api_key and OPENAI_OK:
            try:
                scenes = llm_generate_scenes(story_text, api_key, num_scenes, style_prefix)
                update("1/3", msg("step1.ok", n=len(scenes)), 15)
            except Exception as e:
                update("1/3", msg("step1.warn_llm", e=e), 15)
                scenes = DEFAULT_SCENES[:num_scenes]
        else:
            scenes = DEFAULT_SCENES[:num_scenes]
            update("1/3", msg("step1.builtin", n=len(scenes)), 15)

        # Apply style prefix — replace the default ink-wash prefix if present
        ink_prefix = STYLE_PREFIXES[DEFAULT_STYLE]
        for scene in scenes:
            prompt = scene.get("image_prompt", "")
            if prompt.startswith(ink_prefix):
                scene["image_prompt"] = style_prefix + prompt[len(ink_prefix):]
            elif not prompt.startswith(style_prefix):
                scene["image_prompt"] = style_prefix + " " + prompt

        # Derive a human-readable filename: YYYYMMDD_HHMM_<first_scene_title>.mp4
        ts = datetime.now().strftime("%Y%m%d_%H%M")
        scene_name = _safe_filename(scenes[0].get("title", "")) if scenes else "video"
        video_filename = f"{ts}_{scene_name}.mp4"
        jobs[job_id]["video_filename"] = video_filename

        # ── Step 2: generate images ───────────────────────────────────────────
        update("2/3", msg("step2.start"), 20)
        if not PIL_OK:
            raise RuntimeError(msg("job.missing_pil"))
        image_paths = []
        for i, scene in enumerate(scenes):
            pct = 20 + int(60 * (i / len(scenes)))
            update("2/3", msg("step2.scene", i=i+1, n=len(scenes), title=scene.get("title", "")), pct)

            try:
                if api_key and REQUESTS_OK and PIL_OK:
                    raw_path = generate_image(
                        scene.get("image_prompt", "Chinese ink painting scene"),
                        api_key, i, img_dir, fast_mode
                    )
                else:
                    raw_path = make_placeholder(i, scene.get("title", f"Scene {i+1}"), img_dir)
            except Exception as e:
                update("2/3", msg("step2.warn_img", e=e), pct)
                raw_path = make_placeholder(i, scene.get("title", f"Scene {i+1}"), img_dir)

            # Bake subtitle
            if PIL_OK:
                try:
                    final_path = add_subtitle_to_image(
                        raw_path,
                        scene.get("title", ""),
                        scene.get("subtitle", "")
                    )
                    image_paths.append(final_path)
                except Exception as e:
                    update("2/3", msg("step2.warn_sub", e=e), pct)
                    image_paths.append(raw_path)
            else:
                image_paths.append(raw_path)

        update("2/3", msg("step2.ok", n=len(image_paths)), 80)

        # ── Step 3: assemble video ────────────────────────────────────────────
        if not MOVIEPY_OK:
            raise RuntimeError(msg("job.missing_mpy"))

        update("3/3", msg("step3.start"), 82)
        video_path = job_dir / video_filename
        build_video(image_paths, video_path, duration=scene_duration)

        total_sec = int(len(scenes) * scene_duration)
        jobs[job_id]["log"].append(f"[{datetime.now().strftime('%H:%M:%S')}] [Done] {msg('step3.saved', filename=video_path.name)}")
        jobs[job_id]["status"] = "done"
        jobs[job_id]["video_path"] = str(video_path)
        jobs[job_id]["progress"] = 100
        jobs[job_id]["last_msg"] = msg("job.done", n=len(scenes), total_sec=total_sec)
        _save_job(job_id)

    except Exception as e:
        tb = traceback.format_exc()
        jobs[job_id]["status"] = "error"
        jobs[job_id]["error"] = str(e)
        jobs[job_id]["last_msg"] = msg("job.error", e=e)
        jobs[job_id]["log"].append(f"[{datetime.now().strftime('%H:%M:%S')}] [ERROR] {tb}")
        _save_job(job_id)


# ── Flask routes ───────────────────────────────────────────────────────────────

@app.route("/")
def index():
    """Serve the main frontend (index.html) from the same directory."""
    html_file = Path(__file__).parent / "index.html"
    if html_file.exists():
        return send_file(str(html_file))
    return "<h2>請將 index.html 放在同一目錄下</h2>", 404


@app.route("/locales/<path:filename>")
def serve_locale(filename):
    """Serve i18n locale JSON files."""
    return send_from_directory(Path(__file__).parent / "locales", filename)


@app.route("/api/generate", methods=["POST"])
def api_generate():
    """
    POST /api/generate

    Start a new video generation job.

    Request body (JSON):
        api_key        (str)  : NVIDIA NIM API key — required.
        story          (str)  : Story text; defaults to 大鬧天宮 if empty.
        num_scenes     (int)  : Number of scenes 1–12 (default 6).
        use_llm        (bool) : Whether to use LLaMA for scene breakdown (default True).
        fast_mode      (bool) : Use FLUX.1-schnell instead of dev (default False).
        scene_duration (float): Seconds per scene clip, 1–15 (default 5).

    Returns:
        JSON {"job_id": "<8-char id>"} — poll /api/status/<job_id> for progress.
    """
    data = request.json or {}
    api_key = data.get("api_key", "").strip()
    story   = data.get("story", "").strip() or None
    use_llm   = bool(data.get("use_llm", True))
    fast_mode = bool(data.get("fast_mode", False))
    try:
        num_scenes     = max(1, min(12, int(data.get("num_scenes", 6))))
        scene_duration = max(1.0, min(15.0, float(data.get("scene_duration", 5.0))))
    except (TypeError, ValueError):
        return jsonify({"error": msg("api.invalid_params")}), 400

    style = data.get("style", DEFAULT_STYLE)
    if style not in STYLE_PREFIXES:
        style = DEFAULT_STYLE

    if not api_key:
        return jsonify({"error": msg("api.missing_key")}), 400

    job_id = str(uuid.uuid4())[:8]
    jobs[job_id] = {
        "status": "queued",
        "progress": 0,
        "last_msg": msg("job.queued"),
        "log": [],
        "video_path": None,
        "error": None
    }

    story_text = story or (
        "西遊記 - 大鬧天宮\n"
        "孫悟空取得如意金箍棒，自封齊天大聖，"
        "盜食仙桃，大鬧蟠桃盛會，在太上老君八卦爐中煉就火眼金睛，"
        "之後大鬧凌霄寶殿，最終被如來佛祖以五行山鎮壓。"
    )

    thread = threading.Thread(
        target=run_job,
        args=(job_id, api_key, story_text, num_scenes, use_llm, fast_mode,
              scene_duration, style),
        daemon=True
    )
    thread.start()

    return jsonify({"job_id": job_id})


@app.route("/api/status/<job_id>")
def api_status(job_id):
    """
    GET /api/status/<job_id>

    Poll the status of a running or completed job.

    Returns JSON:
        status    (str)       : queued | running | done | error
        progress  (int)       : 0–100
        message   (str)       : Latest human-readable status message.
        log       (list[str]) : Full accumulated log lines for Copy Log feature.
        error     (str|null)  : Error message if status == "error".
        filename  (str|null)  : Download filename once job is done.
    """
    if job_id not in jobs:
        return jsonify({"error": msg("api.job_not_found")}), 404
    job = jobs[job_id]
    return jsonify({
        "status":   job["status"],
        "progress": job["progress"],
        "message":  job["last_msg"],
        "log":      job["log"],
        "error":    job["error"],
        "filename": job.get("video_filename"),
    })


@app.route("/api/download/<job_id>")
def api_download(job_id):
    """
    GET /api/download/<job_id>

    Stream the completed MP4 file as an attachment download.
    Returns 404 if the job doesn't exist or the video hasn't been generated yet.
    """
    if job_id not in jobs:
        return jsonify({"error": msg("api.job_not_found")}), 404
    video_path = jobs[job_id].get("video_path")
    if not video_path or not Path(video_path).exists():
        return jsonify({"error": msg("api.video_not_ready")}), 404
    download_name = jobs[job_id].get("video_filename") or f"story_video_{job_id}.mp4"
    return send_file(
        video_path,
        mimetype="video/mp4",
        as_attachment=True,
        download_name=download_name
    )


@app.route("/api/check")
def api_check():
    """Health check + dependency status."""
    return jsonify({
        "status":  "ok",
        "version": __version__,
        "deps": {
            "requests": REQUESTS_OK,
            "openai":   OPENAI_OK,
            "PIL":      PIL_OK,
            "moviepy":  MOVIEPY_OK
        }
    })


# ── Entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 56)
    print("  AI 故事影片生成器 - NVIDIA NIM")
    print("=" * 56)

    missing = []
    if not REQUESTS_OK:
        missing.append("requests")
    if not OPENAI_OK:
        missing.append("openai")
    if not PIL_OK:
        missing.append("Pillow")
    if not MOVIEPY_OK:
        missing.append("moviepy")

    if missing:
        print(f"\n[!] 缺少套件: {', '.join(missing)}")
        print(f"    請執行: pip install {' '.join(missing)}\n")
    else:
        print("\n[OK] 所有套件已安裝完畢\n")

    restored = [j for j in jobs if jobs[j]["status"] in ("done", "error")]
    if restored:
        print(f"  已還原 {len(restored)} 個歷史任務（可重新下載）\n")

    print("  開啟瀏覽器: http://localhost:5000")
    print("  按 Ctrl+C 停止伺服器\n")

    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)

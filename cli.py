#!/usr/bin/env python3
"""
AI 故事影片生成器 - 無頭模式（排程用）
Headless video generator for scheduled/automated runs.

Usage:
    python cli.py
    python cli.py --story "自訂故事文字"
    python cli.py --scenes 6 --fast
"""

import argparse
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

# ── Config from env or defaults ───────────────────────────────────────────────
API_KEY    = os.environ.get("NVIDIA_API_KEY", "")
OUTPUT_DIR = Path(os.environ.get("VIDEO_OUTPUT_DIR",
    str(Path(__file__).parent / "output")))


def main() -> None:
    """
    CLI entry point for scheduled / headless video generation.

    Reads config from CLI args or environment variables, then delegates
    to video_server.run_job() for the actual generation pipeline.
    The finished MP4 is copied to OUTPUT_DIR with a timestamp filename.

    Environment variables:
        NVIDIA_API_KEY    : NVIDIA NIM API key (overridden by --key).
        VIDEO_OUTPUT_DIR  : Destination folder for finished videos.

    Exit codes:
        0 — success
        1 — missing API key or generation error
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--story",    default="", help="故事文字（留空使用預設）")
    parser.add_argument("--scenes",   type=int,   default=6)
    parser.add_argument("--duration", type=float, default=5.0, help="每場景秒數（1-15，預設 5）")
    parser.add_argument("--fast",     action="store_true", help="使用 FLUX-schnell 快速模式")
    parser.add_argument("--key",      default="", help="NVIDIA API Key（優先於環境變數）")
    args = parser.parse_args()

    api_key = args.key or API_KEY
    if not api_key:
        print("❌ 請設定 NVIDIA_API_KEY 環境變數或使用 --key 參數")
        sys.exit(1)

    server_path = Path(__file__).parent / "video_server.py"
    if server_path.exists():
        sys.path.insert(0, str(server_path.parent))
        from video_server import jobs, run_job  # noqa: PLC0415
    else:
        print("❌ video_server.py 不在同一目錄")
        sys.exit(1)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    job_id = f"sched_{ts}"
    jobs[job_id] = {
        "status": "queued", "progress": 0,
        "last_msg": "", "log": [], "video_path": None, "error": None
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    story = args.story or (
        "西遊記 - 大鬧天宮：孫悟空東海龍宮取得如意金箍棒，自封齊天大聖，"
        "盜食仙桃，大鬧蟠桃盛會，於太上老君八卦爐中煉就火眼金睛，"
        "之後大鬧凌霄寶殿，最終被如來佛祖以五行山鎮壓。"
    )

    scene_dur = max(1.0, min(15.0, args.duration))

    print(f"\n{'='*50}")
    print(" AI 故事影片生成器 (排程模式)")
    print(f" Job ID  : {job_id}")
    print(f" 場景數  : {args.scenes}")
    print(f" 場景時長: {scene_dur}s")
    print(f" 快速模式: {args.fast}")
    print(f"{'='*50}\n")

    run_job(job_id, api_key, story, args.scenes, True, args.fast, scene_dur)

    job = jobs[job_id]
    if job["status"] == "done":
        src = Path(job["video_path"])
        dst = OUTPUT_DIR / f"story_video_{ts}.mp4"
        shutil.copy(src, dst)
        size_kb = dst.stat().st_size // 1024
        print("\n✅ 完成！")
        print(f"   輸出: {dst}")
        print(f"   大小: {size_kb} KB")
    else:
        print(f"\n❌ 失敗: {job['error']}")
        sys.exit(1)


if __name__ == "__main__":
    main()

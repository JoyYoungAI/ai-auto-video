#!/usr/bin/env python3
"""
AI 故事影片生成器 - 無頭模式（排程用）
Headless video generator for scheduled/automated runs.

Usage:
    python generate_video_headless.py
    python generate_video_headless.py --story "自訂故事文字"
    python generate_video_headless.py --scenes 6 --fast
"""

import os, sys, json, base64, io, argparse, uuid
from pathlib import Path
from datetime import datetime

# ── Config from env or defaults ───────────────────────────────────────────────
API_KEY    = os.environ.get("NVIDIA_API_KEY", "")
OUTPUT_DIR = Path(os.environ.get("VIDEO_OUTPUT_DIR",
    r"C:\Users\baiyu\OneDrive\文件\Claude\Projects\ai-auto-video\output"))

def main():
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
    parser.add_argument("--story",  default="", help="故事文字（留空使用預設）")
    parser.add_argument("--scenes", type=int, default=6)
    parser.add_argument("--fast",   action="store_true", help="使用 FLUX-schnell 快速模式")
    parser.add_argument("--key",    default="", help="NVIDIA API Key（優先於環境變數）")
    args = parser.parse_args()

    api_key = args.key or API_KEY
    if not api_key:
        print("❌ 請設定 NVIDIA_API_KEY 環境變數或使用 --key 參數")
        sys.exit(1)

    # Import shared logic from video_server
    server_path = Path(__file__).parent / "video_server.py"
    if server_path.exists():
        sys.path.insert(0, str(server_path.parent))
        from video_server import (
            run_job, jobs, DEFAULT_SCENES,
            generate_image, add_subtitle_to_image, build_video,
            make_placeholder, llm_generate_scenes,
            REQUESTS_OK, PIL_OK, MOVIEPY_OK, OPENAI_OK
        )
    else:
        print("❌ video_server.py 不在同一目錄")
        sys.exit(1)

    # Timestamped output dir
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

    print(f"\n{'='*50}")
    print(f" AI 故事影片生成器 (排程模式)")
    print(f" Job ID  : {job_id}")
    print(f" 場景數  : {args.scenes}")
    print(f" 快速模式: {args.fast}")
    print(f"{'='*50}\n")

    run_job(job_id, api_key, story, args.scenes, True, args.fast)

    job = jobs[job_id]
    if job["status"] == "done":
        src = Path(job["video_path"])
        dst = OUTPUT_DIR / f"story_video_{ts}.mp4"
        import shutil; shutil.copy(src, dst)
        size_kb = dst.stat().st_size // 1024
        print(f"\n✅ 完成！")
        print(f"   輸出: {dst}")
        print(f"   大小: {size_kb} KB")
    else:
        print(f"\n❌ 失敗: {job['error']}")
        sys.exit(1)

if __name__ == "__main__":
    main()

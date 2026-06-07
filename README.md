# AI Story Video Generator · NVIDIA NIM

> **AI 故事影片生成器** — 輸入一段故事，自動產出水墨畫風格 MP4 短影片

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python)](https://python.org)
[![NVIDIA NIM](https://img.shields.io/badge/NVIDIA%20NIM-Free%20API-76b900?logo=nvidia)](https://build.nvidia.com)
[![Flask](https://img.shields.io/badge/Flask-3.0-black?logo=flask)](https://flask.palletsprojects.com)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

---

[繁體中文](#繁體中文) | [English](#english)

---

## 繁體中文

### 專案介紹

利用 **NVIDIA NIM 免費 API** 將文字故事自動轉換成 MP4 短影片：
- **LLaMA 3.3 70B** 將故事拆解為多個視覺場景
- **FLUX.1-dev / schnell** 生成水墨畫風格場景圖片
- **moviepy 2.x** 加上 Ken Burns 縮放動效、淡入淡出、中文字幕組裝成影片

預設內容為西遊記·大鬧天宮，也可輸入任意故事段落。

### 功能特色

- 🎬 **全自動流水線** — 輸入故事文字，輸出 MP4，無需任何手動操作
- 🖌️ **水墨畫風格** — FLUX.1 提示詞針對中國傳統水墨畫調校
- 🔑 **API Key 安全管理** — 僅存於 `sessionStorage`，關閉瀏覽器自動清除
- 📱 **RWD 前端** — 支援桌機、平板、手機
- ⚡ **快速模式** — 切換 FLUX.1-schnell 節省時間
- 📋 **複製 Log** — 一鍵複製完整生成記錄供除錯
- 🌐 **多語系支援** — 繁體中文 / English UI 切換
- ⏰ **排程生成** — 可設定每日定時自動生成（Cowork 技能）

### 架構

```
ai-auto-video/
├── video_server.py          # Flask 後端（API + 影片生成引擎）
├── index.html               # RWD 前端
├── generate_video_headless.py  # 無頭模式（排程用）
├── config.json              # 設定檔（含 API Key）
├── start.bat                # Windows 一鍵啟動
├── pyproject.toml           # uv 套件定義
├── locales/
│   ├── zh-TW.json           # 繁體中文語系
│   └── en.json              # 英文語系
└── output/                  # 生成影片輸出目錄（自動建立）
```

```
使用者瀏覽器
     │  POST /api/generate
     ▼
  Flask 後端
     │
     ├─ LLaMA 3.3 70B ──→ 場景 JSON（標題、字幕、圖像提示詞）
     │   integrate.api.nvidia.com/v1
     │
     ├─ FLUX.1-dev ──→ 水墨畫場景圖片（1344×768）
     │   ai.api.nvidia.com/v1/genai/black-forest-labs/flux.1-dev
     │
     └─ moviepy ──→ Ken Burns + 字幕疊加 + 組裝 MP4
```

### 系統需求

| 項目 | 需求 |
|------|------|
| Python | 3.10+ |
| 套件管理 | [uv](https://docs.astral.sh/uv/) 推薦，或 pip |
| NVIDIA API Key | 免費申請：[build.nvidia.com](https://build.nvidia.com) |
| OS | Windows 10/11、macOS、Linux |

### 快速啟動

#### Windows（推薦）

```batch
# 雙擊 start.bat 即可
# 首次執行會自動安裝 uv 及所有套件
```

#### 手動啟動

```bash
# 1. 安裝 uv（如尚未安裝）
curl -LsSf https://astral.sh/uv/install.sh | sh  # macOS/Linux
# Windows: irm https://astral.sh/uv/install.ps1 | iex

# 2. 安裝套件
uv sync

# 3. 啟動伺服器
uv run video_server.py

# 4. 開啟瀏覽器
# http://localhost:5000
```

#### 使用 pip

```bash
pip install flask flask-cors openai requests Pillow moviepy numpy
python video_server.py
```

### 設定

`config.json` — 排程 / 無頭模式使用，前端直接由瀏覽器輸入：

```json
{
  "nvidia_api_key": "nvapi-...",
  "default_scenes": 6,
  "fast_mode": false,
  "output_dir": "/path/to/output"
}
```

### API 端點

| Method | Endpoint | 說明 |
|--------|----------|------|
| `POST` | `/api/generate` | 啟動影片生成任務 |
| `GET`  | `/api/status/<job_id>` | 查詢任務進度 |
| `GET`  | `/api/download/<job_id>` | 下載生成的 MP4 |
| `GET`  | `/api/check` | 後端健康檢查 |

**POST `/api/generate` 請求格式：**

```json
{
  "api_key": "nvapi-...",
  "story": "故事段落（留空使用預設大鬧天宮）",
  "num_scenes": 6,
  "use_llm": true,
  "fast_mode": false
}
```

### 多語系支援

前端語系切換支援 **繁體中文** 和 **English**，語系設定存於 `localStorage`，重開瀏覽器後保留。
語系檔位於 `locales/` 目錄，歡迎提交 PR 新增其他語言。

### 開發路線圖

- [x] 6 場景 30 秒短影片
- [x] LLaMA 場景分解 + FLUX.1 圖像生成
- [x] Ken Burns 動效 + 字幕疊加
- [x] RWD 前端 + sessionStorage API Key
- [x] 多語系 UI（zh-TW / en）
- [ ] 10 分鐘長影片支援（120 場景）
- [ ] 背景音樂支援
- [ ] 多種藝術風格（油畫、浮世繪、像素藝術）
- [ ] 批次生成模式
- [ ] Docker 容器化

### 授權

本專案採用 [MIT License](LICENSE)。

NVIDIA NIM API 使用受 [NVIDIA API Trial Terms of Service](https://assets.ngc.nvidia.com/products/api-catalog/legal/NVIDIA%20API%20Trial%20Terms%20of%20Service.pdf) 規範。

---

## English

### Overview

An **AI-powered story-to-video pipeline** using free NVIDIA NIM APIs:
- **LLaMA 3.3 70B** breaks the story into visual scenes
- **FLUX.1-dev / schnell** generates Chinese ink-wash style images
- **moviepy 2.x** adds Ken Burns zoom, fade transitions, and Chinese subtitles

Ships with a *Journey to the West — Monkey King's Rampage* demo. Works with any story text.

### Features

- 🎬 **Fully automated** — input text, get MP4, zero manual steps
- 🖌️ **Ink-wash aesthetic** — prompts tuned for traditional Chinese painting style
- 🔑 **Secure key handling** — API key lives in `sessionStorage` only, cleared on browser close
- 📱 **Responsive UI** — desktop, tablet, and mobile
- ⚡ **Fast mode** — switch to FLUX.1-schnell for quicker results
- 📋 **Copy Log** — one-click full log export for debugging
- 🌐 **i18n** — Traditional Chinese / English UI toggle
- ⏰ **Scheduled generation** — daily auto-run via Cowork skill

### Architecture

```
Browser
  │  POST /api/generate
  ▼
Flask backend
  │
  ├─ LLaMA 3.3 70B ──→ Scene JSON (title, subtitle, image prompt)
  │   integrate.api.nvidia.com/v1
  │
  ├─ FLUX.1-dev ──→ Ink-wash scene images (1344×768)
  │   ai.api.nvidia.com/v1/genai/black-forest-labs/flux.1-dev
  │
  └─ moviepy ──→ Ken Burns + subtitle overlay + MP4 assembly
```

### Requirements

| Item | Requirement |
|------|-------------|
| Python | 3.10+ |
| Package manager | [uv](https://docs.astral.sh/uv/) recommended, or pip |
| NVIDIA API Key | Free at [build.nvidia.com](https://build.nvidia.com) |
| OS | Windows 10/11, macOS, Linux |

### Quick Start

#### Windows (recommended)

```batch
# Double-click start.bat
# Automatically installs uv and all packages on first run
```

#### Manual

```bash
# 1. Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh  # macOS/Linux
# Windows: irm https://astral.sh/uv/install.ps1 | iex

# 2. Install dependencies
uv sync

# 3. Start server
uv run video_server.py

# 4. Open browser at http://localhost:5000
```

#### With pip

```bash
pip install flask flask-cors openai requests Pillow moviepy numpy
python video_server.py
```

### Configuration

`config.json` is used by headless / scheduled mode. The browser UI accepts the key interactively:

```json
{
  "nvidia_api_key": "nvapi-...",
  "default_scenes": 6,
  "fast_mode": false,
  "output_dir": "/path/to/output"
}
```

### API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/generate` | Start a video generation job |
| `GET`  | `/api/status/<job_id>` | Poll job progress |
| `GET`  | `/api/download/<job_id>` | Download generated MP4 |
| `GET`  | `/api/check` | Backend health check |

**POST `/api/generate` body:**

```json
{
  "api_key": "nvapi-...",
  "story": "Story text (leave empty for built-in Journey to the West demo)",
  "num_scenes": 6,
  "use_llm": true,
  "fast_mode": false
}
```

### i18n

The frontend supports **Traditional Chinese** and **English**. The language preference is stored in `localStorage`. Language files live in `locales/` — PRs for additional languages are welcome.

### Roadmap

- [x] 30-second video (6 scenes)
- [x] LLaMA scene decomposition + FLUX.1 image generation
- [x] Ken Burns effect + subtitle overlay
- [x] Responsive frontend + sessionStorage API key
- [x] Multi-language UI (zh-TW / en)
- [ ] 10-minute long-form video (120 scenes)
- [ ] Background music support
- [ ] Multiple art styles (oil painting, ukiyo-e, pixel art)
- [ ] Batch generation mode
- [ ] Docker containerization

### License

This project is licensed under the [MIT License](LICENSE).

NVIDIA NIM API usage is subject to the [NVIDIA API Trial Terms of Service](https://assets.ngc.nvidia.com/products/api-catalog/legal/NVIDIA%20API%20Trial%20Terms%20of%20Service.pdf).

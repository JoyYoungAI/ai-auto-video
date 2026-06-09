# 部署指南

## 系統需求

| 項目 | 需求 |
|------|------|
| OS | Windows 10 / 11 |
| 網路 | 需連外（下載套件 + 呼叫 NVIDIA API）|
| NVIDIA API Key | 免費申請：https://build.nvidia.com |

> Python 與所有套件由 `start.bat` 自動安裝，**不需要手動安裝 Python**。

---

## 快速啟動

### 1. 取得專案

```bash
git clone https://github.com/JoyYoungAI/ai-auto-video.git
cd ai-auto-video
```

或直接下載 ZIP 解壓縮。

### 2. 啟動伺服器

雙擊 `start.bat`。

首次執行會自動：
1. 安裝 **uv**（Python 套件管理工具）
2. 下載 **Python 3.10+**
3. 安裝所有依賴套件（flask、moviepy、Pillow 等）

後續啟動直接雙擊即可，不會重複安裝。

### 3. 開啟瀏覽器

```
http://localhost:5000
```

輸入 NVIDIA API Key 後即可使用。

---

## 取得 NVIDIA API Key

1. 前往 https://build.nvidia.com
2. 註冊／登入帳號
3. 點選任一模型頁面 → **Get API Key**
4. 複製 `nvapi-` 開頭的金鑰
5. 貼入網頁介面的「NVIDIA API Key」欄位

> API Key 只存在瀏覽器的 `sessionStorage`，關閉分頁後自動清除，不會儲存到磁碟。

---

## 停止伺服器

在 `start.bat` 的終端機視窗按 `Ctrl + C`。

---

## 常見問題

### `uv sync` 失敗 / 套件安裝錯誤
確認網路正常，關掉視窗後重新雙擊 `start.bat`。

### 瀏覽器顯示「無法連線後端伺服器」
`start.bat` 尚未完成啟動，等終端機出現 `http://localhost:5000` 字樣後再重新整理。

### 影片生成失敗（API 錯誤）
- 確認 API Key 正確（`nvapi-` 開頭）
- NVIDIA 免費帳號有每日用量限制，超過後隔天重試

### 中文字幕顯示異常
Windows 內建微軟雅黑字型，正常情況下不會發生。若字幕顯示為方框，請確認系統有安裝中文字型（控制台 → 字型）。

---

## 輸出檔案位置

生成的 MP4 存放於：

```
ai-auto-video/
└── output/
    └── <job_id>/
        ├── frames/          # 各場景圖片
        └── YYYYMMDD_HHMM_<場景名>.mp4
```

伺服器重啟後仍可從網頁介面重新下載歷史影片。

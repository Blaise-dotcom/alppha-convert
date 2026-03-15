import os

# ─── Bot settings ─────────────────────────────────────────────────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
DATABASE_URL = os.getenv("DATABASE_URL", "")

# ─── Free tier limits (par jour) ──────────────────────────────────────────────
FREE_DOWNLOADS_PER_DAY = 3
FREE_COMPRESSIONS_PER_DAY = 2
FREE_MAX_FILE_SIZE_MB = 50

# ─── Premium limits ───────────────────────────────────────────────────────────
PREMIUM_MAX_FILE_SIZE_MB = 500

# ─── Pricing ──────────────────────────────────────────────────────────────────
STARS_PRICE_WEEKLY = 50      # 50 Telegram Stars
STARS_PRICE_MONTHLY = 150    # 150 Telegram Stars

TON_PRICE_WEEKLY = 0.5       # 0.5 TON
TON_PRICE_MONTHLY = 1.5      # 1.5 TON

TON_WALLET = os.getenv("TON_WALLET_ADDRESS", "TON_WALLET_ICI")

# ─── Paths ────────────────────────────────────────────────────────────────────
DOWNLOAD_PATH = "/tmp/mediabot"

# ─── Supported formats ────────────────────────────────────────────────────────
VIDEO_FORMATS = ["mp4", "mkv", "avi", "mov", "webm"]
AUDIO_FORMATS = ["mp3", "aac"]

# ─── Compression quality presets (CRF = Constant Rate Factor) ─────────────────
# Valeurs CRF : 0 = qualité max, 51 = qualité min (libx264)
QUALITY_PRESETS = {
    "ultra":  {"crf": 18, "label": "🔵 Ultra  (qualité max, fichier lourd)"},
    "high":   {"crf": 23, "label": "🟢 Haute  (très bonne qualité)"},
    "medium": {"crf": 28, "label": "🟡 Standard (bon équilibre)"},
    "low":    {"crf": 35, "label": "🟠 Léger  (fichier plus petit)"},
    "max":    {"crf": 42, "label": "🔴 Max compression (très léger)"},
}

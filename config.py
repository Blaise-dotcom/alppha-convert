import os

BOT_TOKEN    = os.getenv("BOT_TOKEN", "")
DATABASE_URL = os.getenv("DATABASE_URL", "")
PROXY_URL    = os.getenv("PROXY_URL", "")

# ─── Cookies (base64) ─────────────────────────────────────────────────────────
COOKIES_YOUTUBE   = os.getenv("COOKIES_YOUTUBE", "")
COOKIES_INSTAGRAM = os.getenv("COOKIES_INSTAGRAM", "")
COOKIES_TIKTOK    = os.getenv("COOKIES_TIKTOK", "")

# ─── RapidAPI (optionnel) ─────────────────────────────────────────────────────
_raw_keys     = os.getenv("RAPIDAPI_KEYS", os.getenv("RAPIDAPI_KEY", ""))
RAPIDAPI_KEYS = [k.strip() for k in _raw_keys.split(",") if k.strip()]

# ─── Admins ───────────────────────────────────────────────────────────────────
ADMIN_IDS: list[int] = [
    int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()
]

# ─── Limites ──────────────────────────────────────────────────────────────────
FREE_DOWNLOADS_PER_DAY    = 3
FREE_COMPRESSIONS_PER_DAY = 2
FREE_MAX_FILE_SIZE_MB     = 50
PREMIUM_MAX_FILE_SIZE_MB  = 500

# ─── Prix Premium ─────────────────────────────────────────────────────────────
# Stars
STARS_PRICE_1MONTH  = 299
STARS_PRICE_3MONTHS = 749
STARS_PRICE_6MONTHS = 1349
STARS_PRICE_1YEAR   = 2399

# TON
TON_PRICE_1MONTH  = 1.5
TON_PRICE_3MONTHS = 3.5
TON_PRICE_6MONTHS = 6.5
TON_PRICE_1YEAR   = 12.0

# USDT
USDT_PRICE_1MONTH  = 2
USDT_PRICE_3MONTHS = 5
USDT_PRICE_6MONTHS = 9
USDT_PRICE_1YEAR   = 16

# Wallet
TON_WALLET   = os.getenv("TON_WALLET_ADDRESS", "TON_WALLET_ICI")
USDT_WALLET  = os.getenv("USDT_WALLET_ADDRESS", "USDT_WALLET_ICI")

# ─── Anciens (compatibilité) ──────────────────────────────────────────────────
STARS_PRICE_WEEKLY  = 149
STARS_PRICE_MONTHLY = STARS_PRICE_1MONTH
TON_PRICE_WEEKLY    = 0.75
TON_PRICE_MONTHLY   = TON_PRICE_1MONTH

# ─── Chemins & formats ────────────────────────────────────────────────────────
DOWNLOAD_PATH = "/tmp/mediabot"
VIDEO_FORMATS = ["mp4", "mkv", "avi", "mov", "webm"]
AUDIO_FORMATS = ["mp3", "aac"]

QUALITY_PRESETS = {
    "ultra":  {"crf": 18, "label": "🔵 Ultra  (qualité max, fichier lourd)"},
    "high":   {"crf": 23, "label": "🟢 Haute  (très bonne qualité)"},
    "medium": {"crf": 28, "label": "🟡 Standard (bon équilibre)"},
    "low":    {"crf": 35, "label": "🟠 Léger  (fichier plus petit)"},
    "max":    {"crf": 42, "label": "🔴 Max compression (très léger)"},
}

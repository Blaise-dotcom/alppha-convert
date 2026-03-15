import os

# ─── Bot settings ─────────────────────────────────────────────────────────────
BOT_TOKEN    = os.getenv("BOT_TOKEN", "")
DATABASE_URL = os.getenv("DATABASE_URL", "")

# ─── Proxy (obligatoire sur Railway pour YouTube) ─────────────────────────────
# Format : "http://user:password@host:port" ou "socks5://user:pass@host:port"
# Services recommandés : Webshare.io (gratuit 10 proxies), Proxyscrape
PROXY_URL = os.getenv("PROXY_URL", "")  # laisser vide = pas de proxy

# ─── Admins ───────────────────────────────────────────────────────────────────
ADMIN_IDS: list[int] = [
    int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()
]

# ─── Free tier limits ─────────────────────────────────────────────────────────
FREE_DOWNLOADS_PER_DAY    = 3
FREE_COMPRESSIONS_PER_DAY = 2
FREE_MAX_FILE_SIZE_MB     = 50

# ─── Premium limits ───────────────────────────────────────────────────────────
PREMIUM_MAX_FILE_SIZE_MB = 500

# ─── Pricing ──────────────────────────────────────────────────────────────────
STARS_PRICE_WEEKLY  = 50
STARS_PRICE_MONTHLY = 150
TON_PRICE_WEEKLY    = 0.5
TON_PRICE_MONTHLY   = 1.5
TON_WALLET          = os.getenv("TON_WALLET_ADDRESS", "TON_WALLET_ICI")

# ─── Paths ────────────────────────────────────────────────────────────────────
DOWNLOAD_PATH = "/tmp/mediabot"

# ─── Formats & qualité ────────────────────────────────────────────────────────
VIDEO_FORMATS = ["mp4", "mkv", "avi", "mov", "webm"]
AUDIO_FORMATS = ["mp3", "aac"]

QUALITY_PRESETS = {
    "ultra":  {"crf": 18, "label": "🔵 Ultra  (qualité max, fichier lourd)"},
    "high":   {"crf": 23, "label": "🟢 Haute  (très bonne qualité)"},
    "medium": {"crf": 28, "label": "🟡 Standard (bon équilibre)"},
    "low":    {"crf": 35, "label": "🟠 Léger  (fichier plus petit)"},
    "max":    {"crf": 42, "label": "🔴 Max compression (très léger)"},
}

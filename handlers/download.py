"""
services/downloader.py — yt-dlp avec cookies (YouTube + TikTok + Instagram)
Les cookies sont stockés en base64 dans les variables d'environnement Railway.
"""
import yt_dlp, os, re, base64, logging, tempfile
from config import DOWNLOAD_PATH, PROXY_URL, COOKIES_YOUTUBE, COOKIES_INSTAGRAM, COOKIES_TIKTOK

logger = logging.getLogger(__name__)
os.makedirs(DOWNLOAD_PATH, exist_ok=True)

# ─── Écrire les cookies dans /tmp à chaque démarrage ─────────────────────────

def _write_cookie(b64_content: str, filename: str) -> str | None:
    if not b64_content:
        return None
    try:
        path = os.path.join("/tmp", filename)
        with open(path, "wb") as f:
            f.write(base64.b64decode(b64_content))
        return path
    except Exception as e:
        logger.warning(f"Cookie write failed ({filename}): {e}")
        return None

# Écrire les cookies au démarrage
_cookie_paths = {
    "youtube":   _write_cookie(COOKIES_YOUTUBE,   "yt_cookies.txt"),
    "instagram": _write_cookie(COOKIES_INSTAGRAM, "ig_cookies.txt"),
    "tiktok":    _write_cookie(COOKIES_TIKTOK,    "tt_cookies.txt"),
}

logger.info(f"Cookies chargés: { {k: bool(v) for k, v in _cookie_paths.items()} }")


# ─── Détection plateforme ─────────────────────────────────────────────────────

def detect_platform(url: str) -> str | None:
    u = url.lower()
    if "youtube.com" in u or "youtu.be" in u:
        return "youtube"
    elif "instagram.com" in u:
        return "instagram"
    elif "tiktok.com" in u or "vm.tiktok.com" in u:
        return "tiktok"
    return None


# ─── Récupérer les infos ──────────────────────────────────────────────────────

def get_video_info(url: str) -> dict:
    platform = detect_platform(url)
    cookie_file = _cookie_paths.get(platform or "")

    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extractor_args": {"youtube": {"player_client": ["android", "web"]}},
    }
    if cookie_file:
        opts["cookiefile"] = cookie_file
    if PROXY_URL:
        opts["proxy"] = PROXY_URL

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)

    return {
        "title":     info.get("title", "Vidéo"),
        "duration":  info.get("duration", 0),
        "thumbnail": info.get("thumbnail"),
        "uploader":  info.get("uploader", ""),
        "platform":  info.get("extractor_key", ""),
    }


# ─── Téléchargement ───────────────────────────────────────────────────────────

def download_media(url: str, format_type: str = "mp4", quality: str = "best") -> tuple[str | None, str]:
    platform    = detect_platform(url)
    cookie_file = _cookie_paths.get(platform or "")
    tpl         = os.path.join(DOWNLOAD_PATH, "%(id)s_%(title).60s.%(ext)s")
    downloaded  = []

    def hook(d):
        if d["status"] == "finished":
            downloaded.append(d["filename"])

    common = {
        "quiet":            True,
        "no_warnings":      True,
        "progress_hooks":   [hook],
        "outtmpl":          tpl,
        "retries":          3,
        "fragment_retries": 3,
        "extractor_args":   {"youtube": {"player_client": ["android", "web"]}},
    }
    if cookie_file:
        common["cookiefile"] = cookie_file
        logger.info(f"Utilisation cookies {platform}")
    if PROXY_URL:
        common["proxy"] = PROXY_URL

    # ── MP3 ───────────────────────────────────────────────────────────────────
    if format_type == "mp3":
        opts = {
            **common,
            "format": "bestaudio[ext=m4a]/bestaudio/best",
            "postprocessors": [{
                "key":              "FFmpegExtractAudio",
                "preferredcodec":   "mp3",
                "preferredquality": "192",
            }],
        }

    # ── MP4 ───────────────────────────────────────────────────────────────────
    else:
        qmap = {
            "best": "best[ext=mp4]/best",
            "720":  "best[height<=720][ext=mp4]/best[height<=720]",
            "480":  "best[height<=480][ext=mp4]/best[height<=480]",
            "360":  "best[height<=360][ext=mp4]/best[height<=360]",
        }
        opts = {
            **common,
            "format":              qmap.get(quality, qmap["best"]),
            "merge_output_format": "mp4",
        }

    with yt_dlp.YoutubeDL(opts) as ydl:
        info  = ydl.extract_info(url, download=True)
        title = info.get("title", "media")

    path = downloaded[-1] if downloaded else None
    if path and not os.path.exists(path):
        base = os.path.splitext(path)[0]
        for ext in [".mp3", ".mp4", ".m4a", ".webm", ".mkv"]:
            if os.path.exists(base + ext):
                return base + ext, title

    return path, title

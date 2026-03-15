"""
services/downloader.py — yt-dlp avec cookies (YouTube + TikTok + Instagram)
Les cookies sont stockés en base64 dans les variables d'environnement Railway.
"""
import yt_dlp, os, base64, logging, shutil
from config import DOWNLOAD_PATH, PROXY_URL, COOKIES_YOUTUBE, COOKIES_INSTAGRAM, COOKIES_TIKTOK

logger = logging.getLogger(__name__)
os.makedirs(DOWNLOAD_PATH, exist_ok=True)

# ─── Vérification Node.js (nécessaire pour résoudre les challenges YouTube) ───
_node = shutil.which("node")
if _node:
    logger.info(f"✅ Node.js trouvé : {_node}")
else:
    logger.warning("⚠️ Node.js introuvable — les challenges YouTube risquent d'échouer")

# ─── Écrire les cookies dans /tmp à chaque démarrage ─────────────────────────

def _write_cookie(b64_content: str, filename: str) -> str | None:
    if not b64_content:
        logger.warning(f"Cookie vide pour {filename}.")
        return None
    try:
        path = os.path.join("/tmp", filename)
        with open(path, "wb") as f:
            f.write(base64.b64decode(b64_content))
        logger.info(f"Cookie écrit : {path}")
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


# ─── Options communes ─────────────────────────────────────────────────────────

def _common_opts(platform: str | None, hook=None) -> dict:
    cookie_file = _cookie_paths.get(platform or "")

    opts = {
        "quiet":            False,
        "no_warnings":      False,
        "retries":          3,
        "fragment_retries": 3,
        # Utiliser web_creator qui ne nécessite pas de challenge JS complexe
        "extractor_args": {
            "youtube": {
                "player_client": ["web_creator", "web", "ios"],
            }
        },
    }

    if cookie_file:
        opts["cookiefile"] = cookie_file
        logger.info(f"Utilisation cookies {platform} : {cookie_file}")
    else:
        logger.warning(f"Pas de cookie pour {platform}.")

    if hook:
        opts["progress_hooks"] = [hook]

    if PROXY_URL:
        opts["proxy"] = PROXY_URL
        logger.info(f"Proxy utilisé : {PROXY_URL}")

    return opts


# ─── Récupérer les infos ──────────────────────────────────────────────────────

def get_video_info(url: str) -> dict:
    platform = detect_platform(url)
    opts = {
        **_common_opts(platform),
        "skip_download": True,
    }

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as e:
        logger.error(f"get_video_info error [{platform}] {url}: {e}")
        raise

    return {
        "title":     info.get("title", "Vidéo"),
        "duration":  info.get("duration", 0),
        "thumbnail": info.get("thumbnail"),
        "uploader":  info.get("uploader", ""),
        "platform":  info.get("extractor_key", ""),
    }


# ─── Téléchargement ───────────────────────────────────────────────────────────

def download_media(url: str, format_type: str = "mp4", quality: str = "best") -> tuple[str | None, str]:
    platform   = detect_platform(url)
    tpl        = os.path.join(DOWNLOAD_PATH, "%(id)s_%(title).60s.%(ext)s")
    downloaded = []

    logger.info(f"Début téléchargement | platform={platform} | format={format_type} | quality={quality} | url={url}")

    def hook(d):
        if d["status"] == "finished":
            downloaded.append(d["filename"])
            logger.info(f"Fichier téléchargé : {d['filename']}")
        elif d["status"] == "error":
            logger.error(f"Erreur hook yt-dlp : {d}")

    common = {
        **_common_opts(platform, hook),
        "outtmpl": tpl,
    }

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
            "best": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best",
            "720":  "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=720]+bestaudio/best",
            "480":  "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=480]+bestaudio/best",
            "360":  "bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=360]+bestaudio/best",
        }
        opts = {
            **common,
            "format":              qmap.get(quality, qmap["best"]),
            "merge_output_format": "mp4",
        }

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info  = ydl.extract_info(url, download=True)
            title = info.get("title", "media")
            logger.info(f"Extraction réussie : {title}")
    except yt_dlp.utils.DownloadError as e:
        logger.error(f"DownloadError [{platform}] format={format_type} quality={quality}: {e}")
        raise
    except Exception as e:
        logger.error(f"Erreur inattendue [{platform}] format={format_type}: {e}")
        raise

    path = downloaded[-1] if downloaded else None
    logger.info(f"Chemin brut retourné par hook : {path}")

    if path and not os.path.exists(path):
        base = os.path.splitext(path)[0]
        logger.warning(f"Fichier introuvable à {path}, recherche par extension...")
        for ext in [".mp3", ".mp4", ".m4a", ".webm", ".mkv"]:
            candidate = base + ext
            if os.path.exists(candidate):
                logger.info(f"Fichier trouvé : {candidate}")
                return candidate, title

    if not path or not os.path.exists(path):
        logger.error(f"Fichier final introuvable. downloaded={downloaded}")
        return None, title

    logger.info(f"Téléchargement terminé : {path}")
    return path, title

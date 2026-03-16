"""
services/downloader.py
"""
import yt_dlp, os, base64, logging, re
from yt_dlp.networking.impersonate import ImpersonateTarget
from config import DOWNLOAD_PATH, PROXY_URL, COOKIES_YOUTUBE, COOKIES_INSTAGRAM, COOKIES_TIKTOK

logger = logging.getLogger(__name__)
os.makedirs(DOWNLOAD_PATH, exist_ok=True)

def _write_cookie(b64_content: str, filename: str) -> str | None:
    if not b64_content:
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

_cookie_paths = {
    "youtube":   _write_cookie(COOKIES_YOUTUBE,   "yt_cookies.txt"),
    "instagram": _write_cookie(COOKIES_INSTAGRAM, "ig_cookies.txt"),
    "tiktok":    _write_cookie(COOKIES_TIKTOK,    "tt_cookies.txt"),
}

logger.info(f"Cookies chargés: { {k: bool(v) for k, v in _cookie_paths.items()} }")


def detect_platform(url: str) -> str | None:
    u = url.lower()
    if "youtube.com" in u or "youtu.be" in u:
        return "youtube"
    elif "instagram.com" in u:
        return "instagram"
    elif "tiktok.com" in u or "vm.tiktok.com" in u or "vt.tiktok.com" in u:
        return "tiktok"
    return None


def get_video_info(url: str) -> dict:
    platform = detect_platform(url)
    opts = {"quiet": True, "no_warnings": True, "skip_download": True, "extractor_args": {"youtube": {"player_client": ["android", "web"]}}}

    if platform == "instagram" and _cookie_paths.get("instagram"):
        opts["cookiefile"] = _cookie_paths["instagram"]
    if platform == "tiktok":
        opts["impersonate"] = ImpersonateTarget("chrome")
        if _cookie_paths.get("tiktok"):
            opts["cookiefile"] = _cookie_paths["tiktok"]
    if PROXY_URL:
        opts["proxy"] = PROXY_URL

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


def download_media(url: str, format_type: str = "mp4", quality: str = "720") -> tuple[str | None, str]:
    platform = detect_platform(url)
    tpl      = os.path.join(DOWNLOAD_PATH, "%(id)s_%(title).60s.%(ext)s")
    title    = "media"

    logger.info(f"Début téléchargement | platform={platform} | format={format_type} | quality={quality}")

    base_opts = {
        "outtmpl":     tpl,
        "quiet":       False,
        "no_warnings": False,
        # Fallback automatique si le format exact n'existe pas
        "ignoreerrors": False,
        "extractor_args": {"youtube": {"player_client": ["android", "web"]}},
    }

    if PROXY_URL:
        base_opts["proxy"] = PROXY_URL
    if platform == "instagram" and _cookie_paths.get("instagram"):
        base_opts["cookiefile"] = _cookie_paths["instagram"]
        logger.info("Instagram : cookies activés")
    if platform == "tiktok":
        base_opts["impersonate"] = ImpersonateTarget("chrome")
        if _cookie_paths.get("tiktok"):
            base_opts["cookiefile"] = _cookie_paths["tiktok"]
        logger.info("TikTok : impersonate chrome")
    if platform == "youtube":
        logger.info("YouTube : mode android (sans cookies)")

    # ── MP3 ───────────────────────────────────────────────────────────────────
    if format_type == "mp3":
        opts = {
            **base_opts,
            "format": "bestaudio/best",
            "postprocessors": [{
                "key":              "FFmpegExtractAudio",
                "preferredcodec":   "mp3",
                "preferredquality": "192",
            }],
        }
    # ── MP4 ───────────────────────────────────────────────────────────────────
    else:
        if platform == "instagram":
            fmt = "best[ext=mp4]/best"
        else:
            # Format avec fallbacks robustes pour chaque qualité
            # On essaie d'abord mp4 pur, puis merge, puis best disponible sous cette résolution
            qmap = {
                "1080": (
                    "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]"
                    "/bestvideo[height<=1080]+bestaudio"
                    "/best[height<=1080]"
                    "/best"
                ),
                "720": (
                    "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]"
                    "/bestvideo[height<=720]+bestaudio"
                    "/best[height<=720]"
                    "/best"
                ),
                "480": (
                    "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]"
                    "/bestvideo[height<=480]+bestaudio"
                    "/best[height<=480]"
                    "/best[height<=720]"
                    "/best"
                ),
                "360": (
                    "bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]"
                    "/bestvideo[height<=360]+bestaudio"
                    "/best[height<=360]"
                    "/best[height<=480]"
                    "/best"
                ),
            }
            fmt = qmap.get(quality, qmap["720"])

        opts = {
            **base_opts,
            "format":              fmt,
            "merge_output_format": "mp4",
        }

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info  = ydl.extract_info(url, download=True)
            title = info.get("title", "media")
            path  = ydl.prepare_filename(info)
            base  = re.sub(r'\.\w+$', '', path)
            for ext in [".mp4", ".mp3", ".mkv", ".webm", ".m4a"]:
                candidate = base + ext
                if os.path.exists(candidate):
                    logger.info(f"Téléchargement terminé : {candidate}")
                    return candidate, title
            video_id = info.get("id", "")
            if video_id:
                for f in os.listdir(DOWNLOAD_PATH):
                    if f.startswith(video_id) and not f.endswith(('.part', '.ytdl')):
                        full = os.path.join(DOWNLOAD_PATH, f)
                        logger.info(f"Fichier trouvé par ID : {full}")
                        return full, title

            logger.error(f"Fichier introuvable après téléchargement. path={path}")
            return None, title

    except yt_dlp.utils.DownloadError as e:
        logger.error(f"DownloadError [{platform}] format={format_type} quality={quality}: {e}")
        raise
    except Exception as e:
        logger.error(f"Erreur inattendue [{platform}] format={format_type}: {e}")
        raise

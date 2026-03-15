import yt_dlp
import os
import logging
from config import DOWNLOAD_PATH

logger = logging.getLogger(__name__)
os.makedirs(DOWNLOAD_PATH, exist_ok=True)


# ─── Détection de plateforme ──────────────────────────────────────────────────

def detect_platform(url: str) -> str | None:
    url = url.lower()
    if "youtube.com" in url or "youtu.be" in url:
        return "youtube"
    elif "instagram.com" in url:
        return "instagram"
    elif "tiktok.com" in url or "vm.tiktok.com" in url:
        return "tiktok"
    return None


# ─── Récupérer les infos sans télécharger ────────────────────────────────────

def get_video_info(url: str) -> dict:
    opts = {"quiet": True, "no_warnings": True, "skip_download": True}
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
    """
    Télécharge une vidéo ou audio.
    Retourne (chemin_fichier, titre)
    """
    filename_tpl = os.path.join(DOWNLOAD_PATH, "%(id)s_%(title).60s.%(ext)s")
    downloaded = []

    def progress_hook(d):
        if d["status"] == "finished":
            downloaded.append(d["filename"])

    # ── Audio ──────────────────────────────────────────────────────────────────
    if format_type == "mp3":
        opts = {
            "format":      "bestaudio/best",
            "outtmpl":     filename_tpl,
            "quiet":       True,
            "no_warnings": True,
            "postprocessors": [{
                "key":              "FFmpegExtractAudio",
                "preferredcodec":   "mp3",
                "preferredquality": "192",
            }],
            "progress_hooks": [progress_hook],
        }

    # ── Vidéo ──────────────────────────────────────────────────────────────────
    else:
        quality_map = {
            "best": "best[ext=mp4]/best",
            "720":  "best[height<=720][ext=mp4]/best[height<=720]",
            "480":  "best[height<=480][ext=mp4]/best[height<=480]",
            "360":  "best[height<=360][ext=mp4]/best[height<=360]",
        }
        opts = {
            "format":              quality_map.get(quality, quality_map["best"]),
            "outtmpl":             filename_tpl,
            "merge_output_format": "mp4",
            "quiet":               True,
            "no_warnings":         True,
            "progress_hooks":      [progress_hook],
        }

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        title = info.get("title", "media")

    # Retrouver le fichier (yt-dlp peut changer l'extension après post-process)
    path = downloaded[-1] if downloaded else None
    if path and not os.path.exists(path):
        base = os.path.splitext(path)[0]
        for ext in [".mp3", ".mp4", ".mkv", ".webm", ".m4a"]:
            candidate = base + ext
            if os.path.exists(candidate):
                path = candidate
                break

    return path, title

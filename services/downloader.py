"""
services/downloader.py
— yt-dlp prioritaire + RapidAPI fallback pour YouTube, TikTok, Instagram
"""
import yt_dlp, os, base64, logging, re, random, httpx
from yt_dlp.networking.impersonate import ImpersonateTarget
from config import DOWNLOAD_PATH, PROXY_URL, COOKIES_YOUTUBE, COOKIES_INSTAGRAM, COOKIES_TIKTOK, RAPIDAPI_KEYS

logger = logging.getLogger(__name__)
os.makedirs(DOWNLOAD_PATH, exist_ok=True)

# ── Proxies ───────────────────────────────────────────────────────────────────
_raw_proxies = os.environ.get("PROXY_URLS", PROXY_URL or "")
PROXY_LIST = [p.strip() for p in _raw_proxies.split(",") if p.strip()]
logger.info(f"Proxies: {len(PROXY_LIST)} | RapidAPI keys: {len(RAPIDAPI_KEYS)}")

def _get_proxy():
    return random.choice(PROXY_LIST) if PROXY_LIST else None

# ── RapidAPI key rotation ─────────────────────────────────────────────────────
_rapi_idx = 0
def _get_rapidapi_key():
    global _rapi_idx
    if not RAPIDAPI_KEYS:
        return None
    key = RAPIDAPI_KEYS[_rapi_idx % len(RAPIDAPI_KEYS)]
    _rapi_idx += 1
    return key

def _rapi_headers(host: str) -> dict:
    return {"X-RapidAPI-Key": _get_rapidapi_key(), "X-RapidAPI-Host": host}

# ── Cookies ───────────────────────────────────────────────────────────────────
def _write_cookie(b64: str, filename: str):
    if not b64:
        return None
    try:
        path = f"/tmp/{filename}"
        with open(path, "wb") as f:
            f.write(base64.b64decode(b64))
        return path
    except Exception as e:
        logger.warning(f"Cookie write failed: {e}")
        return None

_cookie_paths = {
    "youtube":   _write_cookie(COOKIES_YOUTUBE,   "yt_cookies.txt"),
    "instagram": _write_cookie(COOKIES_INSTAGRAM, "ig_cookies.txt"),
    "tiktok":    _write_cookie(COOKIES_TIKTOK,    "tt_cookies.txt"),
}


# ─────────────────────────────────────────────────────────────────────────────
def detect_platform(url: str) -> str | None:
    u = url.lower()
    if "youtube.com" in u or "youtu.be" in u: return "youtube"
    if "instagram.com" in u:                  return "instagram"
    if "tiktok.com" in u or "vm.tiktok" in u: return "tiktok"
    return None

def _extract_yt_id(url: str) -> str:
    m = re.search(r"(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})", url)
    return m.group(1) if m else url

def _save_stream(dl_url: str, title: str, ext: str) -> str:
    safe = re.sub(r'[^\w\-]', '_', title)[:60]
    path = os.path.join(DOWNLOAD_PATH, f"{safe}{ext}")
    with httpx.stream("GET", dl_url, timeout=120, follow_redirects=True) as r:
        r.raise_for_status()
        with open(path, "wb") as f:
            for chunk in r.iter_bytes(8192):
                f.write(chunk)
    logger.info(f"Saved: {path}")
    return path


# ─────────────────────────────────────────────────────────────────────────────
# RAPIDAPI — INFO
# ─────────────────────────────────────────────────────────────────────────────
def _rapi_info(url: str, platform: str) -> dict | None:
    key = _get_rapidapi_key()
    if not key:
        return None
    try:
        if platform == "youtube":
            r = httpx.get(
                "https://youtube-mp36.p.rapidapi.com/dl",
                params={"id": _extract_yt_id(url)},
                headers={"X-RapidAPI-Key": key, "X-RapidAPI-Host": "youtube-mp36.p.rapidapi.com"},
                timeout=15,
            )
            if r.status_code == 200:
                d = r.json()
                return {"title": d.get("title", "Vidéo"), "duration": int(d.get("duration", 0) or 0),
                        "thumbnail": None, "uploader": "YouTube", "platform": "youtube"}

        elif platform == "tiktok":
            r = httpx.get(
                "https://tiktok-scraper7.p.rapidapi.com/video/info",
                params={"url": url, "hd": "1"},
                headers={"X-RapidAPI-Key": key, "X-RapidAPI-Host": "tiktok-scraper7.p.rapidapi.com"},
                timeout=15,
            )
            if r.status_code == 200:
                d = r.json().get("data", {})
                return {"title": d.get("title", "Vidéo TikTok"), "duration": d.get("duration", 0),
                        "thumbnail": d.get("cover"), "uploader": d.get("author", {}).get("nickname", "TikTok"),
                        "platform": "tiktok"}

        elif platform == "instagram":
            # Essai 1 : instagram-post-reels-stories-downloader-api
            ig_apis = [
                ("https://instagram-post-reels-stories-downloader-api.p.rapidapi.com/api",
                 "instagram-post-reels-stories-downloader-api.p.rapidapi.com"),
                ("https://instagram-reels-downloader-api.p.rapidapi.com/downloadReel",
                 "instagram-reels-downloader-api.p.rapidapi.com"),
            ]
            for endpoint, host in ig_apis:
                try:
                    r = httpx.get(endpoint, params={"url": url},
                                  headers={"X-RapidAPI-Key": key, "X-RapidAPI-Host": host}, timeout=15)
                    logger.info(f"IG info [{host}]: {r.status_code} | {r.text[:100]}")
                    if r.status_code == 200:
                        d = r.json()
                        items = d.get("result", d.get("media", []))
                        thumb = next((m.get("thumb") or m.get("thumbnail") for m in items if "video" in m.get("type","")), None)
                        return {"title": "Video Instagram", "duration": 0,
                                "thumbnail": thumb, "uploader": "Instagram", "platform": "instagram"}
                except Exception as ex:
                    logger.warning(f"IG info [{host}]: {ex}")

    except Exception as e:
        logger.warning(f"RapidAPI info [{platform}]: {e}")
    return None


# ─────────────────────────────────────────────────────────────────────────────
# RAPIDAPI — DOWNLOAD
# ─────────────────────────────────────────────────────────────────────────────
def _rapi_download(url: str, platform: str, format_type: str) -> tuple[str | None, str]:
    key = _get_rapidapi_key()
    if not key:
        return None, "media"
    try:
        # ── YouTube MP3 ───────────────────────────────────────────────────────
        if platform == "youtube" and format_type == "mp3":
            r = httpx.get(
                "https://youtube-mp36.p.rapidapi.com/dl",
                params={"id": _extract_yt_id(url)},
                headers={"X-RapidAPI-Key": key, "X-RapidAPI-Host": "youtube-mp36.p.rapidapi.com"},
                timeout=30,
            )
            if r.status_code == 200:
                d = r.json()
                if d.get("link"):
                    return _save_stream(d["link"], d.get("title", "audio"), ".mp3"), d.get("title", "audio")

        # ── YouTube MP4 ───────────────────────────────────────────────────────
        elif platform == "youtube":
            # Essai 1 : ytjar (youtube-mp36 host)
            r = httpx.get(
                "https://youtube-mp36.p.rapidapi.com/dl",
                params={"id": _extract_yt_id(url), "format": "mp4"},
                headers={"X-RapidAPI-Key": key, "X-RapidAPI-Host": "youtube-mp36.p.rapidapi.com"},
                timeout=30,
            )
            if r.status_code == 200:
                d = r.json()
                dl_url = d.get("link") or d.get("url")
                if dl_url:
                    return _save_stream(dl_url, d.get("title", "video"), ".mp4"), d.get("title", "video")

            # Essai 2 : yt-api
            r2 = httpx.get(
                "https://yt-api.p.rapidapi.com/dl",
                params={"id": _extract_yt_id(url), "cgeo": "US"},
                headers={"X-RapidAPI-Key": key, "X-RapidAPI-Host": "yt-api.p.rapidapi.com"},
                timeout=30,
            )
            if r2.status_code == 200:
                d2 = r2.json()
                # Trouver le meilleur format mp4
                formats = d2.get("adaptiveFormats", []) + d2.get("formats", [])
                mp4s = [f for f in formats if f.get("mimeType", "").startswith("video/mp4")]
                if mp4s:
                    best = sorted(mp4s, key=lambda x: x.get("height", 0), reverse=True)[0]
                    dl_url = best.get("url")
                    title = d2.get("title", "video")
                    if dl_url:
                        return _save_stream(dl_url, title, ".mp4"), title

        # ── TikTok ────────────────────────────────────────────────────────────
        elif platform == "tiktok":
            r = httpx.get(
                "https://tiktok-scraper7.p.rapidapi.com/video/info",
                params={"url": url, "hd": "1"},
                headers={"X-RapidAPI-Key": key, "X-RapidAPI-Host": "tiktok-scraper7.p.rapidapi.com"},
                timeout=30,
            )
            if r.status_code == 200:
                d = r.json().get("data", {})
                title = d.get("title", "tiktok")
                dl_url = d.get("hdplay") or d.get("play") or d.get("wmplay")
                if dl_url:
                    ext = ".mp4"
                    if format_type == "mp3":
                        # Extraire l'audio via music
                        dl_url = d.get("music_info", {}).get("play") or dl_url
                        ext = ".mp3"
                    return _save_stream(dl_url, title, ext), title

        # ── Instagram ─────────────────────────────────────────────────────────
        elif platform == "instagram":
            ig_apis = [
                ("https://instagram-post-reels-stories-downloader-api.p.rapidapi.com/api",
                 "instagram-post-reels-stories-downloader-api.p.rapidapi.com"),
                ("https://instagram-reels-downloader-api.p.rapidapi.com/downloadReel",
                 "instagram-reels-downloader-api.p.rapidapi.com"),
            ]
            for endpoint, host in ig_apis:
                try:
                    r = httpx.get(endpoint, params={"url": url},
                                  headers={"X-RapidAPI-Key": key, "X-RapidAPI-Host": host}, timeout=30)
                    logger.info(f"IG dl [{host}]: {r.status_code} | {r.text[:200]}")
                    if r.status_code == 200:
                        d = r.json()
                        items = d.get("result", d.get("media", []))
                        video_url = None
                        for item in items:
                            if "video" in item.get("type", ""):
                                video_url = item.get("url")
                                break
                        if not video_url and items:
                            video_url = items[0].get("url")
                        if video_url:
                            ext = ".mp3" if format_type == "mp3" else ".mp4"
                            return _save_stream(video_url, "instagram_video", ext), "Instagram"
                except Exception as ex:
                    logger.error(f"IG dl [{host}]: {ex}")

    except Exception as e:
        logger.error(f"RapidAPI download [{platform}]: {e}")
    return None, "media"


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────────────────────────────────────
def get_video_info(url: str) -> dict:
    platform = detect_platform(url)
    opts = {"quiet": True, "no_warnings": True, "skip_download": True}

    if platform == "instagram":
        opts["impersonate"] = ImpersonateTarget("chrome", "131")
        proxy = _get_proxy()
        if proxy: opts["proxy"] = proxy
        if _cookie_paths.get("instagram"): opts["cookiefile"] = _cookie_paths["instagram"]
    elif platform == "tiktok":
        opts["impersonate"] = ImpersonateTarget("chrome")
        proxy = _get_proxy()
        if proxy: opts["proxy"] = proxy
    elif PROXY_LIST:
        opts["proxy"] = _get_proxy()

    # Tentative yt-dlp
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
        return {"title": info.get("title", "Vidéo"), "duration": info.get("duration", 0),
                "thumbnail": info.get("thumbnail"), "uploader": info.get("uploader", ""),
                "platform": platform}
    except Exception as e:
        logger.warning(f"yt-dlp info [{platform}] failed: {e} → RapidAPI")

    # Fallback RapidAPI
    result = _rapi_info(url, platform)
    if result:
        logger.info(f"RapidAPI info OK [{platform}]")
        return result

    raise RuntimeError(f"Impossible de récupérer les infos pour {url}")


def download_media(url: str, format_type: str = "mp4", quality: str = "720") -> tuple[str | None, str]:
    platform = detect_platform(url)
    tpl = os.path.join(DOWNLOAD_PATH, "%(id)s_%(title).60s.%(ext)s")
    logger.info(f"Download | platform={platform} | format={format_type} | quality={quality}")

    base_opts = {"outtmpl": tpl, "quiet": False, "no_warnings": False, "ignoreerrors": False}

    if platform == "instagram":
        base_opts["impersonate"] = ImpersonateTarget("chrome", "131")
        proxy = _get_proxy()
        if proxy: base_opts["proxy"] = proxy
        if _cookie_paths.get("instagram"): base_opts["cookiefile"] = _cookie_paths["instagram"]
    elif platform == "tiktok":
        base_opts["impersonate"] = ImpersonateTarget("chrome")
        proxy = _get_proxy()
        if proxy: base_opts["proxy"] = proxy
        if _cookie_paths.get("tiktok"): base_opts["cookiefile"] = _cookie_paths["tiktok"]
    elif platform == "youtube" and PROXY_LIST:
        base_opts["proxy"] = _get_proxy()

    if format_type == "mp3":
        opts = {**base_opts, "format": "bestaudio/best",
                "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}]}
    else:
        qmap = {
            "1080": "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
            "720":  "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=720]+bestaudio/best[height<=720]/best",
            "480":  "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=480]+bestaudio/best[height<=480]/best",
            "360":  "bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=360]+bestaudio/best[height<=360]/best",
        }
        fmt = "best[ext=mp4]/best" if platform == "instagram" else qmap.get(quality, qmap["720"])
        opts = {**base_opts, "format": fmt, "merge_output_format": "mp4"}

    # Tentative yt-dlp
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info  = ydl.extract_info(url, download=True)
            title = info.get("title", "media")
            path  = ydl.prepare_filename(info)
            base  = re.sub(r'\.\w+$', '', path)
            for ext in [".mp4", ".mp3", ".mkv", ".webm", ".m4a"]:
                if os.path.exists(base + ext):
                    logger.info(f"yt-dlp OK: {base + ext}")
                    return base + ext, title
            vid = info.get("id", "")
            if vid:
                for f in os.listdir(DOWNLOAD_PATH):
                    if f.startswith(vid) and not f.endswith(('.part', '.ytdl')):
                        full = os.path.join(DOWNLOAD_PATH, f)
                        logger.info(f"yt-dlp OK (ID): {full}")
                        return full, title
    except Exception as e:
        logger.warning(f"yt-dlp download [{platform}] failed: {e} → RapidAPI")

    # Fallback RapidAPI
    logger.info(f"RapidAPI fallback [{platform}]")
    path, title = _rapi_download(url, platform, format_type)
    if path and os.path.exists(path):
        logger.info(f"RapidAPI OK: {path}")
        return path, title

    logger.error(f"Echec total [{platform}] {url}")
    return None, "media"

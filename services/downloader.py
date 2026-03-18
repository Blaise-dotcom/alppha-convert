"""
services/downloader.py
— yt-dlp + bgutil POToken (YouTube) + RapidAPI fallback YouTube/TikTok/Instagram
"""
import yt_dlp, os, base64, logging, re, random, httpx, urllib.parse
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

# ── URL Cleaning ──────────────────────────────────────────────────────────────
def clean_url(url: str) -> str:
    try:
        url = url.strip()
        parsed = urllib.parse.urlparse(url)
        params = urllib.parse.parse_qs(parsed.query)
        if "youtube.com" in parsed.netloc or "youtu.be" in parsed.netloc:
            clean_params = {k: v for k, v in params.items() if k == "v"}
            new_query = urllib.parse.urlencode(clean_params, doseq=True)
            return parsed._replace(query=new_query).geturl()
        if "tiktok.com" in parsed.netloc or "vm.tiktok" in parsed.netloc:
            return parsed._replace(query="", fragment="").geturl()
    except Exception:
        pass
    return url.strip()

# ── Platform detection ────────────────────────────────────────────────────────
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
    with httpx.stream("GET", dl_url, timeout=120, follow_redirects=True,
                      headers={"User-Agent": "Mozilla/5.0"}) as r:
        r.raise_for_status()
        with open(path, "wb") as f:
            for chunk in r.iter_bytes(8192):
                f.write(chunk)
    logger.info(f"Saved: {path}")
    return path

# ── bgutil POToken fetch ──────────────────────────────────────────────────────
_pot_cache: dict = {"token": None, "visitor_data": None}

def _fetch_pot(video_id: str = "dQw4w9WgXcQ") -> tuple[str | None, str | None]:
    """Fetch a fresh POToken from the local bgutil server (port 4416)."""
    try:
        r = httpx.post(
            "http://localhost:4416/token",
            json={"videoId": video_id},
            timeout=15,
        )
        if r.status_code == 200:
            d = r.json()
            token = d.get("poToken") or d.get("pot") or d.get("token")
            visitor = d.get("visitorData") or d.get("visitor_data")
            if token:
                logger.info(f"POToken fetched from bgutil OK")
                _pot_cache["token"] = token
                _pot_cache["visitor_data"] = visitor
                return token, visitor
    except Exception as e:
        logger.warning(f"bgutil POToken fetch failed: {e}")
    return _pot_cache.get("token"), _pot_cache.get("visitor_data")


# ── yt-dlp opts YouTube avec bgutil POToken ───────────────────────────────────
def _yt_opts(extra: dict = None, video_id: str = "dQw4w9WgXcQ") -> dict:
    pot, visitor_data = _fetch_pot(video_id)

    yt_args: dict = {"player_client": ["web"]}
    if pot:
        yt_args["po_token"] = [f"web+{pot}"]
    if visitor_data:
        yt_args["visitor_data"] = [visitor_data]

    opts = {
        "quiet": True,
        "no_warnings": True,
        "extractor_args": {"youtube": yt_args},
    }
    if _cookie_paths.get("youtube"):
        opts["cookiefile"] = _cookie_paths["youtube"]
    if extra:
        opts.update(extra)
    return opts

# ── yt-dlp opts TikTok ────────────────────────────────────────────────────────
def _tt_opts(extra: dict = None) -> dict:
    opts = {"quiet": True, "no_warnings": True,
            "impersonate": ImpersonateTarget("chrome")}
    proxy = _get_proxy()
    if proxy:
        opts["proxy"] = proxy
    if _cookie_paths.get("tiktok"):
        opts["cookiefile"] = _cookie_paths["tiktok"]
    if extra:
        opts.update(extra)
    return opts

# ── yt-dlp opts Instagram ─────────────────────────────────────────────────────
def _ig_opts(extra: dict = None) -> dict:
    opts = {"quiet": True, "no_warnings": True,
            "impersonate": ImpersonateTarget("chrome", "131")}
    proxy = _get_proxy()
    if proxy:
        opts["proxy"] = proxy
    if _cookie_paths.get("instagram"):
        opts["cookiefile"] = _cookie_paths["instagram"]
    if extra:
        opts.update(extra)
    return opts

# ── RapidAPI helpers ──────────────────────────────────────────────────────────
def _rapi_info(url: str, platform: str) -> dict | None:
    key = _get_rapidapi_key()
    if not key:
        return None
    try:
        if platform == "youtube":
            r = httpx.get("https://youtube-mp36.p.rapidapi.com/dl",
                params={"id": _extract_yt_id(url)},
                headers={"X-RapidAPI-Key": key, "X-RapidAPI-Host": "youtube-mp36.p.rapidapi.com"},
                timeout=15)
            if r.status_code == 200:
                d = r.json()
                return {"title": d.get("title", "YouTube"), "duration": int(d.get("duration", 0) or 0),
                        "thumbnail": None, "uploader": "YouTube", "platform": "youtube"}

        elif platform == "tiktok":
            r = httpx.get("https://tiktok-scraper7.p.rapidapi.com/video/info",
                params={"url": url, "hd": "1"},
                headers={"X-RapidAPI-Key": key, "X-RapidAPI-Host": "tiktok-scraper7.p.rapidapi.com"},
                timeout=15)
            if r.status_code == 200:
                d = r.json().get("data", {})
                return {"title": d.get("title", "TikTok"), "duration": d.get("duration", 0),
                        "thumbnail": d.get("cover"), "uploader": d.get("author", {}).get("nickname", "TikTok"),
                        "platform": "tiktok"}

        elif platform == "instagram":
            r = httpx.get("https://instagram120.p.rapidapi.com/api/instagram/hls",
                params={"url": url},
                headers={"X-RapidAPI-Key": key, "X-RapidAPI-Host": "instagram120.p.rapidapi.com"},
                timeout=15)
            logger.info(f"Instagram120 hls info: {r.status_code} | {r.text[:200]}")
            if r.status_code == 200:
                return {"title": "Video Instagram", "duration": 0,
                        "thumbnail": None, "uploader": "Instagram", "platform": "instagram"}

    except Exception as e:
        logger.warning(f"RapidAPI info [{platform}]: {e}")
    return None


def _rapi_download(url: str, platform: str, format_type: str) -> tuple[str | None, str]:
    key = _get_rapidapi_key()
    if not key:
        return None, "media"
    try:
        if platform == "youtube" and format_type == "mp3":
            r = httpx.get("https://youtube-mp36.p.rapidapi.com/dl",
                params={"id": _extract_yt_id(url)},
                headers={"X-RapidAPI-Key": key, "X-RapidAPI-Host": "youtube-mp36.p.rapidapi.com"},
                timeout=30)
            if r.status_code == 200:
                d = r.json()
                if d.get("link"):
                    return _save_stream(d["link"], d.get("title", "audio"), ".mp3"), d.get("title", "audio")

        elif platform == "youtube":
            r = httpx.get("https://yt-api.p.rapidapi.com/dl",
                params={"id": _extract_yt_id(url), "cgeo": "US"},
                headers={"X-RapidAPI-Key": key, "X-RapidAPI-Host": "yt-api.p.rapidapi.com"},
                timeout=30)
            if r.status_code == 200:
                d = r.json()
                formats = d.get("adaptiveFormats", []) + d.get("formats", [])
                mp4s = [f for f in formats if f.get("mimeType", "").startswith("video/mp4")]
                if mp4s:
                    best = sorted(mp4s, key=lambda x: x.get("height", 0), reverse=True)[0]
                    if best.get("url"):
                        return _save_stream(best["url"], d.get("title", "video"), ".mp4"), d.get("title", "video")

        elif platform == "tiktok":
            r = httpx.get("https://tiktok-scraper7.p.rapidapi.com/video/info",
                params={"url": url, "hd": "1"},
                headers={"X-RapidAPI-Key": key, "X-RapidAPI-Host": "tiktok-scraper7.p.rapidapi.com"},
                timeout=30)
            if r.status_code == 200:
                d = r.json().get("data", {})
                title = d.get("title", "tiktok")
                dl_url = d.get("hdplay") or d.get("play") or d.get("wmplay")
                if format_type == "mp3":
                    dl_url = d.get("music_info", {}).get("play") or dl_url
                if dl_url:
                    ext = ".mp3" if format_type == "mp3" else ".mp4"
                    return _save_stream(dl_url, title, ext), title

        elif platform == "instagram":
            r = httpx.get("https://instagram120.p.rapidapi.com/api/instagram/hls",
                params={"url": url},
                headers={"X-RapidAPI-Key": key, "X-RapidAPI-Host": "instagram120.p.rapidapi.com"},
                timeout=30)
            logger.info(f"Instagram120 hls dl: {r.status_code} | {r.text[:300]}")
            if r.status_code == 200:
                d = r.json()
                def _find_video(obj):
                    if isinstance(obj, dict):
                        for k, v in obj.items():
                            if k in ("video_url", "url", "src", "link") and isinstance(v, str) and "http" in v:
                                return v
                            if k == "video_versions" and isinstance(v, list) and v:
                                return v[0].get("url")
                            r2 = _find_video(v)
                            if r2: return r2
                    elif isinstance(obj, list):
                        for item in obj:
                            r2 = _find_video(item)
                            if r2: return r2
                    return None
                video_url = _find_video(d)
                if video_url:
                    ext = ".mp3" if format_type == "mp3" else ".mp4"
                    return _save_stream(video_url, "instagram_video", ext), "Instagram"

    except Exception as e:
        logger.error(f"RapidAPI download [{platform}]: {e}")
    return None, "media"


# ── Public API ────────────────────────────────────────────────────────────────
def get_video_info(url: str) -> dict:
    url = clean_url(url)
    platform = detect_platform(url)

    if platform == "youtube":
        vid_id = _extract_yt_id(url)
        opts = _yt_opts({"skip_download": True}, video_id=vid_id)
    elif platform == "tiktok":
        opts = _tt_opts({"skip_download": True})
    else:
        opts = _ig_opts({"skip_download": True})

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
        return {"title": info.get("title", "Vidéo"), "duration": info.get("duration", 0),
                "thumbnail": info.get("thumbnail"), "uploader": info.get("uploader", ""),
                "platform": platform}
    except Exception as e:
        logger.warning(f"yt-dlp info [{platform}] failed: {e} → RapidAPI")

    result = _rapi_info(url, platform)
    if result:
        logger.info(f"RapidAPI info OK [{platform}]")
        return result

    raise RuntimeError(f"Impossible de récupérer les infos pour {url}")


def download_media(url: str, format_type: str = "mp4", quality: str = "720") -> tuple[str | None, str]:
    url = clean_url(url)
    platform = detect_platform(url)
    tpl = os.path.join(DOWNLOAD_PATH, "%(id)s_%(title).60s.%(ext)s")
    logger.info(f"Download | platform={platform} | format={format_type} | quality={quality}")

    if format_type == "mp3":
        fmt_opts = {
            "format": "bestaudio/best",
            "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}],
        }
    else:
        qmap = {
            "1080": "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080]/best",
            "720":  "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720]/best",
            "480":  "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480]/best",
            "360":  "bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/best[height<=360]/best",
        }
        fmt = "best[ext=mp4]/best" if platform == "instagram" else qmap.get(quality, qmap["720"])
        fmt_opts = {"format": fmt, "merge_output_format": "mp4"}

    extra = {"outtmpl": tpl, "quiet": False, "no_warnings": False, **fmt_opts}

    if platform == "youtube":
        vid_id = _extract_yt_id(url)
        opts = _yt_opts(extra, video_id=vid_id)
    elif platform == "tiktok":
        opts = _tt_opts(extra)
    else:
        opts = _ig_opts(extra)

    # Tentative yt-dlp
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get("title", "media")
            path = ydl.prepare_filename(info)
            base = re.sub(r'\.\w+$', '', path)
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
        logger.warning(f"yt-dlp [{platform}] failed: {e} → RapidAPI")

    # Fallback RapidAPI
    logger.info(f"RapidAPI fallback [{platform}]")
    path, title = _rapi_download(url, platform, format_type)
    if path and os.path.exists(path):
        logger.info(f"RapidAPI OK: {path}")
        return path, title

    logger.error(f"Echec total [{platform}] {url}")
    return None, "media"

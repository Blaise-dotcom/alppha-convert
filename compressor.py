import subprocess
import os
import uuid
import json
import logging
from config import QUALITY_PRESETS, DOWNLOAD_PATH

logger = logging.getLogger(__name__)
os.makedirs(DOWNLOAD_PATH, exist_ok=True)


# ─── Info sur une vidéo ───────────────────────────────────────────────────────

def get_file_info(path: str) -> dict:
    cmd = [
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_format", "-show_streams",
        path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    data = json.loads(result.stdout)
    fmt = data.get("format", {})
    return {
        "duration": float(fmt.get("duration", 0)),
        "size_mb":  int(fmt.get("size", 0)) / (1024 * 1024),
        "bitrate":  int(fmt.get("bit_rate", 0)),
    }


# ─── Compression / Conversion ─────────────────────────────────────────────────

def compress_video(input_path: str, output_format: str = "mp4", quality_preset: str = "medium") -> str:
    """
    Compresse et/ou convertit une vidéo.
    Retourne le chemin du fichier de sortie.
    """
    crf = QUALITY_PRESETS.get(quality_preset, QUALITY_PRESETS["medium"])["crf"]
    output_name = f"{uuid.uuid4().hex}.{output_format}"
    output_path = os.path.join(DOWNLOAD_PATH, output_name)

    # ── MP4 / MKV / AVI / MOV → libx264 ──────────────────────────────────────
    if output_format in ["mp4", "mkv", "avi", "mov"]:
        cmd = [
            "ffmpeg", "-i", input_path,
            "-c:v", "libx264",
            "-crf", str(crf),
            "-preset", "fast",
            "-c:a", "aac",
            "-b:a", "128k",
            "-movflags", "+faststart",   # streaming-friendly pour mp4
            "-y", output_path,
        ]

    # ── WebM → VP9 ────────────────────────────────────────────────────────────
    elif output_format == "webm":
        cmd = [
            "ffmpeg", "-i", input_path,
            "-c:v", "libvpx-vp9",
            "-crf", str(crf),
            "-b:v", "0",
            "-c:a", "libopus",
            "-b:a", "96k",
            "-y", output_path,
        ]

    # ── MP3 ───────────────────────────────────────────────────────────────────
    elif output_format == "mp3":
        bitrate_map = {
            "ultra": "320k", "high": "192k",
            "medium": "128k", "low": "96k", "max": "64k",
        }
        bitrate = bitrate_map.get(quality_preset, "128k")
        cmd = [
            "ffmpeg", "-i", input_path,
            "-vn",
            "-c:a", "libmp3lame",
            "-b:a", bitrate,
            "-y", output_path,
        ]

    # ── AAC ───────────────────────────────────────────────────────────────────
    elif output_format == "aac":
        cmd = [
            "ffmpeg", "-i", input_path,
            "-vn",
            "-c:a", "aac",
            "-b:a", "128k",
            "-y", output_path,
        ]

    else:
        raise ValueError(f"Format non supporté : {output_format}")

    logger.info(f"FFmpeg : {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        logger.error(f"FFmpeg stderr: {result.stderr}")
        raise RuntimeError(f"Erreur ffmpeg : {result.stderr[-300:]}")

    return output_path

"""
Configuration and constants for SMS Media Converter.
"""
from dataclasses import dataclass, field
from typing import Optional, List, Dict

LABEL_HARDWARE_CONFIRMED = "Hardware-confirmed on real PS2 hardware"
LABEL_CUSTOM_PROFILE = "SMS-compatible specification; performance not hardware-confirmed"

# Resolution Limits for SMS
MAX_WIDTH = 1024
MAX_HEIGHT = 1024
RECOMMENDED_MAX_WIDTH = 640
RECOMMENDED_MAX_HEIGHT = 480

WARNING_RESOLUTION_MSG = (
    "This resolution satisfies the SMS format limit but may not maintain full-speed playback on PS2 hardware."
)

# File Size Limits (Bytes)
SIZE_3_8_GIB = int(3.8 * 1024 * 1024 * 1024)
SIZE_4_0_GIB = int(4.0 * 1024 * 1024 * 1024) - (10 * 1024 * 1024) # ~3.99 GiB limit

MSG_FILE_SIZE_APPROACHING_LIMIT = (
    "Conversion stopped because the output was approaching the SMS 32-bit file-size limit. "
    "Reduce the bitrate, resolution, or duration, or enable automatic splitting."
)

# Packet Size Validation Thresholds (Bytes)
MAX_VIDEO_PACKET_SIZE = 2_097_088  # 2 MiB
MAX_AUDIO_PACKET_SIZE = 524_224   # 512 KiB

# Stream Limits
MAX_SMS_STREAMS = 8

# Allowed Frame Rates for MPEG-1 and MPEG-2
MPEG_ALLOWED_FPS_MAP: Dict[str, str] = {
    "23.976": "24000/1001",
    "24": "24/1",
    "25": "25/1",
    "29.97": "30000/1001",
    "30": "30/1",
    "50": "50/1",
    "59.94": "60000/1001",
    "60": "60/1"
}

@dataclass
class Preset:
    name: str
    vcodec: Optional[str]  # e.g., 'mpeg4', 'mpeg2video', 'mpeg1video', None for audio only
    vtag: Optional[str]    # e.g., 'XVID'
    width: Optional[int]
    height: Optional[int]
    fps: Optional[str]     # e.g., '30'
    vbitrate_kbps: Optional[int]
    acodec: str           # e.g., 'libmp3lame', 'mp2', 'aac'
    abitrate_kbps: int    # e.g., 128, 192
    sample_rate: int = 48000
    channels: int = 2
    ext: str = ".avi"
    is_hardware_confirmed: bool = True

PRESETS: Dict[str, Preset] = {
    "Xvid-Compatible AVI — Recommended": Preset(
        name="Xvid-Compatible AVI — Recommended",
        vcodec="mpeg4",
        vtag="XVID",
        width=640,
        height=480,
        fps="30",
        vbitrate_kbps=1500,
        acodec="libmp3lame",
        abitrate_kbps=128,
        sample_rate=48000,
        channels=2,
        ext=".avi",
        is_hardware_confirmed=True
    ),
    "MPEG-2 — High Compatibility": Preset(
        name="MPEG-2 — High Compatibility",
        vcodec="mpeg2video",
        vtag=None,
        width=640,
        height=480,
        fps="30",
        vbitrate_kbps=2500,
        acodec="mp2",
        abitrate_kbps=192,
        sample_rate=48000,
        channels=2,
        ext=".mpg",
        is_hardware_confirmed=True
    ),
    "MPEG-1 — Maximum Compatibility": Preset(
        name="MPEG-1 — Maximum Compatibility",
        vcodec="mpeg1video",
        vtag=None,
        width=640,
        height=480,
        fps="30",
        vbitrate_kbps=1150,
        acodec="mp2",
        abitrate_kbps=192,
        sample_rate=48000,
        channels=2,
        ext=".mpg",
        is_hardware_confirmed=True
    ),
    "MPEG-4 MP4 — Recommended": Preset(
        name="MPEG-4 MP4 — Recommended",
        vcodec="mpeg4",
        vtag=None,
        width=640,
        height=480,
        fps="30",
        vbitrate_kbps=1500,
        acodec="aac",
        abitrate_kbps=128,
        sample_rate=48000,
        channels=2,
        ext=".mp4",
        is_hardware_confirmed=True
    ),
    "MPEG-4 MP4 — Small": Preset(
        name="MPEG-4 MP4 — Small",
        vcodec="mpeg4",
        vtag=None,
        width=320,
        height=240,
        fps="30",
        vbitrate_kbps=600,
        acodec="aac",
        abitrate_kbps=128,
        sample_rate=48000,
        channels=2,
        ext=".mp4",
        is_hardware_confirmed=True
    ),
    "AAC Audio Only": Preset(
        name="AAC Audio Only",
        vcodec=None,
        vtag=None,
        width=None,
        height=None,
        fps=None,
        vbitrate_kbps=None,
        acodec="aac",
        abitrate_kbps=128,
        sample_rate=48000,
        channels=2,
        ext=".m4a",
        is_hardware_confirmed=True
    ),
}

VIDEO_CODECS_MAP = {
    "MPEG-1": "mpeg1video",
    "MPEG-2": "mpeg2video",
    "MPEG-4 Part 2": "mpeg4",
    "Xvid-compatible MPEG-4": "mpeg4",
    "Microsoft MPEG-4 v3": "msmpeg4v3",
    "Actual libxvid": "libxvid",
}

AUDIO_CODECS_MAP = {
    "AAC-LC": "aac",
    "MP2": "mp2",
    "MP3": "libmp3lame",
    "AC-3": "ac3",
    "Ogg Vorbis": "libvorbis",
    "FLAC": "flac",
    "WMA v1": "wmav1",
    "WMA v2": "wmav2",
}

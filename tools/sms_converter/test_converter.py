"""
Unit and integration tests for SMS Media Converter core utilities and validator.
"""
import unittest
import os
import sys
from pathlib import Path

# Add sms_converter to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import (
    PRESETS, MAX_WIDTH, MAX_HEIGHT, SIZE_4_0_GIB, MAX_VIDEO_PACKET_SIZE,
    MAX_AUDIO_PACKET_SIZE, MPEG_ALLOWED_FPS_MAP
)
from ffmpeg_utils import (
    find_ffmpeg_binaries, check_libxvid_support, get_media_info,
    parse_media_summary, calculate_estimated_output_size, build_ffmpeg_cmd,
    generate_unique_output_path
)
from validator import validate_converted_file

class TestSMSConverter(unittest.TestCase):

    def test_binary_detection(self):
        ff, fp = find_ffmpeg_binaries()
        self.assertIsNotNone(ff, "FFmpeg binary should be found on system PATH or app dir")
        self.assertIsNotNone(fp, "ffprobe binary should be found on system PATH or app dir")
        print(f"[TEST] FFmpeg found: {ff}")
        print(f"[TEST] ffprobe found: {fp}")

    def test_presets(self):
        self.assertIn("Xvid-Compatible AVI — Recommended", PRESETS)
        self.assertIn("MPEG-2 — High Compatibility", PRESETS)
        self.assertIn("MPEG-1 — Maximum Compatibility", PRESETS)
        self.assertIn("MPEG-4 MP4 — Recommended", PRESETS)
        self.assertIn("MPEG-4 MP4 — Small", PRESETS)
        self.assertIn("AAC Audio Only", PRESETS)

        xvid_preset = PRESETS["Xvid-Compatible AVI — Recommended"]
        self.assertEqual(xvid_preset.vtag, "XVID")
        self.assertEqual(xvid_preset.width, 640)
        self.assertEqual(xvid_preset.height, 480)

    def test_fps_mapping(self):
        self.assertEqual(MPEG_ALLOWED_FPS_MAP["23.976"], "24000/1001")
        self.assertEqual(MPEG_ALLOWED_FPS_MAP["29.97"], "30000/1001")
        self.assertEqual(MPEG_ALLOWED_FPS_MAP["59.94"], "60000/1001")

    def test_estimated_size_calculation(self):
        # 10 minutes (600s), 1500 kbps video + 128 kbps audio
        est_bytes = calculate_estimated_output_size(600, 1500, 128)
        # Expected: ~124.5 MB
        self.assertGreater(est_bytes, 100 * 1024 * 1024)
        self.assertLess(est_bytes, 150 * 1024 * 1024)

    def test_output_path_generation(self):
        source = "sample_movie.mp4"
        final_p, partial_p = generate_unique_output_path(source, ".avi")
        self.assertTrue(final_p.endswith("sample_movie_SMS.avi"))
        self.assertTrue(partial_p.endswith("sample_movie_SMS.avi.partial"))

    def test_cmd_building(self):
        ff, _ = find_ffmpeg_binaries()
        settings = {
            "vcodec": "mpeg4",
            "vtag": "XVID",
            "width": 640,
            "height": 480,
            "fps": "30",
            "vbitrate_kbps": 1500,
            "acodec": "libmp3lame",
            "abitrate_kbps": 128,
            "sample_rate": 48000,
            "channels": 2,
            "scaling_mode": "Letterbox to exact dimensions",
            "limit_streams": True
        }
        cmd = build_ffmpeg_cmd(ff, "input.mp4", "output.avi.partial", settings)

        self.assertIn("-c:v", cmd)
        self.assertIn("mpeg4", cmd)
        self.assertIn("-vtag", cmd)
        self.assertIn("XVID", cmd)
        self.assertIn("-map", cmd)
        self.assertIn("0:v:0?", cmd)
        self.assertIn("0:a:0?", cmd)
        self.assertIn("-sn", cmd)
        self.assertIn("-progress", cmd)

if __name__ == "__main__":
    unittest.main()

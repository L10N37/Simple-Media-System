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

    def test_presets(self):
        self.assertTrue(any("Xvid-Compatible AVI" in k for k in PRESETS.keys()))
        self.assertTrue(any("MPEG-2" in k for k in PRESETS.keys()))
        self.assertTrue(any("MPEG-1" in k for k in PRESETS.keys()))
        self.assertTrue(any("MPEG-4 MP4" in k for k in PRESETS.keys()))

        xvid_preset = PRESETS["Xvid-Compatible AVI [RECOMMENDED - Best PS2 Performance]"]
        self.assertEqual(xvid_preset.vtag, "XVID")
        self.assertEqual(xvid_preset.width, 640)
        self.assertEqual(xvid_preset.height, 480)

    def test_fps_mapping(self):
        self.assertEqual(MPEG_ALLOWED_FPS_MAP["23.976"], "24000/1001")
        self.assertEqual(MPEG_ALLOWED_FPS_MAP["29.97"], "30000/1001")
        self.assertEqual(MPEG_ALLOWED_FPS_MAP["59.94"], "60000/1001")

    def test_estimated_size_calculation(self):
        est_bytes = calculate_estimated_output_size(600, 1500, 128)
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
        # Either encoder is correct here: both produce MPEG-4 Part 2 that SMS decodes, and
        # which one is chosen depends on whether THIS ffmpeg build has libxvid (real Xvid is
        # preferred when present -- measurably better at the same bitrate). Asserting one
        # specific name would make the suite fail on half the machines it runs on.
        self.assertTrue(
            "mpeg4" in cmd or "libxvid" in cmd,
            f"expected an MPEG-4 Part 2 encoder, got: {cmd}",
        )
        self.assertIn("-vtag", cmd)
        self.assertIn("XVID", cmd)
        self.assertIn("-map", cmd)
        self.assertIn("0:v:0?", cmd)
        self.assertIn("0:a:0?", cmd)
        self.assertIn("-sn", cmd)
        self.assertIn("-progress", cmd)

    def test_vtag_is_avi_only(self):
        """An AVI FourCC must never reach a non-AVI container.

        This is a REGRESSION TEST for a bug that broke every .mp4 conversion for as long as
        the MP4 presets existed, on every platform, and reported only "Failed". Two entries
        in VIDEO_CODECS_MAP map to "mpeg4", so the advanced-settings panel matched the Xvid
        one for any mpeg4 preset; vtag is recovered from that combo's TEXT, so the .mp4
        presets came back carrying vtag="XVID". ffmpeg then got
        `-c:v libxvid -vtag XVID ... -f mp4` and aborted while writing the header:
        "Could not find tag for codec mpeg4 in stream #0, codec not currently supported in
        container".

        Asserted at the command builder because that is the layer that knows the container,
        and it is the layer that has to stay right however the settings were assembled.
        """
        ff, _ = find_ffmpeg_binaries()
        polluted = {
            "vcodec": "mpeg4", "vtag": "XVID", "width": 640, "height": 480, "fps": "30",
            "vbitrate_kbps": 1500, "acodec": "aac", "abitrate_kbps": 128,
            "sample_rate": 48000, "channels": 2, "limit_streams": True,
        }

        mp4 = build_ffmpeg_cmd(ff, "input.avi", "output.mp4.partial", polluted)
        self.assertNotIn("-vtag", mp4, f"AVI FourCC leaked into an MP4: {mp4}")
        self.assertIn("mp4", mp4)

        # ...while the AVI path, which is the proven one, keeps it.
        avi = build_ffmpeg_cmd(ff, "input.avi", "output.avi.partial", polluted)
        self.assertIn("-vtag", avi)
        self.assertIn("XVID", avi)

        # And no shipped preset may produce the bad pairing on its own.
        for name, preset in PRESETS.items():
            if not preset.vcodec:
                continue
            s = dict(polluted, vcodec=preset.vcodec, vtag=preset.vtag, acodec=preset.acodec)
            c = build_ffmpeg_cmd(ff, "input.avi", f"output{preset.ext}.partial", s)
            if preset.ext != ".avi":
                self.assertNotIn("-vtag", c, f"preset '{name}' emits a vtag into {preset.ext}")

class TestPresetRoundTrip(unittest.TestCase):
    """Every preset must survive a trip through the settings widget unchanged.

    TWO shipped bugs came from reading the model back out of a display widget, and both were
    invisible until someone tried a conversion:

    1. Two VIDEO_CODECS_MAP keys map to "mpeg4", so the video combo always landed on the Xvid
       one and vtag was recovered from its TEXT -- every .mp4 preset came back as vtag="XVID"
       and ffmpeg refused the container ("Tag XVID incompatible with output codec id '12'").
    2. Audio-only presets park that same hidden combo at index 0, which IS the Xvid entry, so
       they came back claiming vcodec="mpeg4". MP3 and Ogg then failed outright, and the AAC
       .m4a preset silently wrote a VIDEO STREAM into an audio file -- exit 0, no error shown.

    Asserting the round-trip catches the whole class, including the next display name someone
    adds that happens to collide with an existing one.
    """

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from qt_compat import QtWidgets
        cls._app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_presets_round_trip_through_the_widget(self):
        from ui.advanced_settings import AdvancedSettingsWidget

        w = AdvancedSettingsWidget()
        for name, preset in PRESETS.items():
            with self.subTest(preset=name):
                w.load_preset(preset)
                got = w.get_settings_dict()
                self.assertEqual(got.get("vcodec"), preset.vcodec, f"vcodec changed for '{name}'")
                self.assertEqual(got.get("vtag"), preset.vtag, f"vtag changed for '{name}'")

    def test_audio_presets_never_encode_video(self):
        from ui.advanced_settings import AdvancedSettingsWidget

        ff, _ = find_ffmpeg_binaries()
        w = AdvancedSettingsWidget()
        for name, preset in PRESETS.items():
            if preset.vcodec is not None:
                continue
            with self.subTest(preset=name):
                w.load_preset(preset)
                # has_video_stream=True is the case that broke: an audio preset applied to a
                # source that HAS video. It must drop the video, not try to encode it.
                cmd = build_ffmpeg_cmd(
                    ff, "input.avi", f"output{preset.ext}.partial",
                    w.get_settings_dict(), has_video_stream=True,
                )
                self.assertIn("-vn", cmd, f"audio preset '{name}' does not drop video: {cmd}")
                self.assertNotIn("-c:v", cmd, f"audio preset '{name}' encodes video: {cmd}")

class TestQtCompatShim(unittest.TestCase):
    """Guard the Qt binding shim.

    The Windows 7 build routes every Qt import through qt_compat, so a name the shim
    forgets to re-export is not a lint nit -- the app dies at import on BOTH bindings.
    That is exactly what happened: QMenu and QTabWidget were missed, and nothing caught
    it because the suite never imported the UI modules. It does now.
    """

    def test_every_imported_name_is_exported(self):
        import io
        import os
        import re
        import qt_compat

        base = os.path.dirname(os.path.abspath(__file__))
        wanted = set()
        for root, _dirs, names in os.walk(base):
            if "__pycache__" in root:
                continue
            for n in names:
                if not n.endswith(".py") or n == "qt_compat.py":
                    continue
                src = io.open(os.path.join(root, n), encoding="utf-8").read()
                for m in re.finditer(
                    r"from qt_compat import \(([^)]*)\)|from qt_compat import ([^\(\n]+)", src
                ):
                    body = m.group(1) or m.group(2)
                    for tok in body.replace("\n", " ").split(","):
                        tok = tok.strip()
                        # Identifiers only: this scan reads THIS file too, and the regex
                        # literal just above would otherwise be collected as a "name".
                        if tok.isidentifier():
                            wanted.add(tok)

        self.assertTrue(wanted, "found no qt_compat imports -- the scan is broken")
        missing = sorted(w for w in wanted if not hasattr(qt_compat, w))
        self.assertEqual(missing, [], f"qt_compat is missing re-exports: {missing}")

    def test_ui_modules_actually_import(self):
        """Import every UI module. A missing shim export only shows up here."""
        import importlib

        for mod in (
            "ui.main_window", "ui.queue_table", "ui.preset_selector",
            "ui.drop_zone", "ui.advanced_settings", "ui.details_dialog",
            "ui.setup_dialog",
        ):
            with self.subTest(module=mod):
                importlib.import_module(mod)


if __name__ == "__main__":
    unittest.main()

"""
Collapsible advanced video and audio settings panel with hints and tooltips.
"""
from typing import Dict, Any
from qt_compat import Qt, Signal
from qt_compat import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QGroupBox, QFormLayout,
    QComboBox, QSpinBox, QCheckBox, QLabel, QFrame, QScrollArea
)

from config import (
    VIDEO_CODECS_MAP, AUDIO_CODECS_MAP, MPEG_ALLOWED_FPS_MAP,
    MAX_WIDTH, MAX_HEIGHT, WARNING_RESOLUTION_MSG, Preset
)

class AdvancedSettingsWidget(QWidget):
    settings_changed = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_custom_mode = False

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 5, 0, 5)

        # 1. Toggle Button
        self.btn_toggle = QPushButton("[ Advanced Settings ▼ ]")
        self.btn_toggle.setCheckable(True)
        self.btn_toggle.setChecked(False)
        self.btn_toggle.setCursor(Qt.PointingHandCursor)
        self.btn_toggle.setToolTip("Click to expand or collapse fine-grained custom video and audio encoding options.")
        self.btn_toggle.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #63B3ED;
                border: none;
                text-align: left;
                font-weight: bold;
                padding: 4px 0px;
            }
            QPushButton:hover {
                color: #90CDF4;
            }
        """)
        self.btn_toggle.clicked.connect(self._toggle_collapse)

        # 2. Collapsible Container
        self.container = QFrame()
        self.container.setFrameShape(QFrame.StyledPanel)
        self.container.setStyleSheet("""
            QFrame {
                background-color: #2D3748;
                border-radius: 6px;
                border: 1px solid #4A5568;
            }
            QGroupBox {
                color: #E2E8F0;
                font-weight: bold;
                border: 1px solid #4A5568;
                border-radius: 4px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
            QLabel {
                color: #CBD5E0;
            }
        """)
        # visibility is owned by self.scroll ( created below ); the container itself stays shown

        container_layout = QHBoxLayout(self.container)

        # --- Video Group ---
        grp_video = QGroupBox("Video Settings")
        self.grp_video = grp_video
        v_layout = QFormLayout(grp_video)

        self.combo_vcodec = QComboBox()
        self.combo_vcodec.setToolTip(
            "Select output video codec supported natively by SMS on PS2:\n"
            "• Xvid-compatible MPEG-4 (Recommended): Best performance and compatibility.\n"
            "• MPEG-2 Video: Standard DVD video stream format.\n"
            "• MPEG-1 Video: VCD video format with minimal CPU load."
        )
        for k in VIDEO_CODECS_MAP.keys():
            self.combo_vcodec.addItem(k)
        self.combo_vcodec.currentIndexChanged.connect(self._on_control_changed)

        self.spin_width = QSpinBox()
        self.spin_width.setRange(2, MAX_WIDTH)
        self.spin_width.setSingleStep(2)
        self.spin_width.setValue(640)
        self.spin_width.setToolTip("Target width in pixels (max 1024). Standard PS2 resolution is 640. Automatically rounded to even numbers.")
        self.spin_width.valueChanged.connect(self._on_resolution_changed)

        self.spin_height = QSpinBox()
        self.spin_height.setRange(2, MAX_HEIGHT)
        self.spin_height.setSingleStep(2)
        self.spin_height.setValue(480)
        self.spin_height.setToolTip("Target height in pixels (max 1024). Standard PS2 resolution is 480. Automatically rounded to even numbers.")
        self.spin_height.valueChanged.connect(self._on_resolution_changed)

        res_layout = QHBoxLayout()
        res_layout.addWidget(self.spin_width)
        res_layout.addWidget(QLabel("×"))
        res_layout.addWidget(self.spin_height)

        self.chk_aspect = QCheckBox("Preserve aspect ratio (Recommended)")
        self.chk_aspect.setChecked(True)
        self.chk_aspect.setToolTip("Preserves original video proportions by applying black letterbox bars when scaling.")
        self.chk_aspect.stateChanged.connect(self._on_control_changed)

        self.combo_scaling = QComboBox()
        self.combo_scaling.setToolTip(
            "Choose scaling mode:\n"
            "• Letterbox to exact dimensions (Recommended): Pad black bars to fit target resolution.\n"
            "• Fit inside dimensions: Scale down without adding black bars.\n"
            "• Crop to fill: Scale up and crop edges to fill entire screen.\n"
            "• Stretch: Force stretch image to target resolution."
        )
        self.combo_scaling.addItems([
            "Letterbox to exact dimensions",
            "Fit inside dimensions",
            "Crop to fill",
            "Stretch"
        ])
        self.combo_scaling.currentIndexChanged.connect(self._on_control_changed)

        self.chk_upscale = QCheckBox("Allow upscaling (default off)")
        self.chk_upscale.setChecked(False)
        self.chk_upscale.setToolTip("Disabled by default. Upscaling low-res video increases file size without improving quality.")
        self.chk_upscale.stateChanged.connect(self._on_control_changed)

        self.combo_fps = QComboBox()
        self.combo_fps.setToolTip("Target video frame rate. 30 FPS or 24 FPS recommended for PS2 hardware. Restricted for MPEG-1/2.")
        for fps_val in MPEG_ALLOWED_FPS_MAP.keys():
            self.combo_fps.addItem(fps_val)
        self.combo_fps.setCurrentText("30")
        self.combo_fps.currentIndexChanged.connect(self._on_control_changed)

        self.spin_vbitrate = QSpinBox()
        self.spin_vbitrate.setRange(100, 10000)
        self.spin_vbitrate.setSingleStep(100)
        self.spin_vbitrate.setSuffix(" kbps")
        self.spin_vbitrate.setValue(1500)
        self.spin_vbitrate.setToolTip("Target video bitrate. 1500 kbps (1.5 Mbps) recommended for smooth USB 1.1 / SMB network playback.")
        self.spin_vbitrate.valueChanged.connect(self._on_control_changed)

        self.chk_deinterlace = QCheckBox("Deinterlace video")
        self.chk_deinterlace.setChecked(False)
        self.chk_deinterlace.setToolTip("Converts interlaced video to progressive frames. Recommended for TV rips or DVD source material.")
        self.chk_deinterlace.stateChanged.connect(self._on_control_changed)

        self.spin_gop = QSpinBox()
        self.spin_gop.setRange(1, 600)
        self.spin_gop.setValue(50)
        self.spin_gop.setSuffix(" frames")
        self.spin_gop.setToolTip(
            "Keyframe interval (GOP size): how often a complete, self-contained frame is "
            "written. Everything between keyframes is stored as differences.\n\n"
            "This is what decides how fast SEEKING feels on the PS2. Jumping to any point "
            "means decoding forward from the previous keyframe, so at 25 fps an interval of "
            "300 can mean chewing through 12 seconds of video before playback resumes -- on a "
            "294 MHz CPU that is a long stare at a frozen screen.\n\n"
            "Measured on a 640x480 test clip at a fixed 1000 kbps: going from 300 down to 50 "
            "cost about 0.4% in file size and actually scored slightly BETTER quality, while "
            "cutting worst-case seek work from 12 seconds to 2.\n\n"
            "50 (about 2 seconds) is a good balance. Raise it toward 300 if you only ever "
            "watch straight through and want every last byte; lower it if you scrub a lot."
        )
        self.spin_gop.valueChanged.connect(self._on_control_changed)

        self.spin_bframes = QSpinBox()
        self.spin_bframes.setRange(0, 4)
        self.spin_bframes.setValue(0)
        self.spin_bframes.setToolTip(
            "B-frames: extra frames predicted from BOTH the previous and the next frame. They "
            "shrink the file a little but cost decoding work and add latency.\n\n"
            "NOT the same thing as the keyframe interval -- that is the 'Keyframe interval' "
            "box above. B-frames is 0-4; the keyframe interval is in the hundreds.\n\n"
            "Recommended: 0. The PS2 decodes MPEG-4 in software, and B-frames are the first "
            "thing to cost it frames."
        )
        self.spin_bframes.valueChanged.connect(self._on_control_changed)

        self.chk_qpel = QCheckBox("QPel (Quarter-Pixel, default off)")
        self.chk_qpel.setChecked(False)
        self.chk_qpel.setToolTip("Quarter-Pixel motion estimation. Recommended: OFF for PS2 hardware decoding compatibility.")
        self.chk_qpel.stateChanged.connect(self._on_control_changed)

        # --- Multi-pass encoding -------------------------------------------------------
        self.chk_two_pass = QCheckBox("Multi-pass encoding (better quality, takes twice as long)")
        self.chk_two_pass.setChecked(False)
        self.chk_two_pass.setToolTip(
            "Encodes the video twice: the first run measures the material, the second uses "
            "what it learned to spend the bitrate where it is actually needed.\n\n"
            "Worth it because these presets aim at a FIXED bitrate. A single pass has to guess "
            "while it is still reading the file, so it commonly overshoots -- measured on a "
            "test clip asking for 500 kbps, one pass produced 689 and two produced 516.\n\n"
            "On a PS2 an overshoot is not just a larger file: it is dropped frames over USB or "
            "a network share. Cost is roughly double the conversion time."
        )
        self.chk_two_pass.stateChanged.connect(self._on_two_pass_toggled)

        self.spin_passes = QSpinBox()
        self.spin_passes.setRange(2, 2)
        self.spin_passes.setValue(2)
        self.spin_passes.setEnabled(False)
        self.spin_passes.setToolTip(
            "Number of passes.\n\n"
            "Fixed at 2 -- a limitation of FFMPEG, not of the codec.\n\n"
            "MPEG-4 Part 2 (DivX / Xvid) itself supports as many passes as you like, and the "
            "commercial DivX encoder does exactly that. But this app encodes through ffmpeg, "
            "and ffmpeg's pass 2 never writes back to the statistics log -- verified: the log "
            "is byte-for-byte identical before and after it runs. With nothing new written, a "
            "third pass has nothing to refine.\n\n"
            "Worse, ffmpeg treats -pass as a bitmask, so asking for 3 means pass 1 AND pass 2 "
            "together and the encoder falls back to first-pass behaviour. Measured at a 700 "
            "kbps target: pass 1 gave 5022 kbps, pass 2 gave 712, pass 3 gave 5022 again -- "
            "seven times over target, which on a PS2 means dropped frames.\n\n"
            "So 2 is what is achievable here, not what the format is capable of."
        )

        self.chk_gmc = QCheckBox("GMC (Global Motion Comp, default off)")
        self.chk_gmc.setChecked(False)
        self.chk_gmc.setToolTip("Global Motion Compensation. Recommended: OFF for PS2 hardware decoding compatibility.")
        self.chk_gmc.stateChanged.connect(self._on_control_changed)

        v_layout.addRow("Codec:", self.combo_vcodec)
        v_layout.addRow("Dimensions:", res_layout)
        v_layout.addRow("", self.chk_aspect)
        v_layout.addRow("Scaling Mode:", self.combo_scaling)
        v_layout.addRow("", self.chk_upscale)
        v_layout.addRow("Frame Rate:", self.combo_fps)
        v_layout.addRow("Video Bitrate:", self.spin_vbitrate)
        v_layout.addRow("", self.chk_deinterlace)
        v_layout.addRow("Keyframe interval:", self.spin_gop)
        v_layout.addRow("B-Frames (not keyframes):", self.spin_bframes)
        v_layout.addRow("", self.chk_two_pass)
        v_layout.addRow("Passes:", self.spin_passes)
        v_layout.addRow("", self.chk_qpel)
        v_layout.addRow("", self.chk_gmc)

        # --- Audio Group ---
        grp_audio = QGroupBox("Audio Settings")
        a_layout = QFormLayout(grp_audio)

        self.combo_acodec = QComboBox()
        self.combo_acodec.setToolTip(
            "Select output audio codec supported natively by SMS:\n"
            "• MP3 (Recommended for AVI): Broadest playback support.\n"
            "• AAC-LC (Recommended for MP4): High quality audio at lower bitrates.\n"
            "• MP2: Standard for MPEG-1/2 streams."
        )
        for k in AUDIO_CODECS_MAP.keys():
            self.combo_acodec.addItem(k)
        self.combo_acodec.currentIndexChanged.connect(self._on_control_changed)

        self.combo_abitrate = QComboBox()
        self.combo_abitrate.setToolTip("Target audio bitrate. 128 kbps recommended for MP3/AAC, 192 kbps for MP2.")
        for b in [64, 96, 128, 160, 192, 256, 320]:
            label = f"{b} kbps (Recommended)" if b == 128 else f"{b} kbps"
            self.combo_abitrate.addItem(label, b)
        self.combo_abitrate.setCurrentIndex(2) # 128 kbps
        self.combo_abitrate.currentIndexChanged.connect(self._on_control_changed)

        self.combo_sample = QComboBox()
        self.combo_sample.setToolTip("Audio sampling rate. 48000 Hz (48 kHz) is the hardware recommended baseline for PS2 audio output.")
        for sr in [48000, 44100, 32000, 22050]:
            label = f"{sr} Hz (Recommended)" if sr == 48000 else f"{sr} Hz"
            self.combo_sample.addItem(label, sr)
        self.combo_sample.setCurrentIndex(0) # 48000 Hz
        self.combo_sample.currentIndexChanged.connect(self._on_control_changed)

        self.combo_channels = QComboBox()
        self.combo_channels.setToolTip("Audio channel layout. Stereo (2 ch) recommended for PlayStation 2.")
        self.combo_channels.addItem("Stereo (2 ch) — Recommended", 2)
        self.combo_channels.addItem("Mono (1 ch)", 1)
        self.combo_channels.currentIndexChanged.connect(self._on_control_changed)

        self.chk_normalize = QCheckBox("Normalize audio (Loudnorm)")
        self.chk_normalize.setChecked(False)
        self.chk_normalize.setToolTip("Applies EBU R128 audio normalization filter to equalize volume levels between quiet and loud scenes.")
        self.chk_normalize.stateChanged.connect(self._on_control_changed)

        a_layout.addRow("Codec:", self.combo_acodec)
        a_layout.addRow("Bitrate:", self.combo_abitrate)
        a_layout.addRow("Sample Rate:", self.combo_sample)
        a_layout.addRow("Channels:", self.combo_channels)
        a_layout.addRow("", self.chk_normalize)

        container_layout.addWidget(grp_video)
        container_layout.addWidget(grp_audio)

        # Warning label for custom resolution
        self.label_res_warning = QLabel(WARNING_RESOLUTION_MSG)
        self.label_res_warning.setStyleSheet("color: #ED8936; font-size: 11px; font-style: italic;")
        self.label_res_warning.setWordWrap(True)
        self.label_res_warning.hide()

        main_layout.addWidget(self.btn_toggle)

        # The settings container goes inside a scroll area rather than straight into the
        # layout. Added directly, its full sizeHint height became part of the WINDOW's
        # minimum: expanded, the window could not be smaller than 958px tall, while a
        # 1366x768 laptop has roughly 728px of usable height -- so the Convert button sat
        # below the bottom of the screen and the window could not be shrunk to reach it,
        # because that was a floor and not a preference.
        # Wrapped, the panel keeps its natural size when there is room and scrolls when there
        # is not, which is the behaviour a settings panel should have had anyway.
        self.scroll = QScrollArea()
        self.scroll.setWidget(self.container)
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setVisible(False)
        main_layout.addWidget(self.scroll)
        main_layout.addWidget(self.label_res_warning)

    def load_preset(self, preset: Preset):
        """Populates control values from preset data."""
        self._block_signals(True)
        if preset.vcodec is None:
            # Audio-only preset: hide the entire Video Settings group, not just neutralise the
            # codec combo. Eleven video controls that cannot affect the output were still
            # taking their full width and height, which is a quarter of the presets paying a
            # ~170px penalty for dead controls -- and that height is what pushes the expanded
            # window past the bottom of a 1366x768 screen.
            self.grp_video.setVisible(False)
            # Multi-pass analyses VIDEO; with no video track there is nothing for it to do.
            self.chk_two_pass.setChecked(False)
            self.combo_vcodec.setCurrentIndex(0)
        else:
            self.grp_video.setVisible(True)
            for display_name, ff_name in VIDEO_CODECS_MAP.items():
                if ff_name == preset.vcodec:
                    if preset.vtag == "XVID":
                        self.combo_vcodec.setCurrentText("Xvid-compatible MPEG-4 (Recommended)")
                    else:
                        self.combo_vcodec.setCurrentText(display_name)
                    break

        if preset.width:
            self.spin_width.setValue(preset.width)
        if preset.height:
            self.spin_height.setValue(preset.height)
        if preset.fps:
            self.combo_fps.setCurrentText(str(preset.fps))
        if preset.vbitrate_kbps:
            self.spin_vbitrate.setValue(preset.vbitrate_kbps)

        for display_name, ff_name in AUDIO_CODECS_MAP.items():
            if ff_name == preset.acodec:
                self.combo_acodec.setCurrentText(display_name)
                break

        # Match abitrate
        for i in range(self.combo_abitrate.count()):
            if self.combo_abitrate.itemData(i) == preset.abitrate_kbps:
                self.combo_abitrate.setCurrentIndex(i)
                break

        # Match sample rate
        for i in range(self.combo_sample.count()):
            if self.combo_sample.itemData(i) == preset.sample_rate:
                self.combo_sample.setCurrentIndex(i)
                break

        self.combo_channels.setCurrentIndex(0 if preset.channels == 2 else 1)

        self.spin_bframes.setValue(0)
        self.chk_qpel.setChecked(False)
        self.chk_gmc.setChecked(False)
        self.chk_deinterlace.setChecked(False)
        self.chk_normalize.setChecked(False)

        self._block_signals(False)
        self._check_resolution_warning()

    def get_settings_dict(self) -> Dict[str, Any]:
        vcodec_display = self.combo_vcodec.currentText()
        ff_vcodec = VIDEO_CODECS_MAP.get(vcodec_display, "mpeg4")
        vtag = "XVID" if "Xvid-compatible" in vcodec_display else None

        acodec_display = self.combo_acodec.currentText()
        ff_acodec = AUDIO_CODECS_MAP.get(acodec_display, "aac")

        w = self.spin_width.value()
        h = self.spin_height.value()
        if w % 2 != 0:
            w -= 1
        if h % 2 != 0:
            h -= 1

        return {
            "vcodec": ff_vcodec,
            "vtag": vtag,
            "width": w,
            "height": h,
            "preserve_aspect": self.chk_aspect.isChecked(),
            "scaling_mode": self.combo_scaling.currentText(),
            "allow_upscale": self.chk_upscale.isChecked(),
            "fps": self.combo_fps.currentText(),
            "vbitrate_kbps": self.spin_vbitrate.value(),
            "deinterlace": self.chk_deinterlace.isChecked(),
            "bframes": self.spin_bframes.value(),
            "gop": self.spin_gop.value(),
            "two_pass": self.chk_two_pass.isChecked(),
            "passes": self.spin_passes.value() if self.chk_two_pass.isChecked() else 1,
            "qpel": self.chk_qpel.isChecked(),
            "gmc": self.chk_gmc.isChecked(),
            "acodec": ff_acodec,
            "abitrate_kbps": self.combo_abitrate.currentData(),
            "sample_rate": self.combo_sample.currentData(),
            "channels": self.combo_channels.currentData(),
            "normalize_audio": self.chk_normalize.isChecked(),
            "limit_streams": True
        }

    def _on_two_pass_toggled(self):
        """The pass count is only meaningful when multi-pass is on."""
        self.spin_passes.setEnabled(self.chk_two_pass.isChecked())
        self._on_control_changed()

    def _toggle_collapse(self):
        # Toggle the SCROLL AREA, not the container: the container now lives inside it, so
        # hiding the container alone would leave an empty scroll frame occupying the space.
        if self.btn_toggle.isChecked():
            self.btn_toggle.setText("[ Advanced Settings ▲ ]")
            self.scroll.show()
        else:
            self.btn_toggle.setText("[ Advanced Settings ▼ ]")
            self.scroll.hide()

    def _on_resolution_changed(self):
        w = self.spin_width.value()
        h = self.spin_height.value()
        if w % 2 != 0:
            self.spin_width.setValue(w - 1)
        if h % 2 != 0:
            self.spin_height.setValue(h - 1)
        self._check_resolution_warning()
        self._on_control_changed()

    def _check_resolution_warning(self):
        w = self.spin_width.value()
        h = self.spin_height.value()
        if w > 640 or h > 480:
            self.label_res_warning.show()
        else:
            self.label_res_warning.hide()

    def _on_control_changed(self):
        self.settings_changed.emit(self.get_settings_dict())

    def _block_signals(self, block: bool):
        self.combo_vcodec.blockSignals(block)
        self.spin_width.blockSignals(block)
        self.spin_height.blockSignals(block)
        self.chk_aspect.blockSignals(block)
        self.combo_scaling.blockSignals(block)
        self.chk_upscale.blockSignals(block)
        self.combo_fps.blockSignals(block)
        self.spin_vbitrate.blockSignals(block)
        self.chk_deinterlace.blockSignals(block)
        self.spin_bframes.blockSignals(block)
        self.chk_qpel.blockSignals(block)
        self.chk_gmc.blockSignals(block)
        self.combo_acodec.blockSignals(block)
        self.combo_abitrate.blockSignals(block)
        self.combo_sample.blockSignals(block)
        self.combo_channels.blockSignals(block)
        self.chk_normalize.blockSignals(block)

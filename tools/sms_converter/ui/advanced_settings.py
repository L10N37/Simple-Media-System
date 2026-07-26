"""
Collapsible advanced video and audio settings panel.
"""
from typing import Dict, Any
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QGroupBox, QFormLayout,
    QComboBox, QSpinBox, QCheckBox, QLabel, QFrame
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
        self.btn_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
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
        self.container.setFrameShape(QFrame.Shape.StyledPanel)
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
        self.container.hide()

        container_layout = QHBoxLayout(self.container)

        # --- Video Group ---
        grp_video = QGroupBox("Video Settings")
        v_layout = QFormLayout(grp_video)

        self.combo_vcodec = QComboBox()
        for k in VIDEO_CODECS_MAP.keys():
            self.combo_vcodec.addItem(k)
        self.combo_vcodec.currentIndexChanged.connect(self._on_control_changed)

        self.spin_width = QSpinBox()
        self.spin_width.setRange(2, MAX_WIDTH)
        self.spin_width.setSingleStep(2)
        self.spin_width.setValue(640)
        self.spin_width.valueChanged.connect(self._on_resolution_changed)

        self.spin_height = QSpinBox()
        self.spin_height.setRange(2, MAX_HEIGHT)
        self.spin_height.setSingleStep(2)
        self.spin_height.setValue(480)
        self.spin_height.valueChanged.connect(self._on_resolution_changed)

        res_layout = QHBoxLayout()
        res_layout.addWidget(self.spin_width)
        res_layout.addWidget(QLabel("×"))
        res_layout.addWidget(self.spin_height)

        self.chk_aspect = QCheckBox("Preserve aspect ratio")
        self.chk_aspect.setChecked(True)
        self.chk_aspect.stateChanged.connect(self._on_control_changed)

        self.combo_scaling = QComboBox()
        self.combo_scaling.addItems([
            "Letterbox to exact dimensions",
            "Fit inside dimensions",
            "Crop to fill",
            "Stretch"
        ])
        self.combo_scaling.currentIndexChanged.connect(self._on_control_changed)

        self.chk_upscale = QCheckBox("Allow upscaling (default off)")
        self.chk_upscale.setChecked(False)
        self.chk_upscale.stateChanged.connect(self._on_control_changed)

        self.combo_fps = QComboBox()
        for fps_val in MPEG_ALLOWED_FPS_MAP.keys():
            self.combo_fps.addItem(fps_val)
        self.combo_fps.setCurrentText("30")
        self.combo_fps.currentIndexChanged.connect(self._on_control_changed)

        self.spin_vbitrate = QSpinBox()
        self.spin_vbitrate.setRange(100, 10000)
        self.spin_vbitrate.setSingleStep(100)
        self.spin_vbitrate.setSuffix(" kbps")
        self.spin_vbitrate.setValue(1500)
        self.spin_vbitrate.valueChanged.connect(self._on_control_changed)

        self.chk_deinterlace = QCheckBox("Deinterlace video")
        self.chk_deinterlace.setChecked(False)
        self.chk_deinterlace.stateChanged.connect(self._on_control_changed)

        self.spin_bframes = QSpinBox()
        self.spin_bframes.setRange(0, 4)
        self.spin_bframes.setValue(0)
        self.spin_bframes.valueChanged.connect(self._on_control_changed)

        self.chk_qpel = QCheckBox("QPel (Quarter-Pixel, default off)")
        self.chk_qpel.setChecked(False)
        self.chk_qpel.stateChanged.connect(self._on_control_changed)

        self.chk_gmc = QCheckBox("GMC (Global Motion Comp, default off)")
        self.chk_gmc.setChecked(False)
        self.chk_gmc.stateChanged.connect(self._on_control_changed)

        v_layout.addRow("Codec:", self.combo_vcodec)
        v_layout.addRow("Dimensions:", res_layout)
        v_layout.addRow("", self.chk_aspect)
        v_layout.addRow("Scaling Mode:", self.combo_scaling)
        v_layout.addRow("", self.chk_upscale)
        v_layout.addRow("Frame Rate:", self.combo_fps)
        v_layout.addRow("Video Bitrate:", self.spin_vbitrate)
        v_layout.addRow("", self.chk_deinterlace)
        v_layout.addRow("B-Frames:", self.spin_bframes)
        v_layout.addRow("", self.chk_qpel)
        v_layout.addRow("", self.chk_gmc)

        # --- Audio Group ---
        grp_audio = QGroupBox("Audio Settings")
        a_layout = QFormLayout(grp_audio)

        self.combo_acodec = QComboBox()
        for k in AUDIO_CODECS_MAP.keys():
            self.combo_acodec.addItem(k)
        self.combo_acodec.currentIndexChanged.connect(self._on_control_changed)

        self.combo_abitrate = QComboBox()
        for b in [64, 96, 128, 160, 192, 256, 320]:
            self.combo_abitrate.addItem(f"{b} kbps", b)
        self.combo_abitrate.setCurrentText("128 kbps")
        self.combo_abitrate.currentIndexChanged.connect(self._on_control_changed)

        self.combo_sample = QComboBox()
        for sr in [48000, 44100, 32000, 22050]:
            self.combo_sample.addItem(f"{sr} Hz", sr)
        self.combo_sample.setCurrentText("48000 Hz")
        self.combo_sample.currentIndexChanged.connect(self._on_control_changed)

        self.combo_channels = QComboBox()
        self.combo_channels.addItem("Stereo (2 ch)", 2)
        self.combo_channels.addItem("Mono (1 ch)", 1)
        self.combo_channels.currentIndexChanged.connect(self._on_control_changed)

        self.chk_normalize = QCheckBox("Normalize audio (Loudnorm)")
        self.chk_normalize.setChecked(False)
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
        main_layout.addWidget(self.container)
        main_layout.addWidget(self.label_res_warning)

    def load_preset(self, preset: Preset):
        """Populates control values from preset data."""
        self._block_signals(True)
        if preset.vcodec is None:
            # Audio only
            self.combo_vcodec.setCurrentText("MPEG-4 Part 2")
        else:
            for display_name, ff_name in VIDEO_CODECS_MAP.items():
                if ff_name == preset.vcodec:
                    if preset.vtag == "XVID":
                        self.combo_vcodec.setCurrentText("Xvid-compatible MPEG-4")
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

        self.combo_abitrate.setCurrentText(f"{preset.abitrate_kbps} kbps")
        self.combo_sample.setCurrentText(f"{preset.sample_rate} Hz")
        self.combo_channels.setCurrentIndex(0 if preset.channels == 2 else 1)

        self.spin_bframes.setValue(0)
        self.chk_qpel.setChecked(False)
        self.chk_gmc.setChecked(False)
        self.chk_deinterlace.setChecked(False)
        self.chk_normalize.setChecked(False)

        self._block_signals(False)
        self._check_resolution_warning()

    def get_settings(() -> Dict[str, Any]:
        pass  # Will define below

    def get_settings_dict(self) -> Dict[str, Any]:
        vcodec_display = self.combo_vcodec.currentText()
        ff_vcodec = VIDEO_CODECS_MAP.get(vcodec_display, "mpeg4")
        vtag = "XVID" if vcodec_display == "Xvid-compatible MPEG-4" else None

        acodec_display = self.combo_acodec.currentText()
        ff_acodec = AUDIO_CODECS_MAP.get(acodec_display, "aac")

        w = self.spin_width.value()
        h = self.spin_height.value()
        # Even number rounding
        if w % 2 != 0: w -= 1
        if h % 2 != 0: h -= 1

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
            "qpel": self.chk_qpel.isChecked(),
            "gmc": self.chk_gmc.isChecked(),
            "acodec": ff_acodec,
            "abitrate_kbps": self.combo_abitrate.currentData(),
            "sample_rate": self.combo_sample.currentData(),
            "channels": self.combo_channels.currentData(),
            "normalize_audio": self.chk_normalize.isChecked(),
            "limit_streams": True
        }

    def _toggle_collapse(self):
        if self.btn_toggle.isChecked():
            self.btn_toggle.setText("[ Advanced Settings ▲ ]")
            self.container.show()
        else:
            self.btn_toggle.setText("[ Advanced Settings ▼ ]")
            self.container.hide()

    def _on_resolution_changed(self):
        w = self.spin_width.value()
        h = self.spin_height.value()
        if w % 2 != 0: self.spin_width.setValue(w - 1)
        if h % 2 != 0: self.spin_height.setValue(h - 1)
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

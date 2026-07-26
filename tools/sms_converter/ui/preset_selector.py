"""
Preset selection and destination configuration widget with visual hints and recommendation badges.
"""
from typing import Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QFormLayout, QComboBox, QLabel, QHBoxLayout, QPushButton, QFileDialog, QVBoxLayout, QFrame
)

from config import PRESETS, LABEL_HARDWARE_CONFIRMED, LABEL_CUSTOM_PROFILE

class PresetSelectorWidget(QWidget):
    preset_changed = Signal(str, object)   # preset_name, Preset object or None
    destination_changed = Signal(str, str) # mode ("same" or "custom"), custom_path

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QFormLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # 1. Preset Dropdown
        self.combo_preset = QComboBox()
        self.combo_preset.setStyleSheet("""
            QComboBox {
                padding: 6px;
                font-weight: bold;
                background-color: #2D3748;
                border: 1px solid #4A5568;
                border-radius: 4px;
                color: #FFFFFF;
            }
            QComboBox QAbstractItemView {
                background-color: #1A202C;
                color: white;
                selection-background-color: #3182CE;
            }
        """)
        self.combo_preset.setToolTip(
            "Select a PlayStation 2 hardware-tested export preset.\n"
            "• Xvid-Compatible AVI is recommended for maximum performance over USB and SMB network shares."
        )
        for name in PRESETS.keys():
            self.combo_preset.addItem(name)
        self.combo_preset.currentIndexChanged.connect(self._on_preset_changed)

        # 2. Preset Description Hint Box
        self.lbl_preset_desc = QLabel("")
        self.lbl_preset_desc.setStyleSheet("""
            QLabel {
                color: #63B3ED;
                font-size: 11px;
                font-style: italic;
                padding-left: 2px;
            }
        """)
        self.lbl_preset_desc.setWordWrap(True)

        # 3. Quality / Confirmation Badge Label (Pill Style)
        self.label_badge = QLabel(LABEL_HARDWARE_CONFIRMED)
        self.label_badge.setToolTip(
            "Indicates whether your output profile is hardware-tested on real PS2 consoles.\n"
            "Standard presets guarantee hardware performance."
        )
        self.set_badge_state(True)

        # 4. Save to Destination Dropdown & Path Display
        save_layout = QHBoxLayout()
        self.combo_save = QComboBox()
        self.combo_save.setToolTip("Select where converted SMS-compatible files will be saved.")
        self.combo_save.addItem("Same folder as source (Default)", "same")
        self.combo_save.addItem("Custom folder…", "custom")
        self.combo_save.currentIndexChanged.connect(self._on_save_changed)

        self.label_custom_dir = QLabel("")
        self.label_custom_dir.setStyleSheet("color: #A0AEC0; font-size: 11px;")
        self.label_custom_dir.hide()

        save_layout.addWidget(self.combo_save)
        save_layout.addWidget(self.label_custom_dir)
        save_layout.addStretch()

        preset_box = QVBoxLayout()
        preset_box.addWidget(self.combo_preset)
        preset_box.addWidget(self.lbl_preset_desc)

        layout.addRow("Output Format:", preset_box)
        layout.addRow("Quality Profile:", self.label_badge)
        layout.addRow("Save Location:", save_layout)

        self.custom_dir_path: Optional[str] = None

        # Trigger initial description
        self._on_preset_changed(0)

    def set_badge_state(self, is_hardware_confirmed: bool):
        if is_hardware_confirmed:
            self.label_badge.setText(LABEL_HARDWARE_CONFIRMED)
            self.label_badge.setStyleSheet("""
                QLabel {
                    background-color: #22543D;
                    color: #68D391;
                    font-weight: bold;
                    font-size: 11px;
                    padding: 4px 8px;
                    border-radius: 4px;
                    border: 1px solid #2F855A;
                }
            """)
        else:
            self.label_badge.setText(LABEL_CUSTOM_PROFILE)
            self.label_badge.setStyleSheet("""
                QLabel {
                    background-color: #7B341E;
                    color: #FBD38D;
                    font-weight: bold;
                    font-size: 11px;
                    padding: 4px 8px;
                    border-radius: 4px;
                    border: 1px solid #C05621;
                }
            """)

    def current_preset_name(self) -> str:
        return self.combo_preset.currentText()

    def get_save_mode(self) -> str:
        return self.combo_save.currentData()

    def get_custom_dir(self) -> Optional[str]:
        return self.custom_dir_path

    def _on_preset_changed(self, index: int):
        name = self.combo_preset.currentText()
        preset = PRESETS.get(name)
        if preset:
            self.set_badge_state(preset.is_hardware_confirmed)
            self.lbl_preset_desc.setText(f"💡 {preset.description}")
        self.preset_changed.emit(name, preset)

    def _on_save_changed(self, index: int):
        mode = self.combo_save.currentData()
        if mode == "custom":
            folder = QFileDialog.getExistingDirectory(self, "Select Output Directory")
            if folder:
                self.custom_dir_path = folder
                self.label_custom_dir.setText(folder)
                self.label_custom_dir.show()
                self.destination_changed.emit("custom", folder)
            else:
                # Revert to same if cancelled
                self.combo_save.setCurrentIndex(0)
                self.destination_changed.emit("same", "")
        else:
            self.custom_dir_path = None
            self.label_custom_dir.hide()
            self.destination_changed.emit("same", "")

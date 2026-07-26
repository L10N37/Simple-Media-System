"""
Dependency setup dialog displayed when FFmpeg or ffprobe binaries are not found.
"""
from typing import Tuple, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QHBoxLayout, QPushButton, QFileDialog, QMessageBox
)

from ffmpeg_utils import find_ffmpeg_binaries

class SetupDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("FFmpeg Setup Required — SMS Media Converter")
        self.resize(550, 250)

        self.ffmpeg_path: Optional[str] = None
        self.ffprobe_path: Optional[str] = None

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        lbl_title = QLabel("FFmpeg & ffprobe Not Detected")
        lbl_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #E53E3E;")

        lbl_desc = QLabel(
            "SMS Media Converter requires both <b>ffmpeg</b> and <b>ffprobe</b> executables to convert and validate video/audio files.<br><br>"
            "Please install FFmpeg or specify the directory containing the <code>ffmpeg</code> and <code>ffprobe</code> binaries."
        )
        lbl_desc.setWordWrap(True)
        lbl_desc.setStyleSheet("color: #E2E8F0;")

        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet("color: #ED8936; font-style: italic;")

        btn_layout = QHBoxLayout()

        btn_browse = QPushButton("Browse for FFmpeg Directory…")
        btn_browse.clicked.connect(self._browse_dir)

        btn_recheck = QPushButton("Re-check System")
        btn_recheck.clicked.connect(self._recheck)

        btn_exit = QPushButton("Exit")
        btn_exit.clicked.connect(self.reject)

        btn_layout.addWidget(btn_browse)
        btn_layout.addWidget(btn_recheck)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_exit)

        layout.addWidget(lbl_title)
        layout.addWidget(lbl_desc)
        layout.addWidget(self.lbl_status)
        layout.addStretch()
        layout.addLayout(btn_layout)

    def _browse_dir(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Directory Containing ffmpeg and ffprobe")
        if folder:
            ff, fp = find_ffmpeg_binaries(folder)
            if ff and fp:
                self.ffmpeg_path = ff
                self.ffprobe_path = fp
                self.accept()
            else:
                QMessageBox.warning(
                    self,
                    "Binaries Missing",
                    "Could not find both ffmpeg and ffprobe in the selected directory."
                )

    def _recheck(self):
        ff, fp = find_ffmpeg_binaries()
        if ff and fp:
            self.ffmpeg_path = ff
            self.ffprobe_path = fp
            self.accept()
        else:
            self.lbl_status.setText("FFmpeg binaries still not found in standard paths.")

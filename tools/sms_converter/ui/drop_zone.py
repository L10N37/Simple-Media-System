"""
Drag and drop file selection widget with format guidance.
"""
import os
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QLabel, QPushButton, QFileDialog
)

class DropZoneWidget(QFrame):
    files_dropped = Signal(list)  # list of file paths

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setObjectName("DropZoneWidget")
        self.setStyleSheet("""
            #DropZoneWidget {
                border: 2px dashed #4A5568;
                border-radius: 8px;
                background-color: #1A202C;
                min-height: 110px;
            }
            #DropZoneWidget:hover {
                border-color: #3182CE;
                background-color: #2D3748;
            }
            QLabel#MainLabel {
                color: #E2E8F0;
                font-size: 15px;
                font-weight: bold;
            }
            QLabel#SubLabel {
                color: #A0AEC0;
                font-size: 11px;
            }
            QPushButton {
                background-color: #3182CE;
                color: white;
                border-radius: 4px;
                padding: 6px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2B6CB0;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(6)

        self.label_main = QLabel("📁 Drop ANY Audio or Video File Here")
        self.label_main.setObjectName("MainLabel")
        self.label_main.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.label_sub = QLabel("Supports MKV, MP4, AVI, MOV, WMV, FLV, TS, VOB, WEBM, MP3, AAC, FLAC & more")
        self.label_sub.setObjectName("SubLabel")
        self.label_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.btn_browse = QPushButton("Browse Files…")
        self.btn_browse.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_browse.clicked.connect(self._open_file_dialog)

        layout.addWidget(self.label_main)
        layout.addWidget(self.label_sub)
        layout.addWidget(self.btn_browse, 0, Qt.AlignmentFlag.AlignCenter)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        files = []
        for u in urls:
            path = u.toLocalFile()
            if os.path.isfile(path):
                files.append(path)
        if files:
            self.files_dropped.emit(files)
            event.acceptProposedAction()

    def _open_file_dialog(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Audio or Video Files",
            "",
            "Media Files (*.mkv *.mp4 *.avi *.mpg *.mpeg *.mov *.wmv *.flv *.ts *.vob *.webm *.mp3 *.aac *.m4a *.wav *.flac *.ogg *.wma);;All Files (*.*)"
        )
        if files:
            self.files_dropped.emit(files)

"""
Dialog showing complete FFmpeg console log and post-conversion SMS validation report.
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QTabWidget, QTextEdit, QHBoxLayout, QPushButton, QFileDialog
)
from ui.queue_table import QueueItem

class DetailsDialog(QDialog):
    def __init__(self, item: QueueItem, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Details & Log — {item.file_name}")
        self.resize(700, 500)
        self.item = item

        layout = QVBoxLayout(self)

        tabs = QTabWidget()

        # Tab 1: Validation Report
        self.txt_val = QTextEdit()
        self.txt_val.setReadOnly(True)
        self.txt_val.setStyleSheet("font-family: monospace; background-color: #1A202C; color: #E2E8F0;")
        
        if item.validation_result:
            self.txt_val.setPlainText(item.validation_result.generate_report())
        else:
            self.txt_val.setPlainText("No validation report available for this item.")

        tabs.addTab(self.txt_val, "Validation Report")

        # Tab 2: Console Log & Command Line
        self.txt_log = QTextEdit()
        self.txt_log.setReadOnly(True)
        self.txt_log.setStyleSheet("font-family: monospace; background-color: #1A202C; color: #A0AEC0;")
        self.txt_log.setPlainText(item.console_log if item.console_log else "No conversion log available.")

        tabs.addTab(self.txt_log, "FFmpeg Command & Log")

        layout.addWidget(tabs)

        # Bottom Buttons
        btn_layout = QHBoxLayout()
        btn_export = QPushButton("Export Log…")
        btn_export.clicked.connect(self._export_log)

        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.accept)

        btn_layout.addWidget(btn_export)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_close)

        layout.addLayout(btn_layout)

    def _export_log(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Conversion Log",
            f"{self.item.file_name}_log.txt",
            "Text Files (*.txt);;All Files (*.*)"
        )
        if file_path:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(f"FILE: {self.item.file_path}\n")
                f.write(f"STATUS: {self.item.status}\n\n")
                f.write("=== VALIDATION REPORT ===\n")
                f.write(self.txt_val.toPlainText())
                f.write("\n\n=== CONSOLE LOG ===\n")
                f.write(self.txt_log.toPlainText())

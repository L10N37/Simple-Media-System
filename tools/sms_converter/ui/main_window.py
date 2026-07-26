"""
Main Application Window for SMS Media Converter.
"""
from pathlib import Path
from typing import Dict, Optional, List
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QProgressBar, QPushButton, QMessageBox
)

from config import (
    PRESETS, SIZE_3_8_GIB, SIZE_4_0_GIB, MSG_FILE_SIZE_APPROACHING_LIMIT, Preset
)
from ffmpeg_utils import calculate_estimated_output_size, generate_unique_output_path
from validator import ValidationResult
from worker import InspectWorker, ConversionWorker

from ui.drop_zone import DropZoneWidget
from ui.preset_selector import PresetSelectorWidget
from ui.advanced_settings import AdvancedSettingsWidget
from ui.queue_table import QueueTableWidget, QueueItem
from ui.details_dialog import DetailsDialog

class MainWindow(QMainWindow):
    def __init__(self, ffmpeg_path: str, ffprobe_path: str):
        super().__init__()
        self.setWindowTitle("SMS Media Converter")
        self.resize(750, 680)

        self.ffmpeg_path = ffmpeg_path
        self.ffprobe_path = ffprobe_path

        # State management
        self.queue_order: List[str] = []
        self.current_worker: Optional[ConversionWorker] = None
        self.inspect_workers: Dict[str, InspectWorker] = {}
        self.is_converting = False

        # Main Widget & Layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # 1. Drop Zone
        self.drop_zone = DropZoneWidget()
        self.drop_zone.files_dropped.connect(self._on_files_added)

        # 2. Preset Selector
        self.preset_selector = PresetSelectorWidget()
        self.preset_selector.preset_changed.connect(self._on_preset_changed)
        self.preset_selector.destination_changed.connect(self._on_destination_changed)

        # 3. Advanced Settings
        self.advanced_settings = AdvancedSettingsWidget()
        self.advanced_settings.settings_changed.connect(self._on_settings_changed)

        # 4. Queue Table
        self.queue_table = QueueTableWidget()
        self.queue_table.show_details_requested.connect(self._show_details)

        # 5. Bottom Status Bar & Controls
        self.lbl_estimated_size = QLabel("Estimated output: --")
        self.lbl_estimated_size.setStyleSheet("font-weight: bold; font-size: 13px; color: #E2E8F0;")

        self.lbl_size_warning = QLabel("")
        self.lbl_size_warning.setStyleSheet("font-size: 11px; font-weight: bold;")
        self.lbl_size_warning.hide()

        size_layout = QHBoxLayout()
        size_layout.addWidget(self.lbl_estimated_size)
        size_layout.addWidget(self.lbl_size_warning)
        size_layout.addStretch()

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #4A5568;
                border-radius: 4px;
                background-color: #1A202C;
                text-align: center;
                color: white;
                font-weight: bold;
                height: 18px;
            }
            QProgressBar::chunk {
                background-color: #3182CE;
                border-radius: 3px;
            }
        """)

        self.lbl_status_msg = QLabel("Ready")
        self.lbl_status_msg.setStyleSheet("color: #A0AEC0; font-size: 12px;")

        # Action Buttons
        btn_layout = QHBoxLayout()

        self.btn_remove = QPushButton("Remove")
        self.btn_remove.clicked.connect(self._remove_selected)

        self.btn_clear = QPushButton("Clear")
        self.btn_clear.clicked.connect(self._clear_queue)

        self.btn_details = QPushButton("Details")
        self.btn_details.clicked.connect(self._show_selected_details)

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self._cancel_conversion)

        self.btn_convert = QPushButton("Convert")
        self.btn_convert.setStyleSheet("""
            QPushButton {
                background-color: #38A169;
                color: white;
                font-weight: bold;
                padding: 6px 20px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #2F855A;
            }
            QPushButton:disabled {
                background-color: #4A5568;
                color: #A0AEC0;
            }
        """)
        self.btn_convert.clicked.connect(self._start_conversion)

        btn_layout.addWidget(self.btn_remove)
        btn_layout.addWidget(self.btn_clear)
        btn_layout.addWidget(self.btn_details)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_convert)

        # Assembly
        main_layout.addWidget(self.drop_zone)
        main_layout.addWidget(self.preset_selector)
        main_layout.addWidget(self.advanced_settings)
        main_layout.addWidget(self.queue_table, 1)
        main_layout.addLayout(size_layout)
        main_layout.addWidget(self.progress_bar)
        main_layout.addWidget(self.lbl_status_msg)
        main_layout.addLayout(btn_layout)

        # Initialize defaults
        self._on_preset_changed(
            self.preset_selector.current_preset_name(),
            PRESETS.get(self.preset_selector.current_preset_name())
        )

    # --- Queue Management ---
    def _on_files_added(self, file_paths: List[str]):
        for fp in file_paths:
            item_id = str(Path(fp).resolve())
            if item_id in self.queue_table.items_dict:
                continue

            item = QueueItem(
                item_id=item_id,
                file_path=fp,
                file_name=Path(fp).name,
                status="Inspecting"
            )
            self.queue_table.add_queue_item(item)
            self.queue_order.append(item_id)

            # Spawn non-blocking background inspection
            inspect_worker = InspectWorker(self.ffprobe_path, fp)
            inspect_worker.finished_signal.connect(self._on_inspect_finished)
            self.inspect_workers[item_id] = inspect_worker
            inspect_worker.start()

    def _on_inspect_finished(self, file_path: str, summary: dict):
        item_id = str(Path(file_path).resolve())
        self.inspect_workers.pop(item_id, None)

        duration = summary.get("duration", 0.0)
        size = summary.get("size", 0)
        v_width = summary.get("width", 0)
        v_height = summary.get("height", 0)

        # Calculate estimated size based on current settings
        settings = self.advanced_settings.get_settings_dict()
        est_bytes = calculate_estimated_output_size(
            duration,
            settings.get("vbitrate_kbps", 1500),
            settings.get("abitrate_kbps", 128)
        )

        self.queue_table.update_item_metadata(item_id, duration, size, est_bytes)
        self.queue_table.update_item_status(item_id, "Ready")

        self._update_total_estimated_size()

    def _on_preset_changed(self, name: str, preset: Optional[Preset]):
        if preset:
            self.advanced_settings.load_preset(preset)
        self._recalculate_estimates()

    def _on_destination_changed(self, mode: str, path: str):
        pass

    def _on_settings_changed(self, settings: dict):
        self._recalculate_estimates()

    def _recalculate_estimates(self):
        settings = self.advanced_settings.get_settings_dict()
        for item_id, item in self.queue_table.items_dict.items():
            if item.duration_sec > 0:
                est = calculate_estimated_output_size(
                    item.duration_sec,
                    settings.get("vbitrate_kbps", 1500),
                    settings.get("abitrate_kbps", 128)
                )
                item.estimated_size_bytes = est
        self._update_total_estimated_size()

    def _update_total_estimated_size(self):
        total_bytes = sum(item.estimated_size_bytes for item in self.queue_table.items_dict.values())
        if total_bytes <= 0:
            self.lbl_estimated_size.setText("Estimated output: --")
            self.lbl_size_warning.hide()
            return

        mib = total_bytes / (1024 * 1024)
        if mib >= 1024:
            size_str = f"{mib / 1024:.2f} GB"
        else:
            size_str = f"{mib:.1f} MB"

        self.lbl_estimated_size.setText(f"Estimated output: {size_str}")

        # Check 4 GiB thresholds
        if total_bytes >= SIZE_4_0_GIB:
            self.lbl_size_warning.setText("[BLOCKED: Projected file size >= 4.0 GiB limit]")
            self.lbl_size_warning.setStyleSheet("color: #E53E3E; font-weight: bold;")
            self.lbl_size_warning.show()
        elif total_bytes >= SIZE_3_8_GIB:
            self.lbl_size_warning.setText("[WARNING: Projected file size approaching 4.0 GiB ceiling]")
            self.lbl_size_warning.setStyleSheet("color: #ED8936; font-weight: bold;")
            self.lbl_size_warning.show()
        else:
            self.lbl_size_warning.hide()

    # --- Batch Conversion Execution ---
    def _start_conversion(self):
        if self.is_converting:
            return

        # Check if queue has ready items
        ready_ids = [i_id for i_id in self.queue_order if self.queue_table.items_dict[i_id].status in ("Ready", "Failed", "Cancelled")]
        if not ready_ids:
            QMessageBox.information(self, "No Files Ready", "There are no files in the queue ready for conversion.")
            return

        self.is_converting = True
        self.btn_convert.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.btn_remove.setEnabled(False)
        self.btn_clear.setEnabled(False)

        self._process_next_in_queue()

    def _process_next_in_queue(self):
        next_id = None
        for i_id in self.queue_order:
            status = self.queue_table.items_dict[i_id].status
            if status in ("Ready", "Failed", "Cancelled"):
                next_id = i_id
                break

        if not next_id:
            # Queue Finished!
            self.is_converting = False
            self.btn_convert.setEnabled(True)
            self.btn_cancel.setEnabled(False)
            self.btn_remove.setEnabled(True)
            self.btn_clear.setEnabled(True)
            self.lbl_status_msg.setText("Batch conversion completed.")
            self.progress_bar.setValue(100)
            return

        item = self.queue_table.items_dict[next_id]
        self.queue_table.update_item_status(next_id, "Converting")

        settings = self.advanced_settings.get_settings_dict()

        # Add preset name metadata to settings
        preset_name = self.preset_selector.current_preset_name()
        settings["preset_name"] = preset_name

        # Determine extension
        ext = PRESETS[preset_name].ext if preset_name in PRESETS else ".avi"
        save_mode = self.preset_selector.get_save_mode()
        custom_dir = self.preset_selector.get_custom_dir() if save_mode == "custom" else None

        final_path, partial_path = generate_unique_output_path(
            item.file_path,
            ext,
            custom_dir
        )
        item.final_output_path = final_path

        self.current_worker = ConversionWorker(
            item_id=next_id,
            ffmpeg_path=self.ffmpeg_path,
            ffprobe_path=self.ffprobe_path,
            input_file=item.file_path,
            partial_file=partial_path,
            final_file=final_path,
            settings=settings,
            duration_sec=item.duration_sec
        )
        self.current_worker.progress_signal.connect(self._on_worker_progress)
        self.current_worker.log_signal.connect(self._on_worker_log)
        self.current_worker.validation_signal.connect(self._on_worker_validation)
        self.current_worker.failed_signal.connect(self._on_worker_failed)
        self.current_worker.cancelled_signal.connect(self._on_worker_cancelled)

        self.current_worker.start()

    def _on_worker_progress(self, item_id: str, pct: float, status_msg: str):
        self.progress_bar.setValue(int(pct))
        self.lbl_status_msg.setText(status_msg)

    def _on_worker_log(self, item_id: str, log_line: str):
        if item_id in self.queue_table.items_dict:
            self.queue_table.items_dict[item_id].console_log += log_line + "\n"

    def _on_worker_validation(self, item_id: str, result: ValidationResult, output_path: str):
        if item_id in self.queue_table.items_dict:
            item = self.queue_table.items_dict[item_id]
            item.validation_result = result
            if result.status == "PASS":
                self.queue_table.update_item_status(item_id, "Passed")
            elif result.status == "WARN":
                self.queue_table.update_item_status(item_id, "Warning")
            else:
                self.queue_table.update_item_status(item_id, "Failed")

        self._process_next_in_queue()

    def _on_worker_failed(self, item_id: str, err_msg: str):
        if item_id in self.queue_table.items_dict:
            item = self.queue_table.items_dict[item_id]
            item.console_log += f"\nFAILURE: {err_msg}\n"
            self.queue_table.update_item_status(item_id, "Failed")

        # Continue queue even if individual file failed
        self._process_next_in_queue()

    def _on_worker_cancelled(self, item_id: str):
        if item_id in self.queue_table.items_dict:
            self.queue_table.update_item_status(item_id, "Cancelled")
        self.is_converting = False
        self.btn_convert.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.btn_remove.setEnabled(True)
        self.btn_clear.setEnabled(True)
        self.lbl_status_msg.setText("Conversion cancelled by user.")

    def _cancel_conversion(self):
        if self.current_worker and self.current_worker.isRunning():
            self.current_worker.cancel()

    # --- UI Actions ---
    def _remove_selected(self):
        selected_ids = self.queue_table.get_selected_item_ids()
        for i_id in selected_ids:
            self.queue_table.remove_item(i_id)
            if i_id in self.queue_order:
                self.queue_order.remove(i_id)
        self._update_total_estimated_size()

    def _clear_queue(self):
        self.queue_table.clear_all()
        self.queue_order.clear()
        self._update_total_estimated_size()

    def _show_selected_details(self):
        selected_ids = self.queue_table.get_selected_item_ids()
        if selected_ids:
            self._show_details(selected_ids[0])

    def _show_details(self, item_id: str):
        if item_id in self.queue_table.items_dict:
            item = self.queue_table.items_dict[item_id]
            dlg = DetailsDialog(item, self)
            dlg.exec()

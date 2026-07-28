"""
Main Application Window for SMS Media Converter.
"""
from pathlib import Path
from typing import Dict, Optional, List
from qt_compat import Qt, QTimer, Signal, dialog_exec
from qt_compat import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QProgressBar, QPushButton, QMessageBox
)

import crash_log
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
        # Workers handed off but not yet destroyed. See _advance_queue_soon: dropping the last
        # reference to a QThread that has not finished aborts the process.
        self._retired_workers: List[ConversionWorker] = []
        self.inspect_workers: Dict[str, InspectWorker] = {}
        self.is_converting = False

        # Main Widget & Layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # 0. Guidance Banner
        self.banner = QLabel("💡 Drop in any video or audio file and it comes out ready to play on a PlayStation 2 running SMS. The recommended settings are already chosen.")
        # Without word wrap this single long line sets the window's minimum WIDTH to its own
        # rendered width -- 820px measured -- so the resize(750, 680) below could never take
        # effect and the window could not be narrowed. Wrapping drops that floor to ~512.
        self.banner.setWordWrap(True)
        self.banner.setStyleSheet("""
            QLabel {
                background-color: #2B6CB0;
                color: #FFFFFF;
                font-weight: bold;
                font-size: 12px;
                padding: 8px 12px;
                border-radius: 6px;
            }
        """)
        main_layout.addWidget(self.banner)

        # 1. Drop Zone
        self.drop_zone = DropZoneWidget()
        self.drop_zone.files_dropped.connect(self._on_files_added)

        # Accept drops on the WHOLE window, not just the drop zone. Once the queue has files
        # the user's attention is on the table, and dropping there is the natural gesture --
        # it previously did nothing at all, silently, because drop_zone was the only widget
        # with setAcceptDrops. The affordance was obvious for the first file and misleading
        # for every one after it.
        self.setAcceptDrops(True)

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
        self.lbl_estimated_size.setToolTip("Estimated output file size calculated from target video and audio bitrates.")
        self.lbl_size_warning.hide()

        size_layout = QHBoxLayout()
        size_layout.addWidget(self.lbl_estimated_size)
        size_layout.addWidget(self.lbl_size_warning)
        size_layout.addStretch()

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setToolTip("Real-time encoding progress for the active media file.")
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
        self.btn_remove.setToolTip("Remove selected item(s) from the conversion queue.")
        self.btn_remove.clicked.connect(self._remove_selected)

        self.btn_clear = QPushButton("Clear")
        self.btn_clear.setToolTip("Clear all files from the queue.")
        self.btn_clear.clicked.connect(self._clear_queue)

        self.btn_details = QPushButton("Details")
        self.btn_details.setToolTip("Open conversion log, FFmpeg command details, and post-conversion SMS validation report.")
        self.btn_details.clicked.connect(self._show_selected_details)

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setToolTip("Cancel the active encoding job.")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self._cancel_conversion)

        self.btn_convert = QPushButton("Convert")
        self.btn_convert.setToolTip("Start converting queued media files into SMS hardware-compatible format.")
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

        # Status, progress and the size estimate share ONE row instead of three stacked
        # full-width rows. They are three short left-aligned strings that are idle most of the
        # time, and each was consuming a full row plus spacing -- roughly 90px of chrome that
        # the queue table (the only widget allowed to grow) was paying for. Merged, that space
        # goes to the file list, which is what the user is actually reading.
        status_row = QHBoxLayout()
        status_row.addLayout(size_layout)
        status_row.addWidget(self.progress_bar, 1)
        status_row.addWidget(self.lbl_status_msg)
        main_layout.addLayout(status_row)

        main_layout.addLayout(btn_layout)

        # Initialize defaults
        self._on_preset_changed(
            self.preset_selector.current_preset_name(),
            PRESETS.get(self.preset_selector.current_preset_name())
        )

    # --- Queue Management ---
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
        """Window-level drop. Reuses the same path as the drop zone so behaviour is identical."""
        import os as _os
        files = [
            u.toLocalFile() for u in event.mimeData().urls()
            if u.toLocalFile() and _os.path.isfile(u.toLocalFile())
        ]
        if files:
            self._on_files_added(files)
            event.acceptProposedAction()
        else:
            event.ignore()

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
        preset_name = self.preset_selector.current_preset_name()
        preset = PRESETS.get(preset_name)
        if preset:
            is_match = (
                settings.get("width") == (preset.width or settings.get("width")) and
                settings.get("height") == (preset.height or settings.get("height")) and
                settings.get("vbitrate_kbps") == (preset.vbitrate_kbps or settings.get("vbitrate_kbps")) and
                settings.get("bframes") == 0 and
                not settings.get("qpel") and
                not settings.get("gmc")
            )
            self.preset_selector.set_badge_state(is_match)

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

        # Pressing Convert is what re-arms a previous failure. _process_next_in_queue only ever
        # advances through "Ready" items, so this is the single place a retry can be asked for,
        # and it takes a deliberate press rather than happening on its own.
        for i_id in ready_ids:
            if self.queue_table.items_dict[i_id].status in ("Failed", "Cancelled"):
                self.queue_table.update_item_status(i_id, "Ready")

        self.is_converting = True
        self.btn_convert.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.btn_remove.setEnabled(False)
        self.btn_clear.setEnabled(False)

        self._process_next_in_queue()

    def _process_next_in_queue(self):
        # "Ready" ONLY, and that is load-bearing.
        #
        # This used to also pick up "Failed" and "Cancelled". Since a failure sets the item to
        # "Failed" and then calls straight back into here, the very same item was selected
        # again, converted again, failed again -- forever. Every lap started another QThread
        # and another ffmpeg, so the app spun up threads as fast as ffmpeg could fail until
        # the process died. No Python exception is raised on that path, which is exactly why
        # a tester reporting "the app just closes" got an empty crash log.
        #
        # A success never showed it: the item becomes "Passed", which this scan ignores, so it
        # returned here and stopped. That asymmetry is why the failure looked codec-specific --
        # whichever preset failed on the user's machine was the one that appeared to crash.
        #
        # Retrying is still available, but only when the USER asks: _start_conversion promotes
        # failed and cancelled items back to "Ready". An automatic retry of something that just
        # failed for a deterministic reason can only fail again.
        next_id = None
        for i_id in self.queue_order:
            if self.queue_table.items_dict[i_id].status == "Ready":
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

        crash_log.breadcrumb("Convert pressed; building settings")
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

        crash_log.breadcrumb(f"starting worker thread for {Path(item.file_path).name}")
        self.current_worker.start()

    def _on_worker_progress(self, item_id: str, pct: float, status_msg: str):
        self.progress_bar.setValue(int(pct))
        self.lbl_status_msg.setText(status_msg)

    # Kept bounded. This appends to a str on the GUI thread once per forwarded line, and a str
    # += reallocates the whole buffer each time -- so an unbounded log is quadratic in both time
    # and memory over a long encode. The worker no longer forwards the per-second progress
    # block, which removes most of the traffic; this caps what is left. Only the tail is ever
    # shown, so trimming the front loses nothing a user would look for.
    _LOG_MAX_CHARS = 64 * 1024

    def _on_worker_log(self, item_id: str, log_line: str):
        if item_id in self.queue_table.items_dict:
            item = self.queue_table.items_dict[item_id]
            item.console_log += log_line + "\n"
            if len(item.console_log) > self._LOG_MAX_CHARS:
                item.console_log = item.console_log[-self._LOG_MAX_CHARS:]

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

        self._advance_queue_soon()

    def _on_worker_failed(self, item_id: str, err_msg: str):
        if item_id in self.queue_table.items_dict:
            item = self.queue_table.items_dict[item_id]
            item.console_log += f"\nFAILURE: {err_msg}\n"
            self.queue_table.update_item_status(item_id, "Failed")

        # Continue queue even if individual file failed
        self._advance_queue_soon()

    def _advance_queue_soon(self):
        """Move to the next item from the event loop, never from inside a worker's signal.

        Both callers are slots invoked by the worker that is finishing, and advancing the queue
        assigns a NEW ConversionWorker over self.current_worker -- which drops the last
        reference to the QThread whose signal is still on the stack. Destroying a QThread that
        has not finished is a hard abort in Qt, with no Python exception to catch: the process
        simply disappears, which is the symptom being chased here.

        Deferring with a zero timer lets the signal return and the thread finish first, and
        holding the outgoing worker in _retired_workers keeps it alive until Qt is genuinely
        done with it. This matters on the ORDINARY path too, not just after a failure -- a
        two-file batch hands over exactly the same way.
        """
        if self.current_worker is not None:
            self._retired_workers.append(self.current_worker)
            self.current_worker = None
        QTimer.singleShot(0, self._drain_retired_and_advance)

    def _drain_retired_and_advance(self):
        """Release finished workers, then start the next item."""
        still_running = []
        for w in self._retired_workers:
            if w.isRunning():
                still_running.append(w)
            else:
                w.deleteLater()
        self._retired_workers = still_running
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
            dialog_exec(dlg)

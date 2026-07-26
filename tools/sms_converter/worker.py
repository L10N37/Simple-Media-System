"""
Asynchronous worker threads for file inspection, conversion execution, file size monitoring, and validation.
"""
import os
import sys
import time
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional
from PySide6.QtCore import QThread, Signal

from config import SIZE_4_0_GIB, MSG_FILE_SIZE_APPROACHING_LIMIT
from ffmpeg_utils import (
    get_media_info,
    parse_media_summary,
    build_ffmpeg_cmd,
    generate_unique_output_path,
)
from validator import validate_converted_file, ValidationResult

class InspectWorker(QThread):
    """Worker thread for non-blocking file inspection via ffprobe."""
    finished_signal = Signal(str, dict)  # file_path, summary_dict

    def __init__(self, ffprobe_path: str, file_path: str):
        super().__init__()
        self.ffprobe_path = ffprobe_path
        self.file_path = file_path

    def run(self):
        probe_data = get_media_info(self.ffprobe_path, self.file_path)
        summary = parse_media_summary(probe_data)
        self.finished_signal.emit(self.file_path, summary)


class ConversionWorker(QThread):
    """
    Worker thread that executes FFmpeg with pipe:1 progress reporting,
    monitors partial file size against the 4 GiB SMS ceiling,
    and runs post-conversion validation.
    """
    progress_signal = Signal(str, float, str)  # item_id, percentage, status_msg
    log_signal = Signal(str, str)             # item_id, log_line
    validation_signal = Signal(str, ValidationResult, str) # item_id, result, final_path
    failed_signal = Signal(str, str)          # item_id, error_message
    cancelled_signal = Signal(str)            # item_id

    def __init__(
        self,
        item_id: str,
        ffmpeg_path: str,
        ffprobe_path: str,
        input_file: str,
        partial_file: str,
        final_file: str,
        settings: Dict[str, Any],
        duration_sec: float
    ):
        super().__init__()
        self.item_id = item_id
        self.ffmpeg_path = ffmpeg_path
        self.ffprobe_path = ffprobe_path
        self.input_file = input_file
        self.partial_file = partial_file
        self.final_file = final_file
        self.settings = settings
        self.duration_sec = duration_sec

        self._is_cancelled = False
        self._process: Optional[subprocess.Popen] = None
        self.console_log = []
        self.cmd_str = ""

    def cancel(self):
        """Requests worker cancellation and terminates running process."""
        self._is_cancelled = True
        if self._process and self._process.poll() is None:
            try:
                self._process.terminate()
                self._process.wait(timeout=2)
            except Exception:
                try:
                    self._process.kill()
                except Exception:
                    pass

    def run(self):
        cmd = build_ffmpeg_cmd(
            self.ffmpeg_path,
            self.input_file,
            self.partial_file,
            self.settings
        )
        self.cmd_str = " ".join(f'"{arg}"' if " " in arg else arg for arg in cmd)
        self.log_signal.emit(self.item_id, f"Executing command:\n{self.cmd_str}\n")

        try:
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )

            start_time = time.time()
            out_time_us = 0

            while True:
                if self._is_cancelled:
                    break

                # 1. Size Monitoring Safeguard
                if os.path.exists(self.partial_file):
                    current_size = os.path.getsize(self.partial_file)
                    if current_size >= SIZE_4_0_GIB:
                        self.cancel()
                        try:
                            self._process.wait(timeout=5)
                        except Exception:
                            pass
                        self.failed_signal.emit(self.item_id, MSG_FILE_SIZE_APPROACHING_LIMIT)
                        self._cleanup_partial()
                        return

                # 2. Read FFmpeg progress output line by line
                line = self._process.stdout.readline()
                if not line:
                    break

                self.console_log.append(line)
                self.log_signal.emit(self.item_id, line.rstrip())

                if "=" in line:
                    key, _, val = line.strip().partition("=")
                    key = key.strip()
                    val = val.strip()

                    if key == "out_time_us":
                        try:
                            out_time_us = int(val)
                        except ValueError:
                            pass
                    elif key == "progress":
                        current_sec = out_time_us / 1_000_000.0
                        pct = 0.0
                        if self.duration_sec > 0:
                            pct = min(100.0, (current_sec / self.duration_sec) * 100.0)

                        elapsed = time.time() - start_time
                        remaining_msg = ""
                        if pct > 0:
                            total_est = (elapsed / pct) * 100.0
                            rem_sec = int(total_est - elapsed)
                            rem_min = rem_sec // 60
                            rem_s = rem_sec % 60
                            if rem_min > 0:
                                remaining_msg = f" — approximately {rem_min} min remaining"
                            else:
                                remaining_msg = f" — approximately {rem_s} sec remaining"

                        status_msg = f"Encoding {Path(self.input_file).name}{remaining_msg}"
                        self.progress_signal.emit(self.item_id, pct, status_msg)

            if self._is_cancelled:
                try:
                    self._process.wait(timeout=5)
                except Exception:
                    pass
                self._cleanup_partial()
                self.cancelled_signal.emit(self.item_id)
                return

            if self._process.stdout:
                self._process.stdout.close()
            return_code = self._process.wait()

            if return_code != 0:
                err_text = "".join(self.console_log[-20:])
                self._cleanup_partial()
                self.failed_signal.emit(self.item_id, f"FFmpeg exited with code {return_code}:\n{err_text}")
                return

            # 3. Validation Stage
            self.progress_signal.emit(self.item_id, 100.0, f"Validating {Path(self.input_file).name}...")
            val_result = validate_converted_file(
                self.ffprobe_path,
                self.partial_file,
                self.settings.get("preset_name")
            )

            # If PASS or WARN, promote the partial file without clobbering an
            # unrelated file that appeared after the output name was selected.
            if val_result.status in ("PASS", "WARN"):
                target_path = self.final_file
                while True:
                    try:
                        # A hard-link creation is atomic and fails if target_path
                        # already exists. The partial and final paths share an
                        # output directory, so they are on the same filesystem.
                        os.link(self.partial_file, target_path)
                        os.unlink(self.partial_file)
                        break
                    except FileExistsError:
                        target_path, _ = generate_unique_output_path(
                            self.input_file,
                            Path(self.final_file).suffix,
                            str(Path(self.final_file).parent)
                        )
                self.validation_signal.emit(self.item_id, val_result, target_path)
            else:
                self._cleanup_partial()
                self.validation_signal.emit(self.item_id, val_result, self.partial_file)

        except Exception as e:
            self._cleanup_partial()
            self.failed_signal.emit(self.item_id, str(e))

    def _cleanup_partial(self):
        if os.path.exists(self.partial_file):
            try:
                os.remove(self.partial_file)
            except Exception:
                pass

"""Crash reporting, because a --windowed build cannot report anything by itself.

WHY THIS EXISTS
---------------
Both shipped executables are built with PyInstaller `--onefile --windowed`. Windowed means
no console is attached, which on Windows leaves `sys.stdout` and `sys.stderr` set to None.
An unhandled exception therefore goes nowhere at all: Python's default hook tries to write a
traceback to a stream that does not exist, and the process simply disappears.

That is precisely what a Windows 7 tester hit -- "every time I hit convert, app closes" --
with no message, no log and nothing on screen. It could not be diagnosed remotely because
the build had no way to say what went wrong, and it could not be reproduced locally because
the failure needs Python 3.8 + PySide2 on Windows 7. A silent exit is the worst possible
failure mode for a tool whose testers are on hardware the developer does not have.

So: every unhandled exception is written to a log file the user can send back, and the user
is told where it is. This does not fix any particular crash; it turns "it closed" into a
traceback with a line number.

WHAT IS COVERED
---------------
* Main-thread exceptions            -- sys.excepthook
* Worker-thread exceptions          -- threading.excepthook (3.8+, which is the Win7 floor)
* Exceptions raised inside Qt slots -- these reach sys.excepthook on PySide6, which ABORTS
  the process afterwards; PySide2 prints and continues. Logging them makes the two bindings
  produce the same evidence even though they differ in what happens next.

WHERE THE LOG GOES
------------------
Next to the executable, which is where a user will look first. If that directory is not
writable -- Program Files, or a read-only stick -- it falls back to the home directory
rather than losing the report, and the message box always states the resolved path.
"""

import os
import sys
import platform
import threading
import traceback
from datetime import datetime
from pathlib import Path

LOG_NAME = "sms-converter-crash.log"

_installed = False


def _candidate_dirs():
    """Where to try writing, best first."""
    if getattr(sys, "frozen", False):
        yield Path(sys.executable).parent
    else:
        yield Path(__file__).resolve().parent
    yield Path.home()


def crash_log_path() -> Path:
    """Resolve a writable location for the log. Never raises."""
    for d in _candidate_dirs():
        try:
            d.mkdir(parents=True, exist_ok=True)
            probe = d / (LOG_NAME + ".probe")
            probe.write_text("", encoding="utf-8")
            probe.unlink()
            return d / LOG_NAME
        except Exception:
            continue
    # Last resort: the temp directory always exists somewhere.
    import tempfile
    return Path(tempfile.gettempdir()) / LOG_NAME


def _environment() -> str:
    try:
        from qt_compat import QT_BINDING
    except Exception:
        QT_BINDING = "unknown"
    return (
        f"  when     : {datetime.now().isoformat(timespec='seconds')}\n"
        f"  python   : {sys.version.split()[0]}\n"
        f"  qt       : {QT_BINDING}\n"
        f"  platform : {platform.platform()}\n"
        f"  frozen   : {bool(getattr(sys, 'frozen', False))}\n"
        f"  exe      : {sys.executable}\n"
    )


def write_report(exc_type, exc_value, exc_tb, context: str = "") -> Path:
    """Append one crash report. Returns the path written. Never raises."""
    path = crash_log_path()
    try:
        body = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        with open(path, "a", encoding="utf-8") as fh:
            fh.write("\n" + "=" * 78 + "\n")
            if context:
                fh.write(f"context: {context}\n")
            fh.write(_environment())
            fh.write("-" * 78 + "\n")
            fh.write(body)
    except Exception:
        pass          # a crash handler that crashes helps nobody
    return path


def _notify(path: Path, exc_value) -> None:
    """Tell the user, but only if Qt is already up. Never raises."""
    try:
        from qt_compat import QApplication, QMessageBox
        if QApplication.instance() is None:
            return
        box = QMessageBox()
        box.setIcon(QMessageBox.Critical)
        box.setWindowTitle("SMS Media Converter - unexpected error")
        box.setText("Something went wrong and the details have been saved to a log file.")
        box.setInformativeText(
            f"{type(exc_value).__name__}: {exc_value}\n\n"
            f"Log file:\n{path}\n\n"
            "Please attach that file to your bug report -- it names the exact line "
            "that failed."
        )
        box.exec() if hasattr(box, "exec") else box.exec_()
    except Exception:
        pass


def install(notify: bool = True) -> None:
    """Route every unhandled exception to the log. Safe to call more than once."""
    global _installed
    if _installed:
        return
    _installed = True

    def _hook(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            return
        path = write_report(exc_type, exc_value, exc_tb, "main thread")
        if notify:
            _notify(path, exc_value)

    sys.excepthook = _hook

    # Worker threads. QThread.run() exceptions surface here, which is where a failing
    # conversion would land -- the exact path the Windows 7 report implicates.
    if hasattr(threading, "excepthook"):          # 3.8+, so present on the Win7 build too
        def _thread_hook(args):
            if issubclass(args.exc_type, KeyboardInterrupt):
                return
            name = getattr(args.thread, "name", "?")
            write_report(args.exc_type, args.exc_value, args.exc_traceback,
                         f"thread {name}")
        threading.excepthook = _thread_hook

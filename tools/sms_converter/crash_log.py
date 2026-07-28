"""Crash reporting and a flight recorder, because a --windowed build cannot report anything.

WHY THIS EXISTS
---------------
Both shipped executables are PyInstaller `--onefile --windowed`. Windowed means no console,
which on Windows leaves `sys.stdout` and `sys.stderr` as None. An unhandled exception goes
nowhere: Python's default hook tries to write a traceback to a stream that does not exist and
the process simply disappears.

A Windows 7 tester hit exactly that -- "every time I hit convert, app closes" -- with no
message and no log. The first attempt at this file added sys.excepthook and
threading.excepthook, and it STILL produced no log on his machine. That result is the reason
this file now looks the way it does, because it ruled out the easy explanation and left only
two:

  1. QThread does NOT go through threading.excepthook. A QThread's run() is invoked from C++,
     not from threading.Thread._bootstrap_inner, so that hook is simply not in the path. The
     conversion runs in a QThread. This was a real hole in the first version.

  2. A NATIVE crash -- an access violation inside Qt or Shiboken -- kills the process before
     Python regains control. No Python-level hook can ever catch that, which is why the log
     stayed empty.

So there are now three independent nets, and they degrade rather than replace each other:

  * faulthandler       -- catches SIGSEGV / access violations and dumps a C-level traceback.
                          This is the ONLY thing that can report cause 2.
  * excepthooks        -- ordinary Python exceptions, main thread and threading threads.
  * breadcrumbs        -- an append-and-flush trail of what the app was doing. Survives ANY
                          death, including a hard kill, because every line is on disk before
                          the next step begins.

The breadcrumb idea is lifted from the E-code trail that cracked the PS2 exit hang: when a
process dies without saying why, the last thing it managed to write IS the diagnosis.

THE LOG IS OPENED AND WRITTEN AT STARTUP, deliberately. If the file does not exist at all,
that is itself a finding -- it means the build could not write there -- and it must not be
confused with "the app never crashed".
"""

import os
import sys
import faulthandler
import platform
import threading
import traceback
from datetime import datetime
from pathlib import Path

LOG_NAME = "sms-converter-crash.log"

_installed = False
_log_path = None
_fault_fh = None          # kept open for the process lifetime; faulthandler needs a live fd
_lock = threading.Lock()


def _candidate_dirs():
    """Where to try writing, best first."""
    if getattr(sys, "frozen", False):
        yield Path(sys.executable).parent
    else:
        yield Path(__file__).resolve().parent
    yield Path.home()
    import tempfile
    yield Path(tempfile.gettempdir())


def crash_log_path() -> Path:
    """Resolve a writable location for the log, once. Never raises."""
    global _log_path
    if _log_path is not None:
        return _log_path
    for d in _candidate_dirs():
        try:
            d.mkdir(parents=True, exist_ok=True)
            probe = d / (LOG_NAME + ".probe")
            probe.write_text("", encoding="utf-8")
            probe.unlink()
            _log_path = d / LOG_NAME
            return _log_path
        except Exception:
            continue
    _log_path = Path(LOG_NAME)          # cwd, last resort
    return _log_path


def _append(text: str) -> None:
    """Write and FLUSH immediately. Never raises.

    Flushing per line is the whole point: a buffered line is a line that dies with the
    process, and the interesting cases here are precisely the ones where the process dies.
    """
    try:
        with _lock:
            with open(crash_log_path(), "a", encoding="utf-8") as fh:
                fh.write(text)
                fh.flush()
                os.fsync(fh.fileno())
    except Exception:
        pass


def breadcrumb(msg: str) -> None:
    """Record that the app reached a point. The last one written is where it died."""
    _append(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n")


def _environment() -> str:
    try:
        from qt_compat import QT_BINDING
    except Exception:
        QT_BINDING = "unknown"
    return (
        f"  started  : {datetime.now().isoformat(timespec='seconds')}\n"
        f"  python   : {sys.version.split()[0]}\n"
        f"  qt       : {QT_BINDING}\n"
        f"  platform : {platform.platform()}\n"
        f"  frozen   : {bool(getattr(sys, 'frozen', False))}\n"
        f"  exe      : {sys.executable}\n"
    )


def write_report(exc_type, exc_value, exc_tb, context: str = "") -> Path:
    """Append one crash report. Never raises."""
    try:
        body = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        _append("\n" + "!" * 78 + "\nUNHANDLED EXCEPTION"
                + (f" ({context})" if context else "") + "\n" + body + "!" * 78 + "\n")
    except Exception:
        pass
    return crash_log_path()


def _notify(path: Path, exc_value) -> None:
    """Tell the user, but only if Qt is still up. Never raises."""
    try:
        from qt_compat import QApplication, QMessageBox
        if QApplication.instance() is None:
            return
        box = QMessageBox()
        box.setIcon(QMessageBox.Critical)
        box.setWindowTitle("SMS Media Converter - unexpected error")
        box.setText("Something went wrong. The details were saved to a log file.")
        box.setInformativeText(
            f"{type(exc_value).__name__}: {exc_value}\n\nLog file:\n{path}\n\n"
            "Please attach that file to your bug report."
        )
        box.exec() if hasattr(box, "exec") else box.exec_()
    except Exception:
        pass


def guard(context: str):
    """Decorator that logs anything escaping a function, then re-raises.

    For QThread.run(), which neither excepthook reaches: PySide invokes it from C++, so an
    escaping exception is reported by Qt (or not at all) and never touches threading.excepthook.
    """
    def deco(fn):
        def wrapper(*a, **kw):
            try:
                return fn(*a, **kw)
            except BaseException:
                write_report(*sys.exc_info(), context=context)
                raise
        wrapper.__name__ = getattr(fn, "__name__", "wrapped")
        return wrapper
    return deco


def install(notify: bool = True) -> None:
    """Install every net. Safe to call more than once."""
    global _installed, _fault_fh
    if _installed:
        return
    _installed = True

    path = crash_log_path()
    _append("\n" + "=" * 78 + "\nSMS Media Converter starting\n" + _environment())

    # NATIVE crashes. The only net that can catch an access violation inside Qt/Shiboken,
    # which is a live hypothesis for the Windows 7 report precisely BECAUSE the Python-level
    # hooks produced nothing. The handle is deliberately leaked for the process lifetime --
    # faulthandler writes through it during the crash, so it must outlive everything.
    try:
        _fault_fh = open(path, "a", encoding="utf-8", buffering=1)
        faulthandler.enable(file=_fault_fh, all_threads=True)
    except Exception:
        pass

    def _hook(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            return
        p = write_report(exc_type, exc_value, exc_tb, "main thread")
        if notify:
            _notify(p, exc_value)

    sys.excepthook = _hook

    if hasattr(threading, "excepthook"):          # 3.8+, so the Win7 build has it too
        def _thread_hook(args):
            if issubclass(args.exc_type, KeyboardInterrupt):
                return
            write_report(args.exc_type, args.exc_value, args.exc_traceback,
                         f"thread {getattr(args.thread, 'name', '?')}")
        threading.excepthook = _thread_hook

    breadcrumb("crash handling installed")

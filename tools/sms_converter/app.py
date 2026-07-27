"""
Application launcher and Qt environment initialization.
"""
import os
import sys
from qt_compat import QApplication, dialog_exec, app_exec, DIALOG_ACCEPTED
from qt_compat import QPalette, QColor, QIcon
from ffmpeg_utils import find_ffmpeg_binaries
from ui.setup_dialog import SetupDialog
from ui.main_window import MainWindow


def resource_path(*parts):
    """Resolve a bundled asset both when run from source and from a PyInstaller --onefile exe.

    A one-file build unpacks to a temporary directory at run time and exposes it as
    sys._MEIPASS; the ordinary __file__ path points inside the archive and does not exist on
    disk. Getting this wrong is silent -- the icon simply never appears -- so it is resolved
    in one place.
    """
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, *parts)


def app_icon():
    """The window/taskbar icon, or a null QIcon if the asset is missing.

    Never raises: a missing icon must not stop the converter from starting.
    """
    path = resource_path("assets", "sms-converter.ico")
    return QIcon(path) if os.path.exists(path) else QIcon()

DARK_STYLESHEET = """
QMainWindow, QDialog {
    background-color: #171923;
}
QWidget {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    color: #E2E8F0;
}
QToolTip {
    background-color: #2D3748;
    color: white;
    border: 1px solid #4A5568;
    padding: 4px;
}
"""

def run_app():
    app = QApplication(sys.argv)
    # Set on the QApplication so every window, dialog and the taskbar entry inherit it.
    app.setWindowIcon(app_icon())
    app.setStyleSheet(DARK_STYLESHEET)

    # 1. Search for FFmpeg binaries
    ffmpeg_path, ffprobe_path = find_ffmpeg_binaries()

    if not ffmpeg_path or not ffprobe_path:
        setup_dlg = SetupDialog()
        if dialog_exec(setup_dlg) == DIALOG_ACCEPTED:
            ffmpeg_path = setup_dlg.ffmpeg_path
            ffprobe_path = setup_dlg.ffprobe_path
        else:
            sys.exit(0)

    # 2. Launch Main Window
    window = MainWindow(ffmpeg_path, ffprobe_path)
    window.show()
    sys.exit(app_exec(app))

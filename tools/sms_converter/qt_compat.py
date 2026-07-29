"""Qt binding shim so one codebase builds for both modern Windows and Windows 7.

WHY THIS EXISTS
---------------
Users on Windows 7 could not run the converter at all. The cause is a hard platform floor,
not a bug we can patch around:

  * Qt 6 (and therefore PySide6) requires Windows 10. Qt dropped Windows 7 entirely.
  * CPython 3.9+ dropped Windows 7 support. 3.8 is the last release that runs there.

So a Windows 7 build has to be Python 3.8 + PySide2 (Qt 5). Rather than fork the app, every
module imports Qt through this shim: it prefers PySide6 and falls back to PySide2, and
papers over the handful of places the two APIs differ.

Keeping ONE codebase matters more than it looks -- a forked Win7 copy would quietly drift
out of sync with the preset and validator changes, which are precisely the parts that decide
whether the output plays on a PS2 at all.

WHAT DIFFERS, and how it is handled here
----------------------------------------
1. QDialog.exec() vs exec_().  Qt 5 named it exec_() because `exec` was a keyword in
   Python 2. Call `dialog_exec(dlg)` instead of either spelling.
2. Scoped enums.  Qt 6 prefers QDialog.DialogCode.Accepted; Qt 5 only has QDialog.Accepted.
   Use the DIALOG_ACCEPTED constant exported here.
3. QApplication.exec() vs exec_().  Use `app_exec(app)`.

Everything else this app touches -- the widget set, Qt.AlignCenter-style flags, Signal,
QThread, QPalette/QColor -- is spelled identically in both bindings, which is why the shim
stays this small.
"""

QT_BINDING = None

try:                                             # modern Windows / Linux
    from PySide6 import QtCore, QtGui, QtWidgets
    QT_BINDING = "PySide6"
except ImportError:                              # Windows 7 fallback
    from PySide2 import QtCore, QtGui, QtWidgets
    QT_BINDING = "PySide2"

# --- re-exports, so callers never import a binding directly ---------------------------
Qt = QtCore.Qt
Signal = QtCore.Signal
Slot = QtCore.Slot
QThread = QtCore.QThread
QTimer = QtCore.QTimer

QPalette = QtGui.QPalette
QColor = QtGui.QColor
QIcon = QtGui.QIcon
QPixmap = QtGui.QPixmap

QApplication = QtWidgets.QApplication
QWidget = QtWidgets.QWidget
QDialog = QtWidgets.QDialog
QMainWindow = QtWidgets.QMainWindow
QLabel = QtWidgets.QLabel
QPushButton = QtWidgets.QPushButton
QComboBox = QtWidgets.QComboBox
QCheckBox = QtWidgets.QCheckBox
QSpinBox = QtWidgets.QSpinBox
QLineEdit = QtWidgets.QLineEdit
QFileDialog = QtWidgets.QFileDialog
QMessageBox = QtWidgets.QMessageBox
QVBoxLayout = QtWidgets.QVBoxLayout
QHBoxLayout = QtWidgets.QHBoxLayout
QFormLayout = QtWidgets.QFormLayout
QGridLayout = QtWidgets.QGridLayout
QGroupBox = QtWidgets.QGroupBox
QFrame = QtWidgets.QFrame
QProgressBar = QtWidgets.QProgressBar
QTableWidget = QtWidgets.QTableWidget
QTableWidgetItem = QtWidgets.QTableWidgetItem
QHeaderView = QtWidgets.QHeaderView
QAbstractItemView = QtWidgets.QAbstractItemView
QSizePolicy = QtWidgets.QSizePolicy
QScrollArea = QtWidgets.QScrollArea
QTextEdit = QtWidgets.QTextEdit
QDialogButtonBox = QtWidgets.QDialogButtonBox
QStyle = QtWidgets.QStyle
QMenu = QtWidgets.QMenu
QTabWidget = QtWidgets.QTabWidget

# --- normalised bits ------------------------------------------------------------------

# Qt 6 exposes QDialog.DialogCode.Accepted; Qt 5 only QDialog.Accepted.
try:
    DIALOG_ACCEPTED = QtWidgets.QDialog.DialogCode.Accepted
except AttributeError:
    DIALOG_ACCEPTED = QtWidgets.QDialog.Accepted


def dialog_exec(dlg):
    """Run a modal dialog on either binding and return its result code."""
    runner = getattr(dlg, "exec", None) or getattr(dlg, "exec_")
    return runner()


def menu_exec(menu, pos):
    """Pop up a context menu at `pos` on either binding, returning the chosen action.

    PySide2 has only QMenu.exec_; PySide6 added QMenu.exec. Calling .exec directly raises
    AttributeError on the Windows 7 build -- which turned every right-click in the queue into
    a crash dialog there, on a binding the owner cannot test locally.
    """
    runner = getattr(menu, "exec", None) or getattr(menu, "exec_")
    return runner(pos)


def app_exec(app):
    """Enter the application event loop on either binding."""
    runner = getattr(app, "exec", None) or getattr(app, "exec_")
    return runner()

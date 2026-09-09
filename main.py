"""HxSSH 远程监控 — 入口。"""
import os
import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from hxssh.ui.main_window import MainWindow
from hxssh.ui.styles import STYLESHEET


def _asset_path(rel):
    """兼容 PyInstaller onefile（sys._MEIPASS）与源码运行的资源路径。"""
    base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName('HxSSH 远程监控')
    icon = _asset_path(os.path.join('assets', 'icon.ico'))
    if os.path.exists(icon):
        app.setWindowIcon(QIcon(icon))
    app.setStyle('Fusion')
    app.setStyleSheet(STYLESHEET)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()

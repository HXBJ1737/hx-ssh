"""HxSSH 远程监控 — 入口。"""
import sys

from PySide6.QtWidgets import QApplication

from hxssh.ui.main_window import MainWindow
from hxssh.ui.styles import STYLESHEET


def main():
    app = QApplication(sys.argv)
    app.setApplicationName('HxSSH 远程监控')
    app.setStyle('Fusion')
    app.setStyleSheet(STYLESHEET)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()

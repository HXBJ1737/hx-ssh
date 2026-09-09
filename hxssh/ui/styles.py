 # __BASE__ 全局字号，__BIG__/__TITLE__ 按基准推导
_TEMPLATE = """
* { font-size: __BASE__px; }
QMainWindow, QWidget#LoginRoot { background: #17181d; }
QFrame[card="true"] { background: #202229; border: 1px solid #2d3038; border-radius: 12px; }
QLabel { color: #d7dae0; background: transparent; }
QLabel#BigTitle { font-size: __BIG__px; font-weight: 700; color: #ffffff; }
QLabel#SubTitle { color: #8f96a3; font-size: __BASE__px; }
QLabel#CardTitle { color: #8f96a3; font-size: __TITLE__px; font-weight: 600; letter-spacing: 1px; }
QLabel#InfoText { color: #b8bec9; }
QLabel#ErrorText { color: #f28b82; }
QLineEdit, QSpinBox, QComboBox {
  background: #1a1c22; border: 1px solid #363b48; border-radius: 8px;
  padding: 7px 10px; color: #e7e9ee; selection-background-color: #4f8cff;
}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus { border: 1px solid #4f8cff; }
QComboBox::drop-down { border: none; width: 24px; }
QComboBox QAbstractItemView {
  background: #23252d; color: #e7e9ee; border: 1px solid #3a3f4d;
  selection-background-color: #31435f; outline: none;
}
QPushButton {
  background: #2b2e37; color: #e7e9ee; border: none; border-radius: 8px; padding: 8px 16px;
}
QPushButton:hover { background: #353945; }
QPushButton:disabled { color: #6f7480; background: #262932; }
QPushButton#Primary { background: #4f8cff; color: #ffffff; font-weight: 600; }
QPushButton#Primary:hover { background: #3f7bef; }
QPushButton#Danger { background: #a8383a; color: #ffffff; }
QPushButton#Danger:hover { background: #b84345; }
QCheckBox { color: #b8bec9; spacing: 6px; background: transparent; }
QTableWidget {
  background: #1b1d23; alternate-background-color: #1f2129; border: none;
  gridline-color: #262932; color: #d7dae0;
}
QHeaderView::section {
  background: #202229; color: #8f96a3; border: none;
  border-bottom: 1px solid #2d3038; padding: 6px 8px; font-weight: 600;
}
QTableCornerButton::section { background: #202229; border: none; }
QTableWidget::item { padding: 2px 4px; }
QTableWidget::item:selected { background: #2d3f63; color: #ffffff; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: #3a3f4d; border-radius: 5px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: #4a505f; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
QScrollBar::handle:horizontal { background: #3a3f4d; border-radius: 5px; min-width: 30px; }
QScrollBar::handle:horizontal:hover { background: #4a505f; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: transparent; }
QMessageBox { background: #202229; }
QMessageBox QLabel { color: #d7dae0; }
QToolTip { background: #2a2d36; color: #e7e9ee; border: 1px solid #3a3f4d; padding: 4px; }
QScrollArea { background: transparent; border: none; }
QScrollArea > QWidget > QWidget { background: transparent; }
QSplitter::handle { background: #262932; }
QSplitter::handle:vertical {
  height: 8px; min-height: 8px; margin: 3px 10px;
  border-radius: 4px;
}
QSplitter::handle:vertical:hover { background: #4f8cff; }
QChartView { background: transparent; border: none; }
"""


def build_stylesheet(base: int = 13) -> str:
    """按基准字号生成全局样式。"""
    base = max(10, int(base))
    return (_TEMPLATE
            .replace('__BASE__', str(base))
            .replace('__BIG__', str(base + 9))
            .replace('__TITLE__', str(max(10, base - 1))))


STYLESHEET = build_stylesheet()

"""进程表：排序 / 搜索 / 暂停 / 结束进程。"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QHBoxLayout,
                               QHeaderView, QLabel, QLineEdit, QMessageBox,
                               QPushButton, QTableWidget, QTableWidgetItem,
                               QVBoxLayout, QWidget)

from ..utils import fmt_kb


class NumItem(QTableWidgetItem):
    """带数值排序的表格项。"""

    def __init__(self, text, value):
        super().__init__(text)
        self.setData(Qt.ItemDataRole.UserRole, value)

    def __lt__(self, other):
        a = self.data(Qt.ItemDataRole.UserRole)
        b = other.data(Qt.ItemDataRole.UserRole)
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            return a < b
        return self.text().casefold() < other.text().casefold()


class ProcessTable(QWidget):
    kill_requested = Signal(int, str)

    COLS = [('PID', 50), ('用户', 50), ('CPU%', 60), ('内存', 60), ('内存%', 55),
            ('状态', 50), ('启动', 60), ('t(CPU)', 60), ('命令', 0)]

    def __init__(self, parent=None):
        super().__init__(parent)
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(8)

        bar = QHBoxLayout()
        self.ed_search = QLineEdit()
        self.ed_search.setPlaceholderText('搜索进程名 / 用户 / PID')
        self.ed_search.setClearButtonEnabled(True)
        self.ed_search.setMinimumWidth(50)
        self.ed_search.setMaximumWidth(260)
        self.cb_pause = QCheckBox('暂停刷新')
        self.lb_count = QLabel('')
        self.lb_count.setObjectName('SubTitle')
        self.btn_kill = QPushButton('结束进程')
        self.btn_kill.setObjectName('Danger')
        self.btn_kill.setToolTip('对选中进程执行 kill -9（不可恢复）；\n权限不足时自动用 sudo 提权重试')
        bar.addWidget(self.ed_search)
        bar.addWidget(self.cb_pause)
        bar.addStretch(1)
        bar.addWidget(self.lb_count)
        bar.addWidget(self.btn_kill)
        v.addLayout(bar)

        self.table = QTableWidget(0, len(self.COLS))
        self.table.setHorizontalHeaderLabels([c[0] for c in self.COLS])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        header = self.table.horizontalHeader()
        header.setStretchLastSection(True)
        for i, (_name, w) in enumerate(self.COLS[:-1]):
            self.table.setColumnWidth(i, w)
        header.setSortIndicator(2, Qt.SortOrder.DescendingOrder)  # 默认按 CPU% 排序
        self.table.setSortingEnabled(True)
        self.table.setMinimumHeight(100)
        v.addWidget(self.table, 1)

        self._procs = []
        self._row_keys = []

        self.ed_search.textChanged.connect(self._apply_filter)
        self.btn_kill.clicked.connect(self._emit_kill)

    # ------ 数据更新 ------
    def update_procs(self, procs):
        if self.cb_pause.isChecked():
            return
        self._procs = procs
        old_pid = self._sel_pid()
        vbar = self.table.verticalScrollBar()
        prev_pos = vbar.value()
        t = self.table
        t.setSortingEnabled(False)
        t.setRowCount(len(procs))
        self._row_keys = []
        for r, pr in enumerate(procs):
            items = [
                NumItem(str(pr['pid']), pr['pid']),
                QTableWidgetItem(pr['user']),
                NumItem(f"{pr['cpu']:.1f}", round(pr['cpu'], 1)),
                NumItem(fmt_kb(pr['rss_kb']), pr['rss_kb']),
                NumItem(f"{pr['mem_pct']:.1f}", round(pr['mem_pct'], 1)),
                QTableWidgetItem(pr['stat']),
                QTableWidgetItem(pr['start']),
                QTableWidgetItem(pr['time']),
                QTableWidgetItem(pr['cmd']),
            ]
            for c, it in enumerate(items):
                t.setItem(r, c, it)
            self._row_keys.append(f"{pr['pid']}\n{pr['user'].lower()}\n{pr['cmd'].lower()}")
        t.setSortingEnabled(True)
        if old_pid is not None:
            for r in range(t.rowCount()):
                it = t.item(r, 0)
                if it is not None and it.data(Qt.ItemDataRole.UserRole) == old_pid:
                    t.selectRow(r)  # 仅恢复选中高亮，不滚动视口
                    break
        # 稳定视口：刷新前后滚动位置保持不变，避免排序抖动导致视口漂移
        vbar.setValue(min(prev_pos, vbar.maximum()))
        self._apply_filter()

    def _apply_filter(self):
        q = self.ed_search.text().strip().lower()
        vis = 0
        for r, key in enumerate(self._row_keys):
            hide = bool(q) and q not in key
            self.table.setRowHidden(r, hide)
            if not hide:
                vis += 1
        self.lb_count.setText(f'显示 {vis} / 共 {len(self._procs)} 个进程')

    # ------ 选择 / 操作 ------
    def _sel_row(self):
        rows = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        return rows[0].row() if rows else None

    def _sel_pid(self):
        r = self._sel_row()
        if r is None:
            return None
        it = self.table.item(r, 0)
        if it is None:
            return None
        v = it.data(Qt.ItemDataRole.UserRole)
        return int(v) if v is not None else None

    def _emit_kill(self):
        r = self._sel_row()
        if r is None:
            QMessageBox.information(self, '提示', '请先在表格中选择一个进程。')
            return
        pid_it = self.table.item(r, 0)
        cmd_it = self.table.item(r, 8)
        pid = int(pid_it.data(Qt.ItemDataRole.UserRole))
        cmd = cmd_it.text() if cmd_it else ''
        self.kill_requested.emit(pid, cmd)

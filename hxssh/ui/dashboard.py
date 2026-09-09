"""监控仪表盘：CPU / 内存 / 磁盘 / 网络 / 进程。"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QGridLayout, QHBoxLayout,
                               QLabel, QPushButton, QScrollArea, QSizePolicy,
                               QSplitter, QVBoxLayout, QWidget)

from ..utils import fmt_bytes, fmt_kb, fmt_rate, fmt_uptime
from .process_table import ProcessTable
from .widgets import Card, CoreGridWidget, LineChart, MiniBar


class Dashboard(QWidget):
    disconnect_requested = Signal()
    interval_changed = Signal(float)
    font_changed = Signal(int)
    kill_requested = Signal(int, str)
    topmost_changed = Signal(bool)

    def __init__(self, interval=2.0, font_px=13, cfg=None, parent=None):
        super().__init__(parent)
        self._base = ''
        self._disk_keys = []
        self._disk_bars = {}
        self._cfg = cfg or {}

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 12)
        root.setSpacing(10)

        # ---- 顶部信息条 ----
        top = QHBoxLayout()
        self.lb_info = QLabel('未连接')
        self.lb_info.setObjectName('InfoText')
        self.lb_info.setMinimumWidth(0)
        self.lb_info.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.cb_interval = QComboBox()
        for s in (1, 2, 3, 5):
            self.cb_interval.addItem(f'{s} 秒', s)
        idx = self.cb_interval.findData(int(interval))
        self.cb_interval.setCurrentIndex(idx if idx >= 0 else 1)
        self.cb_font = QComboBox()
        for label, px in (('小', 12), ('标准', 13), ('大', 14), ('特大', 16)):
            self.cb_font.addItem(f'字体 {label}', px)
        fidx = self.cb_font.findData(int(font_px))
        self.cb_font.setCurrentIndex(fidx if fidx >= 0 else 1)
        btn_disc = QPushButton('断开连接')
        btn_disc.clicked.connect(self.disconnect_requested.emit)
        top.addWidget(self.lb_info, 1)
        top.addWidget(QLabel('刷新间隔'))
        top.addWidget(self.cb_interval)
        top.addWidget(self.cb_font)
        top.addSpacing(6)
        self.cb_disk = QCheckBox('磁盘')
        self.cb_net = QCheckBox('网络')
        self.cb_disk.setChecked(True)
        self.cb_net.setChecked(True)
        top.addWidget(self.cb_disk)
        top.addWidget(self.cb_net)
        top.addSpacing(6)
        self.cb_topmost = QCheckBox('置顶')
        self.cb_topmost.setChecked(self._cfg.get('always_on_top', False))
        top.addWidget(self.cb_topmost)
        top.addWidget(btn_disc)
        root.addLayout(top)

        # ---- 上下可拖拽分割：监控卡片 ↔ 进程列表 ----
        # 往下拖手柄 = 看更多进程；把手柄拖到顶可完全收起监控卡片
        cards_zone = QWidget()
        cards_lay = QVBoxLayout(cards_zone)
        cards_lay.setContentsMargins(0, 0, 0, 0)
        cards_lay.setSpacing(0)
        self._grid = self._build_cards()
        cards_lay.addLayout(self._grid)
        proc_card = Card('进程列表')
        self.ptable = ProcessTable()
        proc_card.body.addWidget(self.ptable, 1)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setHandleWidth(10)
        splitter.addWidget(cards_zone)
        splitter.addWidget(proc_card)
        splitter.setCollapsible(0, True)   # 卡片区可被拖到完全收起
        splitter.setCollapsible(1, False)  # 进程列表不会被拖没
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([430, 204])
        root.addWidget(splitter, 1)

        btn_disc.clicked.connect(self.disconnect_requested.emit)
        self.cb_interval.currentIndexChanged.connect(self._interval_changed)
        self.cb_font.currentIndexChanged.connect(self._font_changed)
        self.cb_disk.toggled.connect(self._update_card_layout)
        self.cb_net.toggled.connect(self._update_card_layout)
        self.cb_topmost.toggled.connect(self.topmost_toggled)
        self.ptable.kill_requested.connect(self.kill_requested.emit)

    # ------ 卡片开关 ------
    def _update_card_layout(self):
        """按开关显示/隐藏磁盘与网络卡片；单独开启时占满整行。"""
        show_disk = self.cb_disk.isChecked()
        show_net = self.cb_net.isChecked()
        self.disk_card.setVisible(show_disk)
        self.net_card.setVisible(show_net)
        grid = self._grid
        grid.removeWidget(self.disk_card)
        grid.removeWidget(self.net_card)
        if show_disk and show_net:
            grid.addWidget(self.disk_card, 1, 0)
            grid.addWidget(self.net_card, 1, 1)
        elif show_disk:
            grid.addWidget(self.disk_card, 1, 0, 1, 2)
        elif show_net:
            grid.addWidget(self.net_card, 1, 0, 1, 2)

    # ------ 构建卡片 ------
    def _build_cards(self):
        grid = _Grid()

        self.cpu_card = Card('CPU 使用率')
        row = QHBoxLayout()
        row.setSpacing(10)
        self.cpu_chart = LineChart([('CPU %', '#4f8cff')], y_max=100)
        self.cpu_chart.setMinimumHeight(50)
        self.cores = CoreGridWidget()
        self.cores.setMinimumWidth(150)
        self.cores.setMaximumWidth(640)
        row.addWidget(self.cpu_chart, 3)
        row.addWidget(self.cores, 2)
        self.cpu_card.body.addLayout(row)

        mem_card = Card('内存 / 交换分区')
        self.bar_mem = MiniBar()
        self.bar_mem.setMinimumHeight(26)
        self.bar_swap = MiniBar()
        self.bar_swap.setMinimumHeight(26)
        self.lb_mem_detail = QLabel('')
        self.lb_mem_detail.setObjectName('SubTitle')
        mem_card.body.addWidget(self.bar_mem)
        mem_card.body.addWidget(self.bar_swap)
        mem_card.body.addWidget(self.lb_mem_detail)
        mem_card.body.addStretch(1)

        self.disk_card = Card('磁盘使用率')
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        self.disk_lay = QVBoxLayout(inner)
        self.disk_lay.setContentsMargins(0, 0, 4, 0)
        self.disk_lay.setSpacing(6)
        self.disk_lay.addStretch(1)
        scroll.setWidget(inner)
        self.disk_card.body.addWidget(scroll)

        self.net_card = Card('网络速率')
        nrow = QHBoxLayout()
        nrow.setSpacing(14)
        self.lb_net_rx = QLabel('↓ 下行 --')
        self.lb_net_rx.setStyleSheet('color:#3fb27f; font-weight:600;')
        self.lb_net_tx = QLabel('↑ 上行 --')
        self.lb_net_tx.setStyleSheet('color:#f2a33c; font-weight:600;')
        self.lb_net_total = QLabel('')
        self.lb_net_total.setObjectName('SubTitle')
        nrow.addWidget(self.lb_net_rx)
        nrow.addWidget(self.lb_net_tx)
        nrow.addStretch(1)
        nrow.addWidget(self.lb_net_total)
        self.net_card.body.addLayout(nrow)
        self.net_chart = LineChart([('下行 RX', '#3fb27f'), ('上行 TX', '#f2a33c')])
        self.net_chart.setMinimumHeight(50)
        self.net_card.body.addWidget(self.net_chart)

        grid.addWidget(self.cpu_card, 0, 0)
        grid.addWidget(mem_card, 0, 1)
        grid.addWidget(self.disk_card, 1, 0)
        grid.addWidget(self.net_card, 1, 1)
        grid.setColumnStretch(0, 3)
        grid.setColumnStretch(1, 2)
        return grid

    # ------ 槽 ------
    def _interval_changed(self):
        self.interval_changed.emit(float(self.cb_interval.currentData() or 2))

    def _font_changed(self):
        self.font_changed.emit(int(self.cb_font.currentData() or 13))

    def topmost_toggled(self, checked):
        self.topmost_changed.emit(checked)

    def set_sysinfo(self, info):
        self._base = (f"{info.get('host', '')}  ·  {info.get('os', '')}  ·  "
                      f"{info.get('kernel', '')}  ·  {info.get('arch', '')}")
        self.lb_info.setText(self._base)

    def update_sample(self, s):
        cpu = s['cpu']
        self.cpu_card.set_title(f"CPU 使用率 · {cpu['count']} 核 · 当前 {cpu['usage']:.0f}%")
        self.cpu_chart.add([round(cpu['usage'], 1)])
        self.cores.set_cores(cpu['cores'])

        mem = s['mem']
        self.bar_mem.set_value(
            '内存', mem['pct'],
            f"{fmt_kb(mem['used'])} / {fmt_kb(mem['total'])}  ·  {mem['pct']:.0f}%")
        self.bar_swap.set_value(
            '交换分区', mem['swap_pct'],
            f"{fmt_kb(mem['swap_used'])} / {fmt_kb(mem['swap_total'])}  ·  {mem['swap_pct']:.0f}%"
            if mem['swap_total'] else '未启用')
        self.lb_mem_detail.setText(
            f"可用 {fmt_kb(mem['avail'])}  ·  缓冲/缓存 {fmt_kb(mem['buffers'] + mem['cached'])}")

        self._sync_disks(s['disk'])
        net = s['net']
        self.lb_net_rx.setText(f"↓ 下行 {fmt_rate(net['rx_rate'])}")
        self.lb_net_tx.setText(f"↑ 上行 {fmt_rate(net['tx_rate'])}")
        self.lb_net_total.setText(
            f"累计 ↓ {fmt_bytes(net['rx_total'])} · ↑ {fmt_bytes(net['tx_total'])}")
        self.net_chart.add([net['rx_rate'] / 1024.0, net['tx_rate'] / 1024.0])
        self.ptable.update_procs(s['procs'])

        l = s['load']
        self.lb_info.setText(
            f"{self._base}    ·    已运行 {fmt_uptime(s['uptime'])}    ·    "
            f"负载 {l[0]:.2f} / {l[1]:.2f} / {l[2]:.2f}"
        )

    def _sync_disks(self, disks):
        mounts = [d['mount'] for d in disks]
        if mounts != self._disk_keys:
            while self.disk_lay.count() > 1:
                item = self.disk_lay.takeAt(0)
                w = item.widget()
                if w:
                    w.deleteLater()
            self._disk_bars = {}
            for d in disks:
                b = MiniBar()
                b.setMinimumHeight(26)
                self._disk_bars[d['mount']] = b
                self.disk_lay.insertWidget(self.disk_lay.count() - 1, b)
            self._disk_keys = mounts
        for d in disks:
            b = self._disk_bars.get(d['mount'])
            if b:
                b.set_value(f"{d['mount']}   ({d['dev']})", d['pct'],
                            f"{fmt_kb(d['used_kb'])} / {fmt_kb(d['total_kb'])}  ·  {d['pct']:.0f}%")


class _Grid(QGridLayout):
    """小包装，避免在 __init__ 里到处 import。"""

    def __init__(self):
        super().__init__()
        self.setSpacing(10)

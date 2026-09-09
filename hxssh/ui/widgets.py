"""自绘监控控件：卡片、环形仪表、核心负载条、实时曲线。"""
from __future__ import annotations

import math
from collections import deque

from PySide6.QtCharts import (QAreaSeries, QChart, QChartView, QLineSeries,
                              QValueAxis)
from PySide6.QtCore import QMargins, QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QVBoxLayout, QWidget

from .. import utils
from ..utils import clamp, level_color


class Card(QFrame):
    def __init__(self, title='', parent=None):
        super().__init__(parent)
        self.setProperty('card', 'true')
        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 12, 14, 14)
        outer.setSpacing(8)
        self.title_label = QLabel(title)
        self.title_label.setObjectName('CardTitle')
        outer.addWidget(self.title_label)
        self.body = QVBoxLayout()
        self.body.setContentsMargins(0, 0, 0, 0)
        self.body.setSpacing(8)
        outer.addLayout(self.body)

    def set_title(self, text):
        self.title_label.setText(text)


class MiniBar(QWidget):
    """单行水平负载条（CPU 核 / 磁盘）。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._label = ''
        self._right = ''
        self._pct = 0.0
        self.setMinimumHeight(22)
        self.setMinimumWidth(80)

    def set_value(self, label, pct, right=''):
        self._label = label
        self._pct = clamp(float(pct), 0.0, 100.0)
        self._right = right
        self.update()

    def paintEvent(self, ev):  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -1.5, -1.5)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor('#272a33'))
        p.drawRoundedRect(r, 6, 6)
        if self._pct > 0:
            fw = max(6.0, r.width() * self._pct / 100.0)
            p.setBrush(QColor(level_color(self._pct)))
            p.drawRoundedRect(QRectF(r.left(), r.top(), fw, r.height()), 6, 6)
        p.setPen(QColor('#c9cedb'))
        f = QFont()
        f.setPixelSize(max(9, utils.BASE_FONT_PX - 2))
        p.setFont(f)
        tr = r.adjusted(8, 0, -8, 0)
        p.drawText(tr, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self._label)
        p.drawText(tr, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, self._right)


class CoreGridWidget(QWidget):
    """每核负载条网格，核数变化时自动重建。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setSpacing(6)
        self._bars = []

    def set_cores(self, usages):
        n = len(usages)
        if n != len(self._bars):
            for b in self._bars:
                self._grid.removeWidget(b)
                b.deleteLater()
            self._bars = []
            cols = 1 if n <= 4 else max(2, math.ceil(n / 8))
            for i in range(n):
                b = MiniBar(self)
                self._bars.append(b)
                self._grid.addWidget(b, i // cols, i % cols)
        for i, (b, v) in enumerate(zip(self._bars, usages)):
            b.set_value(f'CPU{i}', v, f'{v:.0f}%')


_NICE = [10, 25, 50, 100, 200, 500, 1000, 2500, 5000, 10000, 25000, 50000,
         100000, 250000, 500000, 1000000, 2500000, 5000000]


def _nice_ceiling(v):
    if v <= 0:
        return 10
    for c in _NICE:
        if v <= c:
            return c
    return int(v * 1.2)


class LineChart(QChartView):
    """滚动窗口实时折线图；第一个序列带面积填充，Y 轴可动态。"""

    def __init__(self, series_defs, *, y_max=None, window=150, parent=None):
        super().__init__(parent)
        self.setStyleSheet('background: transparent; border: none;')
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self._window = window
        self._fixed = y_max is not None
        self._bufs = [deque(maxlen=window) for _ in series_defs]
        self._series = []

        chart = QChart()
        chart.setBackgroundVisible(False)
        chart.setMargins(QMargins(2, 2, 2, 2))
        chart.setAnimationOptions(QChart.AnimationOption.NoAnimation)

        ax_x = QValueAxis()
        ax_x.setRange(0, window - 1)
        ax_x.setTickCount(5)
        ax_x.setLabelsVisible(False)
        ax_x.setLineVisible(False)
        ax_x.setGridLineVisible(False)

        self._ax_y = QValueAxis()
        self._ax_y.setRange(0, y_max if y_max is not None else 100)
        self._ax_y.setTickCount(5)
        self._ax_y.setLabelFormat('%d')

        for ax in (ax_x, self._ax_y):
            ax.setLabelsColor(QColor('#8f96a3'))
            ax.setGridLineColor(QColor('#2b2e37'))
            ax.setLineVisible(False)
            f = ax.labelsFont()
            f.setPixelSize(max(8, utils.BASE_FONT_PX - 3))
            ax.setLabelsFont(f)

        chart.addAxis(ax_x, Qt.AlignmentFlag.AlignBottom)
        chart.addAxis(self._ax_y, Qt.AlignmentFlag.AlignLeft)

        first = True
        for name, color in series_defs:
            s = QLineSeries()
            s.setName(name)
            c = QColor(color)
            pen = QPen(c, 2)
            s.setPen(pen)
            self._series.append(s)
            if first:
                area = QAreaSeries(s)
                fill = QColor(c)
                fill.setAlpha(38)
                area.setBrush(QBrush(fill))
                area.setPen(pen)
                area.setName(name)
                chart.addSeries(area)
                area.attachAxis(ax_x)
                area.attachAxis(self._ax_y)
                first = False
            else:
                chart.addSeries(s)
                s.attachAxis(ax_x)
                s.attachAxis(self._ax_y)

        if len(series_defs) > 1:
            lg = chart.legend()
            lg.setVisible(True)
            lg.setAlignment(Qt.AlignmentFlag.AlignBottom)
            lg.setLabelColor(QColor('#9aa3af'))
        else:
            chart.legend().setVisible(False)
        self.setChart(chart)

    def add(self, values):
        peak = 0.0
        for s, buf, v in zip(self._series, self._bufs, values):
            buf.append(float(v))
            s.replace([QPointF(i, y) for i, y in enumerate(buf)])
            if buf:
                peak = max(peak, max(buf))
        if not self._fixed:
            self._ax_y.setMax(_nice_ceiling(peak * 1.2))

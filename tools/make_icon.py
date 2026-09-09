"""生成 HxSSH 应用图标：assets/icon.ico（16~256 多尺寸）+ icon_256.png。

仅依赖 PySide6 离屏渲染，无需 Pillow。用法：
    python tools/make_icon.py
"""
import os
import struct
import sys

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import QBuffer, QIODevice, QPointF, Qt  # noqa: E402
from PySide6.QtGui import (QColor, QGuiApplication, QLinearGradient,  # noqa: E402
                           QPainter, QPainterPath, QPen, QPixmap)

SIZES = [16, 24, 32, 48, 64, 128, 256]
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def paint_icon(size: int) -> QPixmap:
    """深色终端窗口 + 心电脉冲线。所有几何按 size 比例绘制，小尺寸同样清晰。"""
    s = float(size)
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    radius = s * 0.195
    path = QPainterPath()
    path.addRoundedRect(0.0, 0.0, s, s, radius, radius)
    p.setClipPath(path)

    grad = QLinearGradient(0.0, 0.0, 0.0, s)
    grad.setColorAt(0.0, QColor('#262b38'))
    grad.setColorAt(1.0, QColor('#12141a'))
    p.fillPath(path, grad)

    # 终端标题栏 + 分隔线
    p.fillRect(0, 0, int(s), int(s * 0.166), QColor('#323848'))
    p.fillRect(0, int(s * 0.166), int(s), max(1, int(s * 0.007)), QColor('#0d0f14'))

    # 红黄绿窗口点
    p.setPen(Qt.PenStyle.NoPen)
    for i, col in enumerate(('#e8564f', '#f2a33c', '#3fb27f')):
        p.setBrush(QColor(col))
        p.drawEllipse(QPointF(s * (0.109 + 0.082 * i), s * 0.083), s * 0.0264, s * 0.0264)

    # 心电脉冲线：两层辉光 + 主线
    pts = [QPointF(s * x, s * y) for x, y in (
        (0.078, 0.586), (0.215, 0.586), (0.262, 0.633), (0.309, 0.586),
        (0.391, 0.586), (0.441, 0.359), (0.504, 0.810), (0.559, 0.508),
        (0.602, 0.586), (0.742, 0.586), (0.785, 0.543), (0.832, 0.586),
        (0.922, 0.586))]
    for w, col in ((0.10, (63, 178, 127, 36)), (0.062, (63, 178, 127, 80))):
        pen = QPen(QColor(*col), max(1.0, s * w))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.drawPolyline(pts)
    pen = QPen(QColor('#4fe0a0'), max(1.0, s * 0.030))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.drawPolyline(pts)

    # 圆角描边
    p.setClipping(False)
    p.setPen(QPen(QColor('#4a5266'), max(1.0, s * 0.008)))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPath(path)
    p.end()
    return pm


def pixmap_png(pm: QPixmap) -> bytes:
    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    pm.save(buf, 'PNG')
    return bytes(buf.data())


def make_ico(images: dict[int, bytes]) -> bytes:
    """组装 ICO：每尺寸一个 PNG 条目（Windows Vista+ 原生支持）。"""
    out = struct.pack('<HHH', 0, 1, len(images))
    entries = bytearray()
    body = bytearray()
    offset = 6 + 16 * len(images)
    for size in sorted(images, reverse=True):
        png = images[size]
        v = 0 if size >= 256 else size  # 256 在 ICO 里用 0 表示
        entries += struct.pack('<BBBBHHII', v, v, 0, 0, 1, 32, len(png), offset)
        body += png
        offset += len(png)
    return out + bytes(entries) + bytes(body)


def main():
    _app = QGuiApplication(sys.argv)  # noqa: F841
    out_dir = os.path.join(ROOT, 'assets')
    os.makedirs(out_dir, exist_ok=True)
    pngs = {}
    for size in SIZES:
        pm = paint_icon(size)
        pngs[size] = pixmap_png(pm)
        if size == 256:
            pm.save(os.path.join(out_dir, 'icon_256.png'), 'PNG')
    ico_path = os.path.join(out_dir, 'icon.ico')
    with open(ico_path, 'wb') as f:
        f.write(make_ico(pngs))
    print('written:', ico_path)


if __name__ == '__main__':
    main()

"""格式化小工具。"""
from __future__ import annotations


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def fmt_bytes(n):
    n = float(n)
    for unit in ('B', 'KB', 'MB', 'GB', 'TB', 'PB'):
        if abs(n) < 1024 or unit == 'PB':
            return f'{n:.0f} {unit}' if unit == 'B' else f'{n:.1f} {unit}'
        n /= 1024
    return f'{n:.1f} PB'


def fmt_kb(kb):
    return fmt_bytes((kb or 0) * 1024)


def fmt_rate(bps):
    """比特速率自适应单位：B/s → KB/s → MB/s。"""
    b = float(bps or 0)
    if b < 1024:
        return f'{b:.0f} B/s'
    if b < 1024 ** 2:
        return f'{b / 1024:.1f} KB/s'
    return f'{b / 1024 ** 2:.2f} MB/s'


def fmt_uptime(secs):
    secs = int(secs)
    d, rem = divmod(secs, 86400)
    h, rem = divmod(rem, 3600)
    m, _ = divmod(rem, 60)
    if d:
        return f'{d}天{h}小时'
    if h:
        return f'{h}小时{m}分钟'
    if m:
        return f'{m}分钟'
    return f'{secs}秒'


def level_color(pct):
    """按使用率返回颜色：<60 绿，<85 橙，否则红。"""
    if pct < 60:
        return '#3fb27f'
    if pct < 85:
        return '#f2a33c'
    return '#e8544f'

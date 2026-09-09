"""离线自检：解析逻辑 + 界面构建（无真实 SSH）。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtWidgets import QApplication  # noqa: E402

from hxssh.ssh_worker import SshWorker, build_sample  # noqa: E402


RAW1 = """===STAT
cpu  10000 0 5000 80000 1000 0 1000 0 0 0
cpu0 2500 0 1250 20000 250 0 250 0 0 0
cpu1 2500 0 1250 20000 250 0 250 0 0 0
cpu2 2500 0 1250 20000 250 0 250 0 0 0
cpu3 2500 0 1250 20000 250 0 250 0 0 0
intr 123456
===MEM
MemTotal:       16300000 kB
MemFree:        7300000 kB
MemAvailable:   8000000 kB
Buffers:         400000 kB
Cached:         3000000 kB
SwapTotal:       2000000 kB
SwapFree:        1500000 kB
===LOAD
0.52 0.58 0.59 2/1234 5678
===UPTIME
12345.67 48000.12
===NET
Inter-|   Receive                                                |  Transmit
 face |bytes    packets errs drop fifo frame compressed multicast|bytes
    lo: 1000 10 0 0 0 0 0 0 1000 10 0 0 0 0 0 0
  eth0: 1000000 800 0 0 0 0 0 0 500000 600 0 0 0 0 0 0
===DISK
Filesystem 1024-blocks Used Available Capacity Mounted on
/dev/sda1 100000000 40000000 60000000 40% /
tmpfs 1000000 0 1000000 0% /dev/shm
/dev/sdb1 50000000 45000000 5000000 90% /data
===PROCJ
1 2500
2345 50000
2400 8000
===PS
USER       PID %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND
root         1  0.0  0.1 169300 13000 ?        Ss   09:00   0:05 /sbin/init
root      2345  2.0  3.5 1234567 570000 ?       Sl   09:10  12:34 /usr/bin/app --flag
www-data  2400  0.5  1.2 999999 195000 ?       S    09:20   1:00 nginx: worker process
root      3000 300.0  0.0   1234   567 ?        R    12:00   0:01 ps aux
===END
"""

RAW2 = RAW1.replace(
    'cpu  10000 0 5000 80000 1000 0 1000 0 0 0',
    'cpu  12000 0 5000 80100 1000 0 1000 0 0 0',
).replace(
    'cpu0 2500 0 1250 20000 250 0 250 0 0 0',
    'cpu0 3500 0 1250 20100 250 0 250 0 0 0',
).replace(
    'cpu1 2500 0 1250 20000 250 0 250 0 0 0',
    'cpu1 3300 0 1250 20050 250 0 250 0 0 0',
).replace(
    'cpu2 2500 0 1250 20000 250 0 250 0 0 0',
    'cpu2 3400 0 1250 20050 250 0 250 0 0 0',
).replace(
    'cpu3 2500 0 1250 20000 250 0 250 0 0 0',
    'cpu3 3600 0 1250 20050 250 0 250 0 0 0',
).replace('12345.67 48000.12', '12347.67 48004.12').replace(
    'eth0: 1000000 800', 'eth0: 1100000 800').replace(
    '500000 600', '520000 600').replace(
    '2345 50000', '2345 50300').replace(
    '2400 8000', '2400 8100')


def test_parse():
    rc, msg = SshWorker._parse_rc('bash: line 1: kill: (49131) - Operation not permitted\nRC=1\n')
    assert rc == 1 and 'Operation not permitted' in msg

    prev = {'stat': None, 'net': None, 't': None, 'ticks': None}
    s1 = build_sample(RAW1, prev, 100.0, 2.0)
    s2 = build_sample(RAW2, prev, 100.0, 2.0)

    assert s1['cpu']['count'] == 4
    assert s1['cpu']['usage'] == 0.0
    assert s2['cpu']['count'] == 4
    assert 90 <= s2['cpu']['usage'] <= 100, s2['cpu']['usage']
    assert len(s2['cpu']['cores']) == 4
    assert all(80 <= c <= 100 for c in s2['cpu']['cores']), s2['cpu']['cores']

    expect = (16300000 - 8000000) / 16300000 * 100
    assert abs(s2['mem']['pct'] - expect) < 0.5
    assert s2['mem']['swap_pct'] == 25.0

    assert abs(s2['net']['rx_rate'] - 50000) < 1
    assert abs(s2['net']['tx_rate'] - 10000) < 1

    assert [d['mount'] for d in s2['disk']] == ['/', '/data']
    assert s2['disk'][1]['pct'] == 90

    procs = {p['pid']: p for p in s2['procs']}
    assert len(procs) == 3
    assert not any(p['cmd'] == 'ps aux' for p in s2['procs'])
    assert not any('===STAT' in p['cmd'] for p in s2['procs'])
    assert abs(procs[2345]['cpu'] - 150.0) < 0.01, procs[2345]['cpu']
    assert abs(procs[2400]['mem_pct'] - 1.2) < 0.01
    assert procs[1]['cmd'] == '/sbin/init'
    print('parse OK', {
        'cpu': round(s2['cpu']['usage'], 1),
        'mem%': round(s2['mem']['pct'], 1),
        'rx KB/s': round(s2['net']['rx_rate'] / 1024, 1),
        'tx KB/s': round(s2['net']['tx_rate'] / 1024, 1),
    })


def test_ui():
    app = QApplication.instance() or QApplication(sys.argv)
    from hxssh.ui.main_window import MainWindow

    w = MainWindow()
    info = {'host': 'test-server', 'os': 'Ubuntu 22.04 LTS', 'kernel': '5.15.0-generic', 'arch': 'x86_64'}
    prev = {'stat': None, 'net': None, 't': None, 'ticks': None}
    s = build_sample(RAW1, prev, 100.0, 2.0)
    w._on_connected(info)
    w._on_stats(s)
    app.processEvents()
    c = w.login.collect()
    assert isinstance(c, dict)
    w.close()
    print('UI OK')


if __name__ == '__main__':
    test_parse()
    test_ui()
    print('SELFTEST OK')

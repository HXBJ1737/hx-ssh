"""SSH 数据采集线程：连接远端 Linux，周期采集 CPU/内存/磁盘/网络/进程。"""
from __future__ import annotations

import queue
import socket
import threading
import time

import paramiko
from PySide6.QtCore import QThread, Signal

from .utils import clamp


PROCJ_AWK = (
    "awk '{pid=$1; k=0; for(i=length($0); i>=1; i--) "
    "if(substr($0,i,1)==\")\"){k=i; break} "
    "rest=substr($0,k+2); split(rest,g,\" \"); "
    "print pid, g[12]+g[13]}' /proc/[0-9]*/stat 2>/dev/null"
)

POLL_CMD = (
    "echo ===STAT; cat /proc/stat;"
    "echo ===MEM; cat /proc/meminfo;"
    "echo ===LOAD; cat /proc/loadavg;"
    "echo ===UPTIME; cat /proc/uptime;"
    "echo ===NET; cat /proc/net/dev;"
    "echo ===DISK; df -P -k 2>/dev/null;"
    "echo ===PROCJ; " + PROCJ_AWK + ";"
    "echo ===PS; ps aux;"
    "echo ===END"
)

SYSINFO_CMD = (
    "echo ===HOST; hostname 2>/dev/null;"
    "echo ===KERNEL; uname -r;"
    "echo ===ARCH; uname -m;"
    "echo ===OS; (. /etc/os-release 2>/dev/null; "
    "[ -n \"$PRETTY_NAME\" ] && echo \"$PRETTY_NAME\") || uname -s;"
    "echo ===END"
)


def parse_sections(raw):
    secs, cur = {}, None
    for ln in raw.splitlines():
        if ln.startswith('==='):
            cur = ln[3:].strip()
            secs[cur] = []
            continue
        if cur is not None:
            secs[cur].append(ln)
    return secs


def _stat_fields(rest):
    vals = []
    for tok in rest.split():
        try:
            vals.append(int(tok))
        except ValueError:
            vals.append(0)
    while len(vals) < 10:
        vals.append(0)
    return vals


def _cpu_usage(prev, cur):
    if not prev or not cur:
        return 0.0
    d_total = sum(cur) - sum(prev)
    if d_total <= 0:
        return 0.0
    d_idle = (cur[3] + cur[4]) - (prev[3] + prev[4])
    return clamp((1.0 - d_idle / d_total) * 100.0, 0.0, 100.0)


def _parse_mem(lines):
    info = {}
    for ln in lines:
        if ':' not in ln:
            continue
        k, v = ln.split(':', 1)
        tok = v.strip().split()
        if tok:
            try:
                info[k] = int(tok[0])
            except ValueError:
                pass
    return info


def load_private_key(path, password=None):
    last = None
    for cls in (paramiko.Ed25519Key, paramiko.RSAKey, paramiko.ECDSAKey):
        try:
            return cls.from_private_key_file(path, password=password)
        except Exception as e:  # noqa: BLE001
            last = e
    raise last


def build_sample(raw, prev, clk_tck=100.0, interval=2.0):
    """把一次 POLL_CMD 输出解析成监控样本；prev 就地更新。"""
    secs = parse_sections(raw)
    sample = {'time': time.time()}

    # ---- CPU（/proc/stat 两次采样差值）----
    agg = None
    cores = {}
    for ln in secs.get('STAT', []):
        parts = ln.split()
        if not parts or not parts[0].startswith('cpu'):
            continue
        if parts[0] == 'cpu':
            agg = _stat_fields(' '.join(parts[1:]))
        elif parts[0][3:].isdigit():
            cores[parts[0][3:]] = _stat_fields(' '.join(parts[1:]))
    prev_stat = prev.get('stat')
    core_ids = sorted(cores, key=lambda x: int(x))
    if prev_stat and agg is not None:
        agg_usage = _cpu_usage(prev_stat.get('_'), agg)
        core_usages = [
            _cpu_usage(prev_stat.get(cid), cores[cid]) if prev_stat.get(cid) else 0.0
            for cid in core_ids
        ]
    else:
        agg_usage = 0.0
        core_usages = [0.0] * len(core_ids)
    prev['stat'] = dict(cores)
    prev['stat']['_'] = agg
    sample['cpu'] = {'count': len(core_ids), 'usage': agg_usage, 'cores': core_usages}

    # ---- 内存 ----
    mi = _parse_mem(secs.get('MEM', []))
    total = mi.get('MemTotal', 0)
    avail = mi.get('MemAvailable')
    if avail is None:
        avail = (mi.get('MemFree', 0) + mi.get('Buffers', 0) + mi.get('Cached', 0)
                 + mi.get('SReclaimable', 0) - mi.get('Shmem', 0))
    avail = max(0, min(avail, total))
    used = total - avail
    sw_t = mi.get('SwapTotal', 0)
    sw_u = max(0, sw_t - mi.get('SwapFree', 0))
    sample['mem'] = {
        'total': total, 'used': used, 'avail': avail,
        'pct': used / total * 100 if total else 0.0,
        'swap_total': sw_t, 'swap_used': sw_u,
        'swap_pct': sw_u / sw_t * 100 if sw_t else 0.0,
        'buffers': mi.get('Buffers', 0),
        'cached': mi.get('Cached', 0) + mi.get('SReclaimable', 0),
    }

    # ---- 负载 / 运行时长 ----
    load = [0.0, 0.0, 0.0]
    l_lines = secs.get('LOAD', [])
    if l_lines:
        p = l_lines[0].split()
        try:
            load = [float(p[0]), float(p[1]), float(p[2])]
        except (IndexError, ValueError):
            pass
    uptime = 0.0
    u_lines = secs.get('UPTIME', [])
    if u_lines:
        try:
            uptime = float(u_lines[0].split()[0])
        except (IndexError, ValueError):
            pass
    sample['load'] = load
    sample['uptime'] = uptime

    # ---- 网络（/proc/net/dev 差值速率）----
    rx = tx = 0
    net = {}
    for ln in secs.get('NET', []):
        if ':' not in ln:
            continue
        name, rest = ln.split(':', 1)
        name = name.strip()
        if name in ('lo', 'face'):
            continue
        f = rest.split()
        if not f:
            continue
        try:
            r = int(f[0])
            t = int(f[8]) if len(f) > 8 else 0
        except ValueError:
            continue
        net[name] = (r, t)
        rx += r
        tx += t
    pt = prev.get('t')
    dt = interval
    if pt is not None and uptime > pt:
        dt = max(0.2, uptime - pt)
    rx_rate = tx_rate = 0.0
    pr = prev.get('net')
    if pr and dt > 0:
        rx_rate = max(0.0, (rx - pr.get('_rx', rx)) / dt)
        tx_rate = max(0.0, (tx - pr.get('_tx', tx)) / dt)
    prev['net'] = dict(net)
    prev['net']['_rx'] = rx
    prev['net']['_tx'] = tx
    prev['t'] = uptime
    sample['net'] = {'rx_rate': rx_rate, 'tx_rate': tx_rate, 'rx_total': rx, 'tx_total': tx}

    # ---- 磁盘 ----
    disks, seen = [], set()
    for ln in secs.get('DISK', []):
        cols = ln.split()
        if len(cols) < 6 or cols[0] == 'Filesystem':
            continue
        dev = cols[0]
        if not dev.startswith('/dev/') or dev.startswith('/dev/loop'):
            continue
        mount = cols[5]
        if mount in seen:
            continue
        try:
            total_kb = int(cols[1])
            used_kb = int(cols[2])
        except ValueError:
            continue
        try:
            pct = float(cols[4].rstrip('%'))
        except ValueError:
            pct = used_kb / total_kb * 100 if total_kb else 0.0
        seen.add(mount)
        disks.append({'dev': dev, 'mount': mount, 'total_kb': total_kb,
                      'used_kb': used_kb, 'pct': clamp(pct, 0.0, 100.0)})
    disks.sort(key=lambda d: d['mount'])
    sample['disk'] = disks

    # ---- 进程（ps aux + /proc/*/stat 差值算实时 CPU%）----
    ticks = {}
    for ln in secs.get('PROCJ', []):
        p = ln.split()
        if len(p) >= 2:
            try:
                ticks[int(p[0])] = int(p[1])
            except ValueError:
                pass
    pticks = prev.get('ticks') or {}
    procs = []
    for ln in secs.get('PS', []):
        cols = ln.split(None, 10)
        if len(cols) < 11 or cols[1] == 'PID':
            continue
        cmd = cols[10]
        # 过滤监控命令自身的瞬时进程：ps aux 快照会包含自己，
        # 其 %CPU=累计CPU/存活时间，刚启动即采样会得到 300% 之类的失真值；
        # 外壳进程的命令行里含有唯一标记 ===STAT，一并隐藏。
        if cmd == 'ps aux' or cmd.startswith('ps aux '):
            continue
        if '===STAT' in cmd or cmd.startswith("awk '{pid=$1"):
            continue
        try:
            pid = int(cols[1])
            cpu_ps = float(cols[2])
            rss = int(cols[5])
            mem_pct = float(cols[3])
        except ValueError:
            continue
        cur = ticks.get(pid)
        pv = pticks.get(pid)
        if cur is not None and pv is not None and dt > 0 and clk_tck:
            cpu_pct = (cur - pv) / dt * 100.0 / clk_tck
        else:
            cpu_pct = cpu_ps  # 首个采样回退为 ps 累计均值
        procs.append({
            'pid': pid, 'user': cols[0], 'cpu': clamp(cpu_pct, 0.0, 9999.0),
            'rss_kb': rss, 'mem_pct': mem_pct, 'stat': cols[7],
            'start': cols[8], 'time': cols[9], 'cmd': cmd,
        })
    prev['ticks'] = ticks
    sample['procs'] = procs
    return sample


class SshWorker(QThread):
    """后台线程：建立 SSH 连接并周期采集。"""

    connect_failed = Signal(str)
    connected = Signal(dict)
    stats_ready = Signal(dict)
    disconnected = Signal(str)
    kill_done = Signal(int, bool, str)

    def __init__(self, cfg, parent=None):
        super().__init__(parent)
        self.cfg = dict(cfg)
        self.interval = float(cfg.get('interval') or 2)
        self.user_stop = False
        self.sudo_pass = cfg.get('password') or ''
        self._client = None
        self._sysinfo = {}
        self._clk = 100.0
        self._stop_evt = threading.Event()
        self._cmds = queue.Queue()

    # ------ 公开接口（线程安全）------
    def stop(self):
        self._stop_evt.set()

    def kill(self, pid):
        self._cmds.put(('kill', int(pid)))

    def kill_sudo(self, pid):
        """用户已提供 sudo 密码后的提权重试入口。"""
        self._cmds.put(('kill_sudo', int(pid)))

    # ------ 线程主体 ------
    def run(self):
        try:
            self._connect()
        except Exception as e:  # noqa: BLE001
            self.connect_failed.emit(self._friendly(e))
            self._cleanup()
            return
        self.connected.emit(self._sysinfo)
        prev = {'stat': None, 'net': None, 't': None, 'ticks': None}
        err = ''
        while not self._stop_evt.is_set():
            self._drain()
            if self._stop_evt.is_set():
                break
            try:
                ok, out = self._exec(POLL_CMD, timeout=max(10, self.interval * 4))
                if not ok:
                    raise RuntimeError('远程命令执行失败')
                sample = build_sample(out, prev, self._clk, self.interval)
                self.stats_ready.emit(sample)
            except Exception as e:  # noqa: BLE001
                err = self._friendly(e)
                break
            self._stop_evt.wait(self.interval)
        self._cleanup()
        self.disconnected.emit('' if self.user_stop else (err or '连接已断开'))

    # ------ 内部实现 ------
    def _connect(self):
        cfg = self.cfg
        self._client = paramiko.SSHClient()
        self._client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        kw = dict(
            hostname=cfg['host'], port=int(cfg.get('port') or 22),
            username=cfg.get('username') or 'root',
            timeout=12, banner_timeout=20, auth_timeout=20,
            allow_agent=False, look_for_keys=False,
        )
        if cfg.get('auth') == 'key':
            kw['pkey'] = load_private_key(cfg.get('key_path'), cfg.get('key_pass') or None)
        else:
            kw['password'] = cfg.get('password') or ''
        self._client.connect(**kw)
        tr = self._client.get_transport()
        tr.set_keepalive(15)

        ok, out = self._exec(SYSINFO_CMD, 15)

        def first(name):
            for ln in parse_sections(out).get(name, []):
                ln = ln.strip()
                if ln:
                    return ln
            return ''

        self._sysinfo = {
            'host': first('HOST') or cfg['host'],
            'kernel': first('KERNEL'),
            'arch': first('ARCH'),
            'os': first('OS') or 'Linux',
        }
        try:
            _ok2, out2 = self._exec('getconf CLK_TCK', 5)
            self._clk = float(out2.strip().splitlines()[-1]) if _ok2 and out2.strip() else 100.0
        except Exception:  # noqa: BLE001
            self._clk = 100.0

    def _exec(self, cmd, timeout=15, stdin_data=None):
        tr = self._client.get_transport()
        if tr is None or not tr.is_active():
            raise EOFError('SSH 通道已关闭')
        ch = tr.open_session(timeout=timeout)
        ch.settimeout(timeout)
        ch.exec_command(cmd)
        if stdin_data:
            ch.sendall(str(stdin_data).encode('utf-8'))
            try:
                ch.shutdown_write()
            except Exception:  # noqa: BLE001
                pass
        buf = bytearray()
        while True:
            data = ch.recv(65536)
            if not data:
                break
            buf.extend(data)
        rc = ch.recv_exit_status()
        try:
            ch.close()
        except Exception:  # noqa: BLE001
            pass
        return rc == 0, bytes(buf).decode('utf-8', 'replace')

    def _drain(self):
        while True:
            try:
                kind, val = self._cmds.get_nowait()
            except queue.Empty:
                return
            if kind == 'kill':
                try:
                    pid = int(val)
                    ok, msg = self._kill_once(pid, use_sudo=False)
                    if not ok and msg == 'NEED_SUDO' and self.sudo_pass:
                        ok, msg = self._kill_once(pid, use_sudo=True)
                    self.kill_done.emit(pid, ok, '' if ok else msg)
                except Exception as e:  # noqa: BLE001
                    self.kill_done.emit(int(val), False, self._friendly(e))
            elif kind == 'kill_sudo':
                try:
                    ok, msg = self._kill_once(int(val), use_sudo=True)
                    self.kill_done.emit(int(val), ok, '' if ok else msg)
                except Exception as e:  # noqa: BLE001
                    self.kill_done.emit(int(val), False, self._friendly(e))

    def _kill_once(self, pid, use_sudo):
        """执行一次 kill；权限不足返回 NEED_SUDO 哨兵，由上层决定提权重试。"""
        if use_sudo:
            if not self.sudo_pass:
                return False, 'NEED_SUDO'
            cmd = "sudo -S -p '' kill -9 %d 2>&1; echo RC=$?" % pid
            _ok, out = self._exec(cmd, 15, stdin_data=self.sudo_pass + '\n')
        else:
            _ok, out = self._exec(f'kill -9 {pid} 2>&1; echo RC=$?', 10)
        rc, msg = self._parse_rc(out)
        if rc == 0 or 'No such process' in out:
            return True, ''
        if not use_sudo and 'Operation not permitted' in out:
            return False, 'NEED_SUDO'
        low = out.lower()
        if 'incorrect password' in low:
            msg = 'sudo 密码不正确'
        elif 'not in the sudoers' in low:
            msg = '当前用户不在 sudoers 文件中，无法提权'
        elif 'a password is required' in low:
            msg = 'sudo 需要密码'
        elif use_sudo and 'Operation not permitted' in out:
            msg = '使用 sudo 后仍无权限（可能是受保护的内核进程）'
        return False, msg or '结束进程失败'

    @staticmethod
    def _parse_rc(out):
        lines = out.splitlines()
        rc_line = [l for l in lines if l.startswith('RC=')]
        rc = int(rc_line[-1][3:]) if rc_line else 1
        msg = ' '.join(l for l in lines if not l.startswith('RC=')).strip()
        return rc, msg

    def _cleanup(self):
        c, self._client = self._client, None
        if c:
            try:
                c.close()
            except Exception:  # noqa: BLE001
                pass

    @staticmethod
    def _friendly(e):
        if isinstance(e, paramiko.AuthenticationException):
            return '认证失败：请检查用户名、密码或私钥'
        if isinstance(e, paramiko.SSHException):
            return f'SSH 错误：{e}'
        if isinstance(e, socket.gaierror):
            return '无法解析主机名，请检查主机地址'
        if isinstance(e, ConnectionRefusedError):
            return '连接被拒绝：目标端口未开放 SSH 服务'
        if isinstance(e, FileNotFoundError):
            return f'找不到私钥文件：{e}'
        if isinstance(e, (TimeoutError, socket.timeout)):
            return '连接超时：请检查主机地址与网络'
        if isinstance(e, EOFError):
            return '连接被远端关闭'
        return f'{type(e).__name__}: {e}'

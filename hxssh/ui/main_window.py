"""主窗口：登录页 ↔ 监控仪表盘 切换与后台线程编排。"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QApplication, QInputDialog, QLineEdit,
                               QMainWindow, QMessageBox, QStackedWidget)

from .. import config
from .. import utils
from ..ssh_worker import SshWorker
from ..ui.styles import build_stylesheet
from .dashboard import Dashboard
from .login import LoginWidget


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._cfg = config.load()
        self.worker = None

        self.setWindowTitle('HxSSH 远程监控')
        self.resize(1060, 690)
        self.setMinimumSize(800, 600)

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)
        # 允许极限压缩：尺寸不足时由分割器收起卡片、表格横向滚动
        self.stack.setMinimumSize(0, 0)
        self.login = LoginWidget(self._cfg)
        self.dash = Dashboard(self._cfg.get('interval', 2), self._cfg.get('font_size', 13), self._cfg)
        self.stack.addWidget(self.login)
        self.stack.addWidget(self.dash)

        self.login.connect_requested.connect(self._start_connect)
        self.dash.disconnect_requested.connect(self._disconnect)
        self.dash.interval_changed.connect(self._change_interval)
        self.dash.font_changed.connect(self._change_font)
        self.dash.kill_requested.connect(self._kill)
        self.dash.topmost_changed.connect(self._set_topmost)

    # ------ 连接生命周期 ------
    def _start_connect(self, cfg):
        self._cfg = cfg
        config.save(cfg)
        self.login.set_busy(True)
        self.login.show_error('')
        w = SshWorker(cfg)
        w.connected.connect(self._on_connected)
        w.connect_failed.connect(self._on_connect_failed)
        w.stats_ready.connect(self._on_stats)
        w.disconnected.connect(self._on_disconnected)
        w.kill_done.connect(self._on_kill_done)
        w.finished.connect(w.deleteLater)
        self.worker = w
        w.start()

    def _on_connected(self, info):
        self.login.set_busy(False)
        self.dash.set_sysinfo(info)
        self.stack.setCurrentWidget(self.dash)
        self.setWindowTitle(f"HxSSH — {self._cfg.get('username')}@{self._cfg.get('host')}")

    def _on_connect_failed(self, msg):
        self.login.set_busy(False)
        self.login.show_error(msg)
        self.worker = None

    def _on_stats(self, sample):
        if self.stack.currentWidget() is self.dash:
            self.dash.update_sample(sample)

    def _on_disconnected(self, reason):
        self.worker = None
        self.login.set_busy(False)
        self.stack.setCurrentWidget(self.login)
        if reason:
            QMessageBox.warning(self, '连接已断开', reason)
            self.login.show_error(reason)

    def _disconnect(self):
        if self.worker:
            self.worker.user_stop = True
            self.worker.stop()
        self.stack.setCurrentWidget(self.login)

    def _change_interval(self, v):
        self._cfg['interval'] = v
        if self.worker:
            self.worker.interval = v
        config.save(self._cfg)

    def _change_font(self, px):
        utils.BASE_FONT_PX = int(px)
        QApplication.instance().setStyleSheet(build_stylesheet(utils.BASE_FONT_PX))
        self._cfg['font_size'] = int(px)
        config.save(self._cfg)

    def _set_topmost(self, on):
        flags = self.windowFlags()
        if on:
            flags |= Qt.WindowStaysOnTopHint
        else:
            flags &= ~Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.show()
        self._cfg['always_on_top'] = on
        config.save(self._cfg)

    def _kill(self, pid, cmd):
        if self.worker:
            self.worker.kill(pid)

    def _on_kill_done(self, pid, ok, msg):
        if ok:
            return
        if msg == 'NEED_SUDO':
            pw, okd = QInputDialog.getText(
                self, '需要 sudo 权限',
                f'结束进程 {pid} 权限不足。\n'
                f'请输入 {self._cfg.get("username")} 的登录密码（sudo 提权，仅本次会话内使用）：',
                QLineEdit.EchoMode.Password)
            if okd and pw and self.worker:
                self.worker.sudo_pass = pw
                self.worker.kill_sudo(pid)
            elif self.stack.currentWidget() is self.dash:
                QMessageBox.information(self, '已取消', '未提供 sudo 密码，已跳过提权结束进程。')
            return
        QMessageBox.warning(self, '操作失败', f'结束进程 {pid} 失败：{msg or "权限不足或进程不存在"}')

    def closeEvent(self, ev):  # noqa: N802
        if self.worker:
            self.worker.user_stop = True
            self.worker.stop()
            self.worker.wait(15000)
        super().closeEvent(ev)

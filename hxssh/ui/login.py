"""连接页：主机 / 端口 / 用户 / 密码或私钥。"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFileDialog, QFormLayout,
                               QFrame, QHBoxLayout, QLabel, QLineEdit,
                               QPushButton, QSpinBox, QStackedWidget,
                               QVBoxLayout, QWidget)


class LoginWidget(QWidget):
    connect_requested = Signal(dict)

    def __init__(self, cfg, parent=None):
        super().__init__(parent)
        self.setObjectName('LoginRoot')
        self._interval = cfg.get('interval', 2)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addStretch(2)

        card = QFrame()
        card.setProperty('card', 'true')
        card.setFixedWidth(450)
        v = QVBoxLayout(card)
        v.setContentsMargins(30, 28, 30, 26)
        v.setSpacing(12)

        big = QLabel('HxSSH 远程监控')
        big.setObjectName('BigTitle')
        big.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        sub = QLabel('SSH 连接 Linux 服务器 · 实时查看 CPU / 内存 / 磁盘 / 网络 / 进程')
        sub.setObjectName('SubTitle')
        sub.setWordWrap(True)
        sub.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        v.addWidget(big)
        v.addWidget(sub)
        v.addSpacing(6)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.ed_host = QLineEdit(cfg.get('host', ''))
        self.ed_host.setPlaceholderText('例如 192.168.1.10')
        self.sp_port = QSpinBox()
        self.sp_port.setRange(1, 65535)
        self.sp_port.setValue(int(cfg.get('port') or 22))
        self.ed_user = QLineEdit(cfg.get('username', 'root'))
        self.cb_auth = QComboBox()
        self.cb_auth.addItems(['密码登录', '私钥登录'])
        form.addRow('主机地址', self.ed_host)
        form.addRow('端口', self.sp_port)
        form.addRow('用户名', self.ed_user)
        form.addRow('认证方式', self.cb_auth)

        self.stack = QStackedWidget()
        p1 = QWidget()
        l1 = QVBoxLayout(p1)
        l1.setContentsMargins(0, 0, 0, 0)
        self.ed_pass = QLineEdit()
        self.ed_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self.ed_pass.setPlaceholderText('SSH 密码')
        l1.addWidget(self.ed_pass)
        p2 = QWidget()
        l2 = QVBoxLayout(p2)
        l2.setContentsMargins(0, 0, 0, 0)
        l2.setSpacing(8)
        row = QHBoxLayout()
        self.ed_key = QLineEdit(cfg.get('key_path', ''))
        self.ed_key.setPlaceholderText(r'私钥路径，如 C:\Users\you\.ssh\id_ed25519')
        btn_key = QPushButton('浏览…')
        btn_key.clicked.connect(self._browse_key)
        row.addWidget(self.ed_key, 1)
        row.addWidget(btn_key)
        self.ed_key_pass = QLineEdit()
        self.ed_key_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self.ed_key_pass.setPlaceholderText('私钥口令（可选）')
        l2.addLayout(row)
        l2.addWidget(self.ed_key_pass)
        self.stack.addWidget(p1)
        self.stack.addWidget(p2)
        form.addRow(self.stack)
        v.addLayout(form)

        self.cb_remember = QCheckBox('记住连接信息（密码将以明文保存在本机配置文件）')
        self.cb_remember.setChecked(bool(cfg.get('remember')))
        v.addWidget(self.cb_remember)

        self.btn = QPushButton('连  接')
        self.btn.setObjectName('Primary')
        self.btn.setDefault(True)
        self.btn.setMinimumHeight(40)
        v.addWidget(self.btn)

        self.lb_status = QLabel('')
        self.lb_status.setObjectName('ErrorText')
        self.lb_status.setWordWrap(True)
        self.lb_status.setVisible(False)
        v.addWidget(self.lb_status)

        outer.addWidget(card, 0, Qt.AlignmentFlag.AlignHCenter)
        outer.addStretch(3)

        self.cb_auth.currentIndexChanged.connect(self.stack.setCurrentIndex)
        self.btn.clicked.connect(self._emit)
        self.ed_pass.returnPressed.connect(self._emit)
        self.ed_key_pass.returnPressed.connect(self._emit)
        self.stack.setCurrentIndex(0 if cfg.get('auth', 'password') == 'password' else 1)

    def _browse_key(self):
        path, _ = QFileDialog.getOpenFileName(self, '选择 SSH 私钥', str(Path.home()))
        if path:
            self.ed_key.setText(path)

    def collect(self):
        return {
            'host': self.ed_host.text().strip(),
            'port': self.sp_port.value(),
            'username': self.ed_user.text().strip() or 'root',
            'auth': 'password' if self.stack.currentIndex() == 0 else 'key',
            'password': self.ed_pass.text(),
            'key_path': self.ed_key.text().strip(),
            'key_pass': self.ed_key_pass.text(),
            'remember': self.cb_remember.isChecked(),
            'interval': self._interval,
        }

    def _emit(self):
        c = self.collect()
        if not c['host']:
            self.show_error('请填写主机地址')
            return
        if c['auth'] == 'password' and not c['password']:
            self.show_error('请填写密码')
            return
        if c['auth'] == 'key' and not c['key_path']:
            self.show_error('请选择私钥文件')
            return
        self.show_error('')
        self.connect_requested.emit(c)

    def set_busy(self, busy):
        self.btn.setEnabled(not busy)
        self.btn.setText('连接中…' if busy else '连  接')

    def show_error(self, msg):
        self.lb_status.setText(msg)
        self.lb_status.setVisible(bool(msg))

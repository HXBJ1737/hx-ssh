# HxSSH 远程监控

一个只做一件事的 SSH 工具：连接成功后，图形化实时显示远端 Linux 服务器的 CPU、内存、磁盘、网络与进程。

## 功能

- SSH 连接：密码或私钥（Ed25519 / RSA / ECDSA），可记住连接信息
- **CPU**：总使用率实时曲线、每核负载条、核心数、负载均值（loadavg）
- **内存**：环形仪表（已用 / 可用 / 缓冲缓存）+ 交换分区仪表
- **磁盘**：各挂载点使用率条形图
- **网络**：上下行速率实时曲线（KB/s）
- **进程**：全量进程表（PID / 用户 / CPU% / 内存 / 状态 / 启动时间 / 命令），
  点击表头排序、关键字搜索、暂停刷新、一键结束进程（SIGKILL，需确认）
- 刷新间隔 1 / 2 / 3 / 5 秒可调；断线自动提示并可重连

## 运行

Windows 下直接双击 `run.bat`（首次运行自动创建虚拟环境并安装依赖，需要联网）。

手动运行：

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python main.py
```

## 打包为 EXE

双击 `build_exe.bat`（或命令行运行），完成后得到单文件程序 `dist\HxSSH.exe`，
可拷贝到任意 Windows 机器直接运行，无需安装 Python。

说明：
- 使用 PyInstaller `--onefile --windowed` 打包，首次启动需解压，会慢 1~3 秒。
- 单文件 EXE 偶发被杀毒软件/SmartScreen 误报，属 PyInstaller 常见现象，添加信任即可；
  如在意可改用目录模式（去掉 `--onefile` 参数）。

## 说明

- 监控数据来自远端 Linux 的 `/proc` 与 `ps` / `df`，适用于常见 Linux 发行版。
- 进程 CPU% 由相邻两次采样的 utime+stime 差值计算，比 `ps aux` 的累计平均更接近实时。
- “结束进程”使用 `kill -9`，不可恢复，请谨慎操作。
- “结束进程”权限不足时会自动尝试 `sudo` 提权：密码登录直接复用登录密码；
  私钥登录会在需要时弹窗询问一次，仅缓存在本次会话内，不写入磁盘。
- 勾选“记住连接信息”后，密码以明文保存在 `~/.hxssh.json`，请自行权衡风险。

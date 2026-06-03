# PulseClick

这是 PulseClick 的重构版，旧版单文件程序已移除，当前主目录就是可运行版本。

## UI 方向

界面采用左侧控制栏、右侧工作区的桌面工具布局。主题提供 `棕色` 和 `白色` 两套暖中性色搭配，切换时带轻量淡化过渡。

## 改动重点

- 把 Windows API、热键线程、连点线程、录制线程、脚本回放和 UI 拆到独立模块。
- 热键注册失败会返回具体信息，不再静默失败。
- 连点和脚本执行使用 `SendInput`，减少旧 `mouse_event` 的兼容问题。
- 后台线程只通过回调通知 UI，UI 更新统一回到 Tk 主线程。
- 设置文件保存在当前目录下的 `pulseclick_refactor_settings.json`。
- 全局滚动容器覆盖侧栏和内容区，小窗口下也能访问底部按钮。

## 运行

```powershell
python -m pip install -r .\requirements.txt
python .\main.py
```

也可以双击 `启动连点器.bat`。

## 打包

已验证可用的单文件 exe 输出位置：

```text
dist\PulseClickRefactor.exe
```

重新打包：

```powershell
python -m pip install pyinstaller
python -m PyInstaller --noconfirm --clean --onefile --windowed --name PulseClickRefactor main.py
```

`build`、`dist` 和 `*.spec` 属于本地构建产物，默认不提交到 Git。

## CODEX Dragon Companion · CODEX龙娘桌宠

轻盈的龙娘桌宠，悬停展开淡紫色圆角活动面板。保留原角色动画，透明边缘和文字使用 Qt 平滑渲染。

![桌宠与面板](ui-preview.png)

## Windows 发行版（Windows 10/11 x64）

从 [Releases](https://github.com/DoubleD600/dragon-companion/releases) 下载 ZIP，解压整个文件夹到固定位置，双击 `DragonCompanion.exe`。无需安装 Python。请保留 `_internal` 文件夹。

- 拖动角色移动；悬停后拖动面板右下角调整大小。
- 单击角色有表情反馈；右键可隐藏、打开桌面端或退出。
- 关闭、最小化、Esc 均隐藏到系统托盘；托盘点击恢复，右键菜单退出。
- 用量和任务从本地 Codex 数据读取；上下文为最近一次输入量与窗口容量的估算。
- 点击任务打开对应对话；“新建对话”使用系统注册的 Codex 链接协议。
- 展开面板自动避开屏幕边缘与任务栏。

```powershell
.\DragonCompanion.exe --install-shortcut
.\DragonCompanion.exe --install-startup
.\DragonCompanion.exe --remove-startup
```

启动项是轻量监控器：用户登录后等待 ChatGPT/Codex 桌面端启动，再启动桌宠；手动退出后不会在同一次桌面端运行期间反复拉起。托盘图标始终注册，是否放入 Windows 溢出区由系统托盘设置决定。

## 配置与通用数据接口

配置位置：Windows `%LOCALAPPDATA%/DragonCompanion/config.json`；macOS `~/Library/Application Support/DragonCompanion/config.json`；Linux `$XDG_CONFIG_HOME/dragon-companion/config.json`（默认 `~/.config`）。复制 `config.example.json` 后修改，也可使用 `--config <文件>`。

默认自动查找 `CODEX_HOME` 或 `~/.codex`，选择版本最高的 `state_*.sqlite`。数据库以只读方式访问，不上传任务内容。Codex 本地数据库与事件格式属于内部格式，后续版本可能需要适配。日志写入配置目录的 `app.log`。

`provider: "json"` 配合 `snapshot_file` 可以接入其他任务系统，格式见 `examples/snapshot.json`。Python 扩展接口见 [ARCHITECTURE.md](ARCHITECTURE.md)。桌面程序名、启动命令、任务链接模板、字体、轮询间隔均可配置，没有作者电脑的绝对路径。

`--snapshot` 输出标准化 JSON（无控制台的 EXE 写入配置目录 `snapshot.json`；可用 `--snapshot-output <文件>` 指定路径），仅用于本地诊断，其中包含任务标题；公开问题报告前请自行删去私人信息。

## 源码运行与构建

Python 3.10+，推荐独立虚拟环境：

```sh
python -m venv .venv
# 激活虚拟环境后
python -m pip install -e .
python -m unittest discover -s tests
python -m dragon_companion
```

Windows 打包：`powershell -File scripts/build.ps1 -Python .venv/Scripts/python.exe`。项目使用固定依赖版本，构建脚本从自身位置解析相对路径。GitHub Actions 对 Windows/Linux 做测试，并在 Windows 构建发行包。

数据模型、JSON 数据源及 Qt 界面可跨平台运行；此发行版只验证 Windows x64。macOS/Linux 需要配置 `desktop_command` 和对话协议处理器，自动安装启动项/快捷方式目前限 Windows，托盘需要桌面环境支持。

## 许可

程序代码 MIT。角色图像与第三方库的许可分别见 [ASSETS.md](ASSETS.md) 和发行包 `THIRD_PARTY_LICENSES`，代码许可不覆盖角色原作权益。

---
A lightweight Qt desktop companion with configurable read-only Codex/JSON providers, translucent rendering, tray controls and screen-aware panels. Windows x64 binaries are published in Releases; other desktop platforms need native integration configuration.

"""Native operations behind one configurable desktop adapter."""
import ctypes
import json
import os
import subprocess
import sys
import tempfile
from ctypes import wintypes
from pathlib import Path
from urllib.parse import quote

import psutil


def launch_command():
    if getattr(sys, "frozen", False):
        return [sys.executable]
    return [sys.executable, "-m", "dragon_companion"]


class DesktopAdapter:
    launch_command = staticmethod(launch_command)

    def __init__(self, settings):
        self.settings = settings

    def process_ids(self):
        names = {name.lower() for name in self.settings.desktop_processes}
        found = set()
        for process in psutil.process_iter(["name"]):
            if (process.info["name"] or "").lower() in names:
                found.add(process.pid)
        return found

    def windows_window(self):
        if sys.platform != "win32":
            return None
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        user32.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
        user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        user32.IsWindowVisible.argtypes = [wintypes.HWND]
        user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
        user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        user32.GetWindow.argtypes = [wintypes.HWND, ctypes.c_uint]
        user32.GetWindow.restype = wintypes.HWND
        pids, candidates = self.process_ids(), []

        @callback_type
        def collect(hwnd, _):
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value in pids and user32.IsWindowVisible(hwnd) and not user32.GetWindow(hwnd, 4):
                title = ctypes.create_unicode_buffer(user32.GetWindowTextLengthW(hwnd) + 1)
                user32.GetWindowTextW(hwnd, title, len(title))
                if title.value:
                    candidates.append((title.value.lower() in ("chatgpt", "codex"), hwnd))
            return True

        user32.EnumWindows(collect, 0)
        return max(candidates, default=(False, None))[1]

    def running(self):
        return bool(self.windows_window()) if sys.platform == "win32" else bool(self.process_ids())

    def focus(self):
        if sys.platform == "win32":
            hwnd = self.windows_window()
            if hwnd:
                user32 = ctypes.WinDLL("user32", use_last_error=True)
                user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
                user32.SetForegroundWindow.argtypes = [wintypes.HWND]
                user32.ShowWindow(hwnd, 9)
                return bool(user32.SetForegroundWindow(hwnd))
        if self.settings.desktop_command:
            subprocess.Popen(list(self.settings.desktop_command), close_fds=True)
            return True
        if sys.platform == "win32":
            # Discover installed package identifiers; never embed one user's app version/path.
            result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
                "Get-StartApps | Where-Object { $_.Name -in @('ChatGPT','Codex') } | ConvertTo-Json -Compress"],
                capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW, timeout=10)
            rows = json.loads(result.stdout or "[]")
            rows = rows if isinstance(rows, list) else [rows]
            for row in rows:
                if row.get("AppID"):
                    os.startfile("shell:AppsFolder\\" + row["AppID"])
                    return True
        raise RuntimeError("请在配置中设置 desktop_command 以打开桌面端")

    def open_task(self, task_id):
        self.open_url(self.settings.task_url.format(id=quote(task_id, safe="")))

    def new_chat(self):
        self.open_url(self.settings.new_chat_url)

    def install_shortcut(self, kind, remove=False):
        return install_shortcut(kind.capitalize(), remove)

    @staticmethod
    def open_url(url):
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        if not QDesktopServices.openUrl(QUrl(url)):
            raise RuntimeError("系统未注册该对话链接协议")


def install_shortcut(kind, remove=False):
    if sys.platform != "win32":
        raise RuntimeError("自动安装快捷方式目前支持 Windows；其他系统可使用 --watch-codex")
    command = launch_command()
    data = {"kind": kind, "remove": remove, "target": command[0],
            "args": subprocess.list2cmdline(command[1:] + (["--watch-codex"] if kind == "Startup" else []))}
    script = '''param([string]$DataFile)
$data = Get-Content -LiteralPath $DataFile -Raw | ConvertFrom-Json
$folder = [Environment]::GetFolderPath($data.kind)
$name = if($data.kind -eq 'Startup') {'Dragon Companion - Codex Startup.lnk'} else {'GPT 龙娘桌宠.lnk'}
$path = Join-Path $folder $name
if($data.remove){if(Test-Path -LiteralPath $path){Remove-Item -LiteralPath $path}; exit 0}
$shell = New-Object -ComObject WScript.Shell
$link = $shell.CreateShortcut($path)
$link.TargetPath = $data.target
$link.Arguments = $data.args
$link.WorkingDirectory = Split-Path -Parent $data.target
$link.IconLocation = "$($data.target),0"
$link.Save()
Write-Output $path
'''
    with tempfile.TemporaryDirectory(prefix="dragon-shortcut-") as directory:
        data_path, script_path = Path(directory) / "data.json", Path(directory) / "install.ps1"
        data_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8-sig")
        script_path.write_text(script, encoding="utf-8-sig")
        result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-File", str(script_path), str(data_path)],
            capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW, timeout=15)
        if result.returncode:
            raise RuntimeError(result.stderr)
        return result.stdout.strip()

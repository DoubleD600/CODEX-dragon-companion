import argparse
import json
import logging
import sys
from dataclasses import asdict
from pathlib import Path

from .config import Settings, config_directory
from .desktop import DesktopAdapter
from .providers import make_provider


def main():
    parser = argparse.ArgumentParser(description="Dragon Companion desktop pet")
    parser.add_argument("--config", type=Path)
    parser.add_argument("--watch-codex", action="store_true")
    parser.add_argument("--snapshot", action="store_true")
    parser.add_argument("--snapshot-output", type=Path)
    parser.add_argument("--install-startup", action="store_true")
    parser.add_argument("--install-shortcut", action="store_true")
    parser.add_argument("--remove-startup", action="store_true")
    args = parser.parse_args()
    directory = config_directory()
    directory.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=directory / "app.log", level=logging.WARNING,
                        format="%(asctime)s %(levelname)s %(message)s")
    settings = Settings.load(args.config)
    desktop = DesktopAdapter(settings)
    if args.install_startup or args.remove_startup:
        desktop.install_shortcut("startup", remove=args.remove_startup)
        return
    if args.install_shortcut:
        desktop.install_shortcut("desktop")
        return
    provider = make_provider(settings)
    if args.snapshot or args.snapshot_output:
        content = json.dumps(asdict(provider.snapshot()), ensure_ascii=False, indent=2)
        if args.snapshot_output:
            args.snapshot_output.write_text(content, encoding="utf-8")
        elif sys.stdout is not None:
            print(content)
        else:
            (directory / "snapshot.json").write_text(content, encoding="utf-8")
        return
    from PySide6.QtCore import QLockFile, QTimer
    from PySide6.QtNetwork import QLocalServer, QLocalSocket
    from PySide6.QtWidgets import QApplication
    app = QApplication(sys.argv[:1])
    app.setQuitOnLastWindowClosed(False)
    if args.watch_codex:
        import subprocess
        lock = QLockFile(str(directory / "watcher.lock"))
        if not lock.tryLock(0):
            return
        previous = False
        def check():
            nonlocal previous
            running = desktop.running()
            if running and not previous:
                command = desktop.launch_command()
                if args.config:
                    command += ["--config", str(args.config.resolve())]
                subprocess.Popen(command, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            previous = running
        timer = QTimer()
        timer.timeout.connect(check)
        timer.start(2500)
        check()
        return app.exec()
    lock = QLockFile(str(directory / "pet.lock"))
    socket_name = "dragon-companion-" + __import__("hashlib").sha256(str(directory).encode()).hexdigest()[:16]
    if not lock.tryLock(0):
        socket = QLocalSocket()
        socket.connectToServer(socket_name)
        if socket.waitForConnected(1000):
            socket.write(b"show")
            socket.waitForBytesWritten(1000)
        return
    from .ui import PetWindow
    window = PetWindow(settings, provider, desktop)
    QLocalServer.removeServer(socket_name)
    server = QLocalServer()
    server.listen(socket_name)
    def show_existing():
        connection = server.nextPendingConnection()
        window.show_pet()
        connection.disconnectFromServer()
        connection.deleteLater()
    server.newConnection.connect(show_existing)
    window.show_pet()
    result = app.exec()
    from PySide6.QtCore import QThreadPool
    QThreadPool.globalInstance().waitForDone()
    server.close()
    return result


if __name__ == "__main__":
    sys.exit(main() or 0)

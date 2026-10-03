import json
import os
import sys
from dataclasses import asdict, dataclass, fields
from pathlib import Path


def config_directory():
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / "DragonCompanion"
    if sys.platform == "darwin":
        return Path.home() / "Library/Application Support/DragonCompanion"
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "dragon-companion"


@dataclass
class Settings:
    provider: str = "codex"
    data_root: str = ""
    snapshot_file: str = ""
    database: str = ""
    refresh_seconds: float = 4
    scale: float = 1
    font_family: str = ""
    desktop_processes: tuple[str, ...] = ("ChatGPT.exe", "Codex.exe")
    desktop_command: tuple[str, ...] = ()
    task_url: str = "codex://threads/{id}"
    new_chat_url: str = "codex://threads/new"
    hover_delay_ms: int = 350

    @property
    def codex_home(self):
        return Path(self.data_root or os.environ.get("CODEX_HOME", Path.home() / ".codex")).expanduser()

    @classmethod
    def load(cls, path: Path | None = None):
        path = path or config_directory() / "config.json"
        if not path.exists():
            return cls()
        data = json.loads(path.read_text(encoding="utf-8"))
        known = {field.name for field in fields(cls)}
        unknown = set(data) - known
        if unknown:
            raise ValueError("Unknown configuration keys: " + ", ".join(sorted(unknown)))
        for key in ("desktop_processes", "desktop_command"):
            if key in data:
                data[key] = tuple(data[key])
        settings = cls(**data)
        if settings.refresh_seconds < 1 or settings.scale <= 0:
            raise ValueError("refresh_seconds must be >= 1 and scale must be positive")
        for key in ("data_root", "database", "snapshot_file"):
            value = getattr(settings, key)
            if value and not Path(value).expanduser().is_absolute():
                setattr(settings, key, str((path.parent / value).resolve()))
        return settings

    def save(self, path=None):
        path = path or config_directory() / "config.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")

"""Read-only local Codex and portable JSON adapters."""
import json
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

from .models import Snapshot, Task


class JsonProvider:
    def __init__(self, path):
        self.path = Path(path)

    def snapshot(self):
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return Snapshot([Task(**row) for row in data.get("tasks", [])], data.get("rate_limits"))
        except (OSError, ValueError, TypeError) as exc:
            return Snapshot(error=f"数据源不可用：{exc}")


class CodexProvider:
    def __init__(self, settings):
        self.root = settings.codex_home
        self.database = Path(settings.database).expanduser() if settings.database else None
        self.cache = {}

    def read_log(self, path):
        try:
            path = Path(path)
            if not path.is_absolute():
                path = self.root / path
            stat = path.stat()
            key = (stat.st_mtime_ns, stat.st_size)
            if path in self.cache and self.cache[path][0] == key:
                return self.cache[path][1]
            state, used, window, rate, rate_at = "idle", None, None, None, 0
            with path.open("rb") as stream:
                for raw in stream:
                    if b'"event_msg"' not in raw:
                        continue
                    try:
                        event = json.loads(raw)
                        payload = event.get("payload") or {}
                        kind = payload.get("type")
                        if kind == "task_started":
                            state = "running"
                            window = payload.get("model_context_window") or window
                        elif kind == "task_complete":
                            state = "ready"
                        elif kind in ("task_failed", "turn_aborted"):
                            state = "blocked"
                        elif kind == "token_count":
                            info = payload.get("info") or {}
                            used = (info.get("last_token_usage") or {}).get("input_tokens", used)
                            window = info.get("model_context_window") or window
                            if payload.get("rate_limits"):
                                stamp = datetime.fromisoformat(event["timestamp"].replace("Z", "+00:00")).timestamp()
                                if stamp >= rate_at:
                                    rate, rate_at = payload["rate_limits"], stamp
                    except (ValueError, TypeError, KeyError, AttributeError):
                        continue
            result = state, used, window, rate, rate_at
            self.cache[path] = (key, result)
            return result
        except OSError:
            return "unknown", None, None, None, 0

    def snapshot(self):
        candidates = list(self.root.glob("state_*.sqlite"))
        def version(path):
            try:
                return int(path.stem.split("_")[-1])
            except ValueError:
                return -1
        database = self.database or (max(candidates, key=version) if candidates else None)
        if not database or not database.exists():
            return Snapshot(error="未找到 Codex 数据源，可在 config.json 配置 data_root")
        try:
            with closing(sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True, timeout=1)) as conn:
                columns = {row[1] for row in conn.execute("PRAGMA table_info(threads)")}
                required = {"id", "title", "rollout_path", "updated_at"}
                if not required <= columns:
                    return Snapshot(error="当前 Codex 数据库结构不受支持")
                title = "coalesce(nullif(name,''),title)" if "name" in columns else "title"
                filters = []
                if "archived" in columns:
                    filters.append("archived=0")
                if "agent_role" in columns:
                    filters.append("(agent_role is null or agent_role='')")
                if "thread_source" in columns:
                    filters.append("(thread_source is null or thread_source not in ('subagent','guardian_review'))")
                where = "where " + " and ".join(filters) if filters else ""
                rows = conn.execute(f"select id,{title},rollout_path,updated_at from threads {where} order by updated_at desc limit 30").fetchall()
            tasks, latest, latest_at = [], None, 0
            for task_id, title, path, stamp in rows:
                if not path:
                    continue
                state, used, window, rate, rate_at = self.read_log(path)
                if rate and rate_at >= latest_at:
                    latest, latest_at = rate, rate_at
                tasks.append(Task(task_id, " ".join((title or "未命名对话").split()), state, used, window, stamp))
            return Snapshot(tasks, latest)
        except (OSError, sqlite3.Error) as exc:
            return Snapshot(error=f"数据源暂不可用：{exc}")


def make_provider(settings):
    if settings.provider == "json":
        return JsonProvider(settings.snapshot_file)
    if settings.provider == "codex":
        return CodexProvider(settings)
    raise ValueError(f"Unsupported provider: {settings.provider}")

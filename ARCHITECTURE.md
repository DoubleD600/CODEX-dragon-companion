# Architecture

```
CodexProvider / JsonProvider → Snapshot(Task[], rate_limits, error)
                                      ↓
                             background worker → PetWindow
                                      ↓
                              DesktopAdapter → OS / URI handler
```

- `models.py`: normalized immutable task/snapshot records and `TaskProvider` protocol. States: `idle`, `running`, `ready`, `blocked`, `unknown`. A provider implements `snapshot() -> Snapshot`; wire it into `make_provider` to add sources.
- `providers.py`: read-only SQLite/JSONL adapter with schema checks and mtime cache; portable JSON adapter. No GUI imports.
- `config.py`: user configuration, platform-specific locations, no machine-specific constants.
- `desktop.py`: process/window discovery, desktop focus, configurable URI dispatch and shortcut installation. Windows API calls are confined here.
- `ui.py`: Qt logical-pixel geometry, asynchronous polling, preserved sprite alpha, antialiased vector panels and system font fallback. Screen geometry uses Qt coordinates consistently for high DPI.
- `__main__.py`: CLI, per-user instance lock, local IPC restore and startup watcher.

No task content or credentials enter the release. JSON producers should replace the snapshot file atomically; errors are reported in the panel and retried. Rate fields follow `primary` / `secondary` objects with `used_percent` and Unix `resets_at`; missing values remain unavailable.

The app uses packaged relative assets. Distribution is a folder rather than one-file extraction, making Qt shared libraries and license notices directly available.

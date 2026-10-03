# Release validation

Validated locally on Windows 11 x64, Python 3.14.7 / Qt 6.11.2.

- Three automated tests passed: provider/schema/title/context/cache, JSON/config handling, screen clamp/rounded alpha/close-to-tray.
- Frozen EXE successfully reads the local provider snapshot and exits normally.
- Live EXE shows a responding Dragon Companion window; repeated launch restores the same instance.
- Desktop and startup shortcuts installed successfully; startup watcher runs independently.
- Source wheel builds and includes animation/font assets.
- Transparent renderer uses premultiplied alpha, antialiased vector corners and font fallback; preview uses synthetic task data.

The Windows Computer Use helper failed to initialize (`failed to write kernel assets`, system path missing), so live mouse/menu interaction could not be independently automated. macOS/Linux distributions are not yet tested. GitHub Actions supplies additional platform test jobs; its results are separate from these local checks.

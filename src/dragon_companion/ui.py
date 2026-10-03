"""Qt translucent renderer, independent from provider and desktop implementation."""
import logging
import math
import time
from pathlib import Path

from PySide6.QtCore import QObject, QPoint, QPointF, QRectF, QRunnable, QThreadPool, QTimer, Qt, Signal
from PySide6.QtGui import QColor, QCursor, QFont, QFontDatabase, QFontMetricsF, QIcon, QImage, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon, QWidget

from .models import Snapshot

WIDTH, PET_HEIGHT, COLLAPSED_HEIGHT, HEIGHT = 380, 208, 238, 560


class WorkerSignals(QObject):
    ready = Signal(object)


class SnapshotWorker(QRunnable):
    def __init__(self, provider):
        super().__init__()
        self.provider, self.signals = provider, WorkerSignals()

    def run(self):
        try:
            snapshot = self.provider.snapshot()
        except Exception:
            logging.exception("Provider failed")
            snapshot = Snapshot(error="读取数据暂时失败，稍后自动重试")
        self.signals.ready.emit(snapshot)


class PetWindow(QWidget):
    def __init__(self, settings, provider, desktop):
        super().__init__()
        self.settings, self.provider, self.desktop = settings, provider, desktop
        self.setWindowTitle("Dragon Companion")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMouseTracking(True)
        self.scale = min(1.8, max(0.7, settings.scale))
        self.hovered = self.on_sprite = False
        self.expanded = True
        self.leave_at = None
        self.reaction_until = 0
        self.frame = 0
        self.animation_at = time.monotonic()
        self.state = "idle"
        self.snapshot = Snapshot()
        self.actions = []
        self.drag_offset = self.press_point = self.resize_origin = None
        self.press_sprite = False
        self.quitting = self.busy = False
        self.assets = Path(__file__).parent / "assets"
        self.frames = {}
        for state in ("idle", "running", "waiting", "failed", "review"):
            images = [QImage(str(path)).convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
                      for path in sorted((self.assets / state).glob("*.png"))]
            if not images or any(image.isNull() for image in images):
                raise RuntimeError(f"Skin assets missing or invalid: {state}")
            self.frames[state] = images
        for font_path in (self.assets / "fonts").glob("*.ttf"):
            QFontDatabase.addApplicationFont(str(font_path))
        available = set(QFontDatabase.families())
        choices = [settings.font_family, "Microsoft YaHei UI", "Noto Sans SC", "Noto Sans CJK SC", "PingFang SC", "Segoe UI", "Sans Serif"]
        self.family = next((family for family in choices if family in available), QApplication.font().family())
        QApplication.setFont(self.font())
        self.icon = QIcon(str(self.assets / "app.ico"))
        self.setWindowIcon(self.icon)
        self.move(90, 90)
        self.ensure_geometry()
        self.menu = self.make_menu(False)
        self.tray = QSystemTrayIcon(self.icon, self)
        self.tray.setToolTip("Dragon Companion")
        self.tray.setContextMenu(self.make_menu(True))
        self.tray.activated.connect(self.tray_activated)
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray.show()
        else:
            logging.warning("System tray unavailable; use desktop context menu to exit")
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(33)
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh)
        self.refresh_timer.start(round(settings.refresh_seconds * 1000))
        self.refresh()

    def make_menu(self, tray):
        menu = QMenu(self)
        menu.setWindowFlag(Qt.WindowType.FramelessWindowHint)
        menu.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        menu.setStyleSheet("QMenu{background:#fcfbff;color:#554862;border:1px solid #e3dced;border-radius:12px;padding:6px;}"
                           "QMenu::item{padding:8px 18px;}QMenu::item:selected{background:#ede6f7;border-radius:6px;}")
        if tray:
            menu.addAction("显示桌宠", self.show_pet)
        menu.addAction("隐藏界面", self.hide)
        menu.addAction("打开 CODEX 界面", lambda: self.safe(self.desktop.focus))
        menu.addSeparator()
        menu.addAction("退出", self.quit_app)
        return menu

    def safe(self, action):
        try:
            action()
        except Exception as exc:
            logging.exception("Desktop action failed")
            QMessageBox.warning(self, "Dragon Companion", str(exc))

    def tray_activated(self, reason):
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            self.show_pet()

    def show_pet(self):
        self.hovered = self.on_sprite = False
        self.ensure_geometry()
        self.show()
        self.raise_()
        self.update()

    def quit_app(self):
        self.quitting = True
        self.timer.stop()
        self.refresh_timer.stop()
        self.tray.hide()
        self.close()
        QApplication.quit()

    def closeEvent(self, event):
        if self.quitting:
            event.accept()
        else:
            self.hide()
            event.ignore()

    def ensure_geometry(self):
        height = HEIGHT if self.hovered and self.expanded else COLLAPSED_HEIGHT if self.hovered else PET_HEIGHT
        screen = QApplication.screenAt(self.pos() + QPoint(round(190 * self.scale), round(104 * self.scale))) or QApplication.primaryScreen()
        area = screen.availableGeometry().adjusted(8, 8, -8, -8)
        self.scale = min(self.scale, area.width() / WIDTH, area.height() / height)
        width_px, height_px = round(WIDTH * self.scale), round(height * self.scale)
        self.resize(width_px, height_px)
        x = max(area.left(), min(self.x(), area.right() + 1 - width_px))
        y = max(area.top(), min(self.y(), area.bottom() + 1 - height_px))
        self.move(x, y)

    def current_state(self):
        return "waiting" if time.monotonic() < self.reaction_until else "review" if self.on_sprite else self.state

    def image(self):
        frames = self.frames[self.current_state()]
        return frames[self.frame % len(frames)]

    def sprite_hit(self, point):
        x, y = point.x() / self.scale - 94, point.y() / self.scale
        image = self.image()
        if 0 <= x < 192 and 0 <= y < 208:
            return image.pixelColor(round(x * (image.width() - 1) / 192), round(y * (image.height() - 1) / 208)).alpha() > 64
        return False

    def tick(self):
        if not self.isVisible():
            return
        now = time.monotonic()
        point = self.mapFromGlobal(QCursor.pos())
        self.on_sprite = self.sprite_hit(point)
        inside = self.on_sprite or (self.hovered and self.rect().contains(point)) or self.drag_offset is not None or self.resize_origin is not None or self.menu.isVisible()
        if inside:
            self.leave_at = None
            if not self.hovered:
                self.hovered = True
                self.ensure_geometry()
        elif self.hovered:
            self.leave_at = self.leave_at or now
            if (now - self.leave_at) * 1000 >= self.settings.hover_delay_ms:
                self.hovered = self.on_sprite = False
                self.ensure_geometry()
        if now - self.animation_at >= 0.19:
            self.frame += 1
            self.animation_at = now
        self.update()

    def refresh(self):
        if self.busy or self.quitting:
            return
        self.busy = True
        self.worker = SnapshotWorker(self.provider)
        self.worker.signals.ready.connect(self.receive_snapshot)
        QThreadPool.globalInstance().start(self.worker)

    def receive_snapshot(self, snapshot):
        self.busy = False
        if self.quitting:
            return
        self.snapshot = snapshot
        self.state = "failed" if any(task.state == "blocked" for task in snapshot.tasks) else "running" if any(task.state == "running" for task in snapshot.tasks) else "idle"
        self.update()

    def font(self, pixels=13, bold=False):
        font = QFont(self.family)
        font.setPixelSize(pixels)
        font.setWeight(QFont.Weight.DemiBold if bold else QFont.Weight.Normal)
        font.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
        return font

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform | QPainter.RenderHint.TextAntialiasing)
        painter.scale(self.scale, self.scale)
        now = time.monotonic()
        offset = 2 * math.sin(now * 5.5) if self.on_sprite else 0
        painter.drawImage(QRectF(94, max(0, offset), 192, 208), self.image())
        self.actions = []

        def card(rect, fill="#ffffff", radius=14, action=None, border="#e6deef"):
            painter.setPen(QPen(QColor(border), 0.8))
            painter.setBrush(QColor(fill))
            painter.drawRoundedRect(rect, radius, radius)
            if action:
                self.actions.append((rect, action))

        def text(x, y, value, size=13, color="#655570", bold=False, width=320):
            painter.setPen(QColor(color))
            painter.setFont(self.font(size, bold))
            painter.drawText(QRectF(x, y, width, 24), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, value)

        if now < self.reaction_until:
            y = 25 - (0.85 - (self.reaction_until - now)) * 15
            heart = QPainterPath(QPointF(258, y + 17))
            heart.cubicTo(237, y + 4, 252, y - 3, 258, y + 5)
            heart.cubicTo(264, y - 3, 279, y + 4, 258, y + 17)
            painter.setPen(QPen(QColor("#c89bd3"), 1.3))
            painter.setBrush(QColor("#f0deee"))
            painter.drawPath(heart)
        if not self.hovered:
            return
        card(QRectF(301, 8, 33, 31), action=self.hide, radius=15)
        text(310, 11, "−", 21)
        card(QRectF(340, 8, 33, 31), action=self.hide, radius=15)
        text(348, 11, "×", 20)
        card(QRectF(14, 210, 124, 27), action=self.toggle_panel, radius=13)
        text(42, 211, "活动面板", 12)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#9b8ca9"))
        painter.drawPolygon(QPolygonF([QPointF(25, 221 if self.expanded else 225),
                                      QPointF(34, 221 if self.expanded else 225),
                                      QPointF(29.5, 227 if self.expanded else 219)]))
        if self.expanded:
            # Painted vector geometry retains fractional alpha at rounded corners.
            card(QRectF(12, 242, 356, 306), "#faf8fd", 21)
            text(27, 250, "用量概览", 18, bold=True)
            card(QRectF(251, 249, 103, 27), "#eee6f9", 13, lambda: self.safe(self.desktop.new_chat))
            text(261, 250, "＋ 新建对话", 12)
            card(QRectF(24, 282, 332, 80))
            if self.snapshot.error:
                text(35, 301, self.snapshot.error, 11, "#b77b86", width=310)
            elif self.snapshot.rate_limits:
                from datetime import datetime
                for y, key, label, color in [(287, "primary", "5 小时", "#b499d6"), (321, "secondary", "7 天", "#8ecfc0")]:
                    part = self.snapshot.rate_limits.get(key) or {}
                    value = part.get("used_percent")
                    text(35, y, label, 12)
                    text(102, y, f"已用 {value:.0f}%" if isinstance(value, (int, float)) else "暂无数据", 12)
                    if part.get("resets_at"):
                        text(235, y, "重置 " + datetime.fromtimestamp(part["resets_at"]).strftime("%m-%d %H:%M"), 10, "#9b8ca9")
                    bar = QRectF(35, y + 27, 309, 5)
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(QColor("#eee8f3"))
                    painter.drawRoundedRect(bar, 2.5, 2.5)
                    if isinstance(value, (int, float)) and value > 0:
                        painter.setBrush(QColor(color))
                        painter.drawRoundedRect(QRectF(bar.x(), bar.y(), 309 * max(0, min(100, value)) / 100, 5), 2.5, 2.5)
            else:
                text(35, 303, "用量数据暂不可用", 12, "#9b8ca9")
            text(27, 369, "活动任务", 18, bold=True)
            text(291, 370, "点击打开", 11, "#9b8ca9")
            active = [task for task in self.snapshot.tasks if task.state in ("running", "ready", "blocked")]
            active.sort(key=lambda task: ({"blocked": 0, "running": 1, "ready": 2}[task.state], -task.updated_at))
            for index, task in enumerate(active[:4]):
                y = 398 + index * 29
                card(QRectF(24, y, 332, 26), action=lambda task_id=task.id: self.safe(lambda: self.desktop.open_task(task_id)), radius=10)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor({"running": "#8ecfc0", "ready": "#b9a4d0", "blocked": "#dc9aaa"}[task.state]))
                painter.drawEllipse(QRectF(35, y + 9, 7, 7))
                title = QFontMetricsF(self.font(11)).elidedText(task.title, Qt.TextElideMode.ElideRight, 245)
                text(49, y + 1, title, 11)
                if task.context_percent is not None:
                    text(307, y + 1, f"约{task.context_percent}%", 10, "#9b8ca9")
            if not active:
                text(35, 407, "当前没有活动任务", 12, "#9b8ca9")
            text(27, 521, "上下文占用为估算值", 11, "#aa9bb5")
            self.actions.append((QRectF(280, 521, 55, 25), self.refresh))
            text(283, 521, "刷新", 12, "#897698")
            self.grip = QRectF(340, 518, 27, 26)
            grip_x, grip_y = 354, 536
        else:
            card(QRectF(335, 210, 33, 27), radius=13)
            self.grip = QRectF(335, 210, 33, 27)
            grip_x, grip_y = 354, 228
        pen = QPen(QColor("#b1a0c4"), 1.7)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        for inset in (0, 6):
            painter.drawLine(QPoint(grip_x - inset, grip_y), QPoint(grip_x + 7, grip_y - 7 - inset))

    def toggle_panel(self):
        self.expanded = not self.expanded
        self.ensure_geometry()
        self.update()

    def mousePressEvent(self, event):
        point = event.position() / self.scale
        if event.button() == Qt.MouseButton.RightButton and self.sprite_hit(event.position()):
            self.menu.popup(event.globalPosition().toPoint())
            return
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if self.hovered and getattr(self, "grip", QRectF()).contains(point):
            self.resize_origin = (event.globalPosition(), self.scale)
            return
        for rect, action in self.actions:
            if rect.contains(point):
                action()
                return
        if self.sprite_hit(event.position()):
            self.press_sprite = True
            self.press_point = event.globalPosition()
            self.drag_offset = event.globalPosition() - self.pos()

    def mouseMoveEvent(self, event):
        if self.resize_origin:
            origin, scale = self.resize_origin
            delta = event.globalPosition() - origin
            change = delta.x() if abs(delta.x()) > abs(delta.y()) else delta.y()
            self.scale = max(0.7, min(1.8, scale + change / WIDTH))
            self.ensure_geometry()
        elif self.drag_offset is not None:
            self.move((event.globalPosition() - self.drag_offset).toPoint())
            self.ensure_geometry()
        elif self.hovered and getattr(self, "grip", QRectF()).contains(event.position() / self.scale):
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        else:
            self.unsetCursor()

    def mouseReleaseEvent(self, event):
        if self.press_sprite and self.press_point is not None and (event.globalPosition() - self.press_point).manhattanLength() < 7:
            self.reaction_until = time.monotonic() + 0.85
            self.frame = 0
        self.drag_offset = self.resize_origin = self.press_point = None
        self.press_sprite = False

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.hide()

import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from dragon_companion.config import Settings
from dragon_companion.models import Task, Snapshot
from dragon_companion.providers import CodexProvider, JsonProvider

class ProviderTests(unittest.TestCase):
    def test_readonly_schema_title_and_context(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            events = [
                {"type":"event_msg","timestamp":"2026-10-01T01:00:00Z","payload":{"type":"task_started"}},
                {"type":"event_msg","timestamp":"2026-10-01T01:01:00Z","payload":{"type":"token_count","info":{"last_token_usage":{"input_tokens":200},"model_context_window":1000},"rate_limits":{"primary":{"used_percent":25}}}}]
            (root / "task.jsonl").write_text("\n".join(json.dumps(e) for e in events)+"\n{partial",encoding="utf-8")
            with sqlite3.connect(root / "state_9.sqlite") as db:
                db.execute("create table threads(id text, title text, name text, rollout_path text, updated_at real, archived int)")
                db.execute("insert into threads values('a','old',' New  title ','task.jsonl',1,0)")
                db.execute("insert into threads values('b','hidden',null,'task.jsonl',2,1)")
            db.close()
            provider = CodexProvider(Settings(data_root=temp))
            snapshot = provider.snapshot()
            self.assertIsNone(snapshot.error)
            self.assertEqual(len(snapshot.tasks),1)
            self.assertEqual(snapshot.tasks[0].title,"New title")
            self.assertEqual(snapshot.tasks[0].state,"running")
            self.assertEqual(snapshot.tasks[0].context_percent,20)
            self.assertEqual(snapshot.rate_limits["primary"]["used_percent"],25)
            self.assertEqual(provider.snapshot(),snapshot)
            with (root / "task.jsonl").open("a") as stream:
                stream.write('\n'+json.dumps({"type":"event_msg","payload":{"type":"task_complete"}}))
            self.assertEqual(provider.snapshot().tasks[0].state,"ready")

    def test_json_and_bad_configuration(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"data.json"
            path.write_text(json.dumps({"tasks":[{"id":"x","title":"portable"}]}))
            self.assertEqual(JsonProvider(path).snapshot().tasks[0].title,"portable")
            path.write_text('{broken')
            self.assertTrue(JsonProvider(path).snapshot().error)
            path.write_text('{"refresh_seconds":0}')
            with self.assertRaises(ValueError): Settings.load(path)
            Settings(scale=1.2).save(path)
            self.assertEqual(Settings.load(path).scale,1.2)

class GeometryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app=QApplication.instance() or QApplication([])

    def test_screen_clamp_alpha_and_hide(self):
        from dragon_companion.ui import PetWindow
        from dragon_companion.desktop import DesktopAdapter
        class Demo:
            def snapshot(self): return Snapshot()
        settings=Settings()
        window=PetWindow(settings,Demo(),DesktopAdapter(settings))
        window.timer.stop(); window.refresh_timer.stop()
        window.hovered=True
        window.move(10000,10000)
        window.ensure_geometry()
        area=self.app.primaryScreen().availableGeometry()
        self.assertTrue(area.contains(window.geometry()))
        image=window.grab().toImage()
        self.assertEqual(image.pixelColor(0,0).alpha(),0)
        fractional=any(0<image.pixelColor(x,y).alpha()<255 for x in range(10,40) for y in range(240,275) if x<image.width() and y<image.height())
        self.assertTrue(fractional,"rounded edges should retain smooth alpha")
        window.show(); window.close()
        self.assertFalse(window.isVisible())
        window.show_pet();self.assertTrue(window.isVisible())
        window.quitting=True;window.tray.hide();window.close()
        from PySide6.QtCore import QThreadPool
        QThreadPool.globalInstance().waitForDone()
        self.app.processEvents()

if __name__ == "__main__": unittest.main()

import tempfile
import time
from pathlib import Path
import unittest
import sys
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine_control import EngineControl


class IdleTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / 'data').mkdir()
        (self.root / 'main.py').touch()
        self.queue = {'queue_running': [], 'queue_pending': []}
        async def engine(path, data=None):
            if path == '/queue':
                return self.queue
            if path == '/gimmemusic/activity':
                return {'last_activity': time.time() - 4000}
            return {}
        self.engine = AsyncMock(side_effect=engine)
        self.control = EngineControl(self.root, self.root, 'http://127.0.0.1:8189', {}, self.engine)
        self.control.last_activity = time.time() - 1900

    def tearDown(self):
        self.temp.cleanup()

    async def test_idle_unloads_once_without_stopping_server(self):
        await self.control.tick()
        await self.control.tick()
        frees = [c for c in self.engine.call_args_list if c.args[0] == '/free']
        self.assertEqual(len(frees), 1)
        self.assertEqual(frees[0].args[1], {'unload_models': True, 'free_memory': True})
        self.assertTrue(self.control.released)

    async def test_running_and_pending_jobs_block_unloading_and_stopping(self):
        for key in ('queue_running', 'queue_pending'):
            self.queue[key] = ['job']
            await self.control.tick()
            self.assertLess(time.time() - self.control.last_activity, 2)
            with self.assertRaisesRegex(ValueError, 'running or queued'):
                await self.control.action('unload')
            with patch.object(self.control, 'process', return_value=MagicMock()) as proc:
                with self.assertRaisesRegex(ValueError, 'running or queued'):
                    await self.control.action('stop')
                proc.return_value.terminate.assert_not_called()
            self.queue[key] = []

    async def test_browser_activity_and_disabled_timer_keep_models_loaded(self):
        self.control.touch()
        await self.control.tick()
        self.assertFalse(self.control.released)
        await self.control.action('settings', 0)
        self.control.last_activity = time.time() - 4000
        await self.control.tick()
        self.assertFalse(self.control.released)
        restored = EngineControl(self.root, self.root, 'http://127.0.0.1:8189', {}, self.engine)
        self.assertEqual(restored.minutes, 0)

    async def test_comfy_interaction_keeps_models_loaded(self):
        self.engine.side_effect = None
        self.engine.side_effect = [self.queue, {'last_activity': time.time()}]
        await self.control.tick()
        self.assertFalse(self.control.released)

    async def test_unknown_comfy_activity_disables_automatic_unloading(self):
        self.engine.side_effect = [self.queue, ValueError('Bridge not installed')]
        await self.control.tick()
        self.assertFalse(self.control.released)
        self.assertFalse(self.control.bridge)

    async def test_queue_rechecked_before_unloading(self):
        self.engine.side_effect = [self.queue, {'last_activity': time.time() - 4000}, {'queue_running': ['new job'], 'queue_pending': []}]
        with self.assertRaises(ValueError):
            await self.control.tick()
        self.assertFalse(self.control.released)

    async def test_foreign_process_is_not_stopped(self):
        with patch.object(self.control, 'process', return_value=None):
            with self.assertRaisesRegex(ValueError, 'does not match'):
                await self.control.action('stop')

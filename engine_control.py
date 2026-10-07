"""Local ComfyUI process controls and queue-aware idle model unloading."""
import asyncio
import json
import os
from pathlib import Path
import subprocess
import shutil
import sys
import time
from urllib.parse import urlparse

import aiohttp
import psutil


def install_bridge(root, comfy):
    source = root / 'comfy_bridge'
    if source.is_dir() and (comfy / 'custom_nodes').is_dir():
        shutil.copytree(source, comfy / 'custom_nodes/GimmeMusic-Bridge', dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns('__pycache__'))


class EngineControl:
    def __init__(self, root, comfy, url, config, engine):
        self.root, self.comfy, self.engine = root, comfy, engine
        endpoint = urlparse(url)
        self.port = endpoint.port or 80
        self.local = endpoint.hostname in ('localhost', '127.0.0.1', '::1')
        self.python = (root / config['python']).resolve() if config.get('python') else comfy.parent / 'python_embeded/python.exe'
        if not self.python.is_file():
            self.python = Path(sys.executable)
        self.settings_path = root / 'data/engine-settings.json'
        self.minutes = 30
        if self.settings_path.is_file():
            self.minutes = json.loads(self.settings_path.read_text())['idle_minutes']
        self.last_activity = time.time()
        self.released = False
        self.bridge = False
        self.message = ''
        self.child = None
        self.lock = asyncio.Lock()

    def touch(self, generation=False):
        self.last_activity = time.time()
        if generation:
            self.released = False

    def process(self):
        if not self.local:
            return None
        main = (self.comfy / 'main.py').resolve()
        for proc in psutil.process_iter(['exe', 'cmdline', 'cwd']):
            try:
                args = proc.info['cmdline'] or []
                if not proc.info['exe'] or Path(proc.info['exe']).resolve() != self.python.resolve():
                    continue
                port = int(args[args.index('--port') + 1]) if '--port' in args else 8188
                if port != self.port:
                    continue
                if any(Path(a).name == 'main.py' and (Path(proc.info['cwd']) / a).resolve() == main for a in args[1:]):
                    return proc
            except (psutil.Error, OSError, ValueError, IndexError, TypeError):
                continue
        return None

    def snapshot(self):
        return {'idle_minutes': self.minutes, 'idle_seconds': max(0, int(time.time() - self.last_activity)),
                'released': self.released, 'activity_bridge': self.bridge, 'message': self.message,
                'starting': self.child is not None and self.child.poll() is None and self.message == 'Starting ComfyUI…'}

    async def busy(self):
        queue = await self.engine('/queue')
        return bool(queue['queue_running'] or queue['queue_pending'])

    async def unload(self):
        if await self.busy():
            raise ValueError('Models cannot be unloaded while music is running or queued.')
        await self.engine('/free', {'unload_models': True, 'free_memory': True})
        self.released = True
        self.message = 'Model unload requested. Models reload when the next run needs them.'

    async def tick(self):
        if await self.busy():
            self.touch(generation=True)
            self.message = 'Generating or queued — idle timer paused.'
            return
        try:
            activity = await self.engine('/gimmemusic/activity')
            self.last_activity = max(self.last_activity, min(time.time(), activity['last_activity']))
            self.bridge = True
        except (aiohttp.ClientError, ValueError, asyncio.TimeoutError, KeyError):
            self.bridge = False
            self.message = 'Restart ComfyUI to enable activity tracking and automatic unloading.'
            return
        if self.minutes and not self.released and time.time() - self.last_activity >= self.minutes * 60:
            async with self.lock:
                await self.unload()
        elif not self.released:
            self.message = 'Models unload after inactivity; queued runs keep them loaded.'

    async def watch(self):
        while True:
            try:
                await self.tick()
            except (aiohttp.ClientError, asyncio.TimeoutError, ValueError):
                self.bridge = False
                if self.child and self.child.poll() is not None:
                    self.message = 'Engine stopped. See data/engine.stderr.log if startup failed.'
            await asyncio.sleep(10)

    async def action(self, action, minutes=None):
        async with self.lock:
            if action == 'settings':
                if type(minutes) is not int or minutes not in (0, 15, 30, 60):
                    raise ValueError('Choose Off, 15, 30, or 60 minutes.')
                self.minutes = minutes
                self.settings_path.write_text(json.dumps({'idle_minutes': minutes}))
                self.touch()
                return
            if action == 'unload':
                await self.unload()
                return
            if not self.local or not (self.comfy / 'main.py').is_file():
                raise ValueError('Start/stop controls require a configured local ComfyUI installation.')
            proc = await asyncio.to_thread(self.process)
            if action == 'stop':
                if await self.busy():
                    raise ValueError('ComfyUI has running or queued work. Wait for it to finish before stopping.')
                if not proc:
                    raise ValueError('The running server does not match this studio’s configured ComfyUI. It was left running.')
                await asyncio.to_thread(proc.terminate)
                try:
                    await asyncio.to_thread(proc.wait, timeout=10)
                except psutil.TimeoutExpired:
                    raise ValueError('ComfyUI is still shutting down. Try again shortly.')
                self.child = None
                self.message = 'ComfyUI stopped. Your studio and library remain open.'
            elif action == 'start':
                if proc:
                    return
                # Never silently take over a different local server on the configured port.
                try:
                    await self.engine('/system_stats')
                except (aiohttp.ClientError, asyncio.TimeoutError):
                    pass
                else:
                    raise ValueError('Another server is already using the configured engine address.')
                env = os.environ.copy()
                cache = self.root / 'runtime/cache'
                temp = self.root / 'runtime/temp'
                temp.mkdir(parents=True, exist_ok=True)
                env.update(HF_HOME=str(cache / 'huggingface'), TORCH_HOME=str(cache / 'torch'),
                           XDG_CACHE_HOME=str(cache), TEMP=str(temp), TMP=str(temp),
                           HF_HUB_DISABLE_TELEMETRY='1', DO_NOT_TRACK='1')
                with (self.root / 'data/engine.stdout.log').open('w') as out, (self.root / 'data/engine.stderr.log').open('w') as err:
                    self.child = subprocess.Popen([str(self.python), '-s', str(self.comfy / 'main.py'),
                        '--windows-standalone-build', '--listen', '127.0.0.1', '--port', str(self.port)],
                        cwd=self.comfy.parent, env=env, stdout=out, stderr=err,
                        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                self.touch(generation=True)
                self.message = 'Starting ComfyUI…'
            else:
                raise ValueError('Unknown engine action.')

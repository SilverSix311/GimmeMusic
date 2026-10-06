"""Check installed CUDA, model files, node schemas and profiles without generating audio."""
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]


def verify(comfy, runtime_only=False):
    import torch
    import ctranslate2
    import faster_whisper
    import rotary_embedding_torch
    if not torch.cuda.is_available():
        raise RuntimeError('PyTorch cannot access the NVIDIA GPU. Update the NVIDIA driver, reboot, and rerun Install-GimmeMusic.bat.')
    print('CUDA ready:', torch.cuda.get_device_name(0), 'Torch', torch.__version__, flush=True)
    if runtime_only:
        return
    # Use a temporary port so the installer never interrupts an existing studio.
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    logs = ROOT / 'runtime/logs'
    logs.mkdir(parents=True, exist_ok=True)
    profiles = json.loads((ROOT / 'workflows/profiles.json').read_text(encoding='utf-8'))
    with (logs / 'verification.log').open('w', encoding='utf-8') as log:
        process = subprocess.Popen([sys.executable, '-s', str(comfy / 'main.py'), '--windows-standalone-build',
            '--listen', '127.0.0.1', '--port', str(port), '--disable-auto-launch'], cwd=comfy,
            stdout=log, stderr=subprocess.STDOUT, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        try:
            schema = None
            for _ in range(240):
                if process.poll() is not None:
                    raise RuntimeError('ComfyUI startup failed. See runtime/logs/verification.log.')
                try:
                    with urlopen(f'http://127.0.0.1:{port}/object_info', timeout=2) as response:
                        schema = json.load(response)
                    break
                except OSError:
                    time.sleep(1)
            if schema is None:
                raise RuntimeError('ComfyUI startup timed out. See runtime/logs/verification.log.')
            missing = sorted({n['class_type'] for p in profiles.values() for n in p['prompt'].values()} - schema.keys())
            if missing:
                raise RuntimeError('Required workflow nodes are missing: ' + ', '.join(missing))
            spec = schema['PlenioTranscribeLyrics']['input']
            if 'original_lyrics' not in {**spec.get('required', {}), **spec.get('optional', {})}:
                raise RuntimeError('The original-lyrics extension did not load.')
            for profile in profiles.values():
                for node in profile['prompt'].values():
                    for name, value in node['inputs'].items():
                        if isinstance(value, str) and value.endswith(('.safetensors', '.ckpt', '.bin')):
                            if not any((comfy / 'models').rglob(value)):
                                raise RuntimeError('Missing workflow model: ' + value)
            print('Song and cover profiles: all node classes and model filenames available.', flush=True)
        finally:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
    report = {'gpu': torch.cuda.get_device_name(0), 'torch': torch.__version__, 'profiles': list(profiles),
              'checked': time.time(), 'audio_render_tested': False}
    (logs / 'verification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('Portable verification passed. No audio render was queued.', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--comfy-root', required=True)
    parser.add_argument('--runtime-only', action='store_true')
    args = parser.parse_args()
    verify(Path(args.comfy_root).resolve(), args.runtime_only)

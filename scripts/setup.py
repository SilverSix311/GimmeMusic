"""Connect an existing ComfyUI installation; install pinned Plenio without overwriting it."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]


def setup(comfy, engine_url, skip_dependencies=False):
    comfy = Path(comfy).resolve()
    if not (comfy / 'main.py').is_file() or not (comfy / 'custom_nodes').is_dir():
        raise ValueError('Choose the ComfyUI directory containing main.py and custom_nodes.')
    url = urlparse(engine_url)
    if url.scheme != 'http' or url.hostname not in ('localhost', '127.0.0.1') or url.username or url.password or url.path not in ('', '/'):
        raise ValueError('Use the local ComfyUI URL, for example http://127.0.0.1:8189.')
    upstream = json.loads((ROOT / 'workflows/upstream.json').read_text())
    target = comfy / 'custom_nodes/Plenio-Music-Production-System'
    if target.exists():
        if not (target / 'plenio').is_dir():
            raise ValueError(f'{target} exists but does not look like Plenio; it was left untouched.')
        print('Using existing Plenio; checking compatibility before installing the original-lyrics extension.')
    else:
        subprocess.run(['git', 'clone', '--no-checkout', upstream['repository'], str(target)], check=True)
        subprocess.run(['git', '-C', str(target), 'checkout', '--detach', upstream['commit']], check=True)
    subprocess.run([sys.executable, str(ROOT / 'scripts/install_lyrics.py'), str(target)], check=True)
    if not skip_dependencies:
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', str(ROOT / 'requirements.txt'), '-r', str(target / 'requirements.txt'), 'faster-whisper', 'rotary-embedding-torch'], check=True)
        if sys.platform == 'win32':
            subprocess.run([sys.executable, '-m', 'pip', 'install', 'nvidia-cublas-cu12', 'nvidia-cudnn-cu12'], check=True)
    # Spawned transcription workers must also be able to import Plenio.
    for pth in Path(sys.executable).parent.glob('python*._pth'):
        lines = pth.read_text().splitlines()
        path = str(target)
        if path not in lines and not any((pth.parent / line).resolve() == target for line in lines if line and not line.startswith(('#', 'import '))):
            pth.write_text('\n'.join(lines + [path]) + '\n')
    destination = comfy / 'user/default/workflows/GimmeMusic'
    destination.mkdir(parents=True, exist_ok=True)
    for source in (ROOT / 'workflows/comfyui').glob('*.json'):
        if not (destination / source.name).exists():
            shutil.copy2(source, destination / source.name)
    config = {'comfy_root': str(comfy), 'engine_url': engine_url.rstrip('/'), 'python': sys.executable}
    (ROOT / 'config.json').write_text(json.dumps(config, indent=2) + '\n')
    print('Saved local config.json; existing workflow files and studio profiles were preserved.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--comfy-root', required=True)
    parser.add_argument('--engine-url', default='http://127.0.0.1:8189')
    parser.add_argument('--skip-dependencies', action='store_true')
    args = parser.parse_args()
    setup(args.comfy_root, args.engine_url, args.skip_dependencies)

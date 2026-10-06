"""Download the bundled song/cover model manifest. Requires curl for resumable downloads."""
import argparse
import json
import hashlib
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def verified(path, model):
    if not path.is_file() or path.stat().st_size != model['size']:
        return False
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest() == model['sha256']


def download(comfy_root, verify_only=False):
    comfy = Path(comfy_root).resolve()
    if not (comfy / 'main.py').is_file():
        raise ValueError('ComfyUI root must contain main.py.')
    for model in json.loads((ROOT / 'workflows/models.json').read_text()):
        target = comfy / 'models' / model['folder'] / model['file']
        if verified(target, model):
            print('Verified:', target.name, flush=True)
            continue
        if verify_only:
            raise ValueError('Missing or damaged model: ' + str(target))
        if target.exists():
            raise ValueError('Existing model differs from the pinned manifest; it was not overwritten: ' + str(target))
        target.parent.mkdir(parents=True, exist_ok=True)
        part = target.with_suffix(target.suffix + '.part')
        print('Downloading:', target.name, flush=True)
        if not verified(part, model):
            if part.is_file() and part.stat().st_size >= model['size']:
                part.unlink()  # A complete but invalid temporary download cannot be resumed.
            subprocess.run(['curl.exe' if os.name == 'nt' else 'curl', '-L', '--fail', '--retry', '4', '-C', '-', '-o', str(part), model['url']], check=True)
        if not verified(part, model):
            part.unlink()
            raise ValueError('Download checksum failed for ' + target.name + '. Rerun the installer to retry.')
        part.replace(target)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--comfy-root', required=True)
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args()
    download(args.comfy_root, args.verify_only)

"""Download the bundled song/cover model manifest. Requires curl for resumable downloads."""
import argparse
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def download(comfy_root):
    comfy = Path(comfy_root).resolve()
    if not (comfy / 'main.py').is_file():
        raise ValueError('ComfyUI root must contain main.py.')
    for model in json.loads((ROOT / 'workflows/models.json').read_text()):
        target = comfy / 'models' / model['folder'] / model['file']
        if target.is_file():
            print('Already present:', target.name)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        part = target.with_suffix(target.suffix + '.part')
        print('Downloading:', target.name, flush=True)
        subprocess.run(['curl', '-L', '--fail', '--retry', '4', '-C', '-', '-o', str(part), model['url']], check=True)
        part.replace(target)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--comfy-root', required=True)
    args = parser.parse_args()
    download(args.comfy_root)

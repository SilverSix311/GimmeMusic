"""Install GimmeMusic's optional source-lyrics input into the pinned Plenio node."""
from pathlib import Path
import shutil
import subprocess


def install(target):
    target = Path(target).resolve()
    patches = Path(__file__).resolve().parents[1] / 'patches'
    patch = str(patches / 'original-lyrics.patch')
    command = ['git', '-C', str(target), 'apply']
    applied = subprocess.run(command + ['--reverse', '--check', patch], capture_output=True).returncode == 0
    if not applied:
        check = subprocess.run(command + ['--check', patch], capture_output=True, text=True)
        if check.returncode:
            raise ValueError('The original-lyrics extension does not match this Plenio version. No patch was applied. ' + check.stderr)
        subprocess.run(command + [patch], check=True)
    shutil.copy2(patches / 'original_lyrics.py', target / 'plenio/core/original_lyrics.py')
    print('Original-lyrics input installed. Restart ComfyUI to load it; saved workflows are unchanged.')


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('plenio_root')
    install(parser.parse_args().plenio_root)

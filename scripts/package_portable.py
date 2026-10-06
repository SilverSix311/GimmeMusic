"""Package committed application sources and the built UI; never include local data or models."""
import hashlib
import io
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def package():
    subprocess.run(['git', 'diff', '--exit-code', 'HEAD', '--'], cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
    if not (ROOT / 'dist/index.html').is_file():
        raise ValueError('Build the frontend before packaging: npm run build')
    archive = subprocess.check_output(['git', 'archive', '--format=zip', '--prefix=GimmeMusic/', 'HEAD'], cwd=ROOT)
    out = ROOT / 'runtime/releases/GimmeMusic-portable.zip'
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(archive)) as source, zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as destination:
        for item in source.infolist():
            if not item.is_dir():
                destination.writestr(item.filename, source.read(item))
        for file in sorted((ROOT / 'dist').rglob('*')):
            if file.is_file():
                destination.write(file, 'GimmeMusic/' + file.relative_to(ROOT).as_posix())
    with out.open('rb') as handle:
        digest = hashlib.file_digest(handle, 'sha256').hexdigest()
    out.with_name('SHA256SUMS.txt').write_text(digest + '  ' + out.name + '\n', encoding='utf-8')
    print(out)


if __name__ == '__main__':
    package()

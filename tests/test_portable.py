import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('models_download', ROOT / 'scripts/download_models.py')
downloader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(downloader)


class ModelDownloadTests(unittest.TestCase):
    def test_corrupt_existing_model_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'main.py').touch()
            (root / 'workflows').mkdir()
            target = root / 'models/test/model.bin'
            target.parent.mkdir(parents=True)
            target.write_bytes(b'corrupt')
            model = {'folder': 'test', 'file': 'model.bin', 'size': 4, 'sha256': hashlib.sha256(b'good').hexdigest(), 'url': 'unused'}
            (root / 'workflows/models.json').write_text(json.dumps([model]))
            with patch.object(downloader, 'ROOT', root), patch.object(downloader.subprocess, 'run') as run:
                with self.assertRaisesRegex(ValueError, 'not overwritten'):
                    downloader.download(root)
                self.assertEqual(target.read_bytes(), b'corrupt')
                run.assert_not_called()

    def test_verified_partial_is_promoted_and_rerun_skips_network(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'main.py').touch()
            (root / 'workflows').mkdir()
            target = root / 'models/test/model.bin'
            target.parent.mkdir(parents=True)
            target.with_suffix('.bin.part').write_bytes(b'good')
            model = {'folder': 'test', 'file': 'model.bin', 'size': 4, 'sha256': hashlib.sha256(b'good').hexdigest(), 'url': 'unused'}
            (root / 'workflows/models.json').write_text(json.dumps([model]))
            with patch.object(downloader, 'ROOT', root), patch.object(downloader.subprocess, 'run') as run:
                downloader.download(root)
                downloader.download(root, verify_only=True)
                run.assert_not_called()
            self.assertEqual(target.read_bytes(), b'good')

    def test_manifest_covers_both_profiles_and_asr(self):
        models = json.loads((ROOT / 'workflows/models.json').read_text())
        profiles = json.loads((ROOT / 'workflows/profiles.json').read_text())
        names = {m['file'] for m in models}
        for profile in profiles.values():
            for node in profile['prompt'].values():
                for value in node['inputs'].values():
                    if isinstance(value, str) and value.endswith(('.bin', '.ckpt', '.safetensors')):
                        self.assertIn(value, names)
        self.assertIn('model.bin', names)
        for model in models:
            self.assertGreater(model['size'], 0)
            self.assertRegex(model['sha256'], '^[a-f0-9]{64}$')
            self.assertNotIn('/resolve/main/', model['url'])

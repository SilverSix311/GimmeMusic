import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('studio_setup', Path(__file__).resolve().parents[1] / 'scripts/setup.py')
setup_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup_module)


class SetupTests(unittest.TestCase):
    def test_preserves_existing_install_and_workflows(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            comfy = root / 'ComfyUI'
            (comfy / 'custom_nodes/Plenio-Music-Production-System/plenio').mkdir(parents=True)
            (comfy / 'main.py').touch()
            workflows = root / 'workflows/comfyui'
            workflows.mkdir(parents=True)
            (workflows / 'example.json').write_text('{"new":true}')
            (root / 'workflows/upstream.json').write_text('{}')
            dest = comfy / 'user/default/workflows/GimmeMusic'
            dest.mkdir(parents=True)
            (dest / 'example.json').write_text('{"user":true}')
            python = root / 'python.exe'
            pth = root / 'python312._pth'
            pth.write_text('.\nimport site\n')
            with patch.object(setup_module, 'ROOT', root), patch.object(setup_module.sys, 'executable', str(python)), patch.object(setup_module.subprocess, 'run') as run:
                setup_module.setup(comfy, 'http://127.0.0.1:8189', True)
                setup_module.setup(comfy, 'http://127.0.0.1:8189', True)
                self.assertEqual(run.call_count, 2)
                self.assertIn("install_lyrics.py", run.call_args.args[0][1])
            self.assertEqual(json.loads((dest / 'example.json').read_text()), {'user': True})
            self.assertEqual(len(pth.read_text().splitlines()), 3)
            self.assertEqual(json.loads((root / 'config.json').read_text())['comfy_root'], str(comfy))

    def test_rejects_invalid_install(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                setup_module.setup(directory, 'http://127.0.0.1:8189', True)

    def test_portable_paths_survive_moving_the_folder(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            comfy = root / 'runtime/ComfyUI_windows_portable/ComfyUI'
            (comfy / 'custom_nodes/Plenio-Music-Production-System/plenio').mkdir(parents=True)
            (comfy / 'main.py').touch()
            (root / 'workflows/studio').mkdir(parents=True)
            (root / 'workflows/studio/GimmeMusic - song.json').write_text('{}')
            (root / 'workflows/upstream.json').write_text('{}')
            python = comfy.parent / 'python_embeded/python.exe'
            python.parent.mkdir()
            python.touch()
            pth = python.parent / 'python312._pth'
            pth.write_text('.\nimport site\n')
            with patch.object(setup_module, 'ROOT', root), patch.object(setup_module.sys, 'executable', str(python)), patch.object(setup_module.subprocess, 'run'):
                setup_module.setup(comfy, 'http://127.0.0.1:8189', True, portable=True)
            config = json.loads((root / 'config.json').read_text())
            self.assertTrue(config['portable'])
            self.assertFalse(Path(config['comfy_root']).is_absolute())
            self.assertFalse(Path(config['python']).is_absolute())
            self.assertEqual((root / config['python']).resolve(), python.resolve())
            self.assertFalse(Path(pth.read_text().splitlines()[-1]).is_absolute())
            self.assertTrue((comfy / 'user/default/workflows/GimmeMusic/GimmeMusic - song.json').is_file())

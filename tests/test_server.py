import copy
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server
server.studio.profiles = server.read_json(server.ROOT / 'workflows/profiles.json', {})


class GraphTests(unittest.TestCase):
    def test_all_vocal_modes_supply_required_children(self):
        schema = server.read_json(Path(__file__).with_name('node-schema.json'))
        for profile in server.studio.profiles.values():
            original = copy.deepcopy(profile['prompt'])
            _, brief = server.brief_node(original)
            branches = schema[brief['class_type']]['input']['required']['vocals'][1]['options']
            for branch in branches:
                params = {'fields': {'vocals': branch['key']}, 'randomize': True}
                result = server.build_prompt(profile, params, schema)
                _, changed = server.brief_node(result)
                for key, spec in branch.get('inputs', {}).get('required', {}).items():
                    self.assertIn('vocals.' + key, changed['inputs'])
                self.assertEqual(profile['prompt'], original)
                for key, node in original.items():
                    self.assertEqual(node['class_type'], result[key]['class_type'])
                    for name, value in node['inputs'].items():
                        if isinstance(value, list):
                            self.assertEqual(value, result[key]['inputs'][name])

    def test_seed_upper_boundary_fits_refinement_node(self):
        with patch.object(server.secrets, 'randbelow', side_effect=lambda maximum: maximum - 1):
            for profile in server.studio.profiles.values():
                prompt = server.build_prompt(profile, {'randomize': True})
                for node in prompt.values():
                    for name in ('seed', 'noise_seed', 'sampling_mode.seed'):
                        value = node['inputs'].get(name)
                        if isinstance(value, int):
                            self.assertLessEqual(value, 4294967295)

    def test_new_branch_accepts_custom_settings(self):
        schema = server.read_json(Path(__file__).with_name('node-schema.json'))
        result = server.build_prompt(server.studio.profiles['cover'], {'fields': {'vocals': 'instrumental', 'vocals.melody': 'accompaniment only', 'vocals.lead_instrument': 'piano'}}, schema)
        _, brief = server.brief_node(result)
        self.assertEqual(brief['inputs']['vocals.melody'], 'accompaniment only')
        self.assertEqual(brief['inputs']['vocals.lead_instrument'], 'piano')
        result = server.build_prompt(server.studio.profiles['cover'], {'fields': {'vocals': 'new lyrics', 'vocals.phrasing_reference': True}}, schema)
        self.assertTrue(server.brief_node(result)[1]['inputs']['vocals.phrasing_reference'])

    def test_preserve_is_exact_copy(self):
        self.assertEqual(set(server.studio.profiles), {'song', 'cover'})
        for profile in server.studio.profiles.values():
            result = server.build_prompt(profile, {})
            self.assertEqual(result, profile['prompt'])
            self.assertIsNot(result, profile['prompt'])

    def test_run_changes_preserve_topology_and_original(self):
        for profile in server.studio.profiles.values():
            original = copy.deepcopy(profile['prompt'])
            result = server.build_prompt(profile, {'fields': {'description': 'Test sound'}, 'randomize': True, 'lyricsMode': 'manual', 'lyrics': 'Test lyrics'})
            self.assertEqual(profile['prompt'], original)
            self.assertEqual(set(result), set(original))
            changed_seeds = 0
            for key, node in original.items():
                self.assertEqual(result[key]['class_type'], node['class_type'])
                for field, value in node['inputs'].items():
                    if isinstance(value, list):
                        self.assertEqual(result[key]['inputs'][field], value)
                    if field in ('seed', 'noise_seed', 'sampling_mode.seed') and isinstance(value, int):
                        changed_seeds += result[key]['inputs'][field] != value
            self.assertGreater(changed_seeds, 0)

    def test_paths_cannot_escape(self):
        with self.assertRaises(server.web.HTTPForbidden):
            server.contained(server.OUTPUT, '../secret.txt')


class QueueTests(unittest.IsolatedAsyncioTestCase):
    async def test_first_run_uses_bundled_profiles_without_engine_history(self):
        with patch.object(server.studio, 'profiles', {}), patch.object(server.studio, 'engine', AsyncMock()) as engine, patch.object(server, 'write_json'):
            await server.studio.bootstrap()
            self.assertEqual(set(server.studio.profiles), {'song', 'cover'})
            engine.assert_not_called()

    async def test_batch_submits_independent_graphs(self):
        request = AsyncMock()
        request.json.return_value = {'profile': 'song', 'count': 2, 'randomize': True}
        with patch.object(server.studio, 'engine', AsyncMock(return_value={})), patch.object(server.studio, 'submit', new=AsyncMock(side_effect=['one', 'two'])) as submit:
            response = await server.generate(request)
            self.assertEqual(json.loads(response.body)['ids'], ['one', 'two'])
            self.assertNotEqual(submit.call_args_list[0].args[0], submit.call_args_list[1].args[0])

    async def test_batch_limit(self):
        request = AsyncMock()
        request.json.return_value = {'profile': 'song', 'count': 9}
        with self.assertRaises(ValueError):
            await server.generate(request)

    async def test_continued_review_does_not_reappear(self):
        fake_jobs = {'old': {'id': 'old', 'status': 'continued', 'review': [], 'profile': 'cover'}}
        engine = AsyncMock(side_effect=[{'old': {'status': {'status_str': 'success'}, 'outputs': {'sheet': {'plenio_sheet': [{'waiting': True}]}}}}, {'queue_running': [], 'queue_pending': []}])
        with patch.object(server.studio, 'jobs', fake_jobs), patch.object(server.studio, 'engine', engine), patch.object(server, 'write_json'):
            response = await server.jobs(None)
            self.assertEqual(json.loads(response.body)[0]['status'], 'continued')

    async def test_review_requeues_with_same_seed(self):
        prompt = {'sheet': {'class_type': 'PlenioSongSheet', 'inputs': {'sheet_state': '{}'}}, 'seed': {'class_type': 'SeedNode', 'inputs': {'seed': 42}}}
        sheet = {'node': 'sheet', 'owned': ['lyrics'], 'docs': {'lyrics': {'text': 'Old', 'upstream': 'Old'}}, 'review': 'always'}
        job = {'id': 'old', 'profile': 'song', 'status': 'review', 'prompt': prompt, 'review': [sheet]}
        request = AsyncMock()
        request.match_info = {'id': 'old'}
        request.json.return_value = {'edits': {'sheet': {'lyrics': 'New'}}}
        with patch.object(server.studio, 'jobs', {'old': job}), patch.object(server.studio, 'engine', AsyncMock(return_value={'fingerprint': 'checked', 'findings': []})), patch.object(server.studio, 'submit', AsyncMock(return_value='next')) as submit, patch.object(server, 'write_json'):
            await server.approve(request)
            sent = submit.call_args.args[0]
            self.assertEqual(sent['seed']['inputs']['seed'], 42)
            self.assertEqual(json.loads(sent['sheet']['inputs']['sheet_state'])['review']['approved_fingerprint'], 'checked')
            self.assertEqual(prompt['sheet']['inputs']['sheet_state'], '{}')
            self.assertEqual(job['status'], 'continued')


if __name__ == '__main__':
    unittest.main()

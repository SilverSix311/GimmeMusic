import copy
import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server
from workflow_edit import apply_node_inputs, apply_documents


class EditingTests(unittest.TestCase):
    def test_title_applies_to_song_and_cover_without_rewiring(self):
        for profile in server.read_json(server.ROOT / 'workflows/profiles.json').values():
            original = copy.deepcopy(profile['prompt'])
            result = server.build_prompt(profile, {'title': 'A new title'})
            sheets = [n for n in result.values() if n['class_type'] == 'PlenioSongSheet' and 'title' in n['inputs']]
            self.assertTrue(sheets)
            for node in sheets:
                self.assertEqual(json.loads(node['inputs']['sheet_state'])['docs']['title']['text'], 'A new title')
            self.assertEqual(profile['prompt'], original)
            for key, node in original.items():
                for name, value in node['inputs'].items():
                    if isinstance(value, list):
                        self.assertEqual(result[key]['inputs'][name], value)

    def test_setting_bounds_and_links(self):
        prompt = {'a': {'class_type': 'Sampler', 'inputs': {'steps': 32, 'model': ['upstream', 0]}}}
        schema = {'Sampler': {'input': {'required': {'steps': ['INT', {'min': 1, 'max': 100}], 'model': ['MODEL']}}}}
        apply_node_inputs(prompt, {'a': {'steps': 24}}, schema)
        self.assertEqual(prompt['a']['inputs']['steps'], 24)
        for edits in ({'steps': 101}, {'steps': float('nan')}, {'model': 'replace'}, {'unknown': 1}):
            with self.assertRaises(ValueError):
                apply_node_inputs(prompt, {'a': edits}, schema)

    def test_sheet_changes_clear_approval_and_auto_removes_override(self):
        state = {'schema': 'plenio.sheet_state/1', 'docs': {}, 'review': {'approved_fingerprint': 'old'}}
        prompt = {'s': {'class_type': 'PlenioSongSheet', 'inputs': {'score': ['up', 0], 'sheet_state': json.dumps(state)}}}
        apply_documents(prompt, {'s': {'score': {'state': 'manual', 'text': 'X:1\nK:C\nC4|'}}})
        result = json.loads(prompt['s']['inputs']['sheet_state'])
        self.assertNotIn('review', result)
        self.assertEqual(result['docs']['score']['state'], 'manual')
        apply_documents(prompt, {'s': {'score': {'state': 'auto'}}})
        self.assertEqual(json.loads(prompt['s']['inputs']['sheet_state'])['docs'], {})
        with self.assertRaises(ValueError):
            apply_documents(prompt, {'s': {'title': {'state': 'manual', 'text': 'Not owned'}}})

    def test_specific_node_seed_beats_common_fixed_seed(self):
        profile = {'prompt': {'seed': {'class_type': 'SeedNode', 'inputs': {'seed': 1}}}}
        schema = {'SeedNode': {'input': {'required': {'seed': ['INT', {'min': 0, 'max': 100}]}}}}
        result = server.build_prompt(profile, {'seed': 2, 'nodeInputs': {'seed': {'seed': 3}}}, schema)
        self.assertEqual(result['seed']['inputs']['seed'], 3)

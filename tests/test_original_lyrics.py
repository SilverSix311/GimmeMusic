import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server


class OriginalLyricsTests(unittest.TestCase):
    def setUp(self):
        self.profile = server.read_json(server.ROOT / 'workflows/profiles.json')['cover']
        self.schema = server.read_json(Path(__file__).with_name('node-schema.json'))
        self.schema.setdefault('PlenioTranscribeLyrics', {}).setdefault('input', {}).setdefault('optional', {})['original_lyrics'] = ['STRING', {}]

    def test_source_words_feed_transcription_and_clear_old_sheet_overrides(self):
        before = copy.deepcopy(self.profile)
        edits = {k: {'lyrics': {'state': 'manual', 'text': 'Old replacement'}}
                 for k, n in self.profile['prompt'].items() if n['class_type'] == 'PlenioSongSheet' and 'lyrics' in n['inputs']}
        result = server.build_prompt(self.profile, {'lyricsMode': 'original', 'originalLyrics': 'Source words',
            'lyricsIntent': 'custom', 'sheetEdits': edits, 'fields': {'vocals': 'new lyrics'}}, self.schema)
        self.assertEqual(server.brief_node(result)[1]['inputs']['vocals'], 'original lyrics')
        targets = [n for n in result.values() if n['class_type'] == 'PlenioTranscribeLyrics' and 'expected_lyrics' not in n['inputs']]
        self.assertTrue(targets)
        self.assertTrue(all(n['inputs']['original_lyrics'] == 'Source words' for n in targets))
        for key in edits:
            self.assertNotEqual(json.loads(result[key]['inputs']['sheet_state']).get('docs', {}).get('lyrics', {}).get('state'), 'manual')
        self.assertEqual(self.profile, before)
        for key, node in before['prompt'].items():
            for field, value in node['inputs'].items():
                if isinstance(value, list):
                    self.assertEqual(result[key]['inputs'][field], value)
        restored = server.default_form({'prompt': result})
        self.assertEqual(restored['originalLyrics'], 'Source words')
        self.assertEqual(restored['lyricsMode'], 'original')
        auto = server.build_prompt({'prompt': result}, {'lyricsMode': 'auto'}, self.schema)
        self.assertTrue(all('original_lyrics' not in n['inputs'] for n in auto.values() if n['class_type'] == 'PlenioTranscribeLyrics'))

    def test_blank_and_uninstalled_original_input_fail_before_queue(self):
        with self.assertRaisesRegex(ValueError, 'Paste the original'):
            server.build_prompt(self.profile, {'lyricsMode': 'original'}, self.schema)
        with self.assertRaisesRegex(ValueError, 'extension'):
            server.build_prompt(self.profile, {'lyricsMode': 'original', 'originalLyrics': 'Words'}, {})


try:
    from plenio.core.asr import AsrWord
    from plenio.core.original_lyrics import original_words
    from plenio.core.alignment import align, normalize_words
except ImportError:
    original_words = None


@unittest.skipIf(original_words is None, 'Native Plenio integration requires the installed extension')
class AlignmentIntegrationTests(unittest.TestCase):
    def test_native_node_verifies_plain_lyrics_against_untouched_asr(self):
        from plenio.comfy.nodes import transcribe_lyrics as node
        from plenio.core.asr import AsrResult
        heard = 'I hear the wrong tonight we rise into the light'
        result = AsrResult('test', 'test', 'en', 1.0, (), tuple(AsrWord(i, i + .8, w) for i, w in enumerate(heard.split())))
        with patch.object(node, '_run_asr', return_value=result) as asr, patch.object(node.host, 'audio_sha256', return_value='test'), patch.object(node.host, 'Progress', MagicMock()), patch.object(node, 'asr_notes') as notes:
            output = node.PlenioTranscribeLyrics.execute(None, engine='faster-whisper large-v3', language='English', original_lyrics='I hear the thunder tonight we rise into the light')
            self.assertEqual(asr.call_count, 1)
            self.assertIn('thunder', output.result[0])
            self.assertEqual(output.result[1], heard)
            reference = output.result[3].data['original_lyrics']
            self.assertEqual(reference['estimated_words'], 1)
            self.assertGreater(reference['verification']['wer'], 0)
            self.assertEqual(notes.return_value.put.call_args.args[0]['original_lyrics']['transcript'], heard)

    def test_corrections_keep_source_words_and_flag_estimated_timing(self):
        heard = [AsrWord(i, i + .8, word) for i, word in enumerate('I hear the wrong tonight'.split())]
        words, report = original_words('[Verse]\nI hear the thunder tonight', heard)
        self.assertEqual([w.word for w in words], 'I hear the thunder tonight'.split())
        self.assertEqual(report['matched_words'], 4)
        self.assertEqual(report['estimated_words'], 1)
        self.assertEqual(words[3].p, 0)
        self.assertEqual(words[3].start, 3)
        draft = align(words, [], timeline=None, supplied_words=True)
        self.assertEqual(normalize_words(draft.lyrics), normalize_words('I hear the thunder tonight'))

    def test_repeats_insertions_and_asr_inventions(self):
        heard = [AsrWord(i, i + .5, w) for i, w in enumerate('hey you hey you thanks for watching'.split())]
        words, report = original_words('Hey you\nHey you\nStay', heard)
        self.assertEqual([w.word for w in words], ['Hey', 'you', 'Hey', 'you', 'Stay'])
        self.assertEqual(report['matched_words'], 4)
        self.assertTrue(all(a.start <= b.start for a, b in zip(words, words[1:])))

    def test_empty_asr_and_section_only_input_do_not_fake_alignment(self):
        with self.assertRaisesRegex(ValueError, 'No source words'):
            original_words('Hello', [])
        with self.assertRaisesRegex(ValueError, 'section labels'):
            original_words('[Verse]', [AsrWord(0, 1, 'Hi')])

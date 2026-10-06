import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server


class ProjectsTests(unittest.IsolatedAsyncioTestCase):
    async def test_create_rename_draft_and_assignment_persist(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(server, 'PROJECTS', Path(directory)/'projects.json'):
            request=AsyncMock(); request.method='POST'; request.json.return_value={'name':'My covers'}
            created=json.loads((await server.projects_api(request)).body)
            project_id=created['id']
            request.json.return_value={'id':project_id,'name':'Album drafts','draft':{'profile':'cover','lyrics':'My words'}}
            await server.projects_api(request)
            self.assertEqual(server.project_store()['projects'][project_id]['draft']['lyrics'],'My words')
            self.assertEqual(server.project_store()['projects'][project_id]['name'],'Album drafts')
            request.match_info={'id':'track'}; request.json.return_value={'projectId':project_id}
            with patch.object(server.studio,'library',return_value=[{'id':'track'}]):
                await server.assign_project(request)
                self.assertEqual(server.track_project('elsewhere/song.plenio.json','track',server.project_store()),project_id)
                request.json.return_value={'projectId':None}; await server.assign_project(request)
                self.assertIsNone(server.track_project('plenio/gimmemusic-projects/'+project_id+'/song.plenio.json','track',server.project_store()))

    async def test_project_generations_are_routed_without_mutating_profile(self):
        profile=server.read_json(server.ROOT/'workflows/profiles.json')['song']
        original=copy.deepcopy(profile)
        request=AsyncMock();request.json.return_value={'profile':'song','count':2,'projectId':'project','randomize':True}
        with patch.object(server,'editor_profile',return_value=(profile,{})), patch.object(server,'project_store',return_value={'projects':{'project':{}},'tracks':{}}),patch.object(server.studio,'engine',AsyncMock(return_value={})),patch.object(server.studio,'submit',AsyncMock(side_effect=['a','b'])) as submit:
            result=json.loads((await server.generate(request)).body)
            self.assertEqual(result['ids'],['a','b'])
            for call in submit.call_args_list:
                self.assertEqual(call.kwargs['project_id'],'project')
                folders=[n['inputs']['folder'] for n in call.args[0].values() if n['class_type']=='PlenioExportRelease']
                self.assertEqual(folders,['plenio/gimmemusic-projects/project'])
            self.assertEqual(original,profile)

    async def test_manual_cover_lyrics_enable_vocals(self):
        profile=server.read_json(server.ROOT/'workflows/profiles.json')['cover']
        schema=server.read_json(Path(__file__).with_name('node-schema.json'))
        prompt=server.build_prompt(profile,{'fields':{'vocals':'instrumental'},'lyricsMode':'manual','lyrics':'[Verse]\nThese are my words'},schema)
        _,brief=server.brief_node(prompt)
        self.assertEqual(brief['inputs']['vocals'],'new lyrics')
        self.assertIn('vocals.phrasing_reference',brief['inputs'])
        sheets=[n for n in prompt.values() if n['class_type']=='PlenioSongSheet' and 'lyrics' in n['inputs']]
        self.assertEqual(json.loads(sheets[0]['inputs']['sheet_state'])['docs']['lyrics']['text'],'[Verse]\nThese are my words')

    async def test_empty_custom_lyrics_rejected(self):
        profile=server.read_json(server.ROOT/'workflows/profiles.json')['cover']
        with self.assertRaises(ValueError):
            server.build_prompt(profile,{'lyricsMode':'manual','lyrics':' '})

    async def test_approved_run_keeps_project(self):
        with patch.object(server.studio,'jobs',{'parent':{'projectId':'project'}}),patch.object(server.studio,'engine',AsyncMock(return_value={'prompt_id':'child'})),patch.object(server,'write_json'):
            await server.studio.submit({},'cover',parent='parent')
            self.assertEqual(server.studio.jobs['child']['projectId'],'project')

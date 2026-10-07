"""GimmeMusic: a local studio for unchanged ComfyUI API graphs."""
import asyncio
import copy
import hashlib
import json
import mimetypes
import os
import secrets
import sys
import time
import uuid
from pathlib import Path
from urllib.parse import quote

import aiohttp
from aiohttp import web

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))  # Windows embedded Python omits the script directory.
from workflow_edit import DOCUMENTS, apply_node_inputs, apply_documents
from engine_control import EngineControl, install_bridge
CONFIG = json.loads((ROOT / 'config.json').read_text(encoding='utf-8-sig')) if (ROOT / 'config.json').is_file() else {}
COMFY = (ROOT / Path(os.environ.get('GIMMEMUSIC_COMFY_ROOT') or CONFIG.get('comfy_root') or ROOT.parent / 'Plenio-Portable/ComfyUI_windows_portable/ComfyUI')).resolve()
OUTPUT = COMFY / 'output'
DATA = ROOT / 'data'
ENGINE = (os.environ.get('GIMMEMUSIC_ENGINE_URL') or CONFIG.get('engine_url') or 'http://127.0.0.1:8189').rstrip('/')
DATA.mkdir(exist_ok=True)
PROFILES = DATA / 'profiles.json'
JOBS_FILE = DATA / 'jobs.json'
FAVORITES = DATA / 'favorites.json'
PROJECTS = DATA / 'projects.json'


def project_store():
    return read_json(PROJECTS, {'projects': {}, 'tracks': {}})


def track_project(relative, track_id, store):
    if track_id in store['tracks']:
        return store['tracks'][track_id]
    parts = Path(relative).parts
    if 'gimmemusic-projects' in parts:
        index = parts.index('gimmemusic-projects') + 1
        if index < len(parts) and parts[index] in store['projects']:
            return parts[index]
    return None


def read_json(path, default=None):
    try:
        return json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError, ValueError):
        return default


def write_json(path, value):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(path)


def contained(base, relative):
    path = (base / relative).resolve()
    if not path.is_relative_to(base.resolve()):
        raise web.HTTPForbidden(text='Path is outside the library.')
    return path


def brief_node(prompt):
    return next(((k, n) for k, n in prompt.items() if n.get('class_type') in ('PlenioSongBrief', 'PlenioCoverBrief')), (None, None))


def default_form(profile):
    prompt = profile['prompt']
    _, node = brief_node(prompt)
    fields = copy.deepcopy(node['inputs']) if node else {}
    lyrics = ''
    lyrics_mode = 'preserve'
    for n in prompt.values():
        if n['class_type'] == 'PlenioSongSheet':
            state = json.loads(n['inputs'].get('sheet_state') or '{}')
            entry = state.get('docs', {}).get('lyrics', {})
            if entry.get('state') == 'manual':
                lyrics, lyrics_mode = entry.get('text', ''), 'manual'
    source = next((n['inputs'].get('audio', '') for n in prompt.values() if n['class_type'] == 'LoadAudio'), '')
    seeds = [n['inputs'].get('seed', 0) for n in prompt.values() if n['class_type'] == 'SeedNode']
    title = fields.get('title', '')
    for n in prompt.values():
        if n['class_type'] == 'PlenioSongSheet':
            entry = json.loads(n['inputs'].get('sheet_state') or '{}').get('docs', {}).get('title', {})
            if entry.get('state') == 'manual':
                title = entry.get('text', '')
    original_lyrics = next((n['inputs'].get('original_lyrics', '') for n in prompt.values() if n['class_type'] == 'PlenioTranscribeLyrics' and 'expected_lyrics' not in n['inputs']), '')
    if original_lyrics:
        lyrics_mode = 'original'
    return {'originalLyrics': original_lyrics, 'title': title, 'fields': {k: v for k, v in fields.items() if not isinstance(v, (list, dict))}, 'lyrics': lyrics,
            'lyricsMode': lyrics_mode, 'source': source, 'seed': seeds[-1] if seeds else 0}


def vocal_fields(node, schema):
    required = schema.get(node['class_type'], {}).get('input', {}).get('required', {})
    spec = required.get('vocals', [None, {}])
    options = spec[1].get('options', []) if len(spec) > 1 else []
    branch = next((o for o in options if isinstance(o, dict) and o.get('key') == node['inputs'].get('vocals')), {})
    return branch.get('inputs', {}).get('required', {})


def build_prompt(profile, params, schema=None):
    """Only scalar run inputs change; every class and connection stays intact."""
    prompt = copy.deepcopy(profile['prompt'])
    apply_node_inputs(prompt, params.get('nodeInputs', {}), schema or {})
    _, node = brief_node(prompt)
    original_mode = params.get('lyricsMode') == 'original'
    if original_mode:
        if not node or node['class_type'] != 'PlenioCoverBrief':
            raise ValueError('Original source lyrics require a cover workflow.')
        if not str(params.get('originalLyrics', '')).strip():
            raise ValueError('Paste the original lyrics, or choose automatic transcription.')
        params = copy.deepcopy(params)
        params['lyricsIntent'] = None
        params.setdefault('fields', {})['vocals'] = 'original lyrics'
        spec = (schema or {}).get('PlenioTranscribeLyrics', {}).get('input', {})
        if 'original_lyrics' not in {**spec.get('optional', {}), **spec.get('required', {})}:
            raise ValueError('Install the GimmeMusic original-lyrics extension and restart ComfyUI before using provided original lyrics.')
    manual_lyrics = params.get('lyricsMode') == 'manual' or params.get('lyricsIntent') == 'custom'
    if params.get('lyricsMode') == 'manual' and not str(params.get('lyrics', '')).strip():
        raise ValueError('Paste lyrics, or choose automatic lyrics.')
    if manual_lyrics and node:
        params = copy.deepcopy(params)
        params.setdefault('fields', {})['vocals'] = 'new lyrics' if node['class_type'] == 'PlenioCoverBrief' else 'sung'
    permitted = {'description', 'genre', 'mood', 'tempo', 'length', 'mode', 'title', 'template', 'vocals',
                 'vocals.language', 'vocals.voice', 'vocals.theme', 'harmony', 'key', 'meter'}
    if node:
        for key, value in params.get('fields', {}).items():
            if key in permitted and key in node['inputs'] and isinstance(value, str):
                node['inputs'][key] = value
        # Dynamic combo children depend on the selected vocal mode, not on the
        # branch that happened to be active when the graph was captured.
        for key, spec in vocal_fields(node, schema or {}).items():
            name = 'vocals.' + key
            config = spec[1] if len(spec) > 1 else {}
            if name not in node['inputs'] and 'default' in config:
                node['inputs'][name] = copy.deepcopy(config['default'])
            value = params.get('fields', {}).get(name)
            if (spec[0] == 'BOOLEAN' and isinstance(value, bool)) or (spec[0] in ('STRING', 'COMBO') and isinstance(value, str)):
                node['inputs'][name] = value
    for node_id, n in prompt.items():
        inputs = n['inputs']
        if n['class_type'] == 'PlenioTranscribeLyrics' and 'expected_lyrics' not in inputs:
            if original_mode:
                inputs['original_lyrics'] = str(params['originalLyrics'])
            elif params.get('lyricsMode') in ('manual', 'auto', 'original'):
                inputs.pop('original_lyrics', None)
        if n['class_type'] == 'LoadAudio' and params.get('source'):
            source = str(params['source'])
            if not contained(COMFY / 'input', source).is_file():
                raise ValueError('Choose an existing source recording or upload one.')
            inputs['audio'] = source
        if n['class_type'] == 'PlenioSongSheet' and 'lyrics' in inputs and params.get('lyricsMode', 'preserve') != 'preserve':
            state = json.loads(inputs.get('sheet_state') or '{}')
            state.setdefault('schema', 'plenio.sheet_state/1')
            state.setdefault('docs', {})
            mode = params.get('lyricsMode', 'preserve')
            if mode == 'manual':
                state['docs']['lyrics'] = {'state': 'manual', 'text': str(params.get('lyrics', ''))}
                state.pop('review', None)
            elif mode in ('auto', 'original'):
                state['docs'].pop('lyrics', None)
                state.pop('review', None)
            inputs['sheet_state'] = json.dumps(state)
        if params.get('randomize'):
            for key in ('seed', 'noise_seed', 'sampling_mode.seed'):
                if key in inputs and isinstance(inputs[key], int):
                    # Shared safe range includes PlenioRefine's uint32 limit.
                    inputs[key] = secrets.randbelow(2**32)
        elif params.get('seed') is not None and n['class_type'] == 'SeedNode' and 'seed' not in params.get('nodeInputs', {}).get(node_id, {}):
            inputs['seed'] = int(params['seed'])
    sheet_edits = copy.deepcopy(params.get('sheetEdits', {}))
    if params.get('lyricsMode') in ('manual', 'auto', 'original'):
        for node_id, n in prompt.items():
            if n['class_type'] == 'PlenioSongSheet' and 'lyrics' in n['inputs']:
                sheet_edits.setdefault(node_id, {})['lyrics'] = ({'state': 'manual', 'text': params['lyrics']}
                    if params['lyricsMode'] == 'manual' else {'state': 'auto'})
    apply_documents(prompt, sheet_edits, params.get('title'))
    return prompt


class Studio:
    def __init__(self):
        self.profiles = read_json(PROFILES, {})
        self.jobs = read_json(JOBS_FILE, {})
        self.client_id = 'gimmemusic-' + str(uuid.uuid4())
        self.session = None
        self.event = {}
        self.online = False
        self.catalogue = []
        self.catalogue_at = 0
        self.schema = {}

    async def engine(self, path, data=None):
        async with self.session.request('GET' if data is None else 'POST', ENGINE + path, json=data) as response:
            payload = await response.json(content_type=None)
            if response.status >= 400:
                raise ValueError(json.dumps(payload, ensure_ascii=False))
            return payload

    async def bootstrap(self):
        if self.profiles:
            return
        # Public defaults are self-contained. Never harvest personal history on first run.
        self.profiles = read_json(ROOT / 'workflows/profiles.json', {})
        if self.profiles:
            write_json(PROFILES, self.profiles)

    def library(self, refresh=False):
        if not refresh and time.time() - self.catalogue_at < 8:
            return self.catalogue
        favorites = read_json(FAVORITES, [])
        projects = project_store()
        tracks = []
        for file in OUTPUT.rglob('*.plenio.json'):
            if 'portable-test' in file.parts:
                continue
            record = read_json(file, {})
            rel = file.relative_to(OUTPUT).as_posix()
            track_id = hashlib.sha256(rel.encode()).hexdigest()[:20]
            files = []
            for entry in record.get('files', []):
                name = entry.get('name', '')
                if Path(name).suffix.lower() not in ('.flac', '.mp3', '.wav', '.ogg'):
                    continue
                path = (file.parent / name).resolve()
                if path.is_relative_to(OUTPUT.resolve()) and path.is_file():
                    files.append({'name': path.name, 'format': path.suffix[1:].upper(), 'url': '/media/' + quote(path.relative_to(OUTPUT).as_posix())})
            if not files:
                continue
            docs = record.get('documents', {})
            doc = lambda key: docs.get(key, {}).get('text', '')
            prompt = record.get('prompt', {})
            _, brief = brief_node(prompt)
            fields = brief.get('inputs', {}) if brief else {}
            seeds = [n['inputs'].get('seed') for n in prompt.values() if n.get('class_type') == 'SeedNode']
            cover = next((file.with_suffix('').with_suffix(ext) for ext in ('.jpg', '.png', '.jpeg') if file.with_suffix('').with_suffix(ext).is_file()), None)
            tracks.append({'id': track_id, 'title': record.get('title') or file.stem, 'created': record.get('created', ''),
                           'mtime': file.stat().st_mtime, 'duration': record.get('audio', {}).get('seconds', 0),
                           'style': doc('style') or fields.get('description', ''), 'lyrics': doc('lyrics'), 'files': files,
                           'favorite': track_id in favorites, 'seed': seeds[-1] if seeds else None, 'projectId': track_project(rel, track_id, projects),
                           'genre': fields.get('genre') or 'YuE2', 'kind': 'Cover' if brief and brief['class_type'] == 'PlenioCoverBrief' else 'Song',
                           'art': '/media/' + quote(cover.relative_to(OUTPUT).as_posix()) if cover else None,
                           'record': '/media/' + quote(rel), 'licenses': record.get('licences', []),
                           'sampleRate': record.get('audio', {}).get('sample_rate'), 'recordPath': rel})
        self.catalogue = sorted(tracks, key=lambda t: t['mtime'], reverse=True)
        self.catalogue_at = time.time()
        return self.catalogue

    async def submit(self, prompt, profile, parent=None, project_id=None):
        control.touch(generation=True)
        if parent and project_id is None:
            project_id = self.jobs[parent].get('projectId')
        result = await self.engine('/prompt', {'prompt': prompt, 'client_id': self.client_id})
        pid = result['prompt_id']
        self.jobs[pid] = {'id': pid, 'profile': profile, 'created': time.time(), 'status': 'queued', 'prompt': prompt, 'parent': parent, 'projectId': project_id}
        write_json(JOBS_FILE, self.jobs)
        return pid

    async def watch(self):
        while True:
            try:
                async with self.session.ws_connect(ENGINE.replace('http:', 'ws:') + '/ws?clientId=' + self.client_id, heartbeat=25) as ws:
                    async for message in ws:
                        if message.type == aiohttp.WSMsgType.TEXT:
                            event = json.loads(message.data)
                            if event['type'] in ('executing', 'progress', 'execution_start'):
                                self.event = event
                                control.touch(generation=True)
            except (aiohttp.ClientError, asyncio.TimeoutError, ValueError):
                await asyncio.sleep(3)


studio = Studio()
control = EngineControl(ROOT, COMFY, ENGINE, CONFIG, studio.engine)


@web.middleware
async def errors(request, handler):
    if request.method not in ('GET', 'HEAD'):
        origin = request.headers.get('Origin')
        if origin and origin not in ('http://127.0.0.1:8195', 'http://localhost:8195'):
            raise web.HTTPForbidden(text='Only the local studio may make changes.')
    try:
        return await handler(request)
    except (ValueError, KeyError) as error:
        return web.json_response({'error': str(error)}, status=400)
    except (aiohttp.ClientError, asyncio.TimeoutError) as error:
        return web.json_response({'error': 'ComfyUI is unavailable. Start Plenio, then try again.'}, status=503)


async def profiles(request):
    await studio.bootstrap()
    if not studio.schema:
        try:
            studio.schema = await studio.engine('/object_info')
        except (aiohttp.ClientError, ValueError, asyncio.TimeoutError):
            pass
    def options(profile):
        _, node = brief_node(profile['prompt'])
        required = studio.schema.get(node['class_type'], {}).get('input', {}).get('required', {})
        return {key: (value[0] if isinstance(value[0], list) else value[1].get('options', [])) for key, value in required.items() if len(value) > 1 or isinstance(value[0], list)}
    def vocal_options(profile):
        _, node = brief_node(profile['prompt'])
        spec = studio.schema.get(node['class_type'], {}).get('input', {}).get('required', {}).get('vocals', [None, {}])
        return {o['key']: o.get('inputs', {}).get('required', {}) for o in spec[1].get('options', []) if isinstance(o, dict)}
    return web.json_response([{'id': p['id'], 'name': p['name'], 'kind': p['kind'], 'hash': p['hash'], 'defaults': default_form(p), 'options': options(p), 'vocalOptions': vocal_options(p)} for p in studio.profiles.values()])


async def brief_fields(request):
    data = await request.json()
    fields = data.get('fields', {})
    mapped = {k.removeprefix('vocals.'): v for k, v in fields.items() if isinstance(v, str)}
    return web.json_response(await studio.engine('/plenio/brief/fields',
        {'kind': data.get('kind', 'cover'), 'template': fields.get('template', 'none'), 'fields': mapped}))


async def status(request):
    try:
        stats, queue = await asyncio.gather(studio.engine('/system_stats'), studio.engine('/queue'))
        return web.json_response({'control': control.snapshot(), 'app': 'GimmeMusic', 'engine_url': ENGINE, 'online': True, 'stats': stats, 'running': len(queue['queue_running']), 'pending': len(queue['queue_pending']), 'event': studio.event})
    except (aiohttp.ClientError, ValueError, asyncio.TimeoutError):
        return web.json_response({'control': control.snapshot(), 'app': 'GimmeMusic', 'engine_url': ENGINE, 'online': False, 'running': 0, 'pending': 0})


async def engine_action(request):
    data = await request.json()
    await control.action(data.get('action'), data.get('idle_minutes'))
    return web.json_response(control.snapshot())


async def engine_activity(request):
    control.touch()
    return web.json_response({'ok': True})


async def library(request):
    return web.json_response(await asyncio.to_thread(studio.library, request.query.get('refresh') == '1'))


async def favorite(request):
    data = await request.json()
    ids = set(read_json(FAVORITES, []))
    if data.get('favorite'):
        ids.add(request.match_info['id'])
    else:
        ids.discard(request.match_info['id'])
    write_json(FAVORITES, sorted(ids))
    studio.catalogue_at = 0
    return web.json_response({'ok': True})


async def media(request):
    path = contained(OUTPUT, request.match_info['path'])
    if path.suffix.lower() not in ('.mp3', '.flac', '.wav', '.ogg', '.jpg', '.png', '.jpeg', '.json') or not path.is_file():
        raise web.HTTPNotFound()
    response = web.FileResponse(path)
    if request.query.get('download') == '1':
        response.headers['Content-Disposition'] = "attachment; filename*=UTF-8''" + quote(path.name)
    return response


async def inputs(request):
    return web.json_response(sorted(p.relative_to(COMFY / 'input').as_posix() for p in (COMFY / 'input').rglob('*') if p.suffix.lower() in ('.mp3', '.flac', '.wav', '.ogg', '.m4a') and p.is_file()))


async def upload(request):
    reader = await request.multipart()
    part = await reader.next()
    if not part or not part.filename:
        raise ValueError('Choose an audio file.')
    suffix = Path(part.filename).suffix.lower()
    if suffix not in ('.mp3', '.flac', '.wav', '.ogg', '.m4a'):
        raise ValueError('Choose WAV, FLAC, MP3, OGG, or M4A audio.')
    name = 'GimmeMusic-' + uuid.uuid4().hex[:10] + suffix
    dest = COMFY / 'input' / name
    size = 0
    try:
        with dest.open('wb') as handle:
            while chunk := await part.read_chunk(1024 * 1024):
                size += len(chunk)
                if size > 300 * 1024 * 1024:
                    raise ValueError('Audio uploads are limited to 300 MB.')
                handle.write(chunk)
    except BaseException:
        dest.unlink(missing_ok=True)
        raise
    return web.json_response({'name': name})


async def generate(request):
    data = await request.json()
    profile, _ = editor_profile(data['profile'], data.get('baseTrack'))
    count = int(data.get('count', 1))
    if not 1 <= count <= 8:
        raise ValueError('Choose between 1 and 8 takes.')
    schema = await studio.engine('/object_info')
    project_id = data.get('projectId')
    if project_id and project_id not in project_store()['projects']:
        raise ValueError('Choose an existing project.')
    ids = []
    for _ in range(count):
        try:
            prompt = build_prompt(profile, data, schema)
            if project_id:
                for node in prompt.values():
                    if node['class_type'] == 'PlenioExportRelease':
                        node['inputs']['folder'] = 'plenio/gimmemusic-projects/' + project_id
            else:
                for node in prompt.values():
                    if node['class_type'] == 'PlenioExportRelease' and '/gimmemusic-projects/' in node['inputs'].get('folder', ''):
                        node['inputs']['folder'] = node['inputs']['folder'].split('/gimmemusic-projects/')[0] or 'plenio'
            ids.append(await studio.submit(prompt, profile['id'], project_id=project_id))
        except (ValueError, aiohttp.ClientError, asyncio.TimeoutError) as error:
            message = (f'{len(ids)} take(s) were queued before submission stopped. ' if ids else '') + str(error)
            return web.json_response({'ids': ids, 'error': message}, status=400)
    return web.json_response({'ids': ids})


async def jobs(request):
    try:
        history, queue = await asyncio.gather(studio.engine('/history'), studio.engine('/queue'))
    except (aiohttp.ClientError, ValueError, asyncio.TimeoutError):
        return web.json_response([dict(id=j['id'], status='offline', created=j['created'], profile=j['profile']) for j in list(studio.jobs.values())[-25:]])
    running = {row[1] for row in queue['queue_running']}
    pending = {row[1] for row in queue['queue_pending']}
    result = []
    for pid, job in list(studio.jobs.items())[-30:]:
        if job['status'] in ('continued', 'cancelled'):
            result.append({k: v for k, v in job.items() if k != 'prompt'})
            continue
        record = history.get(pid)
        review = []
        if record:
            job['status'] = record['status']['status_str']
            job['sheets'] = []
            checks = {c['draft_sha256']: c for c in job.get('lyricChecks', [])}
            for node, out in record.get('outputs', {}).items():
                checks.update({note['draft_sha256']: dict(note, node=node) for note in out.get('plenio_asr', []) if note.get('original_lyrics')})
                for sheet in out.get('plenio_sheet', []):
                    job['sheets'].append(dict(sheet, node=node))
                    if sheet.get('waiting'):
                        review.append(dict(sheet, node=node))
            if not checks and any(n.get('inputs', {}).get('original_lyrics') for n in job.get('prompt', {}).values()):
                for sheet in job['sheets']:
                    note = await lyric_note(sheet.get('docs', {}).get('lyrics', {}).get('text', ''))
                    if note and note.get('original_lyrics'):
                        checks[note['draft_sha256']] = dict(note, node=sheet['node'])
            job['lyricChecks'] = list(checks.values())
            messages = [m[1] for m in record['status'].get('messages', []) if m[0] == 'execution_error']
            job['error'] = messages[-1].get('exception_message') if messages else None
            if review:
                job['status'] = 'review'
                job['review'] = review
        elif pid in running:
            job['status'] = 'running'
        elif pid in pending:
            job['status'] = 'queued'
        elif job['status'] in ('running', 'queued'):
            job['status'] = 'unknown'
        result.append({k: v for k, v in job.items() if k != 'prompt'})
    write_json(JOBS_FILE, studio.jobs)
    return web.json_response(list(reversed(result)))


async def approve(request):
    job = studio.jobs[request.match_info['id']]
    if job['status'] != 'review':
        raise ValueError('This run is not waiting for review.')
    data = await request.json()
    prompt = copy.deepcopy(job['prompt'])
    for sheet in job['review']:
        node = prompt[sheet['node']]
        state = json.loads(node['inputs'].get('sheet_state') or '{}')
        state.setdefault('schema', 'plenio.sheet_state/1')
        state.setdefault('docs', {})
        for kind, text in data.get('edits', {}).get(sheet['node'], {}).items():
            if kind not in sheet['owned'] or not isinstance(text, str):
                raise ValueError('Invalid Song Sheet document.')
            if text != sheet['docs'][kind]['text']:
                state['docs'][kind] = {'state': 'manual', 'text': text}
        checked = await studio.engine('/plenio/sheet/resolve', {'sheet_state': json.dumps(state), 'upstream': {k: v['upstream'] for k, v in sheet['docs'].items()},
            'owned': sheet['owned'], 'context': sheet.get('context', {}), 'review': sheet['review'], 'brief_mode': 'careful',
            'engine': sheet.get('engine'), 'instrumental': sheet.get('instrumental', False), 'target_seconds': sheet.get('target_seconds')})
        errors = [f['message'] for f in checked.get('findings', []) if f.get('severity') == 'error']
        if errors:
            raise ValueError('\n'.join(errors))
        state['review'] = {'approved_fingerprint': checked['fingerprint']}
        node['inputs']['sheet_state'] = json.dumps(state)
    pid = await studio.submit(prompt, job['profile'], job['id'])
    job['status'] = 'continued'
    job['review'] = []
    write_json(JOBS_FILE, studio.jobs)
    return web.json_response({'id': pid})


async def cancel(request):
    pid = request.match_info['id']
    job = studio.jobs[pid]
    queue = await studio.engine('/queue')
    if pid in {row[1] for row in queue['queue_running']}:
        await studio.engine('/interrupt', {})
    elif pid in {row[1] for row in queue['queue_pending']}:
        await studio.engine('/queue', {'delete': [pid]})
    else:
        raise ValueError('This run is no longer queued or running.')
    job['status'] = 'cancelled'
    write_json(JOBS_FILE, studio.jobs)
    return web.json_response({'ok': True})


def make_waveform(path):
    import av
    import numpy as np
    pieces = []
    with av.open(str(path)) as audio:
        resampler = av.AudioResampler(format='flt', layout='mono', rate=1000)
        for decoded in audio.decode(audio=0):
            pieces.extend(frame.to_ndarray().ravel() for frame in resampler.resample(decoded))
        pieces.extend(frame.to_ndarray().ravel() for frame in resampler.resample(None))
    if not pieces:
        return []
    samples = np.abs(np.concatenate(pieces))
    peaks = np.array([float(np.max(chunk)) if len(chunk) else 0 for chunk in np.array_split(samples, 180)])
    return (peaks / max(float(peaks.max()), 1e-8)).round(3).tolist()


async def waveform(request):
    track = next((t for t in studio.library() if t['id'] == request.match_info['id']), None)
    if not track:
        raise web.HTTPNotFound()
    cache = DATA / ('wave-' + track['id'] + '.json')
    peaks = read_json(cache)
    if peaks is None:
        from urllib.parse import unquote
        path = contained(OUTPUT, unquote(track['files'][0]['url'].removeprefix('/media/')))
        peaks = await asyncio.to_thread(make_waveform, path)
        write_json(cache, peaks)
    return web.json_response(peaks)


async def static(request):
    name = request.match_info.get('path') or 'index.html'
    if name.startswith('api/'):
        raise web.HTTPNotFound()
    path = contained(ROOT / 'dist', name)
    if not path.is_file():
        path = ROOT / 'dist/index.html'
    return web.FileResponse(path)


def editor_profile(profile_id, track_id=None):
    profile = studio.profiles[profile_id]
    if not track_id:
        return profile, {}
    track = next((t for t in studio.library() if t['id'] == track_id), None)
    if not track:
        raise ValueError('The selected release is no longer in the library.')
    record = read_json(contained(OUTPUT, track['recordPath']), {})
    prompt = record.get('prompt', {})
    _, brief = brief_node(prompt)
    if not brief or ('cover' if brief['class_type'] == 'PlenioCoverBrief' else 'song') != profile_id:
        raise ValueError('Choose the matching song or cover profile for this release.')
    return {**profile, 'prompt': prompt}, record


async def lyric_note(text):
    if not text:
        return None
    normalized = '\n'.join(line.rstrip() for line in text.replace('\r\n', '\n').replace('\r', '\n').split('\n')).strip('\n')
    digest = hashlib.sha256(normalized.encode()).hexdigest()
    try:
        return (await studio.engine('/plenio/asr/notes/' + digest)).get('note')
    except (aiohttp.ClientError, ValueError, asyncio.TimeoutError):
        return None


async def workbench(request):
    profile, record = editor_profile(request.query['profile'], request.query.get('track'))
    try:
        studio.schema = await studio.engine('/object_info')
    except (aiohttp.ClientError, ValueError, asyncio.TimeoutError):
        pass
    nodes = []
    for node_id, node in profile['prompt'].items():
        nodes.append({'id': node_id, 'type': node['class_type'], 'title': node.get('_meta', {}).get('title') or node['class_type'],
                      'inputs': node['inputs'], 'schema': studio.schema.get(node['class_type'], {}).get('input', {})})
    note = await lyric_note(record.get('documents', {}).get('lyrics', {}).get('text', ''))
    return web.json_response({'lyricCheck': note.get('original_lyrics') if note else None, 'nodes': nodes, 'defaults': default_form(profile), 'documents': record.get('documents', {}),
                              'reports': record.get('reports', []), 'title': record.get('title', ''), 'schemaAvailable': bool(studio.schema)})


async def validate_sheets(request):
    data = await request.json()
    profile, record = editor_profile(data['profile'], data.get('baseTrack'))
    schema = await studio.engine('/object_info')
    prompt = build_prompt(profile, {**data, 'randomize': False}, schema)
    _, brief = brief_node(prompt)
    results = []
    for node_id, node in prompt.items():
        if node['class_type'] != 'PlenioSongSheet':
            continue
        owned = [k for k in DOCUMENTS if k in node['inputs']]
        upstream = {k: record.get('documents', {}).get(k, {}).get('text') for k in owned}
        result = await studio.engine('/plenio/sheet/resolve', {'sheet_state': node['inputs'].get('sheet_state', ''),
            'owned': owned, 'upstream': upstream, 'context': {k: v.get('text', '') for k, v in record.get('documents', {}).items() if k not in owned},
            'review': node['inputs'].get('review', 'continue'), 'brief_mode': 'batch' if 'every run' in brief['inputs'].get('mode', '') else 'careful',
            'engine': 'yue2', 'instrumental': brief['inputs'].get('vocals') == 'instrumental'})
        results.append({'node': node_id, **result})
    return web.json_response(results)


async def projects_api(request):
    store = project_store()
    if request.method == 'GET':
        return web.json_response(list(store['projects'].values()))
    data = await request.json()
    project_id = data.get('id') or uuid.uuid4().hex
    if data.get('id') and project_id not in store['projects']:
        raise ValueError('Project not found.')
    old = store['projects'].get(project_id, {})
    name = str(data.get('name', old.get('name', ''))).strip()
    if not name or len(name) > 120:
        raise ValueError('Enter a project name between 1 and 120 characters.')
    project = {**old, 'id': project_id, 'name': name, 'updated': time.time()}
    if 'draft' in data:
        if not isinstance(data['draft'], dict) or data['draft'].get('profile') not in studio.profiles:
            raise ValueError('Choose a workflow before saving a draft.')
        project['draft'] = data['draft']
    store['projects'][project_id] = project
    write_json(PROJECTS, store)
    return web.json_response(project)


async def assign_project(request):
    track_id = request.match_info['id']
    if not any(t['id'] == track_id for t in studio.library()):
        raise ValueError('Track not found.')
    data = await request.json()
    store = project_store()
    project_id = data.get('projectId') or None
    if project_id and project_id not in store['projects']:
        raise ValueError('Project not found.')
    store['tracks'][track_id] = project_id
    write_json(PROJECTS, store)
    studio.catalogue_at = 0
    return web.json_response({'ok': True})


async def lifecycle(app):
    studio.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30))
    await studio.bootstrap()
    await asyncio.to_thread(install_bridge, ROOT, COMFY)
    idle_watcher = asyncio.create_task(control.watch())
    watcher = asyncio.create_task(studio.watch())
    yield
    watcher.cancel()
    idle_watcher.cancel()
    await asyncio.gather(watcher, idle_watcher, return_exceptions=True)
    await studio.session.close()


def create_app():
    app = web.Application(middlewares=[errors], client_max_size=301 * 1024 * 1024)
    app.cleanup_ctx.append(lifecycle)
    app.add_routes([web.post('/api/engine', engine_action), web.post('/api/engine/activity', engine_activity), web.get('/api/profiles', profiles), web.get('/api/status', status), web.get('/api/library', library),
        web.post('/api/brief/fields', brief_fields), web.get('/api/workbench', workbench), web.post('/api/sheets/validate', validate_sheets),
        web.get('/api/projects', projects_api), web.post('/api/projects', projects_api), web.post('/api/tracks/{id}/project', assign_project),
        web.post('/api/favorites/{id}', favorite), web.get('/api/inputs', inputs), web.post('/api/upload', upload),
        web.post('/api/generate', generate), web.get('/api/jobs', jobs), web.post('/api/jobs/{id}/approve', approve),
        web.post('/api/jobs/{id}/cancel', cancel), web.get('/api/waveform/{id}', waveform), web.get('/media/{path:.+}', media),
        web.get('/{path:.*}', static)])
    return app


if __name__ == '__main__':
    web.run_app(create_app(), host='127.0.0.1', port=8195, print=lambda s: print('GimmeMusic · ' + s, flush=True))

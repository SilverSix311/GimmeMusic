"""Schema-driven widget editing without allowing graph rewiring."""
import copy
import json
import math

DOCUMENTS = ('title', 'style', 'lyrics', 'score', 'artwork_prompt')


def widget_specs(schema, values, prefix=''):
    result = {}
    for group in ('required', 'optional'):
        for key, spec in schema.get(group, {}).items():
            name = prefix + key
            result[name] = spec
            config = spec[1] if len(spec) > 1 and isinstance(spec[1], dict) else {}
            if spec[0] == 'COMFY_DYNAMICCOMBO_V3':
                for option in config.get('options', []):
                    if option['key'] == values.get(name, config.get('default')):
                        result.update(widget_specs(option.get('inputs', {}), values, name + '.'))
    return result


def checked_value(name, value, spec):
    kind = spec[0]
    config = spec[1] if len(spec) > 1 and isinstance(spec[1], dict) else {}
    choices = kind if isinstance(kind, list) else config.get('options')
    if choices is not None:
        choices = [o['key'] if isinstance(o, dict) else o for o in choices]
        if value not in choices:
            raise ValueError(f'{name}: choose one of the available options.')
    elif kind == 'STRING' and not isinstance(value, str):
        raise ValueError(f'{name}: enter text.')
    elif kind == 'BOOLEAN' and not isinstance(value, bool):
        raise ValueError(f'{name}: choose on or off.')
    elif kind in ('INT', 'FLOAT'):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(f'{name}: enter a finite number.')
        if kind == 'INT' and int(value) != value:
            raise ValueError(f'{name}: enter a whole number.')
        if value < config.get('min', -math.inf) or value > config.get('max', math.inf):
            raise ValueError(f'{name}: value is outside the allowed range.')
    elif choices is None and kind not in ('STRING', 'BOOLEAN'):
        raise ValueError(f'{name}: this input is a connection, not an editable setting.')
    return value


def apply_node_inputs(prompt, edits, schema):
    for node_id, changes in edits.items():
        if node_id not in prompt or not isinstance(changes, dict):
            raise ValueError('Unknown workflow node.')
        node = prompt[node_id]
        values = node['inputs']
        definitions = schema.get(node['class_type'], {}).get('input', {})
        # Inspect the requested branch, but never accept arrays / connection replacements.
        specs = widget_specs(definitions, {**values, **changes})
        for name, value in changes.items():
            if name == 'sheet_state' or isinstance(values.get(name), list) or name not in specs:
                raise ValueError(f'{node_id}.{name}: use Song Sheet for documents; connections are read-only.')
            spec = specs[name]
            if isinstance(spec[0], str) and spec[0] not in ('STRING', 'INT', 'FLOAT', 'BOOLEAN', 'COMBO', 'COMFY_DYNAMICCOMBO_V3') and isinstance(values.get(name), str):
                spec = ['STRING', {}]  # Custom text/JSON widgets, e.g. stem mixer.
            values[name] = checked_value(f'{node_id}.{name}', value, spec)
        for name, spec in widget_specs(definitions, values).items():
            config = spec[1] if len(spec) > 1 and isinstance(spec[1], dict) else {}
            choices = spec[0] if isinstance(spec[0], list) else config.get('options')
            choices = [v['key'] if isinstance(v, dict) else v for v in choices] if choices else None
            if '.' in name and name not in changes and not isinstance(values.get(name), list):
                if name not in values or (choices and values[name] not in choices):
                    if 'default' in config:
                        values[name] = copy.deepcopy(config['default'])
                    elif choices:
                        values[name] = choices[0]


def apply_documents(prompt, edits, title=None):
    for node_id in edits:
        if node_id not in prompt or prompt[node_id]['class_type'] != 'PlenioSongSheet':
            raise ValueError('Unknown Song Sheet node.')
    if title is not None and not isinstance(title, str):
        raise ValueError('Song title must be text.')
    for node_id, node in prompt.items():
        values = node['inputs']
        if title is not None and node['class_type'] == 'PlenioCoverBrief':
            values['title'] = title
        if node['class_type'] != 'PlenioSongSheet':
            continue
        changes = copy.deepcopy(edits.get(node_id, {}))
        if title is not None and 'title' in values:
            changes['title'] = {'state': 'manual', 'text': title} if title.strip() else {'state': 'auto'}
        if not changes:
            continue
        state = json.loads(values.get('sheet_state') or '{}')
        state.setdefault('schema', 'plenio.sheet_state/1')
        state.setdefault('docs', {})
        for kind, entry in changes.items():
            if kind not in DOCUMENTS or kind not in values or not isinstance(entry, dict):
                raise ValueError(f'{node_id}: this sheet does not own {kind}.')
            if entry.get('state') == 'auto':
                state['docs'].pop(kind, None)
            elif entry.get('state') == 'manual' and isinstance(entry.get('text'), str):
                state['docs'][kind] = {'state': 'manual', 'text': entry['text']}
            else:
                raise ValueError('Choose automatic or manual document text.')
        state.pop('review', None)
        values['sheet_state'] = json.dumps(state)

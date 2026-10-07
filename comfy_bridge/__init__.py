"""Report real ComfyUI browser interaction to GimmeMusic's local idle monitor."""
import time
from aiohttp import web
from server import PromptServer

last_activity = time.time()


@PromptServer.instance.routes.get('/gimmemusic/activity')
async def activity(request):
    return web.json_response({'last_activity': last_activity})


@PromptServer.instance.routes.post('/gimmemusic/activity')
async def touch(request):
    global last_activity
    last_activity = time.time()
    return web.json_response({'ok': True})


WEB_DIRECTORY = './web'
NODE_CLASS_MAPPINGS = {}
__all__ = ['WEB_DIRECTORY', 'NODE_CLASS_MAPPINGS']

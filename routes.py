from aiohttp import web
from server import PromptServer
from .storage import read_state,work,resolve_frame
import asyncio,json

@PromptServer.instance.routes.get('/h3v2/project')
async def project(request):
    name=request.query.get('project','my_first_story')
    state=read_state(name)
    p=work(name)/'latest_plan.json'
    if p.exists(): state['latest_plan']=json.loads(p.read_text())
    return web.json_response(state)

@PromptServer.instance.routes.post('/h3v2/frame')
async def frame(request):
    try:
        data=await request.json()
        return web.json_response({'image':await asyncio.to_thread(resolve_frame,data)})
    except (ValueError,KeyError,TypeError) as e: return web.json_response({'error':str(e)},status=400)

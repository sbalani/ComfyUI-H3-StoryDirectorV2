"""Story -> variable-length H3 renders -> exact edited master, in one queue."""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time

import folder_paths
from comfy_execution.graph_utils import GraphBuilder, is_link
from comfy_execution.graph import ExecutionBlocker
from .planning import VERSION, SYSTEM, parse_json, validate_plan, shot_prompt, timeline

WEB_DIRECTORY = './web'
CATEGORY = 'video/H3 Story Director v2'
MODES = ['Auto plan + render', 'Plan only', 'Use edited plan + render']
CANVASES = {'Draft 672x384': (672,384), 'Preview 896x512': (896,512), 'Native 1344x768': (1344,768)}
DEFAULT_REFS = '<Subject 1> is Mara, the single adult woman in <Picture 1>. Preserve her face, long brown hair and black dress. The image is a character sheet of one person.\n<Subject 2> is the hotel in <Picture 2>. Preserve its architecture, palette and lighting; allow new camera angles.'
DEFAULT_STORY = 'Mara enters the quiet hotel lobby, notices a sealed envelope on a table, picks it up and looks toward the exit. End with her walking out carrying the envelope. Three clear story beats, no dialogue.'


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:24]


def project_dir(project):
    slug = re.sub(r'[^A-Za-z0-9_-]+','_',project).strip('_')[:70] or 'my_film'
    path = Path(folder_paths.get_output_directory())/'h3_story_director_v2'/slug
    path.mkdir(parents=True, exist_ok=True)
    return path


def atomic_json(path, data):
    tmp = path.with_suffix('.tmp.json')
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    tmp.replace(path)


def run_writer(messages, seed, work):
    import comfy.model_management as mm
    model_path = Path(folder_paths.models_dir)/'LLM/Qwen3-4B-Instruct-2507'
    if not (model_path/'config.json').exists():
        raise RuntimeError('Install the local writer first: run install.py from the H3 Story Director pack with --download-writer. Expected models/LLM/Qwen3-4B-Instruct-2507.')
    mm.unload_all_models()
    mm.soft_empty_cache()
    with tempfile.TemporaryDirectory(prefix='writer_', dir=work) as tmp:
        req, out = Path(tmp)/'request.json', Path(tmp)/'response.txt'
        req.write_text(json.dumps({'messages':messages,'seed':seed}))
        logpath = work/'writer.log'
        with logpath.open('a') as log:
            proc = subprocess.Popen([sys.executable,str(Path(__file__).with_name('writer.py')),str(req),str(out),str(model_path)],stdout=log,stderr=subprocess.STDOUT)
            start = time.monotonic()
            try:
                while proc.poll() is None:
                    mm.throw_exception_if_processing_interrupted()
                    if time.monotonic()-start > 900:
                        raise RuntimeError('Qwen planner exceeded 15 minutes. See '+str(logpath))
                    time.sleep(0.3)
                if proc.returncode or not out.exists():
                    raise RuntimeError('Qwen planner failed; see '+str(logpath))
                return out.read_text()
            finally:
                if proc.poll() is None:
                    proc.terminate()
                    try: proc.wait(timeout=10)
                    except subprocess.TimeoutExpired: proc.kill(); proc.wait()


class H3V2Planner:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {
          'story': ('STRING', {'multiline':True,'default':DEFAULT_STORY}),
          'reference_notes': ('STRING', {'multiline':True,'default':DEFAULT_REFS}),
          'style': ('STRING', {'multiline':True,'default':'Live-action cinematic realism, natural skin and believable motion. Consistent lighting and wardrobe.'}),
          'target_seconds': ('FLOAT', {'default':20.0,'min':5.0,'max':180.0,'step':1.0}),
          'max_clips': ('INT', {'default':8,'min':1,'max':12}),
          'mode': (MODES,),
          'plan_json': ('STRING', {'multiline':True,'default':'','tooltip':'The generated plan is saved here automatically. Use Shot dashboard to edit and select clips.'}),
          'seed': ('INT', {'default':42001,'min':0,'max':2147483647}),
          'project': ('STRING', {'default':'my_first_story'}),
        }}
    RETURN_TYPES = ('STRING','BOOLEAN','STRING')
    RETURN_NAMES = ('plan_json','render_enabled','timeline')
    FUNCTION = 'plan'
    CATEGORY = CATEGORY
    OUTPUT_NODE = True

    def plan(self, story, reference_notes, style, target_seconds, max_clips, mode, plan_json, seed, project):
        work = project_dir(project)
        if '<Picture ' not in reference_notes or '<Subject ' not in reference_notes:
            raise ValueError('Reference notes must map <Subject 1> to <Picture 1>, etc. Match the order in the H3 picker.')
        key = digest([VERSION,story,reference_notes,style,target_seconds,max_clips,seed])
        cache = work/f'plan_{key}.json'
        if mode == 'Use edited plan + render':
            if not plan_json.strip(): raise ValueError('Open the Shot dashboard and load or generate a plan, then Save edits before rendering.')
            plan = validate_plan(parse_json(plan_json), max_shots=12)
        elif cache.exists():
            plan = validate_plan(json.loads(cache.read_text()), target_seconds, max_clips, automatic=True)
        else:
            if target_seconds > max_clips*15:
                raise ValueError('Target duration needs more clips. Raise max_clips or lower target_seconds.')
            count_min = math.ceil(target_seconds/15)
            count_max = min(max_clips, math.floor(target_seconds/5))
            user = (f'Story: {story}\nReference map: {reference_notes}\nStyle: {style}\n'
                    f'Total duration: {target_seconds:g} seconds. Choose {count_min} to {count_max} clips. Each clip 5–15 seconds.')
            messages = [{'role':'system','content':SYSTEM},{'role':'user','content':user}]
            for attempt in range(2):
                raw = run_writer(messages, seed+attempt, work)
                (work/f'writer_{key}_{attempt}.txt').write_text(raw)
                try:
                    plan = validate_plan(parse_json(raw), target_seconds,max_clips,automatic=True)
                    break
                except (ValueError,TypeError,KeyError) as exc:
                    if attempt: raise ValueError('Qwen produced an invalid plan after a repair attempt. See writer files in '+str(work)) from exc
                    messages += [{'role':'assistant','content':raw},{'role':'user','content':f'Fix this validation error and return the full corrected JSON: {exc}'}]
            atomic_json(cache,plan)
        plan.update(reference_notes=reference_notes, style=style, project=project, seed=seed)
        # Reject invented picture labels before any video inference.
        allowed = set(re.findall(r'<Picture \d+>',reference_notes))
        for s in plan['shots']:
            shot_allowed=set(re.findall(r'<Picture \d+>',s.get('reference_notes') or reference_notes))
            if not set(re.findall(r'<Picture \d+>',s['description'])).issubset(shot_allowed):
                raise ValueError('The plan refers to a picture absent from your reference notes.')
        atomic_json(work/'latest_plan.json',plan)
        text = json.dumps(plan,indent=2,ensure_ascii=False)
        summary = timeline(plan)
        print('[H3 Director] '+summary,flush=True)
        return {'ui':{'text':[summary], 'director_plan':[text]}, 'result':(text,mode!='Plan only',summary)}


def raw(typ): return (typ,{'rawLink':True,'lazy':True})


def status(node_id, message):
    from server import PromptServer
    PromptServer.instance.send_sync('h3_v2_status', {'node':str(node_id), 'message':message})


def lineage(link, dynprompt, seen=None):
    if not is_link(link): return link
    seen = set() if seen is None else seen
    if link[0] in seen: raise ValueError('Cycle in render inputs')
    node = dynprompt.get_node(link[0])
    return {'class_type':node['class_type'],'slot':link[1],
       'inputs':{k:lineage(v,dynprompt,seen|{link[0]}) for k,v in node['inputs'].items()}}


def file_stamps(value):
    """Include referenced file timestamps so replacing an asset invalidates a take."""
    found = {}
    def walk(v, key=''):
        if isinstance(v,dict):
            for k,x in v.items(): walk(x,k)
        elif isinstance(v,list):
            for x in v: walk(x,key)
        elif isinstance(v,str):
            if v.startswith(('[','{')):
                try: walk(json.loads(v))
                except ValueError: pass
            candidates=[Path(folder_paths.get_input_directory())/v]
            folders={'unet_name':'diffusion_models','clip_name':'text_encoders','vae_name':'vae','lora_name':'loras'}
            if key in folders:
                path=folder_paths.get_full_path(folders[key],v)
                if path: candidates.append(Path(path))
            for p in candidates:
                try:
                    if p.is_file():
                        stat=p.stat();found[str(p)]=[stat.st_size,stat.st_mtime_ns]
                except (OSError,ValueError): pass
    walk(value)
    return found


class H3V2Render:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required':{
          'plan_json':('STRING',{'forceInput':True}),
          'render_enabled':('BOOLEAN',{'forceInput':True}),
          'canvas':(list(CANVASES),),
          'steps':('INT',{'default':20,'min':12,'max':50}),
          'model':raw('MODEL'),'clip':raw('CLIP'),'vae':raw('VAE'),'audio_vae':raw('VAE'),
          'references':raw('H3_REFS'),'mods':raw('H3_REF_MODS'),'frame_model':raw('MODEL'),
        },'hidden':{'dynprompt':'DYNPROMPT','unique_id':'UNIQUE_ID'}}
    RETURN_TYPES=('VIDEO',)
    RETURN_NAMES=('assembled_video',)
    FUNCTION='render'
    CATEGORY=CATEGORY
    def check_lazy_status(self, **kwargs): return []

    def render(self,plan_json,render_enabled,canvas,steps,dynprompt,unique_id,**links):
        if not render_enabled:
            status(unique_id,'Plan ready. Edit the shots or switch to Auto plan + render.')
            return (ExecutionBlocker(None),)
        data=json.loads(plan_json)
        plan=validate_plan(data,max_shots=12)
        width,height=CANVASES[canvas]
        from .storage import asset_path, read_state, write_state, resolve_frame, make_params
        state = read_state(data['project'])
        dependencies={k:lineage(v,dynprompt) for k,v in links.items()}
        stamps=file_stamps(dependencies)
        g=GraphBuilder(); clips=[]; manifest=[]
        # Validate every shot and anchor before scheduling any costly render.
        prepared=[]
        for i,s in enumerate(plan['shots']):
            params=make_params(s,data,width,height,steps,i)
            approved=s.get('approved_file','')
            if not s.get('selected',True):
                if not approved: raise ValueError(f'Clip {i+1}: no saved take. Tick it to render.')
                asset_path(approved, 'output')
                existing=next((t for t in state.get('clips',{}).get(s['id'],{}).get('takes',[]) if t['file']==approved),None)
                if existing:
                    if abs(existing['seconds']-s['seconds'])>1/48: raise ValueError(f'Clip {i+1}: changed duration needs rendering; tick this clip.')
                    params=existing['render']
                key=None
            else:
                for name in ('first_frame','last_frame'):
                    if s.get(name): params[name]=resolve_frame(s[name])
                if params['mode']=='frames' and not any(params.get(n) for n in ('first_frame','last_frame')):
                    raise ValueError(f'Clip {i+1}: frame mode needs a first or last frame.')
                key=digest([VERSION,params,dependencies,stamps,file_stamps(params)])
            prepared.append((s,params,approved,key))
        for i,(s,params,approved,key) in enumerate(prepared):
            output_file=approved if key is None else f'h3_story_director_v2/{project_dir(data["project"]).name}/clips/{key}.mp4'
            record={'shot':i+1,'id':s['id'],'title':s['title'],'seconds':s['seconds'],'file':output_file,'render':params}
            manifest.append(record)
            node=g.node('H3V2Shot',shot_json=json.dumps(params),project=data['project'],cache_key=key or '',
                  approved_file=approved if key is None else '',record_json=json.dumps(record),
                  label=f'Clip {i+1}/{len(plan["shots"])}: {s["title"]}',status_id=str(unique_id),**links)
            if clips: node.set_input('previous_clip',clips[-1])
            clips.append(node.out(0))
        write_state(data['project'], {'plan':data,'clips':state.get('clips',{}),'pending':manifest})
        concat=g.node('ConcatenateVideo',codec='h264',**{f'videos.video{i}':c for i,c in enumerate(clips)}) if len(clips)>1 else None
        finish=g.node('H3V2Finish',video=concat.out(0) if concat else clips[0],project=data['project'],
          manifest_json=json.dumps({'version':VERSION,'plan':data,'clips':manifest}),status_id=str(unique_id))
        return {'result':(finish.out(0),),'expand':g.finalize()}


class H3V2Shot:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required':{'shot_json':('STRING',{}),'project':('STRING',{}),'cache_key':('STRING',{}),'label':('STRING',{}),'status_id':('STRING',{}),
          'model':raw('MODEL'),'clip':raw('CLIP'),'vae':raw('VAE'),'audio_vae':raw('VAE'),
          'references':raw('H3_REFS'),'mods':raw('H3_REF_MODS'),'frame_model':raw('MODEL')},
          'optional':{'previous_clip':('VIDEO',),'approved_file':('STRING',{'default':''}),'record_json':('STRING',{'default':'{}'})}}
    RETURN_TYPES=('VIDEO',)
    FUNCTION='render'
    CATEGORY=CATEGORY+'/internal'
    def check_lazy_status(self,**kwargs): return []
    @classmethod
    def IS_CHANGED(cls,**kwargs): return float('nan')

    def render(self,shot_json,project,cache_key,label,status_id,model,clip,vae,audio_vae,references,mods,frame_model,previous_clip=None,approved_file="",record_json="{}"):
        from comfy_api.latest import InputImpl
        from .storage import asset_path, record_clip
        if approved_file:
            p=asset_path(approved_file,'output')
            record_clip(project,json.loads(record_json),status_id)
            return (InputImpl.VideoFromFile(str(p)),)
        p=project_dir(project)/'clips'/f'{cache_key}.mp4'
        if p.exists() and p.with_suffix('.json').exists():
            print(f'[H3 Director] REUSE {label}: {p.name}',flush=True)
            status(status_id,'Reusing saved '+label)
            record_clip(project,json.loads(record_json),status_id)
            return (InputImpl.VideoFromFile(str(p)),)
        print(f'[H3 Director] RENDER {label}',flush=True)
        s=json.loads(shot_json)
        status(status_id,f'Rendering {label} | {s["seconds"]:g}s | {s["width"]}×{s["height"]} | {s["steps"]} steps')
        g=GraphBuilder()
        if s['mode']=='frames':
            frames={}
            for name in ('first_frame','last_frame'):
                if s.get(name): frames[name]=g.node('LoadImage',image=s[name]).out(0)
            enc=g.node('MiniMaxH3ImageToVideo',prompt=s['prompt'],width=s['width'],height=s['height'],length=s['frames'],clip=clip,vae=vae,**frames)
            conditioning,latent=enc.out(0),enc.out(1)
            model=frame_model
        else:
            if s.get('media_state'):
                references=g.node('MiniMaxH3MediaLoader',media_state=s['media_state']).out(0)
            enc=g.node('MiniMaxH3FantasticRefModTextEncode',prompt=s['prompt'],width=s['width'],height=s['height'],length=s['frames'],
              ref_image_size='match',reference_fps=24.0,max_total_tokens=0,voice_description_at_label=False,stack_pictures='every 4th',stack_pictures_n=8,
              clip=clip,vae=vae,audio_vae=audio_vae,references=references,mods=mods)
            conditioning,latent=enc.out(0),enc.out(2)
        guider=g.node('BasicGuider',model=model,conditioning=conditioning)
        noise=g.node('RandomNoise',noise_seed=s['seed'])
        sampler=g.node('KSamplerSelect',sampler_name='res_multistep')
        sched=g.node('BasicScheduler',model=model,scheduler='simple',steps=s['steps'],denoise=1.0)
        sample=g.node('SamplerCustomAdvanced',noise=noise.out(0),guider=guider.out(0),sampler=sampler.out(0),sigmas=sched.out(0),latent_image=latent)
        video=g.node('VAEDecode',vae=vae,samples=sample.out(0))
        audio=g.node('VAEDecodeAudio',vae=audio_vae,samples=sample.out(0))
        conform=g.node('H3V2Conform',images=video.out(0),frames=round(s['seconds']*24),keep_last=s['mode']=='frames' and bool(s.get('last_frame')))
        create=g.node('CreateVideo',images=conform.out(0),audio=audio.out(0),fps=24.0,bit_depth='auto',color_space='sRGB',codec='h264')
        trim=g.node('Video Slice',video=create.out(0),start_time=0.0,duration=s['seconds'],strict_duration=True)
        store=g.node('H3V2Store',video=trim.out(0),project=project,cache_key=cache_key,shot_json=shot_json,label=label,status_id=status_id,record_json=record_json)
        return {'result':(store.out(0),),'expand':g.finalize()}


class H3V2Store:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required':{'video':('VIDEO',),'project':('STRING',{}),'cache_key':('STRING',{}),'shot_json':('STRING',{}),'label':('STRING',{}),'status_id':('STRING',{})},
                'optional':{'record_json':('STRING',{'default':'{}'})},'hidden':{'prompt':'PROMPT','extra_pnginfo':'EXTRA_PNGINFO'}}
    RETURN_TYPES=('VIDEO',)
    FUNCTION='save'
    CATEGORY=CATEGORY+'/internal'
    def save(self,video,project,cache_key,shot_json,label,status_id,prompt=None,extra_pnginfo=None,record_json="{}"):
        from comfy_api.latest import InputImpl,Types
        p=project_dir(project)/'clips'/f'{cache_key}.mp4'
        p.parent.mkdir(exist_ok=True)
        tmp=p.with_suffix('.partial.mp4')
        metadata={'prompt':prompt,'director_shot':json.loads(shot_json)}
        if extra_pnginfo: metadata.update(extra_pnginfo)
        video.save_to(str(tmp),format=Types.VideoContainer('mp4'),codec=Types.VideoCodec('auto'),metadata=metadata)
        tmp.replace(p)
        atomic_json(p.with_suffix('.json'),{'label':label,'render':json.loads(shot_json),'version':VERSION})
        print(f'[H3 Director] SAVED {label}: {p}',flush=True)
        status(status_id,'Saved '+label)
        from .storage import record_clip
        record_clip(project,json.loads(record_json),status_id)
        return (InputImpl.VideoFromFile(str(p)),)


class H3V2Finish:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required':{'video':('VIDEO',),'project':('STRING',{}),'manifest_json':('STRING',{}),'status_id':('STRING',{})}}
    RETURN_TYPES=('VIDEO',)
    FUNCTION='finish'
    CATEGORY=CATEGORY+'/internal'
    def finish(self,video,project,manifest_json,status_id):
        data=json.loads(manifest_json)
        work=project_dir(project)
        atomic_json(work/f'edit_{digest(data)}.json',data)
        atomic_json(work/'latest_edit.json',data)
        status(status_id,f'{len(data["clips"])} clips ready · {data["plan"]["total_seconds"]:g}s. Saving final movie.')
        return (video,)


class H3V2Conform:
    @classmethod
    def INPUT_TYPES(cls): return {'required':{'images':('IMAGE',),'frames':('INT',),'keep_last':('BOOLEAN',)}}
    RETURN_TYPES=('IMAGE',)
    FUNCTION='run'
    CATEGORY=CATEGORY+'/internal'
    def run(self,images,frames,keep_last):
        import torch
        if len(images)<frames: raise ValueError('Decoded video shorter than requested duration')
        return (images[torch.linspace(0,len(images)-1,frames).round().long()] if keep_last else images[:frames],)

from . import routes
NODE_CLASS_MAPPINGS={c.__name__:c for c in (H3V2Planner,H3V2Render,H3V2Shot,H3V2Store,H3V2Finish,H3V2Conform)}
NODE_DISPLAY_NAME_MAPPINGS={'H3V2Planner':'H3 Story Director v2 · Plan', 'H3V2Render':'H3 Story Director v2 · Render & Assemble'}

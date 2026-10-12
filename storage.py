"""Pinned takes, atomic progress, and extraction from completed videos only."""
import hashlib
import json
from pathlib import Path
import re
import threading
import folder_paths
from .planning import shot_prompt
LOCK=threading.RLock()

def asset_path(name, kind):
    root=Path(folder_paths.get_input_directory() if kind=='input' else folder_paths.get_output_directory()).resolve()
    p=(root/name).resolve()
    if not p.is_relative_to(root) or not p.is_file(): raise ValueError('Missing or invalid '+kind+' asset: '+str(name))
    return p

def work(project):
    slug=re.sub(r'[^A-Za-z0-9_-]+','_',project).strip('_')[:70] or 'my_film'
    p=Path(folder_paths.get_output_directory())/'h3_story_director_v2'/slug
    p.mkdir(parents=True,exist_ok=True)
    return p

def read_state(project):
    with LOCK:
        p=work(project)/'dashboard.json'
        return json.loads(p.read_text()) if p.exists() else {'clips':{}}

def write_state(project,data):
    with LOCK:
        p=work(project)/'dashboard.json';tmp=p.with_suffix('.tmp.json')
        tmp.write_text(json.dumps(data,indent=2));tmp.replace(p)

def record_clip(project,record,node):
    if not record.get('id'): return
    with LOCK:
        state=read_state(project)
        old=state.setdefault('clips',{}).get(record['id'],{})
        takes=old.get('takes',[])
        if record['file'] not in [t['file'] for t in takes]: takes.append({k:v for k,v in record.items() if k!='takes'})
        record={**record,'takes':takes,'status':'saved'}
        state['clips'][record['id']]=record
        write_state(project,state)
    from server import PromptServer
    PromptServer.instance.send_sync('h3_v2_clip',{'project':project,'node':node,'clip':record})

def extract_frame(video,which):
    import av
    p=asset_path(video,'output')
    st=p.stat()
    key=hashlib.sha256(f'{video}:{st.st_size}:{st.st_mtime_ns}:{which}'.encode()).hexdigest()[:24]
    rel='h3_story_director_v2/frames/'+key+'.png'
    dest=Path(folder_paths.get_input_directory())/rel
    if not dest.exists():
        with av.open(str(p)) as container:
            chosen=None
            for idx,frame in enumerate(container.decode(video=0)):
                chosen=frame
                if which=='first' or (isinstance(which,int) and idx==which): break
            if chosen is None: raise ValueError('Video contains no frames')
            if isinstance(which,int) and idx<which: raise ValueError('Frame index exceeds video length')
            dest.parent.mkdir(parents=True,exist_ok=True)
            tmp=dest.with_suffix('.tmp.png');chosen.to_image().save(tmp);tmp.replace(dest)
        dest.with_suffix('.json').write_text(json.dumps({'source':video,'frame':which,'size':st.st_size,'mtime_ns':st.st_mtime_ns}))
    return rel

def resolve_frame(spec):
    if not isinstance(spec,dict): raise ValueError('Frame source must be an object')
    if spec.get('image'):
        asset_path(spec['image'],'input');return spec['image']
    if spec.get('video'):
        which=spec.get('frame','last')
        if which not in ('first','last') and (isinstance(which,bool) or not isinstance(which,int) or which<0): raise ValueError('Invalid frame index')
        return extract_frame(spec['video'],which)
    raise ValueError('Choose an uploaded image or a saved clip frame')

def make_params(s,data,width,height,steps,i):
    mode=s.get('mode','reference')
    if mode not in ('reference','frames'): raise ValueError('Invalid shot generation mode')
    refs=s.get('reference_notes') or data['reference_notes']
    if mode=='frames':
        prompt=f'summary:\nContinue the scene from the supplied keyframe. {s["title"]}\n\ndetailed_description:\n{data["style"]}\n[Shot 1] {s["description"]}\nPreserve the location, person, wardrobe and light visible in the keyframe.\n\noverall_soundscape:\n{s["sound"]}\n\nnon_diegetic_music:\nN/A'
    else: prompt=shot_prompt(s,refs,data['style'])
    media=s.get('media_state','')
    if media:
        items=json.loads(media)
        if not isinstance(items,list) or not items: raise ValueError('Shot references must contain at least one picture')
        for item in items:
            if item.get('kind')!='picture': raise ValueError('Per-shot overrides currently support pictures')
            asset_path(item['file'],'input')
    return {'prompt':prompt,'mode':mode,'media_state':media,'frames':s['generation_frames'],
      'seconds':s['seconds'],'width':width,'height':height,'steps':steps,'seed':(data['seed']+1009*i+s.get('take',0))%(2**63)}

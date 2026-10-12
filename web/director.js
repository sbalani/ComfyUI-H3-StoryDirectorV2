import { app } from '../../scripts/app.js';
import { api } from '../../scripts/api.js';
const W=(n,k)=>n.widgets.find(w=>w.name===k);
const url=(file,type='output')=>{const parts=file.split('/');return api.apiURL('/view?'+new URLSearchParams({filename:parts.pop(),subfolder:parts.join('/'),type}));};
function persist(n,p){const text=JSON.stringify(p,null,2);W(n,'plan_json').value=text;n._directorPlan=text;n.setDirtyCanvas(true,true);app.graph.change?.();}
async function state(n){const r=await api.fetchApi('/h3v2/project?'+new URLSearchParams({project:W(n,'project').value}));if(!r.ok)throw Error('Cannot load project');return r.json();}
async function dashboard(n){
 let saved=await state(n), plan;
 try{plan=JSON.parse(W(n,'plan_json').value||n._directorPlan||JSON.stringify(saved.latest_plan));if(!plan.shots?.length)throw Error();}
 catch{alert('Run Plan only to create a plan first.');return;}
 const d=document.createElement('dialog');d.style.cssText='width:96vw;max-width:1600px;height:88vh;background:#14202c;color:#eef4ff;border:1px solid #6080a0;border-radius:12px;padding:20px;font:14px system-ui';
 const el=(tag,text,parent)=>{const x=document.createElement(tag);if(text)x.textContent=text;parent?.append(x);return x;};
 const button=(text,parent,fn)=>{const b=el('button',text,parent);b.type='button';b.style.cssText='padding:7px;margin:4px;cursor:pointer';b.onclick=async()=>{try{await fn();}catch(e){alert(e.message);}};return b;};
 const header=el('div','',d);header.style.cssText='position:sticky;top:0;background:#14202c;z-index:5;padding:4px 0';
 const closeX=button('×',header,()=>d.close());closeX.setAttribute('aria-label','Close shot dashboard');closeX.title='Close shot dashboard';closeX.style.cssText='float:right;width:44px;height:44px;font-size:30px;line-height:1;cursor:pointer;color:#eef4ff;background:#24384c;border:1px solid #6080a0;border-radius:6px';
 el('h2','Story Director v2.1 · Shot dashboard',header);
 el('p','Tick only the clips to render. Unticked clips keep the chosen saved take. Each completed clip is saved immediately. Frame sources are pinned to existing takes.',d);
 const toolbar=el('div','',header);toolbar.style.cssText='background:#14202c;padding:6px;clear:both';
 const info=el('p','',toolbar), table=el('table','',d);table.style.cssText='width:100%;border-collapse:collapse';
 const head=el('tr','',el('thead','',table));for(const title of ['Render / clip','Prompt and sound','Mode / references / frames','Saved output'])el('th',title,head);
 const body=el('tbody','',table), rows=new Map(), edited=new Set();
 function applyRecords(){for(const [i,s] of plan.shots.entries()){
  s.id??=`shot_${String(i+1).padStart(2,'0')}`;const r=saved.clips?.[s.id];
  if(!s.approved_file&&r?.file){s.approved_file=r.file;s.selected=false;}
  s.selected??=!s.approved_file;
 }}applyRecords();
 const total=()=>info.textContent=`${plan.shots.length} clips · ${plan.shots.reduce((a,s)=>a+Number(s.seconds),0).toFixed(2)} seconds · ${plan.shots.filter(s=>s.selected).length} selected`;
 const dirty=s=>{edited.add(s.id);s.selected=true;rows.get(s.id)?.check && (rows.get(s.id).check.checked=true);total();};
 const field=(parent,label,value,change,multi=false)=>{const labelEl=el('label',label,parent);labelEl.style.display='block';const x=el(multi?'textarea':'input','',parent);x.value=value??'';x.style.cssText='display:block;box-sizing:border-box;width:100%;background:#0b1420;color:white;border:1px solid #52677e;padding:7px;margin:5px 0 12px';if(multi)x.rows=4;x.oninput=()=>change(x.value);return x;};
 async function upload(){return new Promise(resolve=>{const f=document.createElement('input');f.type='file';f.accept='image/*';f.oncancel=()=>resolve(null);f.onchange=async()=>{try{const data=new FormData();data.append('image',f.files[0]);data.append('subfolder','h3_story_director_v2/uploads');data.append('overwrite','false');const r=await api.fetchApi('/upload/image',{method:'POST',body:data});if(!r.ok)throw Error('Upload failed');const j=await r.json();resolve([j.subfolder,j.name].filter(Boolean).join('/'));}catch(e){alert(e.message);resolve(null);}};f.click();});}
 function draw(){body.replaceChildren();rows.clear();
 for(const [i,s] of plan.shots.entries()){
  const tr=el('tr','',body);tr.style.cssText='border-top:1px solid #53677c;vertical-align:top';
  const a=el('td','',tr);a.style.cssText='width:12%;padding:12px';
  const check=el('input','',a);check.type='checkbox';check.checked=s.selected;check.onchange=()=>{s.selected=check.checked;total();};
  el('strong',` Clip ${i+1}`,a);
  field(a,'Title',s.title,v=>{s.title=v;dirty(s);});
  const seconds=field(a,'Seconds',s.seconds,v=>{s.seconds=Number(v);dirty(s);});seconds.type='number';seconds.min=5;seconds.max=15;seconds.step=1/24;
  const b=el('td','',tr);b.style.cssText='width:34%;padding:12px';
  field(b,'Action / camera',s.description,v=>{s.description=v;dirty(s);},true);
  field(b,'Sound / dialogue',s.sound,v=>{s.sound=v;dirty(s);},true);
  const c=el('td','',tr);c.style.cssText='width:27%;padding:12px';
  const mode=el('select','',c);for(const [v,t] of [['reference','Character / location references'],['frames','First / last frame (FL2VA model)']]){const o=el('option',t,mode);o.value=v;}mode.value=s.mode||'reference';mode.onchange=()=>{s.mode=mode.value;dirty(s);draw();};
  if((s.mode||'reference')==='reference'){
   el('p',s.media_state?'Using shot-specific pictures':'Using main H3 picker references',c);
   field(c,'Reference mapping override (blank inherits)',s.reference_notes||'',v=>{s.reference_notes=v;dirty(s);},true);
   const picker=app.graph._nodes.find(x=>x.type==='MiniMaxH3MediaLoader');
   let refs=JSON.parse(s.media_state||(picker&&W(picker,'media_state')?.value)||'[]');
   if(!Array.isArray(refs))throw Error('Reference picker must contain a list of media.');
   async function addFrameReference(source,edge){
    if(!source)throw Error('Choose a clip with a saved take first.');
    const r=await api.fetchApi('/h3v2/frame',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({video:source,frame:edge})});
    const j=await r.json();if(!r.ok)throw Error(j.error);
    const number=refs.filter(x=>x.kind==='picture').length+1;
    refs.push({kind:'picture',file:j.image,name:`Continuity reference (${edge} frame)`,has_audio:false,source_video:source,source_frame:edge});
    s.media_state=JSON.stringify(refs);
    s.reference_notes=(s.reference_notes||W(n,'reference_notes').value||'')+`\n<Picture ${number}> is a continuity reference from a saved clip. Use its setting, lighting and visible wardrobe to guide this shot; follow the action and camera prompt.`;
    dirty(s);draw();
   }
   el('p','Add a saved frame as visual guidance while keeping Ref2VA and your existing references. This does not lock the opening frame.',c);
   const previous=button('Previous clip → last frame as reference',c,()=>addFrameReference(plan.shots[i-1]?.approved_file,'last'));
   previous.disabled=!plan.shots[i-1]?.approved_file;
   const sourceSelect=el('select','',c);sourceSelect.setAttribute('aria-label','Reference source clip');
   for(const [index,shot]of plan.shots.entries()){if(!shot.approved_file)continue;const o=el('option',`Clip ${index+1}: ${shot.title}`,sourceSelect);o.value=shot.approved_file;}
   if(plan.shots[i-1]?.approved_file)sourceSelect.value=plan.shots[i-1].approved_file;
   const edgeSelect=el('select','',c);edgeSelect.setAttribute('aria-label','Reference source frame');
   for(const edge of ['last','first']){const o=el('option',`${edge} frame`,edgeSelect);o.value=edge;}
   button('Add selected frame as reference',c,()=>addFrameReference(sourceSelect.value,edgeSelect.value));
   refs.forEach((r,j)=>{el('div',`Picture ${j+1}: ${r.name||r.file}`,c);const thumb=el('img','',c);thumb.src=url(r.file,'input');thumb.style.cssText='width:100px;height:70px;object-fit:contain';button('Replace',c,async()=>{const file=await upload();if(file){refs[j]={kind:'picture',file,name:file.split('/').pop(),has_audio:false};s.media_state=JSON.stringify(refs);dirty(s);draw();}});button('Remove',c,()=>{refs.splice(j,1);s.media_state=refs.length?JSON.stringify(refs):'';dirty(s);draw();});});
   button('Add shot reference image',c,async()=>{const file=await upload();if(!file)return;refs.push({kind:'picture',file,name:file.split('/').pop(),has_audio:false});s.media_state=JSON.stringify(refs);dirty(s);draw();});
   button('Copy main picker references',c,()=>{const picker=app.graph._nodes.find(x=>x.type==='MiniMaxH3MediaLoader');s.media_state=W(picker,'media_state').value;dirty(s);draw();});
   button('Use main picker',c,()=>{s.media_state='';s.reference_notes='';dirty(s);draw();});
  }else{
   el('p','Frame mode uses the keyframes, not the character reference stack.',c);
   for(const [key,label,neighbor,edge] of [['first_frame','First frame',i-1,'last'],['last_frame','Last frame',i+1,'first']]){
    el('strong',label,c);const spec=s[key];
    if(spec?.image){const img=el('img','',c);img.src=url(spec.image,'input');img.style.cssText='width:100%;max-height:110px;object-fit:contain';}
    el('div',spec?.image||spec?.video||'None',c);
    button(key==='first_frame'?'Previous clip → last frame':'Next clip → first frame',c,async()=>{
      const source=plan.shots[neighbor]?.approved_file;if(!source)throw Error('The adjacent clip needs a saved take first.');
      const r=await api.fetchApi('/h3v2/frame',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({video:source,frame:edge})});const j=await r.json();if(!r.ok)throw Error(j.error);s[key]={image:j.image,source_video:source,source_frame:edge};dirty(s);draw();
    });
    button('Upload image',c,async()=>{const file=await upload();if(file){s[key]={image:file};dirty(s);draw();}});
    button('Clear',c,()=>{delete s[key];dirty(s);draw();});
   }
  }
  const out=el('td','',tr);out.style.cssText='width:27%;padding:12px';
  rows.set(s.id,{check,out});showOutput(s); 
 }total();}
 function showOutput(s){const out=rows.get(s.id)?.out;if(!out)return;out.replaceChildren();const r=saved.clips?.[s.id];
  if(!s.approved_file){el('p','Waiting for first render',out);return;}
  const v=el('video','',out);v.src=url(s.approved_file);v.controls=true;v.preload='metadata';v.style.width='100%';
  const link=el('a','Download clip',out);link.href=v.src;link.download='';link.style.color='#9cddff';
  if(r?.takes?.length){const select=el('select','',out);select.style.width='100%';for(const [j,t]of r.takes.entries()){const o=el('option',`Take ${j+1} · ${t.render.mode||'reference'}`,select);o.value=t.file;}select.value=s.approved_file;select.onchange=()=>{s.approved_file=select.value;s.selected=false;rows.get(s.id).check.checked=false;showOutput(s);total();};}
 }
 async function save(queue){
  for(const s of plan.shots){if(!s.title.trim()||!s.description.trim()||!s.sound.trim()||!Number.isFinite(s.seconds)||s.seconds<5||s.seconds>15)throw Error('Each clip needs title, action, sound and 5–15 seconds.');if(!s.selected&&!s.approved_file)throw Error('Select clips without saved takes.');if(s.selected&&s.mode==='frames'&&!s.first_frame&&!s.last_frame)throw Error('Frame mode needs at least one keyframe.');}
  if(queue){const q=await (await api.fetchApi('/queue')).json();if(q.queue_running.length||q.queue_pending.length)throw Error('Wait for the current queue to finish before starting a new edit.');for(const s of plan.shots)if(s.selected)s.take=(s.take||0)+1;}
  persist(n,plan);W(n,'mode').value='Use edited plan + render';n.setDirtyCanvas(true,true);
  if(queue){edited.clear();await app.queuePrompt(0,1);info.textContent='Queued. Completed clips will appear here as they finish.';}else info.textContent='Edits saved into the workflow. Queue to render your selection.';
 }
 button('Select all',toolbar,()=>{plan.shots.forEach(s=>s.selected=true);draw();});
 button('Select none',toolbar,()=>{plan.shots.forEach(s=>s.selected=false);draw();});
 button('Save edits',toolbar,()=>save(false));button('Render selected + assemble',toolbar,()=>save(true));
 button('Refresh saved clips',toolbar,async()=>{saved=await state(n);for(const s of plan.shots){const r=saved.clips?.[s.id];if(!s.approved_file&&r?.file){s.approved_file=r.file;if(!edited.has(s.id))s.selected=false;}}draw();});
 button('Close',toolbar,()=>d.close());
 const onClip=e=>{if(e.detail.project!==W(n,'project').value)return;const r=e.detail.clip;saved.clips??={};saved.clips[r.id]=r;const s=plan.shots.find(s=>s.id===r.id);if(s){s.approved_file=r.file;if(!edited.has(s.id)){s.selected=false;rows.get(s.id).check.checked=false;}showOutput(s);persist(n,plan);total();}};
 api.addEventListener('h3_v2_clip',onClip);
 d.addEventListener('close',()=>{api.removeEventListener('h3_v2_clip',onClip);d.remove();});
 draw();document.body.append(d);d.showModal();
}
app.registerExtension({name:'H3.StoryDirectorV2',async setup(){api.addEventListener('h3_v2_status',e=>{const n=app.graph.getNodeById(e.detail.node),w=n&&W(n,'Production status');if(w){w.value=e.detail.message;n.setDirtyCanvas(true,true);}});},
 async beforeRegisterNodeDef(type,data){if(!['H3V2Planner','H3V2Render'].includes(data.name))return;
 const created=type.prototype.onNodeCreated;type.prototype.onNodeCreated=function(){created?.apply(this,arguments);if(data.name==='H3V2Render'){this.addWidget('text','Production status','Ready',()=>{},{serialize:false});return;}const control=W(this,'control_after_generate');if(control)control.value='fixed';this.addWidget('button','Open shot dashboard',null,()=>dashboard(this).catch(e=>alert(e.message)),{serialize:false});this.addWidget('button','Recover saved project plan',null,async()=>{try{const s=await state(this);if(!s.latest_plan)throw Error('No saved plan for this project');persist(this,s.latest_plan);}catch(e){alert(e.message);}},{serialize:false});};
 if(data.name==='H3V2Planner'){const executed=type.prototype.onExecuted;type.prototype.onExecuted=function(m){executed?.apply(this,arguments);if(m.director_plan?.[0])persist(this,JSON.parse(m.director_plan[0]));};}
 }});

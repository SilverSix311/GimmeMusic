import React, {useEffect, useState} from 'react';
import {FileText, SlidersHorizontal, CheckCircle2, ArrowRight, RotateCcw, Download, Search} from 'lucide-react';

const kinds=['title','style','lyrics','score','artwork_prompt'];
const label=s=>s.replaceAll('_',' ').replaceAll('.',' / ');
const readState=n=>{try{return JSON.parse(n.inputs.sheet_state||'{}')}catch{return {}}};
function specs(schema, values, prefix='') {
  const result={};
  for(const group of ['required','optional'])for(const [key,spec] of Object.entries(schema?.[group]||{})){
    const name=prefix+key;result[name]=spec;
    if(spec[0]==='COMFY_DYNAMICCOMBO_V3'){
      const branch=spec[1]?.options?.find(o=>o.key===(values[name]??spec[1]?.default));
      Object.assign(result,specs(branch?.inputs,values,name+'.'));
    }
  }
  return result;
}
function Widget({name,value,spec,onChange,disabled}){
  const [type,config={}]=spec||['STRING',{}];
  const choices=Array.isArray(type)?type:config.options;
  const props={'aria-label':name,disabled};
  if(choices)return <select {...props} value={value??config.default??''} onChange={e=>onChange(e.target.value)}>{!choices.some(o=>(o.key??o)===value)&&<option value={value??''}>{value||'Choose…'}</option>}{choices.map(o=><option key={o.key??o} value={o.key??o}>{o.key??o}</option>)}</select>;
  if(type==='BOOLEAN'||typeof value==='boolean')return <select {...props} value={String(value??config.default??false)} onChange={e=>onChange(e.target.value==='true')}><option value="false">Off</option><option value="true">On</option></select>;
  if(['INT','FLOAT'].includes(type)||typeof value==='number')return <input {...props} type="number" min={config.min} max={config.max} step={type==='INT'?1:config.step||'any'} value={value??config.default??0} onChange={e=>onChange(e.target.value===''?'':Number(e.target.value))}/>;
  if(config.multiline||name.endsWith('/ mix'))return <textarea {...props} rows={4} value={value??config.default??''} onChange={e=>onChange(e.target.value)}/>;
  return <input {...props} value={value??config.default??''} onChange={e=>onChange(e.target.value)}/>;
}

export default function Workbench({projectControls,view,profile,profiles,form,setForm,loadProfile,tracks,selected,jobs,onReview,generate,busy,online,notify,randomize,setRandomize,count,setCount}){
  const [source,setSource]=useState('draft'),[trackId,setTrackId]=useState(selected?.id||''),[data,setData]=useState(null),[error,setError]=useState(''),[validation,setValidation]=useState([]),[checking,setChecking]=useState(false),[search,setSearch]=useState('');
  const [runId,setRunId]=useState('');
  useEffect(()=>{if(!trackId&&selected?.id)setTrackId(selected.id)},[selected?.id,trackId]);
  const track=tracks.find(t=>t.id===trackId), releaseProfile=track?.kind==='Cover'?'cover':'song';
  const activeProfile=source==='release'?releaseProfile:profile?.id;
  const baseTrack=source==='release'?trackId:form.baseTrack;
  useEffect(()=>{
    if(!activeProfile)return;
    let stopped=false;setData(null);setError('');
    fetch('/api/workbench?'+new URLSearchParams({profile:activeProfile,...(baseTrack?{track:baseTrack}:{})})).then(async r=>{const d=await r.json();if(!r.ok)throw Error(d.error);if(!stopped)setData(d)}).catch(e=>{if(!stopped)setError(e.message)});
    return()=>{stopped=true};
  },[activeProfile,baseTrack]);
  useEffect(()=>setValidation([]),[form,source,trackId]);
  const patchNode=(node,key,value)=>{
    if(['PlenioSongBrief','PlenioCoverBrief'].includes(node.type))setForm(old=>({...old,...(key==='title'?{title:value}:{}),fields:{...old.fields,[key]:value}}));
    else if(node.type==='LoadAudio'&&key==='audio')setForm(old=>({...old,source:value}));
    else setForm(old=>({...old,nodeInputs:{...old.nodeInputs,[node.id]:{...old.nodeInputs?.[node.id],[key]:value}}}));
  };
  const docEntry=(node,kind)=>{
    if(kind==='title'&&form.title?.trim())return {state:'manual',text:form.title};
    if(form.sheetEdits?.[node.id]?.[kind])return form.sheetEdits[node.id][kind];
    if(kind==='lyrics'&&form.lyricsMode==='manual')return {state:'manual',text:form.lyrics};
    if(kind==='lyrics'&&form.lyricsMode==='auto')return {state:'auto'};
    return readState(node).docs?.[kind]||{state:'auto'};
  };
  const setDoc=(node,kind,entry)=>setForm(old=>({...old,...(kind==='title'?{title:entry.state==='manual'?entry.text:''}:{}),...(kind==='lyrics'?{lyricsMode:'preserve',lyricsIntent:entry.state==='manual'?'custom':undefined,fields:{...old.fields,...(entry.state==='manual'?{vocals:profile.kind==='cover'?'new lyrics':'sung'}:{})}}:{}),sheetEdits:{...old.sheetEdits,[node.id]:{...old.sheetEdits?.[node.id],[kind]:entry}}}));
  const useRelease=()=>{
    const p=profiles.find(p=>p.id===releaseProfile);if(!p)return;
    loadProfile(p);
    const sheetEdits={};
    for(const node of data.nodes.filter(n=>n.type==='PlenioSongSheet')){
      sheetEdits[node.id]={};for(const kind of kinds)if(kind in node.inputs&&data.documents[kind]?.text!=null)sheetEdits[node.id][kind]={state:'manual',text:data.documents[kind].text};
    }
    setForm({...data.defaults,baseTrack:trackId,sheetEdits,title:data.title||data.defaults.title,lyricsMode:'preserve',projectId:track?.projectId||form.projectId||null});setSource('draft');notify('Loaded the release’s graph and documents into your next take.');
  };
  const validate=async()=>{
    setChecking(true);try{const r=await fetch('/api/sheets/validate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...form,profile:profile.id})});const d=await r.json();if(!r.ok)throw Error(d.error);setValidation(d)}catch(e){notify(e.message,'error')}finally{setChecking(false)}
  };
  const download=()=>{const text=JSON.stringify({profile:profile.id,...form},null,2);const url=URL.createObjectURL(new Blob([text],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='GimmeMusic-draft.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)};
  const run=jobs.find(j=>j.id===runId);
  const readonly=source!=='draft';
  return <section className="workbench">
    <div className="bench-heading"><div><span className="eyebrow">EVERY DETAIL, YOURS</span><h1>{view==='sheet'?'Song Sheet':'Workflow settings'}<span>.</span></h1><p>{view==='sheet'?'The words, score, and direction behind your next take.':'Edit node settings while keeping the workflow’s connections intact.'}</p></div>{view==='sheet'?<FileText size={30}/>:<SlidersHorizontal size={30}/>}</div>
    <div className="bench-toolbar"><div className="bench-tabs">{[['draft','Next take'],['release','Saved releases'],['run','Run sheets']].map(([key,text])=><button className={source===key?'active':''} key={key} onClick={()=>setSource(key)}>{text}</button>)}</div>
      {source==='draft'?<select aria-label="Editing workflow" value={profile?.id||''} onChange={e=>loadProfile(profiles.find(p=>p.id===e.target.value))}>{profiles.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select>:source==='release'?<select aria-label="Saved release" value={trackId} onChange={e=>setTrackId(e.target.value)}><option value="">Choose a release</option>{tracks.map(t=><option key={t.id} value={t.id}>{t.title} · {new Date(t.mtime*1000).toLocaleString()}</option>)}</select>:<select aria-label="Run sheet" value={runId} onChange={e=>setRunId(e.target.value)}><option value="">Choose a run</option>{jobs.map(j=><option key={j.id} value={j.id}>{j.profile} · {new Date(j.created*1000).toLocaleString()} · {j.status}</option>)}</select>}
    </div>
    {source==='draft'&&<div className="bench-note">Draft saved in this browser. Changes apply when you create the next take.{form.baseTrack&&' Using the selected release’s saved graph.'} {view==='settings'&&'Seed hunting takes priority over node seed values when enabled.'}</div>}
    {source==='draft'&&projectControls}
    {source==='draft'&&<div className="bench-run-controls"><select aria-label="Seed behavior" value={randomize?'random':'fixed'} onChange={e=>setRandomize(e.target.value==='random')}><option value="random">Seed hunting · randomize each take</option><option value="fixed">Use fixed seeds</option></select><select aria-label="Takes from editor" value={count} onChange={e=>setCount(Number(e.target.value))}>{[1,2,3,4,6,8].map(n=><option key={n} value={n}>{n} {n===1?'take':'takes'}</option>)}</select><button className="quiet-button" disabled={!profile} onClick={()=>setForm(structuredClone(profile.defaults))}><RotateCcw size={14}/> Restore defaults</button></div>}
    {source==='release'&&data&&trackId&&<div className="bench-actions"><span>Saved release · original documents and settings</span><button className="small-primary" onClick={useRelease}>Use for next take <ArrowRight size={15}/></button></div>}
    {error&&<p className="job-error">{error}</p>}
    {source==='run'?<>
      {run?.status==='review'&&<button className="small-primary" onClick={()=>onReview(run)}>Review & approve this run</button>}
      {(run?.sheets||run?.review||[]).map(s=><article className="bench-card" key={s.node}><h2>Song Sheet · {s.node}</h2><p>{s.status}</p>{Object.entries(s.docs||{}).map(([kind,doc])=><label className="field" key={kind}><span className="field-label">{label(kind)} · {doc.state}</span><textarea readOnly rows={kind==='title'?2:10} value={doc.text||''}/></label>)}{s.findings?.map((f,i)=><p className="review-finding" key={i}>{f.severity}: {f.message}</p>)}</article>)}
      {!(run?.sheets?.length||run?.review?.length)&&<p className="bench-note">Choose a run with Song Sheet output. Sheets appear after that stage completes.</p>}
    </>:!data?<p className="bench-note">{error?'Unable to load this sheet.':'Loading workflow…'}</p>:<>
      {view==='sheet'?<>
        {data.nodes.filter(n=>n.type==='PlenioSongSheet').map(node=><article className="bench-card" key={node.id}><div className="bench-card-heading"><h2>{node.title}</h2><span>Node {node.id}</span></div>
          {!readonly&&<label className="field"><span className="field-label">Review behavior</span><Widget name={'Review behavior '+node.id} value={form.nodeInputs?.[node.id]?.review??node.inputs.review} spec={node.schema.required?.review||['COMBO',{options:['as the brief says','stop for review','continue']}]} onChange={v=>patchNode(node,'review',v)}/></label>}
          {kinds.filter(k=>k in node.inputs).map(kind=>{
            const entry=docEntry(node,kind), saved=data.documents[kind]?.text, text=readonly?saved||'':entry.text??saved??'';
            return <div className="sheet-document" key={kind}><div className="doc-heading"><label htmlFor={node.id+'-'+kind}>{label(kind)}</label>{!readonly&&<select aria-label={label(kind)+' mode '+node.id} value={entry.state==='auto'?'auto':'manual'} onChange={e=>setDoc(node,kind,e.target.value==='auto'?{state:'auto'}:{state:'manual',text})}><option value="auto">Automatic draft</option><option value="manual">Use my text</option></select>}</div>
              <textarea id={node.id+'-'+kind} aria-label={label(kind)+' document '+node.id} className={kind==='score'?'score-input':''} rows={kind==='title'?2:kind==='score'?18:8} readOnly={readonly||entry.state==='auto'} value={text} placeholder={entry.state==='auto'?'Generated by the workflow. Choose “Use my text” to supply this document.':'Enter your '+label(kind)} onChange={e=>setDoc(node,kind,{state:'manual',text:e.target.value})}/>
              {kind==='score'&&<small>Native ABC score: melody, chords, timing, and section labels. Validate edits before rendering.</small>}
            </div>;
          })}
        </article>)}
      </>:<>
        <label className="bench-search"><Search size={16}/><input aria-label="Search workflow settings" placeholder="Find a node or setting…" value={search} onChange={e=>setSearch(e.target.value)}/></label>
        {!data.schemaAvailable&&<p className="review-finding">Connect Plenio to load setting types, model choices, and allowed ranges.</p>}
        {data.nodes.map(node=>{
          let values={...node.inputs,...(!readonly?form.nodeInputs?.[node.id]:{})};
          if(!readonly&&['PlenioSongBrief','PlenioCoverBrief'].includes(node.type))values={...values,...form.fields,...('title' in values?{title:form.title??values.title}:{})};
          if(!readonly&&node.type==='LoadAudio')values.audio=form.source;
          const definitions=specs(node.schema,values);
          const fields=Object.entries(definitions).filter(([key,[type,c={} ]])=>key!=='sheet_state'&&!Array.isArray(values[key])&&(!c.forceInput||key in values)&&(Array.isArray(type)||['STRING','BOOLEAN','INT','FLOAT','COMBO','COMFY_DYNAMICCOMBO_V3'].includes(type)||['string','boolean','number'].includes(typeof values[key])));
          if(!fields.length||![node.title,node.type,node.id,...fields.map(([k])=>k)].join(' ').toLowerCase().includes(search.toLowerCase()))return null;
          return <details className="bench-card node-settings" key={node.id} open={search?true:undefined}><summary><span>{node.title}</span><small>{node.type} · {node.id} · {fields.length} settings</small></summary><div className="node-fields">{fields.map(([key,spec])=><label className="field" key={key}><span className="field-label">{label(key)}</span><Widget name={node.id+' / '+key} value={values[key]} spec={spec} disabled={readonly||!data.schemaAvailable} onChange={v=>patchNode(node,key,v)}/>{spec[1]?.tooltip&&<small>{spec[1].tooltip}</small>}</label>)}</div><details className="connections"><summary>Connections (read-only)</summary>{Object.entries(node.inputs).filter(([,v])=>Array.isArray(v)).map(([k,v])=><p key={k}>{label(k)} ← Node {v[0]}, output {v[1]}</p>)}</details></details>;
        })}
      </>}
      {source==='release'&&data.reports?.length>0&&<details className="bench-card"><summary>Saved validation and processing reports</summary>{data.reports.map((r,i)=><div key={i}><h3>{r.summary||r.kind}</h3>{r.messages?.map((m,j)=><p className="review-finding" key={j}>{m}</p>)}</div>)}</details>}
      {validation.map(s=><article className="bench-card" key={s.node}><h2>Validation · Sheet {s.node}</h2><p>{s.status}</p>{s.findings?.map((f,i)=><p className="review-finding" key={i}>{f.severity}: {f.message}</p>)}<small>Automatic documents may be unavailable until their upstream steps run. This does not queue or approve a render.</small></article>)}
    </>}
    {source==='draft'&&<div className="bench-footer"><button className="quiet-button" disabled={!profile} onClick={download}><Download size={15}/> Export draft</button><button className="quiet-button" disabled={checking||!online||!data} onClick={validate}><CheckCircle2 size={15}/>{checking?'Checking…':'Validate Song Sheets'}</button><button className="small-primary" disabled={busy||!online||!profile||!data||(profile.kind==='cover'&&!form.source)} onClick={generate}>Create next take <ArrowRight size={15}/></button></div>}
  </section>;
}

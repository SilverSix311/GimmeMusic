import React, { useEffect, useRef, useState } from 'react';
import '@fontsource/dm-sans/400.css';
import '@fontsource/dm-sans/500.css';
import '@fontsource/dm-sans/600.css';
import '@fontsource/dm-sans/700.css';
import '@fontsource/space-grotesk/400.css';
import '@fontsource/space-grotesk/500.css';
import '@fontsource/space-grotesk/700.css';
import { createRoot } from 'react-dom/client';
import { flushSync } from 'react-dom';
import { AudioLines, Disc3, Library, Heart, ListMusic, ArrowUpRight, ChevronDown, ChevronRight, Plus, Search, SlidersHorizontal, Sparkles, Upload, Play, Pause, SkipBack, SkipForward, Volume2, VolumeX, Repeat2, Shuffle, Download, X, Check, RefreshCw, Activity, Cpu, Music2, Mic2, Radio, WandSparkles, Dices, MoreHorizontal, FileAudio, CircleHelp, LoaderCircle, Settings2, Headphones, FileText, CheckCircle2, AlertCircle } from 'lucide-react';
import './style.css';
import Workbench from './Workbench';

const timeLabel = (seconds) => `${Math.floor((seconds || 0) / 60)}:${String(Math.floor((seconds || 0) % 60)).padStart(2, '0')}`;
const api = async (url, body) => {
  const response = await fetch(url, body === undefined ? {} : {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const result = await response.json();
  if (!response.ok || result.error) throw new Error(result.error || 'Something went wrong. Please try again.');
  return result;
};
function IconButton({icon:Icon, label, active, className='', ...props}) {
  return <button type="button" title={label} aria-label={label} className={`icon-button ${active?'active':''} ${className}`} {...props}><Icon size={18}/></button>;
}
function Field({label, children, hint}) {return <label className="field"><span className="field-label">{label}{hint && <span>{hint}</span>}</span>{children}</label>}
function Select({value, onChange, options, label}) {
  return <div className="select-wrap"><select aria-label={label} value={value ?? ''} onChange={e=>onChange(e.target.value)}>{options.map(o=><option key={typeof o==='string'?o:o.value} value={typeof o==='string'?o:o.value}>{typeof o==='string'?o:o.label}</option>)}</select><ChevronDown size={14}/></div>;
}
function Cover({track, className='', children}) {
  const number = track?.id ? parseInt(track.id.slice(0,2),16)%5 : 0;
  return <div className={`cover cover-${number} ${className}`}><img src={track?.art || '/assets/studio-art.jpeg'} alt="" loading="lazy"/>{!track?.art && <div className="cover-wordmark">GM<span>ORIGINALS</span></div>}{children}</div>;
}
function Waveform({peaks, progress=0, onSeek}) {
  return <div className={`waveform ${onSeek?'seekable':''}`} role={onSeek?'slider':undefined} tabIndex={onSeek?0:undefined} aria-label={onSeek?'Seek in track':undefined} aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(progress*100)} onKeyDown={e=>{if(onSeek&&['ArrowRight','ArrowLeft'].includes(e.key)){e.preventDefault();onSeek(Math.max(0,Math.min(1,progress+(e.key==='ArrowRight'?.02:-.02))))}}} onClick={e=>{if(onSeek){const r=e.currentTarget.getBoundingClientRect();onSeek((e.clientX-r.left)/r.width)}}}>
    {peaks?.length ? peaks.map((p,i)=><i key={i} className={i/peaks.length<progress?'passed':''} style={{height:`${Math.max(5,p*100)}%`}}/>) : <div className="wave-empty">Select a track to explore its waveform</div>}
  </div>;
}

function App() {
  const [profiles,setProfiles]=useState([]), [profile,setProfile]=useState(null), [form,setForm]=useState({fields:{},lyrics:'',lyricsMode:'preserve',source:'',seed:0});
  const [tracks,setTracks]=useState([]), [selected,setSelected]=useState(null), [status,setStatus]=useState({online:false}), [jobs,setJobs]=useState([]), [sources,setSources]=useState([]);
  const [view,setView]=useState('studio'), [formTab,setFormTab]=useState('sound'), [search,setSearch]=useState(''), [filter,setFilter]=useState('all'), [sort,setSort]=useState('newest');
  const [randomize,setRandomize]=useState(true), [count,setCount]=useState(1), [busy,setBusy]=useState(false), [toast,setToast]=useState(null), [review,setReview]=useState(null), [edits,setEdits]=useState({});
  const [playing,setPlaying]=useState(false), [current,setCurrent]=useState(0), [duration,setDuration]=useState(0), [volume,setVolume]=useState(.8), [repeat,setRepeat]=useState(false), [shuffle,setShuffle]=useState(false), [peaks,setPeaks]=useState([]), [detailTab,setDetailTab]=useState('details'), [help,setHelp]=useState(false);
  const audio=useRef(null), upload=useRef(null), toastTimer=useRef(null), mounted=useRef(true);
  const notify=(message,type='info')=>{setToast({message,type});clearTimeout(toastTimer.current);toastTimer.current=setTimeout(()=>setToast(null),9000)};
  const refreshLibrary=async()=>{try{const list=await api('/api/library');if(mounted.current){setTracks(list);setSelected(old=>old ? list.find(t=>t.id===old.id)||old : list[0]||null)}}catch(e){notify(e.message,'error')}};
  const loadProfile=p=>{
    setProfile(p);setFormTab('sound');
    let cached;try{cached=JSON.parse(localStorage.getItem('gimmemusic-form-'+p.id)||'null')}catch{}
    setForm(cached?.hash===p.hash ? {...p.defaults,...cached.form,title:cached.form.title??cached.form.fields?.title??p.defaults.title} : structuredClone(p.defaults));
  };
  useEffect(()=>{
    mounted.current=true;
    api('/api/profiles').then(list=>{setProfiles(list);if(list.length)loadProfile(list.find(p=>p.kind==='cover')||list[0])}).catch(e=>notify(e.message,'error'));
    api('/api/inputs').then(setSources).catch(()=>{});
    refreshLibrary();
    const refresh=async()=>{try{const [s,j]=await Promise.all([api('/api/status'),api('/api/jobs')]);if(mounted.current){setStatus(s);setJobs(j)}}catch{setStatus({online:false})}};
    refresh();const t=setInterval(refresh,3000), l=setInterval(refreshLibrary,12000);
    return()=>{mounted.current=false;clearInterval(t);clearInterval(l);clearTimeout(toastTimer.current)};
  },[]);
  useEffect(()=>{if(profile)localStorage.setItem('gimmemusic-form-'+profile.id,JSON.stringify({hash:profile.hash,form}))},[form,profile]);
  useEffect(()=>{let cancelled=false;setPeaks([]);if(selected)api('/api/waveform/'+selected.id).then(p=>{if(!cancelled)setPeaks(p)}).catch(()=>{});return()=>{cancelled=true}},[selected?.id]);
  useEffect(()=>{if(audio.current)audio.current.volume=volume},[volume]);
  const field=(name,value)=>setForm(old=>({...old,fields:{...old.fields,[name]:value}}));
  const opts=(name,fallback=[])=>{
    const entries=profile?.options?.[name] || [];
    const values=entries.map(v=>typeof v==='string'?v:v.key).filter(Boolean);
    return values.length?values:fallback;
  };
  const isCover=profile?.kind==='cover';
  const visible=tracks.filter(t=>(view!=='favorites'||t.favorite)&&(filter==='all'||t.kind.toLowerCase()===filter)&&`${t.title} ${t.style} ${t.genre}`.toLowerCase().includes(search.toLowerCase())).sort((a,b)=>sort==='oldest'?a.mtime-b.mtime:sort==='title'?a.title.localeCompare(b.title):b.mtime-a.mtime);
  const activeJobs=jobs.filter(j=>['queued','running','review'].includes(j.status));
  const gpu=status.stats?.devices?.[0];
  const gpuTotal=gpu?.vram_total||0, gpuUsed=gpuTotal-(gpu?.vram_free||0);
  const reset=()=>{if(profile){setForm(structuredClone(profile.defaults));notify('Restored the workflow’s captured settings.')}};
  const favorite=async(track)=>{try{await api('/api/favorites/'+track.id,{favorite:!track.favorite});setTracks(old=>old.map(t=>t.id===track.id?{...t,favorite:!t.favorite}:t));setSelected(old=>old?.id===track.id?{...old,favorite:!old.favorite}:old)}catch(e){notify(e.message,'error')}};
  const playTrack=async(track)=>{
    if(!track)return;
    if(selected?.id===track.id&&!audio.current.paused){audio.current.pause();return;}
    if(selected?.id!==track.id){
      // React owns src. Commit it once before play(), within the user gesture.
      // A second imperative src assignment would cancel the pending play promise.
      flushSync(()=>{setSelected(track);setCurrent(0);setDuration(0);setPlaying(false)});
    }
    try{await audio.current.play()}catch(e){
      // Switching tracks or pausing intentionally cancels an earlier play request.
      if(e.name!=='AbortError')notify('Playback could not start: '+e.message,'error');
    }
  };
  const next=(step=1)=>{const list=visible.length?visible:tracks;if(!list.length)return;let index=list.findIndex(t=>t.id===selected?.id);index=shuffle?Math.floor(Math.random()*list.length):(index+step+list.length)%list.length;playTrack(list[index]);};
  const seek=f=>{if(audio.current&&Number.isFinite(audio.current.duration))audio.current.currentTime=f*audio.current.duration};
  const generate=async()=>{
    setBusy(true);
    try{const r=await api('/api/generate',{...form,profile:profile.id,count,randomize});notify(`${r.ids.length} ${r.ids.length===1?'take':'takes'} queued. Let’s make some noise.`);setJobs(await api('/api/jobs'))}catch(e){notify(e.message,'error')}finally{setBusy(false)}
  };
  const uploadFile=async(file)=>{
    if(!file)return;setBusy(true);
    try{const body=new FormData();body.append('audio',file);const r=await fetch('/api/upload',{method:'POST',body});const value=await r.json();if(!r.ok)throw new Error(value.error||'Upload failed');setSources(await api('/api/inputs'));setForm(old=>({...old,source:value.name}));notify(`Uploaded ${file.name}`)}catch(e){notify(e.message,'error')}finally{setBusy(false)}
  };
  const openReview=job=>{setReview(job);setEdits(Object.fromEntries(job.review.map(s=>[s.node,Object.fromEntries(Object.entries(s.docs).map(([k,v])=>[k,v.text||'']))])))};
  const approve=async()=>{setBusy(true);try{await api('/api/jobs/'+review.id+'/approve',{edits});setReview(null);notify('Song Sheet approved. Generation is continuing.');setJobs(await api('/api/jobs'))}catch(e){notify(e.message,'error')}finally{setBusy(false)}};
  const cancel=async(job)=>{try{await api('/api/jobs/'+job.id+'/cancel',{});setJobs(await api('/api/jobs'));notify('Run cancelled.')}catch(e){notify(e.message,'error')}};

  return <div className="app">
    <aside className="sidebar">
      <a href="#" className="brand" onClick={e=>{e.preventDefault();setView('studio')}}><img src="/assets/logo.png" alt="Gimmesamoa logo"/><div>Gimme<span>Music</span><small>YOUR SOUND, AMPLIFIED.</small></div></a>
      <div className="workspace-label">YOUR WORKSPACE</div>
      <nav>{[[AudioLines,'studio','Studio'],[FileText,'sheet','Song Sheet'],[SlidersHorizontal,'settings','Workflow settings'],[Library,'library','My library'],[Heart,'favorites','Favorites'],[ListMusic,'queue','Generation queue']].map(([Icon,key,label])=><button key={key} className={`nav-item ${view===key?'selected':''}`} onClick={()=>setView(key)}><Icon size={19}/><span>{label}</span>{key==='queue'&&activeJobs.length>0?<b>{activeJobs.length}</b>:key==='library'?<small>{tracks.length}</small>:null}</button>)}</nav>
      <div className="sidebar-session"><div className="session-icon"><Disc3 size={24}/></div><strong>A little chaos.<br/>A lot of possibility.</strong><p>Your ideas. Your machine.<br/>Your next favorite track.</p><button onClick={()=>setHelp(true)}>Meet your studio <ArrowUpRight size={13}/></button></div>
      <div className="sidebar-bottom">
        <div className="hardware"><div className="hardware-title"><Cpu size={15}/><strong>{gpu?.name?.replace('cuda:0 ','').replace('NVIDIA GeForce ','').split(' : ')[0] || 'Local engine'}</strong><span className={`dot ${status.online?'':'offline'}`}/></div><div className="meter-label"><span>GPU memory</span><span>{gpuTotal?`${(gpuUsed/2**30).toFixed(1)} / ${(gpuTotal/2**30).toFixed(0)} GB`:'—'}</span></div><div className="meter"><i style={{width:gpuTotal?`${gpuUsed/gpuTotal*100}%`:'0%'}}/></div><div className="engine-status"><span className={`dot ${status.online?'':'offline'}`}/>{status.online?'Plenio connected':'Plenio offline'}</div></div>
        <a className="engine-link" href={status.engine_url||"http://127.0.0.1:8189"} target="_blank" rel="noreferrer"><Settings2 size={16}/> Open ComfyUI <ArrowUpRight size={13}/></a>
        <div className="user"><img src="/assets/logo.png" alt=""/><div>Gimmesamoa<small>LOCAL STUDIO</small></div><IconButton icon={CircleHelp} label="Studio help" onClick={()=>setHelp(true)}/></div>
      </div>
    </aside>

    <div className="workspace">
      <header className="topbar"><div className="breadcrumbs">Workspace <ChevronRight size={13}/><strong>{view==='studio'?'Music studio':view==='library'?'My library':view==='favorites'?'Favorites':view==='sheet'?'Song Sheet':view==='settings'?'Workflow settings':'Generation queue'}</strong></div><div className="topbar-right"><span className="local-tag"><span className="dot"/> MADE ON YOUR MACHINE</span><button className="quiet-button" onClick={()=>{setView('studio');setFormTab('sound')}}><Plus size={15}/> Create a track</button></div></header>
      {['sheet','settings'].includes(view)?<Workbench view={view} randomize={randomize} setRandomize={setRandomize} count={count} setCount={setCount} profile={profile} profiles={profiles} form={form} setForm={setForm} loadProfile={loadProfile} tracks={tracks} selected={selected} jobs={jobs} onReview={openReview} generate={generate} busy={busy} online={status.online} notify={notify}/>:<div className={`studio-grid ${view==='studio'?'':'no-composer'}`}>
        {view==='studio'&&<section className="composer">
          <div className="composer-heading"><div><span className="eyebrow">THE SOUND STARTS HERE</span><h1>Create music<span>.</span></h1></div><IconButton icon={RefreshCw} label="Restore workflow defaults" onClick={reset}/></div>
          <div className="profile-switch">{profiles.map(p=><button key={p.id} className={profile?.id===p.id?'active':''} onClick={()=>loadProfile(p)}>{p.kind==='cover'?<Disc3 size={15}/>:<WandSparkles size={15}/>} {p.kind==='cover'?'Make a cover':'New song'}</button>)}</div>
          <div className="engine-selector"><div className="model-icon"><AudioLines size={20}/></div><div><strong>{profile?.name||'Loading workflow…'}</strong><span>Plenio Music Production System</span></div><span className="model-badge">LOCAL</span></div>
          <div className="composer-tabs">{[['sound','Sound'],['lyrics','Lyrics'],['settings','Controls']].map(([key,label])=><button key={key} className={formTab===key?'active':''} onClick={()=>setFormTab(key)}>{label}</button>)}</div>
          <div className="composer-scroll">
          {formTab==='sound'&&<>
            <Field label="SONG TITLE" hint="Leave blank to generate"><input disabled={!profile} aria-label="Song title" placeholder="Give this song a name…" value={form.title??form.fields.title??''} onChange={e=>setForm(old=>({...old,title:e.target.value}))}/></Field>
            {isCover&&<div className="source-section"><div className="section-label"><FileAudio size={14}/> SOURCE RECORDING</div><div className="source-picker"><Select label="Source recording" value={form.source} onChange={source=>setForm(old=>({...old,source}))} options={[{value:'',label:'Choose a recording'},...sources]}/><button className="upload-button" onClick={()=>upload.current.click()} disabled={busy}><Upload size={15}/> Upload audio</button><input ref={upload} type="file" accept="audio/*,.flac" hidden onChange={e=>uploadFile(e.target.files[0])}/></div></div>}
            <Field label="THE SOUND" hint="Be specific. Get weird."><textarea className="style-prompt" aria-label="Describe your sound" placeholder="Low-tuned guitars. Rolling tom fills. A chorus that refuses to leave your head…" value={form.fields.description||''} onChange={e=>field('description',e.target.value)}/></Field>
            <div className="prompt-footer"><span>{(form.fields.description||'').length} characters</span><span><AudioLines size={12}/> Your creative direction</span></div>
            <div className="inspiration"><span>ADD A LITTLE</span><div>{['Heavy tom fills','Half-time breakdown','Raw vocals','Atmospheric'].map(t=><button key={t} onClick={()=>field('description',`${form.fields.description||''}${form.fields.description?', ':''}${t.toLowerCase()}`)}><Plus size={11}/>{t}</button>)}</div></div>
            <div className="form-row"><Field label="GENRE"><input value={form.fields.genre||''} placeholder="Nu-metal, ambient…" onChange={e=>field('genre',e.target.value)}/></Field><Field label="MOOD"><input value={form.fields.mood||''} placeholder="Dark, euphoric…" onChange={e=>field('mood',e.target.value)}/></Field></div>
            {isCover?<Field label="HARMONY"><Select label="Harmony" value={form.fields.harmony} onChange={v=>field('harmony',v)} options={opts('harmony',['keep original chords','new chords'])}/></Field>:<div className="form-row"><Field label="TEMPO" hint="BPM"><input value={form.fields.tempo||''} placeholder="Auto" onChange={e=>field('tempo',e.target.value)}/></Field><Field label="LENGTH"><Select label="Song length" value={form.fields.length} onChange={v=>field('length',v)} options={opts('length',[form.fields.length||'standard (about 3:00)'])}/></Field></div>}
            <div className="tip"><Sparkles size={16}/><p>Describe the moments you want to hear.<br/><span>“Tom fills throughout the verses” beats “more drums.”</span></p></div>
          </>}
          {formTab==='lyrics'&&<>
            <Field label="VOCALS"><Select label="Vocals" value={form.fields.vocals} onChange={v=>field('vocals',v)} options={opts('vocals',isCover?['original lyrics','new lyrics','instrumental']:['sung','instrumental'])}/></Field>
            {Object.entries(profile?.vocalOptions?.[form.fields.vocals]||{}).map(([key,[type,config={}]])=>{
              const name='vocals.'+key, label=key.replaceAll('_',' ').toUpperCase(), value=form.fields[name]??config.default??'';
              return <Field key={name} label={label}>{type==='BOOLEAN'?<Select label={label} value={String(value)} onChange={v=>field(name,v==='true')} options={[{value:'false',label:'Off'},{value:'true',label:'On'}]}/>:type==='COMBO'?<Select label={label} value={value} onChange={v=>field(name,v)} options={config.options||[]}/>:<input aria-label={label} value={value} onChange={e=>field(name,e.target.value)}/>}</Field>;
            })}
            <Field label="LYRIC SOURCE"><Select label="Lyric source" value={form.lyricsMode} onChange={lyricsMode=>setForm(old=>({...old,lyricsMode}))} options={[{value:'preserve',label:'Use workflow’s lyric settings'},{value:'auto',label:isCover?'Transcribe / write from source':'Write new lyrics for me'},{value:'manual',label:'Use my own lyrics'}]}/></Field>
            {form.lyricsMode==='manual'?<Field label="YOUR WORDS"><textarea className="lyrics-input" aria-label="Custom lyrics" placeholder={'[Verse]\nYour story starts here…\n\n[Chorus]\nMake it unforgettable.'} value={form.lyrics} onChange={e=>setForm(old=>({...old,lyrics:e.target.value}))}/></Field>:<div className="lyrics-empty"><Mic2 size={32}/><h3>{isCover?'A new voice for your song.':'Leave room for inspiration.'}</h3><p>{isCover?'Your workflow handles transcription and lyric creation. The Song Sheet will pause when a review is needed.':'The workflow’s writer follows your sound and mood. Choose “Use my own lyrics” to bring your words.'}</p></div>}
          </>}
          {formTab==='settings'&&<>
            <Field label="WORKFLOW MODE"><Select label="Workflow mode" value={form.fields.mode} onChange={v=>field('mode',v)} options={opts('mode',isCover?['one cover, stop to review','new cover every run']:['new song every run','one song, stop to review'])}/></Field>
            <div className="setting-card"><div><Dices size={18}/><div><strong>Seed hunting</strong><p>Randomize seeds for each take</p></div></div><button role="switch" aria-label="Randomize seeds" aria-checked={randomize} className={`toggle ${randomize?'on':''}`} onClick={()=>setRandomize(!randomize)}><span/></button></div>
            {!randomize&&<Field label="FIXED SEED"><input type="number" min="0" max="281474976710655" value={form.seed} onChange={e=>setForm(old=>({...old,seed:e.target.value}))}/></Field>}
            <Field label="TAKES PER RUN"><Select label="Number of takes" value={count} onChange={v=>setCount(Number(v))} options={[1,2,3,4,6,8].map(n=>({value:n,label:`${n} ${n===1?'take':'takes'}`}))}/></Field>
            <div className="tip"><CircleHelp size={17}/><p>For a completely new song, choose “new song every run” and automatic lyrics. Keep your lyrics for alternate performances.</p></div>
            <div className="workflow-info"><CheckCircle2 size={17}/><div><strong>Your workflow, intact.</strong><p>These controls set inputs for this run. Your saved nodes, connections, models, and processing stay as they are.</p></div></div>
          </>}
          </div>
          <footer className="create-footer"><div><span className={`dot ${status.online?'':'offline'}`}/>{status.online?(status.running?'Engine working · new takes will queue':'Engine ready'):'Start Plenio to connect'}<span>{count} {count===1?'take':'takes'}</span></div><button className="create-button" disabled={busy||!status.online||!profile||(isCover&&!form.source)} onClick={generate}>{busy?<LoaderCircle className="spin" size={20}/>:<Sparkles size={20}/>} {busy?'Queuing…':isCover?'Create cover':'Create music'}<span>↗</span></button><small>Local generation. Limitless possibility.</small></footer>
        </section>}

        <main className="library-panel">
          <section className="hero"><img src="/assets/studio-art.jpeg" alt="Violet and magenta skeleton artwork"/><div className="hero-shade"/><div className="hero-content"><div className="hero-kicker"><span/> THE GIMMEMUSIC STUDIO</div><h2>Make some<br/><em>noise.</em></h2><p>A spark of an idea. A sound that’s yours.</p></div><div className="hero-stamp"><AudioLines size={20}/><span>BUILT FOR<br/>YOUR SOUND</span></div></section>
          {view==='queue'?<section className="queue-view"><div className="library-heading"><div><span className="eyebrow">FROM IDEA TO AUDIO</span><h2>Generation queue<span>{jobs.length}</span></h2></div></div><p className="section-description">Your studio runs. Other ComfyUI tasks stay in ComfyUI.</p>{jobs.length===0?<div className="empty"><ListMusic size={36}/><h3>Ready when you are.</h3><p>Create a track and follow its progress here.</p></div>:jobs.map(job=><div className="job-card" key={job.id}><div className={`job-icon ${job.status}`}><Activity size={19}/></div><div><strong>{profiles.find(p=>p.id===job.profile)?.name||job.profile}</strong><p>{new Date(job.created*1000).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'})} · {job.status==='review'?'Song Sheet needs your approval':job.status}</p>{job.error&&<p className="job-error">{job.error}</p>}</div>{job.status==='review'?<button className="small-primary" onClick={()=>openReview(job)}>Review</button>:['queued','running'].includes(job.status)?<IconButton icon={X} label="Cancel this run" onClick={()=>cancel(job)}/>:job.status==='success'?<CheckCircle2 size={19} className="cyan"/>:null}</div>)}</section>:<>
          <div className="library-heading"><div><span className="eyebrow">YOUR SOUND COLLECTION</span><h2>{view==='favorites'?'On repeat':'Your tracks'}<span>{view==='favorites'?tracks.filter(t=>t.favorite).length:tracks.length}</span></h2></div><IconButton icon={RefreshCw} label="Refresh library" onClick={refreshLibrary}/></div>
          <div className="library-toolbar"><div className="search"><Search size={16}/><input aria-label="Search tracks" placeholder="Find your next favorite…" value={search} onChange={e=>setSearch(e.target.value)}/>{search&&<IconButton icon={X} label="Clear search" onClick={()=>setSearch('')}/>}</div><Select label="Sort tracks" value={sort} onChange={setSort} options={[{value:'newest',label:'Newest first'},{value:'oldest',label:'Oldest first'},{value:'title',label:'Title A–Z'}]}/></div>
          <div className="filter-row"><div>{[['all','All tracks'],['song','Songs'],['cover','Covers']].map(([key,label])=><button className={filter===key?'selected':''} key={key} onClick={()=>setFilter(key)}>{label}</button>)}</div><span><Headphones size={13}/> Made by you</span></div>
          {activeJobs.length>0&&<div className="queue-banner"><div className="equalizer"><i/><i/><i/><i/></div><div><strong>{activeJobs.some(j=>j.status==='review')?'Your Song Sheet is ready':'Something good is taking shape'}</strong><span>{activeJobs.length} active {activeJobs.length===1?'run':'runs'} · {activeJobs[0].status}</span></div><button onClick={()=>setView('queue')}>View queue <ChevronRight size={14}/></button></div>}
          <div className="track-list">{visible.length===0?<div className="empty"><Music2 size={36}/><h3>{search?'No tracks found.':view==='favorites'?'Keep the ones that hit.':'Your first track is waiting.'}</h3><p>{search?'Try another title, genre, or sound.':view==='favorites'?'Tap the heart on a track to save it here.':'Create a song to start your collection.'}</p></div>:visible.map((track,index)=><article key={track.id} className={`track ${selected?.id===track.id?'selected':''}`} onClick={()=>setSelected(track)} tabIndex={0} onKeyDown={e=>{if(e.key==='Enter')setSelected(track)}}>
            <span className="track-number">{String(index+1).padStart(2,'0')}</span><Cover track={track} className="track-cover"><button aria-label={(playing&&selected?.id===track.id?'Pause ':'Play ')+track.title} onClick={e=>{e.stopPropagation();playTrack(track)}}>{playing&&selected?.id===track.id?<Pause size={17} fill="currentColor"/>:<Play size={17} fill="currentColor"/>}</button></Cover>
            <div className="track-text"><h3>{track.title}</h3><p>{track.style||'Your local music creation'}</p><div><span className="track-type">{track.kind}</span><span>{track.files[0].format}</span><span>{new Date(track.created).toLocaleDateString(undefined,{month:'short',day:'numeric'})}</span></div></div>
            <div className="track-actions"><span>{timeLabel(track.duration)}</span><IconButton icon={Heart} label={track.favorite?'Remove from favorites':'Add to favorites'} active={track.favorite} onClick={e=>{e.stopPropagation();favorite(track)}}/><a className="icon-button track-download" href={track.files[0].url+'?download=1'} title="Download audio" aria-label={'Download '+track.title} onClick={e=>e.stopPropagation()}><Download size={16}/></a></div>
          </article>)}</div><div className="library-bottom"><span className="dot"/> Stored locally · {tracks.length} releases in your library</div>
          </>}
        </main>

        <aside className="details-panel"><div className="details-heading"><span>TRACK DETAILS</span><Disc3 size={16}/></div>{selected?<>
          <Cover track={selected} className="detail-cover"><span className="art-badge">GIMMEMUSIC ORIGINAL</span><button className="art-play" aria-label={playing?'Pause selected track':'Play selected track'} onClick={()=>playTrack(selected)}>{playing?<Pause size={22} fill="currentColor"/>:<Play size={22} fill="currentColor"/>}</button><span className="art-duration">{timeLabel(selected.duration)}</span></Cover>
          <div className="selected-heading"><h2>{selected.title}</h2><IconButton icon={Heart} label="Favorite selected track" active={selected.favorite} onClick={()=>favorite(selected)}/></div>
          <div className="artist"><img src="/assets/logo.png" alt=""/><div>Gimmesamoa<span>{selected.kind} · {new Date(selected.created).toLocaleDateString(undefined,{month:'long',day:'numeric',year:'numeric'})}</span></div></div>
          <div className="detail-wave"><Waveform peaks={peaks} progress={duration?current/duration:0} onSeek={seek}/><div><span>{timeLabel(current)}</span><span>{timeLabel(selected.duration)}</span></div></div>
          <div className="detail-tabs"><button className={detailTab==='details'?'active':''} onClick={()=>setDetailTab('details')}>About this track</button><button className={detailTab==='lyrics'?'active':''} onClick={()=>setDetailTab('lyrics')}>Lyrics</button></div>
          {detailTab==='details'?<><div className="detail-section"><label>THE SOUND</label><p>{selected.style||'No style description was saved for this release.'}</p><div className="genre-tags">{selected.style.split(',').slice(0,3).filter(Boolean).map((s,i)=><span key={i}>{s.trim()}</span>)}</div></div><div className="detail-stats"><div><label>MODEL</label><strong>YuE2</strong></div><div><label>SAMPLE RATE</label><strong>{selected.sampleRate?`${selected.sampleRate/1000} kHz`:'—'}</strong></div><div className="seed-stat"><label>TAKE SEED</label><strong>{selected.seed??'Not recorded'}</strong><button onClick={()=>{if(selected.seed!=null){setForm(old=>({...old,seed:selected.seed}));setRandomize(false);setView('studio');setFormTab('settings');notify('Seed copied to controls. Other settings still affect the result.')}}} disabled={selected.seed==null}>Use seed <ArrowUpRight size={12}/></button></div></div></>:<div className="detail-lyrics">{selected.lyrics||'No lyrics were saved for this track.'}</div>}
          <div className="download-section"><label>KEEP YOUR CREATION</label><div>{selected.files.map((file,i)=><a key={i} href={file.url+'?download=1'}><Download size={14}/>{file.format}</a>)}<a href={selected.record+'?download=1'} title="Download the full release record"><FileText size={14}/> Record</a></div></div>
        </>:<div className="empty"><Disc3 size={34}/><h3>Get into the details.</h3><p>Select a track to see its sound, lyrics, and downloads.</p></div>}</aside>
      </div>}
    </div>

    <footer className="player"><div className="player-track">{selected?<Cover track={selected} className="player-cover"/>:<div className="player-cover placeholder"><Music2 size={22}/></div>}<div><strong>{selected?.title||'Find your frequency.'}</strong><span>{selected?'Gimmesamoa · '+selected.kind:'Your music lives here.'}</span></div>{selected&&<IconButton icon={Heart} label="Favorite playing track" active={selected.favorite} onClick={()=>favorite(selected)}/>}</div><div className="player-center"><div className="transport"><IconButton icon={Shuffle} label="Shuffle" active={shuffle} onClick={()=>setShuffle(!shuffle)} disabled={!tracks.length}/><IconButton icon={SkipBack} label="Previous track" onClick={()=>next(-1)} disabled={!tracks.length}/><button className="main-play" aria-label={playing?'Pause':'Play'} onClick={()=>playTrack(selected)} disabled={!selected}>{playing?<Pause size={21} fill="currentColor"/>:<Play size={21} fill="currentColor"/>}</button><IconButton icon={SkipForward} label="Next track" onClick={()=>next(1)} disabled={!tracks.length}/><IconButton icon={Repeat2} label="Repeat track" active={repeat} onClick={()=>setRepeat(!repeat)} disabled={!selected}/></div><div className="scrubber"><span>{timeLabel(current)}</span><input type="range" aria-label="Playback position" min="0" max="1000" value={duration?Math.round(current/duration*1000):0} onChange={e=>seek(Number(e.target.value)/1000)} disabled={!selected}/><span>{timeLabel(duration||selected?.duration)}</span></div></div><div className="player-right"><span className="quality">{selected?.files?.[0]?.format||'LOCAL'}<span>{selected?.sampleRate?selected.sampleRate/1000+' kHz':'AUDIO'}</span></span><IconButton icon={volume===0?VolumeX:Volume2} label={volume===0?'Unmute':'Mute'} onClick={()=>setVolume(volume===0?.8:0)}/><input type="range" min="0" max="1" step="0.01" value={volume} aria-label="Volume" onChange={e=>setVolume(Number(e.target.value))}/>{selected&&<a className="icon-button" href={selected.files[0].url+'?download=1'} aria-label="Download playing track"><Download size={17}/></a>}</div></footer>
    <audio ref={audio} src={selected?.files[0]?.url} preload="metadata" onPlay={()=>setPlaying(true)} onPause={()=>setPlaying(false)} onTimeUpdate={e=>setCurrent(e.currentTarget.currentTime)} onLoadedMetadata={e=>{setDuration(e.currentTarget.duration);setCurrent(e.currentTarget.currentTime)}} onEnded={()=>{if(repeat){audio.current.currentTime=0;audio.current.play().catch(()=>{})}else next()}} onError={()=>{if(selected)notify('This audio could not be played. Try downloading it instead.','error')}}/>
    {toast&&<div className={`toast ${toast.type}`} role="status">{toast.type==='error'?<AlertCircle size={19}/>:<CheckCircle2 size={19}/>}<span>{toast.message}</span><IconButton icon={X} label="Dismiss notification" onClick={()=>setToast(null)}/></div>}
    {review&&<div className="modal-backdrop"><section className="modal review-modal" role="dialog" aria-modal="true" aria-labelledby="review-title"><div className="modal-heading"><div><span className="eyebrow">BEFORE THE NEXT TAKE</span><h2 id="review-title">Your Song Sheet</h2></div><IconButton icon={X} label="Close review" onClick={()=>setReview(null)}/></div><p className="section-description">Review the actual documents your workflow will use. Approving continues this take with the same seeds.</p><div className="review-body">{review.review.map(sheet=><div key={sheet.node}>{sheet.findings?.filter(f=>f.severity!=='info').map((f,i)=><p className="review-finding" key={i}>{f.message}</p>)}{sheet.owned.map(kind=><Field key={kind} label={kind.toUpperCase()}><textarea className={kind==='score'?'score-input':''} rows={kind==='title'?2:8} value={edits[sheet.node]?.[kind]||''} onChange={e=>setEdits(old=>({...old,[sheet.node]:{...old[sheet.node],[kind]:e.target.value}}))}/></Field>)}</div>)}</div><button className="create-button" onClick={approve} disabled={busy}>{busy?<LoaderCircle className="spin" size={18}/>:<Check size={18}/>} Approve & continue</button></section></div>}
    {help&&<div className="modal-backdrop"><section className="modal help-modal" role="dialog" aria-modal="true" aria-labelledby="help-title"><div className="modal-heading"><h2 id="help-title">Welcome to GimmeMusic.</h2><IconButton icon={X} label="Close help" onClick={()=>setHelp(false)}/></div><p>A studio for your existing Plenio workflows. Everything runs locally.</p><div className="help-step"><span>01</span><div><strong>Shape your sound</strong><p>Choose a song or cover, describe the sound, and set your lyrics. Cover sources can be selected or uploaded.</p></div></div><div className="help-step"><span>02</span><div><strong>Find the take</strong><p>Use Controls to randomize seeds and queue up to eight takes. Review mode pauses for your Song Sheet approval.</p></div></div><div className="help-step"><span>03</span><div><strong>Keep what hits</strong><p>Play your real exports, compare takes, favorite the keepers, and download audio plus the release record.</p></div></div><p className="help-note">The studio uses captured API graphs from your existing runs. Song Sheet edits documents and ABC scores; Workflow settings edits node controls. Graph rewiring and the visual piano roll remain in ComfyUI. Your workflow files are never rewritten. YuE2 model licensing still applies.</p><a href={status.engine_url||"http://127.0.0.1:8189"} target="_blank" rel="noreferrer" className="quiet-button">Open ComfyUI <ArrowUpRight size={15}/></a></section></div>}
  </div>;
}

createRoot(document.getElementById('root')).render(<App/>);

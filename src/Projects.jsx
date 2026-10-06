import React,{useState} from 'react';
import {FolderPlus, Pencil, FileText} from 'lucide-react';

export default function Projects({projects,tracks,active,onSelect,onSave,onLoadDraft,jobs=[],ready=true}){
  const [name,setName]=useState(''),[editing,setEditing]=useState(null),[busy,setBusy]=useState(false);
  const current=projects.find(p=>p.id===active);
  const save=async e=>{e.preventDefault();setBusy(true);try{await onSave({...(editing?{id:editing}:{}),name});setName('');setEditing(null)}catch{}finally{setBusy(false)}};
  return <section className="projects-panel"><div className="library-heading"><div><span className="eyebrow">KEEP THE TAKES TOGETHER</span><h2>Projects<span>{projects.length}</span></h2></div><FolderPlus size={24}/></div><p className="section-description">Group versions of the same song. Select a project to browse its takes and send your next generations there.</p>
    <form className="project-create" onSubmit={save}><input aria-label="Project name" placeholder="Name a project…" maxLength={120} value={name} onChange={e=>setName(e.target.value)} required/><button className="small-primary" disabled={busy||!name.trim()}>{editing?'Save name':'Create project'}</button>{editing&&<button type="button" onClick={()=>{setEditing(null);setName('')}}>Cancel</button>}</form>
    <div className="project-cards"><button className={!active?'selected':''} onClick={()=>onSelect('')}><strong>All projects</strong><span>{tracks.length} tracks in your library</span></button>{projects.map(p=><button className={p.id===active?'selected':''} key={p.id} onClick={()=>onSelect(p.id)}><strong>{p.name}</strong><span>{tracks.filter(t=>t.projectId===p.id).length} takes{p.draft?' · Draft saved':''}</span></button>)}</div>
    {current&&<div className="project-current"><strong>{current.name}</strong><button className="quiet-button" onClick={()=>{setEditing(current.id);setName(current.name)}}><Pencil size={14}/> Rename</button>{current.draft&&<button disabled={!ready} className="quiet-button" onClick={()=>onLoadDraft(current)}><FileText size={14}/> Load saved draft</button>}</div>}
    {current&&jobs.some(j=>j.projectId===current.id)&&<details><summary>Recent generations</summary>{jobs.filter(j=>j.projectId===current.id).map(j=><div className="project-run" key={j.id}><span>{new Date(j.created*1000).toLocaleString()} · {j.profile}</span><span>{j.status}</span></div>)}</details>}
  </section>;
}

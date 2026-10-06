import React, {useEffect, useState} from 'react';

const textFields=['description','genre','mood','tempo','key','meter','vocals.language','vocals.voice','vocals.theme','vocals.lead_instrument'];
const fieldName=k=>['language','voice','theme','melody','lead_instrument'].includes(k)?'vocals.'+k:k;

export default function BriefTemplate({profile,form,setForm,notify}) {
  const [answer,setAnswer]=useState(null),[error,setError]=useState('');
  const fields=JSON.stringify(form.fields);
  useEffect(()=>{
    const controller=new AbortController();setAnswer(null);setError('');
    const timer=setTimeout(async()=>{
      try{
        const r=await fetch('/api/brief/fields',{method:'POST',headers:{'Content-Type':'application/json'},signal:controller.signal,body:JSON.stringify({kind:profile?.kind,fields:JSON.parse(fields)})});
        const d=await r.json();if(!r.ok)throw Error(d.error);setAnswer(d);
      }catch(e){if(e.name!=='AbortError')setError(e.message)}
    },300);
    return()=>{clearTimeout(timer);controller.abort()};
  },[fields,profile?.kind]);
  const choices=(profile?.options?.template||[]).map(o=>o.key??o);
  const patch=changes=>setForm(old=>({...old,fields:{...old.fields,...changes}}));
  const copy=()=>patch(Object.fromEntries((answer?.fills||[]).filter(f=>!form.fields[fieldName(f.field)]?.trim()).map(f=>[fieldName(f.field),f.value])));
  const applyChoices=()=>{
    const changes=Object.fromEntries((answer?.choices||[]).map(c=>[fieldName(c.field),c.suggested]));
    setForm(old=>({...old,fields:{...old.fields,...changes},...(changes.vocals&&changes.vocals!==old.fields.vocals?{lyricsMode:'auto',lyricsIntent:undefined}:{})}));
  };
  return <section className="brief-template">
    <label className="field"><span className="field-label">BRIEF TEMPLATE</span><select aria-label="Brief template" value={form.fields.template||'none'} onChange={e=>patch({template:e.target.value})}>{choices.map(t=><option value={t} key={t}>{t}</option>)}</select></label>
    <div className="template-actions"><button disabled={!answer?.fills?.length} onClick={copy}>Copy template text</button><button disabled={!answer?.choices?.length} onClick={applyChoices}>Use template choices</button><button disabled={!answer||answer.template==='none'} onClick={()=>{patch(Object.fromEntries(textFields.filter(k=>k in form.fields).map(k=>[k,''])));notify('Brief text cleared. Template defaults now apply.')}}>Reset all to template</button></div>
    {error?<p className="job-error">{error}</p>:answer&&<details><summary>Template defaults & suggestions</summary>{answer.fills?.length?answer.fills.map(f=><p key={f.field}><strong>{f.field.replaceAll('_',' ')}:</strong> {f.value}</p>):<p>No empty fields are filled by this template.</p>}{answer.choices?.map(c=><p key={c.field}><strong>{c.field}:</strong> {c.suggested}</p>)}{answer.notes?.map((n,i)=><p key={i}>{n}</p>)}</details>}
  </section>;
}

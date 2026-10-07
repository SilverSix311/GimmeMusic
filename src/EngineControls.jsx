import React,{useEffect,useState} from 'react';
import {Power,MemoryStick,LoaderCircle} from 'lucide-react';

export default function EngineControls({status,api,notify}){
  const [busy,setBusy]=useState(false),[settings,setSettings]=useState(null);
  const control=settings||status.control||{};
  useEffect(()=>setSettings(null),[status]);
  useEffect(()=>{
    let last=0;
    const touch=e=>{
      if(!e.isTrusted||Date.now()-last<15000)return;
      last=Date.now();api('/api/engine/activity',{}).catch(()=>{});
    };
    for(const name of ['pointerdown','pointermove','keydown','wheel','input'])window.addEventListener(name,touch,{passive:true});
    return()=>{for(const name of ['pointerdown','pointermove','keydown','wheel','input'])window.removeEventListener(name,touch)};
  },[]);
  const action=async(action,extra={})=>{
    setBusy(true);
    try{setSettings(await api('/api/engine',{action,...extra}));notify(action==='settings'?'Idle timer updated.':action==='start'?'ComfyUI is starting…':action==='stop'?'ComfyUI stopped. The studio stays open.':'Model unload requested. The next generation will reload them.');}
    catch(e){notify(e.message,'error')}finally{setBusy(false)}
  };
  const working=Boolean(status.running||status.pending),remaining=Math.max(0,Math.ceil(((control.idle_minutes||30)*60-(control.idle_seconds||0))/60));
  return <div className="engine-controls">
    <div className="engine-buttons"><button disabled={busy||working||control.starting} onClick={()=>action(status.online?'stop':'start')} title={working?'Wait for running and queued music to finish':undefined}>{busy||control.starting?<LoaderCircle size={13} className="spin"/>:<Power size={13}/>} {control.starting?'Starting…':status.online?'Stop engine':'Start engine'}</button><button disabled={busy||!status.online||working} onClick={()=>action('unload')} title="Unload models and free cached memory"><MemoryStick size={13}/> Free memory</button></div>
    <label className="idle-setting">Unload when idle<select aria-label="Unload models when idle" value={control.idle_minutes??30} disabled={busy} onChange={e=>action('settings',{idle_minutes:Number(e.target.value)})}>{[0,15,30,60].map(m=><option key={m} value={m}>{m?m+' min':'Off'}</option>)}</select></label>
    <p title={control.message}>{!status.online?'Studio stays open while the engine is off.':working?'Idle timer paused · music is queued or running':!control.activity_bridge?'Restart engine to enable ComfyUI activity tracking.':control.released?'Memory released · reloads on next generation':control.idle_minutes===0?'Automatic unloading is off':`Unloads after ${remaining} min without activity`}</p>
  </div>;
}

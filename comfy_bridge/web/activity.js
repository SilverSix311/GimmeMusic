import {app} from '/scripts/app.js';
import {api} from '/scripts/api.js';

app.registerExtension({name:'GimmeMusic.Activity',setup(){
  let last=0;
  const touch=event=>{
    if(event&&!event.isTrusted)return;
    if(Date.now()-last<15000)return;
    last=Date.now();
    api.fetchApi('/gimmemusic/activity',{method:'POST'}).catch(()=>{});
  };
  for(const name of ['pointerdown','pointermove','keydown','wheel','input'])window.addEventListener(name,touch,{passive:true});
  touch();
}});

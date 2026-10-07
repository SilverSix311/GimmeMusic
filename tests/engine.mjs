import {chromium,expect} from '@playwright/test';
const browser=await chromium.launch({headless:true});
try{
 const page=await browser.newPage({viewport:{width:1600,height:1000}});
 await page.goto('http://127.0.0.1:8195');
 await expect(page.getByRole('button',{name:'Stop engine',exact:true})).toBeVisible();
 await expect(page.getByLabel('Unload models when idle')).toHaveValue('30');
 const actions=[];
 await page.route('**/api/engine',async route=>{actions.push(route.request().postDataJSON());await route.fulfill({json:{idle_minutes:30,activity_bridge:true,released:true}})});
 await page.getByRole('button',{name:'Free memory',exact:true}).click();
 expect(actions.at(-1).action).toBe('unload');
 await page.screenshot({path:'tests/engine-controls.png'});
 const response=await page.request.get('http://127.0.0.1:8195/api/status');const status=await response.json();
 await page.route('**/api/status',r=>r.fulfill({json:{...status,running:1,pending:2}}));
 await expect(page.getByRole('button',{name:'Stop engine',exact:true})).toBeDisabled({timeout:7000});
 await expect(page.getByRole('button',{name:'Free memory',exact:true})).toBeDisabled();
 const comfy=await browser.newPage();await comfy.goto('http://127.0.0.1:8189');
 const ping=comfy.waitForRequest(r=>r.url().endsWith('/gimmemusic/activity')&&r.method()==='POST');
 await comfy.waitForFunction(()=>window.app?.graph);
 await ping;
 console.log('PASS studio engine controls, busy guards, default idle timer, and native ComfyUI activity bridge.');
}finally{await browser.close()}

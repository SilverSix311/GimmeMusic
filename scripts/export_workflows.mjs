// Export the public API profiles through ComfyUI's own serializer, in an isolated browser session.
import {chromium} from '@playwright/test';
import fs from 'node:fs/promises';
import assert from 'node:assert/strict';
const browser=await chromium.launch({headless:true});
try {
  const page=await browser.newPage();
  await page.goto(process.env.GIMMEMUSIC_ENGINE_URL||'http://127.0.0.1:8189');
  await page.waitForFunction(()=>window.app?.graph);
  const profiles=JSON.parse(await fs.readFile('workflows/profiles.json','utf8'));
  await fs.mkdir('workflows/studio',{recursive:true});
  for(const [id,profile] of Object.entries(profiles)) {
    const prompt=structuredClone(profile.prompt);
    for(const node of Object.values(prompt)) {
      // The visual autogrow widget requires contiguous report socket numbers.
      const reports=Object.entries(node.inputs).filter(([k])=>k.startsWith('reports.report_')).sort(([a],[b])=>Number(a.split('_').at(-1))-Number(b.split('_').at(-1)));
      reports.forEach(([key])=>delete node.inputs[key]);
      reports.forEach(([,value],index)=>node.inputs['reports.report_'+index]=value);
    }
    const result=await page.evaluate(async ({prompt,id})=>{
      await window.app.loadApiJson(prompt,`GimmeMusic - ${id}.json`);
      const workflow=window.app.graph.serialize();
      await window.app.loadGraphData(workflow,true);
      return {workflow,output:(await window.app.graphToPrompt()).output};
    },{prompt,id});
    for(const [key,node] of Object.entries(prompt)) {
      const actual=result.output[key.replaceAll(':','_')];
      assert.equal(actual?.class_type,node.class_type);
      for(const [name,value] of Object.entries(node.inputs)) {
        const expected=Array.isArray(value)?[String(value[0]).replaceAll(':','_'),value[1]]:value;
        assert.deepEqual(actual.inputs[name],expected,`${id}: ${key}.${name}`);
      }
    }
    await fs.writeFile(`workflows/studio/GimmeMusic - ${id}.json`,JSON.stringify(result.workflow,null,2)+'\n');
    console.log(`${id}: settings and connections round-trip through ComfyUI successfully`);
  }
} finally {await browser.close()}

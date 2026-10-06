import { chromium, expect } from '@playwright/test';
const browser = await chromium.launch({headless:true});
try {
  const page = await browser.newPage({viewport:{width:1600,height:1000}});
  await page.goto('http://127.0.0.1:8195');
  await page.getByRole('button',{name:'Make a cover',exact:true}).click();
  await page.locator('.composer-tabs').getByRole('button',{name:'Lyrics',exact:true}).click();
  await page.getByLabel('Vocals',{exact:true}).selectOption('instrumental');
  await expect(page.getByLabel('MELODY',{exact:true})).toHaveValue('instrument plays the lead');
  await page.getByLabel('LEAD INSTRUMENT',{exact:true}).fill('piano');
  await expect(page.getByLabel('VOICE',{exact:true})).toHaveCount(0);
  let submitted;
  await page.route('**/api/generate',async route=>{submitted=route.request().postDataJSON();await route.fulfill({json:{ids:['test-instrumental']}})});
  await page.getByRole('button',{name:'Create cover',exact:false}).click();
  await expect.poll(()=>submitted?.fields['vocals.lead_instrument']).toBe('piano');
  await page.getByLabel('Vocals',{exact:true}).selectOption('new lyrics');
  await expect(page.getByLabel('PHRASING REFERENCE',{exact:true})).toHaveValue('false');
  await page.getByLabel('PHRASING REFERENCE',{exact:true}).selectOption('true');
  await page.getByRole('button',{name:'Create cover',exact:false}).click();
  await expect.poll(()=>submitted?.fields['vocals.phrasing_reference']).toBe(true);
  await expect(page.getByLabel('MELODY',{exact:true})).toHaveCount(0);
  console.log('PASS: instrumental controls, vocal mode switching, boolean settings, and submission payloads (intercepted).');
} finally { await browser.close(); }

import { chromium, expect } from '@playwright/test';
const browser = await chromium.launch({headless:true});
try {
  const page = await browser.newPage({viewport:{width:1600,height:1000}});
  await page.goto('http://127.0.0.1:8195');
  await expect(page.locator('.track').nth(2)).toBeVisible();
  const audio = page.locator('audio');
  const assertPlaying = async () => {
    await expect.poll(()=>audio.evaluate(a=>!a.paused && a.currentTime>0)).toBe(true);
    await expect(page.locator('.toast.error')).toHaveCount(0);
  };
  // Starting a different row used to assign src twice and abort play().
  await page.locator('.track').nth(1).locator('.track-cover button').click();
  await assertPlaying();
  const second = await audio.getAttribute('src');
  await page.locator('.track').nth(2).locator('.track-cover button').click();
  await assertPlaying();
  expect(await audio.getAttribute('src')).not.toBe(second);
  await page.getByRole('button',{name:'Next track',exact:true}).click();
  await assertPlaying();
  await page.getByRole('button',{name:'Previous track',exact:true}).click();
  await assertPlaying();
  await page.getByRole('button',{name:'Pause',exact:true}).click();
  expect(await audio.evaluate(a=>a.paused)).toBe(true);
  await page.getByRole('button',{name:'Play',exact:true}).click();
  await assertPlaying();
  // Rapid changes invalidate earlier play promises without false error notices.
  await page.locator('.track-cover button').evaluateAll(buttons=>{
    buttons[0].click(); buttons[1].click(); buttons[2].click();
  });
  await assertPlaying();
  await page.getByRole('slider',{name:'Playback position'}).fill('500');
  await expect.poll(()=>audio.evaluate(a=>a.currentTime/a.duration)).toBeGreaterThan(.49);
  console.log('PASS: start another song, switch while playing, next/previous, pause/resume, rapid switching, seek; no playback errors.');
} finally { await browser.close(); }

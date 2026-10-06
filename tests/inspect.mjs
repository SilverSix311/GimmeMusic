import { chromium } from '@playwright/test';
const browser=await chromium.launch({headless:true});
const page=await browser.newPage({viewport:{width:1600,height:1000}});
page.on('pageerror', e=>console.log('PAGE ERROR',e.message));
await page.goto('http://127.0.0.1:8195');
await page.locator('.track').first().waitFor();
await page.screenshot({path:'tests/desktop.png',fullPage:true});
console.log('tracks',await page.locator('.track').count());
await browser.close();

/* Re-drive the frozen Builder Center captures, audit full-text navigation, and then
   run the supplier proof as an already-onboarded visitor. Writes only to the supplied
   output directory. Defaults to the public offline demo; override POOL_CAPTURE_URL
   for a local production build. No model invocation, no video editing. */
import { createRequire } from 'node:module';
// Use an existing Playwright installation; the frozen media directory is only read.
// POOL_PLAYWRIGHT_PACKAGE can name another package.json with Playwright installed.
const require = createRequire(process.env.POOL_PLAYWRIGHT_PACKAGE || new URL('../video/final-hybrid-human/package.json', import.meta.url));
const { chromium } = require('playwright');
import fs from 'node:fs';

const URL = process.env.POOL_CAPTURE_URL || 'https://d38kno05ygcarw.cloudfront.net/verify';
const OUT = process.argv[2];
if (!OUT) throw new Error('Usage: node scripts/audit_demo_polish.mjs /tmp/pool-audit');
fs.mkdirSync(OUT, { recursive: true });
const facts = [];

const browser = await chromium.launch();
const ctx = async () => {
  const page = await (await browser.newContext({viewport: {width:390,height:844}, deviceScaleFactor:2, timezoneId:'America/Chicago'})).newPage();
  // Original captures: Sep 11 UTC, Sep 10 evening locally. Pin Date, not timers.
  await page.clock.setFixedTime(new Date('2026-09-11T02:00:00Z'));
  return page;
};

const shot = async (page, name) => {

  /* Scroll to the document top first. An element screenshot scrolls the element into
     view, which can park the sticky header over main's first rows. */
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.waitForTimeout(900);                      // let any 240 ms reveal settle
  /* fullPage, not an element screenshot: an element capture composites the sticky
     header over main's first rows. fullPage paints the document once, so the header
     sits at its natural top and nothing is occluded. Still a straight capture. */
  await page.screenshot({ path: `${OUT}/${name}.png`, fullPage: true });
  console.log('  shot', name);
};
const txt = async (page) => (await page.locator('main').innerText()).replace(/\s+/g, ' ');

/* ---------- 4. Share my location (fresh session, onboarding step 2) ---------- */
{
  const page = await ctx();
  await page.goto(URL, { waitUntil: 'networkidle' });
  await page.getByRole('button', { name: /^Start/ }).click();
  await page.getByPlaceholder('Alex').fill('Alex');
  await page.getByRole('button', { name: 'Continue', exact: true }).click();
  await page.getByRole('button', { name: 'Share my location' }).waitFor();
  facts.push(['location step', await txt(page)]);
  await shot(page, 'article-3-share-my-location', 'main');
  await page.close();
}

/* ---------- the declaring session ---------- */
const page = await ctx();
const proof = [];
page.on('response', async response => {
  if (/\/api\/needs\/[^/]+\/coordination\?/.test(response.url()) && response.ok()) {
    proof.push(await response.json());
  }
});
await page.goto(URL, { waitUntil: 'networkidle' });
await page.getByRole('button', { name: /^Start/ }).click();
await page.getByPlaceholder('Alex').fill('Alex');
await page.getByRole('button', { name: 'Continue', exact: true }).click();
await page.getByRole('button', { name: 'Share my location' }).click();

/* 1. Declaration / flexibility */
await page.getByPlaceholder(/coffee, paper towels/).fill('coffee');
await page.getByRole('button', { name: /Or pick one exact product/ }).click();
await page.getByText('Kestrel Roastworks').last().click();
await page.getByText('Any brand that matches my preferences').click();
await page.waitForTimeout(4000);                        // clarification questions arrive
facts.push(['declaration', await txt(page)]);
await shot(page, 'article-1-declare-flexibility', 'main');

await page.getByRole('button', { name: 'Add this' }).click();
await page.getByRole('button', { name: 'Continue', exact: true }).click();
await page.getByRole('button', { name: 'Finish' }).click();
await page.waitForTimeout(11000);                       // the bounded run

/* allow dark roast so the Harbourstone adaptation can form */
await page.getByRole('button', { name: 'What you buy', exact: true }).click();
await page.getByRole('button', { name: 'Change' }).first().click();
await page.waitForTimeout(1500);
await page.getByText('Dark', { exact: true }).click();
await page.getByRole('button', { name: 'Save changes' }).click();
await page.waitForTimeout(12000);

/* 2. Why this order? */
await page.getByRole('button', { name: 'Home', exact: true }).click();
await page.waitForTimeout(2500);
facts.push(['home / order', await txt(page)]);
await page.getByText('Why this order?').click();
await page.waitForTimeout(2500);
facts.push(['why this order', await txt(page)]);
await shot(page, 'article-2-why-this-order', 'main');

/* 3. Paper towels 7 of 48 */
await page.getByRole('button', { name: 'What you buy', exact: true }).click();
await page.waitForTimeout(2000);
await page.getByRole('button', { name: 'Add a need' }).click();
await page.getByPlaceholder(/coffee, paper towels/).fill('paper towels');
await page.waitForTimeout(2500);
await page.getByText('Paper towels', { exact: true }).first().click();
await page.getByRole('button', { name: 'Add this need' }).click();
await page.waitForTimeout(11000);
await page.getByRole('button', { name: 'Home', exact: true }).click();
await page.waitForTimeout(2500);
facts.push(['home / towels', await txt(page)]);
await shot(page, 'article-3-paper-towels-7-of-48', 'main');

// Sample the whole screen, not only the heading: the original short probe missed
// 435–446 ms of missing content below the heading on Home and What you buy.
const transitions = [];
for (const name of ['What you buy', 'Home', 'Orders', 'Home']) {
  await page.evaluate(() => {
    window.auditFrames = [];
    window.auditSampling = true;
    const start = performance.now();
    const sample = () => {
      if (!window.auditSampling) return;
      const text = document.querySelector('main')?.innerText.replace(/\s+/g, ' ').trim() ?? '';
      const last = window.auditFrames.at(-1);
      if (!last || last.text !== text) window.auditFrames.push({ms: Math.round(performance.now() - start), text});
      requestAnimationFrame(sample);
    };
    requestAnimationFrame(sample);
  });
  await page.getByRole('button', {name, exact:true}).click();
  await page.waitForTimeout(1500);
  const frames = await page.evaluate(() => {window.auditSampling = false; return window.auditFrames;});
  transitions.push({name, frames});
  console.log('navigation', name, frames.map(f => f.ms));
}
fs.writeFileSync(`${OUT}/navigation.json`, JSON.stringify(transitions, null, 2));

// Verify that the new route works for an already-onboarded coffee buyer.
await page.getByTitle('Demo environment, controls, and what is real here').click();
if (await page.getByRole('button', {name:'Reset Demo University',exact:true}).count()) throw new Error('member has operator reset');
await page.getByRole('button', {name:'Check the supplier walkthrough'}).click();
await page.getByRole('heading', {name:"Check Pool's central claim yourself"}).waitFor();
if (await page.getByText('An order formed from demand that was already there.', {exact:false}).count()) throw new Error('coffee counted as rice proof');
console.log('judge route after coffee:', page.url());
await page.getByRole('button', {name:'Set that up for me'}).click();
await page.getByRole('button', {name:'Import quote A',exact:false}).waitFor();
await page.waitForTimeout(1500);
await page.getByRole('button', {name:'Import quote A',exact:false}).click();
await page.getByRole('button', {name:'Import quote B',exact:false}).waitFor();
await page.waitForTimeout(2000);
facts.push(['judge refused A', await txt(page)]);
await page.getByRole('button', {name:'Import quote B',exact:false}).click();
await page.waitForTimeout(2000);
facts.push(['judge ready B', await txt(page)]);
await page.getByRole('button', {name:'Ask Pool to check now',exact:false}).click();
await page.getByRole('button', {name:'See it on your home screen'}).waitFor({timeout:45000});
facts.push(['judge formed', await txt(page)]);
console.log('judge proof completed');
const checks = [
  ['location step', ['Find people near you', 'Share my location', 'Synthetic location for this demo — Pool did not ask your browser where you are.']],
  ['home / order', ['$43.96', '$55.50', 'with 5 others', "past the supplier's 12-bag minimum", 'Host needed', 'Nothing charged']],
  ['why this order', ['Kestrel Roastworks', '$367.19', '$360.00', '23 bags standing from 8 people', 'Harbourstone Coffee', 'CHOSEN', 'Saves $69.18', '$263.82', '$333.00', '20.7%', '18 bags · 3 full cases of 6 · nothing left over', 'Nothing has been charged, ordered or assigned']],
  ['home / towels', ['7 packs declared 48 required 3 people near you']],
  ['judge refused A', ['Supplier found — not cheaper']],
  ['judge formed', ['An order formed from demand that was already there']],
];
for (const [label, expected] of checks) {
  const value = facts.find(([key]) => key === label)?.[1] ?? '';
  for (const phrase of expected) if (!value.includes(phrase)) throw new Error(`${label}: missing ${phrase}`);
}
if (!proof.some(p => JSON.stringify(p).includes('not_cheaper'))) throw new Error('missing stored refusal');
if (proof.some(p => p.run && (p.run.input_tokens !== 0 || p.run.output_tokens !== 0))) throw new Error('unexpected model tokens');
fs.writeFileSync(`${OUT}/coordination.json`, JSON.stringify(proof, null, 2));
console.log('canonical UI facts and stored zero-token refusal verified');
await browser.close();
fs.writeFileSync(`${OUT}/facts.txt`, facts.map(([k, v]) => `### ${k}\n${v}\n`).join('\n'));
console.log('done');

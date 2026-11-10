const fs = require('fs');
const path = require('path');
const root = path.resolve(__dirname, '..');
process.env.PLAYWRIGHT_BROWSERS_PATH = path.join(root, 'work', 'recording-tools', 'browsers');
const { chromium } = require('./recording-tools/node_modules/playwright');
(async () => {
  const dir = path.join(root, 'work', 'demo');
  fs.mkdirSync(dir, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1600, height: 1000 }, reducedMotion: 'reduce' });
  const token = fs.readFileSync(path.join(root, 'fraud-investigation', '.tools', 'analyst-demo.token'), 'utf8').trim();
  await context.addInitScript(({token}) => sessionStorage.setItem('fraudinv.analystToken', token), {token});
  const page = await context.newPage();
  await page.goto('http://127.0.0.1:8765', { waitUntil: 'networkidle' });
  await page.getByText('Replay runs', { exact: true }).waitFor();
  await page.screenshot({ path: path.join(dir, 'overview.png'), fullPage: true });
  const data = await page.evaluate(async () => {
    const overview = await (await fetch('/overview')).json();
    const queue = await (await fetch('/cases?run_id=demo-test-d14-16&day=15&limit=100')).json();
    return { overview, queue };
  });
  const seen = new Set();
  for (const f of ['assistant_eval_holdout.json','assistant_eval_v2_holdout.json','assistant_eval_v2_dev.json']) {
    const p = path.join(root,'fraud-investigation','reports','day6',f);
    if (fs.existsSync(p)) for (const r of JSON.parse(fs.readFileSync(p)).results || []) if(r.case) seen.add(r.case);
  }
  const candidates = data.queue.items.filter(c => c.status === 'new' && !seen.has(c.case_id));
  const main = candidates.find(c => !c.dest_has_prior) || candidates[0];
  const history = candidates.find(c => c.dest_has_prior) || data.queue.items.find(c=>c.dest_has_prior);
  if (!main) throw new Error('No new, non-evaluation demonstration case available');
  fs.writeFileSync(path.join(dir, 'selection.json'), JSON.stringify({main,history}, null, 2));
  console.log(JSON.stringify({runs:data.overview.runs,queue_total:data.queue.total,main,history},null,2));
  await page.goto('http://127.0.0.1:8765/#/case/' + encodeURIComponent(main.case_id), { waitUntil:'networkidle' });
  await page.getByRole('heading',{name:'Transaction',exact:true}).waitFor();
  await page.screenshot({path:path.join(dir,'case.png'),fullPage:true});
  console.log((await page.locator('body').innerText()).slice(0,11000));
  await context.close();
  await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});

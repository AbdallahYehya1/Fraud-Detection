const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const root = path.resolve(__dirname, '..');
const dir = path.join(root, 'work', 'demo');
const app = path.join(root, 'fraud-investigation');
process.env.PLAYWRIGHT_BROWSERS_PATH = path.join(root, 'work', 'recording-tools', 'browsers');
const { chromium } = require('./recording-tools/node_modules/playwright');
const selection = JSON.parse(fs.readFileSync(path.join(dir, 'selection.json')));
const base = 'http://127.0.0.1:8765';
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
const digest = p => crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const protectedFiles = ['assistant_eval_holdout.json','assistant_eval_v2_holdout.json','assistant_freeze_v2.json'];

(async () => {
  const metadata = { recorded_date:'2026-11-10', actual_app_capture:true, audio:'none; captioned',
    model:'qwen3:4b', case_id:selection.main.case_id, chapter_marks:[],
    protected_report_hashes_before:Object.fromEntries(protectedFiles.map(f=>[f,digest(path.join(app,'reports','day6',f))])) };
  const browser = await chromium.launch({ headless:true });
  const context = await browser.newContext({
    viewport:{width:1600,height:1000}, recordVideo:{dir:path.join(dir,'raw'),size:{width:1600,height:1000}},
    reducedMotion:'reduce'
  });
  const token = fs.readFileSync(path.join(app,'.tools','analyst-demo.token'),'utf8').trim();
  await context.addInitScript(({token})=>sessionStorage.setItem('fraudinv.analystToken',token),{token});
  const page = await context.newPage();
  page.setDefaultTimeout(20000);
  const started = Date.now();
  const mark = (title, detail) => {
    const sec=(Date.now()-started)/1000;
    metadata.chapter_marks.push({start_seconds:sec,title,detail});
    console.log(JSON.stringify({chapter:title,seconds:Math.round(sec)}),true);
  };
  const show = async (locator) => {
    await locator.evaluate(el=>el.scrollIntoView({block:'start',behavior:'instant'}));
    await page.evaluate(()=>window.scrollBy(0,-75));
    await pause(1000);
  };
  try {
    await page.goto(base,{waitUntil:'networkidle'});
    await page.getByText('Replay runs',{exact:true}).waitFor();
    mark('1 / 7  •  FRAUD REVIEW WORKBENCH',
         'Prioritize recorded transactions for human review. Synthetic PaySim v2; all services run locally.');
    await pause(14000);
    mark('A REPRODUCIBLE MODEL AND REVIEW POLICY',
         'Frozen features and model version. Top 100 reviews per simulation day; ranking scores are not probabilities.');
    await pause(16000);
    await show(page.getByRole('heading',{name:'Frozen test partition (run once)',exact:true}));
    mark('2 / 7  •  MEASURED OFFLINE RESULTS',
         'Champion: 1,189 of 4,250 positives found at 100/day. The amount/type rule found 670.');
    await pause(14000);
    mark('SIMULATOR LIMITATIONS STAY VISIBLE',
         'Many hours contain only fraud-labelled rows. Mixed-hour hits: 505 of 2,000; no real-bank savings claim.');
    await pause(14000);
    await page.getByRole('link',{name:'Queue',exact:true}).click();
    await page.getByRole('heading',{name:'Alert queue',exact:true}).waitFor();
    await page.getByLabel('Simulation day',{exact:true}).fill('15');
    await page.getByRole('link',{name:selection.main.event_id,exact:true}).waitFor();
    mark('3 / 7  •  A CAPACITY-LIMITED ANALYST QUEUE',
         'Day 15: ranked alerts, simulation units and explicit missing-history indicators.');
    await pause(20000);
    await page.getByRole('link',{name:selection.main.event_id,exact:true}).click();
    await page.getByRole('heading',{name:'Transaction',exact:true}).waitFor();
    metadata.evidence_before_assistant = await page.evaluate(async id =>
      (await fetch('/cases/'+id+'/evidence')).json(), selection.main.case_id);
    mark('4 / 7  •  EVIDENCE FOR THIS CASE',
         'The case records its scoring step and review cutoff. Model associations are not proof of fraud.');
    await pause(18000);
    await show(page.getByRole('heading',{name:'Computed facts',exact:true}));
    mark('COMPUTED FACTS AND KNOWN GAPS',
         'Source-linked facts are separated from missing device, identity and customer information.');
    await pause(17000);
    if(selection.history) {
      await page.goto(base+'/#/case/'+encodeURIComponent(selection.history.case_id),{waitUntil:'networkidle'});
      await page.getByRole('heading',{name:'Recipient history',exact:true}).waitFor();
      await show(page.getByRole('heading',{name:'Recipient history',exact:true}));
      mark('HISTORY AT SCORING VS. EVIDENCE AT REVIEW',
           'A second case shows earlier recipient records and later review-time records in separate sections.');
      await pause(16000);
    }
    await page.goto(base+'/#/case/'+encodeURIComponent(selection.main.case_id),{waitUntil:'networkidle'});
    await show(page.getByRole('heading',{name:'Local assistant',exact:true}));
    mark('5 / 7  •  LIVE LOCAL INVESTIGATION ASSISTANT',
         'One case, read-only evidence tools and a fixed cutoff. This generation is shown in real time.');
    const answerPromise = page.waitForResponse(r=>r.url().endsWith('/assistant')&&r.request().method()==='POST',{timeout:240000});
    await page.getByRole('button',{name:'Ask',exact:true}).click();
    const response = await answerPromise;
    if(!response.ok()) throw new Error('Assistant API status '+response.status());
    const reply = await response.json();
    metadata.assistant = reply;
    if(reply.mode!=='assistant') throw new Error('Live case returned '+reply.mode+'; preserve this attempt and inspect before retrying');
    await page.locator('.assistant-reply').waitFor();
    await show(page.locator('.assistant-reply'));
    await page.screenshot({path:path.join(dir,'live-assistant.png'),fullPage:true});
    metadata.evidence_after_assistant=await page.evaluate(async id=>
      (await fetch('/cases/'+id+'/evidence')).json(),selection.main.case_id);
    metadata.assistant_changed_case = metadata.evidence_after_assistant.case.version!==metadata.evidence_before_assistant.case.version
      ||metadata.evidence_after_assistant.audit.length!==metadata.evidence_before_assistant.audit.length
      ||metadata.evidence_after_assistant.notes.length!==metadata.evidence_before_assistant.notes.length;
    if(metadata.assistant_changed_case) throw new Error('Case state changed during assistant section');
    mark('CHECKED ANSWER, VISIBLE REFERENCES',
         'The system-added scope line is distinct from model text. The assistant did not change the case.');
    await pause(23000);
    await show(page.getByRole('heading',{name:'Review action',exact:true}));
    mark('6 / 7  •  THE HUMAN MAKES THE DECISION',
         'Start review, add an analyst note, and close with “needs more information.” No fraud label is asserted.');
    await page.getByPlaceholder('Analyst note (optional for a status change)').fill(
      'Demo review: inspected source facts and the evidence cutoff; further investigation is required.');
    await pause(2500);
    const transition1=page.waitForResponse(r=>r.url().endsWith('/transition')&&r.request().method()==='POST');
    await page.getByRole('button',{name:'Start review',exact:true}).click();
    if(!(await transition1).ok()) throw new Error('Start review failed');
    await page.getByRole('button',{name:'Close with disposition',exact:true}).waitFor();
    await pause(3500);
    await page.getByLabel('Disposition (required to close)',{exact:true}).selectOption('needs_more_information');
    await pause(2500);
    const transition2=page.waitForResponse(r=>r.url().endsWith('/transition')&&r.request().method()==='POST');
    await page.getByRole('button',{name:'Close with disposition',exact:true}).click();
    if(!(await transition2).ok()) throw new Error('Close failed');
    await page.getByText('Closed cases cannot be reopened in this demo.',{exact:true}).waitFor();
    await pause(2500);
    await show(page.getByRole('heading',{name:'Audit trail',exact:true}));
    mark('AN APPEND-ONLY REVIEW TRAIL',
         'The audit records the human actor, actions, prior state and new state.');
    await pause(13000);
    await page.screenshot({path:path.join(dir,'audit-trail.png'),fullPage:true});
    metadata.evidence_after_review=await page.evaluate(async id=>
      (await fetch('/cases/'+id+'/evidence')).json(),selection.main.case_id);
    await page.getByRole('link',{name:'Overview',exact:true}).click();
    await page.getByText('Replay runs',{exact:true}).waitFor();
    await page.evaluate(()=>window.scrollTo(0,0));
    mark('7 / 7  •  REPRODUCIBLE, WITH HONEST LIMITS',
         '101 tests pass. Fresh assistant holdout: 10/12; two failures remain documented, with no unsafe delivered output observed.');
    await pause(17000);
    mark('KNOWN ASSISTANT LIMITATIONS',
         'Question-number filtering, refusal grading and short note paraphrases need further work. Small holdout; no universal safety claim.');
    await pause(14000);
    metadata.duration_seconds=(Date.now()-started)/1000;
    metadata.completed=true;
  } catch(e) {
    metadata.completed=false;
    metadata.error=String(e.stack||e);
    console.error(e);
    await page.screenshot({path:path.join(dir,'recording-error.png'),fullPage:true}).catch(()=>{});
  } finally {
    const video=page.video();
    await context.close();
    await video.saveAs(path.join(dir,'browser-recording.webm'));
    await browser.close();
    metadata.protected_report_hashes_after=Object.fromEntries(protectedFiles.map(f=>[f,digest(path.join(app,'reports','day6',f))]));
    metadata.protected_reports_unchanged=JSON.stringify(metadata.protected_report_hashes_before)===JSON.stringify(metadata.protected_report_hashes_after);
    fs.writeFileSync(path.join(dir,'recording-metadata.json'),JSON.stringify(metadata,null,2));
    console.log(JSON.stringify({completed:metadata.completed,duration_seconds:metadata.duration_seconds,protected_reports_unchanged:metadata.protected_reports_unchanged,error:metadata.error||null}));
    if(!metadata.completed) process.exitCode=1;
  }
})().catch(e=>{console.error(e);process.exit(1)});

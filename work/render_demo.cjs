const fs=require('fs');
const path=require('path');
const {spawnSync}=require('child_process');
const crypto=require('crypto');
const root=path.resolve(__dirname,'..');
const dir=path.join(root,'work','demo');
const out=path.join(root,'outputs');
const meta=JSON.parse(fs.readFileSync(path.join(dir,'recording-metadata.json'),'utf8'));
if(!meta.completed || !meta.protected_reports_unchanged) throw new Error('Recording not completed or protected reports changed');
const ffmpeg=require('./recording-tools/node_modules/@ffmpeg-installer/ffmpeg').path;
const marks=meta.chapter_marks;
const esc=s=>s.replace(/\\/g,'/').replace(/[{}]/g,'');
const assTime=s=>{
  const cs=Math.round(s*100),h=Math.floor(cs/360000),m=Math.floor(cs/6000)%60,sec=Math.floor(cs/100)%60;
  return h+':'+String(m).padStart(2,'0')+':'+String(sec).padStart(2,'0')+'.'+String(cs%100).padStart(2,'0');
};
const srtTime=s=>{
  const ms=Math.round(s*1000),h=Math.floor(ms/3600000),m=Math.floor(ms/60000)%60,sec=Math.floor(ms/1000)%60;
  return String(h).padStart(2,'0')+':'+String(m).padStart(2,'0')+':'+String(sec).padStart(2,'0')+','+String(ms%1000).padStart(3,'0');
};
let ass='[Script Info]\nScriptType: v4.00+\nPlayResX: 1600\nPlayResY: 1120\nWrapStyle: 0\n\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\nStyle: Default,Segoe UI,26,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,2,40,40,20,1\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n';
let srt='';
for(let i=0;i<marks.length;i++){
  const m=marks[i],end=marks[i+1]?.start_seconds ?? meta.duration_seconds;
  ass+='Dialogue: 0,'+assTime(m.start_seconds)+','+assTime(end)+',Default,,0,0,0,,{\\b1\\fs28}'+esc(m.title)+'{\\b0\\fs26}\\N'+esc(m.detail)+'\n';
  srt+=(i+1)+'\n'+srtTime(m.start_seconds)+' --> '+srtTime(end)+'\n'+m.title+'\n'+m.detail+'\n\n';
}
fs.writeFileSync(path.join(dir,'captions.ass'),ass,'utf8');
fs.writeFileSync(path.join(out,'Fraud_Detection_Demo.srt'),srt,'utf8');
const target=path.join(out,'Fraud_Detection_Demo.mp4');
const filter='[0:v]trim=end='+meta.source_clips.prefix_end+',setpts=PTS-STARTPTS[v0];[1:v]trim=start='+meta.source_clips.continuation_start+',setpts=PTS-STARTPTS[v1];[v0][v1]concat=n=2:v=1:a=0,pad=iw:ih+120:0:0:color=0x111827,subtitles=captions.ass[v]';
let r=spawnSync(ffmpeg,['-hide_banner','-y','-i','browser-recording-part1.webm','-i','browser-recording-part2.webm','-filter_complex',filter,'-map','[v]','-c:v','libx264','-preset','fast','-crf','19','-pix_fmt','yuv420p','-r','25','-an','-movflags','+faststart',target],{cwd:dir,encoding:'utf8',maxBuffer:10*1024*1024});
fs.writeFileSync(path.join(dir,'encode.log'),r.stderr||'');
if(r.status!==0) throw new Error('Encoding failed: '+(r.stderr||'').slice(-3000));
r=spawnSync(ffmpeg,['-v','error','-i',target,'-f','null','-'],{cwd:dir,encoding:'utf8',maxBuffer:2*1024*1024});
if(r.status!==0 || (r.stderr||'').trim()) throw new Error('Decode verification failed: '+r.stderr);
meta.delivery={
  file:'Fraud_Detection_Demo.mp4',
  bytes:fs.statSync(target).size,
  sha256:crypto.createHash('sha256').update(fs.readFileSync(target)).digest('hex'),
  caption_file:'Fraud_Detection_Demo.srt',
  capture:'Unmodified local app behaviour; browser video with editorial captions in a separate lower band.',
  playback:'Real-time actions and AI generation; one chapter edit between human review actions.',
  full_decode_verified:true
};
const summary={
  recorded_date:meta.recorded_date,case_id:meta.case_id,duration_seconds:meta.duration_seconds,
  assistant:{mode:meta.assistant.mode,model:meta.assistant.model,seconds:meta.assistant.seconds,tool_calls:meta.assistant.tool_calls,case_changed:meta.assistant_changed_case},
  review:{status:meta.evidence_after_review.case.status,disposition:meta.evidence_after_review.case.disposition,audit_entries:meta.evidence_after_review.audit.length},
  protected_reports_unchanged:meta.protected_reports_unchanged,protected_report_sha256:meta.protected_report_hashes_after,
  capture_edit:meta.capture_edit,
  delivery:meta.delivery,chapters:marks
};
fs.writeFileSync(path.join(out,'Fraud_Detection_Demo_Verification.json'),JSON.stringify(summary,null,2));
fs.writeFileSync(path.join(dir,'recording-metadata.json'),JSON.stringify(meta,null,2));
spawnSync(ffmpeg,['-hide_banner','-y','-i',target,'-vf','fps=1/40,scale=640:-1',path.join(dir,'frame-%02d.jpg')],{encoding:'utf8',maxBuffer:1024*1024});
console.log(JSON.stringify({duration_seconds:meta.duration_seconds,bytes:meta.delivery.bytes,full_decode_verified:true,protected_reports_unchanged:meta.protected_reports_unchanged,assistant_seconds:meta.assistant.seconds},null,2));

/* VEAP Studio local pilot. No persistent browser token storage. */
'use strict';
const state={token:'',me:null,tenant:'',project:'',scenarios:[],runs:[],evidence:[],scene:null,trace:[],currentRun:null,selectedReport:null,playing:false,playHandle:null};
const el=(id)=>document.getElementById(id);
const text=(id,value)=>{let e=el(id);if(e)e.textContent=String(value??'—');};
const msg=(value)=>{text('toast',value);clearTimeout(msg.timer);msg.timer=setTimeout(()=>text('toast',''),4000);};
const opt=(id,options)=>{let s=el(id);s.replaceChildren();for(let [value,label] of options)s.add(new Option(label,value));};
async function api(path,options={}){
  const headers={'Authorization':'Bearer '+state.token,...(options.headers||{})};
  const res=await fetch('/api/studio'+path,{...options,headers,cache:'no-store'});
  if(!res.ok){let err={};try{err=await res.json();}catch{}throw new Error((err.detail||'HTTP '+res.status).toString());}
  const ct=res.headers.get('content-type')||'';
  if(options.download||ct.includes('application/octet-stream'))return res.blob();
  return res.json();
}
const base=()=>'/t/'+encodeURIComponent(state.tenant);
const projectPath=()=>base()+'/projects/'+encodeURIComponent(state.project);
function selectPage(which){
  for(const e of document.querySelectorAll('.view'))e.hidden=e.id!=='view-'+which;
  for(const e of document.querySelectorAll('.nav-link'))e.classList.toggle('active',e.dataset.view===which);
  text('current-view',({'overview':'Command center','experiments':'Experiment lab','evidence':'Evidence vault','reviews':'Human review','audit':'Audit ledger','engines':'Engine status'})[which]);
  if(which==='audit')loadAudit();if(which==='engines')loadEngines();if(which==='reviews')loadReviews();
}
async function connect(){
  const supplied=el('token-input').value.trim();if(!supplied){text('connect-error','A personal bearer token is required.');return;}
  state.token=supplied;
  try{
    const me=await api('/me');state.me=me;state.token=supplied;el('token-input').value='';text('user-pill',me.name+' · '+me.email);
    el('connect-overlay').hidden=true;
    opt('tenant-select',me.tenants.map(t=>[t.id,t.name+' / '+t.role]));
    if(me.tenants.length){state.tenant=me.tenants[0].id;await loadTenant();}
    else msg('Account is not assigned to any organisation.');
  }catch(error){state.token='';text('connect-error',error.message);}
}
function disconnect(){state.token='';state.me=null;state.tenant='';state.project='';state.runs=[];state.scene=null;state.trace=[];el('connect-overlay').hidden=false;el('token-input').value='';text('user-pill','Not connected');draw();}
async function loadTenant(){
  if(!state.tenant)return;
  try{
    const [projects,scenarios]=await Promise.all([api(base()+'/projects'),api(base()+'/scenarios')]);
    state.scenarios=scenarios;
    opt('scenario-select',scenarios.map(s=>[s.id,s.title]));
    opt('project-select',projects.map(p=>[p.id,p.name]));
    state.project=projects[0]?.id||'';
    await loadProject();await loadScene();
  }catch(error){msg('Unable to read workspace: '+error.message);}
}
async function loadProject(){
  if(!state.project){state.runs=[];state.evidence=[];updateProjectUI();return;}
  try{
    [state.runs,state.evidence]=await Promise.all([api(projectPath()+'/runs'),api(projectPath()+'/evidence')]);
    updateProjectUI();
  }catch(error){msg(error.message);}
}
function cell(row,val){const td=document.createElement('td');td.textContent=String(val??'—');row.append(td);return td;}
function statusPill(val,isBad=false){const b=document.createElement('span');b.className='pill'+(isBad?' bad':(!val?' gray':''));b.textContent=val?'YES':'NO';return b;}
function updateProjectUI(){
  text('kpi-runs',state.runs.length);
  text('kpi-verified',state.runs.filter(r=>r.summary?.verified).length);
  text('kpi-violations',state.runs.reduce((n,r)=>n+(r.summary?.safety_violations||0),0));
  text('kpi-evidence',state.evidence.length);
  text('run-count',state.runs.length+' RECORDS');
  for(const id of ['run-table','experiments-table'])el(id).replaceChildren();
  for(const r of state.runs){
    const summary=r.summary||{};
    const row=document.createElement('tr');row.dataset.run=r.id;
    cell(row,r.id.slice(0,10));cell(row,r.scenario_id);cell(row,r.policy+(r.shield?' + gate':''));cell(row,r.status);
    const td=document.createElement('td');td.append(statusPill(Boolean(summary.verified),r.status==='completed'&&!summary.verified));row.append(td);
    row.onclick=()=>selectRun(r.id);
    el('run-table').append(row);
    const long=document.createElement('tr');long.dataset.run=r.id;
    for(const val of [r.id.slice(0,12),r.scenario_id,r.policy,r.seed,r.status,summary.safety_violations??'—'])cell(long,val);
    long.onclick=()=>selectRun(r.id);el('experiments-table').append(long);
  }
  if(!state.runs.length)for(const id of ['run-table','experiments-table']){
    const tr=document.createElement('tr');const td=document.createElement('td');td.colSpan=id==='run-table'?5:6;td.className='muted-cell';td.textContent='No experiments recorded in this project.';tr.append(td);el(id).append(tr);
  }
  const completed=state.runs.filter(r=>r.status==='completed');
  opt('review-run',completed.map(r=>[r.id,r.id.slice(0,10)+' · '+r.scenario_id]));
  if(completed.length&&state.currentRun===null)state.currentRun=completed[0].id;
  const tbl=el('evidence-table');tbl.replaceChildren();
  for(const e of state.evidence){const row=document.createElement('tr');cell(row,e.filename);cell(row,e.format);cell(row,(e.size_bytes/1024).toFixed(1)+' KB');cell(row,e.content_sha256.slice(0,15)+'…');cell(row,e.provenance);
    row.style.cursor='pointer';row.title='Click to download tenant-scoped evidence';row.onclick=()=>downloadEvidence(e);tbl.append(row);
  }
  if(!state.evidence.length){let row=document.createElement('tr');let td=document.createElement('td');td.colSpan=5;td.className='muted-cell';td.textContent='No external evidence uploaded.';row.append(td);tbl.append(row);}
}
async function loadScene(){
  if(!state.tenant||!el('scenario-select').value)return;
  try{state.scene=await api(base()+'/scenarios/'+encodeURIComponent(el('scenario-select').value)+'/scene');state.trace=[];text('scene-name',state.scene.scene_id.toUpperCase());draw();}
  catch(error){msg(error.message);}
}
async function startRun(){
  if(!state.project){msg('Create a project before running a trial.');return;}
  const body={scenario_id:el('scenario-select').value,policy:el('policy-select').value,
    shield:el('shield').checked,seed:Number(el('seed-input').value)};
  const button=el('execute');button.disabled=true;
  try{
    const result=await api(projectPath()+'/runs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    state.currentRun=result.id;text('verification-status','QUEUED');text('verification-desc','Worker processing read-only experiment.');
    await pollRun(result.id);
  }catch(err){msg('Run failed to start: '+err.message);}finally{button.disabled=false;}
}
async function pollRun(id){
  for(let i=0;i<50;i++){
    if(!state.token||!state.project)return;
    const run=await api(projectPath()+'/runs/'+id);
    text('verification-status',run.status.toUpperCase());
    if(['completed','failed','rejected','interrupted'].includes(run.status)){
      await loadProject();await selectRun(id);return;
    }
    await new Promise(resolve=>setTimeout(resolve,350));
  }
  msg('Run is still queued. Refresh the project to inspect the result.');
}
async function selectRun(id){
  if(!id||!state.project)return;
  try{
    state.currentRun=id;
    const r=await api(projectPath()+'/runs/'+id);
    text('selected-run-json',JSON.stringify(r,null,2));
    const s=r.summary||{};
    text('verification-status',r.status==='completed'?(s.verified?'ACCEPTED · MODELLED CONTRACT':'REJECTED · MODELLED CONTRACT'):r.status.toUpperCase());
    text('verification-desc',r.status==='completed'?('Recorded violations: '+(s.safety_violations??'—')+' · Trace integrity: '+Boolean(s.trace_integrity)+' · Source: deterministic toy-world'):(r.error||'Not completed'));
    el('download-run').disabled=r.status!=='completed';
    if(r.status==='completed'){
      const blob=await api(projectPath()+'/runs/'+id+'/bundle',{download:true});
      const json=JSON.parse(await blob.text());
      state.trace=(json.events||[]).filter(e=>e.kind==='state').map(e=>({x:e.payload.x,y:e.payload.y}));
      const scenario=json.manifest?.scenario?.id;
      if(scenario&&el('scenario-select').value!==scenario){el('scenario-select').value=scenario;await loadScene();state.trace=(json.events||[]).filter(e=>e.kind==='state').map(e=>({x:e.payload.x,y:e.payload.y}));}
      el('scrub').value=100;
      draw();
    }
  }catch(err){msg(err.message);}
}
async function downloadBlob(path,filename){
  const blob=await api(path,{download:true});const url=URL.createObjectURL(blob);
  const a=document.createElement('a');a.href=url;a.download=filename;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),2500);
}
async function downloadRun(){if(state.currentRun)await downloadBlob(projectPath()+'/runs/'+state.currentRun+'/bundle','veap-'+state.currentRun.slice(0,8)+'.json');}
async function downloadEvidence(e){try{await downloadBlob(projectPath()+'/evidence/'+e.id+'/download',e.filename);}catch(err){msg(err.message);}}
async function createProject(){
  const name=prompt('Project name (2–100 characters)');if(!name)return;
  const description=prompt('Project purpose (optional)')||'';
  try{const created=await api(base()+'/projects',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name,description})});
    await loadTenant();el('project-select').value=created.id;state.project=created.id;await loadProject();msg('Project created.');
  }catch(err){msg(err.message);}
}
async function uploadEvidence(){
  const file=el('evidence-file').files[0];if(!file){msg('Choose a JSONL, JSON, or MCAP file.');return;}
  if(!state.project){msg('Select a project first.');return;}
  const ext=file.name.split('.').pop().toLowerCase();if(!['json','jsonl','mcap'].includes(ext)){msg('Unsupported evidence format.');return;}
  try{
    const record=await api(projectPath()+'/evidence?filename='+encodeURIComponent(file.name)+'&format='+ext,
      {method:'POST',headers:{'Content-Type':'application/octet-stream'},body:file});
    await loadProject();msg('Evidence imported as '+record.provenance+'; checksum recorded.');
  }catch(err){msg('Evidence rejected: '+err.message);}
}
async function loadReviews(){
  const id=el('review-run').value||state.currentRun;if(!id){text('reviews-list','No completed experiment.');return;}
  const reviews=await api(projectPath()+'/runs/'+id+'/reviews').catch(()=>[]);
  const container=el('reviews-list');container.replaceChildren();
  for(const r of reviews){const div=document.createElement('div');div.textContent=r.verdict.toUpperCase()+' · '+r.rationale+' · reviewer '+r.reviewer_id.slice(0,8);container.append(div);}
  if(!reviews.length)container.textContent='No reviews submitted for this run.';
}
async function submitReview(){
  const id=el('review-run').value;if(!id){msg('Choose a completed run.');return;}
  const body={verdict:el('review-decision').value,rationale:el('review-notes').value};
  try{await api(projectPath()+'/runs/'+id+'/reviews',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    el('review-notes').value='';await loadReviews();msg('Human review recorded in the tenant audit log.');
  }catch(err){msg('Review not accepted: '+err.message);}
}
async function loadAudit(){
  const body=el('audit-table');body.replaceChildren();if(!state.tenant)return;
  try{
    const events=await api(base()+'/audit');
    for(const e of events){const row=document.createElement('tr');for(const val of [e.id,e.action,e.actor_id.slice(0,12),e.object_id.slice(0,14),e.event_sha256.slice(0,14)+'…'])cell(row,val);body.append(row);}
    if(!events.length)body.textContent='No audit events';
  }catch(err){text('audit-status','Restricted to owner/auditor roles: '+err.message);}
}
async function verifyAudit(){try{const result=await api(base()+'/audit/verify');text('audit-status',(result.chain_consistent?'CONSISTENT':'DISCREPANCY')+' · '+result.events_checked+' events · NOT authenticity proof');}catch(err){msg(err.message);}}
async function loadEngines(){
  try{
    const info=await api('/engines');const grid=el('engine-grid');grid.replaceChildren();
    for(const [name,data] of Object.entries(info.engines)){
      const card=document.createElement('div');card.className='engine-card';
      const title=document.createElement('h3');title.textContent=name.toUpperCase();
      const status=document.createElement('small');status.textContent=data.available?'DETECTED · NOT VALIDATED':'NOT INSTALLED';if(!data.available)status.className='pending';
      const p=document.createElement('p');p.textContent=data.interface+' · '+data.execution;
      card.append(title,status,p);grid.append(card);
    }
    const assets=el('asset-links');assets.replaceChildren();
    if(state.tenant&&el('scenario-select').value){
      for(const ext of ['usda','xml','sdf','urdf','glb','scene.json']){
        const btn=document.createElement('button');btn.textContent='↓ '+ext.toUpperCase();btn.onclick=()=>downloadBlob(base()+'/scenarios/'+el('scenario-select').value+'/assets/'+ext,el('scenario-select').value+'.'+ext).catch(err=>msg(err.message));assets.append(btn);
      }
    }
  }catch(err){msg(err.message);}
}

// Isometric geometry preview of the 2D toy-world; NOT Isaac Sim/Unreal rendering.
let drawWidth=0,drawHeight=0;
function draw(){
  const canvas=el('world');if(!canvas)return;
  const dpr=Math.min(devicePixelRatio||1,2);const w=canvas.clientWidth||600,h=canvas.clientHeight||360;
  if(!w||!h)return;
  canvas.width=Math.floor(w*dpr);canvas.height=Math.floor(h*dpr);
  const g=canvas.getContext('2d');g.setTransform(dpr,0,0,dpr,0,0);g.clearRect(0,0,w,h);
  const scene=state.scene;
  if(!scene){g.fillStyle='#8aadb9';g.font='13px system-ui';g.fillText('Select an organisation and scenario to load the scene.',28,h/2);return;}
  const [maxx,maxy]=scene.bounds_m;
  const k=Math.min((w-100)/((maxx+maxy)*.88),(h-90)/((maxx+maxy)*.45));
  const origin={x:w/2,y:h*.49};
  const proj=(x,y,z=0)=>({x:origin.x+(x-y)*k*.86,y:origin.y+(x+y-(maxx+maxy)/2)*k*.42-z*k*.72});
  const polygon=(points,fill,stroke)=>{g.beginPath();g.moveTo(points[0].x,points[0].y);for(const p of points.slice(1))g.lineTo(p.x,p.y);g.closePath();g.fillStyle=fill;g.fill();if(stroke){g.strokeStyle=stroke;g.lineWidth=1;g.stroke();}};
  const tile=[proj(0,0),proj(maxx,0),proj(maxx,maxy),proj(0,maxy)];polygon(tile,'#142c36','#37616b');
  for(let x=0;x<=maxx;x+=1){const a=proj(x,0),b=proj(x,maxy);g.beginPath();g.moveTo(a.x,a.y);g.lineTo(b.x,b.y);g.strokeStyle='#27414a';g.stroke();}
  for(let y=0;y<=maxy;y+=1){const a=proj(0,y),b=proj(maxx,y);g.beginPath();g.moveTo(a.x,a.y);g.lineTo(b.x,b.y);g.strokeStyle='#27414a';g.stroke();}
  const boxes=scene.objects.filter(o=>o.role==='obstacle'||o.role==='boundary'||o.role==='forbidden'||o.role==='waypoint');
  boxes.sort((a,b)=>(a.position_m[0]+a.position_m[1])-(b.position_m[0]+b.position_m[1]));
  for(const o of boxes){
    let sx=o.shape==='box'?o.size_m[0]:(o.size_m[0]*2),sy=o.shape==='box'?o.size_m[1]:(o.size_m[0]*2),sz=o.shape==='box'?o.size_m[2]:o.size_m[1];
    const [cx,cy,cz]=o.position_m;const x0=cx-sx/2,x1=cx+sx/2,y0=cy-sy/2,y1=cy+sy/2;
    const z0=cz-sz/2,z1=cz+sz/2;
    const bottom=[proj(x0,y0,z0),proj(x1,y0,z0),proj(x1,y1,z0),proj(x0,y1,z0)];
    const top=[proj(x0,y0,z1),proj(x1,y0,z1),proj(x1,y1,z1),proj(x0,y1,z1)];
    const colors=o.role==='forbidden'?['#5b2c40a6','#e25e78b0','#aa4058a8']:o.role==='waypoint'?['#16897b','#56e5c4','#248f80']:o.role==='boundary'?['#284859aa','#3a5c69bb','#284350aa']:['#99603a','#d39a53','#7e5038'];
    polygon([bottom[1],bottom[2],top[2],top[1]],colors[0]);polygon([bottom[2],bottom[3],top[3],top[2]],colors[2]);polygon(top,colors[1]);
  }
  const num=Math.max(0,Math.min(state.trace.length-1,Math.round((Number(el('scrub').value)/100)*(state.trace.length-1))));
  if(state.trace.length){
    g.beginPath();state.trace.slice(0,num+1).forEach((p,i)=>{const q=proj(p.x,p.y,.18);if(!i)g.moveTo(q.x,q.y);else g.lineTo(q.x,q.y);});
    g.lineWidth=2.8;g.strokeStyle='#8ef8d1';g.shadowColor='#8ef8d1';g.shadowBlur=11;g.stroke();g.shadowBlur=0;
  }
  const robot=state.trace[num]||{x:scene.robot.initial_pose_xyz_m[0],y:scene.robot.initial_pose_xyz_m[1]};
  const p=proj(robot.x,robot.y,.32);g.beginPath();g.ellipse(p.x,p.y,9,6,0,0,Math.PI*2);g.fillStyle='#b7ffec';g.shadowColor='#67f5d6';g.shadowBlur=20;g.fill();g.shadowBlur=0;
  text('trace-tick','FRAME '+(num+1)+'/'+Math.max(state.trace.length,1));
}
function playPause(){
  if(state.playHandle){clearInterval(state.playHandle);state.playHandle=null;text('play','▶ Play trace');return;}
  if(!state.trace.length){msg('Select a completed run with trajectory states.');return;}
  if(Number(el('scrub').value)>=100)el('scrub').value=0;
  text('play','Ⅱ Pause');state.playHandle=setInterval(()=>{el('scrub').value=Number(el('scrub').value)+2;
    draw();if(Number(el('scrub').value)>=100)playPause();},90);
}
function events(){
  document.querySelectorAll('.nav-link').forEach(btn=>btn.addEventListener('click',()=>selectPage(btn.dataset.view)));
  el('connect').onclick=connect;el('token-input').addEventListener('keydown',e=>{if(e.key==='Enter')connect();});
  el('disconnect').onclick=disconnect;
  el('tenant-select').onchange=async(e)=>{state.tenant=e.target.value;await loadTenant();};
  el('project-select').onchange=async(e)=>{state.project=e.target.value;state.currentRun=null;await loadProject();};
  el('scenario-select').onchange=loadScene;el('refresh').onclick=loadProject;el('new-project').onclick=createProject;
  el('execute').onclick=startRun;el('download-run').onclick=()=>downloadRun().catch(err=>msg(err.message));
  el('play').onclick=playPause;el('scrub').oninput=draw;el('upload-evidence').onclick=uploadEvidence;
  el('review-run').onchange=loadReviews;el('submit-review').onclick=submitReview;
  el('verify-audit').onclick=verifyAudit;
  new ResizeObserver(draw).observe(el('world'));
  fetch('/api/studio/health').then(r=>r.json()).then(r=>text('service-status','● '+r.mode.toUpperCase())).catch(()=>text('service-status','● OFFLINE'));
}
events();draw();

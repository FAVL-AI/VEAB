/* VEAP Foundry Studio R0.3 — original user interface, local-only research pilot.
   All camera/depth/scene renderings in demo mode are synthetic illustrations.
   Uploading MCAP does not prove source authenticity or enable ROS command authority. */
(()=>{
'use strict';
const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
const readToken=()=>{try{return sessionStorage.getItem('veap-token')||''}catch{return ''}};
const st={assets:[], current:null,rows:[],report:null,idx:0,playing:false,speed:1,lastTime:0,angle:-.72,zoom:1.00,pointcloud:true,bounds:true,view:'replay',inspect:'events',reportExport:null,modal:false,modelVerts:null,worldPoints:null,mediaAsset:null,token:readToken()};
const esc=s=>String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
const num=(n,d=2)=>n!==null&&n!==undefined&&n!==''&&Number.isFinite(Number(n))?Number(n).toFixed(d):'—';
let toastHandle=null, mediaBlobUrl=null, currentDetailAsset=null;
function toast(text,bad=false){const t=$('#toast');t.textContent=text;t.style.borderColor=bad?'#ae5c5c':'#668d43';t.classList.add('show');clearTimeout(toastHandle);toastHandle=setTimeout(()=>t.classList.remove('show'),4500)}
async function api(path,options={}){let headers={'x-veap-token':st.token,...(options.headers||{})};let r=await fetch(path,{...options,headers});if(r.status===401){let value=prompt('Enter local VEAP_STUDIO_TOKEN configured on the server:');if(value){st.token=value;try{sessionStorage.setItem('veap-token',value)}catch{};return api(path,options)}}if(!r.ok){let j=await r.json().catch(()=>({detail:r.statusText}));throw Error(typeof j.detail==='string'?j.detail:'Request failed '+r.status)}return r.json()}
function openPage(name){st.view=name;$$('.page').forEach(p=>p.classList.toggle('active',p.id==='page'+name[0].toUpperCase()+name.slice(1)));$$('.railbutton[data-page]').forEach(b=>b.classList.toggle('active',b.dataset.page===name));let titles={replay:'Replay Operations',world:'World Studio',data:'Evidence Registry',policy:'Policy Lab',assurance:'Assurance',connectors:'Runtime Workbench'};$('#crumbPage').textContent=titles[name]||name;if(name==='world'){renderWorld();requestAnimationFrame(()=>drawScene('#worldCanvas'))}if(name==='data'){renderRegistry();loadInbox()};if(name==='assurance'){populateSelects();renderAssuranceCards();loadContracts()}if(name==='connectors')renderConnectors();if(name==='replay')requestAnimationFrame(renderAll)}
function setSide(name){$$('[data-side]').forEach(b=>b.classList.toggle('selected',b.dataset.side===name));$$('.side-content').forEach(n=>n.classList.add('hidden'));$('#side'+name[0].toUpperCase()+name.slice(1)).classList.remove('hidden')}
function badge(a){if(a.origin==='DEMO_SYNTHETIC')return '<span class="badge-lite">SYNTHETIC</span>';if(a.origin==='DERIVED_SYNTHETIC_FAULT')return '<span class="badge-lite">DERIVED</span>';return '<span class="badge-lite">UNATTESTED</span>'}
function assetLabel(a){return a.name.replace(/\.jsonl$/,'').replace(/\.csv$/,'')}
function assetList(){return st.assets.filter(x=>x.kind==='TRAJECTORY')}
async function refreshAssets(preferId){let j=await api('/api/assets');st.assets=j.assets;$('#sourceCount').textContent=st.assets.length;renderSources();renderRegistry();populateSelects();renderMediaOptions();if(preferId)await selectRun(preferId);else if(!st.current){const initial=assetList().find(a=>a.name.startsWith('M3 · Yard'))||assetList()[0];if(initial)await selectRun(initial.id)}}
function renderSources(){const match=$('#sideSearch').value.toLowerCase();const items=st.assets.filter(a=>!match||[a.name,a.kind,a.origin].join(' ').toLowerCase().includes(match));$('#sourceItems').innerHTML=items.map(a=>`<div class="source-item ${a.id===st.current?.id?'active':''}" data-source="${a.id}" role="button" tabindex="0"><div class="source-symbol">${a.kind==='TRAJECTORY'?'↝':a.kind==='VIDEO'?'▣':a.kind==='MCAP'?'◉':'◇'}</div><div><span>${esc(assetLabel(a))}</span><small>${esc(a.kind)} · ${a.origin==='DEMO_SYNTHETIC'?'Synthetic demonstration':'Unattested upload'}</small></div></div>`).join('')||'<p class="small-note">No matching evidence. Import a file.</p>';$$('[data-source]').forEach(n=>{n.onclick=()=>openAsset(n.dataset.source);n.onkeydown=e=>{if(e.key==='Enter')openAsset(n.dataset.source)}})}
function openAsset(id){let a=st.assets.find(x=>x.id===id);if(!a)return;
if(a.kind==='TRAJECTORY'){selectRun(id).then(()=>openPage('replay')).catch(e=>toast(e.message,true));return}
if(['MODEL_3D','CAD','ROBOT_DESCRIPTION','POINT_CLOUD'].includes(a.kind)){openPage('world');$('#geometrySelect').value=a.id;inspectGeometry();return}
if(['VIDEO','IMAGE'].includes(a.kind)){openPage('replay');$('#cameraSource').value=id;pickCameraMedia(id);toast('Media preview: recorded clock alignment has not been established.');return}
showAssetDetails(a)}
async function showAssetDetails(a){currentDetailAsset=a;$('#assetModalTitle').textContent=a.name;$('#assetTags').value=(a.meta.tags||[]).join(', ');$('#assetNote').value=a.note||'';$('#assetDetail').textContent=JSON.stringify({kind:a.kind,sha256:a.sha256,bytes:a.size,source:a.origin,provenance:a.meta.provenance,metadata:a.meta},null,2);$('#assetOverlay').classList.remove('hidden');
if(a.kind==='LOG'){try{let j=await api('/api/assets/'+a.id+'/text-preview');$('#assetDetail').textContent=j.text+(j.truncated?'\n[Preview truncated at 128 KB]':'')}catch(e){toast(e.message,true)}}}
function closeAssetDetails(){currentDetailAsset=null;$('#assetOverlay').classList.add('hidden')}
async function saveAssetDetails(){if(!currentDetailAsset)return;let tags=$('#assetTags').value.split(',').map(x=>x.trim()).filter(Boolean);try{let j=await api('/api/assets/'+currentDetailAsset.id,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({tags,note:$('#assetNote').value})});closeAssetDetails();await refreshAssets();toast('Local tags and notes updated; source bytes unchanged.')}catch(e){toast(e.message,true)}}
async function selectRun(id){let j=await api('/api/traces/'+id);st.current=j.asset;st.rows=j.rows;st.report=j.report;st.idx=0;st.playing=false;$('#playBtn').textContent='▶';updateHeader();renderSources();populateSelects();renderAll();await doCompare(false)}
function updateHeader(){let a=st.current,s=st.report;if(!a||!s)return;$('#runSubtitle').textContent=`${assetLabel(a)} • ${a.origin==='DEMO_SYNTHETIC'?'SYNTHETIC SOURCE':'UNATTESTED SOURCE'} • ${s.duration_s}s • ${s.samples} samples`;$('#statTask').textContent=s.task_complete===null?'NOT SCORED':(s.task_complete?'COMPLETE':'INCOMPLETE');$('#statTask').className=s.task_complete===null?'orange-text':(s.task_complete?'green-text':'orange-text');$('#statVerdict').textContent=s.process_accepted===null?'NO CONTRACT':(s.process_accepted?'ACCEPTED':'REVIEW');$('#statVerdict').className=s.process_accepted===null?'orange-text':(s.process_accepted?'green-text':'red-text');$('#statViolations').textContent=s.violations===null?'N/A':s.violations;$('#statViolations').className=s.violations===null?'orange-text':(s.violations?'red-text':'green-text');$('#statSamples').textContent=s.samples.toLocaleString();$('#contractVerdict').textContent=s.verdict;$('#sourceDigest').textContent=a.sha256;renderAssuranceCards();$('#eventCount').textContent=`${s.events.length} recorded events`;$('#timelineDuration').textContent=`${num(s.duration_s,1)} sec`;$('#scrub').max=Math.max(0,st.rows.length-1);$('#scrub').value=0;$('#worldMode').textContent=(a.name.includes('G1')?'G1 · FACILITY':'M3 · WAREHOUSE');let evts=s.events.length?s.events.slice(0,120):[{kind:'NO CONTRACT EVENTS',t_ns:st.rows[0].t_ns,index:0,severity:'info'}];$('#eventList').innerHTML=evts.map(e=>`<div class="event-card ${esc(e.severity)}" data-idx="${Number(e.index)}"><div class="event-title"><span class="evt-icon">${e.severity==='critical'?'!':e.severity==='warn'?'△':'•'}</span>${esc(e.kind)}<span class="event-time">${num((e.t_ns-st.rows[0].t_ns)/1e9,2)}s</span></div><div class="event-sub">${e.severity==='critical'?'Constraint breached under selected example':e.severity==='warn'?'Evidence-quality warning':'Trace event'} · sample ${e.index}</div></div>`).join('');$$('[data-idx]').forEach(e=>e.onclick=()=>seek(Number(e.dataset.idx)));drawEventTrack();}
function populateSelects(){let options=assetList().map(a=>`<option value="${a.id}">${esc(assetLabel(a))}</option>`).join('');['#compareSelect','#faultSource','#assuranceSource','#assuranceCompare'].forEach(selector=>{let s=$(selector);let old=s.value;s.innerHTML=(selector==='#assuranceCompare'?'<option value="">No reference</option>':'')+options;if([...s.options].some(x=>x.value===old))s.value=old;else if(st.current){if(selector==='#assuranceSource'||selector==='#faultSource')s.value=st.current.id;else if(selector==='#compareSelect'||selector==='#assuranceCompare'){let ref=assetList().find(x=>x.id!==st.current.id);if(ref)s.value=ref.id}}})}
async function doCompare(notify=true){if(!st.current||!$('#compareSelect').value)return;try{let c=await api('/api/compare',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({reference_id:st.current.id,candidate_id:$('#compareSelect').value})});$('#compareRmse').textContent=num(c.rmse_m,3)+' m';$('#compareMax').textContent=num(c.max_error_m,3)+' m';$('#compareRef').textContent=c.alignment==='ELAPSED_TIME_ONLY'?'ELAPSED':'—';$('#compareSummary').title='Uncalibrated discrepancy; not independent physics validation';if(notify)toast('Cross-trace discrepancy computed; calibration and ground truth not established.')}catch(e){$('#compareRmse').textContent='—';if(notify)toast(e.message,true)}}
function seek(i){if(!st.rows.length)return;st.idx=Math.max(0,Math.min(st.rows.length-1,Math.round(i)));$('#scrub').value=st.idx;renderAll()}
function frameSeconds(i){return st.rows.length?(st.rows[i].t_ns-st.rows[0].t_ns)/1e9:0}
function fmtTime(sec){let m=Math.floor(sec/60),s=Math.floor(sec%60),ms=Math.floor((sec%1)*1000);return `${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}.${String(ms).padStart(3,'0')}`}
function tickVisual(){let n=st.rows.length;if(!n)return;let r=st.rows[st.idx];$('#worldFrame').textContent=`t = ${num(frameSeconds(st.idx),2)} s`;$('#timelineClock').textContent=`${fmtTime(frameSeconds(st.idx))} / ${fmtTime(frameSeconds(n-1))}`;$('#frameText').textContent=`${String(st.idx).padStart(3,'0')} / ${n-1}`;['#cursor1','#cursor2','#cursor3'].forEach(s=>$(s).style.left=`${st.idx/Math.max(1,n-1)*100}%`);$('#scrub').value=st.idx}
const rand=(seed)=>{let x=Math.sin(seed*127.1)*43758.5453;return x-Math.floor(x)};
function ctx2(id){let cv=$(id),rect=cv.getBoundingClientRect();if(rect.width<1||rect.height<1)return null;let dpr=Math.min(2,window.devicePixelRatio||1);let w=Math.max(1,Math.round(rect.width*dpr)),h=Math.max(1,Math.round(rect.height*dpr));if(cv.width!==w||cv.height!==h){cv.width=w;cv.height=h}let c=cv.getContext('2d');c.setTransform(dpr,0,0,dpr,0,0);return {c,w:rect.width,h:rect.height}}
function poly(ctx,pts,fill,stroke,width=1){ctx.beginPath();ctx.moveTo(pts[0][0],pts[0][1]);for(const [x,y] of pts.slice(1))ctx.lineTo(x,y);ctx.closePath();if(fill){ctx.fillStyle=fill;ctx.fill()}if(stroke){ctx.strokeStyle=stroke;ctx.lineWidth=width;ctx.stroke()}}
function drawScene(selector='#sceneCanvas'){let obj=ctx2(selector);if(!obj||!st.rows.length)return;let {c,w,h}=obj;let g=c.createRadialGradient(w*.5,h*.3,5,w*.5,h*.5,Math.max(w,h)*.75);g.addColorStop(0,'#243a40');g.addColorStop(.55,'#12242c');g.addColorStop(1,'#09151b');c.fillStyle=g;c.fillRect(0,0,w,h);let scale=Math.min(w/18,h/10)*st.zoom;let angle=st.angle;
const p=(x,y,z=0)=>{let xx=x-6,yy=y-4.7;let X=xx*Math.cos(angle)-yy*Math.sin(angle);let Y=xx*Math.sin(angle)+yy*Math.cos(angle);return [w*.48+X*scale,h*.60+Y*scale*.58-z*scale*1.05]};
let ground=[p(0,0),p(12,0),p(12,9.4),p(0,9.4)];poly(c,ground,'#14252a','#52646b',1.5);
for(let x=0;x<=12;x+=.5){let a=p(x,0),b=p(x,9.4);c.beginPath();c.moveTo(...a);c.lineTo(...b);c.strokeStyle=(x%2===0)?'#3b575c6a':'#30505936';c.lineWidth=.8;c.stroke()}
for(let y=0;y<=9.4;y+=.5){let a=p(0,y),b=p(12,y);c.beginPath();c.moveTo(...a);c.lineTo(...b);c.strokeStyle=(y%2===0)?'#3b575c6a':'#30505936';c.stroke()}
function box(x,y,z,dx,dy,dz,col='#31515a',rim='#5e8791'){let top=[p(x,y,z+dz),p(x+dx,y,z+dz),p(x+dx,y+dy,z+dz),p(x,y+dy,z+dz)];poly(c,[p(x,y,z),p(x+dx,y,z),top[1],top[0]],'#1b343d',rim,0.6);poly(c,[p(x+dx,y,z),p(x+dx,y+dy,z),top[2],top[1]],'#173138',rim,.6);poly(c,[p(x,y+dy,z),p(x+dx,y+dy,z),top[2],top[3]],'#203c44',rim,.6);poly(c,top,col,rim,.9)}
let obstacles=[[1.3,2.4,1.6,.52,1.25],[7.3,6.8,2.2,.65,1.32],[8.8,3.2,1.25,.8,1.5],[2.8,7.1,2.0,.55,1.7]];
obstacles.forEach(([x,y,dx,dy,dz],j)=>{box(x,y,0,dx,dy,dz,j===0?'#375a62':'#304953','#6f9fab');for(let k=0;k<3;k++){let a=p(x+.1,y+.12,.35+k*.35),b=p(x+dx-.1,y+.12,.35+k*.35);c.strokeStyle='#89acbb58';c.beginPath();c.moveTo(...a);c.lineTo(...b);c.stroke()}});
// sensor point cloud, intentionally synthetic points and not a recovered real map
if(st.pointcloud){for(let k=0;k<650;k++){let x=rand(k+5)*12,y=rand(k*9+12)*9.4;if(rand(k+23)>.44)continue;let [cx,cy]=p(x,y,rand(k+777)*.22);c.fillStyle=k%9===0?'#a1d8bb93':'#76baba55';c.fillRect(cx,cy,1.2,1.2)}}
// Imported point-cloud source: user-provided metric coordinates; registration is unknown.
if(st.worldPoints?.length){let skip=Math.max(1,Math.floor(st.worldPoints.length/2700));for(let i=0;i<st.worldPoints.length;i+=skip){let [x,y,z]=st.worldPoints[i];let [cx,cy]=p(x,y,z);c.fillStyle='#c0f078ae';c.fillRect(cx,cy,2.0,2.0)}}
// Mesh vertices are normalized solely for display; no physics/collision semantics assumed.
if(st.modelVerts?.length){for(let i=0;i<st.modelVerts.length;i++){let [x,y,z]=st.modelVerts[i],pos=p(x,y,z);c.fillStyle='#ffca79b2';c.fillRect(pos[0],pos[1],1.4,1.4)}}
if(st.bounds){let z={x1:3.75,x2:5.65,y1:2.3,y2:4.55};let bounds=[p(z.x1,z.y1,.05),p(z.x2,z.y1,.05),p(z.x2,z.y2,.05),p(z.x1,z.y2,.05)];poly(c,bounds,'#bd645a30','#e68c6c',1.3);c.save();c.setLineDash([4,4]);poly(c,bounds,null,'#ec9a779c',1);c.restore();let [lx,ly]=p(z.x1,z.y2,.07);c.font='700 9px ui-monospace,monospace';c.fillStyle='#f3a18d';c.fillText('KEEP-OUT A',lx,ly-12)}
let prefix=st.rows.slice(0,st.idx+1);const drawLine=(data,col,width=2.4,dash=[])=>{if(!data.length)return;c.beginPath();data.forEach((r,i)=>{let v=p(r.x_m,r.y_m,.16);if(i===0)c.moveTo(...v);else c.lineTo(...v)});c.setLineDash(dash);c.strokeStyle=col;c.lineWidth=width;c.lineJoin='round';c.lineCap='round';c.stroke();c.setLineDash([])};
drawLine(st.rows,'#5adfe34c',2,[3,5]);drawLine(prefix,st.report?.process_accepted?'#99e344':'#ffb264',3.2);
// floor goal marker
let [gx,gy]=p(10.5,7.2,.1);c.beginPath();c.arc(gx,gy,9,0,Math.PI*2);c.strokeStyle='#a8eb45';c.lineWidth=2;c.stroke();c.fillStyle='#a2dd63';c.font='700 9px monospace';c.fillText('GOAL',gx+14,gy-3);
let r=st.rows[st.idx];let a=p(r.x_m,r.y_m,0),u=p(r.x_m,r.y_m,.38);let robotG1=st.current?.name.includes('G1');if(robotG1){box(r.x_m-.15,r.y_m-.13,0,.3,.27,.78,'#b0c4cb','#d5eaf0');let head=p(r.x_m,r.y_m,1.0);c.beginPath();c.arc(...head,5,0,2*Math.PI);c.fillStyle='#cfe8e1';c.fill();c.strokeStyle='#79e8c8';c.stroke()}else{box(r.x_m-.27,r.y_m-.24,0,.54,.48,.24,'#a8c0c6','#cbf0e7');let cam=p(r.x_m+.13,r.y_m+.04,.41);c.beginPath();c.arc(...cam,3,0,2*Math.PI);c.fillStyle='#9ef1da';c.fill()}
let rr=4+3*Math.sin(performance.now()/600);c.beginPath();c.ellipse(a[0],a[1],rr*2,rr,0,0,Math.PI*2);c.strokeStyle='#7deab277';c.stroke();if(st.pointcloud){for(let k=0;k<35;k++){let ang=k/35*Math.PI*2;let pt=p(r.x_m+1.6*Math.cos(ang),r.y_m+1.6*Math.sin(ang),.03);c.fillStyle='#7dd6c69c';c.fillRect(pt[0],pt[1],1.2,1.2)}}
let pt=p(r.x_m,r.y_m,.9);c.fillStyle='#d9f6e9';c.font='700 10px monospace';c.fillText(robotG1?'G1 / SURROGATE':'M3 PRO / SURROGATE',pt[0]+10,pt[1]-8);
c.strokeStyle='#344f5788';c.beginPath();c.moveTo(...p(0,0));c.lineTo(...p(0,9.4));c.moveTo(...p(12,0));c.lineTo(...p(12,9.4));c.stroke();
}
function drawCamera(id,index){let cv=ctx2(id);if(!cv)return;let {c,w,h}=cv;let r=st.rows[st.idx]||{x_m:0,y_m:0},s=index-1, horizon=h*.40;let bg=c.createLinearGradient(0,0,0,h);bg.addColorStop(0,'#273c49');bg.addColorStop(.4,'#44616a');bg.addColorStop(.41,'#2a3e44');bg.addColorStop(1,'#192f37');c.fillStyle=bg;c.fillRect(0,0,w,h);
// artificial warehouse camera reference
c.fillStyle='#31434b';poly(c,[[0,h],[w,h],[w*.68,horizon],[w*.31,horizon]],'#31434b');
for(let k=0;k<7;k++){let off=1/(k+1);let y=horizon+(h-horizon)*(1-off);c.strokeStyle='#97b1a42c';c.lineWidth=1;c.beginPath();c.moveTo(0,y);c.lineTo(w,y);c.stroke()}
for(let side of [-1,1]){for(let j=0;j<3;j++){let depth=j/3,factor=1-depth*.6,fw=24*factor,fh=(h*.53)*factor;let x=(side<0?0:w)-side*(10+j*11)*factor+(side<0?0:-fw),y=horizon+(j*.16*h);c.fillStyle=side===-1?'#3f5862':'#435965';c.fillRect(x,y,fw,fh);c.strokeStyle='#7e9e9b5e';c.strokeRect(x,y,fw,fh);for(let a=1;a<=3;a++){c.strokeStyle='#9caeaf33';c.beginPath();c.moveTo(x,y+a*fh/4);c.lineTo(x+fw,y+a*fh/4);c.stroke()}}}
let dx=(r.x_m/12-.5)*w*.18+s*w*.03,center=w*.52+dx;poly(c,[[center-16,h*.83],[center+16,h*.83],[center+10,h*.59],[center-10,h*.59]],'#7a9383','#aad6c0',1);
c.strokeStyle='#93eb9e';c.setLineDash([4,3]);c.lineWidth=1.5;c.strokeRect(center-22,h*.52,44,h*.35);c.setLineDash([]);
for(let x=0;x<w;x+=9){c.fillStyle='#84bab60c';c.fillRect(x,0,1,h)}c.fillStyle='#061015a1';c.fillRect(0,h-17,w,17);c.fillStyle='#b6d6d3';c.font='8px monospace';c.fillText('RGB 640×480 • SYNTHETIC',8,h-6);c.fillStyle='#8dea98';c.fillText(num(frameSeconds(st.idx),2)+'s',w-45,h-6)}
function drawSignals(){let o=ctx2('#signalCanvas');if(!o||!st.rows.length)return;let {c,w,h}=o;c.fillStyle='#111a20';c.fillRect(0,0,w,h);for(let k=0;k<5;k++){let y=9+k*(h-18)/4;c.beginPath();c.moveTo(0,y);c.lineTo(w,y);c.strokeStyle='#283e467f';c.lineWidth=.8;c.stroke()}let series=[['speed_m_s','#99d83f',1.5],['clearance_m','#6aa9df',1.1],['latency_ms','#e5a15b',50]];for(let [key,col,max] of series){c.beginPath();st.rows.forEach((r,i)=>{let x=8+(w-16)*i/Math.max(1,st.rows.length-1),y=h-10-(Math.min(max,r[key]??0)/max)*(h-22);if(!i)c.moveTo(x,y);else c.lineTo(x,y)});c.lineWidth=1.8;c.strokeStyle=col;c.stroke()}let x=8+(w-16)*st.idx/Math.max(1,st.rows.length-1);c.beginPath();c.moveTo(x,0);c.lineTo(x,h);c.strokeStyle='#e8efed';c.lineWidth=1;c.stroke()}
function drawEventTrack(){let el=$('#eventTrack');if(!st.report)return;let n=st.rows.length||1;el.innerHTML=st.report.events.filter(e=>e.severity==='critical').map(e=>`<i class="track-marker" style="left:${Math.min(99,100*e.index/(n-1))}%"></i>`).join('')}
function renderAll(){if(!st.rows.length)return;tickVisual();drawCamera('#cam1',0);drawCamera('#cam2',1);drawCamera('#cam3',2);drawScene();drawSignals()}
function anim(now){if(st.playing&&st.rows.length){let delta=Math.min(150,Math.max(0,now-st.lastTime||0));let ti=st.rows[st.idx].t_ns+delta*1e6*st.speed;while(st.idx+1<st.rows.length&&st.rows[st.idx+1].t_ns<=ti)st.idx++;if(st.idx>=st.rows.length-1){st.playing=false;$('#playBtn').textContent='▶'}renderAll()}st.lastTime=now;requestAnimationFrame(anim)}
function renderRegistry(){let q=$('#registrySearch').value.toLowerCase();let all=st.assets.filter(a=>!q||[a.name,a.kind,a.sha256,a.origin].join(' ').toLowerCase().includes(q));$('#registryCount').textContent=`${all.length} indexed assets`;$('#registryTable').innerHTML=`<table class="data-table"><thead><tr><th>Asset / Session</th><th>Format</th><th>Evidence class</th><th>Size</th><th>SHA-256</th><th>Action</th></tr></thead><tbody>${all.map(a=>`<tr><td>${esc(a.name)}</td><td>${esc(a.kind)}</td><td>${badge(a)}</td><td>${(a.size/1048576).toFixed(2)} MB</td><td class="mono">${esc(a.sha256.slice(0,14))}…</td><td><button class="mini-btn" data-open="${a.id}">${a.kind==='TRAJECTORY'?'REPLAY':'DETAILS'}</button></td></tr>`).join('')}</tbody></table>`;$$('[data-open]').forEach(n=>n.onclick=()=>openAsset(n.dataset.open))}
function renderWorld(){let models=st.assets.filter(a=>['MODEL_3D','CAD','ROBOT_DESCRIPTION','POINT_CLOUD'].includes(a.kind));$('#geometrySelect').innerHTML=models.map(a=>`<option value="${a.id}">${esc(a.name)}</option>`).join('')||'<option value="">No imported geometry</option>';$('#modelRegistry').innerHTML=models.length?`<table class="data-table"><thead><tr><th>Name</th><th>Type</th><th>Source</th></tr></thead><tbody>${models.map(a=>`<tr><td>${esc(a.name)}</td><td>${esc(a.kind)}</td><td>${esc(a.origin)}</td></tr>`).join('')}</tbody></table>`:'<div class="result-box">No external model imported. Current viewport uses explicitly uncalibrated M3/G1 surrogate geometry.</div>';$('#worldCapabilities').innerHTML=[['First-party USD/MJCF/SDF reference scene','EXPORT IMPLEMENTED'],['URDF / CAD / mesh inspection','FORMAT INSPECTION'],['Native Isaac Lab physics','RUNTIME PROBE IN WORKBENCH'],['Native MuJoCo physics','RUNTIME PROBE IN WORKBENCH'],['CAD fidelity and inertia','NOT CALIBRATED'],['Point cloud registration','NOT YET VALIDATED']].map(([a,b])=>`<div class="cap-row"><span>${a}</span><strong class="pending">${b}</strong></div>`).join('')}
async function inspectGeometry(){let id=$('#geometrySelect').value;if(!id)return toast('Import URDF, mesh or ASCII point cloud before inspection.',true);let a=st.assets.find(x=>x.id===id);if(!a)return;try{let j=await api(a.kind==='POINT_CLOUD'?'/api/reconstruct/'+id:'/api/geometry/'+id);let r=j.reconstruction||j.geometry;$('#geometryReadout').textContent=JSON.stringify({...r,vertices_sampled:undefined,points:undefined,occupancy_cells:undefined},null,2);st.worldPoints=null;st.modelVerts=null;
 if(r.points){let mins=r.bounds_m.min;st.worldPoints=r.points.map(pt=>[pt[0]-mins[0]+.9,pt[1]-mins[1]+.9,pt[2]-mins[2]]);toast('Projected point-cloud samples. Sensor registration and calibration remain unverified.')}
 if(r.vertices_sampled){let v=r.vertices_sampled,b=r.bounds_in_file_units,den=Math.max(...b[1].map((x,i)=>x-b[0][i]),.01);st.modelVerts=v.map(pt=>[(pt[0]-b[0][0])/den*3.4+4.6,(pt[1]-b[0][1])/den*3.4+3.1,(pt[2]-b[0][2])/den*2.8]);toast('Imported mesh vertex preview. Geometry units are unverified.')}
 drawScene('#worldCanvas');}catch(e){toast(e.message,true)}}
function renderAssuranceCards(){let s=st.report,fields=[['CONTRACT STATUS',s?(s.process_accepted===null?'NO CONTRACT':s.process_accepted?'PASS':'REVIEW'):'PENDING','Against recorded trace; not physical validation'],['VIOLATION TIMELINE',s?(s.violations===null?'NOT SCORED':s.violations+' events'):'—','Geometry / timestamp / dropout categories'],['RECOVERY DEADLINE','NOT TESTED','No independent fault-recovery timestamps'],['EVIDENCE COMPLETENESS',s?s.samples+' parsed':'—','Mission interval and sensors not attested'],['FAILURE ATTRIBUTION','HYPOTHESIS ONLY','No causal classification without reference truth'],['COST & LATENCY',s?(s.max_latency_ms===null?'NOT RECORDED':num(s.max_latency_ms,1)+' ms'):'—','Max supplied latency; energy not measured']];$('#assuranceMetrics').innerHTML=fields.map(([k,v,d])=>`<div class="assurance-metric"><span>${k}</span><strong>${esc(v)}</strong><small>${esc(d)}</small></div>`).join('')}
function renderMediaOptions(){let media=st.assets.filter(a=>a.kind==='VIDEO'||a.kind==='IMAGE');let select=$('#cameraSource'),old=select.value;select.innerHTML='<option value="">SYNTHETIC ONLY</option>'+media.map(a=>`<option value="${a.id}">${esc(a.name)}</option>`).join('');if([...select.options].some(o=>o.value===old))select.value=old}
async function pickCameraMedia(id){const el=$('#mediaOverlay');el.replaceChildren();if(mediaBlobUrl){URL.revokeObjectURL(mediaBlobUrl);mediaBlobUrl=null}if(!id){el.classList.add('hidden');return}let a=st.assets.find(x=>x.id===id);if(!a)return;try{let r=await fetch('/api/assets/'+id+'/raw',{headers:{'x-veap-token':st.token}});if(!r.ok)throw Error('Media access failed: '+r.status);mediaBlobUrl=URL.createObjectURL(await r.blob());let media=document.createElement(a.kind==='VIDEO'?'video':'img');media.src=mediaBlobUrl;if(a.kind==='VIDEO'){media.controls=true;media.muted=true;media.preload='metadata'}else media.alt='Uploaded camera/image evidence';el.appendChild(media);let cap=document.createElement('small');cap.textContent='UPLOAD / UNSYNCHRONIZED / UNATTESTED';el.appendChild(cap);el.classList.remove('hidden')}catch(e){toast(e.message,true)}}
async function loadInbox(){
 let el=$('#inboxResults');el.textContent='Scanning VEAP local inbox...';
 try{let v=await api('/api/inbox');
    if(!v.files.length){el.textContent='No local staged files. Place MCAP or CAD files in '+v.root+' using rsync or your file manager.';return}
    el.innerHTML=`<b>Local staging: ${esc(v.root)}</b>`+v.files.map(x=>`<div class="studio-inline" style="margin:7px 0"><span>${esc(x.name)} · ${(x.bytes/1048576).toFixed(1)} MiB</span><button class="mini-btn" data-inbox="${esc(x.name)}">Import source</button></div>`).join('');
    $$('[data-inbox]').forEach(btn=>btn.onclick=async()=>{try{let j=await api('/api/inbox/import',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:btn.dataset.inbox})});toast('Original evidence indexed: '+j.asset.sha256.slice(0,14));await refreshAssets();await loadInbox()}catch(e){toast(e.message,true)}})
 }catch(e){el.textContent='Local inbox discovery failed: '+e.message}
}
let integrationCache=null;
async function renderConnectors(){
  let root=$('#connectorGrid');
  root.innerHTML='<div class="result-box">Probing installed local engine environments…</div>';
  try{
    const [payload,jobs]=await Promise.all([api('/api/integrations'),api('/api/jobs')]);
    integrationCache=payload;
    root.innerHTML=payload.connectors.map(c=>{
      let ready=['AVAILABLE_LOCAL','MODULES_AVAILABLE','ROS_DECODER_AVAILABLE','CLI_FOUND','CONTAINER_READER_AVAILABLE'].includes(c.status);
      let cls=ready?'status-ready':(c.status==='NO_LIVE_LINK'?'status-muted':'status-fail');
      return `<div class="connector"><h3>${esc(c.name)}</h3><p>${esc(c.description)}</p><div class="status ${cls}">● ${esc(c.status.replaceAll('_',' '))}</div><small>${esc(c.claim)}</small>${c.runtime?`<small>${esc(c.runtime)}</small>`:''}</div>`
    }).join('');
    renderNativeJobs(jobs.jobs);
  }catch(e){root.innerHTML=`<div class="result-box">Unable to inspect engine runtime: ${esc(e.message)}</div>`}
  updateSourceOptions();
  $('#recordPlan').textContent=`# VEAP read-only ROS2 recording plan (execute manually after source qualification)\nsource /opt/ros/humble/setup.bash\nexport ROS_DOMAIN_ID=30\nros2 topic list -t\nros2 bag list storage\n# Requires an available ROS2 MCAP plugin and valid sensor graph.\nros2 bag record -s mcap -o veap_m3_session \
  /scan0 /scan1 /odom_raw /imu/data_raw /cmd_vel /tf\n# Not run by the browser. Do not run on the unqualified Jetson.`;
}
function updateSourceOptions(){
  let sels=[['#mcapSource',a=>a.kind==='MCAP','No MCAP files'],['#lerobotSource',a=>a.kind==='TRAJECTORY','No trajectories']];
  for(let [sel,filter,label] of sels){let el=$(sel);if(!el)continue;let old=el.value;let list=st.assets.filter(filter);el.innerHTML=list.map(a=>`<option value="${a.id}">${esc(a.name)} · ${esc(a.origin)}</option>`).join('')||`<option value="">${label}</option>`;if(list.some(a=>a.id===old))el.value=old}
}
function renderNativeJobs(jobs){
  let table=$('#nativeJobTable');if(!table)return;
  if(!jobs.length){table.innerHTML='<div class="result-box">No native jobs yet. Start an engine test or export a reference world.</div>';return}
  table.innerHTML=`<table class="job-table"><thead><tr><th>Job</th><th>Runtime</th><th>State</th><th>Result</th></tr></thead><tbody>`+jobs.map(j=>{
    let state=j.status==='COMPLETED'?'complete':j.status==='FAILED'?'failed':'running';
    let result=j.status==='COMPLETED'?(j.asset_id?'Indexed evidence '+j.asset_id.slice(0,8):'Artifacts available'):(j.error||'Pending');
    let links=j.kind==='scene_export'&&j.status==='COMPLETED'?` <button class="mini-btn" data-job-file="${j.id}:veap_reference.usda">USD</button> <button class="mini-btn" data-job-file="${j.id}:veap_reference.xml">MJCF</button> <button class="mini-btn" data-job-file="${j.id}:veap_reference.sdf">SDF</button> <button class="mini-btn" data-job-file="${j.id}:veap_reference.gltf">glTF</button>`:'';
    return `<tr><td><code>${esc(j.id.slice(0,10))}</code></td><td>${esc(j.kind)}</td><td class="${state}">${esc(j.status)}</td><td>${esc(result)}${links}</td></tr>`
  }).join('')+'</tbody></table>';
  $$('[data-job-file]').forEach(btn=>btn.onclick=async()=>{try{let [id,file]=btn.dataset.jobFile.split(':');let r=await fetch('/api/jobs/'+id+'/artifact/'+file,{headers:{'x-veap-token':st.token}});if(!r.ok)throw Error('File retrieval failed '+r.status);let url=URL.createObjectURL(await r.blob());let a=document.createElement('a');a.href=url;a.download=file;a.click();setTimeout(()=>URL.revokeObjectURL(url),2000)}catch(e){toast(e.message,true)}});
}
async function createNativeJob(kind,source_id=null){
  if(['mcap_decode','lerobot_dataset'].includes(kind)&&!source_id)return toast('Select a source asset first',true);
  try{
    let j=await api('/api/jobs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({kind,source_id})});
    toast('VEAP job queued: '+kind+' — '+j.job.id.slice(0,8));
    await renderConnectors();
  }catch(e){toast('Cannot queue native operation: '+e.message,true)}
}
async function createFault(){if(!$('#faultSource').value)return toast('Import a trajectory first.',true);let request={asset_id:$('#faultSource').value,fault:$('#faultType').value,severity:Number($('#faultSeverity').value),seed:Number($('#faultSeed').value)};try{let r=await api('/api/counterfactual',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(request)});$('#faultResult').textContent=`Generated: ${r.asset.name}\nSource: SYNTHETIC COUNTERFACTUAL\nVerdict: ${r.report.verdict}\nEpisodes: 1 · Seed: ${request.seed}\nInferred physical safety: NOT ESTABLISHED`;await refreshAssets(r.asset.id);openPage('replay');toast('Counterfactual created and indexed. This is an analytic trace perturbation only.')}catch(e){toast(e.message,true)}}
function openModal(){st.modal=true;$('#modalOverlay').classList.remove('hidden');$('#uploadStatus').textContent='Maximum file size 128 MiB. Original input is copied into protected local storage.'}
function closeModal(){st.modal=false;$('#modalOverlay').classList.add('hidden')}
async function doUpload(){let file=$('#fileInput').files[0];if(!file)return toast('Select a file before importing.',true);if(file.size>128*1048576)return toast('File exceeds local 128 MiB limit.',true);let fd=new FormData();fd.append('file',file);fd.append('classification',$('#fileClass').value);$('#uploadStatus').textContent='Validating, hashing and indexing local evidence...';try{let j=await api('/api/assets',{method:'POST',body:fd});closeModal();$('#fileInput').value='';toast(`Imported ${file.name}. Provenance: UNATTESTED.`);await refreshAssets(j.asset.kind==='TRAJECTORY'?j.asset.id:null);if(j.asset.kind!=='TRAJECTORY')openPage('data')}catch(e){$('#uploadStatus').textContent='Import rejected: '+e.message;toast(e.message,true)}}
async function loadContracts(){
 try{let j=await api('/api/contracts');let el=$('#contractSelect');let old=el.value;el.innerHTML='<option value="">No matching contract</option>'+j.contracts.map(c=>`<option value="${c.id}">${esc(c.contract.name)} · ${c.id.slice(0,10)}</option>`).join('');if(j.contracts.some(c=>c.id===old))el.value=old}
 catch(e){toast('Contract list unavailable: '+e.message,true)}
}
async function registerContract(){
 try{let body=JSON.parse($('#contractJson').value);let j=await api('/api/contracts',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});await loadContracts();$('#contractSelect').value=j.id;toast('Immutable contract registered: '+j.id.slice(0,12))}
 catch(e){toast('Contract registration failed: '+e.message,true)}
}
async function evaluateContract(){
 let c=$('#contractSelect').value,a=$('#assuranceSource').value;
 if(!c||!a)return toast('Select registered contract and source trace first.',true);
 try{let result=await api('/api/contracts/'+c+'/evaluate/'+a,{method:'POST'});$('#reportText').textContent=JSON.stringify(result,null,2);st.reportExport={...result,report_id:c.slice(0,12)};$('#downloadJson').disabled=false;
 toast('Separate-process recorded-trace monitor completed. Physical truth remains unverified.')}
 catch(e){toast('External monitor unavailable: '+e.message,true)}
}
async function createAssurance(){if(!$('#assuranceSource').value)return toast('No trajectory selected.',true);try{let src=$('#assuranceSource').value,ref=$('#assuranceCompare').value;let r=await api('/api/reports',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({source_id:src,candidate_id:ref||null})});st.reportExport=r;$('#reportText').textContent=JSON.stringify(r,null,2);$('#downloadJson').disabled=false;toast('Report generated with explicit evidence and limitation fields.')}catch(e){toast(e.message,true)}}
function download(name,value,mime='application/json'){let blob=new Blob([value],{type:mime}),url=URL.createObjectURL(blob);let a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}
function setSidebarCollapsed(collapsed){
  let shell=$('.shell');if(!shell)return;
  shell.classList.toggle('sidebar-collapsed',collapsed);
  let icon=$('#sidebarSliderIcon');if(icon)icon.textContent=collapsed?'›':'‹';
  ['#sidebarCollapseBtn','#sidebarSliderBtn'].forEach(sel=>{let b=$(sel);if(b)b.setAttribute('aria-expanded',String(!collapsed))});
  try{localStorage.setItem('veap-sidebar-collapsed',collapsed?'1':'0')}catch{}
  requestAnimationFrame(()=>{renderAll();if(st.view==='world')drawScene('#worldCanvas')});
  setTimeout(()=>{renderAll();if(st.view==='world')drawScene('#worldCanvas')},240);
}
function toggleSidebar(){
  let shell=$('.shell');if(!shell)return;
  setSidebarCollapsed(!shell.classList.contains('sidebar-collapsed'));
}
function initSidebarSlider(){
  let shell=$('.shell'),slider=$('#sidebarSlider'),btn=$('#sidebarSliderBtn'),collapseBtn=$('#sidebarCollapseBtn');
  if(!shell||!slider)return;
  try{
    let savedW=Number(localStorage.getItem('veap-sidebar-width'));
    if(savedW>=180&&savedW<=440)shell.style.setProperty('--sidebar-w',savedW+'px');
    if(localStorage.getItem('veap-sidebar-collapsed')==='1')setSidebarCollapsed(true);
  }catch{}
  if(collapseBtn)collapseBtn.onclick=()=>toggleSidebar();
  if(btn)btn.onclick=e=>{e.stopPropagation();toggleSidebar()};
  let dragging=false,moved=false,startX=0;
  slider.addEventListener('pointerdown',e=>{
    if(e.target.closest('#sidebarSliderBtn'))return;
    dragging=true;moved=false;startX=e.clientX;
    shell.classList.add('sidebar-dragging');
    slider.setPointerCapture(e.pointerId);
  });
  slider.addEventListener('pointermove',e=>{
    if(!dragging)return;
    if(Math.abs(e.clientX-startX)>3)moved=true;
    let railW=$('.rail')?.getBoundingClientRect().width||51;
    let w=e.clientX-railW;
    if(w<110){
      setSidebarCollapsed(true);
    }else{
      let clamped=Math.max(180,Math.min(440,Math.round(w)));
      shell.style.setProperty('--sidebar-w',clamped+'px');
      if(shell.classList.contains('sidebar-collapsed'))setSidebarCollapsed(false);
      try{localStorage.setItem('veap-sidebar-width',String(clamped))}catch{}
      renderAll();if(st.view==='world')drawScene('#worldCanvas');
    }
  });
  const endDrag=()=>{if(!dragging)return;dragging=false;shell.classList.remove('sidebar-dragging');if(!moved)toggleSidebar();renderAll();if(st.view==='world')drawScene('#worldCanvas')};
  slider.addEventListener('pointerup',endDrag);
  slider.addEventListener('pointercancel',endDrag);
  slider.addEventListener('dblclick',()=>{shell.style.setProperty('--sidebar-w','242px');try{localStorage.removeItem('veap-sidebar-width')}catch{};setSidebarCollapsed(false)});
  $$('.side-section.collapsible').forEach(sec=>{
    sec.onclick=()=>{
      let target=$('#'+sec.dataset.collapse);if(!target)return;
      let expanded=sec.getAttribute('aria-expanded')!=='false';
      sec.setAttribute('aria-expanded',String(!expanded));
      target.classList.toggle('collapsed',expanded);
    };
  });
}
function bind(){
initSidebarSlider();
$$('.railbutton[data-page]').forEach(b=>b.onclick=()=>{if(st.view===b.dataset.page&&$('.shell')?.classList.contains('sidebar-collapsed'))setSidebarCollapsed(false);openPage(b.dataset.page)});$$('[data-side]').forEach(b=>b.onclick=()=>setSide(b.dataset.side));$('#sideSearch').oninput=renderSources;
$$('[data-inspect]').forEach(b=>b.onclick=()=>{$$('[data-inspect]').forEach(x=>x.classList.toggle('active',x===b));$$('.inspector-body').forEach(x=>x.classList.add('hidden'));$('#inspector'+b.dataset.inspect[0].toUpperCase()+b.dataset.inspect.slice(1)).classList.remove('hidden')});
$('#scrub').oninput=e=>{st.playing=false;$('#playBtn').textContent='▶';seek(Number(e.target.value))};$('#playBtn').onclick=()=>{if(st.idx===st.rows.length-1)seek(0);st.playing=!st.playing;$('#playBtn').textContent=st.playing?'❚❚':'▶'};
$('#skipBack').onclick=()=>{st.playing=false;$('#playBtn').textContent='▶';seek(0)};$('#skipForward').onclick=()=>{st.playing=false;$('#playBtn').textContent='▶';seek(st.rows.length-1)};$('#playSpeed').onchange=e=>st.speed=Number(e.target.value);
$('#cameraReset').onclick=()=>{st.angle=-.72;st.zoom=1;drawScene()};$('#togglePoints').onclick=e=>{st.pointcloud=!st.pointcloud;e.currentTarget.classList.toggle('selected',st.pointcloud);drawScene()};$('#toggleBounds').onclick=e=>{st.bounds=!st.bounds;e.currentTarget.classList.toggle('selected',st.bounds);drawScene()};
let canvas=$('#sceneCanvas'),drag=false,prev=0;canvas.addEventListener('pointerdown',e=>{drag=true;prev=e.clientX;canvas.setPointerCapture(e.pointerId)});canvas.addEventListener('pointermove',e=>{if(!drag)return;st.angle+=(e.clientX-prev)*.007;prev=e.clientX;drawScene()});canvas.addEventListener('pointerup',()=>drag=false);canvas.addEventListener('wheel',e=>{e.preventDefault();st.zoom=Math.max(.6,Math.min(2.4,st.zoom*(e.deltaY>0?.92:1.08)));drawScene()},{passive:false});
$('#runCompare').onclick=()=>doCompare();$('#compareSelect').onchange=()=>doCompare(false);$('#btnCompare').onclick=()=>{$('#compareSelect').focus();doCompare()};$('#btnRecord').onclick=()=>{openPage('connectors');toast('Record plan shown. Live capture is not enabled in this research pilot.')};$('#dataRecord').onclick=()=>openPage('connectors');$('#inspectInbox').onclick=loadInbox;
['#btnUpload','#dataImport','#worldImport'].forEach(k=>$(k).onclick=openModal);$('#closeModal').onclick=closeModal;$('#cancelModal').onclick=closeModal;$('#modalOverlay').onclick=e=>{if(e.target===$('#modalOverlay'))closeModal()};$('#uploadNow').onclick=doUpload;
$('#assetClose').onclick=closeAssetDetails;$('#assetCancel').onclick=closeAssetDetails;$('#assetSave').onclick=saveAssetDetails;$('#assetOverlay').onclick=e=>{if(e.target===$('#assetOverlay'))closeAssetDetails()};$('#worldReconstruct').onclick=()=>{openPage('data');$('#registrySearch').value='POINT_CLOUD';renderRegistry();toast('Import an XYZ/PLY point cloud for future reconstruction. No calibrated registration is currently implemented.')};$('#worldEngines').onclick=()=>openPage('connectors');$('#previewGeometry').onclick=inspectGeometry;$('#cameraSource').onchange=e=>pickCameraMedia(e.target.value);$('#registrySearch').oninput=renderRegistry;
$('#faultSeverity').oninput=e=>$('#faultSeverityValue').textContent=num(e.target.value,1);$('#createFault').onclick=createFault;$('#buildReport').onclick=createAssurance;$('#registerContract').onclick=registerContract;$('#evaluateContract').onclick=evaluateContract;$('#downloadJson').onclick=()=>{if(st.reportExport)download('veap-assurance-'+st.reportExport.report_id.slice(0,9)+'.json',JSON.stringify(st.reportExport,null,2))};$('#exportReport').onclick=()=>{openPage('assurance');if(st.current)$('#assuranceSource').value=st.current.id};
$('#comparePhysics').onclick=async()=>{try{let j=await api('/api/jobs');let m=j.jobs.find(x=>x.kind==='mujoco_fall'&&x.status==='COMPLETED');let i=j.jobs.find(x=>x.kind==='isaac_fall'&&x.status==='COMPLETED');if(!m||!i)return toast('Native MuJoCo and Isaac runs must both complete first.',true);let result=await api('/api/physics/compare',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({reference_job_id:m.id,candidate_job_id:i.id})});$('#nativeCompareReport').textContent=JSON.stringify(result,null,2);toast('3D discrepancy calculated; physics calibration remains unvalidated.')}catch(e){toast(e.message,true)}};$('#refreshIntegrations').onclick=renderConnectors;$('#runMujoco').onclick=()=>createNativeJob('mujoco_fall');if($('#runGazebo'))$('#runGazebo').onclick=()=>createNativeJob('gazebo_fall');$('#runIsaac').onclick=()=>createNativeJob('isaac_fall');$('#buildScene').onclick=()=>createNativeJob('scene_export');$('#worldExportScene').onclick=()=>{openPage('connectors');createNativeJob('scene_export')};$('#decodeMcap').onclick=()=>createNativeJob('mcap_decode',$('#mcapSource').value);$('#makeLeRobot').onclick=()=>createNativeJob('lerobot_dataset',$('#lerobotSource').value);
$('#copyRecord').onclick=()=>navigator.clipboard.writeText($('#recordPlan').textContent).then(()=>toast('Recording command copied; execute only after live topics and storage are qualified.')).catch(()=>toast('Clipboard permission denied; select the text and copy it.'));
$('#shortcuts').onclick=()=>toast('Shortcuts: Space = play/pause · [ or Ctrl+B = toggle sidebar · / = source search · 1–6 = workspace tabs · Arrow keys = seek');$('#about').onclick=()=>toast('VEAP R0.3: first-party engineering studio. Native jobs only when configured. No live robot control or safety certification.');
document.addEventListener('keydown',e=>{if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='b'){e.preventDefault();toggleSidebar();return}if(e.target instanceof HTMLInputElement||e.target instanceof HTMLTextAreaElement||e.target instanceof HTMLSelectElement)return;if(e.key==='['){e.preventDefault();toggleSidebar()}if(e.key===' '){e.preventDefault();$('#playBtn').click()}if(e.key==='ArrowRight')seek(st.idx+1);if(e.key==='ArrowLeft')seek(st.idx-1);if(e.key==='/'){e.preventDefault();$('#sideSearch').focus()}if(/^[1-6]$/.test(e.key))openPage(['replay','world','data','policy','assurance','connectors'][Number(e.key)-1]);if(e.key==='Escape'){closeModal();closeAssetDetails()}});window.addEventListener('resize',()=>{renderAll();if(st.view==='world')drawScene('#worldCanvas')});
}
async function init(){bind();try{await refreshAssets();renderConnectors();renderWorld();requestAnimationFrame(anim);setInterval(()=>{if(st.view==='connectors')api('/api/jobs').then(j=>renderNativeJobs(j.jobs)).catch(()=>{})},4000)}catch(e){toast(e.message,true);$('#eventList').innerHTML=`<p class="small-note">Unable to load server: ${esc(e.message)}. Start the local API using uvicorn.</p>`}}
window.addEventListener('DOMContentLoaded',init);
})();

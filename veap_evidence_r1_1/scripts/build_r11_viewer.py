"""Produce self-contained original VEAP research explorer from deterministic data."""
from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[1]
REPORT=json.loads((ROOT/'artifacts/r1_identifiability/stress_report.json').read_text())
# Fixed source example: no real robot data and no external physics engine.
from veap_evidence.fixtures import cases
from veap_evidence.possible_worlds import construct_gap_pair
item=cases()['missing_critical_interval']
PAIR=construct_gap_pair(item['contract'],item['trace'])

HTML='''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>VEAP R1.1 · Evidence Sufficiency Lab</title>
<style>
:root{color-scheme:dark;--bg:#0b1013;--panel:#131b1f;--line:#263338;--type:#edf5f0;--muted:#9aaeb0;--acid:#bbf72a;--cyan:#56dfdb;--warn:#ff826b}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--type);font-family:Inter,ui-sans-serif,system-ui,-apple-system,Segoe UI,sans-serif}
.header{height:70px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid var(--line);padding:0 34px;background:#0e1519;gap:16px}
.brand{font-size:22px;font-weight:900;letter-spacing:-.6px}.brand b{color:var(--acid)}.muted{color:var(--muted)}
.sub{font-size:11px;letter-spacing:1.5px;color:var(--acid);font-weight:800}
.badge{border:1px solid #486225;background:#26321d;border-radius:6px;padding:8px 13px;color:var(--acid);font-size:11px;font-weight:700;letter-spacing:1px}
.top{padding:27px 34px 14px;display:flex;align-items:flex-end;justify-content:space-between;gap:16px;flex-wrap:wrap}
h1{font-size:32px;letter-spacing:-1.2px;margin:7px 0 8px}.top p{color:var(--muted);margin:0;font-size:14px;max-width:870px}
.metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:18px 34px}
.metric{border:1px solid var(--line);border-radius:10px;padding:17px 18px;background:linear-gradient(130deg,#162123,#0f171b)}.metric .k{color:var(--muted);font-size:12px}.metric .v{font-size:29px;font-weight:800;margin:7px 0 2px}.metric .d{font-size:11px;color:var(--muted)}
.grid{padding:0 34px 26px;display:grid;grid-template-columns:minmax(0,1.7fr) minmax(320px,1fr);gap:14px}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:12px;overflow:hidden;min-width:0}
.head{border-bottom:1px solid var(--line);height:53px;padding:15px 20px;font-size:14px;font-weight:750;display:flex;justify-content:space-between;align-items:center}
.content{padding:20px}.tag{font-size:10px;text-transform:uppercase;letter-spacing:1px;border:1px solid #3d4a4d;border-radius:4px;padding:6px 8px;color:var(--muted)}
svg{background:#0a1317;border:1px solid #263438;width:100%;display:block;border-radius:8px}
.legend{display:flex;flex-wrap:wrap;gap:18px;margin:13px 0;color:var(--muted);font-size:12px}
.dot{width:8px;height:8px;display:inline-block;border-radius:50%;margin-right:7px}
.timeline{display:flex;gap:15px;align-items:center;margin-top:14px}.timeline input{flex:1;accent-color:var(--acid)}
.note{border-left:3px solid var(--acid);background:#1d291e;padding:12px 15px;border-radius:4px;color:#e4f1db;font-size:12px;line-height:1.6;margin-top:18px}
.table{width:100%;border-collapse:collapse;font-size:12px}.table td,.table th{border-bottom:1px solid #283338;padding:11px 12px;text-align:left}.table th{color:#9eb1b2;font-weight:600}.table td:last-child{text-align:right;font-weight:850;color:var(--acid)}
.flag{display:inline-block;border:1px solid #625744;background:#282418;border-radius:4px;color:#ffd48f;font-size:10px;padding:6px 8px;margin:4px 0}
pre{white-space:pre-wrap;word-break:break-word;color:#c5d4d2;font:11px/1.6 ui-monospace,monospace;background:#0c1416;border:1px solid #26383a;border-radius:7px;padding:14px;max-height:300px;overflow:auto}
button{border:1px solid #5d7927;border-radius:6px;background:#20311b;color:var(--acid);font-size:12px;font-weight:750;padding:9px 12px;cursor:pointer}
button:hover{background:#2d411e}.flex{display:flex;gap:10px;flex-wrap:wrap;margin-top:14px}
.footer{color:var(--muted);font-size:11px;padding:0 34px 25px;line-height:1.7}
@media(max-width:850px){.metrics{grid-template-columns:repeat(2,1fr)}.grid{grid-template-columns:1fr}.header,.top{padding-left:17px;padding-right:17px}.metrics{margin:18px 17px}.grid{padding-left:17px;padding-right:17px}.header{height:auto;min-height:65px}}
</style></head><body>
<header class="header"><div class="brand"><b>◈</b> VEAP <span class="muted" style="font-size:12px;font-weight:500">/ RESEARCH · R1.1</span></div><span class="badge">SYNTHETIC EVIDENCE · NOT HARDWARE VERIFIED</span></header>
<section class="top"><div><span class="sub">EVIDENCE-SUFFICIENT EMBODIED EVALUATION</span><h1>One observation record. Two possible worlds.</h1><p>Contract-conditioned evaluation of a recorded robot task. Identical retained measurements admit both compliant and violating paths. The correct verdict is <b style="color:#ffd48f">INCONCLUSIVE</b> until the missing interval can be resolved.</p></div><span class="tag">OFFLINE · FIRST-PARTY VIEWER</span></section>
<section class="metrics"><div class="metric"><div class="k">Synthetic stress cases</div><div class="v">96</div><div class="d">16 correlated geometric translations × 6 conditions</div></div><div class="metric"><div class="k">VEAP verdict agreement</div><div class="v">96/96</div><div class="d">Author-constructed expected epistemic labels</div></div><div class="metric"><div class="k">Separate certificates checked</div><div class="v">96/96</div><div class="d">Independent implementation, shared assumptions</div></div><div class="metric"><div class="k">Dual-world checks</div><div class="v">16/16</div><div class="d">Constructive ambiguity controls</div></div></section>
<div class="grid"><section class="panel"><div class="head">Spatial evidence explorer <span class="tag">MAP FRAME · METRES</span></div><div class="content"><svg id="map" role="img" aria-label="Two simulated paths, the same visible pose observations and an exclusion zone" viewBox="0 0 800 400"></svg><div class="legend"><span><i class="dot" style="background:var(--acid)"></i>Candidate compliant</span><span><i class="dot" style="background:var(--warn)"></i>Candidate violating</span><span><i class="dot" style="background:var(--cyan)"></i>Retained observations</span><span><i class="dot" style="background:#ffdfa0"></i>Exclusion region</span></div><div class="timeline"><b style="font-size:13px">t = <span id="clock">1.00</span>s</b><input id="scrub" type="range" min="0" max="2" step=".01" value="1" aria-label="Replay both possible trajectories"/><button id="play">▶ Play</button></div><div class="note">At <b>t = 1.00 s</b>, no pose observation remains in the evaluator's input. A safe path and a keep-out crossing are both compatible with all retained observations and the declared speed bound. This proves ambiguity <em>under the model assumptions</em>, not what happened in the real world.</div></div></section>
<section class="panel"><div class="head">Evidence and proof obligations <span class="tag">CONTRACT-BOUND</span></div><div class="content"><div class="flag">RESULT: INCONCLUSIVE · MORE EVIDENCE REQUIRED</div><h3 style="margin:12px 0 9px">Witness pair — independently checked</h3><table class="table"><tr><th>Candidate world</th><th>Verdict</th></tr><tr><td>World A — clear path</td><td style="color:var(--acid)">COMPLIANT</td></tr><tr><td>World B — exclusion entry</td><td style="color:var(--warn)">VIOLATING</td></tr></table><p class="muted" style="font-size:12px;line-height:1.6">Both worlds reach the goal at the declared deadline, match all visible pose samples, and respect the specified speed limit. The separate checker recomputes geometry and motion bounds from the exported witness.</p><div class="flex"><button id="toggleSafe">Show/hide compliant</button><button id="toggleBad">Show/hide violating</button></div><h3>Witness metadata</h3><pre id="payload"></pre></div></section>
<section class="panel"><div class="head">Baseline comparison <span class="tag">NOT A HELD-OUT BENCHMARK</span></div><div class="content"><table class="table"><thead><tr><th>Evaluator</th><th>Matches</th></tr></thead><tbody id="comparators"></tbody></table><div class="note">The separate reachability monitor matches VEAP's 96 decisions. That is a useful <b>null comparator result</b>: VEAP has not demonstrated a superior verdict algorithm. The proposed value is a reusable, inspectable evidence certificate.</div></div></section>
<section class="panel"><div class="head">Validity and publication gate <span class="tag">R1-G1 · MECHANISM ONLY</span></div><div class="content"><div class="flag">NO REAL ROBOT OR EXTERNAL GROUND TRUTH</div><p style="font-size:13px;line-height:1.7;color:var(--muted)">This offline viewer uses six author-constructed conditions translated sixteen times. These cases are deliberately correlated and must not be treated as 96 independent deployment environments. EAI's eight upstream cells and ABC's ten assessments are pinned but <b>not reproduced</b>.</p><h3>What must happen next</h3><p style="font-size:13px;line-height:1.7">Independently authored environments; an established runtime-monitor comparator; blinded human review; reference sensing; missing-data interventions; measured reviewer time; and a certificate soundness audit. Report null outcomes and uncertainty.</p></div></section></div>
<div class="footer">VEAP R1.1 · Evidence Sufficiency Lab · Research prototype. No Foxglove dependency. No source authenticity, physical safety, SOTA, or production-readiness claim.</div>
<script>
const PAIR=__PAIR__;
const STRESS=__STRESS__;
const ns='http://www.w3.org/2000/svg';const svg=document.getElementById('map');
const u=x=>75+290*x; const v=y=>337-156*y;
const mk=(name,props)=>{const e=document.createElementNS(ns,name);Object.entries(props||{}).forEach(([k,val])=>e.setAttribute(k,String(val)));svg.appendChild(e);return e};
for(let x=0;x<=2.4;x+=.2){mk('line',{x1:u(x),y1:20,x2:u(x),y2:380,stroke:'#213238','stroke-width':1})}
for(let y=-.2;y<=1.9;y+=.2){mk('line',{x1:50,y1:v(y),x2:780,y2:v(y),stroke:'#213238','stroke-width':1})}
let zone=__ZONE__;mk('rect',{x:u(zone[0]),y:v(zone[3]),width:u(zone[2])-u(zone[0]),height:v(zone[1])-v(zone[3]),fill:'#9a3d2b','fill-opacity':'.29',stroke:'#ff826b','stroke-width':2,'stroke-dasharray':'6 5'});
mk('text',{x:u(zone[0]),y:v(zone[3])-10,fill:'#ffb9a8','font-size':13}).textContent='EXCLUSION ZONE';
function poly(knots,color){return mk('polyline',{points:knots.map(p=>`${u(p.x)},${v(p.y)}`).join(' '),fill:'none',stroke:color,'stroke-width':4,'stroke-linecap':'round','stroke-linejoin':'round'})}
let good=PAIR.paths.candidate_compliant,bad=PAIR.paths.candidate_violating;
const goodLine=poly(good,'#bbf72a'),badLine=poly(bad,'#ff826b');
for(const obs of __OBS__){mk('circle',{cx:u(obs.x),cy:v(obs.y),r:8,fill:'#56dfdb',stroke:'#d8ffff','stroke-width':2});}
const goal=__GOAL__;mk('circle',{cx:u(goal.x),cy:v(goal.y),r:20,fill:'none',stroke:'#56dfdb','stroke-width':2,'stroke-dasharray':'5 3'});
const pGood=mk('circle',{r:12,fill:'#bbf72a',stroke:'#0b1013','stroke-width':4});const pBad=mk('circle',{r:12,fill:'#ff826b',stroke:'#0b1013','stroke-width':4});
let showSafe=true,showBad=true,playing=false,timer=null;
const position=(knots,t)=>{for(let i=0;i<knots.length-1;i++){let a=knots[i],b=knots[i+1];if(t>=a.t_s&&t<=b.t_s){let z=(t-a.t_s)/(b.t_s-a.t_s);return [a.x+(b.x-a.x)*z,a.y+(b.y-a.y)*z]}}let x=knots[knots.length-1];return [x.x,x.y]}
function render(){const t=Number(document.getElementById('scrub').value);document.getElementById('clock').textContent=t.toFixed(2);const a=position(good,t),b=position(bad,t);pGood.setAttribute('cx',u(a[0]));pGood.setAttribute('cy',v(a[1]));pBad.setAttribute('cx',u(b[0]));pBad.setAttribute('cy',v(b[1]));goodLine.style.display=pGood.style.display=showSafe?'':'none';badLine.style.display=pBad.style.display=showBad?'':'none'}
document.getElementById('scrub').addEventListener('input',render);document.getElementById('toggleSafe').onclick=()=>{showSafe=!showSafe;render()};document.getElementById('toggleBad').onclick=()=>{showBad=!showBad;render()};
document.getElementById('play').onclick=()=>{if(playing){clearInterval(timer);playing=false;document.getElementById('play').textContent='▶ Play';return}playing=true;document.getElementById('play').textContent='■ Stop';timer=setInterval(()=>{let e=document.getElementById('scrub'),n=Number(e.value)+.02;e.value=(n>2?0:n).toFixed(2);render()},45)};
const metric=STRESS.summary.correct_by_method;const names=[['veap','VEAP certificate'],['separate_monitor','Separate monitor (strong)'],['goal_only','Goal-only (weak)'],['sampled_safety','Sampled safety'],['gap_aware','Gap-aware abstaining']];document.getElementById('comparators').innerHTML=names.map(([k,label])=>`<tr><td>${label}</td><td>${metric[k]}/${STRESS.n_cases}</td></tr>`).join('');
document.getElementById('payload').textContent=JSON.stringify({contract_sha256:PAIR.contract_sha256,source_trace_sha256:PAIR.available_trace_sha256,missing_interval_s:PAIR.missing_interval_s,constructed_midpoint_s:PAIR.constructed_midpoint_s,pair_sha256:PAIR.pair_sha256,source_authenticity:PAIR.source_authenticity},null,2);
render();
</script></body></html>'''
html=HTML.replace('__PAIR__',json.dumps(PAIR,separators=(',',':'))).replace('__STRESS__',json.dumps({"n_cases":REPORT['n_cases'],"summary":REPORT['summary']},separators=(',',':')))
html=html.replace('__ZONE__',json.dumps(item['contract']['keepout'])).replace('__OBS__',json.dumps(item['trace']['samples'],separators=(',',':'))).replace('__GOAL__',json.dumps(item['contract']['goal']))
path=ROOT/'VEAP_R1_1_Offline_Identifiability_Lab.html'
path.write_text(html,encoding='utf-8')
print(f'Generated {path}, bytes={path.stat().st_size}')

"""Create a truly self-contained read-only synthetic VEAP Studio demonstration."""
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from veap_studio.api import create_app
from fastapi.testclient import TestClient
ROOT=Path(__file__).resolve().parents[1]
base=ROOT/'web'
client=TestClient(create_app(ROOT/'demo_data',seed_demo=True))
assets=client.get('/api/assets').json()['assets']
traces={a['id']:client.get('/api/traces/'+a['id']).json() for a in assets if a['kind']=='TRAJECTORY'}
integration={'source':'OFFLINE_DEMO','network_scans':False,'physical_actuation':False,
 'connectors':[{'id':a,'name':name,'description':description,'status':'DEMO_ONLY',
   'claim':'Offline visual demonstration. No runtime probe or native execution.', 'runtime':None}
  for a,name,description in [
   ('veap','VEAP Native Studio','Original panels, playback, fault analysis'),
   ('isaac','Isaac Sim / Isaac Lab','PhysX native simulation'),
   ('mujoco','MuJoCo','Second-physics validation'),
   ('ros','ROS 2 & MCAP','Robot telemetry'),
   ('lerobot','Learning Data','Robot learning datasets'),
   ('openusd','OpenUSD / CAD','3D interchange'),
   ('g1','Unitree G1','Humanoid evidence suite'),
   ('m3','Yahboom M3 Pro','Mobile robot evidence suite'),
   ('renderer','VEAP 3D Engine','First-party synthetic scene viewport'),
  ]]}
fixture=json.dumps({'assets':{'assets':assets},'traces':traces,'integration':integration},separators=(',',':'))
shim=r'''<script>
window.VEAP_OFFLINE_DEMO=true;
const demo=__FIXTURE__;
const demoJSON=(obj,status=200)=>new Response(JSON.stringify(obj),{status,headers:{'content-type':'application/json'}});
window.fetch=async function(url,init={}){
 const path=String(url),method=String(init.method||'GET').toUpperCase();
 if(path==='/api/assets'&&method==='GET')return demoJSON(demo.assets);
 if(path==='/api/integrations')return demoJSON(demo.integration);
 if(path==='/api/jobs')return demoJSON({jobs:[]});
 if(path==='/api/contracts'&&method==='GET')return demoJSON({contracts:[]});
 if(path==='/api/inbox')return demoJSON({root:'offline_demo_no_filesystem',files:[],custody:'DEMO_ONLY'});
 if(path.startsWith('/api/traces/'))return demoJSON(demo.traces[path.split('/').pop()]||{detail:'No demo trace'},demo.traces[path.split('/').pop()]?200:404);
 if(path.startsWith('/api/geometry/')||path.startsWith('/api/reconstruct/'))return demoJSON({detail:'Upload requires the running local application'},422);
 if(path.startsWith('/api/assets/')&&path.endsWith('/raw'))return demoJSON({detail:'Offline synthetic demonstration has no media file'},422);
 if(path==='/api/compare'&&method==='POST'){
  const o=JSON.parse(init.body),a=demo.traces[o.reference_id],b=demo.traces[o.candidate_id];
  if(!a||!b)return demoJSON({detail:'Demo traces unavailable'},422);
  let errors=a.rows.slice(0,100).map((r,i)=>Math.hypot(r.x_m-b.rows[i].x_m,r.y_m-b.rows[i].y_m));
  return demoJSON({rmse_m:Math.sqrt(errors.reduce((s,v)=>s+v*v,0)/errors.length),max_error_m:Math.max(...errors),alignment:'ELAPSED_TIME_ONLY'});
 }
 if(path==='/api/reports'&&method==='POST'){
  let o=JSON.parse(init.body),a=demo.traces[o.source_id];if(!a)return demoJSON({detail:'Unknown demonstration'},404);
  return demoJSON({...a.report,report_id:'offline_demo',verdict:a.report.verdict,
    evidence_level:'SYNTHETIC_DEMO_ONLY',not_claimed:['physical safety','engine execution','real sensor authenticity']});
 }
 return demoJSON({detail:'Offline demo cannot execute native jobs, upload original evidence or perform ROS capture. Start the local server.'},422);
}
</script>'''.replace('__FIXTURE__',fixture)
html=(base/'index.html').read_text()
html=html.replace('<link rel="stylesheet" href="/assets/style.css"/>','<style>\n'+(base/'style.css').read_text()+'\n</style>')
html=html.replace('<script src="/assets/app.js" defer></script>',shim+'\n<script>\n'+(base/'app.js').read_text()+'\n</script>')
html=html.replace('<title>VEAP Studio — Physical AI Operations</title>','<title>VEAP Studio R0.3 — Offline Synthetic Preview</title>')
html=html.replace('R0.3 <b>INTEGRATED LOCAL</b>','R0.3 <b>OFFLINE SYNTHETIC DEMO</b>')
output=ROOT/'VEAP_Studio_R03_Offline_Demo.html'
output.write_text(html)
print(str(output),output.stat().st_size)

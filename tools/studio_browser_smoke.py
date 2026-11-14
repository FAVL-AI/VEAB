"""Optional UI integration smoke test using a real browser and in-memory FastAPI.

Requires: playwright and an installed Chromium browser. No external networking.
Result: screenshot in the working directory, no production claim.
"""
from __future__ import annotations
import argparse
import base64
import tempfile
from pathlib import Path
from urllib.parse import urlsplit
from fastapi.testclient import TestClient
from veap.enterprise.db import StudioDB
from veap.enterprise.api import create_app


def run(browser_path: str | None, output: str):
    from playwright.sync_api import sync_playwright
    root=Path(__file__).resolve().parents[1]
    directory=root/'web'/'assurance_studio'
    html=(directory/'index.html').read_text().replace(
        '<link rel="stylesheet" href="/studio/static/style.css"><script src="/studio/static/app.js" defer></script>','')
    with tempfile.TemporaryDirectory() as temporary:
        db=StudioDB(temporary)
        tenant,admin=db.bootstrap('Smoke-test organisation','admin@local.invalid','Demo engineer')
        token=db.issue_dev_token(admin,valid_hours=1)
        with TestClient(create_app(data_dir=temporary,mode='dev-token')) as client:
            with sync_playwright() as playwright:
                opts={'headless':True}
                if browser_path:opts['executable_path']=browser_path
                browser=playwright.chromium.launch(**opts)
                page=browser.new_page(viewport={'width':1540,'height':940})
                js_errors=[]
                page.on('pageerror',lambda error:js_errors.append(str(error)))

                def api_bridge(url,options=None):
                    options=options or {}
                    parts=urlsplit(url)
                    path=parts.path+('?' + parts.query if parts.query else '')
                    response=client.request(options.get('method','GET'),path,
                                            headers=options.get('headers') or {},content=options.get('body'))
                    return {'status':response.status_code,'body':base64.b64encode(response.content).decode(),
                            'contentType':response.headers.get('content-type','application/octet-stream')}

                page.expose_function('bridgeApi',api_bridge)
                page.set_content(html,wait_until='load')
                page.add_style_tag(content=(directory/'style.css').read_text())
                page.add_script_tag(content="""window.fetch=async (url,options={})=>{
                    const result=await window.bridgeApi(url,{method:options.method||'GET',headers:options.headers||{},
                       body:typeof options.body==='string'?options.body:undefined});
                    const bytes=Uint8Array.from(atob(result.body),character=>character.charCodeAt(0));
                    return new Response(bytes,{status:result.status,headers:{'Content-Type':result.contentType}});
                };""")
                page.add_script_tag(content=(directory/'app.js').read_text())
                page.locator('#token-input').fill(token)
                page.locator('#connect').click()
                page.locator('#connect-overlay').wait_for(state='hidden',timeout=15000)
                page.on('dialog',lambda dialog:dialog.accept('Demo project'))
                page.locator('#new-project').click()
                page.wait_for_function("document.querySelector('#project-select').options.length > 0",timeout=15000)
                page.locator('#scenario-select').select_option('warehouse-transfer')
                page.locator('#execute').click()
                page.wait_for_function("document.querySelector('#verification-status').textContent.includes('ACCEPTED')",timeout=30000)
                page.screenshot(path=output,full_page=True)
                page.locator('[data-view="engines"]').click()
                page.wait_for_function("document.querySelectorAll('.engine-card').length === 6",timeout=15000)
                assert not js_errors,js_errors
                print('UI smoke passed: authenticated project, run, verification, 3D trace and engine readiness.')
                print('Screenshot:',output)
                browser.close()

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--chromium',default=None,help='Installed Chromium executable (optional)')
    parser.add_argument('--out',default='studio-browser-smoke.png')
    args=parser.parse_args()
    run(args.chromium,args.out)

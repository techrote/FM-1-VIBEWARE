'use strict';
// Run with Node 18+: node test_request_deadline.cjs [live.html]
// Exercise the actual page request helper with loopback HTTP, not a device.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const http=require('node:http');
const path=require('node:path');
const vm=require('node:vm');
const {performance}=require('node:perf_hooks');
const html=fs.readFileSync(process.argv[2]||path.join(__dirname,'live.html'),'utf8');
const helper=html.match(/async function request\(path,q,signal\)\{[\s\S]*?\n\}(?=\nfunction clearAudio)/);
assert.ok(helper,'page request helper not found');
let requests=0;
const server=http.createServer((req,res)=>{
  requests++;req.resume();
  if(req.url==='/headers')return;
  res.setHeader('Content-Type','application/json');
  if(req.url==='/body'){res.write('{"ok":');return;}
  if(req.url==='/error'){res.writeHead(409);res.end('{}');return;}
  res.end('{"ok":true}');
});
(async()=>{
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const origin=`http://127.0.0.1:${server.address().port}`;
  let releaseLate;
  const nativeFetch=globalThis.fetch;
  const context=vm.createContext({AbortController,setTimeout,clearTimeout,Error,fetch:async(p,o)=>{
    if(p==='/late'){
      const r=await nativeFetch(origin+'/ok',o);const body=await r.json();
      return {ok:true,json:()=>new Promise(resolve=>{releaseLate=()=>resolve(body)})};
    }
    return nativeFetch(origin+p,o);
  }});
  vm.runInContext(helper[0],context);
  const request=context.request;
  assert.equal((await request('/ok',{})).ok,true);
  await assert.rejects(request('/error',{}),/Session rejected: 409/);
  for(const endpoint of ['/headers','/body','/late']){
    const t=performance.now();await assert.rejects(request(endpoint,{}),/Request timed out/);
    const ms=performance.now()-t;assert.ok(ms>=1100&&ms<3000,`${endpoint}: ${ms}`);
    console.log(`${endpoint}: deadline ${Math.round(ms)} ms`);
  }
  assert.equal(typeof releaseLate,'function');releaseLate();
  const ac=new AbortController();const t=performance.now();
  const pending=request('/headers',{},ac.signal);setTimeout(()=>ac.abort(),40);
  await assert.rejects(pending,/Request cancelled/);assert.ok(performance.now()-t<1000);
  const already=new AbortController();already.abort();await assert.rejects(request('/ok',{},already.signal),/Request cancelled/);
  assert.equal((await request('/ok',{})).ok,true);
  console.log(`PASS: normal, HTTP 409, header/body/late deadlines, active/pre-aborted cancellation, recovery (${requests} HTTP requests)`);
})().catch(e=>{console.error(e);process.exitCode=1;}).finally(()=>{server.closeAllConnections();server.close();});

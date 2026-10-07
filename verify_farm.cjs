const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict');
const elements=new Map();const element=id=>{if(!elements.has(id))elements.set(id,{value:['minHq','minShare'].includes(id)?'0':id==='minParticipants'?'1':'',getContext:()=>({}),addEventListener(){},replaceChildren(){},classList:{toggle(){}},setAttribute(){}});return elements.get(id)};
const context=vm.createContext({document:{getElementById:element,querySelector:element},window:{addEventListener(){}},console,Map,Set});
let code=fs.readFileSync('app.js','utf8').replace(/start\(\);\s*$/,'');vm.runInContext(code,context);
const data=JSON.parse(fs.readFileSync('data/hqs.json'));const power=JSON.parse(fs.readFileSync('data/power.json'));const shields=JSON.parse(fs.readFileSync('data/shields.json'));const shieldMap=new Map(shields.map(s=>[s.id,s]));
context.records=data.map(h=>({...h,shield:shieldMap.get(h.id)}));context.power=power;
vm.runInContext('hqs=records.filter(h=>h.current!==false||h.roster_current);powerData=power;renderList=()=>{};scheduleDraw=()=>{};',context);
const get=s=>vm.runInContext(s,context);get('refreshList()');const baseline=get('filtered.length');
for(const mode of ['either','alliance','player']){element('farmNames').value=mode;get('refreshList()');const expected=data.filter(h=>(h.current!==false||h.roster_current)&&shieldMap.get(h.id)?.status!=='not_hq').filter(h=>{const a=/farm/i.test(power.alliances[h.tag]?.display||h.tag||'');const p=/farm/i.test(h.name||'');return mode==='alliance'?a:mode==='player'?p:a||p}).map(h=>h.id).sort((a,b)=>a-b);assert.deepEqual(Array.from(get('filtered.map(h=>h.id).sort((a,b)=>a-b)')),expected);assert.equal(get('visiblePins().length'),expected.length);console.log(mode,expected.length);}
element('farmNames').value='either';element('search').value='FaRm';get('refreshList()');assert.equal(get('filtered.length'),get('hqs.filter(h=>shieldStatus(h)!=="not_hq"&&matchesFarm(h)).length'));
element('farmNames').value='';element('search').value='';get('refreshList()');assert.equal(get('filtered.length'),baseline);
element('search').value='State 798 farms';get('refreshList()');assert.ok(get('filtered.length')>0);
get('hqs=[{id:1,name:"FaRm One",tag:"test"},{id:2,name:"Other",tag:"FaRm"},{id:3,name:"Other",tag:"none"}];');element('search').value='';element('farmNames').value='either';get('refreshList()');assert.deepEqual(Array.from(get('filtered.map(h=>h.id)')),[1,2]);
console.log('PASS: full alliance names, mixed case, player/either modes, pins, reset, and unranked map players');

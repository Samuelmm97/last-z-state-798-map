const assert=require('node:assert/strict'),S=require('./shared-state.js');
const power={schemaVersion:1,state:798,source:{url:'workbook',observedAt:'2026-10-14T00:00:00Z'},alliances:[],players:[{uid:'123',name:'New name',tag:'Helm',hq:28,personalPower:{value:200,observedAt:'2026-10-14T00:00:00Z'},components:{hero:{value:25,observedAt:'2026-10-09T00:00:00Z'}}}]};
const data=S.index(power,[{id:1,playerId:'123',name:'Map name',x:480,y:490,observed_at_utc:'2026-10-14T01:00:00Z'}]);
const p=S.enrich({id:1,name:'Old name',x:470,y:480,totalPower:1},data);
assert.equal(p.totalPower,200);assert.equal(p.heroPower,25);assert.equal(p.heroPowerCaptured,'2026-10-09T00:00:00Z');
assert.equal(p.x,470);assert.equal(p.y,480);assert.equal(p.actualX,480);assert.equal(p.actualY,490);assert(p.nameAliases.includes('Old name'));
assert.equal(S.enrich({id:2,name:'unknown',totalPower:999},data).totalPower,null);
assert.throws(()=>S.index({...power,players:power.players.concat(power.players)},[]));
console.log('Shared UID identities, separate power dates and proposed/observed positions passed');

"""Current power is a read-only projection of the authoritative workbook."""
from __future__ import annotations
import datetime as dt
import json
from pathlib import Path

WORKBOOK='11RVzmSmrhbz2nmmMyztuSS0HUkB7ZNpE8rvZUIzXSvE'
URL='https://docs.google.com/spreadsheets/d/'+WORKBOOK

def timestamp(value):
    text=str(value).strip().replace(' ','T')
    if not text.endswith(('Z','+00:00')):text+='Z'
    return dt.datetime.fromisoformat(text.replace('Z','+00:00')).isoformat().replace('+00:00','Z')

def project(players,alliances,breakdown,observed_at,expected_count=None):
    rows=[r for r in players if r and r[0]==798]
    if expected_count is not None and len(rows)!=expected_count:raise ValueError('State 798 roster coverage changed; refusing partial power data')
    result=[];seen=set();parts={str(r[3]):r for r in breakdown if r and r[0]==798}
    for row in rows:
        uid=str(row[6])
        if not uid.isascii() or not uid.isdigit() or uid=='0' or uid in seen:raise ValueError('Duplicate or invalid player ID')
        seen.add(uid)
        value=row[3]
        if type(value) is not int or value<0:raise ValueError('Invalid personal power')
        p=dict(uid=uid,name=row[2],tag=row[1],hq=row[5],allianceId=str(row[7]),allianceName=row[8],
               personalPower=dict(value=value,observedAt=timestamp(observed_at),source='Players'))
        component=parts.get(uid)
        if component:
            if len(component)<13 or component[11]!=0 or sum(component[5:10])!=component[4]:raise ValueError('Invalid power component sum')
            p['components']={k:dict(value=component[i],observedAt=timestamp(component[12]),source='Power Breakdown')
                for k,i in [('structure',5),('tech',6),('troop',7),('hero',8),('vehicle',9)]}
        result.append(p)
    groups=[]
    for row in alliances:
        if len(row)<10 or row[1]!=798:continue
        groups.append(dict(tag=row[2],name=row[3],uid=str(row[9]),rank=row[0],members=row[5],power=dict(value=row[8],observedAt=timestamp(observed_at))))
    return dict(schemaVersion=1,state=798,source=dict(url=URL,spreadsheetId=WORKBOOK,observedAt=timestamp(observed_at),
        retrievedAt=dt.datetime.now(dt.timezone.utc).isoformat().replace('+00:00','Z'),
        coverage='Listed alliances and roster members; unaffiliated players are not covered'),players=result,alliances=groups)

def refresh(atlas,config,write=True):
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import AuthorizedSession
    credentials=Credentials.from_authorized_user_file(config['oauth_token_file'],scopes=['https://www.googleapis.com/auth/spreadsheets'])
    session=AuthorizedSession(credentials);base='https://sheets.googleapis.com/v4/spreadsheets/'+WORKBOOK
    def get(path,**params):
        response=session.get(base+path,params=params,timeout=90)
        if not response.ok:raise RuntimeError('Authoritative power workbook could not be read; current power retained')
        return response.json()
    metadata=get('',fields='sheets.properties')
    sheets={s['properties']['title']:s['properties'] for s in metadata['sheets']}
    if not {'Players','Alliances','States','Power Breakdown'}<=sheets.keys():raise ValueError('Power workbook tabs changed')
    states=get('/values/States!A1:I100',valueRenderOption='UNFORMATTED_VALUE')['values']
    current=next(r for r in states if r and r[0]==798);count=int(current[3]);observed=current[5]
    # The current workbook puts State 798 first. Verify that rather than relying
    # on row numbers when a user sorts or refreshes the table.
    head=get('/values/Players!A1:I'+str(count+2),valueRenderOption='UNFORMATTED_VALUE').get('values',[])
    players=[r for r in head if r and r[0]==798]
    if len(players)!=count:
        players=[]
        for start in range(2,sheets['Players']['gridProperties']['rowCount']+1,4000):
            end=min(start+3999,sheets['Players']['gridProperties']['rowCount'])
            players.extend(r for r in get(f'/values/Players!A{start}:I{end}',valueRenderOption='UNFORMATTED_VALUE').get('values',[]) if r and r[0]==798)
    alliances=get('/values/Alliances!A1:J'+str(sheets['Alliances']['gridProperties']['rowCount']),valueRenderOption='UNFORMATTED_VALUE').get('values',[])
    breakdown=get('/values/\'Power Breakdown\'!A1:M'+str(sheets['Power Breakdown']['gridProperties']['rowCount']),valueRenderOption='UNFORMATTED_VALUE').get('values',[])
    snapshot=project(players,alliances,breakdown,observed,count)
    path=Path(atlas)/'data/power-current.json'
    if path.exists():
        old=json.loads(path.read_text(encoding='utf-8'))
        old_compare=json.loads(json.dumps(old));new_compare=json.loads(json.dumps(snapshot))
        old_compare.get('source',{}).pop('retrievedAt',None);new_compare.get('source',{}).pop('retrievedAt',None)
        if old_compare==new_compare:snapshot=old
    if not write:return snapshot
    temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps(snapshot,ensure_ascii=False,separators=(',',':')),encoding='utf-8');temporary.replace(path)
    return snapshot

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--atlas',type=Path,default=Path(__file__).resolve().parent);parser.add_argument('--config',type=Path,required=True);args=parser.parse_args()
    data=refresh(args.atlas,json.loads(args.config.read_text(encoding='utf-8')))
    print(json.dumps(dict(players=len(data['players']),alliances=len(data['alliances']),observedAt=data['source']['observedAt'])))

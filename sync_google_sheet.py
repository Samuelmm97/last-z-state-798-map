"""Mirror Atlas records into one managed Google Sheets tab after data updates.

Configuration is local/ignored. No Google dependency is needed for --export or
for update scripts until a spreadsheet_id has been configured.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCOPE = 'https://www.googleapis.com/auth/spreadsheets'
HEADERS = ['Atlas ID', 'Player', 'Alliance', 'HQ level', 'HQ reading date',
           'HQ review', 'X', 'Y', 'Location date', 'Record status',
           'Previous SvS cohort', 'Roster confirmed', 'Roster date',
           'State membership', 'Personal power', 'Personal power date', 'Power approximate',
           'Strongest hero power', 'Strongest hero date', 'Total hero power', 'Total hero date', 'Previous SvS shield',
           'Shield date', 'Previous terrain', 'Participation date', 'Atlas link']


def read(path, default=None):
    if not path.exists() and default is not None:
        return default
    return json.loads(path.read_text(encoding='utf-8'))


def table(atlas=ROOT):
    atlas = Path(atlas)
    records = read(atlas / 'data/hqs.json')
    if len({p['id'] for p in records}) != len(records):
        raise ValueError('Duplicate Atlas IDs; refusing to sync')
    shields = {p['id']: p for p in read(atlas / 'data/shields.json', [])}
    event = read(atlas / 'data/participation.json', {})
    power = read(atlas / 'data/power.json', {})
    players = {p['atlas_id']: p for p in power.get('players', {}).values()
               if p.get('atlas_id') is not None}
    rows = [HEADERS]
    for p in sorted(records, key=lambda p: p['id']):
        s = shields.get(p['id'], {})
        metrics = players.get(p['id'], {})
        def metric(key, field='value'):
            return (metrics.get(key) or {}).get(field, '')
        def metric_date(key):
            if metric(key) == '':
                return ''
            item = metrics.get(key) or {}
            return (item.get('observed_date') or item.get('captured_date') or
                    (power.get('roster_metrics_carried_from') or {}).get('as_of')
                    if item.get('source') == 'alliance_member_roster' else
                    item.get('observed_date') or item.get('captured_date') or
                    (power.get('sources', {}).get(key) or {}).get('date') or power.get('captured_date') or '')
        status = ('Current map' if p.get('current') is not False else
                  'Roster confirmed; older or unknown location' if p.get('roster_current') else
                  'Historical; not confirmed in latest scan')
        row = [p['id'], p.get('name'), p.get('tag'), p.get('hq'),
               p.get('hq_observed_date') or p.get('observed_date'),
               p.get('hq_review') or p.get('review'), p.get('x'), p.get('y'),
               p.get('observed_date'), status, p.get('zone') or 'outside',
               bool(p.get('roster_current')), p.get('roster_observed_date'),
               p.get('state_membership'), metric('personal_power'),
               metric_date('personal_power'), bool(metric('personal_power', 'approximate')),
               metric('strongest_hero_power'), metric_date('strongest_hero_power'),
               metric('total_hero_power'), metric_date('total_hero_power'),
               s.get('status', 'unscanned'), s.get('observedAt') or s.get('captured_date') or s.get('observed_date') or (event.get('captured_date') if s else ''),
               s.get('terrain', 'unscanned'), p.get('attendance_date'),
               f'https://samuelmm97.github.io/last-z-state-798-map/#hq-{p["id"]}']
        rows.append(['' if value is None else value for value in row])
    return rows


def configuration(atlas):
    path = Path(os.environ.get('LASTZ_SHEETS_CONFIG') or Path(atlas) / '.google-sheets.json')
    config = read(path, {})
    if os.environ.get('LASTZ_SPREADSHEET_ID'):
        config['spreadsheet_id'] = os.environ['LASTZ_SPREADSHEET_ID']
    return config


def sync_if_configured(atlas=ROOT):
    config = configuration(atlas)
    if not config.get('spreadsheet_id'):
        print('Google Sheet sync not configured; Atlas update retained.')
        return False
    sync(atlas, config)
    return True


def sync(atlas, config):
    # Existing collectors use several Python environments. Run the Google-only
    # step in the configured environment without changing their dependencies.
    import subprocess
    import sys
    interpreter = config.get('python')
    if interpreter and Path(interpreter).resolve() != Path(sys.executable).resolve():
        subprocess.run([interpreter, str(ROOT/'sync_google_sheet.py'),
                        '--atlas', str(atlas)], check=True,
                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        return
    # ADC supports either an authorized user refresh token or a service account.
    # Keep credentials outside the repository, e.g. GOOGLE_APPLICATION_CREDENTIALS.
    import google.auth
    from google.auth.transport.requests import AuthorizedSession
    if config.get('oauth_token_file'):
        from google.oauth2.credentials import Credentials
        credentials = Credentials.from_authorized_user_file(config['oauth_token_file'], scopes=[SCOPE])
    else:
        credentials, _ = google.auth.default(scopes=[SCOPE])
    session = AuthorizedSession(credentials)
    spreadsheet_id = config['spreadsheet_id']
    title = config.get('tab', 'HQ Data')
    if title != 'HQ Data':
        raise ValueError('Only the managed HQ Data tab may be overwritten')
    rows = table(atlas)
    base = f'https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}'
    def request(method, url, **kwargs):
        response = session.request(method, url, timeout=90, **kwargs)
        if not response.ok:
            raise RuntimeError(f'Google Sheets request failed ({response.status_code}); Atlas data retained. Retry sync after checking access.')
        return response.json()
    metadata = request('GET', base, params={'fields': 'sheets.properties'})
    sheet = next((s['properties'] for s in metadata.get('sheets', [])
                  if s['properties']['title'] == title), None)
    requests = []
    if sheet:
        sheet_id = sheet['sheetId']
        old_grid = sheet.get('gridProperties', {})
    else:
        sheet_id = max([s['properties']['sheetId'] for s in metadata.get('sheets', [])] + [0]) + 1
        old_grid = {}
        requests.append({'addSheet': {'properties': {'sheetId': sheet_id, 'title': title}}})
    row_count = max(len(rows), old_grid.get('rowCount', 1000))
    column_count = max(len(HEADERS), old_grid.get('columnCount', 26))
    requests.append({'updateSheetProperties': {
        'properties': {'sheetId': sheet_id, 'gridProperties': {
            'rowCount': row_count, 'columnCount': column_count, 'frozenRowCount': 1}},
        'fields': 'gridProperties'}})
    def cell(value):
        kind = 'boolValue' if isinstance(value, bool) else 'numberValue' if isinstance(value, (int, float)) else 'stringValue'
        return {'userEnteredValue': {kind: value}}
    # Google clears the uncovered portion of this range in the same atomic batch.
    # Names are literal strings, never formulas; old trailing rows cannot survive.
    requests.append({'updateCells': {
        'range': {'sheetId': sheet_id, 'startRowIndex': 0, 'endRowIndex': row_count,
                  'startColumnIndex': 0, 'endColumnIndex': len(HEADERS)},
        'rows': [{'values': [cell(value) for value in row]} for row in rows],
        'fields': 'userEnteredValue'}})
    requests.append({'setBasicFilter': {'filter': {'range': {
        'sheetId': sheet_id, 'startRowIndex': 0, 'endRowIndex': len(rows),
        'startColumnIndex': 0, 'endColumnIndex': len(HEADERS)}}}})
    requests.append({'repeatCell': {
        'range': {'sheetId': sheet_id, 'startRowIndex': 0, 'endRowIndex': 1},
        'cell': {'userEnteredFormat': {'backgroundColor': {'red': .09, 'green': .15, 'blue': .12},
                  'textFormat': {'bold': True, 'foregroundColor': {'red': 1, 'green': 1, 'blue': 1}}}},
        'fields': 'userEnteredFormat'}})
    request('POST', base + ':batchUpdate', json={'requests': requests})
    result = request('GET', base + "/values/'HQ%20Data'!A:A",
                     params={'valueRenderOption': 'UNFORMATTED_VALUE'})
    ids = [str(row[0]) for row in result.get('values', [])[1:] if row]
    if ids != [str(row[0]) for row in rows[1:]]:
        raise RuntimeError('Sheet read-back IDs differ; retry sync before reporting success')
    print(f'Google Sheet synced and verified: {len(rows)-1} records. https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--atlas', type=Path, default=ROOT)
    parser.add_argument('--export', type=Path, help='Write a CSV without Google authentication')
    parser.add_argument('--if-configured', action='store_true')
    args = parser.parse_args()
    if args.export:
        with args.export.open('w', encoding='utf-8-sig', newline='') as handle:
            csv.writer(handle).writerows(table(args.atlas))
        print(f'Exported {args.export}')
    elif args.if_configured:
        sync_if_configured(args.atlas)
    else:
        config = configuration(args.atlas)
        if not config.get('spreadsheet_id'):
            raise SystemExit('Set LASTZ_SPREADSHEET_ID or .google-sheets.json before syncing')
        sync(args.atlas, config)


if __name__ == '__main__':
    main()

import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch
import sync_google_sheet as sync


class SheetSyncTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.atlas = Path(self.temp.name)
        (self.atlas/'data').mkdir()
        self.records = [
            {'id': 7, 'name': '=1+1', 'hq': 24, 'current': False,
             'roster_current': True, 'x': None, 'y': None},
            {'id': 2, 'name': 'Historical', 'current': False},
        ]
        self.write('hqs.json', self.records)
        self.write('power.json', {'captured_date': '2026-10-04', 'players': {'a': {
            'atlas_id': 7, 'personal_power': {'value': 49300000,
            'approximate': True, 'captured_date': '2026-10-01'}}}})

    def write(self, name, data):
        (self.atlas/'data'/name).write_text(json.dumps(data), encoding='utf8')

    def test_dates_unknown_locations_and_historical_status(self):
        rows = sync.table(self.atlas)
        self.assertEqual([r[0] for r in rows[1:]], [2, 7])
        p = dict(zip(rows[0], rows[2]))
        self.assertEqual(p['X'], '')
        self.assertEqual(p['Personal power date'], '2026-10-01')
        self.assertTrue(p['Power approximate'])
        self.assertEqual(p['Previous SvS shield'], 'unscanned')
        self.assertEqual(p['Shield date'], '')
        self.assertIn('Historical', rows[1][9])

    def test_duplicate_ids_rejected(self):
        self.write('hqs.json', self.records + self.records[:1])
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            sync.table(self.atlas)

    def test_atomic_replacement_literal_names_and_readback(self):
        requests = []
        class Response:
            ok = True
            def __init__(self, value): self.value = value
            def json(self): return self.value
        class Session:
            def __init__(self, credentials): pass
            def request(self, method, url, **kwargs):
                requests.append((method, url, kwargs))
                if method == 'POST': return Response({})
                if '/values/' in url:
                    return Response({'values': [['Atlas ID'], [2], [7]]})
                return Response({'sheets': [{'properties': {
                    'sheetId': 42, 'title': 'HQ Data',
                    'gridProperties': {'rowCount': 2000, 'columnCount': 30}}},
                    {'properties': {'sheetId': 99, 'title': 'Manual Notes'}}]})
        google = types.ModuleType('google')
        auth = types.ModuleType('google.auth')
        auth.default = lambda **kwargs: (object(), None)
        google.auth = auth
        transport = types.ModuleType('google.auth.transport')
        request_module = types.ModuleType('google.auth.transport.requests')
        request_module.AuthorizedSession = Session
        with patch.dict(sys.modules, {'google': google, 'google.auth': auth,
                        'google.auth.transport': transport,
                        'google.auth.transport.requests': request_module}):
            sync.sync(self.atlas, {'spreadsheet_id': 'test'})
        posts = [r for r in requests if r[0] == 'POST']
        self.assertEqual(len(posts), 1)
        edits = posts[0][2]['json']['requests']
        values = next(r['updateCells'] for r in edits if 'updateCells' in r)
        self.assertEqual(values['range']['sheetId'], 42)
        self.assertEqual(values['range']['endRowIndex'], 2000)
        self.assertEqual(values['rows'][2]['values'][1],
                         {'userEnteredValue': {'stringValue': '=1+1'}})
        self.assertNotIn('99', json.dumps(edits))


if __name__ == '__main__': unittest.main()

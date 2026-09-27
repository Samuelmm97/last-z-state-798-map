"""Import a shield-scan CSV into the static Field Atlas.

Usage: python import_shields.py --csv path/to/svs_shield_status.csv
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VALID_STATUS = {'shielded', 'unshielded', 'review', 'not_applicable', 'not_hq'}
VALID_TERRAIN = {'grass', 'mud', 'review'}


def hex_distance(hq):
    j = hq['y'] - 500
    i = hq['x'] - 500 - j / 2
    return max(abs(i), abs(j), abs(i + j))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--csv', type=Path, required=True)
    parser.add_argument('--atlas', type=Path, default=ROOT / 'data/hqs.json')
    parser.add_argument('--out', type=Path, default=ROOT / 'data/shields.json')
    args = parser.parse_args()

    hqs = {int(hq['id']): hq for hq in json.loads(args.atlas.read_text(encoding='utf-8'))}
    items = []
    seen = set()
    with args.csv.open(encoding='utf-8-sig', newline='') as stream:
        for row in csv.DictReader(stream):
            hq_id = int(row['id'])
            if hq_id in seen or hq_id not in hqs:
                raise ValueError(f'Duplicate or unknown atlas HQ ID: {hq_id}')
            seen.add(hq_id)
            hq = hqs[hq_id]
            if (int(row['x']), int(row['y'])) != (hq['x'], hq['y']):
                raise ValueError(f'Coordinates changed for HQ {hq_id}; rebuild the shield scan')
            if row['shield_status'] not in VALID_STATUS or row['terrain'] not in VALID_TERRAIN:
                raise ValueError(f'Unknown shield or terrain status for HQ {hq_id}')
            items.append({
                'id': hq_id,
                'status': row['shield_status'],
                'terrain': row['terrain'],
                'observedAt': row['captured_at'],
                'source': row['screenshot'],
                'note': row['note'],
            })
    # The scanner searches the terrain edge with an inward margin. HQs well
    # inside that hexagon are unambiguously on mud and cannot have shields.
    for hq_id, hq in hqs.items():
        if hq_id not in seen and hq.get('zone') == 'capital' and hex_distance(hq) < 30:
            items.append({
                'id': hq_id, 'status': 'not_applicable', 'terrain': 'mud',
                'observedAt': '', 'source': hq['source'],
                'note': 'Inside the capital mud hexagon; shields unavailable',
            })
    items.sort(key=lambda item: item['id'])
    args.out.write_text(json.dumps(items, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    print(f'Imported {len(items)} shield observations to {args.out}')


if __name__ == '__main__':
    main()

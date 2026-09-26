"""Append HQs recovered by the badge audit and direct screenshot review."""
import csv
import json
import re
from pathlib import Path

from PIL import Image
from build_assets import ROOT, SOURCE, nearest_observation, make_photo

CAPITAL = SOURCE / 'capital-radius-100'
MANUAL = [
    dict(alliance_tag='Helm', player_name='Samuelm', estimated_city_x=481,
         estimated_city_y=510, hq_level=26, source_image='s798_x0476_y0504.png',
         observation={'x': 1250, 'w': 160, 'y': 760}, review='user_coordinate_visual_name_level'),
    dict(alliance_tag='Helm', player_name='Imperial XXI', estimated_city_x=488,
         estimated_city_y=485, hq_level=27, source_image='s798_x0493_y0492.png',
         observation={'x': 530, 'w': 150, 'y': 305}, review='visually_reviewed_missing'),
]


def main():
    data_path = ROOT / 'data' / 'hqs.json'
    current = json.loads(data_path.read_text(encoding='utf-8'))
    original = [row for row in current if row.get('review') not in
                {'hq_badge_recovery', 'user_coordinate_visual_name_level', 'visually_reviewed_missing'}]
    if len(original) != 3329:
        raise RuntimeError(f'Expected 3,329 original atlas records, got {len(original)}')
    additions = list(csv.DictReader((CAPITAL / 'new_hq_candidates_review.csv').open(encoding='utf-8-sig')))
    for row in MANUAL:
        additions.append(row)
    records = list(original)
    for index, row in enumerate(additions, start=len(original)):
        source = row['source_image']
        obs = row.get('observation') or nearest_observation(
            {'estimated_city_x': row['estimated_city_x'],
             'estimated_city_y': row['estimated_city_y'],
             'player_name': row['player_name']}, source)
        match = re.fullmatch(r's798_x(\d{4})_y(\d{4})\.png', source)
        if not match:
            raise ValueError(source)
        capture_x, capture_y = map(int, match.groups())
        with Image.open(SOURCE / source) as image:
            photo = make_photo(image.convert('RGB'), obs, row, capture_x, capture_y)
            photo.save(ROOT / 'hq' / f'{index:04}.webp', 'WEBP', quality=86, method=4)
        records.append(dict(id=index, name=row['player_name'], tag=row['alliance_tag'],
                            x=int(row['estimated_city_x']), y=int(row['estimated_city_y']),
                            hq=int(row['hq_level']) if row['hq_level'] else None,
                            review=row.get('review') or 'hq_badge_recovery', zone='capital',
                            photo=f'hq/{index:04}.webp', source=source))
        if (index-len(original)+1) % 50 == 0:
            print(f'{index-len(original)+1}/{len(additions)} new HQ photos', flush=True)
    data_path.write_text(json.dumps(records, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    metadata_path = ROOT / 'data' / 'map.json'
    metadata = json.loads(metadata_path.read_text(encoding='utf-8'))
    metadata['hqCount'] = len(records)
    metadata['capitalCount'] = sum(r.get('zone') == 'capital' for r in records)
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    with (CAPITAL / 'names_tags_coordinates_hq.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, ['name', 'alliance_tag', 'x', 'y', 'hq_level', 'source_image'])
        writer.writeheader()
        for row in records:
            if row.get('zone') != 'capital':
                continue
            writer.writerow(dict(name=row['name'], alliance_tag=row['tag'], x=row['x'], y=row['y'],
                                 hq_level=row['hq'], source_image=row['source']))
    print('capital HQ candidates:', metadata['capitalCount'], flush=True)


if __name__ == '__main__':
    main()

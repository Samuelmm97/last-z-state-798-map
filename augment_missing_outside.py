"""Append outside-capital HQs recovered by the full-map badge audit."""
import csv
import json
import re
from pathlib import Path
from PIL import Image
from build_assets import ROOT, SOURCE, nearest_observation, make_photo

INPUT = SOURCE / 'outside_missing_hq_candidates_review.csv'
BASE_COUNT = 3485


def main(photos=True):
    data_path = ROOT / 'data' / 'hqs.json'
    current = json.loads(data_path.read_text(encoding='utf-8'))
    original = [row for row in current if row.get('review') != 'outside_hq_badge_recovery']
    if len(original) != BASE_COUNT:
        raise RuntimeError(f'Expected {BASE_COUNT} current records, found {len(original)}')
    additions = list(csv.DictReader(INPUT.open(encoding='utf-8-sig', newline='')))
    records = list(original)
    for index, row in enumerate(additions, start=len(original)):
        source = row['source_image']
        obs = nearest_observation(row, source)
        match = re.fullmatch(r's798_x(\d{4})_y(\d{4})\.png', source)
        if not match:
            raise ValueError(source)
        capture_x, capture_y = map(int, match.groups())
        photo_path = ROOT / 'hq' / f'{index:04}.webp'
        if photos:
            with Image.open(SOURCE / source) as image:
                photo = make_photo(image.convert('RGB'), obs, row, capture_x, capture_y)
                photo.save(photo_path, 'WEBP', quality=86, method=4)
        elif not photo_path.exists():
            raise FileNotFoundError(photo_path)
        records.append(dict(id=index, name=row['player_name'], tag=row['alliance_tag'],
                            x=int(row['estimated_city_x']), y=int(row['estimated_city_y']),
                            hq=int(row['hq_level']) if row['hq_level'] else None,
                            review='outside_hq_badge_recovery', zone='outside',
                            photo=f'hq/{index:04}.webp', source=source))
        if (index-len(original)+1) % 50 == 0:
            print(f'{index-len(original)+1}/{len(additions)} photos', flush=True)
    data_path.write_text(json.dumps(records, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    metadata_path = ROOT / 'data' / 'map.json'
    metadata = json.loads(metadata_path.read_text(encoding='utf-8'))
    metadata['hqCount'] = len(records)
    metadata['outsideCount'] = sum(r.get('zone', 'outside') == 'outside' for r in records)
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    outside = [row for row in records if row.get('zone', 'outside') == 'outside']
    for path in (SOURCE / 'radius-100' / 'names_tags_coordinates_hq.csv',
                 SOURCE / 'names_tags_coordinates_hq_radius100.csv'):
        fields = ['name', 'alliance_tag', 'x', 'y', 'hq_level']
        if path.parent.name == 'radius-100':
            fields.append('source_image')
        with path.open('w', encoding='utf-8-sig', newline='') as stream:
            writer = csv.DictWriter(stream, fields)
            writer.writeheader()
            for row in outside:
                values = dict(name=row['name'], alliance_tag=row['tag'], x=row['x'], y=row['y'],
                              hq_level=row['hq'])
                if 'source_image' in fields:
                    values['source_image'] = row['source']
                writer.writerow(values)
    print('outside HQ candidates:', len(outside), flush=True)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--metadata-only', action='store_true')
    args = parser.parse_args()
    main(photos=not args.metadata_only)

"""Append capital-circle headquarters and original capture photos to the atlas."""
import csv
import json
import re
from pathlib import Path

from PIL import Image
from build_assets import ROOT, SOURCE, nearest_observation, make_photo

CAPITAL = SOURCE / 'capital-radius-100'
DISPLAY_CORRECTIONS = {"4NGlKingAzzam": ('KingAzzam', '4NG')}


def main(photos=True):
    inventory = [row for row in csv.DictReader((CAPITAL / 'name_candidates.csv').open(encoding='utf-8-sig', newline=''))
                 if row['player_name'] != "3,348 ea.,'euunnar"]
    with (CAPITAL / 'reviewed_name_candidates.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, list(inventory[0]))
        writer.writeheader(); writer.writerows(inventory)
    levels = {(row['alliance_tag'].casefold(), row['player_name'].casefold()): row for row in
              csv.DictReader((CAPITAL / 'hq_level_readings.csv').open(encoding='utf-8-sig', newline=''))}
    data_path = ROOT / 'data' / 'hqs.json'
    existing = json.loads(data_path.read_text(encoding='utf-8'))
    outside = [row for row in existing if row.get('zone', 'outside') == 'outside']
    if len(outside) != 2658:
        raise RuntimeError('Outside capital inventory changed unexpectedly')
    records = list(outside)
    for index, row in enumerate(inventory, start=len(outside)):
        level = levels[row['alliance_tag'].casefold(), row['player_name'].casefold()]
        choices = []
        for name in row['source_images'].split('; '):
            item = nearest_observation(row, name)
            if item is None:
                continue
            center_x, center_y = item['x'] + item['w']/2, item['y']
            margin = min(center_x, 1938-center_x, center_y-40, 950-center_y)
            preference = 25 if name == level['hq_source_image'] else 0
            choices.append((margin+preference, name, item))
        if choices:
            _, name, item = max(choices)
        else:
            name, item = row['source_images'].split('; ')[0], None
        match = re.fullmatch(r's798_x(\d{4})_y(\d{4})\.png', name)
        if not match:
            raise ValueError(name)
        capture_x, capture_y = map(int, match.groups())
        photo_path = ROOT / 'hq' / f'{index:04}.webp'
        if photos:
            with Image.open(SOURCE / name) as image:
                photo = make_photo(image.convert('RGB'), item, row, capture_x, capture_y)
                photo.save(photo_path, 'WEBP', quality=86, method=4)
        elif not photo_path.exists():
            raise FileNotFoundError(photo_path)
        display_name, display_tag = DISPLAY_CORRECTIONS.get(
            row['player_name'], (row['player_name'], row['alliance_tag']))
        records.append(dict(id=index, name=display_name, tag=display_tag,
                            x=int(row['estimated_city_x']), y=int(row['estimated_city_y']),
                            hq=int(level['hq_level']) if level['hq_level'] else None,
                            review=row['review_status'], zone='capital',
                            photo=f'hq/{index:04}.webp', source=name))
        if (index-len(outside)+1) % 100 == 0:
            print(f'{index-len(outside)+1}/{len(inventory)} photos', flush=True)
    data_path.write_text(json.dumps(records, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    map_path = ROOT / 'data' / 'map.json'
    metadata = json.loads(map_path.read_text(encoding='utf-8'))
    metadata['hqCount'] = len(records)
    metadata['outsideCount'] = len(outside)
    metadata['capitalCount'] = len(inventory)
    map_path.write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    with (CAPITAL / 'names_tags_coordinates_hq.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, ['name', 'alliance_tag', 'x', 'y', 'hq_level', 'source_image'])
        writer.writeheader()
        for row in records[len(outside):]:
            writer.writerow({key: value for key, value in row.items()
                             if key in ('name', 'alliance_tag', 'x', 'y', 'hq_level', 'source_image')}
                            | {'alliance_tag': row['tag'], 'hq_level': row['hq'], 'source_image': row['source']})
    print('capital assets complete:', len(inventory), flush=True)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--metadata-only', action='store_true')
    args = parser.parse_args()
    main(photos=not args.metadata_only)

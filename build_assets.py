"""Build a browser-sized stitched map and one original capture crop per HQ.

Run with the Python environment used by the Last Z desktop automation.
The 5,100 full screenshots remain in the user's local capture archive.
"""
from __future__ import annotations

import csv
import json
import math
import re
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent
SOURCE = Path(r'C:\Users\menag\Documents\Codex\2026-09-25\ca\outputs\Last-Z-map-sweep-captures')
INVENTORY = SOURCE / 'radius-100' / 'reviewed_name_candidates.csv'
HQ = SOURCE / 'radius-100' / 'hq_level_reviewed.csv'
SCALE_X, SCALE_Y = 16.0, 10.5
WORLD_SIZE = 1000
WIDTH, HEIGHT = int(WORLD_SIZE * SCALE_X), int(WORLD_SIZE * SCALE_Y)
MAX_ZOOM = 6
# Measured from overlapping captures; the small remaining drift creates seams.
SCREEN_X_PER_WORLD_X = 73.5
SCREEN_X_PER_WORLD_Y = -2.0
SCREEN_Y_PER_WORLD_Y = 45.4
ANCHOR_X, ANCHOR_Y = 972.0, 621.5


def nearest_observation(row: dict, image_name: str):
    match = re.fullmatch(r's798_x(\d{4})_y(\d{4})\.png', image_name)
    if not match:
        return None
    capture_x, capture_y = map(int, match.groups())
    path = SOURCE / 'ocr' / image_name.replace('.png', '.json')
    if not path.exists():
        return None
    items = json.loads(path.read_text(encoding='utf-8'))
    if not items:
        return None
    world_x, world_y = int(row['estimated_city_x']), int(row['estimated_city_y'])
    ranked = []
    for item in items:
        est_x = capture_x + (item['x']+item['w']/2-ANCHOR_X) / SCREEN_X_PER_WORLD_X
        est_y = capture_y + (item['y']+item['h']/2-ANCHOR_Y) / SCREEN_Y_PER_WORLD_Y
        distance = math.hypot(est_x-world_x, est_y-world_y)
        similarity = SequenceMatcher(None, row['player_name'].casefold(), item['raw'].casefold()).ratio()
        ranked.append((distance - 1.5*similarity, distance, item))
    _, distance, item = min(ranked, key=lambda entry: entry[0])
    return item if distance <= 12 else None


def photo_assignments(rows, hq_rows):
    photos = defaultdict(list)
    records = []
    for index, row in enumerate(rows):
        key = (row['alliance_tag'].casefold(), row['player_name'].casefold())
        level_row = hq_rows[key]
        choices = []
        for name in row['source_images'].split('; '):
            item = nearest_observation(row, name)
            if item is None:
                continue
            center_x = item['x'] + item['w']/2
            center_y = item['y']
            margin_x = min(center_x, 1938-center_x)
            margin_y = min(center_y-40, 950-center_y)
            preferred = 25 if name == level_row['hq_source_image'] else 0
            choices.append((min(margin_x, margin_y)+preferred, name, item))
        if choices:
            _, name, item = max(choices)
        else:
            name = row['source_images'].split('; ')[0]
            item = None
        photos[name].append((index, row, item))
        records.append(dict(id=index, name=row['player_name'], tag=row['alliance_tag'],
                            x=int(row['estimated_city_x']), y=int(row['estimated_city_y']),
                            hq=int(level_row['hq_level']),
                            review=row['review_status'], photo=f'hq/{index:04}.webp',
                            source=name))
    return photos, records


def make_photo(image: Image.Image, item: dict | None, row: dict, capture_x: int, capture_y: int):
    if item:
        center_x = item['x'] + item['w']/2 + 12
        name_y = item['y']
    else:
        center_x = ANCHOR_X + SCREEN_X_PER_WORLD_X*(int(row['estimated_city_x'])-capture_x)
        name_y = ANCHOR_Y + SCREEN_Y_PER_WORLD_Y*(int(row['estimated_city_y'])-capture_y)
    width, height = 420, 260
    left = max(0, min(image.width-width, round(center_x-width/2)))
    top = max(40, min(950-height, round(name_y-130)))
    return image.crop((left, top, left+width, top+height))


def partitions(values):
    bounds = []
    for index, value in enumerate(values):
        lower = 0 if index == 0 else (values[index-1]+value)/2
        upper = WORLD_SIZE if index == len(values)-1 else (value+values[index+1])/2
        bounds.append((lower, upper))
    return bounds


def stitch(photos):
    xs = list(range(0, WORLD_SIZE, 17))
    ys = list(range(0, WORLD_SIZE, 12))
    if xs[-1] != 999:
        xs.append(999)
    if ys[-1] != 999:
        ys.append(999)
    if len(xs)*len(ys) != 5100:
        raise RuntimeError(f'Unexpected capture grid: {len(xs)} × {len(ys)}')
    x_bounds, y_bounds = partitions(xs), partitions(ys)
    scratch = ROOT / '_build'
    scratch.mkdir(exist_ok=True)
    path = scratch / 'map-z6.rgb'
    image = np.memmap(path, dtype=np.uint8, mode='w+', shape=(HEIGHT, WIDTH, 3))
    (ROOT / 'hq').mkdir(exist_ok=True)
    completed_photos = set()
    for yi, (cy, (wy0, wy1)) in enumerate(zip(ys, y_bounds)):
        py0, py1 = round(wy0*SCALE_Y), round(wy1*SCALE_Y)
        for xi, (cx, (wx0, wx1)) in enumerate(zip(xs, x_bounds)):
            px0, px1 = round(wx0*SCALE_X), round(wx1*SCALE_X)
            name = f's798_x{cx:04}_y{cy:04}.png'
            with Image.open(SOURCE / name) as source_image:
                source_image = source_image.convert('RGB')
                world_x0, world_y0 = px0/SCALE_X, py0/SCALE_Y
                affine = (
                    SCREEN_X_PER_WORLD_X/SCALE_X,
                    SCREEN_X_PER_WORLD_Y/SCALE_Y,
                    ANCHOR_X + SCREEN_X_PER_WORLD_X*(world_x0-cx)
                    + SCREEN_X_PER_WORLD_Y*(world_y0-cy),
                    0.0,
                    SCREEN_Y_PER_WORLD_Y/SCALE_Y,
                    ANCHOR_Y + SCREEN_Y_PER_WORLD_Y*(world_y0-cy),
                )
                patch = source_image.transform((px1-px0, py1-py0),
                                               Image.Transform.AFFINE, affine,
                                               resample=Image.Resampling.BICUBIC)
                image[py0:py1, px0:px1] = np.asarray(patch)
                for index, row, item in photos.get(name, []):
                    photo = make_photo(source_image, item, row, cx, cy)
                    photo.save(ROOT / 'hq' / f'{index:04}.webp', 'WEBP', quality=86, method=4)
                    completed_photos.add(index)
            if (yi*len(xs)+xi+1) % 300 == 0:
                print(f'stitched {yi*len(xs)+xi+1}/5100 captures; '
                      f'{len(completed_photos)} HQ photos', flush=True)
    image.flush()
    print(f'stitched {len(xs)*len(ys)} captures; {len(completed_photos)} HQ photos', flush=True)
    return image, path, len(completed_photos)


def save_tiles(level: int, pixels: np.ndarray):
    height, width = pixels.shape[:2]
    destination = ROOT / 'tiles' / str(level)
    total = 0
    for tile_x in range(math.ceil(width/256)):
        folder = destination / str(tile_x)
        folder.mkdir(parents=True, exist_ok=True)
        for tile_y in range(math.ceil(height/256)):
            crop = np.asarray(pixels[tile_y*256:min(height,(tile_y+1)*256),
                                     tile_x*256:min(width,(tile_x+1)*256)])
            Image.fromarray(crop).save(folder / f'{tile_y}.webp', 'WEBP', quality=78, method=4)
            total += 1
    print(f'zoom {level}: {width}×{height}, {total} tiles', flush=True)


def pyramid(full, path, start_level=MAX_ZOOM):
    current = full
    current_path = path
    for level in range(start_level, -1, -1):
        save_tiles(level, current)
        if level > 0:
            height, width = current.shape[:2]
            next_width, next_height = math.ceil(width/2), math.ceil(height/2)
            reduced = cv2.resize(current, (next_width, next_height), interpolation=cv2.INTER_AREA)
            next_path = ROOT / '_build' / f'map-z{level-1}.rgb'
            next_map = np.memmap(next_path, dtype=np.uint8, mode='w+',
                                 shape=(next_height, next_width, 3))
            next_map[:] = reduced
            next_map.flush()
            del current
            del reduced
            current, current_path = next_map, next_path
    del current


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--resume-tiles-from', type=int)
    args = parser.parse_args()
    if args.resume_tiles_from is not None:
        level = args.resume_tiles_from
        if not 0 <= level <= MAX_ZOOM:
            raise ValueError('Invalid zoom level')
        factor = 2 ** (MAX_ZOOM-level)
        width, height = math.ceil(WIDTH/factor), math.ceil(HEIGHT/factor)
        path = ROOT / '_build' / f'map-z{level}.rgb'
        image = np.memmap(path, dtype=np.uint8, mode='r', shape=(height,width,3))
        pyramid(image, path, level)
        print('site assets complete', flush=True)
        return
    rows = list(csv.DictReader(INVENTORY.open(encoding='utf-8-sig', newline='')))
    hq_rows = {(row['alliance_tag'].casefold(), row['player_name'].casefold()): row
               for row in csv.DictReader(HQ.open(encoding='utf-8-sig', newline=''))}
    if len(rows) != 2658 or len(hq_rows) != 2658:
        raise RuntimeError('Expected the completed radius-100 inventory')
    photo_tasks, records = photo_assignments(rows, hq_rows)
    (ROOT / 'data').mkdir(exist_ok=True)
    (ROOT / 'data' / 'hqs.json').write_text(json.dumps(records, ensure_ascii=False,
                                                       separators=(',', ':')), encoding='utf-8')
    (ROOT / 'data' / 'map.json').write_text(json.dumps(dict(width=WIDTH, height=HEIGHT,
                                                            scaleX=SCALE_X, scaleY=SCALE_Y,
                                                            maxZoom=MAX_ZOOM, hqCount=len(records)),
                                                       indent=2), encoding='utf-8')
    full, path, photo_count = stitch(photo_tasks)
    if photo_count != len(rows):
        raise RuntimeError(f'Missing HQ crops: {len(rows)-photo_count}')
    pyramid(full, path)
    print('site assets complete', flush=True)


if __name__ == '__main__':
    main()

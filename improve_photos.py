"""Replace HQ photos near UI edges with clearer neighboring captures."""
import csv
import json
import math
import re
from difflib import SequenceMatcher
from pathlib import Path

from PIL import Image

from build_assets import (ROOT, SOURCE, INVENTORY, nearest_observation,
                          make_photo, ANCHOR_X, ANCHOR_Y,
                          SCREEN_X_PER_WORLD_X, SCREEN_Y_PER_WORLD_Y)

xs = set(range(0, 1000, 17)) | {999}
ys = set(range(0, 1000, 12)) | {999}
rows = {(row['alliance_tag'].casefold(), row['player_name'].casefold()): row
        for row in csv.DictReader(INVENTORY.open(encoding='utf-8-sig', newline=''))}
data_path = ROOT / 'data' / 'hqs.json'
records = json.loads(data_path.read_text(encoding='utf-8'))


def margin(obs):
    return min(obs['x'], 1938-obs['x']-obs['w'], obs['y']-40, 950-obs['y']-obs['h']-35)


updated = 0
for record in records:
    row = rows[record['tag'].casefold(), record['name'].casefold()]
    old = nearest_observation(row, record['source'])
    if old is None or (250 <= old['x'] <= 1600 and 200 <= old['y'] <= 790):
        continue
    match = re.fullmatch(r's798_x(\d{4})_y(\d{4})\.png', record['source'])
    cx, cy = map(int, match.groups())
    candidates = [(margin(old), record['source'], old)]
    for dx in (-17, 0, 17):
        for dy in (-12, 0, 12):
            nx, ny = cx+dx, cy+dy
            if (nx,ny)==(cx,cy) or nx not in xs or ny not in ys:
                continue
            name = f's798_x{nx:04}_y{ny:04}.png'
            obs = nearest_observation(row, name)
            if not obs:
                continue
            est_x = nx + (obs['x']+obs['w']/2-ANCHOR_X)/SCREEN_X_PER_WORLD_X
            est_y = ny + (obs['y']+obs['h']/2-ANCHOR_Y)/SCREEN_Y_PER_WORLD_Y
            if math.hypot(est_x-record['x'], est_y-record['y']) > 2.7:
                continue
            tail = re.split(r'[\])]\s*', obs['raw'])[-1]
            similarity = SequenceMatcher(None, record['name'].casefold(), tail.casefold()).ratio()
            if record['name'].casefold() not in obs['raw'].casefold() and similarity < .7:
                continue
            candidates.append((margin(obs), name, obs))
    score, name, obs = max(candidates)
    if name == record['source'] or score < margin(old)+70:
        continue
    nx = int(name.split('_x')[1].split('_y')[0])
    ny = int(name.split('_y')[1].split('.')[0])
    with Image.open(SOURCE / name) as image:
        photo = make_photo(image.convert('RGB'), obs, row, nx, ny)
        photo.save(ROOT / record['photo'], 'WEBP', quality=86, method=4)
    record['source'] = name
    updated += 1

data_path.write_text(json.dumps(records, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
print('improved HQ photos', updated)

from pathlib import Path
from PIL import Image, ImageChops, ImageStat

root = Path(__file__).resolve().parent
source = Image.open(root / 'en005-source.jpg').convert('RGB')
rows = []
for name in ['en005-maxres.jpg', 'en005-hq.jpg', 'en001-maxres.jpg', 'en003-maxres.jpg', 'en006-maxres.jpg']:
    image = Image.open(root / name).convert('RGB')
    resized = image.resize(source.size)
    diff = ImageChops.difference(source, resized)
    mean = sum(ImageStat.Stat(diff).mean) / 3
    bbox = diff.getbbox()
    rows.append({'file': name, 'size': image.size, 'mean_abs_difference': round(mean, 4), 'identical': mean == 0.0, 'diff_bbox': bbox})
print(rows)

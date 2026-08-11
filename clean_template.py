#!/usr/bin/env python3
"""Safely cover example images with white rectangles without destroying text."""
import sys
from pathlib import Path
import fitz
import shutil
from PIL import Image
import io

src = Path('/home/hamzaelnajmi/report-agent/templates/template final.pdf')
out = Path('/home/hamzaelnajmi/report-agent/templates/template final.pdf')
tmp = Path('/home/hamzaelnajmi/report-agent/templates/template final_cover.pdf')

if not src.exists():
    print('ERROR: source template missing')
    sys.exit(1)

# Backup for verification
backup = Path('/tmp/template_backup_verify.pdf')
shutil.copy2(src, backup)

doc = fitz.open(str(src))
print('Template:', len(doc), 'pages')

for i in range(1, len(doc)):
    page = doc[i]
    covered = 0
    for img in page.get_images(full=True):
        if img[0] == 4:
            continue
        try:
            pix = fitz.Pixmap(doc, img[0])
            w, h = pix.width, pix.height
            pix = None
        except Exception:
            continue
        if not (w > 50 and h > 50):
            continue
        try:
            bbox = page.get_image_bbox(img)
        except Exception:
            continue
        if bbox.is_empty:
            continue
        rect = fitz.Rect(bbox.x0 + 1, bbox.y0 + 1, bbox.x1 - 1, bbox.y1 - 1)
        page.draw_rect(rect, color=(1, 1, 1), fill=(1, 1, 1), width=0, overlay=True)
        covered += 1
        print(f'  Covered page {i+1} xref={img[0]} {w}x{h}')
    if covered:
        print(f'  Page {i+1}: covered {covered} images')

doc.save(str(tmp), garbage=4, deflate=True)
doc.close()

shutil.copy2(str(tmp), str(src))
tmp.unlink()

# Verification
print('\nVerification after overlay:')
doc2 = fitz.open(str(src))
for i in range(len(doc2)):
    imgs = doc2[i].get_images(full=True)
    text = doc2[i].get_text()
    print(f'  Page {i+1}: {len(imgs)} images, {len(text)} chars')
doc2.close()

# Verify backup still has all text
doc3 = fitz.open(str(backup))
text_backup = sum(len(p.get_text()) for p in doc3)
print(f'Backup text preserved: {text_backup} chars')
doc3.close()

print('Done')

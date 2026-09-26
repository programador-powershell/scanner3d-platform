"""Index every source sheet without asserting that a reconstructed model exists."""
import argparse
import hashlib
import json
import re
from pathlib import Path
from PIL import Image, ImageDraw, ImageOps


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', default='F:/Alice/prototipo')
    parser.add_argument('--output', default='F:/Alice/Deliverables/Alice_Variants')
    args = parser.parse_args()
    root, out = Path(args.source), Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    variants = []
    final_sheet = Image.new('RGB', (1500, 1000), '#151519')
    draw_final = ImageDraw.Draw(final_sheet)
    for index, directory in enumerate(sorted(root.iterdir(), key=lambda p: p.name.lower())):
        if not directory.is_dir():
            continue
        images = sorted(p for p in directory.iterdir() if p.suffix.lower() in {'.png', '.jpg', '.jpeg'})
        stages, references = [], []
        for file in images:
            with Image.open(file) as image:
                size = list(image.size)
            item = {'file': str(file), 'sha256': hashlib.sha256(file.read_bytes()).hexdigest(), 'size': size}
            match = re.search(r'\((\d+)\)\.[^.]+$', file.name)
            if file.name.startswith('ChatGPT Image') and match:
                item['number'] = int(match[1])
                stages.append(item)
            else:
                references.append(item)
        stages.sort(key=lambda item: item['number'])
        if [item['number'] for item in stages] != list(range(1, 11)):
            raise ValueError(f'Missing or duplicate layer sheet: {directory}')
        slug = directory.name.lower().replace(' ', '_')
        dest = out / slug
        dest.mkdir(exist_ok=True)
        contact = Image.new('RGB', (1500, 1040), '#151519')
        draw = ImageDraw.Draw(contact)
        for slot, item in enumerate(stages):
            with Image.open(item['file']) as image:
                thumb = ImageOps.contain(image.convert('RGB'), (294, 480))
            x, y = (slot % 5) * 300, (slot // 5) * 520
            contact.paste(thumb, (x + (300-thumb.width)//2, y+28))
            draw.text((x+8, y+7), f"{directory.name} / {item['number']:02d}", fill='white')
        contact.save(dest / 'reference_layers.jpg', quality=94)
        final = next((p for p in images if p.name.lower().startswith('alice-') and p.suffix.lower()=='.png'), Path(stages[0]['file']))
        if directory.name.lower()=='alice base':
            final = directory / 'Alice-3D.png'
        with Image.open(final) as image:
            thumb = ImageOps.contain(image.convert('RGB'), (490, 455))
        x, y = (index % 3)*500, (index//3)*500
        final_sheet.paste(thumb, (x+(500-thumb.width)//2, y+32))
        draw_final.text((x+8, y+8), directory.name, fill='white')
        variant = {'id':slug, 'name':directory.name, 'directory':str(directory), 'references':references,
                   'layerSheets':stages, 'finalReference':str(final), 'geometryStatus':'not_created_by_this_index',
                   'fidelityVerified':False}
        (dest/'references.json').write_text(json.dumps(variant, ensure_ascii=False, indent=2), encoding='utf-8')
        variants.append(variant)
    final_sheet.save(out/'all_versions.jpg', quality=94)
    inventory = {'source':str(root), 'variants':variants, 'variantCount':len(variants),
                 'layerSheetCount':sum(len(v['layerSheets']) for v in variants)}
    (out/'reference_inventory.json').write_text(json.dumps(inventory, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'variants':len(variants), 'layerSheets':inventory['layerSheetCount'], 'output':str(out)}))


if __name__ == '__main__':
    main()

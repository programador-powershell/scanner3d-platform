import hashlib, json, shutil
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
workspace = Path(__file__).resolve().parents[1]
repo = workspace / 'scanner3d-platform'
base = Path('F:/Alice/Deliverables/Alice_Variants/alice_chapeleiro/black_cloth_family_ivory_collision_v001')
out = repo / 'docs/alice-experiments/chapeleiro/black-cloth-motion-v001'
sha = lambda f: hashlib.sha256(Path(f).read_bytes()).hexdigest()
read = lambda f: json.loads(Path(f).read_text(encoding='utf-8'))
write = lambda f, r: Path(f).write_text(json.dumps(r, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
before, after = read(base / 'actual_receiver_review/comparison.json'), read(base / 'actual_receiver_review_v002/comparison.json')
assert before['probeDataSha256'] == after['probeDataSha256']
assert before['sourcePhotoSha256'] == after['sourcePhotoSha256']
assert after['parentGlbUnchanged'] and after['checkpointUnchanged']
assert 'Target vertices changed' not in (base / 'actual_receiver_review_v002.log').read_text(encoding='utf-8')
inventory = read(out / 'artifact_inventory.json')
def copy(file, relative, digest=None):
    file = Path(file)
    if digest: assert sha(file) == digest
    target = out / relative
    assert not target.exists()
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(file, target)
    assert sha(target) == sha(file)
    row = {'file': str(Path(relative).as_posix()), 'sha256': sha(target), 'bytes': target.stat().st_size}
    inventory['artifacts'].append(row)
    return row
for name, digest in [('executed_render.py', after['scriptSha256']), ('comparison.json', None)]:
    copy(base / 'actual_receiver_review_v002' / name, 'stable_thin_target/' + name, digest)
copy(base / 'actual_receiver_review_v002.log', 'stable_thin_target/actual_execution.log')
board = Image.new('RGB', (1760, 2280), (24, 26, 29))
draw = ImageDraw.Draw(board)
font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 21)
small = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 16)
draw.text((24, 20), 'CHAPELEIRO / SAIA PRETA / VÍNCULO DA RENDA / ENSAIO LOCAL SEM APROVAÇÃO', font=font, fill='white')
photo = Image.open(after['sourcePhoto']).convert('RGB')
photo.thumbnail((510, 1120))
board.paste(photo, (24, 80))
draw.text((24, 760), 'Foto original completa / etapa 01', font=small, fill='#e3d3b4')
for text, y in zip(['Antes: alvo de espessura instável.', 'Depois: alvo fino de 2.496 vértices.', 'Mesmo cache físico e mesmas poses.', 'A renda ainda apresenta pontas.', 'Babados e colisões não aprovados.', 'Não incorporado ao GLB do site.'], range(820, 1100, 40)):
    draw.text((24, y), text, font=small, fill='#e3d3b4')
draw.text((580, 65), 'Antes / vínculo rompido', font=font, fill='white')
draw.text((1160, 65), 'Depois / vínculo estável, forma ainda defeituosa', font=small, fill='white')
for i, (b, a) in enumerate(zip(before['renders'], after['renders'])):
    assert (b['sourcePhysicsFrame'], b['view'], b['scope']) == (a['sourcePhysicsFrame'], a['view'], a['scope'])
    assert max(abs(x - y) for x, y in zip(b['cameraPosition'], a['cameraPosition'])) < 1e-5
    assert a['actualStableLaceTargetVertices'] == [2496, 2496, 2496] and a['actualLaceBindingsPresent']
    copy(a['file'], 'stable_thin_target/renders/' + Path(a['file']).name, a['sha256'])
    for row, x in [(b, 580), (a, 1160)]:
        assert sha(row['file']) == row['sha256']
        im = Image.open(row['file']).convert('RGBA')
        im.thumbnail((530, 365))
        y = 110 + i * 420
        board.paste(im, (x, y), im)
        draw.text((x, y + 370), f"{row['scope']} / pose {row['sourcePhysicsFrame']} / {row['view']}", font=small, fill='white')
draw.text((24, 2230), 'Estabilidade do vínculo não aprova dobra, costura, renda, colisão, animação ou fidelidade. O exterior inteiro e os GLBs continuam preservados.', font=small, fill='#e3d3b4')
file = base / 'photo_vs_actual_lace_binding_before_after.jpg'
board.save(file, quality=94)
copy(file, file.name)
copy(__file__, 'executed_finish_stable_review.py')
controls = read(out / 'controls.json')
controls.update(stableLaceTargetReviewPending=False, actualStableTargetVertices=[2496, 2496, 2496],
                sameActualCacheRigAndCamerasBeforeAfter=True, actualLaceTargetTopologyWarningsAbsent=True,
                visibleDifferences=['A renda acompanha os alvos, mas forma pontas alongadas. Babados, costuras e contato entre camadas permanecem instáveis.'],
                responseBakedIntoGlb=False, fidelityVerified=False, clothCollisionVerified=False, motionVerified=False)
write(out / 'controls.json', controls)
write(out / 'artifact_inventory.json', inventory)
with (out / 'README.md').open('a', encoding='utf-8', newline='\n') as stream:
    stream.write('\nA [comparação com a foto completa e dez renders antes/depois](photo_vs_actual_lace_binding_before_after.jpg) usa o mesmo cache, rig e câmeras. Os novos alvos finos conservam 2.496 vértices nas cinco poses e o vínculo das três rendas permanece presente, sem os avisos de mudança de topologia. A renda ainda forma pontas alongadas e os babados continuam colapsados; a forma e a física foram rejeitadas. A próxima revisão deve tratar as costuras e a continuidade do suporte, sem promover esta simulação ao modelo publicado.\n')
print('ACTUAL_BLACK_STABLE_TARGET_REVIEW_PRESERVED', len(inventory['artifacts']))

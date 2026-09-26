"""Bind every stage to its own original photo; old geometry is excluded from progress."""
import argparse
import hashlib
import json
from pathlib import Path

STAGES = {
 'alice_base': ['Panorama de montagem', 'Camisa e fundação interna', 'Corsete e cintos', 'Anáguas e rendas', 'Saia externa e avental', 'Mangas, colar e punhos', 'Costas e laço', 'Meias e botas', 'Joias e acessórios', 'Tecidos e acabamentos'],
 'alice_chapeleiro': ['Fundação interna', 'Corpete verde e mangas', 'Avental creme e cartas', 'Saia verde externa', 'Anáguas pretas e rendas', 'Costas, laço e relógios', 'Cartola, cabelo e joias', 'Punhos, meias e botas', 'Materiais e acessórios', 'Montagem final'],
 'alice_cheshire': ['Panorama de montagem', 'Fundação interna', 'Corsete violeta', 'Mangas', 'Anáguas', 'Saia externa', 'Avental e emblema felino', 'Costas e laço', 'Orelhas, joias e acessórios', 'Botas, meias e materiais'],
 'alice_coelho': ['Panorama de montagem', 'Camisa, anáguas e meias da fundação', 'Corsete', 'Corpete e mangas', 'Avental creme com relógios', 'Anáguas e estrutura', 'Saia marinho externa', 'Costas e laço', 'Orelhas, relógios, punhos e botas', 'Tecidos e acabamentos'],
 'alice_lagarta': ['Frente, perfil e costas', 'Base interna creme', 'Corpete azul fechado', 'Estrutura da saia', 'Drapeados e cascatas azuis', 'Mangas longas franzidas', 'Costas, laço e drapeados', 'Lanternas, gemas, joias e botas', 'Tecidos e rendas', 'Montagem final'],
 'alice_rainha': ['Panorama de montagem', 'Base interna creme', 'Corsete vermelho', 'Mangas e decote', 'Estrutura da saia', 'Painéis vermelhos externos', 'Painéis frontais com corações', 'Costas e laço', 'Coroa, joias, punhos e botas', 'Tecidos e acabamentos'],
}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', default='F:/Alice/Deliverables/Alice_Variants')
    args = parser.parse_args()
    root = Path(args.root)
    inventory = json.loads((root/'reference_inventory.json').read_text(encoding='utf-8'))
    previous = json.loads((root/'stage_comparisons.json').read_text(encoding='utf-8')) if (root/'stage_comparisons.json').exists() else {}
    existing = {s['id']:s for s in previous.get('stages',[])}
    entries, rejected = [], []
    for variant in inventory['variants']:
        directory = root/variant['id']
        body = next(p for p in variant['references'] if Path(p['file']).name.lower()=='alice.jpg')
        photos = [(0, 'Corpo, rosto e cabelo', body)] + [(p['number'], STAGES[variant['id']][p['number']-1], p) for p in variant['layerSheets']]
        for number, label, photo in photos:
            source = Path(photo['file'])
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            if digest != photo['sha256']:
                raise ValueError(f'Source photo changed: {source}')
            entry = {'id': f"{variant['id']}_stage_{number:02d}", 'variant': variant['id'],
                            'number': number, 'label': label, 'sourcePhoto': str(source), 'sourcePhotoSha256': digest,
                            'status': 'awaiting_fresh_geometry_and_comparison', 'fidelityVerified': False,
                            'requiredEvidence': ['original_stage_photo', 'source_crop_if_used', 'actual_front_render',
                                                 'actual_side_render', 'actual_back_render', 'actual_threequarter_render',
                                                 'visible_difference_review'],
                            'review': None}
            entry['motionRequirements']={'rigRequired':True,'status':'pending',
                'requiredActions':['walk','run','jump','attack'],
                'clothFollowingRequired':True,'collisionChecksRequired':True,'motionVerified':False}
            old = existing.get(entry['id'])
            if old and old['sourcePhotoSha256']==digest:
                for field in ('comparison','review','status','motionRequirements'):
                    if field in old: entry[field]=old[field]
            entries.append(entry)
        for pattern in ('foundations_v*', 'skirt_layers_v*'):
            for folder in directory.glob(pattern):
                if not folder.is_dir():
                    continue
                record = {'status': 'rejected_reused_geometry', 'countsTowardGoal': False,
                          'reason': 'User requires fresh reconstruction from source photos and comparison to each stage photo.',
                          'preservedForInspectionOnly': True}
                (folder/'REJECTED.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
                rejected.append(str(folder))
    plan = {'status': 'in_progress', 'completed': False, 'fidelityVerified': False,
            'comparisonPolicy': 'Each stage is compared with its own original photo, never a substitute final-outfit image.',
            'freshGeometryPolicy': 'No prior GLB/FBX/BLEND as reconstruction input.', 'stages': entries,
            'motionPolicy':'All actual garment layers must be skinned to one compatible character rig; walk, run, jump and attack require deformation, cloth response and inter-layer collision review.',
            'excludedLegacyDrafts': rejected}
    (root/'stage_comparisons.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'photoBindings': len(entries), 'excludedReusedDrafts': len(rejected), 'completed': False}))

if __name__=='__main__':
    main()

"""Preserve native affine joint matrices; do not decompose/reconstruct them."""
from pathlib import Path
T=Path('F:/Alice/SharedProduction/Tools')
s=(T/'serve_coelho_true_walk_preview_v1175.cjs').read_text(encoding='utf-8-sig')
old="bone.matrix.copy(parent.clone().invert().multiply(desired.get(n)));bone.matrix.decompose(bone.position,bone.quaternion,bone.scale);bone.updateMatrixWorld(true)"
new="bone.matrixAutoUpdate=false;bone.matrix.copy(parent.clone().invert().multiply(desired.get(n)));bone.updateMatrixWorld(true)"
assert s.count(old)==1
s=s.replace(old,new).replace("version:'v1175',pid", "version:'v1179',pid").replace("local_server_v1175.json", "local_server_v1179.json")
p=T/'serve_coelho_exact_matrix_preview_v1179.cjs';assert not p.exists();p.write_text(s,encoding='utf-8')
print('NATIVE_AFFINE_MATRIX_PREVIEW_PREPARED_NOT_YET_BROWSER_VERIFIED')

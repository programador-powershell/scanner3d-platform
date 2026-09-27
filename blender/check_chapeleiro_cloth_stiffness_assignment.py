"""Check actual installed RNA material assignment without saving the checkpoint."""
import argparse, hashlib, json, shutil, sys
from pathlib import Path
import bpy
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--generation', required=True)
p.add_argument('--output', required=True)
a = p.parse_args(sys.argv[sys.argv.index('--') + 1:])
sha = lambda f: hashlib.sha256(Path(f).read_bytes()).hexdigest()
g = json.loads(Path(a.generation).read_text(encoding='utf-8'))
assert sha(g['editableBlend']) == g['editableBlendSha256']
out = Path(a.output)
assert not out.exists()
out.mkdir(parents=True)
bpy.ops.wm.open_mainfile(filepath=g['editableBlend'])
sys.path.insert(0, str(Path(__file__).parent))
from chapeleiro_cloth_material_settings import INPLANE_FIELDS, scale_inplane_stiffness
source = bpy.data.objects['01 / long ivory gathered petticoat / petticoat simulation midsurface']
settings = next(m for m in source.modifiers if m.type == 'CLOTH').settings
before = {name: getattr(settings, name) for name in INPLANE_FIELDS}
actual = scale_inplane_stiffness(settings, before, 8.)
assert all(abs(actual[name] / before[name] - 8.) < 1e-6 for name in INPLANE_FIELDS)
helper = Path(__file__).with_name('chapeleiro_cloth_material_settings.py')
report = {'actualBlenderVersion': bpy.app.version_string, 'before': before, 'requestedFactor': 8.,
          'actualAfter': actual, 'allSixActualRnaFieldsScaledExactlyOnce': True,
          'checkpointUnchanged': sha(g['editableBlend']) == g['editableBlendSha256'],
          'parentEditableSha256': g['editableBlendSha256'], 'scriptSha256': sha(__file__), 'helperSha256': sha(helper),
          'clothSimulationExecuted': False, 'notAMotionOrMaterialFidelityApproval': True}
(out / 'actual_assignment.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
shutil.copyfile(__file__, out / 'executed_check.py'); shutil.copyfile(helper, out / 'executed_helper.py')
print(json.dumps(report, indent=2), flush=True)

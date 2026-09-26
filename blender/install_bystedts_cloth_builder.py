"""Install the user-supplied original free add-on and register its asset library."""
import argparse
import hashlib
import json
import sys
from pathlib import Path
import bpy
import addon_utils

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--zip', required=True)
parser.add_argument('--output', required=True)
args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
archive = Path(args.zip).resolve()
expected = '132440c150ce09a04d5e7b19de57485cfcf0d630914fd63201c9835abca0dab8'
if hashlib.sha256(archive.read_bytes()).hexdigest() != expected:
    raise ValueError('Expected the supplied original Cloth Builder 1.0.1 zip.')
already_installed = any(m.__name__ == 'BystedtsClothBuilder' for m in addon_utils.modules())
if not already_installed:
    bpy.ops.preferences.addon_install(filepath=str(archive), overwrite=False)
bpy.ops.preferences.addon_enable(module='BystedtsClothBuilder')
import BystedtsClothBuilder
asset_dir = Path(BystedtsClothBuilder.__file__).parent / 'BCB cloth assets'
if not any(Path(lib.path).resolve() == asset_dir.resolve() for lib in bpy.context.preferences.filepaths.asset_libraries):
    bpy.ops.preferences.asset_library_add(directory=str(asset_dir))
bpy.ops.wm.save_userpref()
report = {'zipSha256': expected, 'module': 'BystedtsClothBuilder',
          'version': list(BystedtsClothBuilder.bl_info['version']), 'author': 'Daniel Bystedt',
          'blender': bpy.app.version_string, 'modulePath': BystedtsClothBuilder.__file__,
          'enabled': 'BystedtsClothBuilder' in bpy.context.preferences.addons,
          'assetLibrary': str(asset_dir), 'additionalCreditsConsumed': 0, 'cost': 0}
Path(args.output).write_text(json.dumps(report, indent=2), encoding='utf-8')
print('CLOTH_BUILDER_INSTALLED', json.dumps(report))

"""Enable only bundled Blender exporters/importers in this isolated process; never save preferences."""
import sys,addon_utils
from pathlib import Path
boundary=sys.argv.index('--');name=sys.argv[boundary+1];args=sys.argv[boundary+2:];p=Path('F:/Alice/SharedProduction/Tools')/name;assert p.parent==Path('F:/Alice/SharedProduction/Tools') and p.is_file()
name=p.name
if name.startswith('export_'):
 for module in ['io_scene_gltf2','io_scene_fbx']:assert addon_utils.enable(module,default_set=False,persistent=False)
elif name.startswith('reimport_'):
 assert args and args[0] in {'glb','fbx'};assert addon_utils.enable('io_scene_gltf2' if args[0]=='glb' else 'io_scene_fbx',default_set=False,persistent=False)
sys.argv=sys.argv[:boundary+1]+args;exec(compile(p.read_text(encoding='utf-8-sig'),str(p),'exec'),{'__name__':'__main__','__file__':str(p)})

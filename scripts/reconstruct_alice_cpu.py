"""Actual TripoSR inference from one source photo; failures never produce a substitute mesh."""
import argparse
import hashlib
import json
import sys
import time
import types
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--engine', required=True)
parser.add_argument('--weights', required=True)
parser.add_argument('--source', required=True)
parser.add_argument('--output', required=True)
parser.add_argument('--resolution', type=int, default=256)
parser.add_argument('--threads', type=int, default=6)
parser.add_argument('--crop', nargs=4, type=int, help='Source-photo pixel box: left top right bottom')
args = parser.parse_args()
out, source = Path(args.output), Path(args.source)
out.mkdir(parents=True, exist_ok=True)
manifest = out / 'generation.json'
if manifest.exists():
    raise ValueError('Existing generation record: inspect before choosing a new output directory.')
sha = lambda data: hashlib.sha256(data).hexdigest()
report = {'sourcePhoto': str(source.resolve()), 'sourcePhotoSha256': sha(source.read_bytes()),
          'sourceCrop': args.crop, 'method': 'TripoSR-photo-inference', 'reusedGeometry': False,
          'parameters': {'resolution': args.resolution, 'device': 'cpu', 'threads': args.threads},
          'status': 'starting', 'fidelityVerified': False, 'completedOutfit': False}
def record(status):
    report['status'] = status
    manifest.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'status': status, 'source': str(source)}, ensure_ascii=False), flush=True)
record('loading_dependencies')
try:
    import numpy as np
    import torch
    import mcubes
    import rembg
    from PIL import Image
    torch.set_num_threads(args.threads)
    # CPU isosurface implementation, preserving torchmcubes' coordinate convention.
    # This operates on the density field inferred by TripoSR, never on a placeholder.
    def cpu_marching_cubes(level, value):
        vertices, faces = mcubes.marching_cubes(level.detach().cpu().numpy(), float(value))
        return torch.from_numpy(np.ascontiguousarray(vertices[:, [2, 1, 0]])).float(), torch.from_numpy(np.ascontiguousarray(faces)).long()
    module = types.ModuleType('torchmcubes')
    module.marching_cubes = cpu_marching_cubes
    sys.modules['torchmcubes'] = module
    sys.path.insert(0, str(Path(args.engine).resolve()))
    from tsr.system import TSR
    from tsr.utils import remove_background, resize_foreground
    report['weightsSha256'] = sha((Path(args.weights) / 'model.ckpt').read_bytes())
    record('loading_triposr_weights')
    model = TSR.from_pretrained(args.weights, config_name='config.yaml', weight_name='model.ckpt')
    model.eval().to('cpu')
    model.renderer.set_chunk_size(16384)
    image = Image.open(source).convert('RGB')
    if args.crop:
        if not (0 <= args.crop[0] < args.crop[2] <= image.width and 0 <= args.crop[1] < args.crop[3] <= image.height):
            raise ValueError('Crop falls outside source photo.')
        image = image.crop(args.crop)
    image.save(out / 'source_crop.png')
    record('segmenting_source_photo')
    image = remove_background(image, rembg.new_session('u2net'))
    image.save(out / 'source_mask.png')
    image = resize_foreground(image, 0.85)
    rgba = np.asarray(image).astype(np.float32) / 255.0
    rgb = rgba[:, :, :3] * rgba[:, :, 3:4] + (1-rgba[:, :, 3:4]) * 0.5
    input_image = Image.fromarray((rgb * 255).astype(np.uint8))
    input_image.save(out / 'inference_input.png')
    report['inferenceInputSha256'] = sha((out / 'inference_input.png').read_bytes())
    record('inferring_3d_density')
    started = time.monotonic()
    with torch.no_grad():
        code = model(input_image, device='cpu')
    torch.save(code.cpu(), out / 'scene_code.pt')
    report['inferenceSeconds'] = time.monotonic()-started
    record('extracting_3d_surface')
    mesh = model.extract_mesh(code, has_vertex_color=True, resolution=args.resolution)[0]
    if len(mesh.vertices) < 1000 or not np.isfinite(mesh.vertices).all() or np.min(mesh.extents) <= 0.01:
        raise ValueError('Inferred surface has insufficient volume or geometry.')
    mesh.export(out / 'model.glb')
    report.update(modelSha256=sha((out / 'model.glb').read_bytes()), vertices=len(mesh.vertices),
                  triangles=len(mesh.faces), bounds=mesh.bounds.tolist(), model=str((out / 'model.glb').resolve()))
    record('generated_awaiting_visual_review')
except Exception as error:
    report['failure'] = {'type': type(error).__name__, 'message': str(error)[:1000]}
    record('failed_no_model')
    raise

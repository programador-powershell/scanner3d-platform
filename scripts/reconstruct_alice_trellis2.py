"""Use the official TRELLIS.2 Gradio client with one persistent generation session."""
import argparse
import hashlib
import json
import shutil
from pathlib import Path
from gradio_client import Client, handle_file
from huggingface_hub import get_token

parser=argparse.ArgumentParser()
parser.add_argument('--source',required=True)
parser.add_argument('--mask',required=True)
parser.add_argument('--output',required=True)
parser.add_argument('--crop',nargs=4,type=int)
args=parser.parse_args()
source,mask,out=Path(args.source),Path(args.mask),Path(args.output)
out.mkdir(parents=True,exist_ok=True)
manifest=out/'generation.json'
if manifest.exists(): raise ValueError('Generation record exists; inspect before retrying.')
sha=lambda file:hashlib.sha256(Path(file).read_bytes()).hexdigest()
report={'sourcePhoto':str(source.resolve()),'sourcePhotoSha256':sha(source),'sourceCrop':args.crop,
        'method':'TRELLIS.2-official-space-photo-inference','reusedGeometry':False,'fidelityVerified':False,
        'completedOutfit':False,'inferenceInput':str(mask.resolve()),'inferenceInputSha256':sha(mask),
        'parameters':{'seed':1701,'resolution':'1024','decimationTarget':500000,'textureSize':4096},'events':[]}
def record(status):
    report['status']=status;manifest.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'status':status}),flush=True)
try:
    record('connecting_official_service')
    client=Client('microsoft/TRELLIS.2',token=get_token(),verbose=False,download_files=str(out/'downloads'))
    report['sessionHash']=client.session_hash
    def predict(name,**kwargs):
        job=client.submit(api_name=name,**kwargs)
        report['events'].append({'api':name,'eventId':job.communicator.event_id});record('pending_'+name.strip('/'))
        return job.result()
    predict('/start_session')
    prepared=predict('/preprocess_image',input=handle_file(str(mask)))
    record('inferring_source_photo')
    preview=predict('/image_to_3d',image=prepared,seed=1701,resolution='1024',ss_guidance_strength=7.5,
                    ss_guidance_rescale=0.7,ss_sampling_steps=12,ss_rescale_t=5,
                    shape_slat_guidance_strength=7.5,shape_slat_guidance_rescale=0.5,
                    shape_slat_sampling_steps=12,shape_slat_rescale_t=3,
                    tex_slat_guidance_strength=1,tex_slat_guidance_rescale=0,
                    tex_slat_sampling_steps=12,tex_slat_rescale_t=3)
    (out/'service_preview.html').write_text(preview,encoding='utf-8')
    record('extracting_model')
    exported=predict('/extract_glb',decimation_target=500000,texture_size=4096)
    generated=next(Path(f) for f in exported if str(f).endswith('.glb'))
    model=out/'model.glb';shutil.copyfile(generated,model)
    raw=model.read_bytes()
    if raw[:4]!=b'glTF' or int.from_bytes(raw[8:12],'little')!=len(raw): raise ValueError('Invalid GLB output.')
    report.update(model=str(model.resolve()),modelSha256=sha(model),modelBytes=len(raw))
    record('generated_awaiting_visual_review')
except Exception as error:
    report['failure']={'type':type(error).__name__,'message':str(error)[:1400]}
    record('failed_no_model');raise

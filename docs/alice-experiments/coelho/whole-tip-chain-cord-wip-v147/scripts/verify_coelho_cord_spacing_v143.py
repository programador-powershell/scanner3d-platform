from pathlib import Path
R=Path('F:/Alice/SharedProduction');code=(R/'Tools/audit_coelho_tip_chain_cords_v132.py').read_text(encoding='utf-8-sig').replace('apron_lace_local_weave_authoring_audit_v129.json','apron_cord_spacing_authoring_audit_v142.json').replace("zip(['chain','cord'],a['parts'][:2])", "zip(['cord'],a['parts'][1:2])").replace('v132','v143')
code=code.replace("localTargets[other]=meshData(other)", "localTargets[other]=meshData(other);localTargets[a['parts'][2]['object']]=meshData(a['parts'][2]['object'])")
code=code.replace("records.append(dict(role=role", """if role=='cord':
  ref=bpy.data.objects[rec['referenceObject']].data;oldP=np.array([v.co[:] for v in ref.vertices]).reshape(-1,6,3);newP=P.reshape(-1,6,3);radialError=float(np.abs((newP-newP.mean(1)[:,None,:])-(oldP-oldP.mean(1)[:,None,:])).max());assert radialError<1e-7;UV=np.array([v.uv[:] for v in bpy.data.objects[rec['object']].data.uv_layers[0].data]);assert np.array_equal(UV,np.array([v.uv[:] for v in ref.uv_layers[0].data]));metric=dict(maxSectionRigidTranslationErrorM=radialError,UVExactlyPreserved=True)
 records.append(dict(role=role""")
exec(compile(code,__file__,'exec'))

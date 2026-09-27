import json,numpy as np
from pathlib import Path
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
root=Path('F:/Alice/Deliverables/Alice_Variants/alice_chapeleiro/foundation_shared_rig_v089');r=json.loads((root/'native_individual_finger_sections.json').read_text());rows=[]
for row in r['rows']:
 seg=np.array(row['actualOriginalFaceIntersections']);pts,iv=np.unique(np.round(seg.reshape(-1,3),7),axis=0,return_inverse=True)
 edges=np.unique(np.sort(iv.reshape(-1,2),axis=1),axis=0);edges=edges[edges[:,0]!=edges[:,1]]
 graph=coo_matrix((np.ones(len(edges)),(edges[:,0],edges[:,1])),shape=(len(pts),len(pts))).tocsr();n,labels=connected_components(graph,directed=False)
 degree=np.bincount(edges.ravel(),minlength=len(pts));loops=[]
 for i in range(n):
  ids=np.flatnonzero(labels==i);q=pts[ids];low,high=q.min(0),q.max(0)
  if len(q)<8 or high[0]-low[0]<.001 or high[1]-low[1]<.001:continue
  e=edges[np.all(labels[edges]==i,axis=1)]
  adjacency={int(v):[] for v in ids}
  for a,b in e:adjacency[int(a)].append(int(b));adjacency[int(b)].append(int(a))
  closed=bool(np.all(degree[ids]==2));centroid=q.mean(0);ordered=[];area=None
  if closed:
   current=int(ids[0]);previous=-1
   while current not in ordered:
    ordered.append(current);nxt=next(v for v in adjacency[current] if v!=previous);previous,current=current,nxt
   assert current==ordered[0] and len(ordered)==len(ids)
   polygon=pts[ordered];x,y=polygon[:,0],polygon[:,1];xn,yn=np.roll(x,-1),np.roll(y,-1);cross=x*yn-xn*y;area=cross.sum()/2
   if abs(area)>1e-10:centroid=np.array([((x+xn)*cross).sum()/(6*area),((y+yn)*cross).sum()/(6*area),row['z']])
  loops.append({'points':len(q),'bounds':[low.tolist(),high.tolist()],'centroid':centroid.tolist(),'closed':closed,'signedArea':area,'contour':pts[ordered].tolist() if ordered else q.tolist()})
 loops.sort(key=lambda p:p['centroid'][1]);result={'side':row['side'],'z':row['z'],'loops':loops};rows.append(result)
 if row['z'] in [.448,.452,.456,.460,.464,.468,.472,.480,.488]:print(row['side'],row['z'],[(p['points'],p['closed'],[round(v,5) for v in p['centroid']]) for p in loops])
report={k:v for k,v in r.items() if k!='rows'};report['method']='read-only original surface contour components, geometric centroids of closed plane loops';report['rows']=rows
(root/'native_individual_finger_contours.json').write_text(json.dumps(report,indent=2))

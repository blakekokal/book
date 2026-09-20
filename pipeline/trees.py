import numpy as np, json, pickle
from scipy import ndimage as ndi
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from shapely.geometry import Polygon
from model import Y
M=json.load(open("naip_meta.json")); b=M["bounds"]; res=M["res"]
a=np.load("naip.npy").astype(np.float32)
ndvi=np.load("ndvi.npy"); tex=np.load("tex.npy"); bright=np.load("bright.npy")
N=a[...,3]
trees=(tex>10.0)&(ndvi>0.10)&(bright<150)
trees=ndi.binary_closing(trees,np.ones((7,7)))
trees=ndi.binary_opening(trees,np.ones((5,5)))
trees=ndi.binary_fill_holes(trees)
lab,n=ndi.label(trees)
sz=ndi.sum(trees,lab,range(1,n+1))
keep=np.isin(lab,[i+1 for i,s in enumerate(sz) if s*res*res/Y/Y>90])
print("tree blobs kept:",keep.sum()*res*res/Y/Y,"sq yd of",trees.sum()*res*res/Y/Y)
sm=ndi.gaussian_filter(keep.astype(float),2.2)
ny,nx=sm.shape
X=b[0]+(np.arange(nx)+0.5)*res
Yy=b[3]-(np.arange(ny)+0.5)*res
cs=plt.contour(X,Yy,sm,levels=[0.5])
polys=[]
for p in cs.allsegs[0]:
    if len(p)<14: continue
    try:
        pg=Polygon(p)
        if not pg.is_valid: pg=pg.buffer(0)
        if pg.geom_type=="Polygon" and pg.area/Y/Y>110: polys.append(pg.simplify(1.0))
    except Exception: pass
print("tree polygons:",len(polys))
pickle.dump(polys,open("tree_polys.pkl","wb"))

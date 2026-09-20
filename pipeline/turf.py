import numpy as np, json, pickle, math
from scipy import ndimage as ndi
from PIL import Image
from shapely.geometry import Polygon, LineString, Point, MultiPolygon
from shapely.ops import unary_union
from model import Y
M=json.load(open("naip_meta.json")); b=M["bounds"]; res=M["res"]
bright=np.load("bright.npy"); ndvi=np.load("ndvi.npy"); tex=np.load("tex.npy")
a=np.load("naip.npy").astype(np.float32); N=a[...,3]

# turf = vegetated, smooth, not water, not pavement-bright
turf=(ndvi>0.10)&(tex<8.0)&(N>80)&(bright<175)
turf=ndi.binary_closing(turf,np.ones((9,9)))
turf=ndi.binary_opening(turf,np.ones((7,7)))
turf=ndi.binary_fill_holes(turf)

D=pickle.load(open("hole1.pkl","rb"))
lop=D["lop_pts"]; DIRS=D["DIRS"]
def chain_to_xy(d):
    rem=d*Y
    for (ux,uy,L),p in zip(DIRS,lop):
        if rem<=L or (ux,uy,L) is DIRS[-1]: return (p[0]+ux*rem,p[1]+uy*rem)
        rem-=L
def to_px(x,y): return (int((x-b[0])/res), int((b[3]-y)/res))

lab,n=ndi.label(turf)
print("turf components:",n)
# keep components touched by the line of play
keep=set()
for d in range(120,375,3):
    x,y=chain_to_xy(d); j,i=to_px(x,y)
    if 0<=i<lab.shape[0] and 0<=j<lab.shape[1] and lab[i,j]: keep.add(lab[i,j])
print("components on line of play:",keep, [int((lab==k).sum()*res*res/Y/Y) for k in keep])
mask=np.isin(lab,list(keep))
print("kept area %.0f sq yd"%(mask.sum()*res*res/Y/Y))
Image.fromarray((mask*255).astype(np.uint8)).save("turf_mask.png")

# vectorise with marching squares (skimage-free): use matplotlib contour
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
sm=ndi.gaussian_filter(mask.astype(float),3.0)
ny,nx=sm.shape
X=b[0]+(np.arange(nx)+0.5)*res
Yy=b[3]-(np.arange(ny)+0.5)*res
cs=plt.contour(X,Yy,sm,levels=[0.5])
polys=[]
for p in cs.allsegs[0]:
    if len(p)<40: continue
    try:
        pg=Polygon(p)
        if not pg.is_valid: pg=pg.buffer(0)
        if pg.geom_type=="Polygon" and pg.area/Y/Y>2000: polys.append(pg.simplify(1.2))
    except Exception: pass
polys.sort(key=lambda p:-p.area)
print("turf polygons kept:",[int(p.area/Y/Y) for p in polys])
pickle.dump(polys,open("turf_polys.pkl","wb"))

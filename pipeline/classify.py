import numpy as np, json, pickle, math
from scipy import ndimage as ndi
from PIL import Image
from shapely.geometry import Point
a=np.load("naip.npy").astype(np.float32)
M=json.load(open("naip_meta.json")); b=M["bounds"]; res=M["res"]
R,G,B,N=a[...,0],a[...,1],a[...,2],a[...,3]
ndvi=(N-R)/np.maximum(N+R,1)
bright=(R+G+B)/3.0
# local texture = std in 5x5
mu=ndi.uniform_filter(bright,7); mu2=ndi.uniform_filter(bright**2,7)
tex=np.sqrt(np.maximum(mu2-mu**2,0))
print("ndvi  p5=%.2f p50=%.2f p95=%.2f"%tuple(np.percentile(ndvi,[5,50,95])))
print("bright p5=%.0f p50=%.0f p95=%.0f"%tuple(np.percentile(bright,[5,50,95])))
print("tex   p5=%.1f p50=%.1f p95=%.1f"%tuple(np.percentile(tex,[5,50,95])))

D=pickle.load(open("hole1.pkl","rb"))
def to_px(x,y):
    return ((x-b[0])/res, (b[3]-y)/res)
# sample known fairway: along line of play 150..330 yd
from model import Y
lop=D["lop_pts"]; DIRS=D["DIRS"]
def chain_to_xy(d):
    rem=d*Y
    for (ux,uy,L),p in zip(DIRS,lop):
        if rem<=L or (ux,uy,L) is DIRS[-1]: return (p[0]+ux*rem,p[1]+uy*rem)
        rem-=L
fw=[];
for d in range(140,345,5):
    x,y=chain_to_xy(d); px,py=to_px(x,y)
    i,j=int(py),int(px)
    if 0<=i<bright.shape[0] and 0<=j<bright.shape[1]:
        fw.append((bright[i,j],ndvi[i,j],tex[i,j]))
fw=np.array(fw)
print("\nFAIRWAY samples n=%d  bright %.0f+-%.0f  ndvi %.2f+-%.02f  tex %.1f+-%.1f"%(
    len(fw),fw[:,0].mean(),fw[:,0].std(),fw[:,1].mean(),fw[:,1].std(),fw[:,2].mean(),fw[:,2].std()))
# sample known rough/trees: 60 m off axis
ro=[]
for d in range(140,345,5):
    x,y=chain_to_xy(d)
    for (ux,uy,L),p in zip(DIRS,lop): pass
    ux,uy,_=DIRS[-1]
    for sgn in (-1,1):
        xx,yy=x+(-uy)*sgn*55, y+(ux)*sgn*55
        px,py=to_px(xx,yy); i,j=int(py),int(px)
        if 0<=i<bright.shape[0] and 0<=j<bright.shape[1]:
            ro.append((bright[i,j],ndvi[i,j],tex[i,j]))
ro=np.array(ro)
print("OFFAXIS55 samples n=%d  bright %.0f+-%.0f  ndvi %.2f+-%.2f  tex %.1f+-%.1f"%(
    len(ro),ro[:,0].mean(),ro[:,0].std(),ro[:,1].mean(),ro[:,1].std(),ro[:,2].mean(),ro[:,2].std()))
# visualise
vis=np.dstack([np.clip(R,0,255),np.clip(G,0,255),np.clip(B,0,255)]).astype(np.uint8)
Image.fromarray(vis).save("naip_rgb.png")
cls=np.zeros(bright.shape,np.uint8)
trees=(tex>9)&(ndvi>0.05)
water=(N<70)&(ndvi<0.05)
sand=(bright>165)&(ndvi<0.25)
turf=(~trees)&(~water)&(~sand)&(ndvi>0.02)
cls[turf]=1; cls[trees]=2; cls[sand]=3; cls[water]=4
pal=np.array([[40,40,40],[120,200,90],[20,80,30],[240,225,150],[40,90,170]],np.uint8)
Image.fromarray(pal[cls]).save("naip_class.png")
print("\nclass fractions: turf %.2f trees %.2f sand %.2f water %.2f"%(
    turf.mean(),trees.mean(),sand.mean(),water.mean()))
np.save("cls.npy",cls); np.save("bright.npy",bright); np.save("ndvi.npy",ndvi); np.save("tex.npy",tex)

import numpy as np, pickle, math, json
from scipy import ndimage as ndi
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from shapely.geometry import Polygon, LineString, Point
from model import DEM, Y
D=pickle.load(open("hole1.pkl","rb"))
green=D["green"]; front=D["front"]; back=D["back"]; gc=D["gc"]
gb=D["green_bounds"]
dem=DEM(gb,0.5,"greenhi")

# sampling grid in local metres
x0,y0,x1,y1=gb
ny,nx=dem.A.shape
xs=np.linspace(x0,x1,nx); ys=np.linspace(y1,y0,ny)
XX,YY=np.meshgrid(xs,ys)
Z=dem.A.copy()
# mild smoothing: lidar noise floor ~3-5 cm; 1.0 m sigma keeps real breaks
Zs=ndi.gaussian_filter(np.nan_to_num(Z,nan=np.nanmean(Z)),2.0)

px=(x1-x0)/(nx-1)
gy,gx=np.gradient(Zs,(y0-y1)/(ny-1),(x1-x0)/(nx-1))
slope=np.hypot(gx,gy)          # rise/run
print("green bbox %.0f x %.0f m, grid %dx%d, px=%.2f m"%(x1-x0,y1-y0,nx,ny,px))

inside=np.zeros(Zs.shape,bool)
from shapely.vectorized import contains
try:
    inside=contains(green,XX,YY)
except Exception:
    for i in range(ny):
        for j in range(nx):
            inside[i,j]=green.contains(Point(XX[i,j],YY[i,j]))
print("green pixels:",inside.sum())
zi=Zs[inside]
print("green elev range %.2f m (%.1f ft)"%(zi.max()-zi.min(),(zi.max()-zi.min())*3.28084))
si=slope[inside]
print("slope: median %.1f%%  p90 %.1f%%  max %.1f%%"%(np.median(si)*100,np.percentile(si,90)*100,si.max()*100))
print("fraction of green >=4%% slope: %.1f%%"%((si>=0.04).mean()*100))
print("fraction >=2%%: %.1f%%  >=3%%: %.1f%%"%((si>=0.02).mean()*100,(si>=0.03).mean()*100))

# contours every 6 inches (0.1524 m)
lo,hi=np.floor(zi.min()/0.1524)*0.1524, np.ceil(zi.max()/0.1524)*0.1524
levels=np.arange(lo,hi+1e-9,0.1524)
Zm=np.where(inside|ndi.binary_dilation(inside,np.ones((25,25))),Zs,np.nan)
cs=plt.contour(XX,YY,Zm,levels=levels)
conts=[]
for lev,segs in zip(cs.levels,cs.allsegs):
    for s in segs:
        if len(s)>6: conts.append((float(lev),[(float(a),float(bb)) for a,bb in s]))
print("contour polylines:",len(conts),"levels",len(levels))
pickle.dump(dict(XX=XX,YY=YY,Z=Zs,slope=slope,gx=gx,gy=gy,inside=inside,
                 contours=conts,levels=levels,bounds=gb),open("greenfield.pkl","wb"))
print("wrote greenfield.pkl")

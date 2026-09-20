"""Build a normalised hole model for Bridlewood #1 from OSM + USGS 3DEP."""
import json, math, os
import numpy as np, requests, tifffile
from pyproj import CRS, Transformer
from shapely.geometry import Polygon, LineString, Point
from shapely.ops import unary_union, nearest_points

UA={"User-Agent":"yardage-book-prototype/0.1"}
Y=0.9144                      # metres per yard
GREEN_ID, TEE_BLACK, HOLE_ID = 869885498, 869885492, 870888278
TEE_LADDER=[869885492,869885490,869885491,749964166]   # black,blue,white,red (back->fwd)

# ---- local metric frame centred on the hole ------------------------------
LAT0,LON0 = 33.0516, -97.0922
CRS_L = CRS.from_proj4(f"+proj=aeqd +lat_0={LAT0} +lon_0={LON0} +datum=WGS84 +units=m +no_defs")
FWD = Transformer.from_crs("EPSG:4326", CRS_L, always_xy=True)
INV = Transformer.from_crs(CRS_L, "EPSG:4326", always_xy=True)
T3857 = Transformer.from_crs(CRS_L, "EPSG:3857", always_xy=True)

def load_osm():
    d=json.load(open("bridlewood_raw.json"))
    out=[]
    for e in d["elements"]:
        g=[(p["lon"],p["lat"]) for p in (e.get("geometry") or [])]
        if len(g)<2: continue
        t=e.get("tags",{})
        xy=[FWD.transform(x,y) for x,y in g]
        closed=len(xy)>3 and math.dist(xy[0],xy[-1])<0.8
        go=None
        if closed:
            try:
                p=Polygon(xy); p=p if p.is_valid else p.buffer(0)
                if not p.is_empty and p.area>0: go=p
            except Exception: pass
        if go is None: go=LineString(xy)
        out.append(dict(id=e["id"], kind=t.get("golf") or t.get("natural") or t.get("waterway"),
                        tags=t, geom=go))
    return out

# ---- DEM ----------------------------------------------------------------
class DEM:
    """3DEP bare-earth, cached, sampled in the local metric frame."""
    def __init__(self, bounds_l, res_m=1.0, tag="dem"):
        x0,y0,x1,y1 = bounds_l
        self.x0,self.y0,self.x1,self.y1 = x0,y0,x1,y1
        c0=T3857.transform(x0,y0); c1=T3857.transform(x1,y1)
        mx0,my0=min(c0[0],c1[0]),min(c0[1],c1[1]); mx1,my1=max(c0[0],c1[0]),max(c0[1],c1[1])
        nx=int(round((x1-x0)/res_m)); ny=int(round((y1-y0)/res_m))
        nx=max(16,min(nx,4000)); ny=max(16,min(ny,4000))
        f=f"{tag}_{nx}x{ny}.tif"
        if not os.path.exists(f):
            p={"bbox":f"{mx0},{my0},{mx1},{my1}","bboxSR":3857,"imageSR":3857,
               "size":f"{nx},{ny}","format":"tiff","pixelType":"F32","f":"image",
               "interpolation":"RSP_BilinearInterpolation"}
            for a in range(5):
                try:
                    r=requests.get("https://elevation.nationalmap.gov/arcgis/rest/services/"
                                   "3DEPElevation/ImageServer/exportImage",
                                   params=p,headers=UA,timeout=180)
                    if r.status_code==200 and r.headers.get("content-type","").startswith("image"):
                        open(f,"wb").write(r.content); break
                except Exception as e: print("dem retry",a,str(e)[:70])
                import time; time.sleep(2**a)
        A=tifffile.imread(f).astype(np.float64)
        A=np.where(A<-1000,np.nan,A)
        self.A=A; self.ny,self.nx=A.shape
    def z(self,x,y):
        """bilinear sample; x,y in local metres"""
        fx=(np.asarray(x,float)-self.x0)/(self.x1-self.x0)*(self.nx-1)
        fy=(self.y1-np.asarray(y,float))/(self.y1-self.y0)*(self.ny-1)
        fx=np.clip(fx,0,self.nx-1.001); fy=np.clip(fy,0,self.ny-1.001)
        i0=np.floor(fx).astype(int); j0=np.floor(fy).astype(int)
        tx=fx-i0; ty=fy-j0
        a=self.A[j0,i0]; b=self.A[j0,i0+1]; c=self.A[j0+1,i0]; d=self.A[j0+1,i0+1]
        return (a*(1-tx)*(1-ty)+b*tx*(1-ty)+c*(1-tx)*ty+d*tx*ty)

if __name__=="__main__":
    F=load_osm()
    by={f["id"]:f for f in F}
    green=by[GREEN_ID]["geom"]; teeB=by[TEE_BLACK]["geom"]; hole=by[HOLE_ID]["geom"]
    gc=green.centroid; tc=teeB.centroid
    print("green centroid local:",round(gc.x,1),round(gc.y,1))
    print("black tee centroid  :",round(tc.x,1),round(tc.y,1))
    print("straight tee->greenC: %.1f yd"%(tc.distance(gc)/Y))
    print("osm hole line coords:",[(round(a,1),round(b,1)) for a,b in hole.coords])
    xs=[gc.x,tc.x]+[c[0] for c in hole.coords]; ys=[gc.y,tc.y]+[c[1] for c in hole.coords]
    pad=110
    b=(min(xs)-pad,min(ys)-pad,max(xs)+pad,max(ys)+pad)
    print("corridor bounds local:",[round(v,1) for v in b], "size %.0f x %.0f m"%(b[2]-b[0],b[3]-b[1]))
    d=DEM(b,1.0,"corridor")
    print("corridor DEM",d.A.shape,"elev %.2f..%.2f m"%(np.nanmin(d.A),np.nanmax(d.A)))
    print("tee z=%.2f  greenC z=%.2f  delta=%.2f m (%.1f yd)"%(
        d.z(tc.x,tc.y), d.z(gc.x,gc.y), d.z(gc.x,gc.y)-d.z(tc.x,tc.y),
        (d.z(gc.x,gc.y)-d.z(tc.x,tc.y))/Y))
    json.dump({"bounds":list(b)},open("corridor_meta.json","w"))

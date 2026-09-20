"""Turn the extracted pixels into a metric hole model (yards, play-line up)."""
import pickle, math, numpy as np
from PIL import Image
from scipy import ndimage as ndi
from shapely.geometry import Polygon, Point
from shapely.affinity import affine_transform

E=pickle.load(open("extracted.pkl","rb"))

# ---- values read off the source pages ----------------------------------
META={
 "cowboys": dict(club="COWBOYS GOLF CLUB", city="GRAPEVINE, TEXAS", hole=9, par=4, hcp=9,
    yards=441, tee="BLACK", to_green=414, plays=+1, depth=35, width=16,
    # tee and pin in hole-panel pixels
    tee_px=(330,605), pin_px=(329,64),
    # perimeter depth marks on the green page: (label, approx angle from centre, deg CCW from play-up)
    marks=[(35,0),(33,-28),(30,32),(27,-62),(14,86),(4,128)],
    # elevation stations: (yards from tee, value)
    elevs=[(34,+1),(55,+1),(80,+1),(153,+2),(212,+3),(264,+3),(314,+3),(363,+2)],
    calls=[237,214,176,75],
    arcs=[100,150,200,250]),
 "bridle9": dict(club="BRIDLEWOOD GOLF CLUB", city="FLOWER MOUND, TEXAS", hole=9, par=4, hcp=7,
    yards=463, tee="BLACK", to_green=459, plays=-5, depth=33, width=26,
    tee_px=(315,742), pin_px=(315,85),
    marks=[(33,-6),(26,-58),(11,64),(4,104)],
    elevs=[(51,-5),(77,-5),(103,-5),(212,-4),(261,-3),(311,-2),(361,+1),(411,+1)],
    calls=[],
    arcs=[100,150,200,250]),
}

def compass_bearing(img_path, box, corner=(0.70,0.0,1.0,0.30)):
    """angle (deg) of the compass needle, measured clockwise from page-up"""
    a=np.array(Image.open(img_path).convert("RGB"))
    x0,y0,x1,y1=box; sub=a[y0:y1,x0:x1]
    h,w=sub.shape[:2]
    cx0,cy0=int(w*corner[0]),int(h*corner[1]); cx1,cy1=int(w*corner[2]),int(h*corner[3])
    win=sub[cy0:cy1,cx0:cx1]
    dark=(win.max(axis=2)<120)
    if dark.sum()<30: return 0.0
    lab,n=ndi.label(dark)
    sz=ndi.sum(dark,lab,range(1,n+1))
    # the ring is the biggest blob; the needle is the next substantial one
    order=np.argsort(-sz)
    best=None
    for k in order[:4]:
        m=(lab==k+1)
        ys,xs=np.nonzero(m)
        if len(xs)<25: continue
        # a ring is hollow: its filled area is far larger than its pixel count
        filled=ndi.binary_fill_holes(m).sum()
        if filled>m.sum()*2.2: continue          # skip the ring
        q=np.c_[xs-xs.mean(), ys-ys.mean()].astype(float)
        u,s,vt=np.linalg.svd(q,full_matrices=False)
        d=vt[0]
        proj=q@d
        # arrowhead end carries more pixels
        if (proj>0).sum()<(proj<0).sum(): d=-d
        best=math.degrees(math.atan2(d[0],-d[1]))
        break
    return (best or 0.0)

MODELS={}
for nm,M in META.items():
    ex=E[nm]; g=ex["green"]; h=ex["hole"]
    # --- green-page scale: the red depth axis is the stated depth -------
    (ax0,ay0),(ax1,ay1)=g["axis"]
    px_per_yd_g=abs(ay1-ay0)/M["depth"]
    # --- hole-page scale: tee -> pin is the stated distance ------------
    d_px=math.dist(M["tee_px"],M["pin_px"])
    yd_per_px_h=M["to_green"]/d_px
    print(f"{nm}: green {px_per_yd_g:.2f} px/yd | hole {yd_per_px_h:.4f} yd/px "
          f"({1/yd_per_px_h:.2f} px/yd)  tee->pin {d_px:.0f}px")
    # green polygon -> yards, origin at the front of the axis, play line up
    fx,fy=ax0,max(ay0,ay1)                      # front of green = bottom of axis
    def g2y(p):
        return Polygon([((x-fx)/px_per_yd_g, (fy-y)/px_per_yd_g) for x,y in p.exterior.coords])
    surf=g2y(g["surface"])
    model=dict(meta=M, surface=surf,
        collar=[g2y(p) for p in g["collar"]],
        gsand=[g2y(p) for p in g["sand"]],
        gwater=[g2y(p) for p in g["water"]])
    # hole polygons -> yards, origin at the tee, play line up
    tx,ty=M["tee_px"]
    ang=math.atan2(M["pin_px"][0]-tx, ty-M["pin_px"][1])   # rotate play line to +Y
    ca,sa=math.cos(-ang),math.sin(-ang)
    def h2y(p):
        out=[]
        for x,y in p.exterior.coords:
            dx,dy=(x-tx)*yd_per_px_h,(ty-y)*yd_per_px_h
            out.append((dx*ca-dy*sa, dx*sa+dy*ca))
        return Polygon(out)
    for k in ("fairway","water","sand","trees","putt","corridor"):
        if k in h: model[k]=[h2y(p) for p in h[k]]
    model["scale_hole"]=yd_per_px_h
    model["ang"]=ang
    MODELS[nm]=model
    a=surf.bounds
    print(f"   green extent {a[2]-a[0]:.0f} x {a[3]-a[1]:.0f} yd (stated {M['width']} x {M['depth']}), "
          f"area {surf.area:.0f} sq yd")

# compass
import json
BOX={"cowboys":(125,952,706,1566),"bridle9":(95,1096,792,1846)}
IMG={"cowboys":"src_cowboys.png","bridle9":"src_bridle9.png"}
for nm in MODELS:
    b=compass_bearing(IMG[nm],BOX[nm])
    MODELS[nm]["north_deg"]=b
    print(f"{nm}: north is {b:+.0f} deg from page-up on the source hole page")
pickle.dump(MODELS,open("models.pkl","wb"))
print("\nwrote models.pkl")

"""Pull geometry out of the source generator's screenshots."""
import numpy as np, json, pickle
from PIL import Image
from scipy import ndimage as ndi
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from shapely.geometry import Polygon, LineString, Point
from shapely.ops import unary_union

def polys_from_mask(mask, min_px=60, smooth=1.4, simp=1.0):
    if mask.sum()==0: return []
    sm=ndi.gaussian_filter(mask.astype(float),smooth)
    ny,nx=sm.shape
    cs=plt.contour(np.arange(nx),np.arange(ny),sm,levels=[0.5])
    out=[]
    for seg in cs.allsegs[0]:
        if len(seg)<8: continue
        try:
            p=Polygon(seg)
            if not p.is_valid: p=p.buffer(0)
            if p.geom_type=="Polygon" and p.area>=min_px: out.append(p.simplify(simp))
        except Exception: pass
    plt.close("all")
    return sorted(out,key=lambda p:-p.area)

def near(a, rgb, tol):
    return (np.abs(a.astype(np.int16)-np.array(rgb,np.int16)).max(axis=2)<=tol)

SRC={
 "cowboys": dict(img="src_cowboys.png",
     green_box=(125,66,706,614), hole_box=(125,952,706,1566)),
 "bridle9": dict(img="src_bridle9.png",
     green_box=(250,60,764,668), hole_box=(95,1096,792,1846)),
}

def do_green(name,cfg):
    a=np.array(Image.open(cfg["img"]).convert("RGB"))
    x0,y0,x1,y1=cfg["green_box"]
    sub=a[y0:y1,x0:x1]
    PAD=14
    sub=np.pad(sub,((PAD,PAD),(PAD,PAD),(0,0)),constant_values=255)
    # the compass rose lives in the top-right corner; blank it so it is not
    # mistaken for sand or for the putting surface
    ch,cw=sub.shape[0],sub.shape[1]
    sub[:int(ch*0.28), int(cw*0.72):]=255
    dark=(sub.max(axis=2)<150)
    # the putting surface = interior of the heavy black curve
    closed=ndi.binary_closing(dark,np.ones((5,5)))
    filled=ndi.binary_fill_holes(closed)
    interior=filled&~ndi.binary_dilation(dark,np.ones((3,3)))
    lab,n=ndi.label(interior)
    if n==0: return None
    sz=ndi.sum(interior,lab,range(1,n+1))
    surf=(lab==(int(np.argmax(sz))+1))
    surf=ndi.binary_fill_holes(surf)
    print(f"  [{name}] putting surface {surf.sum()} px")
    gp=polys_from_mask(ndi.binary_dilation(surf,np.ones((3,3))),min_px=400,smooth=1.2,simp=0.8)
    # red depth axis
    red=(sub[:,:,0].astype(int)-sub[:,:,1]>45)&(sub[:,:,0].astype(int)-sub[:,:,2]>35)&(sub[:,:,0]>110)
    ys,xs=np.nonzero(red)
    axis=None
    if len(ys)>20:
        axis=((xs.mean(),ys.min()),(xs.mean(),ys.max()))
        print(f"  [{name}] depth axis {ys.max()-ys.min()} px tall at x={xs.mean():.0f}")
    gg=sub.astype(int)
    sm=(gg[:,:,0]-gg[:,:,1]>3)&(gg[:,:,0]>215)&(gg[:,:,2]<gg[:,:,1])
    sm=ndi.binary_opening(sm,np.ones((3,3)))
    sand=polys_from_mask(sm,min_px=700)
    water=polys_from_mask((sub[:,:,2].astype(int)-sub[:,:,0]>16)&(sub[:,:,2]>170),min_px=300)
    collar=polys_from_mask(near(sub,(232,240,230),9)|near(sub,(226,237,224),9),min_px=800)
    print(f"  [{name}] sand {len(sand)} water {len(water)} collar {len(collar)}")
    return dict(surface=gp[0] if gp else None, axis=axis, sand=sand, water=water,
                collar=collar, shape=sub.shape)

def do_hole_vector(name,cfg):
    a=np.array(Image.open(cfg["img"]).convert("RGB"))
    x0,y0,x1,y1=cfg["hole_box"]; sub=a[y0:y1,x0:x1]
    g=sub.astype(int)
    # water: blue-dominant. the callout leader lines cut across it, so close
    # the mask hard enough to bridge them before tracing
    wm=(g[:,:,2]-g[:,:,0]>18)&(g[:,:,2]>185)
    wm=ndi.binary_closing(wm,np.ones((13,13)))
    wm=ndi.binary_fill_holes(wm)
    water=polys_from_mask(wm,min_px=200,smooth=1.8)
    # sand is warm (R above G); the pale fairway green is the opposite, and the
    # two sit inside a few counts of each other on a plain colour distance
    sm=(g[:,:,0]-g[:,:,1]>3)&(g[:,:,0]>222)&(g[:,:,2]<g[:,:,1])
    sm=ndi.binary_opening(sm,np.ones((3,3)))
    sand =polys_from_mask(sm,min_px=110)
    fway =polys_from_mask(near(sub,(226,238,222),11)|near(sub,(219,235,215),11),min_px=1500)
    # trees: mid-green discs, distinct from the pale fairway
    trees=polys_from_mask(near(sub,(198,222,196),22)|near(sub,(186,214,184),22),min_px=90)
    putt =polys_from_mask(near(sub,(205,228,202),14),min_px=200)
    print(f"  [{name}] water {len(water)} sand {len(sand)} fairway {len(fway)} trees {len(trees)}")
    return dict(water=water,sand=sand,fairway=fway,trees=trees,putt=putt,shape=sub.shape)

def do_hole_raster(name,cfg):
    """satellite page: the hole is a feathered cut-out on white, so the corridor
    outline comes straight out of the mask"""
    a=np.array(Image.open(cfg["img"]).convert("RGB"))
    x0,y0,x1,y1=cfg["hole_box"]; sub=a[y0:y1,x0:x1]
    g=sub.astype(int)
    notwhite=(g.max(axis=2)-g.min(axis=2)>18)|(g.mean(axis=2)<225)
    notwhite=ndi.binary_closing(notwhite,np.ones((7,7)))
    notwhite=ndi.binary_opening(notwhite,np.ones((5,5)))
    lab,n=ndi.label(notwhite)
    sz=ndi.sum(notwhite,lab,range(1,n+1))
    keep=(lab==(int(np.argmax(sz))+1))
    keep=ndi.binary_fill_holes(keep)
    print(f"  [{name}] corridor mask {keep.sum()} px")
    corr=polys_from_mask(keep,min_px=4000,smooth=3.0,simp=1.6)
    # water inside the corridor: dark and green-dominant
    wm=keep&(g.mean(axis=2)<105)&(g[:,:,1]>=g[:,:,0])
    wm=ndi.binary_opening(wm,np.ones((5,5)))
    wm=ndi.binary_closing(wm,np.ones((7,7)))
    water=polys_from_mask(wm,min_px=900,smooth=2.2,simp=1.4)
    # putting surface: bright saturated green
    pm=keep&(g[:,:,1]-g[:,:,0]>10)&(g[:,:,1]>70)&(g.mean(axis=2)>75)&(g.mean(axis=2)<150)
    pm=ndi.binary_opening(pm,np.ones((4,4)))
    putt=polys_from_mask(pm,min_px=500,smooth=2.0,simp=1.2)
    # sand: bright, low saturation, light
    sm=keep&(g.mean(axis=2)>195)&(g.max(axis=2)-g.min(axis=2)<38)
    sm=ndi.binary_opening(sm,np.ones((3,3)))
    # sand only well inside the corridor, so the feathered edge is not caught
    sm=sm&ndi.binary_erosion(keep,np.ones((15,15)))
    sand=polys_from_mask(sm,min_px=260,smooth=1.6)
    print(f"  [{name}] corridor {len(corr)} water {len(water)} putt {len(putt)} sand {len(sand)}")
    return dict(corridor=corr,water=water,putt=putt,sand=sand,shape=sub.shape,raster=sub)

out={}
for nm,cfg in SRC.items():
    print(nm)
    g=do_green(nm,cfg)
    h=do_hole_vector(nm,cfg) if nm=="cowboys" else do_hole_raster(nm,cfg)
    out[nm]=dict(green=g,hole=h)
pickle.dump(out,open("extracted.pkl","wb"))
print("\nwrote extracted.pkl")

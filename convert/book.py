# -*- coding: utf-8 -*-
"""Render the whole Cowboys book in the No.1-Golf-style pro format."""
import pickle, math, re
import numpy as np
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from shapely.geometry import Polygon, LineString, Point
from shapely.ops import unary_union
from shapely.affinity import translate

PT=72.0; PW,PH=3.75*PT,6.5*PT; MG=0.155*PT
C_ROUGH=HexColor("#DCDCA6"); C_TURF=HexColor("#FFFFFF")
C_BUNKER=HexColor("#F2EEA8"); C_BUNKED=HexColor("#B9B45E")
C_GREEN=HexColor("#AFC96B");  C_GREENED=HexColor("#7E9642")
C_WATER=HexColor("#9FC2CE");  C_WATERED=HexColor("#5E8A99")
C_TREE=HexColor("#B4C68C");   C_TREED=HexColor("#7F9354")
C_RED=HexColor("#C0392B");    C_INK=HexColor("#1A1A1A")
C_NAVY=HexColor("#1B2A4A");   C_GRID=HexColor("#7FA8C9")
C_COLLAR=HexColor("#EAF0E2"); C_WHITE=HexColor("#FFFFFF")
CLUB="COWBOYS GOLF CLUB"; CITY="GRAPEVINE, TEXAS"
INK=(0.07,0.09,0.12)
M=pickle.load(open("models3.pkl","rb"))

def poly1(sp):
    if len(sp)<4: return None
    try:
        q=Polygon(sp)
        if not q.is_valid: q=q.buffer(0)
    except Exception: return None
    return q if q.geom_type=="Polygon" and q.area>0 else None

def tf_hole(m):
    tx,ty=m["tee"]; ax,ay=m["aim"]; k=m["ypp"]
    th=math.atan2(ax-tx, ty-ay); c,s=math.cos(th),math.sin(th)
    def f(x,y):
        dx,dy=(x-tx)*k,(ty-y)*k
        return (dx*c-dy*s, dx*s+dy*c)
    return f,th

def tf_green(m):
    ax,y0,y1=m["gaxis"]; k=m["gypp"]
    return lambda x,y: ((x-ax)*k,(y1-y)*k)

def conv(recs,f,minarea=0.25):
    out=[]
    for r in recs:
        for sp in r["subs"]:
            q=poly1(sp)
            if q is None: continue
            try:
                t=Polygon([f(x,y) for x,y in q.exterior.coords])
                if not t.is_valid: t=t.buffer(0)
            except Exception: continue
            if t.geom_type=="Polygon" and t.area>minarea: out.append(t)
    return sorted(out,key=lambda p:-p.area)

def north_of(m):
    """compass needle direction on the source page, as deg cw from page-up"""
    best=None
    for bucket in m["hL"].values():
        for r in bucket:
            if r.get("f")!=INK: continue
            for sp in r["subs"]:
                q=poly1(sp)
                if q is None or q.area<2 or q.area>90: continue
                if math.dist((q.centroid.x,q.centroid.y),(243.0,81.0))>13: continue
                P=np.array(sp,float); C=P.mean(0); Q=P-C
                u,s,vt=np.linalg.svd(Q,full_matrices=False); d=vt[0]
                pr=Q@d
                if (pr>0).sum()<(pr<0).sum(): d=-d
                best=math.degrees(math.atan2(d[0],-d[1]))
    return best

H={}
for n,m in M.items():
    f,th=tf_hole(m)
    h=dict(m)
    for key in ("fairway","water","sand","trees","putt"):
        h[key]=conv(m["hL"][key],f)
    h["green"]=conv([dict(subs=[list(m["greenpoly"].exterior.coords)],w=0)],f)[0] if m["greenpoly"] is not None else None
    h["teebox"]=conv([dict(subs=[list(m["teepoly"].exterior.coords)],w=0)],f)[0] if m["teepoly"] is not None else None
    if h["green"] is not None:
        g=h["green"]
        h["putt"]=[p for p in h["putt"] if p.centroid.distance(g.centroid)>2.5]
    gc=h["green"].centroid if h["green"] is not None else Point(0,m["to_green"])
    h["gc"]=(gc.x,gc.y)
    st=[]
    for r in m["hT"]:
        if re.fullmatch(r"[+-]\d+",r["text"]) and 5.5<=r["size"]<=6.4:
            st.append((f(r["cx"],r["cy"]),int(r["text"])))
    st.sort(key=lambda z:z[0][1])
    # approach direction = from the last station into the green
    ap=(st[-1][0] if st else (0.0,0.0))
    d=(gc.x-ap[0],gc.y-ap[1]); L=math.hypot(*d) or 1; d=(d[0]/L,d[1]/L)
    front=None
    if h["green"] is not None:
        ray=LineString([ap,(gc.x+d[0]*200,gc.y+d[1]*200)])
        hit=ray.intersection(h["green"].boundary)
        pts=[hit] if hit.geom_type=="Point" else [q for q in getattr(hit,"geoms",[]) if q.geom_type=="Point"]
        if pts: front=min(pts,key=lambda p:p.distance(Point(ap)))
    if front is None:
        front=Point(gc.x-d[0]*m["depth"]/2, gc.y-d[1]*m["depth"]/2)
    # the front edge must sit on the tee side of the centre
    if front.distance(Point(0,0))>gc.distance(Point(0,0)):
        front=Point(gc.x-d[0]*m["depth"]/2, gc.y-d[1]*m["depth"]/2)
    h["front"]=(front.x,front.y)
    fp=Point(*h["front"])
    h["stations"]=[dict(x=p[0],y=p[1],to_front=Point(p).distance(fp),
                        to_centre=Point(p).distance(gc),from_tee=math.hypot(*p),elev=v)
                   for p,v in st]
    # carry callouts, paired through the leader lines
    leaders=[]
    for r in m["hL"]["inkline"]:
        if r["w"]>0.7: continue
        for sp in r["subs"]:
            if len(sp)==2: leaders.append((sp[0],sp[1]))
    calls=[]
    for r in m["hT"]:
        if r["text"].isdigit() and 6.6<=r["size"]<=7.4:
            v=int(r["text"])
            if v==m["to_green"]: continue
            lp=(r["cx"],r["cy"]); pick=None; bd=1e9
            for a,b in leaders:
                for near,far in ((a,b),(b,a)):
                    dd=math.dist(near,lp)
                    if dd<bd and dd<18: bd=dd; pick=far
            if pick is None: pick=lp
            p=f(*pick)
            calls.append(dict(v=v,x=p[0],y=p[1],to_front=Point(p).distance(fp)))
    h["calls"]=sorted(calls,key=lambda c:-c["v"])
    h["arcs"]=sorted({int(r["text"]) for r in m["hT"] if r["text"].isdigit()
        and 5.5<=r["size"]<=6.4 and int(r["text"]) in (50,100,150,200,250,300)})
    h["north"]=north_of(m)
    # green page
    gf=tf_green(m)
    h["g_surface"]=conv([dict(subs=[list(m["gsurf"].exterior.coords)],w=0)],gf)[0] if m["gsurf"] is not None else None
    for a,b in (("collar","g_collar"),("sand","g_sand"),("water","g_water"),
                ("trees","g_trees"),("putt","g_putt"),("fairway","g_fairway")):
        h[b]=conv(m["gL"][a],gf)
    h["g_edge"]=[dict(v=int(r["text"]),pt=gf(r["cx"],r["cy"])) for r in m["gT"]
                 if r["text"].isdigit() and 6.0<=r["size"]<=7.0]
    H[n]=h
print("prepared",len(H),"holes")
for n in sorted(H):
    h=H[n]
    print(f" {n:2d} par{h['par']} sta={len(h['stations'])} calls={len(h['calls'])} "
          f"arcs={h['arcs']} fw={len(h['fairway'])} tr={len(h['trees'])} "
          f"surf={'y' if h['g_surface'] is not None else 'n'} edge={len(h['g_edge'])} "
          f"N={h['north'] if h['north'] is None else round(h['north'])}")
pickle.dump(H,open("book_models.pkl","wb"))

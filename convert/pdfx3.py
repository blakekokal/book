# -*- coding: utf-8 -*-
"""Shot Pattern PDF -> calibrated hole models. Validated against the book's own numbers."""
import pymupdf, math, re, pickle
import numpy as np
from collections import defaultdict
from shapely.geometry import Polygon, LineString, Point
from shapely.ops import unary_union

RD=lambda c: tuple(round(v,3) for v in c) if c else None
TREE=(0.5,0.7,0.42)
FWAY=(0.89,0.94,0.87);  FWAY_S=(0.7,0.82,0.66)
PUTT=(0.94,0.975,0.93); PUTT_S=(0.56,0.74,0.5)
COLLAR=(0.93,0.96,0.92)
INK=(0.07,0.09,0.12)
WATER=(0.8,0.89,0.97);  WATER_S=(0.42,0.63,0.85)
SAND=(0.94,0.88,0.72);  SAND_S=(0.74,0.63,0.42)
GRID=(0.8,0.8,0.8); REDAX=(0.8,0.22,0.22); ARC=(0.7,0.7,0.7)
NORM=lambda s: s.replace("−","-")

def flatten(items, steps=14):
    subs=[]; cur=[]
    for it in items:
        k=it[0]
        if k=="l":
            a,b=it[1],it[2]
            if not cur: cur=[(a.x,a.y)]
            cur.append((b.x,b.y))
        elif k=="c":
            p0,p1,p2,p3=it[1:5]
            if not cur: cur=[(p0.x,p0.y)]
            for s in range(1,steps+1):
                t=s/steps; m=1-t
                cur.append((m**3*p0.x+3*m*m*t*p1.x+3*m*t*t*p2.x+t**3*p3.x,
                            m**3*p0.y+3*m*m*t*p1.y+3*m*t*t*p2.y+t**3*p3.y))
        elif k=="re":
            r=it[1]
            if cur: subs.append(cur); cur=[]
            subs.append([(r.x0,r.y0),(r.x1,r.y0),(r.x1,r.y1),(r.x0,r.y1),(r.x0,r.y0)])
        elif k=="qu":
            q=it[1]
            if cur: subs.append(cur); cur=[]
            subs.append([(q.ul.x,q.ul.y),(q.ur.x,q.ur.y),(q.lr.x,q.lr.y),(q.ll.x,q.ll.y),(q.ul.x,q.ul.y)])
    if cur: subs.append(cur)
    return [s for s in subs if len(s)>=2]

def dedupe_text(page):
    seen=[]
    for b in page.get_text("dict")["blocks"]:
        for l in b.get("lines",[]):
            for s in l["spans"]:
                t=NORM(s["text"]).strip()
                if not t: continue
                bb=s["bbox"]; cx,cy=(bb[0]+bb[2])/2,(bb[1]+bb[3])/2
                if any(q["text"]==t and abs(q["cx"]-cx)<2.4 and abs(q["cy"]-cy)<2.4 for q in seen): continue
                seen.append(dict(text=t,cx=cx,cy=cy,x=bb[0],y=bb[1],size=round(s["size"],1)))
    return seen

def fit_circle(pts):
    P=np.asarray(pts,float)
    A=np.c_[2*P[:,0],2*P[:,1],np.ones(len(P))]
    sol,*_=np.linalg.lstsq(A,(P**2).sum(1),rcond=None)
    cx,cy=sol[0],sol[1]; r=math.sqrt(max(sol[2]+cx*cx+cy*cy,1e-9))
    return cx,cy,r,float(np.abs(np.hypot(P[:,0]-cx,P[:,1]-cy)-r).max())

def poly1(sp):
    if len(sp)<4: return None
    try:
        q=Polygon(sp)
        if not q.is_valid: q=q.buffer(0)
    except Exception: return None
    return q if q.geom_type=="Polygon" and q.area>0 else None

def classify(page):
    L=defaultdict(list)
    for d in page.get_drawings():
        f,s,w=RD(d.get("fill")),RD(d.get("color")),round(d.get("width") or 0,2)
        dash=(d.get("dashes") or "").strip()
        subs=flatten(d["items"])
        if not subs: continue
        r=dict(subs=subs,w=w,dash=dash,f=f,s=s)
        if   f==TREE:                    L["trees"].append(r)
        elif f==PUTT or s==PUTT_S:       L["putt"].append(r)
        elif f==COLLAR:                  L["collar"].append(r)
        elif f==FWAY or s==FWAY_S:       L["fairway"].append(r)
        elif f==WATER or s==WATER_S:     L["water"].append(r)
        elif f==SAND  or s==SAND_S:      L["sand"].append(r)
        elif s==REDAX:                   L["redaxis"].append(r)
        elif s==GRID and dash:           L["grid"].append(r)
        elif s==ARC  and dash:           L["arcs"].append(r)
        elif f==INK:                     L["dots"].append(r)
        elif s==INK:                     L["inkline"].append(r)
        else:                            L["other"].append(r)
    return L

def biggest(recs, minpts=8, minw=None):
    best=None
    for r in recs:
        if minw is not None and r["w"]<minw: continue
        for sp in r["subs"]:
            if len(sp)<minpts: continue
            q=poly1(sp)
            if q is None: continue
            if best is None or q.area>best.area: best=q
    return best

doc=pymupdf.open("src_book.pdf")
pages=defaultdict(dict)
for i in range(3,39):
    p=doc[i]; T=dedupe_text(p)
    cand=[r for r in T if r["size"]>=28 and r["x"]<50 and r["text"].isdigit()]
    if not cand: continue
    head=" ".join(r["text"] for r in T)
    pages[int(cand[0]["text"])]["green" if "DEPTH" in head else "hole"]=(T,classify(p),head)

M={}
for num in sorted(pages):
    hT,hL,hh = pages[num]["hole"]
    gT,gL,gh = pages[num]["green"]
    par=int(re.search(r"PAR (\d+)",hh).group(1)); hcp=int(re.search(r"HCP (\d+)",hh).group(1))
    to_green=int(re.search(r"(\d+) yd to green",hh).group(1))
    pm=re.search(r"PLAYS\s*([+-]?\d+)\s*YD",hh)
    plays=int(pm.group(1)) if pm else 0
    yards=max((int(r["text"]) for r in hT if r["size"]>=20 and r["x"]>100 and r["text"].isdigit()),default=None)
    depth=int(re.search(r"DEPTH (\d+) YDS",gh).group(1)); width=int(re.search(r"WIDTH (\d+) YDS",gh).group(1))
    # tee box: outlined fairway-fill shape (INK stroke, w>=0.7) nearest the page bottom
    # the tee box is the ink-outlined short-grass shape lowest on the page.
    # Quartz sometimes emits it as one fill+stroke op and sometimes as two,
    # so look for an INK stroke in every bucket.
    teepoly=None
    for bucket in hL.values():
        for r in bucket:
            if r.get("s")!=INK or r["w"]<0.7: continue
            for sp in r["subs"]:
                if len(sp)<8: continue
                q=poly1(sp)
                if q is None or q.area<4 or q.area>4000: continue
                if teepoly is None or q.centroid.y>teepoly.centroid.y: teepoly=q
    greenpoly=biggest(hL["putt"],minpts=10)
    tee=(teepoly.centroid.x,teepoly.centroid.y) if teepoly is not None else None
    aim=(greenpoly.centroid.x,greenpoly.centroid.y) if greenpoly is not None else None
    # scale: prefer the range arcs (a pure geometric ruler)
    fits=[]
    for r in hL["arcs"]:
        for sp in r["subs"]:
            if len(sp)<8: continue
            cx,cy,rad,err=fit_circle(sp)
            if err<2.5 and rad>20: fits.append(rad)
    labels=sorted({int(r["text"]) for r in hT if r["text"].isdigit()
                   and 5.5<=r["size"]<=6.4 and int(r["text"]) in (50,100,150,200,250,300)})
    if fits and labels:
        rr=sorted(fits); ll=sorted(labels)[:len(rr)]
        ypp=float(np.mean([l/r for l,r in zip(ll,rr)])); cal="arcs"
    else:
        ypp=to_green/math.dist(tee,aim); cal="tee->green"
    M[num]=dict(par=par,hcp=hcp,yards=yards,to_green=to_green,plays=plays,depth=depth,width=width,
                ypp=ypp,cal=cal,tee=tee,aim=aim,teepoly=teepoly,greenpoly=greenpoly,
                hT=hT,hL=hL,gT=gT,gL=gL)
    # green page scale from the red depth axis
    ax=None
    for r in gL["redaxis"]:
        for sp in r["subs"]:
            xs=[q[0] for q in sp]; ys=[q[1] for q in sp]
            if max(ys)-min(ys)>20 and max(xs)-min(xs)<6: ax=(float(np.mean(xs)),min(ys),max(ys))
    M[num]["gaxis"]=ax
    M[num]["gypp"]=depth/(ax[2]-ax[1]) if ax else None
    M[num]["gsurf"]=biggest(gL["inkline"],minpts=10,minw=0.95)

# ------- validation against the book's own printed carry numbers --------
print(f"{'#':>3} {'par':>3} {'cal':>10} {'yd/pt':>6} {'strt':>5} {'toG':>4} | carries printed vs computed")
allerr=[]
for n,m in M.items():
    k=m["ypp"]; tee=m["tee"]
    # each callout has a short leader line: one endpoint touches the label,
    # the far endpoint sits on the feature being measured
    leaders=[]
    for r in m["hL"]["inkline"]:
        if r["w"]>0.7: continue
        for sp in r["subs"]:
            if len(sp)==2: leaders.append((sp[0],sp[1]))
    dots=[]
    for r in m["hL"]["dots"]+m["hL"]["other"]:
        for sp in r["subs"]:
            q=poly1(sp)
            if q is not None and q.area<16 and q.length<18: dots.append((q.centroid.x,q.centroid.y))
    rows=[]
    for r in m["hT"]:
        if r["text"].isdigit() and 6.6<=r["size"]<=7.4:
            v=int(r["text"])
            if v==m["to_green"]: continue
            lp=(r["cx"],r["cy"])
            d=None; bestd=1e9
            for a,b in leaders:
                for near,far in ((a,b),(b,a)):
                    dd=math.dist(near,lp)
                    if dd<bestd and dd<18: bestd=dd; d=far
            if d is None and dots:
                cand=min(dots,key=lambda q:math.dist(q,lp))
                if math.dist(cand,lp)<20: d=cand
            if d is None: d=lp
            # snap to the nearest dot if one sits on that leader end
            if dots:
                sn=min(dots,key=lambda q:math.dist(q,d))
                if math.dist(sn,d)<5: d=sn
            comp=math.dist(d,tee)*k
            rows.append((v,comp)); allerr.append(abs(comp-v))
    m["carries"]=rows
    s=" ".join(f"{v}/{c:.0f}" for v,c in rows[:5])
    print(f"{n:3d} {m['par']:3d} {m['cal']:>10} {k:6.3f} {math.dist(tee,m['aim'])*k:5.0f} "
          f"{m['to_green']:4d} | {s}")
if allerr:
    a=np.array(allerr)
    print(f"\ncarry check over {len(a)} printed numbers: median |err| = {np.median(a):.1f} yd, "
          f"90th pct = {np.percentile(a,90):.1f} yd, max = {a.max():.1f} yd")
pickle.dump(M,open("models3.pkl","wb"))
print("wrote models3.pkl")

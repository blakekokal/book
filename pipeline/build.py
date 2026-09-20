"""Compute every number that lands on the Bridlewood #1 pages."""
import json, math, pickle
import numpy as np
from shapely.geometry import Polygon, LineString, Point, MultiPoint
from shapely.ops import unary_union
from model import load_osm, DEM, Y, GREEN_ID, TEE_BLACK, HOLE_ID, TEE_LADDER

F=load_osm(); by={f["id"]:f for f in F}
green=by[GREEN_ID]["geom"]
hole=by[HOLE_ID]["geom"]
tees={i:by[i]["geom"] for i in TEE_LADDER}
teeB=tees[TEE_BLACK]
gc=green.centroid

# ---------- line of play -------------------------------------------------
cs=list(hole.coords)
lop_pts=[(teeB.centroid.x,teeB.centroid.y)]+list(cs[1:-1])+[(gc.x,gc.y)]
lop=LineString(lop_pts)
def seg_dirs(pts):
    out=[]
    for i in range(len(pts)-1):
        dx=pts[i+1][0]-pts[i][0]; dy=pts[i+1][1]-pts[i][1]; L=math.hypot(dx,dy)
        out.append((dx/L,dy/L,L))
    return out
DIRS=seg_dirs(lop_pts)

# green front: where the final approach line enters the green
appr_from=lop_pts[-2]
ray=LineString([appr_from,(gc.x+(gc.x-appr_from[0])*3, gc.y+(gc.y-appr_from[1])*3)])
inter=ray.intersection(green.boundary)
pts=[inter] if inter.geom_type=="Point" else list(inter.geoms)
pts=[p for p in pts if p.geom_type=="Point"]
front=min(pts,key=lambda p:Point(appr_from).distance(p))
back =max(pts,key=lambda p:Point(appr_from).distance(p))
depth=front.distance(back)/Y
print("green depth along line of play: %.1f yd"%depth)
print("green front->centroid: %.1f yd"%(front.distance(gc)/Y))

# ---------- DEM ----------------------------------------------------------
b=json.load(open("corridor_meta.json"))["bounds"]
dem=DEM(tuple(b),1.0,"corridor")
gb=green.buffer(42).bounds
demG=DEM(gb,0.5,"greenhi")
def zc(p): return float(dem.z(p.x,p.y))
z_front=float(demG.z(front.x,front.y)); z_gc=float(demG.z(gc.x,gc.y))
print("z front %.2f  centroid %.2f m"%(z_front,z_gc))

# ---------- station chainage helpers ------------------------------------
def chain_to_xy(d_yd):
    """point at distance d (yd) from the black tee along the line of play"""
    rem=d_yd*Y
    for (ux,uy,L),p in zip(DIRS,lop_pts):
        if rem<=L or (ux,uy,L) is DIRS[-1]:
            return (p[0]+ux*rem, p[1]+uy*rem)
        rem-=L
def xy_to_chain(x,y):
    """distance from tee along line of play of the projection of (x,y)"""
    acc=0; best=None
    for (ux,uy,L),p in zip(DIRS,lop_pts):
        t=(x-p[0])*ux+(y-p[1])*uy
        tc=max(0,min(L,t))
        perp=abs(-(x-p[0])*uy+(y-p[1])*ux)
        d=math.hypot(x-(p[0]+ux*tc), y-(p[1]+uy*tc))
        if best is None or d<best[0]: best=(d,(acc+tc)/Y,perp/Y)
        acc+=L
    return best[1]
front_chain=xy_to_chain(front.x,front.y)
gc_chain=xy_to_chain(gc.x,gc.y)
print("front at chainage %.1f yd ; centre %.1f yd"%(front_chain,gc_chain))

# ---------- corridor features -------------------------------------------
corr=lop.buffer(75)
bunkers=[f for f in F if f["kind"]=="bunker" and f["geom"].geom_type=="Polygon"
         and f["geom"].intersects(corr)]
water=[f for f in F if f["kind"] in ("water","lateral_water_hazard") and
       f["geom"].geom_type=="Polygon" and f["geom"].intersects(corr)]
paths=[f for f in F if f["kind"] in ("path","cartpath") and f["geom"].intersects(corr)]
rough=[f for f in F if f["kind"]=="rough" and f["geom"].geom_type=="Polygon"
       and f["geom"].intersects(corr)]
othergreens=[f for f in F if f["kind"]=="green" and f["id"]!=GREEN_ID and f["geom"].intersects(corr)]
otherteesG=[f for f in F if f["kind"]=="tee" and f["id"] not in TEE_LADDER and f["geom"].intersects(corr)]
print("corridor: %d bunkers, %d water, %d paths, %d rough"%(len(bunkers),len(water),len(paths),len(rough)))

def side_of(geom):
    """which side of the line of play (L/R looking at the green)"""
    c=geom.centroid
    acc=0; best=None
    for (ux,uy,L),p in zip(DIRS,lop_pts):
        t=max(0,min(L,(c.x-p[0])*ux+(c.y-p[1])*uy))
        d=math.hypot(c.x-(p[0]+ux*t), c.y-(p[1]+uy*t))
        s=-(c.x-p[0])*uy+(c.y-p[1])*ux
        if best is None or d<best[0]: best=(d,s)
        acc+=L
    return "L" if best[1]>0 else "R"

def edges_chain(geom):
    """near / far chainage of a polygon measured along the line of play"""
    ch=[xy_to_chain(x,y) for x,y in geom.exterior.coords]
    return min(ch),max(ch)

# ---------- bunker / hazard callouts ------------------------------------
carries=[]
for f in bunkers:
    n,fa=edges_chain(f["geom"])
    carries.append(dict(id=f["id"],near=n,far=fa,side=side_of(f["geom"]),
                        to_front=front_chain-n, area=f["geom"].area/Y/Y))
carries.sort(key=lambda d:d["near"])
print("\nBUNKERS (chainage from black tee):")
for c in carries:
    print("  id=%d %s near=%3.0f far=%3.0f  toFront(near)=%3.0f  %4.0f sqyd"%(
        c["id"],c["side"],c["near"],c["far"],c["to_front"],c["area"]))

# ---------- reference stations ------------------------------------------
stations=[]
for d in range(50,int(front_chain)+1,25):
    x,y=chain_to_xy(d)
    p=Point(x,y)
    stations.append(dict(chain=d, x=x,y=y,
        to_front=front_chain-d, to_centre=gc_chain-d,
        z=zc(p)))
for s in stations:
    s["elev_to_front"]=(z_front-s["z"])/Y
    s["elev_from_tee"]=(s["z"]-zc(Point(*chain_to_xy(0))))/Y
print("\nSTATIONS: %d from %d to %d yd"%(len(stations),stations[0]["chain"],stations[-1]["chain"]))
for s in stations[:4]+stations[-3:]:
    print("  %3d yd  toFront=%3.0f toCentre=%3.0f  elev_to_front=%+.1f elev_from_tee=%+.1f"%(
        s["chain"],s["to_front"],s["to_centre"],s["elev_to_front"],s["elev_from_tee"]))

# ---------- tee ladder --------------------------------------------------
NAMES={869885492:"Black",869885490:"Blue",869885491:"White",749964166:"Red"}
CARD={"Black":428,"Blue":403,"White":391,"Red":354}
ladder=[]
z0=zc(teeB.centroid)
for tid in TEE_LADDER:
    g=tees[tid]; c=g.centroid
    ladder.append(dict(id=tid,name=NAMES[tid],
        back_offset=xy_to_chain(c.x,c.y),
        to_front=front_chain-xy_to_chain(c.x,c.y),
        z=zc(c), dz=(zc(c)-z0)/Y, card=CARD[NAMES[tid]]))
print("\nTEE LADDER:")
for t in ladder:
    print("  %-6s offset=%+5.0f  toFront=%3.0f  dz=%+.1f yd  card=%d"%(
        t["name"],t["back_offset"],t["to_front"],t["dz"],t["card"]))

pickle.dump(dict(green=green,front=front,back=back,depth=depth,gc=gc,
    lop_pts=lop_pts,DIRS=DIRS,front_chain=front_chain,gc_chain=gc_chain,
    bunkers=[(f["id"],f["geom"]) for f in bunkers],
    water=[(f["id"],f["geom"]) for f in water],
    paths=[(f["id"],f["geom"]) for f in paths],
    rough=[(f["id"],f["geom"]) for f in rough],
    othergreens=[(f["id"],f["geom"]) for f in othergreens],
    otherteesG=[(f["id"],f["geom"]) for f in otherteesG],
    tees={k:v for k,v in tees.items()},
    carries=carries, stations=stations, ladder=ladder,
    z_front=z_front, z_gc=z_gc, corridor_bounds=b, green_bounds=gb),
    open("hole1.pkl","wb"))
print("\nwrote hole1.pkl")

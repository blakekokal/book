# -*- coding: utf-8 -*-
"""Render Bridlewood #1 as a tour-style yardage-book spread."""
import pickle, math, json
import numpy as np
from scipy import ndimage as ndi
from reportlab.pdfgen import canvas
from reportlab.lib.colors import Color, HexColor
from reportlab.lib.utils import ImageReader
from shapely.geometry import Polygon, LineString, Point, MultiPolygon
from shapely.ops import unary_union
from model import DEM, Y

PT=72.0
PW,PH=4.0*PT,7.0*PT                      # 4in x 7in page
MG=0.17*PT

C_ROUGH   = HexColor("#DCDCA6")
C_ROUGH2  = HexColor("#E8E7C4")
C_TURF    = HexColor("#FFFFFF")
C_BUNKER  = HexColor("#F2EEA8")
C_BUNKED  = HexColor("#B9B45E")
C_GREEN   = HexColor("#AFC96B")
C_GREENED = HexColor("#7E9642")
C_WATER   = HexColor("#9FC2CE")
C_WATERED = HexColor("#5E8persist")  if False else HexColor("#5E8A99")
C_PATH    = HexColor("#BFBFBF")
C_RED     = HexColor("#C0392B")
C_INK     = HexColor("#1A1A1A")
C_NAVY    = HexColor("#1B2A4A")
C_HATCH   = HexColor("#B9B9B9")
C_CONT    = HexColor("#9A9A9A")
C_GRID    = HexColor("#7FA8C9")

D=pickle.load(open("hole1.pkl","rb"))
GF=pickle.load(open("greenfield.pkl","rb"))
TURF=pickle.load(open("turf_polys.pkl","rb"))
TREES=pickle.load(open("tree_polys.pkl","rb"))
C_TREE=HexColor("#BFCE9A")
C_TREED=HexColor("#8CA061")
green=D["green"]; front=D["front"]; gc=D["gc"]; lop=D["lop_pts"]; DIRS=D["DIRS"]
front_chain=D["front_chain"]; gc_chain=D["gc_chain"]

# --- front / back measured as the extent of the green along the line of play
import numpy as _np
_pts=_np.array(green.exterior.coords)
_appr=_np.array(lop[-2]); _gcv=_np.array([gc.x,gc.y])
_v=_gcv-_appr; _v=_v/_np.linalg.norm(_v)
_al=(_pts-_gcv)@_v
_perp=_np.array([-_v[1],_v[0]])
_ac=(_pts-_gcv)@_perp
_i0=int(_al.argmin()); _i1=int(_al.argmax())
front=Point(*(_gcv+_v*_al.min()))
back =Point(*(_gcv+_v*_al.max()))
depth=(_al.max()-_al.min())/Y
width=(_ac.max()-_ac.min())/Y
front_chain=gc_chain-(_al.max()-_al.min())/2/Y-(-_al.min()-(_al.max()-_al.min())/2)/Y
front_chain=gc_chain+_al.min()/Y
D["depth"]=depth

def chain_to_xy(d):
    """point at chainage d (yards) from the black tee; extrapolates past both ends"""
    rem=d*Y
    if rem<0:
        ux,uy,_=DIRS[0]; p=lop[0]
        return (p[0]+ux*rem, p[1]+uy*rem)
    for i,((ux,uy,L),p) in enumerate(zip(DIRS,lop)):
        if rem<=L or i==len(DIRS)-1:
            return (p[0]+ux*rem, p[1]+uy*rem)
        rem-=L

# ---------------- frames -------------------------------------------------
class Frame:
    """rotate + scale local metres -> page points"""
    def __init__(self,ang,scale,ox,oy,cx=0,cy=0):
        self.c=math.cos(ang); self.s=math.sin(ang); self.k=scale
        self.ox,self.oy=ox,oy; self.cx,self.cy=cx,cy
    def __call__(self,x,y):
        dx,dy=x-self.cx,y-self.cy
        rx=dx*self.c-dy*self.s; ry=dx*self.s+dy*self.c
        return (self.ox+rx*self.k, self.oy+ry*self.k)
    def poly(self,g):
        return [self(x,y) for x,y in g]

def ring(p):  return list(p.exterior.coords)

def draw_poly(c,f,poly,fill=None,stroke=None,lw=0.5,dash=None):
    if poly.is_empty: return
    gs=[poly] if poly.geom_type=="Polygon" else list(poly.geoms)
    for g in gs:
        pts=f.poly(ring(g))
        pth=c.beginPath(); pth.moveTo(*pts[0])
        for q in pts[1:]: pth.lineTo(*q)
        pth.close()
        if fill is not None: c.setFillColor(fill)
        if stroke is not None:
            c.setStrokeColor(stroke); c.setLineWidth(lw)
            if dash: c.setDash(dash)
            else: c.setDash()
        c.drawPath(pth, stroke=1 if stroke else 0, fill=1 if fill is not None else 0)

def draw_line(c,f,coords,col,lw=0.5,dash=None,cap=1):
    pts=f.poly(coords)
    c.setStrokeColor(col); c.setLineWidth(lw); c.setLineCap(cap)
    c.setDash(dash) if dash else c.setDash()
    p=c.beginPath(); p.moveTo(*pts[0])
    for q in pts[1:]: p.lineTo(*q)
    c.drawPath(p,stroke=1,fill=0)

def txt(c,x,y,s,size=5.2,col=C_INK,font="Helvetica",anchor="l",rot=0):
    c.saveState(); c.setFillColor(col); c.setFont(font,size)
    c.translate(x,y)
    if rot: c.rotate(rot)
    if anchor=="c": c.drawCentredString(0,0,s)
    elif anchor=="r": c.drawRightString(0,0,s)
    else: c.drawString(0,0,s)
    c.restoreState()

# ---------------- slope feather field (hole page) -----------------------
def feather_field(c,f,dem,clip_poly,step_m=3.4,minslope=0.012,col=C_HATCH,lw=0.22,length=2.6):
    x0,y0,x1,y1=clip_poly.bounds
    xs=np.arange(x0,x1,step_m); ys=np.arange(y0,y1,step_m)
    c.setStrokeColor(col); c.setLineWidth(lw); c.setDash()
    prep=clip_poly
    for yy in ys:
        row=[]
        for xx in xs:
            if not prep.contains(Point(xx,yy)): continue
            e=1.0
            zx=(float(dem.z(xx+e,yy))-float(dem.z(xx-e,yy)))/(2*e)
            zy=(float(dem.z(xx,yy+e))-float(dem.z(xx,yy-e)))/(2*e)
            s=math.hypot(zx,zy)
            if s<minslope: continue
            row.append((xx,yy,-zx,-zy,s))
        for xx,yy,dx,dy,s in row:
            n=math.hypot(dx,dy) or 1
            dx,dy=dx/n,dy/n
            px,py=f(xx,yy)
            ex,ey=f(xx+dx*step_m*0.62, yy+dy*step_m*0.62)
            p=c.beginPath(); p.moveTo(px,py); p.lineTo(ex,ey)
            # barbs
            ang=math.atan2(ey-py,ex-px); L=length*min(1.0,0.45+s*14)
            for sg in (+1,-1):
                a=ang+sg*2.5
                p.moveTo(ex,ey); p.lineTo(ex+L*math.cos(a), ey+L*math.sin(a))
            c.drawPath(p,stroke=1,fill=0)

# ---------------- number block ------------------------------------------
def numblock(c,f,x,y,red,elev_f,paren,black,elev_t,side="r",dot=True,size=4.6):
    px,py=f(x,y)
    if dot:
        c.setFillColor(C_INK); c.circle(px,py,0.85,stroke=0,fill=1)
    dx = 3.0 if side=="r" else -3.0
    anc= "l" if side=="r" else "r"
    s1=f"{red:.0f}"
    txt(c,px+dx,py+1.0,s1,size,C_RED,"Helvetica-Bold",anc)
    w=c.stringWidth(s1,"Helvetica-Bold",size)
    if elev_f is not None and abs(elev_f)>=0.5:
        txt(c,px+dx+(w+1.0 if side=="r" else -w-1.0),py+2.2,f"{elev_f:+.0f}",size*0.72,C_INK,"Helvetica",anc)
    s2=(f"({paren:.0f}) " if paren is not None else "")+f"{black:.0f}"
    txt(c,px+dx,py-4.0,s2,size*0.92,C_INK,"Helvetica",anc)

# =========================================================================
c=canvas.Canvas("bridlewood_01.pdf",pagesize=(PW,PH))
c.setTitle("Bridlewood Golf Club - Hole 1 - Yardage Book")
c.setAuthor("prototype")

# ============ PAGE 1 : notes + green blow-up =============================
def page_green():
    c.setFillColor(HexColor("#FFFFFF")); c.rect(0,0,PW,PH,stroke=0,fill=1)
    # hole badge
    c.setFillColor(C_NAVY); c.circle(MG+11,PH-MG-11,11,stroke=0,fill=1)
    txt(c,MG+11,PH-MG-14.5,"1",15,HexColor("#FFFFFF"),"Helvetica-Bold","c")
    txt(c,MG+28,PH-MG-11,"BRIDLEWOOD GOLF CLUB",6.4,C_NAVY,"Helvetica-Bold")
    txt(c,MG+28,PH-MG-19,"FLOWER MOUND, TEXAS  ·  PAR 4  ·  428 YARDS (BLACK)",4.8,C_INK)
    c.setStrokeColor(C_NAVY); c.setLineWidth(0.7)
    c.line(MG,PH-MG-30,PW-MG,PH-MG-30)

    # --- notes area (top) ---
    note_top=PH-MG-36; note_bot=PH*0.520
    txt(c,MG,note_top-6,"NOTES",5.0,HexColor("#9A9A9A"),"Helvetica-Bold")
    c.setStrokeColor(HexColor("#E3E3E3")); c.setLineWidth(0.35)
    yy=note_top-16
    while yy>note_bot+6:
        c.line(MG,yy,PW-MG,yy); yy-=11
    c.setStrokeColor(HexColor("#CFCFCF")); c.setLineWidth(0.5)
    c.line(MG,note_bot,PW-MG,note_bot)

    # --- green blow-up (bottom) ---
    # MLR G-11 caps green images at 3/8 inch to 5 yards; use that or smaller
    SC_CAP=(0.375*PT)/(5*Y)
    ang=math.atan2(gc.x-front.x, gc.y-front.y)
    def rot(x,y):
        dx,dy=x-gc.x,y-gc.y
        return (dx*math.cos(ang)-dy*math.sin(ang), dx*math.sin(ang)+dy*math.cos(ang))
    # extent must cover the green, its greenside sand and the depth scale
    ext=[green]+[g for _,g in D["bunkers"] if g.distance(green)<16]
    rp=[rot(*p) for g in ext for p in ring(g)]
    rpg=[rot(*p) for p in ring(green)]
    SCALE_GUTTER=24.0            # points reserved for the depth scale, left
    x_lo=min(p[0] for p in rp); x_hi=max(p[0] for p in rp)
    y_lo=min(p[1] for p in rp); y_hi=max(p[1] for p in rp)
    area_h=note_bot-(MG+30)
    avail_w=PW-MG*2-SCALE_GUTTER-6
    SC=min(SC_CAP, avail_w/(x_hi-x_lo), (area_h-22)/(y_hi-y_lo))
    area_cx=MG+SCALE_GUTTER+(avail_w/2)-((x_lo+x_hi)/2)*SC
    area_cy=MG+30+area_h/2-((y_lo+y_hi)/2)*SC
    f=Frame(ang,SC,area_cx,area_cy,gc.x,gc.y)

    # surrounding sand
    for gid,g in D["bunkers"]:
        if g.distance(green)<30:
            draw_poly(c,f,g,C_BUNKER,C_BUNKED,0.5)
    # contours (6 in on the surface, from lidar)
    for lev,seg in GF["contours"]:
        if len(seg)<8: continue
        draw_line(c,f,seg,C_CONT,0.25)
    # putting surface
    draw_poly(c,f,green,HexColor("#FAFBF6"),C_INK,1.15)

    # 5 x 5 grid, aligned to the line of play
    rx0=min(p[0] for p in rpg); rx1=max(p[0] for p in rpg)
    ry0=min(p[1] for p in rpg); ry1=max(p[1] for p in rpg)
    def unrot(rx,ry):
        return (gc.x+rx*math.cos(-ang)-ry*math.sin(-ang),
                gc.y+rx*math.sin(-ang)+ry*math.cos(-ang))
    c.saveState()
    pth=c.beginPath(); gp=f.poly(ring(green)); pth.moveTo(*gp[0])
    for q in gp[1:]: pth.lineTo(*q)
    pth.close(); c.clipPath(pth,stroke=0,fill=0)
    c.setStrokeColor(C_GRID); c.setLineWidth(0.32)
    for i in range(1,5):
        t=rx0+(rx1-rx0)*i/5
        a=f(*unrot(t,ry0-3)); b2=f(*unrot(t,ry1+3)); c.line(a[0],a[1],b2[0],b2[1])
        t=ry0+(ry1-ry0)*i/5
        a=f(*unrot(rx0-3,t)); b2=f(*unrot(rx1+3,t)); c.line(a[0],a[1],b2[0],b2[1])
    c.restoreState()

    # slope arrows, 4% and steeper, pointing downhill
    XX,YY,SL,GXg,GYg,INS=GF["XX"],GF["YY"],GF["slope"],GF["gx"],GF["gy"],GF["inside"]
    ny,nx=SL.shape
    px_m=(XX[0,1]-XX[0,0]); st=max(1,int(round(1.30/px_m)))
    c.setStrokeColor(HexColor("#333333")); c.setLineWidth(0.27); c.setDash()
    grown=ndi.binary_dilation(INS,np.ones((7,7)))
    for i in range(0,ny,st):
        for j in range(0,nx,st):
            if not grown[i,j] or SL[i,j]<0.04: continue
            dx,dy=-GXg[i,j],-GYg[i,j]
            n=math.hypot(dx,dy) or 1; dx,dy=dx/n,dy/n
            x,y=XX[i,j],YY[i,j]; L=1.05
            a=f(x-dx*L/2,y-dy*L/2); b2=f(x+dx*L/2,y+dy*L/2)
            a2=math.atan2(b2[1]-a[1],b2[0]-a[0]); hl=1.5
            p=c.beginPath(); p.moveTo(*a); p.lineTo(*b2)
            for sg in (+1,-1):
                aa=a2+sg*2.55
                p.moveTo(*b2); p.lineTo(b2[0]+hl*math.cos(aa), b2[1]+hl*math.sin(aa))
            c.drawPath(p,stroke=1,fill=0)

    # front marker
    fp=f(front.x,front.y)
    c.setFillColor(HexColor("#FFFFFF")); c.setStrokeColor(C_INK); c.setLineWidth(0.7)
    c.circle(fp[0],fp[1],2.1,stroke=1,fill=1)
    txt(c,fp[0],fp[1]-8.5,"GREEN FRONT",3.8,C_INK,"Helvetica-Bold","c")

    # depth scale down the left-hand side
    ux,uy=(gc.x-front.x),(gc.y-front.y); nn=math.hypot(ux,uy); ux,uy=ux/nn,uy/nn
    # front and centre both sit on the play axis, so the scale is a page-space ruler
    sx = area_cx + rx0*SC - 9.0
    c.setStrokeColor(HexColor("#8FA9C4")); c.setLineWidth(0.45)
    ys=[]
    for d5 in range(0,int(round(depth))+6,5):
        py=f(front.x+ux*d5*Y, front.y+uy*d5*Y)[1]
        ys.append(py)
        c.line(sx-5.5,py,sx,py)
        txt(c,sx-7.5,py-1.5,str(d5),4.2,HexColor("#5E7FA3"),"Helvetica","r")
    c.setLineWidth(0.3); c.line(sx-2.7,min(ys),sx-2.7,max(ys))
    txt(c,sx-7.5,max(ys)+7,"YDS",3.6,HexColor("#5E7FA3"),"Helvetica-Bold","r")

    # depth + width callout
    txt(c,PW-MG-2,note_bot-14,f"{depth:.0f}",13,C_RED,"Helvetica-Bold","r")
    txt(c,PW-MG-2,note_bot-21,"YARDS DEEP",4.2,C_RED,"Helvetica-Bold","r")
    txt(c,PW-MG-2,note_bot-28,f"{width:.0f} YARDS WIDE",4.2,HexColor("#777777"),"Helvetica","r")

    # scale + rules note
    sc_in=SC*5*Y/PT
    lbl = "3/8 INCH" if abs(sc_in-0.375)<0.002 else f"{sc_in:.3f} INCH"
    txt(c,MG,MG+16,f"PUTTING GREEN SCALED AT {lbl} TO 5 YARDS \u2014 THE G-11 MAXIMUM" if abs(sc_in-0.375)<0.002
        else f"PUTTING GREEN SCALED AT {lbl} TO 5 YARDS (G-11 MAXIMUM 3/8)",3.9,HexColor("#6E6E6E"),"Helvetica-Bold")
    txt(c,MG,MG+10.5,"ARROWS SHOW SLOPE OF 4% OR MORE \u00b7 CONTOURS AT 6 INCHES",3.9,HexColor("#6E6E6E"))
    txt(c,MG,MG+4,"Surface from USGS 3DEP lidar \u00b7 outlines \u00a9 OpenStreetMap contributors (ODbL)",3.4,HexColor("#9A9A9A"))
    bearing=math.degrees(math.atan2(gc.x-front.x, gc.y-front.y))
    nx2,ny2=PW-MG-13,MG+32
    c.saveState(); c.translate(nx2,ny2); c.rotate(-bearing)
    c.setStrokeColor(C_INK); c.setLineWidth(0.5)
    c.line(0,-6,0,6); c.line(0,6,-2,3); c.line(0,6,2,3)
    c.restoreState()
    txt(c,nx2,ny2+9,"N",4.2,C_INK,"Helvetica-Bold","c")
page_green()
c.showPage()

# ============ PAGE 2 : hole layout =======================================
def page_hole():
    c.setFillColor(HexColor("#FFFFFF")); c.rect(0,0,PW,PH,stroke=0,fill=1)
    tee0=chain_to_xy(0)
    # rotate so tee->green is up
    ang=math.atan2(gc.x-tee0[0], gc.y-tee0[1])
    # clip the mown envelope to this hole's corridor so the neighbouring
    # fairway does not bleed into the page
    spine=LineString([chain_to_xy(d) for d in range(-40,int(front_chain)+60,5)])
    CORR=spine.buffer(58.0,cap_style=2,join_style=1)
    TURFC=[]
    for t in TURF:
        z=t.intersection(CORR)
        for g in ([z] if z.geom_type=="Polygon" else list(getattr(z,"geoms",[]))):
            if g.geom_type=="Polygon" and g.area/Y/Y>1500: TURFC.append(g)
    # build draw set to compute extent
    items=[green]+[g for _,g in D["bunkers"]]+TURFC
    allpts=[]
    for g in items:
        allpts+= ring(g) if g.geom_type=="Polygon" else []
    allpts+=[tee0,(gc.x,gc.y)]
    cx,cy=(tee0[0]+gc.x)/2,(tee0[1]+gc.y)/2
    def rot(x,y):
        dx,dy=x-cx,y-cy
        return (dx*math.cos(ang)-dy*math.sin(ang), dx*math.sin(ang)+dy*math.cos(ang))
    rp=[rot(*p) for p in allpts]
    # vertical extent driven by tee..beyond green
    top_m   = rot(*chain_to_xy(front_chain+40))[1]
    bot_m   = rot(*chain_to_xy(-14))[1]
    avail_h = PH-MG*2-46
    avail_w = PW-MG*2
    SC = min(avail_h/(top_m-bot_m), avail_w/132.0)
    f=Frame(ang,SC,PW/2,MG+34+avail_h/2-((top_m+bot_m)/2)*SC,cx,cy)

    # rough background
    c.setFillColor(C_ROUGH); c.rect(0,0,PW,PH,stroke=0,fill=1)
    # turf envelope
    for t in TURFC:
        draw_poly(c,f,t,C_TURF,None)
    dem=DEM(tuple(D["corridor_bounds"]),1.0,"corridor")
    # ground contour feathers inside turf
    c.saveState()
    pth=c.beginPath()
    for t in TURFC:
        q=f.poly(ring(t)); pth.moveTo(*q[0])
        for z in q[1:]: pth.lineTo(*z)
        pth.close()
    c.clipPath(pth,stroke=0,fill=0)
    feather_field(c,f,dem,unary_union(TURFC).buffer(-2),step_m=3.8,minslope=0.014,lw=0.2,length=2.3)
    c.restoreState()
    for t in TURFC:
        draw_poly(c,f,t,None,C_INK,0.75)

    # tree canopy (from NAIP texture/NDVI)
    for t in TREES:
        z=t.intersection(CORR.buffer(26))
        for g in ([z] if z.geom_type=="Polygon" else list(getattr(z,"geoms",[]))):
            if g.geom_type=="Polygon" and g.area/Y/Y>110:
                draw_poly(c,f,g,C_TREE,C_TREED,0.4)

    # water, paths, bunkers, green
    for gid,g in D["water"]:
        draw_poly(c,f,g,C_WATER,C_WATERED,0.5)
    for gid,g in D["paths"]:
        if g.geom_type=="LineString":
            draw_line(c,f,list(g.coords),C_PATH,1.9)
    for gid,g in D["bunkers"]:
        draw_poly(c,f,g,C_BUNKER,C_BUNKED,0.5)
    for gid,g in D["othergreens"]:
        draw_poly(c,f,g,HexColor("#D8E3BE"),HexColor("#A9BC84"),0.4)
    draw_poly(c,f,green,C_GREEN,C_GREENED,0.8)

    # tee boxes
    for t in D["ladder"]:
        g=D["tees"][t["id"]]
        blk = t["name"]=="Black"
        draw_poly(c,f,g,HexColor("#3A3A3A") if blk else HexColor("#FFFFFF"),C_INK,0.5)

    # centre line
    ll=[chain_to_xy(d) for d in range(0,int(front_chain)+1,4)]
    draw_line(c,f,ll,HexColor("#B4B4B4"),0.35,dash=(1.2,1.6))

    # distance arcs to front of green
    for arc in (100,125,150,175,200,250):
        d=front_chain-arc
        if d<12: continue
        x,y=chain_to_xy(d)
        ux,uy=DIRS[-1][0],DIRS[-1][1]
        for (uxs,uys,L),p in zip(DIRS,lop):
            pass
        nx_,ny_=-uy,ux
        seg=[(x+nx_*t, y+ny_*t) for t in np.linspace(-52,-14,10)]
        draw_line(c,f,seg,HexColor("#9AA5B1"),0.3,dash=(1.0,1.4))
        a=f(*seg[0])
        c.setFillColor(HexColor("#FFFFFF")); c.setStrokeColor(C_INK); c.setLineWidth(0.35)
        c.rect(a[0]-12.8,a[1]-2.7,11.6,5.4,stroke=1,fill=1)
        txt(c,a[0]-7.0,a[1]-1.1,str(arc),4.3,C_INK,"Helvetica-Bold","c")

    # reference stations
    for s in D["stations"]:
        if s["chain"]<70: continue
        side="r"
        numblock(c,f,s["x"],s["y"],s["to_front"],s["elev_to_front"],
                 s["to_centre"],s["chain"],s["elev_from_tee"],side=side)

    # bunker carries
    for i,b in enumerate(D["carries"]):
        g=[g for gid,g in D["bunkers"] if gid==b["id"]][0]
        cpt=g.centroid
        px,py=f(cpt.x,cpt.y)
        off = 7.5 if b["side"]=="R" else -7.5
        anc = "l" if b["side"]=="R" else "r"
        if b["to_front"]>=2:
            txt(c,px+off,py+1.6,f"{b['to_front']:.0f}",4.4,C_RED,"Helvetica-Bold",anc)
            txt(c,px+off,py-3.4,f"{b['near']:.0f}",4.2,C_INK,"Helvetica",anc)
        else:
            txt(c,px+off,py-0.8,f"{b['near']:.0f}",4.2,C_INK,"Helvetica",anc)

    # tee fan: carry + run-out lines from the black tee
    t0=chain_to_xy(0)
    fan=[]
    for b in D["carries"]:
        if 150<b["near"]<330: fan.append((b["near"],b["far"],b["side"]))
    letters="ABCDE"; nums="123"
    c.setStrokeColor(HexColor("#6E6E6E")); c.setLineWidth(0.3)
    box_y=MG+26
    for i,(near,far,side) in enumerate(fan[:3]):
        p2=chain_to_xy(far)
        a=f(*t0); b2=f(*p2)
        c.setDash(1.1,1.5); c.setStrokeColor(HexColor("#8A8A8A")); c.setLineWidth(0.3)
        c.line(a[0],a[1],b2[0],b2[1]); c.setDash()
        c.setFillColor(HexColor("#FFFFFF")); c.setStrokeColor(C_INK); c.setLineWidth(0.4)
        c.circle(b2[0]-9.5,b2[1],2.4,stroke=1,fill=1)
        txt(c,b2[0]-9.5,b2[1]-1.5,letters[i],4.0,C_INK,"Helvetica-Bold","c")
        txt(c,b2[0]-14.5,b2[1]-1.5,f"{far:.0f}",4.2,C_INK,"Helvetica-Bold","r")

    # tee inset box
    bw,bh=64,34
    bx,by=MG+1,MG+15
    c.setFillColor(HexColor("#FFFFFF")); c.setStrokeColor(C_INK); c.setLineWidth(0.5)
    c.rect(bx,by,bw,bh,stroke=1,fill=1)
    txt(c,bx+3,by+bh-7,"TEES",4.6,C_INK,"Helvetica-Bold")
    for i,t in enumerate(D["ladder"]):
        yy=by+bh-13-i*6
        c.setFillColor(HexColor("#FFFFFF")); c.setStrokeColor(C_INK); c.setLineWidth(0.4)
        c.rect(bx+4,yy-1.6,4.6,3.4,stroke=1,fill=1)
        txt(c,bx+12,yy-0.8,t["name"].upper(),4.0,C_INK,"Helvetica-Bold")
        txt(c,bx+bw-4,yy-0.8,f"{t['card']}",4.4,C_INK,"Helvetica-Bold","r")
        dzs = "0" if abs(t['dz'])<0.2 else f"{t['dz']:+.1f}"
        txt(c,bx+bw-20,yy-0.8,dzs,3.6,HexColor("#7A7A7A"),"Helvetica","r")

    # hole id block
    hx,hy=PW-MG-2,MG+2
    txt(c,hx-26,hy+20,"1",21,C_NAVY,"Helvetica-Bold","c")
    c.setStrokeColor(C_NAVY); c.setLineWidth(0.6)
    c.line(hx-44,hy+17,hx-8,hy+17)
    txt(c,hx-26,hy+10,"428 YARDS",5.0,C_INK,"Helvetica-Bold","c")
    txt(c,hx-26,hy+4,"PAR 4",5.0,C_INK,"Helvetica","c")

    # compass
    bearing=math.degrees(math.atan2(gc.x-tee0[0], gc.y-tee0[1]))
    nx2,ny2=PW-MG-14,PH-MG-18
    c.saveState(); c.translate(nx2,ny2); c.rotate(-bearing)
    c.setStrokeColor(C_INK); c.setLineWidth(0.5)
    c.line(0,-7,0,7); c.line(0,7,-2.2,3.6); c.line(0,7,2.2,3.6)
    c.restoreState()
    txt(c,nx2,ny2+10,"N",4.2,C_INK,"Helvetica-Bold","c")
    txt(c,MG,MG-6+2,"Outlines © OpenStreetMap contributors (ODbL) · terrain USGS 3DEP · imagery USDA NAIP",3.2,HexColor("#8A8A8A"))
page_hole()
c.showPage()

# ============ PAGE 3 : legend ============================================
def page_legend():
    c.setFillColor(HexColor("#FFFFFF")); c.rect(0,0,PW,PH,stroke=0,fill=1)
    c.setFillColor(C_NAVY); c.rect(0,PH-52,PW,52,stroke=0,fill=1)
    txt(c,MG,PH-26,"LEGEND",13,HexColor("#FFFFFF"),"Helvetica-Bold")
    txt(c,MG,PH-36,"BRIDLEWOOD GOLF CLUB \u00b7 FLOWER MOUND, TEXAS",5.0,HexColor("#C6D0E4"))
    txt(c,MG,PH-44,"Green-reading material conforms to Model Local Rule G-11",4.4,HexColor("#C6D0E4"))

    y=PH-76
    def head(t):
        nonlocal y
        txt(c,MG,y,t,6.2,C_NAVY,"Helvetica-Bold"); y-=4
        c.setStrokeColor(C_NAVY); c.setLineWidth(0.5); c.line(MG,y,PW-MG,y); y-=12
    def item(lbl,desc,gap=11):
        nonlocal y
        txt(c,MG+2,y,lbl,5.2,C_INK,"Helvetica-Bold")
        txt(c,MG+86,y,desc,4.6,HexColor("#444444"))
        y-=gap

    head("NUMBERS AT A REFERENCE POINT")
    # sample block
    bx,by=MG+14,y-2
    c.setFillColor(C_INK); c.circle(bx,by+6,1.1,stroke=0,fill=1)
    txt(c,bx+4,by+7,"146",8,C_RED,"Helvetica-Bold")
    txt(c,bx+22,by+9,"+1",5.6,C_INK)
    txt(c,bx+4,by-2,"(157) 225",7.2,C_INK)
    c.setStrokeColor(HexColor("#C4C4C4")); c.setLineWidth(0.3)
    rows=[(by+7.0, 9.0,"to the FRONT of the green",C_RED,"Helvetica-Bold"),
          (by+9.5,26.0,"elevation change from here to the green, in yards",HexColor("#444444"),"Helvetica"),
          (by-2.0, 8.0,"to the CENTRE of the green",HexColor("#444444"),"Helvetica"),
          (by-2.0,27.0,"from the measuring point on the black tee",HexColor("#444444"),"Helvetica")]
    ty=by+20
    for (ay,ax,lab,col,fnt) in rows:
        c.line(bx+ax,ay,bx+62,ty); c.line(bx+62,ty,bx+68,ty)
        txt(c,bx+71,ty-1.5,lab,4.5,col,fnt)
        ty-=9
    y=by-24

    head("ON THE HOLE PAGE")
    item("Red numbers","distance to the front edge of the putting surface")
    item("Black numbers","distance from the measuring point on the black tee")
    item("(Parentheses)","distance to the centre of the putting surface")
    item("Boxed number","arc marking that distance to the front of the green")
    item("(A) (B) (C)","run-out points \u2014 carry distance from the black tee")
    item("Feathered ticks","ground contouring; each tick points downhill")
    item("Dark tee box","black tees; the tee table lists every set with its offset")

    head("ON THE GREEN PAGE")
    item("5 \u00d7 5 grid","divides the putting surface into fifths both ways")
    item("Grey contours","6-inch contour interval on the putting surface")
    item("Arrows","slope of 4% or more, pointing downhill")
    item("Scale","never larger than 3/8 inch to 5 yards, the G-11 maximum")
    item("Depth scale","yards from the front edge along the line of play")

    head("HOW THIS PAGE WAS BUILT")
    src=[("Hole, green, bunker and water outlines","OpenStreetMap (ODbL)"),
         ("Terrain, elevations and green contours","USGS 3DEP 1 m lidar"),
         ("Mown envelope and tree canopy","USDA NAIP 4-band imagery"),
         ("Hole yardage and par","published Bridlewood scorecard")]
    for a_,b_ in src:
        txt(c,MG+2,y,a_,4.6,C_INK); txt(c,PW-MG-2,y,b_,4.6,HexColor("#666666"),"Helvetica","r"); y-=9
    y-=4
    c.setStrokeColor(HexColor("#DDDDDD")); c.line(MG,y,PW-MG,y); y-=10
    for L in ["No part of this page is surveyed on the ground. Distances are computed",
              "from mapped geometry; green contours are derived from airborne lidar and",
              "are not a substitute for a ground survey. Sprinkler-head references are",
              "not available, so reference points are stations along the line of play."]:
        txt(c,MG+2,y,L,4.2,HexColor("#777777")); y-=7
    y-=8
    txt(c,MG,y,"NOT IN THIS EDITION",6.2,C_NAVY,"Helvetica-Bold"); y-=4
    c.setStrokeColor(C_NAVY); c.setLineWidth(0.5); c.line(MG,y,PW-MG,y); y-=12
    gaps=[("Sprinkler-head numbers","no public source; would need a walk of the hole"),
          ("Fairway / rough mowing line","the NAIP capture is drought-dormant, no mowing contrast"),
          ("Black tee box","absent from OpenStreetMap; the tee table uses scorecard yardages"),
          ("Hole photograph","no licensed ground-level image of the hole")]
    for a_,b_ in gaps:
        txt(c,MG+2,y,a_,4.8,C_INK,"Helvetica-Bold"); y-=6.6
        txt(c,MG+8,y,b_,4.4,HexColor("#777777")); y-=10
    txt(c,MG,MG+2,"Prototype \u2014 not affiliated with Bridlewood Golf Club",3.6,HexColor("#999999"))
page_legend()
c.showPage()

c.save()
print("wrote bridlewood_01.pdf")

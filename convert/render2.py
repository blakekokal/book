# -*- coding: utf-8 -*-
"""Re-lay the source generator's holes into the No.1-Golf-style book format."""
import pickle, math
import numpy as np
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from shapely.geometry import Polygon, Point, LineString
from shapely.ops import unary_union
from shapely.affinity import translate, rotate

PT=72.0; PW,PH=4.0*PT,7.0*PT; MG=0.17*PT
YD=1.0
C_ROUGH=HexColor("#DCDCA6"); C_TURF=HexColor("#FFFFFF")
C_BUNKER=HexColor("#F2EEA8"); C_BUNKED=HexColor("#B9B45E")
C_GREEN=HexColor("#AFC96B");  C_GREENED=HexColor("#7E9642")
C_WATER=HexColor("#9FC2CE");  C_WATERED=HexColor("#5E8A99")
C_TREE=HexColor("#BFCE9A");   C_TREED=HexColor("#8CA061")
C_RED=HexColor("#C0392B");    C_INK=HexColor("#1A1A1A")
C_NAVY=HexColor("#1B2A4A");   C_GRID=HexColor("#7FA8C9")
C_COLLAR=HexColor("#EAF0E2")

M=pickle.load(open("models.pkl","rb"))
M["bridle9"]["north_deg"]=0.0          # the source rose is dead vertical

class Frame:
    def __init__(s,k,ox,oy,cx=0,cy=0): s.k,s.ox,s.oy,s.cx,s.cy=k,ox,oy,cx,cy
    def __call__(s,x,y): return (s.ox+(x-s.cx)*s.k, s.oy+(y-s.cy)*s.k)
    def poly(s,c): return [s(x,y) for x,y in c]

def ring(p): return list(p.exterior.coords)

def dpoly(c,f,p,fill=None,stroke=None,lw=0.5):
    if p is None or p.is_empty: return
    for g in ([p] if p.geom_type=="Polygon" else list(p.geoms)):
        if g.geom_type!="Polygon": continue
        pts=f.poly(ring(g))
        if len(pts)<3: continue
        pa=c.beginPath(); pa.moveTo(*pts[0])
        for q in pts[1:]: pa.lineTo(*q)
        pa.close()
        if fill is not None: c.setFillColor(fill)
        if stroke is not None: c.setStrokeColor(stroke); c.setLineWidth(lw)
        c.setDash()
        c.drawPath(pa,stroke=1 if stroke else 0,fill=1 if fill is not None else 0)

def txt(c,x,y,s,size=5.0,col=C_INK,font="Helvetica",anchor="l"):
    c.saveState(); c.setFillColor(col); c.setFont(font,size); c.translate(x,y)
    if anchor=="c": c.drawCentredString(0,0,s)
    elif anchor=="r": c.drawRightString(0,0,s)
    else: c.drawString(0,0,s)
    c.restoreState()

def rose(c,x,y,north_deg,r=7.0,lab="N"):
    c.saveState(); c.translate(x,y); c.rotate(-north_deg)
    c.setStrokeColor(C_INK); c.setLineWidth(0.5)
    c.line(0,-r,0,r); c.line(0,r,-r*0.3,r*0.55); c.line(0,r,r*0.3,r*0.55)
    c.setFont("Helvetica-Bold",4.0); c.setFillColor(C_INK)
    c.drawCentredString(0,r+2.4,lab)
    c.restoreState()

def numblock(c,f,x,y,red,paren,black,elev,side="r",size=4.7):
    px,py=f(x,y)
    c.setFillColor(C_INK); c.circle(px,py,0.9,stroke=0,fill=1)
    dx=3.2 if side=="r" else -3.2; anc="l" if side=="r" else "r"
    s1=f"{red:.0f}"
    txt(c,px+dx,py+1.1,s1,size,C_RED,"Helvetica-Bold",anc)
    w=c.stringWidth(s1,"Helvetica-Bold",size)
    if elev is not None and elev!=0:
        txt(c,px+dx+(w+1.1 if side=="r" else -w-1.1),py+2.4,f"{elev:+.0f}",size*0.70,C_INK,"Helvetica",anc)
    txt(c,px+dx,py-4.1,f"({paren:.0f}) {black:.0f}",size*0.90,C_INK,"Helvetica",anc)

c=canvas.Canvas("converted_holes.pdf",pagesize=(PW,PH))
c.setTitle("Converted yardage book pages")

# =====================================================================
def green_page(nm):
    m=M[nm]; me=m["meta"]
    c.setFillColor(HexColor("#FFFFFF")); c.rect(0,0,PW,PH,stroke=0,fill=1)
    c.setFillColor(C_NAVY); c.circle(MG+11,PH-MG-11,11,stroke=0,fill=1)
    txt(c,MG+11,PH-MG-14.6,str(me["hole"]),15,HexColor("#FFFFFF"),"Helvetica-Bold","c")
    txt(c,MG+28,PH-MG-10,me["club"],6.3,C_NAVY,"Helvetica-Bold")
    txt(c,MG+28,PH-MG-18.5,
        f"{me['city']}  ·  PAR {me['par']}  ·  {me['yards']} YARDS ({me['tee']})",4.7)
    c.setStrokeColor(C_NAVY); c.setLineWidth(0.7); c.line(MG,PH-MG-30,PW-MG,PH-MG-30)

    note_top=PH-MG-36; note_bot=PH*0.515
    txt(c,MG,note_top-6,"NOTES",5.0,HexColor("#9A9A9A"),"Helvetica-Bold")
    c.setStrokeColor(HexColor("#E3E3E3")); c.setLineWidth(0.35)
    yy=note_top-16
    while yy>note_bot+6: c.line(MG,yy,PW-MG,yy); yy-=11
    c.setStrokeColor(HexColor("#CFCFCF")); c.setLineWidth(0.5); c.line(MG,note_bot,PW-MG,note_bot)

    surf=m["surface"]; depth=me["depth"]
    parts=[surf]+m["collar"]+m["gsand"]+m["gwater"]
    env=unary_union([p for p in parts if p is not None and not p.is_empty])
    ex=env.bounds; sx=surf.bounds
    SC_CAP=(0.375*PT)/5.0                       # points per yard, the G-11 cap
    GUT=24.0
    area_h=note_bot-(MG+30); avail_w=PW-MG*2-GUT-6
    SC=min(SC_CAP, avail_w/max(ex[2]-ex[0],1), (area_h-22)/max(ex[3]-ex[1],1))
    cx0=MG+GUT+avail_w/2-((ex[0]+ex[2])/2)*SC
    cy0=MG+30+area_h/2-((ex[1]+ex[3])/2)*SC
    f=Frame(SC,cx0,cy0,0,0)

    for p in m["collar"]:  dpoly(c,f,p,C_COLLAR,None)
    for p in m["gwater"]:  dpoly(c,f,p,C_WATER,C_WATERED,0.45)
    for p in m["gsand"]:   dpoly(c,f,p,C_BUNKER,C_BUNKED,0.45)
    dpoly(c,f,surf,HexColor("#FAFBF6"),C_INK,1.15)

    # 5 x 5 grid
    c.saveState()
    pa=c.beginPath(); gp=f.poly(ring(surf)); pa.moveTo(*gp[0])
    for q in gp[1:]: pa.lineTo(*q)
    pa.close(); c.clipPath(pa,stroke=0,fill=0)
    c.setStrokeColor(C_GRID); c.setLineWidth(0.32)
    for i in range(1,5):
        t=sx[0]+(sx[2]-sx[0])*i/5; a=f(t,sx[1]-3); b=f(t,sx[3]+3); c.line(a[0],a[1],b[0],b[1])
        t=sx[1]+(sx[3]-sx[1])*i/5; a=f(sx[0]-3,t); b=f(sx[2]+3,t); c.line(a[0],a[1],b[0],b[1])
    c.restoreState()

    # depth ruler on the left, ticks every 5 yd from the front edge
    sxl=cx0+sx[0]*SC-9.0
    c.setStrokeColor(HexColor("#8FA9C4")); c.setLineWidth(0.45); ys=[]
    for d5 in range(0,int(depth)+6,5):
        py=f(0,d5)[1]; ys.append(py)
        c.line(sxl-5.5,py,sxl,py)
        txt(c,sxl-7.5,py-1.5,str(d5),4.2,HexColor("#5E7FA3"),"Helvetica","r")
    c.setLineWidth(0.3); c.line(sxl-2.7,min(ys),sxl-2.7,max(ys))
    txt(c,sxl-7.5,max(ys)+7,"YDS",3.6,HexColor("#5E7FA3"),"Helvetica-Bold","r")

    # front marker
    fp=f(0,0)
    c.setFillColor(HexColor("#FFFFFF")); c.setStrokeColor(C_INK); c.setLineWidth(0.7)
    c.circle(fp[0],fp[1],2.1,stroke=1,fill=1)
    txt(c,fp[0],fp[1]-8.6,"GREEN FRONT",3.8,C_INK,"Helvetica-Bold","c")

    # perimeter depth marks carried across from the source page
    cen=surf.centroid
    for lab,adeg in me["marks"]:
        th=math.radians(adeg)
        # ray from the centre outward; label just outside the edge
        L=60
        seg=LineString([(cen.x,cen.y),(cen.x+L*math.sin(th), cen.y+L*math.cos(th))])
        hit=seg.intersection(surf.boundary)
        pts=[hit] if hit.geom_type=="Point" else [g for g in getattr(hit,"geoms",[]) if g.geom_type=="Point"]
        if not pts: continue
        q=max(pts,key=lambda p:Point(cen.x,cen.y).distance(p))
        ox,oy=f(q.x+2.2*math.sin(th), q.y+2.2*math.cos(th))
        txt(c,ox,oy-1.5,str(lab),5.0,C_INK,"Helvetica-Bold","c")

    txt(c,PW-MG-2,note_bot-14,f"{depth:.0f}",13,C_RED,"Helvetica-Bold","r")
    txt(c,PW-MG-2,note_bot-21,"YARDS DEEP",4.2,C_RED,"Helvetica-Bold","r")
    txt(c,PW-MG-2,note_bot-28,f"{me['width']} YARDS WIDE",4.2,HexColor("#777777"),"Helvetica","r")
    sc_in=SC*5/PT
    lab=("3/8 INCH" if abs(sc_in-0.375)<0.002 else f"{sc_in:.3f} INCH")
    txt(c,MG,MG+16,f"PUTTING GREEN SCALED AT {lab} TO 5 YARDS (G-11 MAXIMUM 3/8)",3.9,HexColor("#6E6E6E"),"Helvetica-Bold")
    txt(c,MG,MG+10.5,"NO SURFACE CONTOUR OR SLOPE DATA IN THE SOURCE PAGE",3.9,C_RED,"Helvetica-Bold")
    txt(c,MG,MG+4,"Green outline, collar, sand and depth marks converted from the source generator",3.4,HexColor("#9A9A9A"))
    rose(c,PW-MG-13,MG+34,m["north_deg"])

# =====================================================================
def hole_page(nm):
    m=M[nm]; me=m["meta"]
    depth=me["depth"]; to_green=me["to_green"]
    front_chain=to_green-depth/2.0
    c.setFillColor(C_ROUGH); c.rect(0,0,PW,PH,stroke=0,fill=1)

    body=[]
    if "corridor" in m: body+= m["corridor"]
    if "fairway"  in m: body+= m["fairway"]
    gsurf=translate(m["surface"],0,front_chain)
    allp=[p for p in body+[gsurf] if p is not None and not p.is_empty]
    env=unary_union(allp).bounds
    lo_y=min(env[1],-14); hi_y=max(env[3],front_chain+depth+24)
    avail_h=PH-MG*2-46; avail_w=PW-MG*2
    SC=min(avail_h/(hi_y-lo_y), avail_w/max(env[2]-env[0]+26,120))
    f=Frame(SC,PW/2-((env[0]+env[2])/2)*SC, MG+34+avail_h/2-((lo_y+hi_y)/2)*SC,0,0)

    for p in body: dpoly(c,f,p,C_TURF,None)
    for p in body: dpoly(c,f,p,None,C_INK,0.75)
    for p in m.get("trees",[]): dpoly(c,f,p,HexColor("#B4C68C"),HexColor("#7F9354"),0.35)
    for p in m.get("water",[]): dpoly(c,f,p,C_WATER,C_WATERED,0.5)
    for p in m.get("sand",[]):  dpoly(c,f,p,C_BUNKER,C_BUNKED,0.5)
    dpoly(c,f,gsurf,C_GREEN,C_GREENED,0.8)

    # centre line
    c.setStrokeColor(HexColor("#B4B4B4")); c.setLineWidth(0.35); c.setDash(1.2,1.6)
    a=f(0,0); b=f(0,front_chain); c.line(a[0],a[1],b[0],b[1]); c.setDash()

    # distance arcs to the front of the green, boxed on the left
    for arc in me["arcs"]:
        ch=front_chain-arc
        if ch<10: continue
        seg=[(t,ch) for t in np.linspace(env[0]-4,-8,10)]
        pts=f.poly(seg)
        c.setStrokeColor(HexColor("#9AA5B1")); c.setLineWidth(0.3); c.setDash(1.0,1.4)
        pa=c.beginPath(); pa.moveTo(*pts[0])
        for q in pts[1:]: pa.lineTo(*q)
        c.drawPath(pa,stroke=1,fill=0); c.setDash()
        p0=pts[0]
        c.setFillColor(HexColor("#FFFFFF")); c.setStrokeColor(C_INK); c.setLineWidth(0.35)
        c.rect(p0[0]-12.8,p0[1]-2.7,11.6,5.4,stroke=1,fill=1)
        txt(c,p0[0]-7.0,p0[1]-1.1,str(arc),4.3,C_INK,"Helvetica-Bold","c")

    # reference points carried over from the source elevation stations.
    # put each block on whichever side of the centre line has more room.
    corr=unary_union([p for p in body if p is not None and not p.is_empty])
    def room(ch):
        cut=corr.intersection(LineString([(env[0]-30,ch),(env[2]+30,ch)]))
        if cut.is_empty: return 0.0,0.0
        segs=[cut] if cut.geom_type=="LineString" else list(getattr(cut,"geoms",[]))
        xs=[x for g in segs for x,_ in g.coords]
        if not xs: return 0.0,0.0
        return abs(min(xs)), abs(max(xs))
    for ch,el in me["elevs"]:
        lft,rgt=room(ch)
        numblock(c,f,0,ch,front_chain-ch,to_green-ch,ch,el,
                 side=("r" if rgt>=lft else "l"))

    # carry callouts from the source page
    for i,d in enumerate(me["calls"]):
        px,py=f(0,d)
        c.setStrokeColor(HexColor("#8A8A8A")); c.setLineWidth(0.3); c.setDash(1.1,1.5)
        c.line(px,py,px-26,py); c.setDash()
        c.setFillColor(HexColor("#FFFFFF")); c.setStrokeColor(C_INK); c.setLineWidth(0.4)
        c.circle(px-30,py,2.4,stroke=1,fill=1)
        txt(c,px-30,py-1.5,"ABCDE"[i],4.0,C_INK,"Helvetica-Bold","c")
        txt(c,px-35,py-1.5,f"{d}",4.3,C_INK,"Helvetica-Bold","r")

    # tee
    tp=f(0,0)
    c.setFillColor(HexColor("#3A3A3A")); c.setStrokeColor(C_INK); c.setLineWidth(0.5)
    c.circle(tp[0],tp[1],2.6,stroke=1,fill=1)
    txt(c,tp[0]+5,tp[1]-1.5,f"{me['tee']} TEE",4.0,C_INK,"Helvetica-Bold")

    # blocks
    bx,by=MG+1,MG+15
    c.setFillColor(HexColor("#FFFFFF")); c.setStrokeColor(C_INK); c.setLineWidth(0.5)
    c.rect(bx,by,74,26,stroke=1,fill=1)
    txt(c,bx+3,by+19,"TEE",4.4,C_INK,"Helvetica-Bold")
    txt(c,bx+71,by+19,f"{me['tee']}",4.4,C_INK,"Helvetica-Bold","r")
    txt(c,bx+3,by+12,f"{me['to_green']} YD TO GREEN",4.2)
    txt(c,bx+3,by+5.5,f"PLAYS {me['plays']:+d} YD",4.2,C_RED,"Helvetica-Bold")
    hx=PW-MG-2
    txt(c,hx-26,by+22,str(me["hole"]),21,C_NAVY,"Helvetica-Bold","c")
    c.setStrokeColor(C_NAVY); c.setLineWidth(0.6); c.line(hx-44,by+19,hx-8,by+19)
    txt(c,hx-26,by+12,f"{me['yards']} YARDS",5.0,C_INK,"Helvetica-Bold","c")
    txt(c,hx-26,by+6,f"PAR {me['par']}  ·  HCP {me['hcp']}",4.6,C_INK,"Helvetica","c")
    rose(c,PW-MG-14,PH-MG-18,m["north_deg"])
    c.setFillColor(HexColor("#FFFFFF")); c.rect(0,0,PW,MG+9,stroke=0,fill=1)
    txt(c,MG,MG-1,f"{me['club']} · HOLE {me['hole']} · converted from the source generator page",3.2,HexColor("#8A8A8A"))

for nm in ("cowboys","bridle9"):
    green_page(nm); c.showPage()
    hole_page(nm);  c.showPage()

# =====================================================================
def legend():
    c.setFillColor(HexColor("#FFFFFF")); c.rect(0,0,PW,PH,stroke=0,fill=1)
    c.setFillColor(C_NAVY); c.rect(0,PH-52,PW,52,stroke=0,fill=1)
    txt(c,MG,PH-26,"CONVERSION NOTES",11,HexColor("#FFFFFF"),"Helvetica-Bold")
    txt(c,MG,PH-38,"Source pages re-laid into the No.1 Golf book format",4.8,HexColor("#C6D0E4"))
    y=PH-74
    def head(t):
        nonlocal y
        txt(c,MG,y,t,6.2,C_NAVY,"Helvetica-Bold"); y-=4
        c.setStrokeColor(C_NAVY); c.setLineWidth(0.5); c.line(MG,y,PW-MG,y); y-=12
    def item(a,b,gap=10.5):
        nonlocal y
        txt(c,MG+2,y,a,5.0,C_INK,"Helvetica-Bold"); txt(c,MG+96,y,b,4.5,HexColor("#444444")); y-=gap
    head("NUMBERS AT A REFERENCE POINT")
    item("Red","to the front of the green")
    item("Superscript","elevation change from there to the green, in yards")
    item("(Parentheses)","to the green, as the source page measures it")
    item("Black","from the tee")
    head("WHAT CARRIED OVER FROM THE SOURCE")
    item("Green outline","traced from the source green panel")
    item("Depth and width","stated on the source page; used to set the scale")
    item("Perimeter marks","the source page's depth figures around the green")
    item("Elevation profile","the source page's per-station values, verbatim")
    item("Hole shape","vector colour fills, or the satellite corridor mask")
    item("Tee, par, HCP, yardage","as printed on the source page")
    head("WHAT THE SOURCE DOES NOT CARRY")
    for a,b in [("Green contours and slope arrows",
                 "the source green panel has no surface data at all, so the"),
                ("", "centre of this format's green page cannot be filled from it"),
                ("Sprinkler references","no numbered references on the source page"),
                ("Ground contouring","no terrain shading on the source hole page"),
                ("Tee ladder","only one tee set is shown per source page")]:
        if a: txt(c,MG+2,y,a,5.0,C_RED if "contour" in a.lower() else C_INK,"Helvetica-Bold"); y-=6.4
        txt(c,MG+8,y,b,4.4,HexColor("#777777")); y-=9.5
    y-=4
    head("SCALE CHECK")
    for a,b in [("Cowboys 9 green","traced 15 x 35 yd against 16 x 35 stated"),
                ("Bridlewood 9 green","traced 26 x 33 yd against 26 x 33 stated"),
                ("Cowboys 9 hole page","1.31 px per yard on the source screenshot"),
                ("Bridlewood 9 hole page","1.43 px per yard on the source screenshot")]:
        txt(c,MG+2,y,a,4.7,C_INK,"Helvetica-Bold"); txt(c,MG+96,y,b,4.4,HexColor("#666666")); y-=9
    y-=6
    for L in ["Converted from screenshots, so outlines carry the resolution of the",
              "screen grab. A vector PDF would give clean geometry and exact",
              "label positions instead of traced approximations."]:
        txt(c,MG+2,y,L,4.3,HexColor("#777777")); y-=7
legend(); c.showPage()
c.save()
print("wrote converted_holes.pdf")

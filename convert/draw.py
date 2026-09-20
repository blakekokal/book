# -*- coding: utf-8 -*-
"""Draw the converted Cowboys book."""
import pickle, math
import numpy as np
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from shapely.geometry import Polygon, Point, LineString
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
H=pickle.load(open("book_models.pkl","rb"))
TOTAL=sum(h["yards"] for h in H.values() if h["yards"])
PARSUM=sum(h["par"] for h in H.values())

class F:
    def __init__(s,k,ox,oy): s.k,s.ox,s.oy=k,ox,oy
    def __call__(s,x,y): return (s.ox+x*s.k, s.oy+y*s.k)
    def poly(s,c): return [s(x,y) for x,y in c]

def ring(p): return list(p.exterior.coords)

def dp(c,f,p,fill=None,stroke=None,lw=0.5):
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

def T(c,x,y,s,size=5.0,col=C_INK,font="Helvetica",anc="l"):
    c.saveState(); c.setFillColor(col); c.setFont(font,size); c.translate(x,y)
    if anc=="c": c.drawCentredString(0,0,s)
    elif anc=="r": c.drawRightString(0,0,s)
    else: c.drawString(0,0,s)
    c.restoreState()

def rose(c,x,y,north,r=6.5):
    if north is None: return
    c.saveState(); c.translate(x,y); c.rotate(-north)
    c.setStrokeColor(C_INK); c.setLineWidth(0.5)
    c.line(0,-r,0,r); c.line(0,r,-r*0.3,r*0.55); c.line(0,r,r*0.3,r*0.55)
    c.setFont("Helvetica-Bold",3.9); c.setFillColor(C_INK)
    c.drawCentredString(0,r+2.3,"N"); c.restoreState()

def numblock(c,f,x,y,red,paren,black,elev,side="r",size=4.6):
    px,py=f(x,y)
    c.setFillColor(C_INK); c.circle(px,py,0.85,stroke=0,fill=1)
    dx=3.0 if side=="r" else -3.0; anc="l" if side=="r" else "r"
    s1=f"{red:.0f}"
    T(c,px+dx,py+1.0,s1,size,C_RED,"Helvetica-Bold",anc)
    w=c.stringWidth(s1,"Helvetica-Bold",size)
    if elev: T(c,px+dx+(w+1.0 if side=="r" else -w-1.0),py+2.3,f"{elev:+d}",size*0.70,C_INK,"Helvetica",anc)
    T(c,px+dx,py-4.0,f"({paren:.0f}) {black:.0f}",size*0.88,C_INK,"Helvetica",anc)

def header(c,n,h,sub):
    c.setFillColor(C_WHITE); c.rect(0,0,PW,PH,stroke=0,fill=1)
    c.setFillColor(C_NAVY); c.circle(MG+10.5,PH-MG-10.5,10.5,stroke=0,fill=1)
    T(c,MG+10.5,PH-MG-13.8,str(n),14,C_WHITE,"Helvetica-Bold","c")
    T(c,MG+26,PH-MG-9.5,CLUB,6.0,C_NAVY,"Helvetica-Bold")
    T(c,MG+26,PH-MG-17.5,sub,4.6)
    c.setStrokeColor(C_NAVY); c.setLineWidth(0.7); c.line(MG,PH-MG-28,PW-MG,PH-MG-28)

def footer(c,n,txt):
    c.setFillColor(C_WHITE); c.rect(0,0,PW,MG+8,stroke=0,fill=1)
    T(c,MG,MG-1,CLUB,3.3,HexColor("#9A9A9A"))
    T(c,PW-MG,MG-1,txt,3.3,HexColor("#9A9A9A"),"Helvetica","r")

# ================= green page ==========================================
def green_page(c,n):
    h=H[n]
    header(c,n,h,f"{CITY}  ·  PAR {h['par']}  ·  HCP {h['hcp']}  ·  {h['yards']} YDS")
    nb=PH*0.505
    T(c,MG,PH-MG-34,"NOTES",4.8,HexColor("#9A9A9A"),"Helvetica-Bold")
    c.setStrokeColor(HexColor("#E3E3E3")); c.setLineWidth(0.35)
    y=PH-MG-44
    while y>nb+6: c.line(MG,y,PW-MG,y); y-=10.5
    c.setStrokeColor(HexColor("#CFCFCF")); c.setLineWidth(0.5); c.line(MG,nb,PW-MG,nb)

    surf=h["g_surface"]
    if surf is None: return
    near=surf.buffer(11.0)
    parts=[surf]
    for p in h["g_collar"]+h["g_sand"]+h["g_water"]+h["g_putt"]:
        if p is None or p.is_empty: continue
        q=p.intersection(near)
        if not q.is_empty and q.area>0.5: parts.append(q)
    env=unary_union(parts).bounds
    sx=surf.bounds
    CAP=(0.375*PT)/5.0; GUT=23.0
    ah=(nb-15)-(MG+28); aw=PW-MG*2-GUT-5
    SC=min(CAP, aw/max(env[2]-env[0],1), (ah-26)/max(env[3]-env[1],1))
    f=F(SC, MG+GUT+aw/2-((env[0]+env[2])/2)*SC, MG+28+ah/2-((env[1]+env[3])/2)*SC)
    c.saveState()
    pa0=c.beginPath(); pa0.rect(MG-1,MG+24,PW-2*MG+2,(nb-16)-MG-24); c.clipPath(pa0,stroke=0,fill=0)
    for p in h["g_fairway"]: dp(c,f,p,HexColor("#F3F6EE"),None)
    for p in h["g_collar"]:  dp(c,f,p,C_COLLAR,None)
    for p in h["g_water"]:   dp(c,f,p,C_WATER,C_WATERED,0.45)
    for p in h["g_sand"]:    dp(c,f,p,C_BUNKER,C_BUNKED,0.45)
    for p in h["g_trees"]:   dp(c,f,p,C_TREE,C_TREED,0.3)
    dp(c,f,surf,HexColor("#FAFBF6"),C_INK,1.1)
    c.restoreState()
    # 5 x 5 grid
    c.saveState()
    pa=c.beginPath(); gp=f.poly(ring(surf)); pa.moveTo(*gp[0])
    for q in gp[1:]: pa.lineTo(*q)
    pa.close(); c.clipPath(pa,stroke=0,fill=0)
    c.setStrokeColor(C_GRID); c.setLineWidth(0.3)
    for i in range(1,5):
        t=sx[0]+(sx[2]-sx[0])*i/5; a=f(t,sx[1]-3); b=f(t,sx[3]+3); c.line(a[0],a[1],b[0],b[1])
        t=sx[1]+(sx[3]-sx[1])*i/5; a=f(sx[0]-3,t); b=f(sx[2]+3,t); c.line(a[0],a[1],b[0],b[1])
    c.restoreState()
    # depth ruler
    sxl=f(sx[0],0)[0]-8.5
    c.setStrokeColor(HexColor("#8FA9C4")); c.setLineWidth(0.42); ys=[]
    for d5 in range(0,int(h["depth"])+6,5):
        py=f(0,d5)[1]; ys.append(py)
        c.line(sxl-5.2,py,sxl,py)
        T(c,sxl-7.2,py-1.4,str(d5),4.0,HexColor("#5E7FA3"),"Helvetica","r")
    if ys:
        c.setLineWidth(0.3); c.line(sxl-2.6,min(ys),sxl-2.6,max(ys))
        T(c,sxl-7.2,max(ys)+6.5,"YDS",3.5,HexColor("#5E7FA3"),"Helvetica-Bold","r")
    fp=f(0,0)
    c.setFillColor(C_WHITE); c.setStrokeColor(C_INK); c.setLineWidth(0.65)
    c.circle(fp[0],fp[1],2.0,stroke=1,fill=1)
    T(c,fp[0],fp[1]-8.2,"GREEN FRONT",3.6,C_INK,"Helvetica-Bold","c")
    # edge numbers carried over from the source page
    for e in h["g_edge"]:
        p=f(*e["pt"]); T(c,p[0],p[1]-1.4,str(e["v"]),4.6,C_INK,"Helvetica-Bold","c")
    T(c,MG,nb-10.5,"GREEN",5.2,C_NAVY,"Helvetica-Bold")
    T(c,PW-MG,nb-10.5,f"DEPTH {h['depth']} YDS   \u00b7   WIDTH {h['width']} YDS",5.2,C_INK,"Helvetica-Bold","r")
    c.setStrokeColor(HexColor("#DCDCDC")); c.setLineWidth(0.4); c.line(MG,nb-14.5,PW-MG,nb-14.5)
    sc=SC*5/PT
    lab="3/8 IN" if abs(sc-0.375)<0.002 else f"{sc:.3f} IN"
    T(c,MG,MG+14,f"GREEN SCALED AT {lab} TO 5 YARDS (G-11 MAXIMUM 3/8)",3.7,HexColor("#6E6E6E"),"Helvetica-Bold")
    T(c,MG,MG+8.6,"EDGE NUMBERS ARE YARDS FROM THE FRONT  ·  5 × 5 GRID",3.7,HexColor("#6E6E6E"))
    T(c,MG,MG+3.2,"NO SURFACE CONTOUR OR SLOPE DATA IN THE SOURCE BOOK",3.7,C_RED,"Helvetica-Bold")
    rose(c,PW-MG-11,MG+30,h["north"])
    footer(c,n,f"HOLE {n} · GREEN")

# ================= hole page ===========================================
def hole_page(c,n,part=None):
    h=H[n]
    lbl={None:"",0:"  ·  OFF THE TEE",1:"  ·  APPROACH"}[part]
    header(c,n,h,f"PAR {h['par']}  ·  HCP {h['hcp']}  ·  {h['yards']} YDS BLACK{lbl}")
    c.setFillColor(C_ROUGH); c.rect(0,MG+8,PW,PH-MG-36-8,stroke=0,fill=1)
    green=h["green"]; gc=Point(*h["gc"]); fp=Point(*h["front"])
    fchain=fp.y
    body=h["fairway"]+([green] if green is not None else [])+([h["teebox"]] if h["teebox"] is not None else [])
    allg=[p for p in body if p is not None and not p.is_empty]
    # the extent follows the played corridor; a distant lake must not shrink it
    spine=LineString([(0,-12),(gc.x,gc.y+h["depth"]*0.7+12)])
    corridor=spine.buffer(max(58.0, h["width"]*1.05, h["depth"]*1.05))
    clipped=[p.intersection(corridor) for p in allg]
    clipped=[q for q in clipped if not q.is_empty and q.area>0.4]
    env=unary_union(clipped).bounds if clipped else (-40,-12,40,gc.y)
    top=max(env[3],gc.y+h["depth"]*0.6+10); bot=min(env[1],-10)
    reach=max(h["to_green"],gc.y)
    if part==0:   lo,hi=bot, bot+reach*0.62
    elif part==1: lo,hi=bot+reach*0.40, top
    else:         lo,hi=bot,top
    ah=PH-MG*2-40; aw=PW-MG*2
    SC=min(ah/max(hi-lo,1), aw/max(env[2]-env[0]+12,70))
    f=F(SC, PW/2-((env[0]+env[2])/2)*SC, MG+30+ah/2-((lo+hi)/2)*SC)
    c.saveState()
    pa=c.beginPath(); pa.rect(0,MG+8,PW,PH-MG-36-8); c.clipPath(pa,stroke=0,fill=0)
    for p in h["fairway"]: dp(c,f,p,C_TURF,None)
    for p in h["fairway"]: dp(c,f,p,None,C_INK,0.6)
    for p in h["trees"]:   dp(c,f,p,C_TREE,C_TREED,0.3)
    for p in h["water"]:   dp(c,f,p,C_WATER,C_WATERED,0.45)
    for p in h["sand"]:    dp(c,f,p,C_BUNKER,C_BUNKED,0.45)
    for p in h["putt"]:    dp(c,f,p,HexColor("#DCE8C6"),C_GREENED,0.4)
    if h["teebox"] is not None: dp(c,f,h["teebox"],HexColor("#3A3A3A"),C_INK,0.5)
    if green is not None:       dp(c,f,green,C_GREEN,C_GREENED,0.75)
    # range arcs to the front of the green, boxed on the left
    for a in h["arcs"]:
        rr=a
        th0,th1=math.radians(196),math.radians(262)
        pts=[(fp.x+rr*math.sin(t), fp.y+rr*math.cos(t)) for t in np.linspace(th0,th1,26)]
        pts=[p for p in pts if lo-8<=p[1]<=hi+8]
        if len(pts)<4: continue
        q=f.poly(pts)
        c.setStrokeColor(HexColor("#9AA5B1")); c.setLineWidth(0.3); c.setDash(1.0,1.4)
        pa2=c.beginPath(); pa2.moveTo(*q[0])
        for z in q[1:]: pa2.lineTo(*z)
        c.drawPath(pa2,stroke=1,fill=0); c.setDash()
        e=q[-1]
        c.setFillColor(C_WHITE); c.setStrokeColor(C_INK); c.setLineWidth(0.33)
        c.rect(e[0]-5.6,e[1]-2.5,11.2,5.0,stroke=1,fill=1)
        T(c,e[0],e[1]-1.0,str(a),4.1,C_INK,"Helvetica-Bold","c")
    # reference stations
    corr=unary_union([p for p in h["fairway"] if not p.is_empty]) if h["fairway"] else None
    for s in h["stations"]:
        if not (lo-4<=s["y"]<=hi+4): continue
        side="r"
        if corr is not None:
            cut=corr.intersection(LineString([(env[0]-40,s["y"]),(env[2]+40,s["y"])]))
            xs=[x for g in ([cut] if cut.geom_type=="LineString" else list(getattr(cut,"geoms",[]))) for x,_ in g.coords]
            if xs and abs(min(xs)-s["x"])>abs(max(xs)-s["x"]): side="l"
        numblock(c,f,s["x"],s["y"],s["to_front"],s["to_centre"],s["from_tee"],s["elev"],side=side)
    # carries
    for i,cl in enumerate(h["calls"]):
        if not (lo-4<=cl["y"]<=hi+4): continue
        p=f(cl["x"],cl["y"])
        c.setFillColor(C_WHITE); c.setStrokeColor(C_INK); c.setLineWidth(0.4)
        c.circle(p[0],p[1],2.2,stroke=1,fill=1)
        T(c,p[0],p[1]-1.4,"ABCDEFGH"[i],3.8,C_INK,"Helvetica-Bold","c")
        T(c,p[0]+4.2,p[1]-1.4,f"{cl['v']}",4.3,C_INK,"Helvetica-Bold")
    c.restoreState()
    # blocks
    bx,by=MG,MG+11
    c.setFillColor(C_WHITE); c.setStrokeColor(C_INK); c.setLineWidth(0.45)
    c.rect(bx,by,72,24,stroke=1,fill=1)
    T(c,bx+3,by+17,"BLACK TEE",4.2,C_INK,"Helvetica-Bold")
    T(c,bx+3,by+10.5,f"{h['to_green']} YD TO GREEN",4.0)
    pl="EVEN" if h["plays"]==0 else f"{h['plays']:+d} YD"
    T(c,bx+3,by+4.5,f"PLAYS {pl}",4.0,C_RED,"Helvetica-Bold")
    hx=PW-MG
    T(c,hx-24,by+19,str(n),19,C_NAVY,"Helvetica-Bold","c")
    c.setStrokeColor(C_NAVY); c.setLineWidth(0.55); c.line(hx-41,by+16.5,hx-7,by+16.5)
    T(c,hx-24,by+10,f"{h['yards']} YARDS",4.7,C_INK,"Helvetica-Bold","c")
    T(c,hx-24,by+4.5,f"PAR {h['par']}  ·  HCP {h['hcp']}",4.3,C_INK,"Helvetica","c")
    rose(c,PW-MG-11,PH-MG-46,h["north"])
    footer(c,n,f"HOLE {n} OF 18" + ("  ·  1 OF 2" if part==0 else "  ·  2 OF 2" if part==1 else ""))

# ================= front matter ========================================
def cover(c):
    c.setFillColor(C_NAVY); c.rect(0,0,PW,PH,stroke=0,fill=1)
    T(c,PW/2,PH*0.62,"Y A R D A G E   B O O K",6.5,HexColor("#9FB0CE"),"Helvetica","c")
    T(c,PW/2,PH*0.555,CLUB,13,C_WHITE,"Helvetica-Bold","c")
    T(c,PW/2,PH*0.515,CITY,6.0,HexColor("#9FB0CE"),"Helvetica","c")
    c.setStrokeColor(HexColor("#41527A")); c.setLineWidth(0.6)
    c.line(PW*0.24,PH*0.487,PW*0.76,PH*0.487)
    T(c,PW/2,PH*0.452,f"BLACK TEES  ·  {TOTAL:,} YARDS  ·  PAR {PARSUM}",5.6,C_WHITE,"Helvetica-Bold","c")
    T(c,PW/2,PH*0.25,"Converted to the No.1 Golf book format",4.6,HexColor("#7F90AE"),"Helvetica","c")
    T(c,PW/2,PH*0.215,"from a Shot Pattern source book",4.6,HexColor("#7F90AE"),"Helvetica","c")

def legend(c):
    c.setFillColor(C_WHITE); c.rect(0,0,PW,PH,stroke=0,fill=1)
    c.setFillColor(C_NAVY); c.rect(0,PH-46,PW,46,stroke=0,fill=1)
    T(c,MG,PH-24,"LEGEND",11,C_WHITE,"Helvetica-Bold")
    T(c,MG,PH-34,"Conforming to Model Local Rule G-11",4.5,HexColor("#C6D0E4"))
    y=PH-66
    def head(t):
        nonlocal y
        T(c,MG,y,t,5.9,C_NAVY,"Helvetica-Bold"); y-=3.5
        c.setStrokeColor(C_NAVY); c.setLineWidth(0.45); c.line(MG,y,PW-MG,y); y-=11
    def item(a,b,g=9.6):
        nonlocal y
        T(c,MG+1,y,a,4.8,C_INK,"Helvetica-Bold"); T(c,MG+84,y,b,4.3,HexColor("#444444")); y-=g
    head("NUMBERS AT A REFERENCE POINT")
    bx,by=MG+12,y-2
    c.setFillColor(C_INK); c.circle(bx,by+5,1.0,stroke=0,fill=1)
    T(c,bx+3.6,by+6,"146",7.6,C_RED,"Helvetica-Bold")
    T(c,bx+20,by+8,"+3",5.2,C_INK)
    T(c,bx+3.6,by-2,"(163) 225",6.8,C_INK)
    rows=[(by+16.5,"to the FRONT of the green",C_RED),
          (by+7.5,"elevation change from here to the green",HexColor("#444444")),
          (by-1.5,"(to the CENTRE of the green)",HexColor("#444444")),
          (by-10.5,"from the black tee",HexColor("#444444"))]
    c.setStrokeColor(HexColor("#C8C8C8")); c.setLineWidth(0.28)
    for yy,lab,col in rows:
        c.line(bx+40,yy,bx+46,yy); T(c,bx+49,yy-1.4,lab,4.3,col,"Helvetica-Bold" if col==C_RED else "Helvetica")
    y=by-22
    head("ON THE HOLE PAGE")
    item("Boxed number","arc at that distance to the front of the green")
    item("(A) (B) (C)","carry distance from the black tee")
    item("Dark tee box","the black tee")
    item("Green fill","putting surface; pale green is short grass")
    head("ON THE GREEN PAGE")
    item("5 × 5 grid","the surface split into fifths both ways")
    item("Edge numbers","yards from the front edge, from the source book")
    item("Depth ruler","yards from the front along the line of play")
    item("Scale","never larger than 3/8 inch to 5 yards")
    head("HOW THIS WAS BUILT")
    for a,b in [("Source","Shot Pattern book, vector PDF, 39 pages"),
                ("Scale","circle-fit on the source range arcs"),
                ("Front and centre","computed from the source green outline"),
                ("Elevations","the source book's own per-station values"),
                ("Carries","the source book's own printed numbers")]:
        T(c,MG+1,y,a,4.5,C_INK,"Helvetica-Bold"); T(c,MG+62,y,b,4.2,HexColor("#666666")); y-=8.4
    y-=3
    head("ACCURACY CHECK")
    for L in ["Every carry number printed in the source book was re-derived from",
              "the extracted geometry. Across 38 numbers the median difference",
              "is 0.4 yards and the largest is 2.0 yards.",
              "",
              "The source book carries no green contour or slope data, so the",
              "centre of each green page is left open. That needs a survey or",
              "lidar, not a conversion."]:
        T(c,MG+1,y,L,4.3,C_RED if "no green contour" in L else HexColor("#555555")); y-=7

c=canvas.Canvas("cowboys_pro_book.pdf",pagesize=(PW,PH))
c.setTitle("Cowboys Golf Club - Yardage Book (pro format)")
cover(c); c.showPage()
legend(c); c.showPage()
for n in sorted(H):
    green_page(c,n); c.showPage()
    if H[n]["par"]==5:
        hole_page(c,n,0); c.showPage()
        hole_page(c,n,1); c.showPage()
    else:
        hole_page(c,n); c.showPage()
c.save()
print("wrote cowboys_pro_book.pdf")

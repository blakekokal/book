import requests, json, numpy as np, tifffile, math
from pyproj import Transformer, CRS
from model import CRS_L, T3857
UA={"User-Agent":"yardage-book-prototype/0.1"}
b=json.load(open("corridor_meta.json"))["bounds"]
x0,y0,x1,y1=b
c0=T3857.transform(x0,y0); c1=T3857.transform(x1,y1)
mx0,my0=min(c0[0],c1[0]),min(c0[1],c1[1]); mx1,my1=max(c0[0],c1[0]),max(c0[1],c1[1])
res=0.5
nx=int((x1-x0)/res); ny=int((y1-y0)/res)
U="https://imagery.nationalmap.gov/arcgis/rest/services/USGSNAIPPlus/ImageServer"
info=requests.get(U,params={"f":"json"},headers=UA,timeout=60).json()
print("bandCount",info.get("bandCount"),"pixelType",info.get("pixelType"))
p={"bbox":f"{mx0},{my0},{mx1},{my1}","bboxSR":3857,"imageSR":3857,"size":f"{nx},{ny}",
   "format":"tiff","f":"image","bandIds":"0,1,2,3" if info.get("bandCount",3)>=4 else "0,1,2"}
r=requests.get(U+"/exportImage",params=p,headers=UA,timeout=180)
print("http",r.status_code,r.headers.get("content-type"),len(r.content))
open("naip.tif","wb").write(r.content)
a=tifffile.imread("naip.tif")
print("shape",a.shape,a.dtype, "min",a.min(),"max",a.max())
np.save("naip.npy",a)
json.dump({"bounds":b,"nx":nx,"ny":ny,"res":res},open("naip_meta.json","w"))

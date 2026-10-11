import requests,bs4,json,re
urls={
 "tokyo_form":"https://www.jra.go.jp/JRADB/accessD.html?CNAME=pw01dde0105202604041120261011/CE",
 "kyoto_form":"https://www.jra.go.jp/JRADB/accessD.html?CNAME=pw01dde0108202604041120261011/AC",
 "tokyo_tf":"https://sports.yahoo.co.jp/keiba/race/odds/tfw/2605040411?ninki=0",
 "kyoto_tf":"https://sports.yahoo.co.jp/keiba/race/odds/tfw/2608040411?ninki=0",
 "kyoto_ur":"https://sports.yahoo.co.jp/keiba/race/odds/ur/2608040411?ninki=0",
 "kyoto_sf":"https://sports.yahoo.co.jp/keiba/race/odds/sf/2608040411?ninki=0",
 "kyoto_st":"https://sports.yahoo.co.jp/keiba/race/odds/st/2608040411?ninki=0",
}
for name,url in urls.items():
 try:
  r=requests.get(url,timeout=18,headers={"User-Agent":"Mozilla/5.0 (compatible; JRA-data-research/1.0)"})
  s=bs4.BeautifulSoup(r.content,"html.parser")
  sections=s.select("table")
  print(json.dumps({"probe":name,"status":r.status_code,"bytes":len(r.content),"tables":len(sections),"rows":[len(t.select('tr')) for t in sections[:12]],"samples":[t.get_text(' ',strip=True)[:260] for t in sections[:4]],"text_start":s.get_text(' ',strip=True)[-1100:] if name.endswith("st") else s.get_text(' ',strip=True)[0:480],"final_url":r.url},ensure_ascii=False))
 except Exception as e:print(json.dumps({"probe":name,"error":str(e)},ensure_ascii=False))

for name,url in {"jra":"https://www.jra.go.jp/JRADB/accessD.html?CNAME=pw01dde0108202604041120261011/AC",
"tf":"https://sports.yahoo.co.jp/keiba/race/odds/tfw/2608040411?ninki=0",
"ur":"https://sports.yahoo.co.jp/keiba/race/odds/ur/2608040411?ninki=0",
"wide":"https://sports.yahoo.co.jp/keiba/race/odds/wide/2608040411?ninki=0",
"ut":"https://sports.yahoo.co.jp/keiba/race/odds/ut/2608040411?ninki=0",
"sf":"https://sports.yahoo.co.jp/keiba/race/odds/sf/2608040411?ninki=0",
"st":"https://sports.yahoo.co.jp/keiba/race/odds/st/2608040411?ninki=0"}.items():
 try:
  r=requests.get(url,timeout=20,headers={"User-Agent":"Mozilla/5.0"})
  soup=bs4.BeautifulSoup(r.content,"html.parser")
  print("STRUCT",name,json.dumps({
   "tables":len(soup.select("table")),
   "headrowcells":[[(e.name,e.get_text(' ',strip=True)[:110],e.get('class')) for e in tr.find_all(['th','td'],recursive=False)[:8]] for tr in soup.select("table")[0].select("tr")[:3]],
   "tailtable":[t.get_text(' ',strip=True)[:50] for t in soup.select("table")[-2:]],
   "firsttable_html":str(soup.select('table')[0])[:650]
  },ensure_ascii=False))
 except Exception as e:print("STRUCT_ERROR",name,str(e))

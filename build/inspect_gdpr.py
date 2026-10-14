import re, lxml.html
t=open("data/raw/gdpr.xhtml",encoding="utf-8").read()
t=re.sub(r'^<\?xml[^>]*\?>','',t); t=re.sub(r'<!DOCTYPE[^>]*>','',t)
root=lxml.html.fromstring(t)
links=[(a.get('href'),a.text_content()) for a in root.iter('a')]
print(len(links), links[:8])
print(set(p.get('class') for p in root.iter('p')))
# articles without numbered paragraph divs
for art in root.xpath('//div[starts-with(@id,"art_") and not(contains(@id,".tit"))]'):
    nums=art.xpath('./div[re:test(@id,"^\d{3}\.\d{3}$")]',namespaces={'re':'http://exslt.org/regular-expressions'})
    if not nums: print(art.get('id'), end=' ')
print()
c=root.xpath('//div[@id="cpt_I"]')[0]
print([ (e.tag,e.get('id'),e.get('class')) for e in c][:8])
print(lxml.html.tostring(c)[:600])

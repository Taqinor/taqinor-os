"""Champs de donnees.md §2 absents de api.md, et clés JSON d'api.md absentes de donnees.md. Jetable."""
import re, pathlib
ref = pathlib.Path(__file__).resolve().parents[2] / 'reference'
don = (ref / 'donnees.md').read_text(encoding='utf-8')
api = (ref / 'api.md').read_text(encoding='utf-8')
sec2 = don.split('## 2. Modèles')[1].split('## 3. Invariants')[0]
models = re.split(r'\n### 2\.\d+ ', sec2)[1:]
fields = {}
for blk in models:
    name = blk.split()[0].strip('`')
    fs = set(re.findall(r'^\| `([a-z_]+)`', blk, re.M))
    for row in re.findall(r'^\| `([a-z_]+)`[^|]*?(?:, `([a-z_]+)`)+', blk, re.M):
        fs.update(r for r in row if r)
    for row in re.findall(r'^\| ((?:`[a-z_]+`(?:, | / )?)+) \|', blk, re.M):
        fs.update(re.findall(r'`([a-z_]+)`', row))
    # inline prose models: "`champ` FK" / "· `champ` Char"
    fs.update(re.findall(r'(?:^|· |: )`([a-z_]+)` (?:FK|Char|Bool|Integer|PositiveInt|PositiveSmallInt|SmallInt|Date|DateTime|Time|JSONField|Decimal)', blk, re.M))
    fields[name] = fs
apikeys = set(re.findall(r'"([a-z_0-9]+)"\s*:', api)) | set(re.findall(r'`([a-z_]+)`', api)) | set(re.findall(r'"([a-z_]+)"', api))
for m, fs in fields.items():
    absent = sorted(f for f in fs if f not in apikeys and f not in ('proprietaire',))
    print(f'{m:18} {len(fs):3} champs ; absents d\'api.md : {absent}')
donkeys = set(re.findall(r'`([a-z_]+)`', don))
jsonkeys = set(re.findall(r'"([a-z_0-9]+)"\s*:', api))
print('\nclés JSON d\'api.md absentes de donnees.md (dérivées attendues) :')
print(sorted(k for k in jsonkeys if k not in donkeys))

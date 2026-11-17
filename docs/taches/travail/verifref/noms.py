"""Longueur des noms de contrainte/index de donnees.md (Django : <= 30 pour Index.name). Jetable."""
import re, pathlib, collections
ref = pathlib.Path(__file__).resolve().parents[2] / 'reference'
don = (ref / 'donnees.md').read_text(encoding='utf-8')
noms = sorted(set(re.findall(r'`(taches_[a-z0-9_]+_(?:uniq|idx|ck))`', don)))
for n in noms:
    print(f'{len(n):3} {"OK " if len(n) <= 30 else "TROP"} {n}')
print('total', len(noms))
dup = [n for n, c in collections.Counter(re.findall(r'`(taches_[a-z0-9_]+_(?:uniq|idx|ck))`', don)).items() if c > 1]
print('cités plusieurs fois :', dup)

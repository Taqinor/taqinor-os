"""Plus longue valeur de chaque énumération de donnees.md §1 vs max_length déclaré en §2 (table saisie à la main). Jetable."""
import re, pathlib
don = (pathlib.Path(__file__).resolve().parents[2] / 'reference' / 'donnees.md').read_text(encoding='utf-8')
sec1 = don.split('## 1.')[1].split('## 2.')[0]
vals = {}
for l in sec1.splitlines():
    m = re.match(r'\| `?([A-Za-z]+)`?[^|]*\| (.*?) \|', l)
    if m:
        vals[m.group(1)] = [v for v in re.findall(r'`([a-z_0-9]+)`', m.group(2))]
decl = {'StatutTache': 12, 'StatutProjet': 12, 'IssueProjet': 10, 'Moment': 12, 'Source': 12, 'Couleur': 16,
        'Visibilite': 10, 'LienEtat': 12, 'Frequence': 12, 'ModeRecurrence': 12, 'ModeRythme': 12,
        'CapaciteSource': 12, 'StatutJour': 12, 'StatutRappel': 12, 'UsageJeton': 10, 'ReponseIncitation': 24,
        'CanalIncitation': 8, 'FamilleSuggestion': 24, 'StatutSuggestion': 12, 'DecisionRevue': 10, 'SourcePreference': 10}
for k, n in decl.items():
    v = vals.get(k, [])
    lon = max(v, key=len) if v else None
    print(f'{k:18} max_length={n:2} plus longue={lon!r:24} {len(lon) if lon else "-"} {"OK" if lon and len(lon) <= n else "?"}')

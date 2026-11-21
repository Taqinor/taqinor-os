# Contrôle de cohérence de toute la vague à partir des copies d'édition.
import re, sys, pathlib, subprocess, collections
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import corr_outils as co
corr = pathlib.Path(sys.argv[1]); integ = pathlib.Path(sys.argv[2])
taches = {}; suppr = {}; doublons = []
for f in sorted(corr.glob("src-*.md")):
    for i, maison, ligne, raison in co.lire_edition(f):
        if i in taches or i in suppr: doublons.append((i, f.name))
        if ligne is None: suppr[i] = (f.name, raison[:90])
        else: taches[i] = (f.name, maison, ligne)
print(f"tâches vivantes : {len(taches)} ; supprimées : {len(suppr)} ; ids en double : {doublons}")
# statut des tâches déjà au plan (main)
statut = {}
for p in list((integ / "docs/plans").glob("*.md")) + [integ / "docs/PLAN.md", integ / "docs/PLAN2.md", integ / "docs/WEB_PLAN.md"]:
    for l in p.read_text(encoding="utf-8").splitlines():
        m = re.match(r"- \[(.*?)\] ((?:ACAL|CALX)\d+) ", l)
        if m and m.group(2) not in taches and m.group(2) not in suppr: statut[m.group(2)] = m.group(1)[:1] or " "
deps = {}
for i, (f, maison, l) in taches.items():
    d = set()
    for m in re.finditer(r"\(@after:\s*([^)]*)\)", l): d |= set(re.findall(r"[A-Z]+\d+", m.group(1)))
    deps[i] = d
pb = collections.defaultdict(list)
for i, d in deps.items():
    for x in sorted(d):
        if x in suppr: pb["@after vers une tâche SUPPRIMÉE"].append(f"{i}→{x} ({taches[i][0]})")
        elif x not in taches and x not in statut: pb["@after vers un id INCONNU"].append(f"{i}→{x} ({taches[i][0]})")
        elif x in statut and statut[x].lower() == "x": pb["@after vers une tâche déjà cochée (inutile)"].append(f"{i}→{x}")
        elif x in statut and statut[x] not in (" ", "x", "X"): pb["@after vers une tâche BLOCKED/GATED du plan"].append(f"{i}→{x} [{statut[x]}]")
# cycles
couleur = {}; cycles = []
def visite(n, pile):
    couleur[n] = 1
    for x in sorted(deps.get(n, ())):
        if x not in taches: continue
        if couleur.get(x) == 1: cycles.append(" → ".join(pile[pile.index(x):] + [x]) if x in pile else f"{n}→{x}")
        elif couleur.get(x) is None: visite(x, pile + [x])
    couleur[n] = 2
sys.setrecursionlimit(10000)
for n in sorted(taches):
    if couleur.get(n) is None: visite(n, [n])
pb["CYCLES"] = cycles
# mentions d'ids supprimés dans le texte (hors @after)
for i, (f, maison, l) in taches.items():
    cites = set(re.findall(r"ACAL\d+", l)) & set(suppr)
    if cites: pb["texte qui cite une tâche supprimée"].append(f"{i} cite {sorted(cites)} ({f})")
# producteurs PACT11 et urls
for i, (f, maison, l) in taches.items():
    fl = l.split("Files:")[-1]
    if re.search(r"apps/calepinage/urls\.py", fl): pb["déclare apps/calepinage/urls.py"].append(i)
    if re.search(r"apps/calepinage/selectors\.py", fl): pb["déclare apps/calepinage/selectors.py (vague 0 attendue : 572 595 770 883 895 948 961 964 978)"].append(i)
    if "%s" in l: pb["reste de gabarit %s"].append(i)
    if not re.search(r"\(gen manuel [0-9a-f]{7}", l): pb["tampon gen manuel absent"].append(i)
    if len(l) > 9000: pb["tâche de plus de 9 000 caractères"].append(f"{i} ({len(l)})")
for k, v in pb.items():
    print(f"\n## {k} : {len(v)}")
    for x in v[:60]: print("  ", x)
par_plan = collections.Counter(m for _, m, _ in taches.values())
print("\n## par plan :", dict(par_plan))

# Découpe la vague 2 en lots de lecture (une clause par ligne) pour les vérificateurs.
import re, sys, pathlib, subprocess, textwrap
integ = pathlib.Path(sys.argv[1]); out = pathlib.Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
MARQ = ["Constat :", "Given ", "Persistance :", "Emplacement :", "Code net :", "Appelants :",
        "Assertions existantes :", "Jumeaux :", "Listes figées :", "Contrat partagé :",
        "Test rouge d'abord :", "Preuve en direct :", "Hors périmètre :", "(gen manuel", "Files:"]
def lisible(l):
    for m in MARQ:
        l = l.replace(" " + m, "\n  " + m)
    res = []
    for ligne in l.split("\n"):
        res.extend(textwrap.wrap(ligne, 1400, subsequent_indent="    ", break_long_words=False, break_on_hyphens=False) or [""])
    return "\n".join(res)
taches = []  # (id, plan, section, domaine, ligne brute)
bloc = integ / "docs/audits/l5-calepinage/INSERTION-PLAN_AUDIT_CALEPINAGE.md"
sec = dom = ""
for l in bloc.read_text(encoding="utf-8").splitlines():
    if l.startswith("### "): sec = l[4:].strip(); dom = ""
    elif l.startswith("#### "): dom = l[5:].split(" ")[0]
    m = re.match(r"- \[.\] (ACAL\d+) ", l)
    if m: taches.append((m.group(1), "PLAN_AUDIT_CALEPINAGE (bloc à insérer)", sec, dom, l))
plans = ["docs/WEB_PLAN.md"] + [f"docs/plans/PLAN_AUDIT_{x}.md" for x in "CHANTIERS DEPLOY DEVIS LEAD MOTEUR PARAMETRES SAV STOCK".split()]
for p in plans:
    d = subprocess.run(["git", "-C", str(integ), "diff", "origin/main", "--", p], capture_output=True, text=True, encoding="utf-8").stdout
    for l in d.splitlines():
        m = re.match(r"\+(- \[.\] (ACAL\d+) .*)", l)
        if m: taches.append((m.group(2), p, "autre plan", "", m.group(1)))
num = lambda t: int(t[0][4:])
D8 = set(range(991, 1012)) | {973, 1030}
def prio(l):
    m = re.search(r"\bP([0-3])\b", l[:400]); return "P" + m.group(1) if m else "?"
# index
with open(out / "INDEX.md", "w", encoding="utf-8") as f:
    f.write("# Index de la vague 2 (une ligne par tâche)\n\n")
    for t in sorted(taches, key=num):
        l = t[4]; titre = re.search(r"\*\*(.*?)\*\*", l); titre = (titre.group(1) if titre else l)[:230]
        apres = re.search(r"\(@after: ([^)]*)\)", l); lane = re.search(r"\(@lane: ([^)]*)\)", l); mod = re.search(r"\(@model: ([^)]*)\)", l)
        f.write(f"- {t[0]} | {t[1].replace('docs/plans/','')} | {t[2][:22]} {t[3]} | {titre} | after: {apres.group(1) if apres else '-'} | lane: {lane.group(1) if lane else '-'} | {mod.group(1) if mod else '-'}\n")
# lots
cal = [t for t in taches if t[1].startswith("PLAN_AUDIT_CALEPINAGE")]
autres = [t for t in taches if not t[1].startswith("PLAN_AUDIT_CALEPINAGE")]
lots = {}
fable = [t for t in taches if num(t) in D8 or t[3] == "D8"]
ids_fable = {t[0] for t in fable}
for d in ["D1","D2","D3","D4","D5","D6","D7"]:
    ts = sorted([t for t in cal if t[3] == d and t[0] not in ids_fable], key=num)
    n = max(1, round(len(ts) / 26))
    k = -(-len(ts) // n)
    for i in range(n): lots[f"{d}-{chr(97+i)}"] = ts[i*k:(i+1)*k]
reste = sorted([t for t in cal if t[3] not in ["D1","D2","D3","D4","D5","D6","D7","D8"] and t[0] not in ids_fable], key=num)
lots["AUTRES-PLANS"] = sorted([t for t in autres if t[0] not in ids_fable], key=num) + reste
lots["D8-FABLE"] = sorted(fable, key=num)
for nom, ts in lots.items():
    with open(out / f"lot-{nom}.md", "w", encoding="utf-8") as f:
        f.write(f"# Lot de vérification {nom} — {len(ts)} tâches (copie de LECTURE, une clause par ligne ; le texte source est sur UNE ligne dans le plan)\n\n")
        for t in ts:
            f.write(f"## {t[0]} — plan : {t[1]} — section : {t[2]} {t[3]}\n{lisible(t[4])}\n\n")
    print(nom, len(ts), (out / f"lot-{nom}.md").stat().st_size // 1024, "Ko", ts[0][0] if ts else "", ts[-1][0] if ts else "")
print("total", len(taches), "uniques", len({t[0] for t in taches}))

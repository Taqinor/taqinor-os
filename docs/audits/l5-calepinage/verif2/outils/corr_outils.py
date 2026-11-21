# Outils de la passe de correction : prepare (copies d'édition), rejoint (retour à une ligne par tâche).
import re, sys, pathlib, subprocess, textwrap
MARQ = ["Constat :", "Given ", "Persistance :", "Emplacement :", "Code net :", "Appelants :",
        "Assertions existantes :", "Jumeaux :", "Listes figées :", "Contrat partagé :",
        "Test rouge d'abord :", "Preuve en direct :", "Hors périmètre :", "(gen manuel", "Files:"]
def lisible(l):
    for m in MARQ:
        l = l.replace(" " + m, "\n  " + m)
    res = []
    for ligne in l.split("\n"):
        res.extend(textwrap.wrap(ligne, 1400, subsequent_indent="    ", break_long_words=False, break_on_hyphens=False, replace_whitespace=False, drop_whitespace=True) or [""])
    return "\n".join(res)
def rejoindre(corps):
    return " ".join(x.strip() for x in corps.split("\n") if x.strip())
def lire_edition(chemin):
    """-> liste de (id, maison, ligne ou None si supprimée, raison)"""
    out = []; cur = None
    for l in pathlib.Path(chemin).read_text(encoding="utf-8").split("\n"):
        m = re.match(r"## (ACAL\d+) @@ (.+?)\s*$", l)
        if m:
            cur = [m.group(1), m.group(2), []]; out.append(cur); continue
        if cur is not None and not l.startswith("# "): cur[2].append(l)
    res = []
    for i, maison, lignes in out:
        corps = rejoindre("\n".join(lignes))
        if corps.startswith("SUPPRIMÉE"): res.append((i, maison, None, corps))
        else: res.append((i, maison, corps, ""))
    return res
if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "rejoint":
        src, dst = sys.argv[2], sys.argv[3]
        with open(dst, "w", encoding="utf-8") as f:
            for i, maison, ligne, raison in lire_edition(src):
                if ligne is None: continue
                if not ligne.startswith(f"- [ ] {i} "): print("ALERTE", i, ": le corps ne commence pas par « - [ ] " + i + " »")
                f.write(ligne + "\n\n")
        print("écrit", dst)
    elif cmd == "prepare":
        integ = pathlib.Path(sys.argv[2]); verif = pathlib.Path(sys.argv[3]); corr = pathlib.Path(sys.argv[4])
        brutes = {}
        bloc = "docs/audits/l5-calepinage/INSERTION-PLAN_AUDIT_CALEPINAGE.md"
        plans = ["docs/WEB_PLAN.md"] + [f"docs/plans/PLAN_AUDIT_{x}.md" for x in "CHANTIERS DEPLOY DEVIS LEAD MOTEUR PARAMETRES SAV STOCK".split()]
        for l in (integ / bloc).read_text(encoding="utf-8").splitlines():
            m = re.match(r"- \[.\] (ACAL\d+) ", l)
            if m: brutes[m.group(1)] = (bloc, l)
        for p in plans:
            d = subprocess.run(["git", "-C", str(integ), "diff", "origin/main", "--", p], capture_output=True, text=True, encoding="utf-8").stdout
            for l in d.splitlines():
                m = re.match(r"\+(- \[.\] (ACAL\d+) .*)", l)
                if m: brutes[m.group(2)] = (p, m.group(1))
        ko = 0; prochain = 1033
        for lot in sorted(verif.glob("lot-*.md")):
            nom = lot.stem[4:]; ids = re.findall(r"^## (ACAL\d+) ", lot.read_text(encoding="utf-8"), flags=re.M)
            with open(corr / f"src-{nom}.md", "w", encoding="utf-8") as f:
                f.write(f"# Copie d'ÉDITION du lot {nom} — {len(ids)} tâches. Ids libres pour une scission : ACAL{prochain} à ACAL{prochain+7}.\n\n")
                for i in ids:
                    maison, l = brutes[i]
                    ed = lisible(l)
                    if re.sub(r"\s+", " ", rejoindre(ed)) != re.sub(r"\s+", " ", l.strip()): ko += 1; print("aller-retour KO", i)
                    f.write(f"## {i} @@ {maison}\n{ed}\n\n")
            print(nom, len(ids), f"ids libres {prochain}-{prochain+7}"); prochain += 8
        print("aller-retour KO :", ko, "| tâches", len(brutes))

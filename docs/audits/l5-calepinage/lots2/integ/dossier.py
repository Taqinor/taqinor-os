"""Génère docs/audits/2026-11-21-calepinage-l5-vague2.md depuis les fichiers INSERTION-* et les registres."""
import re, os, json, glob, sys
from collections import Counter
H = os.path.dirname(os.path.abspath(__file__)); S = os.path.join(H, ".."); L = os.path.join(S, "lots2")
OUT = sys.argv[1]
rows = []
for f in sorted(glob.glob(os.path.join(L, "INSERTION-*.md"))):
    plan = os.path.basename(f)[10:-3]; sec = dom = None
    for l in open(f, encoding="utf-8"):
        m = re.match(r"^#{3,4} ACAL — (.*)", l)
        if m: sec = m.group(1).strip(); continue
        m = re.match(r"^#### (D\d) — ", l)
        if m: dom = m.group(1); continue
        m = re.match(r"^- \[ \] (ACAL\d+) — \*\*(.*?)\*\*", l)
        if not m: continue
        seg = l.split("Constat :", 1)[-1][:160]
        c1 = re.search(r"(C\d+)", seg); c2 = re.search(r"(S[1-4])", seg)
        c = (c1, c2)
        p = re.search(r"Priorité : (P\d)", l)
        titre = re.sub(r"^\[GATED[^\]]*\]\s*", "", m.group(2)).split(" ; fini quand")[0]
        rows.append(dict(id=m.group(1), plan=plan, sec=sec, dom=dom, crit=c[0].group(1) if c[0] else "—", grav=c[1].group(1) if c[1] else "—",
                         prio=p.group(1) if p else "—", titre=titre[:110].replace("|", "/"), line=l))
fi = json.load(open(os.path.join(H, "final_index.json"), encoding="utf-8"))
domid = {r["id"]: r["domain"] for r in fi}
for r in rows:
    r["dom"] = domid.get(r["id"], r["dom"] or "—")
    if r["id"] == "ACAL1031": r["dom"] = "acceptation"
def table(rs):
    out = ["| Constat | Critère, gravité | Tâche | Plan | Section | Titre abrégé |", "|---|---|---|---|---|---|"]
    for r in sorted(rs, key=lambda r: int(r["id"][4:])):
        out.append(f"| C-ACAL-L5-{r['id'][4:]} | {r['crit']}, {r['grav']} | {r['id']} | {r['plan']} | {r['sec']} | {r['titre']} |")
    return out
cnt = lambda key: ", ".join(f"{k} {v}" for k, v in sorted(Counter(r[key] for r in rows).items()))
# constats de relecteurs retenus sans tâche
txt = "\n".join(r["line"] for r in rows)
sans = []
for l in open(os.path.join(S, "registre", "evenements", "T1-consolidation.jsonl"), encoding="utf-8"):
    e = json.loads(l)
    if e.get("verdict") != "retenu": continue
    if e["id"] in txt: continue
    if e.get("tache") and e["tache"] != "nouvelle": continue
    sans.append(e)
dele = json.load(open(os.path.join(H, "deleted.json"), encoding="utf-8"))
reserve = open(os.path.join(H, "reserve.md"), encoding="utf-8").read()
reserve = re.sub(r"<!-- méthode.*?-->", "", reserve, flags=re.S).strip()
D = []
D += ["# Calepinage — vague 2 du complément L5 (21/11/2026) : table des constats et réserve", "",
      "Dossier de la vague 2 de la campagne go-deep L5 calepinage (demandes de Reda des 20 et 21/11/2026 : « much more functionalities as the big players… extremely simple… the most pretty calpinage module… only add tasks to the plan » ; « do a real work… multiple rounds of L5 »). Rien n'est construit : ce dossier accompagne l'insertion des tâches. Dossier du tour 0 et contrat de sortie K1-K15 : `docs/audits/2026-11-20-calepinage-l5.md`. Notes de travail (étude, maquettes, relecteurs, architecture) : `docs/audits/l5-calepinage/`.", "",
      "## Où vivent les tâches", "",
      f"- {len(rows)} tâches v3 (constat `C-ACAL-L5-<numéro de la tâche>`).",
      "- Groupe principal : `docs/plans/PLAN_AUDIT_CALEPINAGE.md`, `## Groupe ACAL — complément du 2026-11-21 (vague 2)`. Si ce groupe n'y est pas encore (fichier tenu par un autre poste au 21/11), le bloc prêt à insérer est `docs/audits/l5-calepinage/lots2/INSERTION-PLAN_AUDIT_CALEPINAGE.md` (branche de notes).",
      "- Moitiés des autres propriétaires : même titre de groupe dans `PLAN_AUDIT_DEVIS`, `PLAN_AUDIT_MOTEUR`, `PLAN_AUDIT_LEAD`, `PLAN_AUDIT_CHANTIERS`, `PLAN_AUDIT_STOCK`, `PLAN_AUDIT_SAV`, `PLAN_AUDIT_PARAMETRES`, `PLAN_AUDIT_DEPLOY` et `docs/WEB_PLAN.md`.",
      "- Décisions de Reda du 21/11 : D-ACAL-35 à D-ACAL-42 (`docs/audits/decisions.yml`, `docs/claude-memory/calepinage-decisions-fondateur.md`).", "",
      "## Comptes", "",
      f"- Par domaine : {cnt('dom')}.", f"- Par priorité : {cnt('prio')}.", f"- Par plan : {cnt('plan')}.",
      f"- Par section : {cnt('sec')}.", f"- Par gravité : {cnt('grav')}.", "",
      "## Table des constats (générée depuis les fichiers d'insertion)", ""] + table(rows) + ["",
      "## Tâches retirées à la réconciliation (doublons ou décisions)", ""] + [f"- {k} — {v}" for k, v in sorted(dele.items(), key=lambda x: int(x[0][4:]))] + ["",
      "## Réserve (capacités non écrites, une ligne chacune)", "",
      re.sub(r"(?m)^(#+) ", lambda m: "#" + m.group(1) + " ", reserve), "",
      "- Gabarit de schéma choisi par distributeur du lead (ex-ACAL679, ACAL680) — D-ACAL-42 : profils par distributeur plus tard.", "",
      "## Constats de relecteurs retenus restés sans tâche", ""]
D += ([f"- {e['id']} ({e.get('priorite')}, {e.get('proprietaire')}) — {e.get('correction','')[:140]}" for e in sans] or ["- aucun : chaque constat retenu du tour 1 est cité par une tâche de cette vague ou couvert par une tâche existante (champ `tache` de `registre/evenements/T1-consolidation.jsonl`)."])
D += ["", "## Limites (dites telles quelles)", "",
      "- Aucun test exécuté : chaque « test rouge d'abord » est attendu, non mesuré ; aucune tâche n'a été construite.",
      "- Les chiffres de l'étude (valeurs publiées, forums) sont à relire à leur source par le constructeur avant d'entrer dans le produit (WebFetch rend des résumés).",
      "- Rien n'a été vu sur une vraie image satellite (fond neutre de la pile de revue).",
      "- Les résultats de simulation et les PDF lourds n'ont pas été observés sur la pile : pas de worker Celery au tour 1 (ACAL1031 l'exige).",
      "- Lecture du code sur `207c7a70e` ; les ancres ont été revérifiées sur `origin/main@919b49b7d` (trois ancres réalignées : `TotalKpis` remplacé par `ResultatHeros` par ACAL443) ; une prémisse peut avoir bougé depuis sur l'autre poste : chaque tâche se re-vérifie avant construction.",
      "- Les dépendances vers une tâche d'un autre plan sont écrites en phrase, le planificateur ne les impose pas.", ""]
open(OUT, "w", encoding="utf-8", newline="\r\n").write("\n".join(D))
print(len(rows), "taches ;", len(sans), "constats sans tache ;", len(dele), "retirees")

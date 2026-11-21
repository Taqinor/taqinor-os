"""Assemble les fichiers prêts à insérer (vague 2) depuis lots2/lot-D*.md réconciliés."""
import re, os, json, glob
H = os.path.dirname(os.path.abspath(__file__)); L = os.path.join(H, "..", "lots2")
CAL = "docs/plans/PLAN_AUDIT_CALEPINAGE.md"
SECS = ["M1 bloquant-fondateur", "M2", "GATED (ne PAS auto-construire)"]
DOMS = {"D1": "Site, toit, relevé", "D2": "Pose, structure, plans d'équipe", "D3": "Électrique",
        "D4": "Simulation, résultats, rapport", "D5": "Consommation, stockage, pompage, réseau",
        "D6": "Parcours, explications, partage avec le client", "D7": "Corrections des constats du tour 1",
        "D8": "Moteur partagé : une seule porte de chiffrage"}
TASK = re.compile(r"^- \[ \] (ACAL\d+) — ")
rows = []
for d in DOMS:
    for suf in ("", "-autres-plans"):
        plan = CAL; sec = None
        for l in open(os.path.join(L, f"lot-{d}{suf}.md"), encoding="utf-8").read().split("\n"):
            m = re.match(r"^## → (\S+)", l)
            if m: plan = m.group(1); continue
            m = re.match(r"^### ACAL — (.*)", l)
            if m: sec = m.group(1).strip(); continue
            m = TASK.match(l)
            if m: rows.append(dict(id=m.group(1), d=d, plan=plan, sec=sec, line=l))
n = lambda i: int(i[4:])
def plages(ids):
    ids = sorted(set(n(i) for i in ids)); out = []; a = b = None
    for x in ids:
        if a is None: a = b = x
        elif x == b + 1: b = x
        else: out.append((a, b)); a = b = x
    if a is not None: out.append((a, b))
    return ", ".join(f"ACAL{a}" if a == b else f"ACAL{a}-{b}" for a, b in out)

cal = [r for r in rows if r["plan"] == CAL]
gated = [r["id"] for r in rows if r["sec"].startswith("GATED")]
couverts_cal = [r["id"] for r in cal if not r["sec"].startswith("GATED")]
autres = [r for r in rows if r["plan"] != CAL and not r["sec"].startswith("GATED")]
N = len(rows) + 1
ACC = ("- [ ] ACAL1031 — **Acceptation live de la vague 2 du complément (" + plages(couverts_cal) + " de ce groupe, hors GATED " + ", ".join(gated)
 + " ; et les moitiés routées aux plans devis, moteur, lead, chantiers, stock, SAV, paramètres, deploy et web : " + plages([r["id"] for r in autres])
 + ") : l'orchestrateur rejoue sur la pile de revue les parcours des relecteurs du tour 1, attaque les matrices de classes et mesure le contrat de sortie K1-K15, puis consigne la trace** : "
 "Constat : C-ACAL-L5-1031 (C19, S3, STATIQUE (lecture du 21/11 sur 207c7a70e)) — acceptation de la vague 2 (modèle : ACAL490 du groupe du 20/11) : une tâche à preuve en direct cochée sans rejeu est une régression livrée ; les 14 constats rejoués au tour 1 (`docs/audits/l5-calepinage/T1/rejeu.md`, six visibles du client) doivent être rejoués corrigés. "
 "Given la pile de revue migrée (`manage.py migrate` + reconstruction du front, AVEC un worker de simulation, ce que le tour 1 n'avait pas) et le seed de démo When l'orchestrateur rejoue les parcours des relecteurs S1, S2, F1, B1 et T1 (rapports `docs/audits/l5-calepinage/T1/*.md`), attaque chaque case « casse » des matrices `docs/audits/l5-calepinage/T1/classes/K-*.md` et mesure les quinze critères du contrat de sortie de `docs/audits/2026-11-20-calepinage-l5.md` (K1-K15) "
 "Then chaque clause « Preuve en direct » des tâches listées en titre est AFFIRMÉE à l'écran ou sur le PDF ; les 14 constats du rejeu ne se reproduisent plus ; pour D-ACAL-35, le PDF d'un devis neuf est-ouest imprime la production de la pose réelle et un devis envoyé est relu à l'identique ; aucune case « casse » d'une matrice K ne casse encore ; K1-K15 mesurés et écrits, chaque seuil manqué devient une tâche. "
 "Persistance : n/a — rejeu. Emplacement : n/a — orchestrateur, aucun code. Code net : n/a — aucune correction de code dans cette tâche. Appelants : n/a — rejeu. Assertions existantes : n/a — rejeu. Jumeaux : n/a — rejeu ; ACAL490 (vague 1) est distincte. Listes figées : n/a — rejeu. Contrat partagé : n/a — rejeu. Test rouge d'abord : n/a — tâche d'acceptation. "
 "Preuve en direct : enregistrement `docs/audits/acceptation/ACAL/<date>-<sha9>.md` et `.results.json` (`couvre:` les ids cochés), matrices K annotées, tableau K1-K15 ; puis les gestes de Reda : deploy (`scripts/deploy-prod.ps1`), essai sur son appareil. "
 "Hors périmètre : toute correction de code (les écarts deviennent des tâches), le deploy (le run s'arrête au merge). (gen manuel 207c7a7) Files: `docs/audits/acceptation/ACAL/` (ROUTINE) (@lane: calepinage/acceptation) (@model: opus) (@acceptation)")

PRE = [
 "> **Complément du 21/11/2026, vague 2 de la campagne go-deep L5 « plus de fonctions, le plus simple, le plus beau »** (demandes de Reda des 20 et 21/11). " + str(N) + " tâches v3, dont " + str(len(cal) + 1) + " dans ce fichier et " + str(len(rows) - len(cal)) + " chez leurs propriétaires (devis, moteur, lead, chantiers, stock, SAV, paramètres, deploy, web). Rien n'est construit. Lecture du code sur `207c7a70e`, ancres revérifiées sur `origin/main@919b49b7d`.",
 "> **Étude derrière ces tâches** : environ 6 100 lignes documentées avec leur source (manuels PVsyst et PV*SOL, éditeurs, forums en huit langues, notes de version, dépôts ouverts) et 136 constats de cinq relecteurs sur le produit réel (tour 1, 98 retenus, 10 classes). Dossier de travail `docs/audits/l5-calepinage/`, table des constats `docs/audits/2026-11-21-calepinage-l5-vague2.md`.",
 "> **Décisions de Reda du 21/11/2026** (`docs/audits/decisions.yml`) : **D-ACAL-35** les nouveaux devis à calepinage enregistré impriment la production de la pose réelle, envoyés inchangés, écarts montrés à Reda AVANT ; elle PRÉCISE D-ACAL-6, QJR107 et la ligne INTERDIT « imprimer le P50 du calepinage sur le devis, le PDF ou la page publique » plus haut dans ce fichier (ligne laissée telle quelle). **D-ACAL-36** surfaces cochées avant le devis. **D-ACAL-37** quatre éléments client hors PDF, sans prix. **D-ACAL-38** toit en pente affleurant = kit de fixation seul. **D-ACAL-39** sans facture : ni économie, ni TRI, ni retour. **D-ACAL-40** réservoir jour par jour interne. **D-ACAL-41** exemples = modèles de bibliothèque. **D-ACAL-42** un dossier distributeur générique.",
 "> **Choix pris seul** (prudents, réversibles) : un dessin automatique non vérifié n'est jamais montré au client ; le devis automatique n'est pas plafonné par un remplissage serveur pour l'instant ; le devis automatique depuis le lead reste possible avant la visite, inchangé ; le compte de panneaux du serveur ne fait pas foi avant un dry-run comparatif ; l'export Word reste en réserve ; le facteur carbone du réseau marocain est une recherche à mener (ACAL765), pas une question à Reda.",
 "> **Architecture corrigée (D8)** : la production et l'économie restent dans `apps/ventes`, derrière UNE porte (`chiffrer_conception`, plan devis) que l'atelier lit ; aucun interrupteur d'environnement sur un chiffre client ; UN niveau de règles (15) pour D-ACAL-35 et D-ACAL-38, activé seulement après lecture du dry-run par Reda (ACAL1001) ; rien de la production ne passe dans `core`. Les corrections P0 du lot D7 ne sont pas refaites en D8.",
 "> **Ordre de construction** : (1) contrats SEULS sur `main` d'abord : ACAL573, ACAL996, ACAL1005 ici, ACAL991 au plan devis ; (2) M1 = les chiffres faux visibles du client (P0) puis ce qui est déjà calculé sans écran (P1) ; (3) M2 ; (4) ACAL1031 en direct par l'orchestrateur. Chaîne D-ACAL-35 : ACAL996 → ACAL997 (ici) → ACAL998, ACAL999, ACAL1000 (devis) → ACAL973 (moteur) → ACAL1001.",
 "> **Dépendances vers un autre plan** : écrites en phrase dans la clause Constat (« ordre : après ACALnnn de … »), jamais en `@after`. Tâches ouvertes du groupe du 20/11 (non éditées) : ACAL397 se construit après ACAL937, ACAL436 après ACAL953. Une tâche qui « s'appuie sur » une tâche du 20/11 marquée BLOCKED lit son code déjà livré.",
 "> **Écran** : les maquettes `docs/audits/l5-calepinage/maquettes/*.dc.html` font foi (jetons de l'ERP, 6 tailles de texte, cibles ≥ 44 px). Un choix de design se tranche par la preuve de l'étude et des relecteurs, jamais « à valider par Reda ».",
 "> **Fichiers mono-écrivain et lanes** : `roof-tool-pro11.ts` et `roofPro11/prefill.ts` (calepinage/atelier-web), `ToitureDesign.jsx` et `BuilderDom.jsx` (calepinage/atelier-erp), `services/planche.py` (calepinage/livrables), `roof_layout_v2.schema.json` (calepinage/contrats), `chaine_pertes.py` et `calepinage_resultat.json` (calepinage/simulation), `PanneauProduction.jsx` (calepinage/resultats). Numéro de migration : toujours relu sur `origin/main` à la construction (`0NNN`).",
 "> **Hors complément** (inchangé) : statuts de devis (règle #4 ; le PDF ne change que par D-ACAL-35 et D-ACAL-38, au niveau 15), argent hors de `ventes`, données ou logiciels payants, trackers, pas sous-horaire, calcul normatif vent/neige.",
]
assert len(PRE) <= 12
HEAD = "## Groupe ACAL — complément du 2026-11-21 (vague 2) · format v3"

def bloc_cal():
    out = [HEAD, ""] + PRE + [""]
    for sec in SECS:
        sel = [r for r in cal if r["sec"] == sec]
        out += [f"### ACAL — {sec}", ""]
        for d in DOMS:
            s2 = [r for r in sel if r["d"] == d]
            if s2:
                out += [f"#### {d} — {DOMS[d]}", ""] + [r["line"] for r in s2] + [""]
    out += ["### ACAL — Acceptation en direct (orchestrateur, jamais une lane)", "", ACC, ""]
    return out
open(os.path.join(L, "INSERTION-PLAN_AUDIT_CALEPINAGE.md"), "w", encoding="utf-8", newline="\n").write("\n".join(bloc_cal()))
NOTE = "> Moitiés de propriétaire {o} de la vague 2 du complément L5 calepinage du 21/11/2026 (groupe principal à insérer dans `docs/plans/PLAN_AUDIT_CALEPINAGE.md` ; décisions D-ACAL-35 à 42 dans `docs/audits/decisions.yml` ; table des constats `docs/audits/2026-11-21-calepinage-l5-vague2.md`) ; une dépendance vers une tâche du plan calepinage est écrite en phrase dans la clause Constat."
fichiers = {}
for plan in sorted({r["plan"] for r in rows if r["plan"] != CAL}):
    sel = [r for r in rows if r["plan"] == plan]
    nom = os.path.basename(plan).replace(".md", "")
    web = plan.endswith("WEB_PLAN.md")
    out = [("### ACAL — complément L5 calepinage du 2026-11-21 (vague 2) · format v3" if web else HEAD), "", NOTE.format(o=nom.replace("PLAN_AUDIT_", "").lower()), ""]
    for sec in SECS:
        s2 = [r for r in sel if r["sec"] == sec]
        if s2: out += [("#### " if web else "### ") + f"ACAL — {sec}", ""] + [r["line"] for r in s2] + [""]
    open(os.path.join(L, f"INSERTION-{nom}.md"), "w", encoding="utf-8", newline="\n").write("\n".join(out))
    fichiers[plan] = len(sel)
json.dump(dict(total=N, cal=len(cal) + 1, autres=fichiers), open(os.path.join(H, "assemble.json"), "w"), indent=1)
print(N, len(cal) + 1, fichiers)

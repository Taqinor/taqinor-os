"""Réconciliation des lots de la vague 2 (L5 calepinage). Lit integ/orig/ + lot-D8* + A-sortie, écrit lots2/lot-D*.md.
Rejouable : repart toujours des originaux (integ/orig) ; journal dans integ/reconcile.log."""
import re, os, json, glob, subprocess
H = os.path.dirname(os.path.abspath(__file__))
L = os.path.join(H, "..", "lots2")
ORIG = os.path.join(H, "orig")
ROOT = r"C:/dev/taqinor-os/.claude/worktrees/l5-vague2-integ"
IDX = json.load(open(os.path.join(H, "plan_index.json"), encoding="utf-8"))
LOG = []
def log(*a): LOG.append(" ".join(str(x) for x in a))

SEC_M1, SEC_M2, SEC_G = "M1 bloquant-fondateur", "M2", "GATED (ne PAS auto-construire)"
CAL = "docs/plans/PLAN_AUDIT_CALEPINAGE.md"
TASK = re.compile(r"^- \[ \] (ACAL\d+) — ")

def parse(path, domain):
    out = []; plan = CAL; sec = None
    for l in open(path, encoding="utf-8").read().split("\n"):
        m = re.match(r"^## → (\S+)", l)
        if m: plan = m.group(1); sec = None; continue
        m = re.match(r"^### ACAL — (.*)", l)
        if m: sec = m.group(1).strip(); continue
        m = TASK.match(l)
        if m:
            out.append(dict(id=m.group(1), domain=domain, plan=plan, sec=sec, line=l.rstrip()))
    return out

tasks = []
for n in range(1, 8):
    for suf in ("", "-autres-plans"):
        p = os.path.join(ORIG, f"lot-D{n}{suf}.md")
        if os.path.exists(p): tasks += parse(p, f"D{n}")
for suf in ("", "-autres-plans"):
    tasks += parse(os.path.join(ORIG, f"lot-D8{suf}.md"), "D8")

def prio(line):
    m = re.search(r"Priorité : (P\d)", line); return m.group(1) if m else "P3"
tasks = [t for t in tasks if not (t["id"] == "ACAL973" and t["domain"] == "D7")]
for t in tasks:
    if t["id"] == "ACAL901": t["plan"] = CAL; log("PLAN 901 -> calepinage (selectors_calepinage.py est au proprietaire calepinage)")
    if "PanneauProduction.jsx::TotalKpis" in t["line"]:
        t["line"] = t["line"].replace("`frontend/src/features/calepinage/production/PanneauProduction.jsx::TotalKpis`", "`frontend/src/features/calepinage/production/ResultatHeros.jsx::ResultatHeros` (ex-`TotalKpis`, remplacé par ACAL443)"); log("ANCRE TotalKpis -> ResultatHeros", t["id"])
for t in tasks:
    if "[GATED" in t["line"][:120]: t["sec"] = SEC_G
    elif t["sec"] not in (SEC_M1, SEC_M2):
        t["sec"] = SEC_M1 if prio(t["line"]) in ("P0", "P1") else SEC_M2
byid = {t["id"]: t for t in tasks}

# ---- 1. sortie A (remplacements + nouvelles) ----
A = parse(os.path.join(H, "A-sortie.md"), "A")
DOM_NEW = {"ACAL1026": "D6", "ACAL1027": "D7", "ACAL1028": "D7", "ACAL1029": "D7"}
for a in A:
    if a["id"] in byid:
        t = byid[a["id"]]; t.update(plan=a["plan"], sec=a["sec"], line=a["line"]); log("A remplace", a["id"], a["plan"][-25:], a["sec"])
    else:
        a["domain"] = DOM_NEW[a["id"]]; tasks.append(a); byid[a["id"]] = a; log("A ajoute", a["id"], a["domain"])

# ---- 2. suppressions ----
DEL = {
 "ACAL898": "doublon d'ACAL697 (même fiche « pertes en mots simples ») — D-ACAL-37(d) la rend remettable au client (sortie A)",
 "ACAL849": "D-ACAL-40 : le bilan du réservoir reste interne ; ACAL807 le montre déjà à l'écran (sortie A)",
 "ACAL899": "D-ACAL-42 : profils par distributeur en réserve ; dossier générique déjà servi par `GabaritDossierReglementaire` (sortie A)",
 "ACAL785": "D-ACAL-42 : rien de prérempli ni deviné ; semis de gabarits par distributeur en réserve (sortie A)",
 "ACAL905": "doublon d'ACAL976 sur `apps/ventes/economie.py` ; D-ACAL-39 tranche (ni économie, ni TRI, ni retour sans consommation)",
 "ACAL691": "doublon d'ACAL854 + ACAL855 (écart PVGIS sous le chiffre de production, avec voyant)",
 "ACAL882": "couvert par ACAL719 (heure solaire ET heure légale sur la barre du soleil et la course du soleil)",
 "ACAL739": "doublon d'ACAL659 (mêmes champs de déclassement thermique de l'onduleur, sous deux noms) ; ACAL740-741 lisent ceux d'ACAL659",
 "ACAL930": "doublon d'ACAL608 (clé de pose des modules : `geometry.panelOrientation` d'ACAL573/601/608 est la seule clé)",
 "ACAL931": "doublon d'ACAL601 + ACAL605 (emprise orientée des modules à la planche et au plan de câblage)",
 "ACAL932": "doublon d'ACAL604 (emprise vraie des modules et tracé unique du toit au DXF)",
 "ACAL841": "second contrat de `zones[].existant` : ACAL573 (D2) est le seul propriétaire de la clé (forme booléen + `anneeMiseEnService`)",
 "ACAL844": "doublon d'ACAL510 (case « Modules déjà en place » et année de mise en service à l'atelier)",
 "ACAL823": "D-ACAL-42 : choix des gabarits par distributeur du lead = profils par distributeur (réserve)",
 "ACAL825": "D-ACAL-42 : saisie d'un distributeur sur un gabarit = profils par distributeur (réserve)",
 "ACAL826": "D-ACAL-42 : limite du profil du distributeur (réserve)",
 "ACAL679": "D-ACAL-42 : gabarit de schéma choisi par distributeur du lead = profils par distributeur (réserve)",
 "ACAL680": "D-ACAL-42 : affichage du gabarit par distributeur, suit ACAL679 (réserve)",
 "ACAL900": "export Word : réserve (preuve mince : deux fils de forum ; dépendance gratuite, donc pas une porte fondateur) — choix pris seul",
}
REMAP = {"ACAL739": "ACAL659", "ACAL930": "ACAL608", "ACAL931": "ACAL601", "ACAL932": "ACAL604", "ACAL841": "ACAL573",
         "ACAL844": "ACAL510", "ACAL823": "ACAL822", "ACAL691": "ACAL854", "ACAL882": "ACAL719", "ACAL898": "ACAL697",
         "ACAL905": "ACAL976", "ACAL849": None, "ACAL899": None, "ACAL785": None, "ACAL825": "ACAL822", "ACAL826": None, "ACAL900": None, "ACAL679": None, "ACAL680": None}
for i in DEL:
    if i in byid: log("SUPPRIME", i, "—", DEL[i])
    else: log("!! suppression d'un id absent", i)
tasks = [t for t in tasks if t["id"] not in DEL]
byid = {t["id"]: t for t in tasks}

# ---- 3. remplacements ciblés (id, ancien, nouveau) ----
EDITS = [
 ("ACAL934", "(`@after: ACAL934` à y poser)", "(ACAL858 porte la dépendance sur cette tâche)"),
 ("ACAL937", "qui doit porter `@after: ACAL937` (prérequis", "qui se construit après cette tâche (ordre écrit au préambule du groupe ; prérequis"),
 ("ACAL735", "(`(@after: ACAL734)`)", "(posé avant elle)"),
 ("ACAL656", " — `(@after: CALX356)`", " — après CALX356 de docs/PLAN2.md"),
 ("ACAL657", " — `(@after: CALX356)`", " — après CALX356 de docs/PLAN2.md"),
 ("ACAL658", " — `(@after: CALX356)`", " — après CALX356 de docs/PLAN2.md"),
 ("ACAL976", "ACAL905 (D6, GATED « règle commerciale ») pose la même question : celle-ci applique la règle zéro chiffre inventé (D-ACAL-7), ACAL905 devient sans objet.",
  "décision D-ACAL-39 du 21/11/2026 (sans consommation connue : aucune économie, aucun TRI, aucun retour affiché ni imprimé ; l'écran dit « renseignez la facture » et mène au champ) : cette tâche l'applique côté serveur, nouveaux rendus seulement."),
 ("ACAL858", "Calculer les contrôles ÉLECTRIQUES du « prêt à envoyer ? » depuis le verdict de publication",
  "Calculer les contrôles ÉLECTRIQUES du « prêt à envoyer ? » depuis l'état à trois valeurs servi par ACAL934 (prêt / à compléter / bloquant ; « à compléter » n'est jamais un blocage) et le verdict de publication"),
]
for i, a, b in EDITS:
    t = byid.get(i)
    if not t: log("!! edit id absent", i); continue
    if a not in t["line"]: log("!! edit introuvable", i, a[:60]); continue
    t["line"] = t["line"].replace(a, b); log("EDIT", i, a[:50])

# 740/741 : clés d'ACAL659
for i in ("ACAL740", "ACAL741"):
    t = byid.get(i)
    if t:
        s = t["line"]
        for a, b in (("ond_derating_t_debut_c", "ond_pnom_reduite_debut_c"), ("ond_derating_pente_pct_par_c", "ond_pnom_pente_pct_c"),
                     ("derating_t_debut_c", "pnom_reduite_debut_c"), ("derating_pente_pct_par_c", "pnom_pente_pct_c")):
            s = s.replace(a, b)
        t["line"] = s; log("EDIT cles 659", i)
# D5 existant : forme d'ACAL573
for i in ("ACAL842", "ACAL843", "ACAL848"):
    t = byid.get(i)
    if t:
        s = t["line"].replace("zones[].existant.annee_mise_en_service", "zones[].anneeMiseEnService").replace("annee_mise_en_service", "anneeMiseEnService")
        if s != t["line"]: log("EDIT existant 573", i)
        t["line"] = s
# 720 / 816 : la migration stock passe à ACAL660
MIG_PHRASE = "la migration est ACAL660 de docs/plans/PLAN_AUDIT_STOCK.md (même merge que ce modèle ; numéro de migration à relire sur origin/main à la construction)"
for i, mig in (("ACAL720", "backend/django_core/apps/stock/migrations/0183_fiche_module_sous_chaines.py"),
               ("ACAL816", "backend/django_core/apps/stock/migrations/0183_var_bus_dc_redresse_v.py")):
    t = byid[i]; s = t["line"]
    head, files = s.rsplit("Files:", 1)
    files = files.replace(f"`{mig}`, ", "").replace(f", `{mig}`", "")
    head = head.replace(f"`{mig}`", MIG_PHRASE).replace(mig, MIG_PHRASE)
    t["line"] = head + "Files:" + files; log("EDIT migration -> ACAL660", i)
t = byid["ACAL660"]
a = "Migrer les champs de fiche technique ajoutés par ACAL659 (cellules en série, coefficient de Isc, réduction de puissance de l'onduleur, entrées MPPT indépendantes, onduleurs compatibles)"
assert a in t["line"]
t["line"] = t["line"].replace(a, "Migrer, en UNE migration, les champs de fiche technique ajoutés par ACAL659 (cellules en série, coefficient de Isc, réduction de puissance de l'onduleur, entrées MPPT indépendantes, onduleurs compatibles), ACAL720 (`sous_chaines_par_module`) et ACAL816 (`var_bus_dc_redresse_v`)")
t["line"] = t["line"].replace("Persistance :", "Persistance : (+ `sous_chaines_par_module` PositiveSmallIntegerField nul, ACAL720 ; `var_bus_dc_redresse_v` DecimalField 6,1 nul, ACAL816) ;", 1)
log("EDIT 660 : une migration pour 659 + 720 + 816")
# 510 : après le contrat 573 ; 824 : après 822 ; 861 : après 922 ; 674 : après 604
ADD_AFTER = {"ACAL510": ["ACAL573"], "ACAL511": ["ACAL573"], "ACAL824": ["ACAL822"], "ACAL861": ["ACAL922"], "ACAL674": ["ACAL604"], "ACAL858": ["ACAL934"]}

# ---- 4. @after : remap, même plan, existants ----
def plan_of(i):
    if i in byid: return byid[i]["plan"], ("gated" if byid[i]["sec"] == SEC_G else "")
    v = IDX.get(i)
    return (v[1], v[0]) if v else (None, None)
AFT = re.compile(r" ?\(@after: ([^)]*)\)")
for t in tasks:
    s = t["line"]
    ms = list(AFT.finditer(s))
    ids = []
    for m in ms: ids += [x.strip() for x in re.split(r"[,\s]+", m.group(1)) if x.strip()]
    for m in reversed(ms): s = s[:m.start()] + s[m.end():]
    ids += ADD_AFTER.get(t["id"], [])
    garde, phrases = [], []
    for d in ids:
        if not re.fullmatch(r"[A-Z]+\d+[a-z]?", d): log("!! @after illisible", t["id"], d); continue
        if d in REMAP:
            nd = REMAP[d]; log("REMAP @after", t["id"], d, "->", nd)
            if nd is None: continue
            d = nd
        if d == t["id"] or d in garde: continue
        p, st = plan_of(d)
        if p is None: log("?? @after inconnu", t["id"], d); continue
        st = (st or "").lower()
        if st.startswith("x"): log("drop @after coché", t["id"], d); continue
        if st.startswith("blocked") and "code livr" in st:
            phrases.append(f"s'appuie sur {d} (code livré, preuve en direct due à ACAL490)"); continue
        if p != t["plan"]:
            phrases.append(f"ordre : après {d} de {p}"); log("XPLAN @after -> phrase", t["id"], d, p); continue
        if st.startswith("gated") or st.startswith("blocked") or st == "gated":
            log("!! @after vers une tâche GATED/BLOCKED du même plan", t["id"], d, st[:40])
        garde.append(d)
    if phrases:
        txt = " ; ".join(phrases)
        k = s.find(")) — ")
        if k > 0 and k < 400: s = s[:k + 5] + txt + " ; " + s[k + 5:]
        else: s = s.replace("Constat : ", "Constat : (" + txt + ") ", 1)
    if garde:
        mm = re.search(r" \(@lane:", s) or re.search(r" \(@model:", s)
        tag = f" (@after: {', '.join(garde)})"
        s = s[:mm.start()] + tag + s[mm.start():] if mm else s + tag
    t["line"] = s

# ---- 5. migrations : numéro jamais choisi ----
PH = "numéro de migration à relire sur origin/main à la construction"
for t in tasks:
    s = t["line"]
    for m in set(re.findall(r"(backend/django_core/apps/\w+/migrations/)(0\d{3})(_[a-z0-9_]+\.py)", s)):
        full = "".join(m)
        if os.path.exists(os.path.join(ROOT, full)): continue
        s = s.replace(full, m[0] + "0NNN" + m[2]); log("MIG 0NNN", t["id"], m[1] + m[2])
        s = re.sub(r"\b" + m[1] + m[2].replace(".py", "") + r"\b", "0NNN" + m[2].replace(".py", ""), s)
    for pat in (r"\(numéro libre à la construction, attendu 0\d{3}\)", r"attendu 0\d{3}", r"migration suivante \(0\d{3}[^)]*\)"):
        s2 = re.sub(pat, PH, s)
        if s2 != s: log("MIG prose", t["id"], pat); s = s2
    if "migrations/0NNN" in s and PH not in s:
        s = s.replace("Persistance : ", "Persistance : (" + PH + ") ", 1)
    t["line"] = s

# ---- 6. lanes des fichiers mono-écrivain ----
LANES = [("apps/web/src/scripts/roof-tool-pro11.ts", "calepinage/atelier-web"), ("apps/web/src/scripts/roofPro11/prefill.ts", "calepinage/atelier-web"),
         ("frontend/src/pages/ventes/ToitureDesign.jsx", "calepinage/atelier-erp"), ("frontend/src/features/calepinage/BuilderDom.jsx", "calepinage/atelier-erp"),
         ("frontend/src/features/calepinage/atelier/BuilderDom.jsx", "calepinage/atelier-erp"),
         ("backend/django_core/apps/calepinage/services/planche.py", "calepinage/livrables"),
         ("backend/django_core/apps/calepinage/services/chaine_pertes.py", "calepinage/simulation"),
         ("backend/django_core/apps/calepinage/contract_samples/calepinage_resultat.json", "calepinage/simulation"),
         ("backend/django_core/apps/calepinage/contract_samples/roof_layout_v2.schema.json", "calepinage/contrats"),
         ("frontend/src/features/calepinage/production/PanneauProduction.jsx", "calepinage/resultats")]
for t in tasks:
    if t["plan"] != CAL: continue
    files = re.findall(r"`([^`]+)`", t["line"].rsplit("Files:", 1)[-1])
    for f, lane in LANES:
        if f in files:
            old = re.search(r"\(@lane: ([^)]+)\)", t["line"])
            if old and old.group(1) != lane:
                t["line"] = t["line"].replace(old.group(0), f"(@lane: {lane})"); log("LANE", t["id"], old.group(1), "->", lane)
            elif not old:
                t["line"] = t["line"].replace(" (@model:", f" (@lane: {lane}) (@model:", 1); log("LANE+", t["id"], lane)
            break

# ---- 6b. mentions périmées « GATED » des tâches dégelées ----
DEG = "ACAL(?:973|968|927|697|895|896|897)"
for t in tasks:
    s0 = t["line"]
    s1 = re.sub(r"(" + DEG + r"),? GATED (D-ACAL-3\d)", lambda m: m.group(1) + ", " + m.group(2), s0)
    s1 = re.sub(r"(" + DEG + r"),? GATED\)", lambda m: m.group(1) + ")", s1)
    s1 = re.sub(r"GATED (" + DEG + r")", lambda m: m.group(1), s1)
    s1 = s1.replace("ACAL899 GATED)", "ACAL899, retirée : D-ACAL-42)")
    if s1 != s0: log("GATED périmé retiré", t["id"]); t["line"] = s1

# ---- 6c. garde de câblage (clause d'atteignabilité) et ACAL901 / ACAL1030 ----
ATT = {"ACAL617", "ACAL700", "ACAL709", "ACAL781", "ACAL784", "ACAL561", "ACAL572", "ACAL600", "ACAL631", "ACAL685",
       "ACAL698", "ACAL737", "ACAL748", "ACAL750", "ACAL762", "ACAL872", "ACAL589", "ACAL668"}
for t in tasks:
    if t["id"] in ATT and "ATTEIGNABLE" not in t["line"]:
        phr = (" Et l'écran est ATTEIGNABLE : composant partagé, monté par les écrans du module qui l'emploient (onglet monté dans son écran parent), aucune route propre."
               if t["id"] == "ACAL872" else
               " Et l'écran est ATTEIGNABLE : le composant neuf est monté dans son écran parent nommé dans `Files:` (onglet monté dans son écran parent), sans route propre.")
        t["line"] = t["line"].replace(" Persistance :", phr + " Persistance :", 1); log("ATTEIGNABLE", t["id"])
        if t["id"] == "ACAL872":
            t["line"] = t["line"].replace(" (ROUTINE)", ", `frontend/src/features/calepinage/module.config.jsx` (ROUTINE)", 1)
t = byid["ACAL901"]
old = "`backend/django_core/apps/ventes/tests/test_selectors_surface.py`"
t["line"] = t["line"].replace(old, "`backend/django_core/apps/calepinage/tests/test_compatibilite_materiel_servie.py`")
t["line"] = t["line"].replace("Constat : C-ACAL-L5-901 (", "Constat : (la surface figée des sélecteurs de ventes est réalignée par ACAL1030 de docs/plans/PLAN_AUDIT_DEVIS.md, dans le même merge) C-ACAL-L5-901 (", 1)
t["line"] = t["line"].replace("(nouveau cas « incompatible", "(Nouveau fichier car : aucun test du propriétaire calepinage n'exerce `selectors_calepinage.py`, la surface figée appartient à devis ; cas « incompatible", 1)
t["line"] = re.sub(r"\(@lane: [^)]+\)", "(@lane: calepinage/selecteurs-ventes)", t["line"])
log("ACAL901 -> test calepinage + moitié ACAL1030")
N1030 = ("- [ ] ACAL1030 — **Ajouter à la surface figée des sélecteurs de ventes la fonction de compatibilité du matériel posée par ACAL901 dans `selectors_calepinage.py` ; fini quand la surface la liste et qu'un nom public de plus non déclaré fait toujours échouer le test** : "
 "Constat : C-ACAL-L5-1030 (C15, S3, STATIQUE (lecture du 21/11 sur 207c7a70e)) — ordre : même merge qu'ACAL901 de docs/plans/PLAN_AUDIT_CALEPINAGE.md ; moitié devis de la fiche CAP-D6-14 : `backend/django_core/apps/ventes/tests/test_selectors_surface.py` fige les noms publics de `selectors_calepinage.py` (SPL144, 11 fonctions + 2 constantes) ; ACAL901 en ajoute une et casserait ce pin sans cette moitié ; Priorité : P2. "
 "Given la surface figée de `selectors_calepinage.py` When ACAL901 ajoute sa fonction publique Then la liste du test gagne ce nom et lui seul ; un autre nom public ajouté sans déclaration échoue comme avant. Persistance : n/a — test de surface. Emplacement : `test_selectors_surface.py` (liste SPL144, 1 l.). Code net : lignes nettes ≤ 2. Appelants : n/a — test. Assertions existantes : `backend/django_core/apps/ventes/tests/test_selectors_surface.py` (à réaligner, un nom). Jumeaux : les surfaces SPL143-147 des autres modules de sélecteurs (inchangées). Listes figées : la liste SPL144. Contrat partagé : n/a — nom de fonction Python. "
 "Test rouge d'abord : `backend/django_core/apps/ventes/tests/test_selectors_surface.py` (la fonction d'ACAL901 présente et non déclarée ⇒ échec ; déclarée ⇒ vert) ; mutant : retirer le nom de la liste ⇒ échec. Preuve en direct : n/a — garde de surface. Hors périmètre : la fonction elle-même (ACAL901). (gen manuel 207c7a7) Files: `backend/django_core/apps/ventes/tests/test_selectors_surface.py` (ROUTINE) (@lane: devis/selectors) (@model: haiku)")
nt = dict(id="ACAL1030", domain="D6", plan="docs/plans/PLAN_AUDIT_DEVIS.md", sec=SEC_M2, line=N1030)
tasks.append(nt); byid["ACAL1030"] = nt; log("AJOUT ACAL1030 (moitié devis d'ACAL901)")

# ---- 7. écriture ----
def emit(domain):
    main = [t for t in tasks if t["domain"] == domain and t["plan"] == CAL]
    autres = [t for t in tasks if t["domain"] == domain and t["plan"] != CAL]
    out = []
    for sec in (SEC_M1, SEC_M2, SEC_G):
        out.append(f"### ACAL — {sec}\n")
        out += [t["line"] + "\n" for t in main if t["sec"] == sec]
    open(os.path.join(L, f"lot-{domain}.md"), "w", encoding="utf-8", newline="\n").write("\n".join(out))
    out = [f"# Lot {domain} — tâches d'un autre propriétaire que calepinage (vague 2, réconcilié)\n"]
    for plan in sorted({t["plan"] for t in autres}):
        out.append(f"## → {plan}\n")
        for sec in (SEC_M1, SEC_M2, SEC_G):
            sel = [t for t in autres if t["plan"] == plan and t["sec"] == sec]
            if sel: out.append(f"### ACAL — {sec}\n"); out += [t["line"] + "\n" for t in sel]
    open(os.path.join(L, f"lot-{domain}-autres-plans.md"), "w", encoding="utf-8", newline="\n").write("\n".join(out))
for d in [f"D{n}" for n in range(1, 9)]: emit(d)
json.dump([{k: t[k] for k in ("id", "domain", "plan", "sec")} | {"prio": prio(t["line"])} for t in tasks],
          open(os.path.join(H, "final_index.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0)
json.dump(DEL, open(os.path.join(H, "deleted.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
open(os.path.join(H, "reconcile.log"), "w", encoding="utf-8").write("\n".join(LOG))
from collections import Counter
print(len(tasks), Counter((t["plan"].split("/")[-1], t["sec"][:5]) for t in tasks))
print("\n".join(l for l in LOG if l.startswith("!!") or l.startswith("??")))

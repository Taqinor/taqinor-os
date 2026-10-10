#!/usr/bin/env python3
"""OWN (02/10/2026) — chaque fichier a UN propriétaire ; chaque tâche reste chez le sien.

POURQUOI CETTE GARDE EXISTE
---------------------------
Plusieurs sessions « work on the plan <x> » tournent en parallèle, une par
fichier plan. Elles ne se marchent jamais dessus SI ET SEULEMENT SI chaque
fichier du dépôt a exactement UN propriétaire, et si chaque tâche d'un plan ne
touche que les fichiers du propriétaire de ce plan. Rien de tout cela n'était
écrit : la construction QJR5 (30/09/2026) a dû faire passer 155 de ses 159
tâches dans UNE lane série, parce que DevisGenerator.jsx, views/devis.py,
solar.js, builder.py, crm/views.py… étaient édités par tous les parcours.

Le registre est une DONNÉE : ``docs/ownership.yml`` (propriétaires, globs,
surfaces append-only, liaison plan → propriétaire). Cette garde le vérifie ;
``scripts/plan_lanes.py`` le lit pour la disjonction des lanes.

LES QUATRE RÈGLES
-----------------
(a) **Exactement un propriétaire.** Chaque fichier suivi sous les ``roots`` est
    revendiqué par UN propriétaire. Résolution à deux étages : un glob ``paths``
    (revendication précise, STRICTE : deux propriétaires = refus) l'emporte ; à
    défaut, les globs ``fallback`` (résiduels d'un sous-arbre) départagés par le
    plus long préfixe littéral — « fichier > dossier > résiduel », la règle de
    docs/audits/unites.yml ; égalité entre deux propriétaires = refus. Aucun
    propriétaire = refus.
    Un glob ne peut pas s'ouvrir directement sur un ``container`` (``apps/*``,
    ``features/**``…) : un module NEUF doit être déclaré, pas avalé.
(b) **Une tâche reste chez son propriétaire.** Une tâche ouverte et
    constructible d'un plan ne déclare (``Files:``) que des fichiers du (des)
    propriétaire(s) de ce plan. Exemptés : les plans des propriétaires listés
    dans ``exempt`` (transverse, plateforme, parqué) et les surfaces
    ``append_only``. Une tâche multi-propriétaires va dans le plan
    ``transverse``, qui ne tourne jamais en parallèle d'un plan qui chevauche.
(c) **Pas de fichier neuf sans propriétaire.** Un fichier déclaré par une tâche
    (même pas encore créé) ou ajouté par une branche (``--base``) doit déjà
    avoir un propriétaire au registre.
(d) **Transverse = déplacements atomiques seulement** (AMET96). Une tâche du
    plan transverse porte `(@atomique: <propriétaires>)` égal EXACTEMENT aux
    propriétaires de ses `Files:` ; sinon « à scinder, contrat d'abord ».
    Mode RAPPORT (code 0) tant que ``--bloquant`` n'est pas passé (AMET101).

Pur stdlib : le job ``stage-names`` n'installe pas PyYAML ; le registre est
écrit dans le sous-ensemble YAML lu par ``plan_lanes._MiniYamlParser``.

Usage
-----
    python scripts/check_ownership.py               # règles (a) (b) (c), code 1 si refus
    python scripts/check_ownership.py --base origin/main   # + fichiers ajoutés par la branche
    python scripts/check_ownership.py --stats       # fichiers et lignes par propriétaire
    python scripts/check_ownership.py --owner-of frontend/src/pages/ventes/DevisGenerator.jsx
    python scripts/check_ownership.py --conflits 40   # la mesure de l'étape 1, rejouable (~2 min)
"""
from __future__ import annotations

import argparse
import ast
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTRE = ROOT / "docs" / "ownership.yml"
PARKED_PY = Path("backend") / "django_core" / "core" / "parked.py"

if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))
import plan_lanes as PL  # noqa: E402  (grammaire des tâches + mini-YAML)

#: Fichiers plan scannés par la règle (b) — tout fichier plan du dépôt.
PLAN_GLOBS = (
    "docs/PLAN*.md", "docs/plans/PLAN_*.md", "docs/ERROR_PLAN.md",
    "docs/WEB_PLAN.md", "docs/WEB_ERROR_PLAN.md", "docs/new_tasks_plan.md",
    "docs/FRONTEND_GAP_PLAN.md", "docs/backlog/*PLAN*.md",
)
PLAN_EXCLUS = {"docs/PLAN_HOWTO.md"}

#: Dossiers de premier niveau de frontend/src qu'un chemin court peut citer.
_FRONT_TOP = ("features/", "pages/", "api/", "components/", "ui/", "lib/",
              "hooks/", "router/", "providers/", "i18n/", "design/",
              "styles/", "utils/", "store/", "test/")
_WEB_TOP = ("src/", "public/", "worker/", "tests/")
_NOM_PROPRIETAIRE = re.compile(r"^[a-z][a-z0-9_-]*$")


# --------------------------------------------------------------------------- globs
def compiler_glob(glob: str) -> re.Pattern:
    """``**`` = n'importe quelle profondeur (zéro comprise), ``*`` = un segment."""
    i, out = 0, []
    while i < len(glob):
        if glob.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif glob.startswith("**", i):
            out.append(".*")
            i += 2
        elif glob[i] == "*":
            out.append("[^/]*")
            i += 1
        elif glob[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(glob[i]))
            i += 1
    return re.compile("".join(out))


def _prefixe_litteral(glob: str) -> str:
    m = re.search(r"[*?]", glob)
    return glob if m is None else glob[:m.start()]


def _specificite(glob: str) -> int:
    """Nombre de caractères littéraux (hors jokers) : « fichier > dossier > résiduel »."""
    return len(re.sub(r"[*?]", "", glob))


def normaliser(brut: str, web: bool = False) -> str | None:
    """Chemin déclaré dans une tâche → chemin du dépôt (``None`` si inexploitable).

    Les plans abrègent : ``apps/crm/views.py`` (= backend/django_core/apps/…),
    ``core/events.py``, ``features/crm/stages.js`` (= frontend/src/…). Un nom
    nu (``views.py``) est ambigu : ignoré. ``web=True`` (plan du site) lit
    ``src/…`` comme ``apps/web/src/…``. ``apps/yanbow-web/…`` (second site
    public, hors Django) reste tel quel, comme ``apps/web/…``.
    """
    p = brut.strip().replace("\\", "/").strip("`'\"() ,;")
    while p.startswith("./"):
        p = p[2:]
    if not p or "/" not in p or any(c in p for c in "<>{}"):
        return None
    if p.startswith(("backend/", "frontend/", "apps/web/", "apps/yanbow-web/")):
        return p
    if p.startswith("django_core/"):
        return "backend/" + p
    if p.startswith(("apps/", "core/")):
        return "backend/django_core/" + p
    if web and p.startswith(_WEB_TOP):
        return "apps/web/" + p
    if p.startswith("src/"):
        return "frontend/" + p
    if p.startswith(_FRONT_TOP):
        return "frontend/src/" + p
    return p


# --------------------------------------------------------------------- registre
def _liste(v) -> list:
    if v in (None, "", {}):
        return []
    return list(v) if isinstance(v, list) else [v]


def _vrai(v) -> bool:
    return v is True or str(v).strip().lower() in {"true", "yes", "oui", "1"}


def _apps_parquees(racine: Path) -> list[str]:
    """Lit ``APPS_PARQUEES`` dans core/parked.py SANS l'importer (source unique)."""
    chemin = racine / PARKED_PY
    if not chemin.is_file():
        return []
    arbre = ast.parse(chemin.read_text(encoding="utf-8"))
    for noeud in arbre.body:
        if isinstance(noeud, ast.Assign) and any(
                isinstance(c, ast.Name) and c.id == "APPS_PARQUEES"
                for c in noeud.targets):
            return [str(x) for x in ast.literal_eval(noeud.value)]
    return []


class Registre:
    """Le contenu de ``docs/ownership.yml``, compilé pour la résolution."""

    def __init__(self, data: dict, racine: Path, texte: str = ""):
        self.racine = racine
        self.texte = texte
        self.roots = tuple(_liste(data.get("roots")))
        self.containers = tuple(_liste(data.get("containers")))
        self.exempt = set(_liste(data.get("exempt")))
        self.owners: dict[str, dict] = {}
        for nom, o in (data.get("owners") or {}).items():
            o = o if isinstance(o, dict) else {}
            paths = [str(g) for g in _liste(o.get("paths"))]
            if _vrai(o.get("paths_from_parked_registry")):
                paths += [f"backend/django_core/apps/{a}/**"
                          for a in _apps_parquees(racine)]
            self.owners[str(nom)] = {
                **o,
                "paths": paths,
                "fallback": [str(g) for g in _liste(o.get("fallback"))],
            }
        self.append_only = [s for s in _liste(data.get("append_only"))
                            if isinstance(s, dict) and s.get("path")]
        self.plans: dict[str, list[str]] = {
            str(k): [str(x) for x in _liste(v)]
            for k, v in (data.get("plans") or {}).items()}
        # Règles compilées : (étage, propriétaire, glob, regex, préfixe littéral)
        self._regles = {"paths": [], "fallback": []}
        for nom, o in self.owners.items():
            for etage in ("paths", "fallback"):
                for g in o[etage]:
                    self._regles[etage].append(
                        (nom, g, compiler_glob(g), _prefixe_litteral(g)))
        self._ao = [(str(s["path"]), compiler_glob(str(s["path"])))
                    for s in self.append_only]

    # -- résolution
    def sous_racines(self, chemin: str) -> bool:
        return chemin.startswith(self.roots)

    def resoudre(self, chemin: str) -> list[str]:
        """Propriétaires qui revendiquent ``chemin`` à l'étage décisif.

        ``paths`` est STRICT : deux propriétaires qui y revendiquent le même
        fichier = refus. ``fallback`` résout les résiduels imbriqués
        (``ventes/**`` ⊃ ``ventes/quote_engine/**`` ; ``ventes/**`` vs
        ``ventes/*_facturation.py``) : le glob qui porte le PLUS de caractères
        littéraux gagne ; une égalité entre deux propriétaires = refus.
        """
        hits = sorted({nom for nom, _, rx, lit in self._regles["paths"]
                       if chemin.startswith(lit) and rx.fullmatch(chemin)})
        if hits:
            return hits
        meilleurs: dict[str, int] = {}
        for nom, glob, rx, lit in self._regles["fallback"]:
            if chemin.startswith(lit) and rx.fullmatch(chemin):
                meilleurs[nom] = max(meilleurs.get(nom, -1), _specificite(glob))
        if not meilleurs:
            return []
        top = max(meilleurs.values())
        return sorted(nom for nom, n in meilleurs.items() if n == top)

    def est_append_only(self, chemin: str) -> bool:
        return any(rx.fullmatch(chemin) for _, rx in self._ao)

    def proprietaires_du_plan(self, plan: str) -> list[str] | None:
        if plan in self.plans:
            return self.plans[plan]
        lies = [nom for nom, o in self.owners.items() if o.get("plan") == plan]
        return lies or None

    @property
    def plan_transverse(self) -> str:
        return str(self.owners.get("transverse", {}).get(
            "plan", "docs/plans/PLAN_TRANSVERSE.md"))


def charger_registre(chemin: Path = REGISTRE, texte: str | None = None,
                     racine: Path = ROOT) -> Registre:
    if texte is None:
        texte = Path(chemin).read_text(encoding="utf-8")
    return Registre(PL._MiniYamlParser(texte).parse(), racine, texte)


def _cles_dupliquees(texte: str) -> list[str]:
    """Le mini-YAML garde le DERNIER bloc d'une clé répétée, sans rien dire
    (critique finale OWN, F5) : on relit le texte pour les repérer."""
    vues, doublons, bloc = set(), [], None
    for ligne in texte.splitlines():
        if not ligne.strip() or ligne.lstrip().startswith("#"):
            continue
        m0 = re.match(r"^([A-Za-z_][\w-]*):", ligne)
        if m0:
            cle = m0.group(1)
            if cle in vues:
                doublons.append(cle)
            vues.add(cle)
            bloc = cle
            continue
        m2 = re.match(r"^  ([A-Za-z_][\w./-]*):", ligne)
        if m2 and bloc in ("owners", "plans"):
            cle = f"{bloc}.{m2.group(1)}"
            if cle in vues:
                doublons.append(cle)
            vues.add(cle)
    return doublons


def proprietaire(reg: Registre, chemin: str) -> str | None:
    hits = reg.resoudre(chemin)
    return hits[0] if len(hits) == 1 else None


# ----------------------------------------------------------------------- règles
def verifier_fichiers(reg: Registre, fichiers) -> list[str]:
    """Règle (a) : chaque fichier sous les racines a exactement un propriétaire."""
    erreurs = []
    for f in fichiers:
        if not reg.sous_racines(f):
            continue
        hits = reg.resoudre(f)
        if not hits:
            erreurs.append(
                f"fichier sans propriétaire : {f} — le revendiquer (paths/"
                f"fallback d'un propriétaire) dans docs/ownership.yml")
        elif len(hits) > 1:
            erreurs.append(
                f"fichier à deux propriétaires : {f} ({', '.join(hits)}) — "
                f"un seul doit le revendiquer dans docs/ownership.yml")
    return erreurs


def verifier_nouveaux(reg: Registre, ajoutes) -> list[str]:
    """Règle (c) : un fichier AJOUTÉ par la branche doit avoir un propriétaire."""
    return [
        f"nouveau fichier sans propriétaire : {f} — le déclarer dans "
        f"docs/ownership.yml dans le même commit"
        for f in ajoutes if reg.sous_racines(f) and not reg.resoudre(f)]


def verifier_registre(reg: Registre, fichiers=()) -> tuple[list[str], list[str]]:
    """Cohérence du registre lui-même (erreurs, avertissements)."""
    erreurs, avert = [], []
    vus: dict[str, str] = {}
    for nom, o in reg.owners.items():
        if not _NOM_PROPRIETAIRE.match(nom):
            erreurs.append(f"propriétaire « {nom} » : nom invalide ([a-z0-9_-])")
        plan = o.get("plan")
        if not plan:
            erreurs.append(f"propriétaire « {nom} » : aucun `plan:` déclaré")
        elif plan in vus:
            erreurs.append(f"le plan {plan} est déclaré par deux propriétaires "
                           f"(« {vus[plan]} » et « {nom} »)")
        else:
            vus[str(plan)] = nom
        for etage in ("paths", "fallback"):
            for g in o[etage]:
                lit = _prefixe_litteral(g)
                if lit != g and lit.endswith("/") and lit in reg.containers:
                    erreurs.append(
                        f"glob trop large pour « {nom} » : {g} — il s'ouvre sur "
                        f"le conteneur {lit} et avalerait d'office un module "
                        f"neuf (règle c) ; nommer le sous-dossier")
    for cle in _cles_dupliquees(reg.texte):
        erreurs.append(f"clé déclarée deux fois dans docs/ownership.yml : {cle} "
                       f"(le second bloc écraserait le premier sans bruit)")
    if "transverse" not in reg.owners:
        erreurs.append("propriétaire « transverse » absent du registre")
    elif reg.owners["transverse"]["paths"] or reg.owners["transverse"]["fallback"]:
        erreurs.append("« transverse » ne possède aucun fichier (multi-"
                       "propriétaires seulement) : retirer ses globs")
    for nom in sorted(reg.exempt - set(reg.owners)):
        erreurs.append(f"exempt : propriétaire inconnu « {nom} »")
    for plan, owners in sorted(reg.plans.items()):
        for nom in owners:
            if nom not in reg.owners:
                erreurs.append(f"plans : {plan} lié à un propriétaire inconnu « {nom} »")
    if fichiers:
        fichiers = [f for f in fichiers if reg.sous_racines(f)]
        for etage in ("paths", "fallback"):
            for nom, g, rx, lit in reg._regles[etage]:
                if not any(f.startswith(lit) and rx.fullmatch(f) for f in fichiers):
                    avert.append(f"glob mort ({nom}, {etage}) : {g} ne couvre aucun fichier")
    return erreurs, avert


# `(?<!@)` : `(@files: …)` est une balise de LANE (plan_lanes), pas la clause.
_FILES_MARQUEUR = re.compile(r"(?i)(?<!@)\b(?:files|fichiers)\s*:")
_SEGMENT_CODE = re.compile(r"`([^`]+)`")
#: chemin nu (sans backticks) : toute extension, bornée pour ne pas couper
#: `.json` en `.js` (critique finale OWN, F1).
_CHEMIN_NU = re.compile(r"[\w./\\[\]{},*-]+\.[A-Za-z0-9]{1,8}(?![\w])")
_REF_LIGNE = re.compile(r":\d+(?:-\d+)?$")


def _accolades(chemin: str) -> list[str]:
    m = re.search(r"\{([^{}]*)\}", chemin)
    if not m:
        return [chemin]
    out = []
    for alt in m.group(1).split(","):
        out += _accolades(chemin[:m.start()] + alt.strip() + chemin[m.end():])
    return out


def chemins_declares(label: str) -> list[str]:
    """Chemins de la clause `Files:` (ou `Fichiers :`) d'une tâche, tels qu'écrits.

    Lit les segments entre backticks (ou, à défaut, les chemins nus), quelle que
    soit l'extension (.astro, .json, .scss…), développe les accolades, ramène
    les antislashs à `/`, retire une référence de ligne `:120-140`. Garde les
    globs (`*`) et les dossiers (`…/`) : la vérification les développe.
    """
    idx = [m.start() for m in _FILES_MARQUEUR.finditer(label)]
    if not idx:
        return []
    queue = label[idx[-1]:]
    bruts = _SEGMENT_CODE.findall(queue) or _CHEMIN_NU.findall(queue)
    out: list[str] = []
    for brut in bruts:
        for morceau in re.split(r",\s+|\s+", brut.strip()):
            morceau = _REF_LIGNE.sub("", morceau.strip().replace("\\", "/").strip("'\"()"))
            for c in _accolades(morceau):
                if "/" in c and (re.search(r"\.[A-Za-z0-9]{1,8}$", c) or c.endswith("/")
                                 or "*" in c):
                    if c not in out:
                        out.append(c)
    return out


def _cibles(reg: "Registre", chemin: str, fichiers) -> list[str]:
    """Un glob ou un dossier déclaré → les fichiers qu'il désigne (ou un
    représentant fictif s'il n'en désigne encore aucun)."""
    if chemin.endswith("/"):
        chemin += "**"
    if "*" not in chemin:
        return [chemin]
    rx = compiler_glob(chemin)
    lit = _prefixe_litteral(chemin)
    hits = [f for f in fichiers if f.startswith(lit) and rx.fullmatch(f)]
    return hits or [re.sub(r"\*+", "x", chemin)]


def _taches_ouvertes(texte: str):
    """(n° de ligne, id, label + continuations) de chaque tâche OUVERTE de la
    file d'un plan ; id ``None`` = ligne de case `- [ ]` mal formée portant
    `Files:`. Une tâche = sa ligne + ses lignes de continuation (indentées)."""
    lignes = texte.splitlines()
    hors_file = False
    for i, brut in enumerate(lignes):
        if brut.startswith(("# ", "## ", "### ")):
            hors_file = bool(PL._NON_QUEUE_SECTION.match(brut))
            continue
        if hors_file:
            continue
        m = PL._TASK_LIST_RE.match(brut) or PL._TASK_HEADER_RE.match(brut)
        if not m:
            if PL._RAW_CHECKLIST_RE.match(brut) and brut.lstrip().startswith("- [ ]") \
                    and _FILES_MARQUEUR.search(brut):
                yield i + 1, None, ""
            continue
        statut = (m.group("status") or "").strip()
        en_ligne = (m.groupdict().get("inline_status") or "").strip()
        if en_ligne:
            statut = en_ligne
        if statut:
            continue  # [x], [BLOCKED…], [GATED…] : rien à construire
        label = m.group("label")
        j = i + 1
        while j < len(lignes) and lignes[j][:1] in (" ", "\t") \
                and not lignes[j].lstrip().startswith("- ["):
            label += " " + lignes[j].strip()
            j += 1
        yield i + 1, m.group("id"), label


def verifier_plans(reg: Registre, plans: dict[str, str], fichiers=()) -> list[str]:
    """Règle (b) (+ (a)/(c) au moment où la tâche est écrite).

    Une ligne de case à cocher qui porte `Files:` sans être lisible comme
    tâche est REFUSÉE (elle échapperait sinon à toute vérification).
    """
    fichiers = list(fichiers)
    erreurs = []
    for plan, texte in sorted(plans.items()):
        owners = reg.proprietaires_du_plan(plan)
        if owners is None:
            erreurs.append(
                f"{plan} : aucun propriétaire ne lie ce plan — le déclarer "
                f"(owners.<x>.plan ou plans:) dans docs/ownership.yml")
            continue
        if "parked" in owners:
            continue  # files parquées : hors périmètre du MVP, jamais drainées
        # Plans exemptés (transverse, files historiques) : seulement de la règle
        # (b). Un fichier qu'ils déclarent doit quand même avoir UN propriétaire.
        exempte = bool(set(owners) & reg.exempt)
        web = owners == ["web"]
        for n_ligne, tid, label in _taches_ouvertes(texte):
            if tid is None:
                erreurs.append(
                    f"{plan}:{n_ligne} — ligne de tâche mal formée (attendu « - [ ] "
                    f"<ID> — … », tiret cadratin) : ses Files: échapperaient à la "
                    f"garde ; la corriger")
                continue
            for declare in chemins_declares(label):
                chemin = normaliser(declare, web=web)
                if not chemin or not reg.sous_racines(chemin):
                    continue
                for cible in _cibles(reg, chemin, fichiers):
                    if reg.est_append_only(cible):
                        continue
                    hits = reg.resoudre(cible)
                    if not hits:
                        erreurs.append(
                            f"{plan}:{n_ligne} {tid} — `{cible}` est sans propriétaire "
                            f"(fichier neuf ?) : le déclarer dans docs/ownership.yml")
                    elif len(hits) > 1:
                        erreurs.append(
                            f"{plan}:{n_ligne} {tid} — `{cible}` a deux propriétaires "
                            f"({', '.join(hits)}) : corriger docs/ownership.yml")
                    elif hits[0] not in owners and not exempte:
                        erreurs.append(
                            f"{plan}:{n_ligne} {tid} — `{cible}` appartient à "
                            f"« {hits[0]} », pas à « {'/'.join(owners)} » : une tâche "
                            f"multi-propriétaires va dans {reg.plan_transverse} "
                            f"(ou retirer ce fichier de Files:)")
    return erreurs


def verifier_transverse(reg: Registre, plans: dict[str, str], fichiers=()) -> list[str]:
    """Règle (d) (AMET96) : le plan transverse n'accepte qu'une tâche
    `(@atomique: <propriétaires>)` dont le tag égale EXACTEMENT les
    propriétaires (règle a) de ses `Files:`, surfaces append-only exclues."""
    plan = reg.plan_transverse
    fichiers = list(fichiers)
    refus = []
    for n_ligne, tid, label in _taches_ouvertes(plans.get(plan, "")):
        if tid is None:
            continue  # déjà refusée par la règle (b)
        tag = PL.proprietaires_atomiques(label)
        reels = set()
        for declare in chemins_declares(label):
            chemin = normaliser(declare)
            if chemin and reg.sous_racines(chemin):
                reels |= {proprietaire(reg, c) for c in _cibles(reg, chemin, fichiers)
                          if not reg.est_append_only(c)} - {None}
        if tag is None:
            refus.append(
                f"{plan}:{n_ligne} {tid} — tâche multi-propriétaires : à scinder, "
                f"contrat d'abord (une par propriétaire, contract_samples/ "
                f"d'abord) — ou `(@atomique: {', '.join(sorted(reels))})` si "
                f"c'est un déplacement construit en UN commit")
        elif tag != reels:
            refus.append(
                f"{plan}:{n_ligne} {tid} — `@atomique: {', '.join(sorted(tag))}` "
                f"≠ propriétaires de ses Files: {', '.join(sorted(reels))} — "
                f"le tag doit les nommer EXACTEMENT")
    return refus


# ------------------------------------------------------------- mesure (brief 1)
def classer_conflits(reg: Registre, taches: dict, commits: list, lignes: dict) -> list[dict]:
    """Classe les fichiers par coût de conflit = tâches × propriétaires × lignes.

    ``taches`` : id → {prefixe, fichiers} ; ``commits`` : [(ids cités, fichiers)] ;
    ``lignes`` : fichier → nombre de lignes. Le PARCOURS d'une tâche est le
    propriétaire majoritaire de ses fichiers (hors surfaces append-only) ; celui
    d'un groupe (préfixe d'ID) est le parcours majoritaire de ses tâches. Les
    « propriétaires » d'un fichier = les parcours des tâches et des commits qui
    l'ont touché : deux ou plus = fichier PARTAGÉ.
    """
    def parcours_tache(fichiers):
        compte: dict[str, int] = {}
        for f in fichiers:
            if reg.est_append_only(f):
                continue
            o = proprietaire(reg, f)
            if o and o != "parked":
                compte[o] = compte.get(o, 0) + 1
        return min(compte, key=lambda o: (-compte[o], o)) if compte else None

    par_groupe: dict[str, dict[str, int]] = {}
    for t in taches.values():
        p = parcours_tache(t["fichiers"])
        if p:
            g = par_groupe.setdefault(t["prefixe"], {})
            g[p] = g.get(p, 0) + 1
    parcours_groupe = {g: min(c, key=lambda o: (-c[o], o)) for g, c in par_groupe.items()}

    stats: dict[str, dict] = {}
    for tid, t in taches.items():
        p = parcours_groupe.get(t["prefixe"])
        for f in t["fichiers"]:
            s = stats.setdefault(f, {"taches": set(), "parcours": set(), "commits": 0})
            s["taches"].add(tid)
            if p:
                s["parcours"].add(p)
    for ids, fichiers in commits:
        ps = {parcours_groupe.get(taches[i]["prefixe"]) for i in ids if i in taches} - {None}
        for f in fichiers:
            s = stats.setdefault(f, {"taches": set(), "parcours": set(), "commits": 0})
            s["commits"] += 1
            s["parcours"] |= ps
    out = []
    for f, s in stats.items():
        if f not in lignes:
            continue  # fichier disparu depuis
        n = len(s["taches"])
        out.append({"fichier": f, "proprietaire": proprietaire(reg, f),
                    "append_only": reg.est_append_only(f), "lignes": lignes[f],
                    "taches": n, "commits": s["commits"], "parcours": sorted(s["parcours"]),
                    "cout": n * max(1, len(s["parcours"])) * max(1, lignes[f])})
    out.sort(key=lambda r: (-r["cout"], r["fichier"]))
    return out


def mesurer_conflits(reg: Registre, n_commits: int = 2000, top: int = 40) -> str:
    """La mesure de l'étape 1, rejouable : plans actuels ET tâches archivées
    (instantané de chaque fichier plan juste avant chaque « clean the plans »),
    ``n_commits`` derniers commits non-merge. Sortie : tableau markdown."""
    import fnmatch
    fichiers = fichiers_du_depot(reg)
    lignes = {}
    for f in fichiers:
        try:
            lignes[f] = (ROOT / f).read_bytes().count(b"\n")
        except OSError:
            pass
    revs = ["HEAD"] + [h + "^" for h in _git("log", "--format=%H", "--", "docs/done_task.md")]
    taches: dict[str, dict] = {}
    for rev in revs:
        for chemin in _git("ls-tree", "-r", "--name-only", rev, "docs/"):
            if chemin in PLAN_EXCLUS or not any(fnmatch.fnmatch(chemin, g) for g in PLAN_GLOBS):
                continue
            for ligne in _git("show", f"{rev}:{chemin}"):
                m = PL._TASK_LIST_RE.match(ligne) or PL._TASK_HEADER_RE.match(ligne)
                if not m or m.group("id") in taches:
                    continue
                fs = {c for d in chemins_declares(m.group("label"))
                      for c in [normaliser(d)] if c and reg.sous_racines(c) and "*" not in c}
                taches[m.group("id")] = {"prefixe": PL._task_prefix(m.group("id")), "fichiers": fs}
    commits, courant = [], None
    jeton = re.compile(r"[A-Z][A-Z0-9]*(?:-[A-Za-z0-9]+)*")
    for ligne in _git("log", f"-{n_commits}", "--no-merges", "--name-only", "--format=@@%s"):
        if ligne.startswith("@@"):
            courant = ({i for i in jeton.findall(ligne[2:]) if i in taches}, set())
            commits.append(courant)
        elif courant is not None:
            courant[1].add(ligne.strip())
    classes = classer_conflits(reg, taches, commits, lignes)
    partages = [r for r in classes if len(r["parcours"]) >= 2]
    entete = [
        f"{len(fichiers)} fichiers, {len(taches)} tâches de plan (ouvertes + archivées), "
        f"{len(commits)} commits ; {len(partages)} fichiers PARTAGÉS (≥ 2 propriétaires).", "",
        "| # | Fichier | Propriétaire | Lignes | Tâches | Commits | Propriétaires qui le touchent | Coût |",
        "|---|---|---|---|---|---|---|---|"]
    for i, r in enumerate(partages[:top], 1):
        ao = " (append-only)" if r["append_only"] else ""
        entete.append(f"| {i} | `{r['fichier']}`{ao} | {r['proprietaire']} | {r['lignes']} | "
                      f"{r['taches']} | {r['commits']} | {', '.join(r['parcours'])} | {r['cout']} |")
    return "\n".join(entete)


# -------------------------------------------------------------------------- CLI
def _git(*args: str) -> list[str]:
    # core.quotepath=off : sans lui git cite les chemins accentués
    # (« "apps/web/src/pages/r\303\251alisations…" ») et ils sortent du registre.
    res = subprocess.run(["git", "-c", "core.quotepath=off", *args], cwd=ROOT,
                         capture_output=True,
                         text=True, encoding="utf-8", errors="replace")
    if res.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} : {res.stderr.strip()}")
    return [ligne for ligne in res.stdout.splitlines() if ligne]


def fichiers_du_depot(reg: Registre) -> list[str]:
    # suivis + non suivis non ignorés : un fichier créé mais pas encore
    # commité est vérifié AVANT de partir en CI.
    # Filtre par PRÉFIXE en Python : passée à git comme pathspec, une racine
    # comme « docker-compose » ne désignerait que le fichier de ce nom exact.
    return sorted({f for f in _git("ls-files", "-co", "--exclude-standard")
                   if reg.sous_racines(f)})


def plans_du_depot() -> dict[str, str]:
    out = {}
    for motif in PLAN_GLOBS:
        for p in sorted(ROOT.glob(motif)):
            rel = p.relative_to(ROOT).as_posix()
            if rel not in PLAN_EXCLUS:
                out[rel] = p.read_text(encoding="utf-8")
    return out


def _stats(reg: Registre, fichiers: list[str]) -> str:
    compte: dict[str, list[int]] = {}
    for f in fichiers:
        o = proprietaire(reg, f) or "—"
        try:
            n = (ROOT / f).read_bytes().count(b"\n")
        except OSError:
            n = 0
        c = compte.setdefault(o, [0, 0])
        c[0] += 1
        c[1] += n
    lignes = [f"{'propriétaire':<14} {'fichiers':>8} {'lignes':>9}  plan"]
    for o, (nf, nl) in sorted(compte.items(), key=lambda x: -x[1][0]):
        plan = reg.owners.get(o, {}).get("plan", "")
        lignes.append(f"{o:<14} {nf:>8} {nl:>9}  {plan}")
    return "\n".join(lignes)


def main(argv=None) -> int:
    for flux in (sys.stdout, sys.stderr):  # console Windows cp1252 (F10)
        try:
            flux.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--base", help="ref git : nomme les fichiers AJOUTÉS sans propriétaire (règle c)")
    ap.add_argument("--stats", action="store_true", help="fichiers/lignes par propriétaire")
    ap.add_argument("--owner-of", nargs="+", metavar="CHEMIN")
    ap.add_argument("--max", type=int, default=60, help="refus imprimés au plus")
    ap.add_argument("--verbose", action="store_true", help="lister aussi les globs morts")
    ap.add_argument("--bloquant", action="store_true",
                    help="règle (d) BLOQUANTE (plan transverse : @atomique exact) ; "
                         "sans l'option elle tourne en mode rapport (code 0)")
    ap.add_argument("--conflits", type=int, nargs="?", const=40, metavar="N",
                    help="mesure : les N fichiers partagés les plus coûteux (tâches × "
                         "propriétaires × lignes, plans + archives + 2000 commits)")
    args = ap.parse_args(argv)

    reg = charger_registre()
    if args.owner_of:
        for brut in args.owner_of:
            c = normaliser(brut) or brut
            hits = reg.resoudre(c)
            ao = " (surface append-only)" if reg.est_append_only(c) else ""
            print(f"{c} → {', '.join(hits) or 'AUCUN'}{ao}")
        return 0

    if args.conflits:
        print(mesurer_conflits(reg, top=args.conflits))
        return 0
    fichiers = fichiers_du_depot(reg)
    if args.stats:
        print(_stats(reg, fichiers))
        return 0

    erreurs, avert = verifier_registre(reg, fichiers)
    erreurs += verifier_fichiers(reg, fichiers)
    plans = plans_du_depot()
    erreurs += verifier_plans(reg, plans, fichiers)
    transverse = verifier_transverse(reg, plans, fichiers)
    if args.bloquant:
        erreurs += transverse
    elif transverse:  # mode RAPPORT jusqu'à la migration D-OWN-FUSION (AMET101)
        for e in transverse[:args.max]:
            print(f"RAPPORT (règle d) : {e}")
        if len(transverse) > args.max:
            print(f"… et {len(transverse) - args.max} autre(s)")
        print(f"note : règle (d) en mode RAPPORT — {len(transverse)} tâche(s) du "
              f"plan transverse à scinder ou à marquer `@atomique` exact ; "
              f"--bloquant pour refuser\n")
    if args.base:
        ajoutes = _git("diff", "--name-only", "--diff-filter=A",
                       f"{args.base}...HEAD", "--", *reg.roots)
        erreurs += verifier_nouveaux(reg, ajoutes)

    morts = [a for a in avert if a.startswith("glob mort")]
    for a in (avert if args.verbose else [a for a in avert if a not in morts]):
        print(f"AVERTISSEMENT : {a}")
    if morts and not args.verbose:
        print(f"note : {len(morts)} glob(s) ne couvrent encore aucun fichier (cibles "
              f"déclarées d'avance par des tâches planifiées, ou globs périmés) — "
              f"--verbose pour la liste")
    if erreurs:
        for e in erreurs[:args.max]:
            print(f"REFUS : {e}")
        if len(erreurs) > args.max:
            print(f"… et {len(erreurs) - args.max} autre(s) refus")
        print(f"\nÉCHEC — {len(erreurs)} refus (docs/ownership.yml, règles a/b/c/d "
              f"en tête de scripts/check_ownership.py)")
        return 1
    print(f"OK — {len(fichiers)} fichiers, chacun à UN propriétaire parmi "
          f"{len(reg.owners)} ; {len(plans)} plans vérifiés ; "
          f"{len(reg.append_only)} surfaces append-only")
    return 0


if __name__ == "__main__":
    sys.exit(main())

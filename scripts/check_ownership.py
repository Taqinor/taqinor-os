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

LES TROIS RÈGLES
----------------
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

Pur stdlib : le job ``stage-names`` n'installe pas PyYAML ; le registre est
écrit dans le sous-ensemble YAML lu par ``plan_lanes._MiniYamlParser``.

Usage
-----
    python scripts/check_ownership.py               # règles (a) (b) (c), code 1 si refus
    python scripts/check_ownership.py --base origin/main   # + fichiers ajoutés par la branche
    python scripts/check_ownership.py --stats       # fichiers et lignes par propriétaire
    python scripts/check_ownership.py --owner-of frontend/src/pages/ventes/DevisGenerator.jsx
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


def normaliser(brut: str, web: bool = False) -> str | None:
    """Chemin déclaré dans une tâche → chemin du dépôt (``None`` si inexploitable).

    Les plans abrègent : ``apps/crm/views.py`` (= backend/django_core/apps/…),
    ``core/events.py``, ``features/crm/stages.js`` (= frontend/src/…). Un nom
    nu (``views.py``) est ambigu : ignoré. ``web=True`` (plan du site) lit
    ``src/…`` comme ``apps/web/src/…``.
    """
    p = brut.strip().strip("`'\"*() ,;")
    while p.startswith("./"):
        p = p[2:]
    if not p or "/" not in p or any(c in p for c in "*<>{}"):
        return None
    if p.startswith(("backend/", "frontend/", "apps/web/")):
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

    def __init__(self, data: dict, racine: Path):
        self.racine = racine
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
        (``ventes/**`` ⊃ ``ventes/quote_engine/**``) : le préfixe littéral le
        plus long gagne ; une égalité entre deux propriétaires = refus.
        """
        hits = sorted({nom for nom, _, rx, lit in self._regles["paths"]
                       if chemin.startswith(lit) and rx.fullmatch(chemin)})
        if hits:
            return hits
        meilleurs: dict[str, int] = {}
        for nom, _, rx, lit in self._regles["fallback"]:
            if chemin.startswith(lit) and rx.fullmatch(chemin):
                meilleurs[nom] = max(meilleurs.get(nom, -1), len(lit))
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
    return Registre(PL._MiniYamlParser(texte).parse(), racine)


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


def verifier_plans(reg: Registre, plans: dict[str, str]) -> list[str]:
    """Règle (b) (+ (c) au moment où la tâche est écrite)."""
    erreurs = []
    for plan, texte in sorted(plans.items()):
        owners = reg.proprietaires_du_plan(plan)
        if owners is None:
            erreurs.append(
                f"{plan} : aucun propriétaire ne lie ce plan — le déclarer "
                f"(owners.<x>.plan ou plans:) dans docs/ownership.yml")
            continue
        if set(owners) & reg.exempt:
            continue
        web = owners == ["web"]
        hors_file = False
        for n_ligne, brut in enumerate(texte.splitlines(), 1):
            if brut.startswith(("# ", "## ", "### ")):
                hors_file = bool(PL._NON_QUEUE_SECTION.match(brut))
                continue
            if hors_file:
                continue
            m = PL._TASK_LIST_RE.match(brut) or PL._TASK_HEADER_RE.match(brut)
            if not m:
                continue
            statut = (m.group("status") or "").strip()
            en_ligne = (m.groupdict().get("inline_status") or "").strip()
            if en_ligne:
                statut = en_ligne
            if statut:
                continue  # [x], [BLOCKED…], [GATED…] : rien à construire
            tid = m.group("id")
            for declare in sorted(PL._task_files_brut(m.group("label"))):
                chemin = normaliser(declare, web=web)
                if not chemin or not reg.sous_racines(chemin) \
                        or reg.est_append_only(chemin):
                    continue
                hits = reg.resoudre(chemin)
                if not hits:
                    erreurs.append(
                        f"{plan}:{n_ligne} {tid} — `{chemin}` est sans propriétaire "
                        f"(fichier neuf ?) : le déclarer dans docs/ownership.yml")
                elif len(hits) > 1:
                    erreurs.append(
                        f"{plan}:{n_ligne} {tid} — `{chemin}` a deux propriétaires "
                        f"({', '.join(hits)}) : corriger docs/ownership.yml")
                elif hits[0] not in owners:
                    erreurs.append(
                        f"{plan}:{n_ligne} {tid} — `{chemin}` appartient à "
                        f"« {hits[0]} », pas à « {'/'.join(owners)} » : une tâche "
                        f"multi-propriétaires va dans {reg.plan_transverse} "
                        f"(ou retirer ce fichier de Files:)")
    return erreurs


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
    return sorted(set(_git("ls-files", "-co", "--exclude-standard", "--",
                           *reg.roots)))


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
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--base", help="ref git : nomme les fichiers AJOUTÉS sans propriétaire (règle c)")
    ap.add_argument("--stats", action="store_true", help="fichiers/lignes par propriétaire")
    ap.add_argument("--owner-of", nargs="+", metavar="CHEMIN")
    ap.add_argument("--max", type=int, default=60, help="refus imprimés au plus")
    args = ap.parse_args(argv)

    reg = charger_registre()
    if args.owner_of:
        for brut in args.owner_of:
            c = normaliser(brut) or brut
            hits = reg.resoudre(c)
            ao = " (surface append-only)" if reg.est_append_only(c) else ""
            print(f"{c} → {', '.join(hits) or 'AUCUN'}{ao}")
        return 0

    fichiers = fichiers_du_depot(reg)
    if args.stats:
        print(_stats(reg, fichiers))
        return 0

    erreurs, avert = verifier_registre(reg, fichiers)
    erreurs += verifier_fichiers(reg, fichiers)
    plans = plans_du_depot()
    erreurs += verifier_plans(reg, plans)
    if args.base:
        ajoutes = _git("diff", "--name-only", "--diff-filter=A",
                       f"{args.base}...HEAD", "--", *reg.roots)
        erreurs += verifier_nouveaux(reg, ajoutes)

    for a in avert:
        print(f"AVERTISSEMENT : {a}")
    if erreurs:
        for e in erreurs[:args.max]:
            print(f"REFUS : {e}")
        if len(erreurs) > args.max:
            print(f"… et {len(erreurs) - args.max} autre(s) refus")
        print(f"\nÉCHEC — {len(erreurs)} refus (docs/ownership.yml, règles a/b/c "
              f"en tête de scripts/check_ownership.py)")
        return 1
    print(f"OK — {len(fichiers)} fichiers, chacun à UN propriétaire parmi "
          f"{len(reg.owners)} ; {len(plans)} plans vérifiés ; "
          f"{len(reg.append_only)} surfaces append-only")
    return 0


if __name__ == "__main__":
    sys.exit(main())

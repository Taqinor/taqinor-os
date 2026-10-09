"""ACRM54 (C-ACRM-015) — garde « geste multi-écriture atomique » du CRM.

CLASSE GARDÉE. Une ``@action`` POST/PATCH/PUT/DELETE de ``apps/crm/views.py``
qui enchaîne DEUX fonctions d'écriture de ``crm.services`` (ou crée un
``Attachment`` puis appelle un service) sans ``transaction.atomic()`` laisse,
si la 2ᵉ écriture échoue, un état à moitié écrit (touche faite sans
prochaine touche, pièce déposée sans étape close…). L'atomicité était décidée
geste par geste à la main.

CE QUE LA GARDE FAIT. Pour chaque telle action, les appels d'écriture doivent
tous se trouver dans un ``with transaction.atomic():`` (ou sous le décorateur
``@transaction.atomic``), y compris ceux faits par un helper ``self._xxx(...)``
de la même classe (un niveau). Une « fonction d'écriture » de ``crm.services``
est une fonction publique dont le corps appelle ``.save/.create/.update/
.delete/.bulk_*`` ou une autre fonction d'écriture du module (clôture
transitive) — calculée sur le SOURCE réel, jamais listée à la main. Sinon :
liste blanche motivée ``fichier::Classe.action``. Une clé qui n'apparie plus
aucun site échoue (cliquet décroissant).

DB-free, AST-only. Usage : ``python scripts/check_actions_atomiques.py``.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CRM = ROOT / "backend" / "django_core" / "apps" / "crm"
VIEWS_REL = "backend/django_core/apps/crm/views.py"
SERVICES_REL = "backend/django_core/apps/crm/services.py"

METHODES_ECRITURE = {"post", "patch", "put", "delete"}
ATTRS_ECRITURE = {"save", "create", "delete", "bulk_create",
                  "bulk_update", "get_or_create", "update_or_create"}
#: ``.update(`` n'écrit que sur un queryset (jamais un ``dict.update``).
MARQUES_QUERYSET = ("objects", ".filter(", ".exclude(", "select_for_update")


def _appel_ecriture(f) -> bool:
    if not isinstance(f, ast.Attribute):
        return False
    if f.attr in ATTRS_ECRITURE:
        return True
    return f.attr == "update" and any(
        m in ast.unparse(f.value) for m in MARQUES_QUERYSET)

#: Liste blanche MOTIVÉE : ``fichier::Classe.action`` -> raison propre.
ALLOWLIST: dict = {
    "backend/django_core/apps/crm/views.py::LeadViewSet.locataire":
        "deux branches EXCLUSIVES (retour anticipé après "
        "clore_locataire_sans_proprietaire) : une seule écriture de service "
        "par requête, rien à rendre atomique",
    "backend/django_core/apps/crm/views.py::RelanceEtapeViewSet.fait":
        "À CORRIGER (constaté au build, hors Files de la garde) : "
        "definir_langue_preferee s'écrit APRÈS le geste atomique "
        "(_marquer/_repondre) dans sa propre transaction — un échec laisse la "
        "touche close sans langue ; correction côté apps/crm",
}


def fonctions_d_ecriture(services_source: str) -> set:
    """Fonctions PUBLIQUES de crm.services qui écrivent (clôture transitive)."""
    tree = ast.parse(services_source)
    fonctions = {n.name: n for n in tree.body
                 if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    ecrit, appels = set(), {}
    for nom, fn in fonctions.items():
        a_ecrit, cibles = False, set()
        for n in ast.walk(fn):
            if isinstance(n, ast.Call):
                f = n.func
                if _appel_ecriture(f):
                    a_ecrit = True
                if isinstance(f, ast.Name) and f.id in fonctions:
                    cibles.add(f.id)
        if a_ecrit:
            ecrit.add(nom)
        appels[nom] = cibles
    change = True
    while change:
        change = False
        for nom, cibles in appels.items():
            if nom not in ecrit and cibles & ecrit:
                ecrit.add(nom)
                change = True
    return {n for n in ecrit if not n.startswith("_")}


def _noms_importes(tree, ecriture: set) -> set:
    """Noms d'écriture de crm.services importés dans la vue (module/fonction)."""
    out = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom) and n.module \
                and n.module.split(".")[-1] == "services":
            for a in n.names:
                if a.name in ecriture:
                    out.add(a.asname or a.name)
    return out


def _est_atomic(expr) -> bool:
    """``transaction.atomic()`` ou un décorateur maison ``*_atomique``
    (``_geste_atomique``, ACRM22)."""
    texte = ast.unparse(expr)
    return "atomic" in texte or "atomique" in texte


def _methodes_http(fn) -> set:
    for d in fn.decorator_list:
        if isinstance(d, ast.Call) and (
                getattr(d.func, "id", None) == "action"
                or getattr(d.func, "attr", None) == "action"):
            for k in d.keywords:
                if k.arg == "methods" and isinstance(k.value, (ast.List,
                                                               ast.Tuple)):
                    return {e.value.lower() for e in k.value.elts
                            if isinstance(e, ast.Constant)}
    return set()


def _decore_atomic(fn) -> bool:
    return any(_est_atomic(d) for d in fn.decorator_list
               if not (isinstance(d, ast.Call)
                       and getattr(d.func, "id", None) == "action"))


def _plages_atomic(fn):
    plages = []
    for n in ast.walk(fn):
        if isinstance(n, (ast.With, ast.AsyncWith)) and any(
                _est_atomic(i.context_expr) for i in n.items):
            plages.append((n.lineno, n.end_lineno))
    return plages


def _ecritures_directes(fn, noms: set):
    """[(nom, ligne)] des appels d'écriture (services ou Attachment) de fn."""
    out = []
    for n in ast.walk(fn):
        if not isinstance(n, ast.Call):
            continue
        f = n.func
        if isinstance(f, ast.Name) and f.id in noms:
            out.append((f.id, n.lineno))
        elif (isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name)
              and f.value.id == "services" and f.attr in noms):
            out.append((f.attr, n.lineno))
        elif (isinstance(f, ast.Attribute) and f.attr == "create"
              and "Attachment" in ast.unparse(f.value)):
            out.append(("Attachment.create", n.lineno))
    return out


def analyser(views_source: str, services_source: str):
    """[(clé, ligne, [écritures non atomiques])] pour les actions fautives."""
    ecriture = fonctions_d_ecriture(services_source)
    tree = ast.parse(views_source)
    noms = _noms_importes(tree, ecriture) | (
        {"services"} and set())  # les appels `services.x` sont gérés à part
    noms_attr = set(ecriture)
    tous = noms | noms_attr
    fautifs = []
    for cls in [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]:
        methodes = {m.name: m for m in cls.body
                    if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))}
        for nom, fn in methodes.items():
            if not _methodes_http(fn) & METHODES_ECRITURE:
                continue
            ecritures = []  # (nom, couvert)
            plages = _plages_atomic(fn)
            couvert_fn = _decore_atomic(fn)

            def couvert(ligne, plages=plages, c=couvert_fn):
                return c or any(a <= ligne <= b for a, b in plages)

            for e, ligne in _ecritures_directes(fn, tous):
                # un nom local importé OU un `services.x` : filtré par `tous`
                if e in noms or e == "Attachment.create" or e in noms_attr:
                    ecritures.append((e, couvert(ligne)))
            for n in ast.walk(fn):  # helpers `self._xxx(...)` d'un niveau
                if (isinstance(n, ast.Call)
                        and isinstance(n.func, ast.Attribute)
                        and isinstance(n.func.value, ast.Name)
                        and n.func.value.id == "self"
                        and n.func.attr in methodes
                        and n.func.attr != nom
                        and n.func.attr.startswith("_")):
                    h = methodes[n.func.attr]
                    h_plages = _plages_atomic(h)
                    h_couvert = _decore_atomic(h) or couvert(n.lineno)
                    for e, ligne in _ecritures_directes(h, tous):
                        ok = h_couvert or any(a <= ligne <= b
                                              for a, b in h_plages)
                        ecritures.append((e, ok))
            distincts = {e for e, _ in ecritures}
            multi = len(distincts) >= 2
            if multi and not all(ok for _, ok in ecritures):
                nus = sorted({e for e, ok in ecritures if not ok})
                fautifs.append((f"{cls.name}.{nom}", fn.lineno, nus))
    return fautifs


def evaluer(views_source: str, services_source: str, allowlist: dict,
            rel: str = VIEWS_REL):
    violations, vues = [], set()
    for sym, ligne, nus in analyser(views_source, services_source):
        cle = f"{rel}::{sym}"
        vues.add(cle)
        if cle not in allowlist:
            violations.append(
                f"{rel}:{ligne}  {sym} — plusieurs écritures de service hors "
                f"transaction.atomic() ({', '.join(nus)})")
    mortes = sorted(c for c in allowlist if c not in vues)
    return violations, mortes


def main(argv=None) -> int:
    vues = (ROOT / VIEWS_REL).read_text(encoding="utf-8")
    services = (ROOT / SERVICES_REL).read_text(encoding="utf-8")
    violations, mortes = evaluer(vues, services, ALLOWLIST)
    violations += [f"{c} — clé morte de la liste blanche : la retirer"
                   for c in mortes]
    if violations:
        print("check_actions_atomiques : @action crm à écritures multiples "
              "hors transaction.atomic() :")
        for v in violations:
            print(f"  - {v}")
        print("\nEnveloppez le geste dans `with transaction.atomic():` "
              "(ACRM22) ; exception motivée : ALLOWLIST du script.")
        return 1
    print("check_actions_atomiques : OK — chaque @action crm à écritures "
          "multiples est atomique (ou listée avec sa raison).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

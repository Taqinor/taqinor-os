#!/usr/bin/env python3
"""ACRM50 - garde de la classe « opposition recomposee a la main dans chaque
point d'entree » (C-ACRM-010, critere C7).

Dans ``apps/crm`` et ``apps/automation`` (hors migrations/tests), TOUTE fonction
qui :
  * cree une touche : ``RelanceEtape.objects.create(...)`` / ``bulk_create(...)``,
  * fabrique un lien ``wa.me`` (litteral de chaine contenant ``wa.me/``),
  * envoie un e-mail : ``send_mail(...)`` / ``EmailMessage(...)``,
doit consulter la garde de contact (``peut_contacter``, ``_lead_relancable``,
``motif_de_refus``) dans son corps, OU figurer dans ``LISTE_BLANCHE`` avec une
raison motivee (une ligne par site, cle de CONTENU ``fichier::fonction::genre``,
jamais un numero de ligne). Analyse AST, DB-free, lecture seule.

Sortie non nulle : fichier:ligne, fonction et genre du site non garde.

Usage : python scripts/check_garde_contact.py
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APPS_DIR = ROOT / "backend" / "django_core" / "apps"
APPS_VISEES = ("crm", "automation")

#: Noms dont la simple presence dans le corps de la fonction vaut « garde ».
GARDES_RECONNUES = {"peut_contacter", "_lead_relancable", "motif_de_refus"}

#: ``fichier::fonction::genre`` -> raison. Site non garde TOLERE, motive.
#: Les raisons « A CORRIGER » sont de la dette reelle a traiter dans la session
#: qui possede le fichier (jamais corrigee depuis cette garde).
LISTE_BLANCHE: dict[str, str] = {
    "backend/django_core/apps/crm/receivers_clients.py::_proposer_lien_parrainage_on_devis_accepted::wa.me":
        "lien de parrainage propose au COMMERCIAL du devis (destinataire interne, pas le prospect) ; aucun envoi au lead",
    "backend/django_core/apps/crm/services.py::_build_lead_wa_reply_url::wa.me":
        "A CORRIGER (ACRM, session crm) : lien wa.me vers le prospect construit sans consulter peut_contacter ; brouillon que le vendeur clique, mais l'opposition n'est pas visible",
    "backend/django_core/apps/crm/services.py::dispatch_appointment_reminder::wa.me":
        "A CORRIGER (ACRM, session crm) : brouillon wa.me de rappel RDV vers le lead sans garde de contact (opposition non verifiee)",
    "backend/django_core/apps/crm/services.py::_poser_etape_de_filet::touche":
        "A CORRIGER (LSVC5-5) : pose de filet sans garde propre ; liste blanche « appelants gardes » OU garde a ajouter, decision du proprietaire crm",
    "backend/django_core/apps/crm/services.py::initialiser_plan_relance::touche":
        "A CORRIGER (session crm) : creation en masse du plan de relance, tache interne du vendeur ; garde de contact a la pose non verifiee",
    "backend/django_core/apps/crm/services.py::assurer_prochaine_etape_apres_succes::touche":
        "A CORRIGER (session crm) : touche de suite posee sans garde de contact a la pose",
    "backend/django_core/apps/crm/services.py::poser_touche_signal::touche":
        "A CORRIGER (session crm) : touche de signal posee sans garde de contact a la pose",
    "backend/django_core/apps/crm/services.py::_poser_etape_visite::touche":
        "A CORRIGER (session crm) : touche de visite posee sans garde de contact a la pose",
    "backend/django_core/apps/crm/services.py::poser_touche_rappel_demande::touche":
        "A CORRIGER (session crm) : touche de rappel demande posee sans garde de contact a la pose",
    "backend/django_core/apps/crm/services.py::_poser_etape_passation::touche":
        "A CORRIGER (session crm) : touche de passation posee sans garde de contact a la pose",
    "backend/django_core/apps/automation/actions.py::_send_email::email":
        "A CORRIGER (LSVC4-3, session automation/crm) : e-mail sortant a un destinataire pouvant deriver d'un lead, sans peut_contacter",
}

GENRE_TOUCHE, GENRE_WAME, GENRE_MAIL = "touche", "wa.me", "email"


def _fichiers():
    for app in APPS_VISEES:
        base = APPS_DIR / app
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*.py")):
            parts = p.relative_to(base).parts
            n = p.name
            if "migrations" in parts or "tests" in parts:
                continue
            if n.startswith(("test_", "tests_")) or n in ("tests.py", "conftest.py") \
                    or n.endswith("_test.py"):
                continue
            yield p


def _rel(p: Path) -> str:
    return str(p.relative_to(ROOT)).replace("\\", "/")


def _nom_appel(func: ast.AST) -> str:
    return func.attr if isinstance(func, ast.Attribute) else (
        func.id if isinstance(func, ast.Name) else "")


class _Visiteur(ast.NodeVisitor):
    def __init__(self):
        self.pile: list[str] = []
        # fonction qualifiee -> {"garde": bool, "sites": [(genre, ligne)]}
        self.fonctions: dict[str, dict] = {}

    def _etat(self):
        cle = ".".join(self.pile) or "<module>"
        return self.fonctions.setdefault(cle, {"garde": False, "sites": []})

    def _porte(self, node):
        self.pile.append(node.name)
        self.generic_visit(node)
        self.pile.pop()

    visit_FunctionDef = visit_AsyncFunctionDef = visit_ClassDef = _porte

    def _noter(self, nom):
        if nom in GARDES_RECONNUES:
            self._etat()["garde"] = True

    def visit_Name(self, node):
        self._noter(node.id)

    def visit_Attribute(self, node):
        self._noter(node.attr)
        self.generic_visit(node)

    def visit_Call(self, node):
        nom = _nom_appel(node.func)
        if isinstance(node.func, ast.Attribute) and nom in ("create", "bulk_create"):
            recv = ast.unparse(node.func.value)
            if recv == "RelanceEtape.objects" or recv.endswith(".RelanceEtape.objects"):
                self._etat()["sites"].append((GENRE_TOUCHE, node.lineno))
        elif nom in ("send_mail", "EmailMessage", "EmailMultiAlternatives"):
            self._etat()["sites"].append((GENRE_MAIL, node.lineno))
        self.generic_visit(node)

    def visit_Import(self, node):
        for a in node.names:
            self._noter(a.name.split(".")[-1])

    def visit_ImportFrom(self, node):
        for a in node.names:
            self._noter(a.name)

    def visit_Constant(self, node):
        if isinstance(node.value, str) and "wa.me/" in node.value:
            self._etat()["sites"].append((GENRE_WAME, node.lineno))


def _retirer_docstrings(tree: ast.AST) -> None:
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)):
            corps = n.body
            if corps and isinstance(corps[0], ast.Expr) \
                    and isinstance(corps[0].value, ast.Constant) \
                    and isinstance(corps[0].value.value, str):
                corps[0].value.value = ""


def analyser_source(source: str, rel: str):
    """-> liste de (cle, ligne, fonction, genre) pour les sites NON gardes."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    _retirer_docstrings(tree)
    v = _Visiteur()
    v.visit(tree)
    out = []
    for fonction, etat in v.fonctions.items():
        if etat["garde"]:
            continue
        vus = set()
        for genre, ligne in etat["sites"]:
            if genre in vus:
                continue
            vus.add(genre)
            out.append((f"{rel}::{fonction}::{genre}", ligne, fonction, genre))
    return out


def main(argv=None) -> int:
    violations = []
    utilises = set()
    for p in _fichiers():
        rel = _rel(p)
        for cle, ligne, fonction, genre in analyser_source(
                p.read_text(encoding="utf-8"), rel):
            if cle in LISTE_BLANCHE:
                utilises.add(cle)
                continue
            violations.append((rel, ligne, fonction, genre))
    perimees = sorted(set(LISTE_BLANCHE) - utilises)
    if violations or perimees:
        for f, l, fn, g in violations:
            print(f"{f}:{l}: {fn}() - {g} sans garde de contact "
                  f"(peut_contacter/_lead_relancable/motif_de_refus) ni liste blanche")
        for c in perimees:
            print(f"liste blanche perimee (plus aucun site) : {c}")
        return 1
    print("check_garde_contact : OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())

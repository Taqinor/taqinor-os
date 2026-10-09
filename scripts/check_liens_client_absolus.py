#!/usr/bin/env python3
"""GARDE CI (backend-lint-fast) — AFAC94 : un lien destiné au client est ABSOLU.

CLASSE C-AFAC-017 : `{'pay_url': f'/api/django/public/pay/{token}/'}` recopié tel
quel dans l'e-mail pré-échéance et le bouton « Payer en ligne » donne un lien
RELATIF — inutilisable hors du site. Un lien client (`pay_url`, lien de paiement,
page publique `/api/django/public/…`) doit être construit par un constructeur
d'URL absolue : `_public_url(...)` ou `request.build_absolute_uri(...)`.

La garde lit par AST le code backend (`apps/**`, `core/**`, hors tests,
migrations) : toute chaîne ou f-string dont le préfixe littéral est
`/api/django/public/` (ou une route client publique de `ROUTES_CLIENT`) qui
n'est pas l'argument DIRECT d'un constructeur autorisé est signalée
(`fichier::fonction`). Les docstrings ne comptent pas.

Passif gelé : `scripts/liens_client_absolus_allow.txt` (`fichier::fonction`),
il ne peut que RÉTRÉCIR : une clé morte fait échouer la garde.

Usage :
    python scripts/check_liens_client_absolus.py [--write-baseline]
"""
from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _cliquet  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
BACKEND = Path("backend") / "django_core"
SOUS_DOSSIERS = ("apps", "core")
BASELINE = ROOT / "scripts" / "liens_client_absolus_allow.txt"
# Préfixes littéraux d'un lien client public (constante de la garde).
ROUTES_CLIENT = ("/api/django/public/",)
# Constructeurs d'URL absolue : un lien est correct s'il est leur argument direct.
CONSTRUCTEURS = {"_public_url", "build_absolute_uri", "public_url"}
IGNORES = {"migrations", "tests", "test", "node_modules", "__pycache__"}
ENTETE = (
    "# Base de reference de check_liens_client_absolus.py (AFAC94).\n"
    "# Une ligne = `fichier::fonction` qui construit un lien client RELATIF\n"
    "# (/api/django/public/...) hors _public_url / build_absolute_uri. DETTE : ne\n"
    "# peut que RETRECIR (rendre le lien absolu : tache C-AFAC-017+020).\n"
)


def _prefixe_litteral(noeud) -> str:
    """Début littéral d'une Constant str ou d'une f-string."""
    if isinstance(noeud, ast.Constant) and isinstance(noeud.value, str):
        return noeud.value
    if isinstance(noeud, ast.JoinedStr) and noeud.values:
        premier = noeud.values[0]
        if isinstance(premier, ast.Constant) and isinstance(premier.value, str):
            return premier.value
    return ""


def _nom_appel(appel: ast.Call) -> str:
    f = appel.func
    return f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else ""


class _Visiteur(ast.NodeVisitor):
    def __init__(self):
        self.pile = []
        self.docstrings = set()
        self.autorises = set()
        self.sites = set()  # noms de fonctions

    def _fn(self):
        return ".".join(self.pile) or "<module>"

    def _porte(self, node):
        corps = node.body
        if (corps and isinstance(corps[0], ast.Expr)
                and isinstance(corps[0].value, ast.Constant)):
            self.docstrings.add(id(corps[0].value))
        self.pile.append(node.name)
        self.generic_visit(node)
        self.pile.pop()

    visit_FunctionDef = visit_AsyncFunctionDef = visit_ClassDef = _porte

    def visit_Module(self, node):
        if (node.body and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, ast.Constant)):
            self.docstrings.add(id(node.body[0].value))
        self.generic_visit(node)

    def visit_Call(self, node):
        if _nom_appel(node) in CONSTRUCTEURS:
            for arg in list(node.args) + [k.value for k in node.keywords]:
                self.autorises.add(id(arg))
        self.generic_visit(node)

    def _verifier(self, node):
        if id(node) in self.docstrings or id(node) in self.autorises:
            return
        prefixe = _prefixe_litteral(node)
        if any(prefixe.startswith(r) for r in ROUTES_CLIENT):
            self.sites.add((self._fn(), node.lineno))

    def visit_Constant(self, node):
        self._verifier(node)

    def visit_JoinedStr(self, node):
        self._verifier(node)
        # ne pas redescendre : les morceaux littéraux de la f-string ne
        # sont pas des chaînes autonomes.


def analyser(root: Path = ROOT) -> dict:
    """{clé 'fichier::fonction': ligne}."""
    trouves: dict = {}
    for sous in SOUS_DOSSIERS:
        base = root / BACKEND / sous
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*.py")):
            rel = p.relative_to(base)
            if (any(x in IGNORES for x in rel.parts[:-1])
                    or rel.name.startswith(("test_", "tests_")) or rel.name == "tests.py"):
                continue
            try:
                source = p.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            if not any(r in source for r in ROUTES_CLIENT):
                continue
            try:
                arbre = ast.parse(source)
            except SyntaxError:
                continue
            visiteur = _Visiteur()
            visiteur.visit(arbre)
            for fonction, ligne in sorted(visiteur.sites):
                trouves.setdefault(f"{p.relative_to(root).as_posix()}::{fonction}", ligne)
    return trouves


def verifier(trouves: dict, base: set) -> list:
    def decrire(cle):
        fichier, fonction = cle.split("::", 1)
        return (f"{fichier}:{trouves[cle]} ({fonction}) construit un lien client en chemin "
                "RELATIF (/api/django/public/…) — passer par _public_url(...) ou "
                "request.build_absolute_uri(...) pour un lien absolu.")
    return _cliquet.comparer(trouves, base, nom_fichier="liens_client_absolus_allow.txt",
                             decrire=decrire)


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--write-baseline", action="store_true")
    ap.add_argument("--autoriser-croissance", action="store_true")
    args = ap.parse_args(argv)
    trouves = analyser()
    if args.write_baseline:
        try:
            _cliquet.ecrire(BASELINE, trouves, ENTETE, "AFAC94 lien client relatif",
                            autoriser_croissance=args.autoriser_croissance)
        except ValueError as exc:
            print("REFUS : " + str(exc))
            return 1
        print(f"Base réécrite ({len(trouves)} entrée(s)).")
        return 0
    erreurs = verifier(trouves, _cliquet.charger(BASELINE))
    if erreurs:
        print("check_liens_client_absolus: ÉCHEC")
        for e in erreurs:
            print("  - " + e)
        return 1
    print(f"check_liens_client_absolus: OK — {len(trouves)} lien(s) relatif(s) gelé(s), "
          "aucun nouveau.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

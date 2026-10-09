#!/usr/bin/env python3
"""AMOT74 - garde de la classe « echeance reglementaire non surveillee ».

Le moteur porte des constantes DATEES dont la validite se termine (tarif d'excedent ANRE
04/26 valable jusqu'au 28/02/2027, millesime 2026 du bareme ONEE). Passee la date, le moteur
extrapolerait une decision perimee. Cette garde LIT ces constantes dans le code reel (AST,
sans Django) et passe au ROUGE 60 jours avant chaque fin de validite, en nommant la constante
et la decision a re-sourcer.

Constantes decouvertes (convention de nommage, pas une liste figee) dans
``backend/django_core/apps/ventes/quote_engine`` (hors tests) :
  - ``<NOM>_PERIODE = (date(debut), date(fin))``  -> fin de validite = ``fin`` ;
  - ``<NOM>_FIN_VALIDITE = date(...)`` / ``RELEVE_LE``-like : ``<NOM>_VALABLE_JUSQUAU``
    -> cette date ;
  - ``MILLESIME_COURANT = AAAA``                  -> fin de validite = 31/12/AAAA.

Usage : python scripts/check_echeances_reglementaires.py [--date AAAA-MM-JJ]
(0 = vert ; 1 = au moins une echeance dans la fenetre de 60 jours ou depassee).
"""
from __future__ import annotations

import ast
import datetime as dt
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MOTEUR = ROOT / "backend" / "django_core" / "apps" / "ventes" / "quote_engine"
FENETRE_JOURS = 60
SUFFIXES_DATE = ("_FIN_VALIDITE", "_VALABLE_JUSQUAU")


def aujourdhui() -> dt.date:
    """Date du jour a Casablanca (repli UTC+1 si tzdata est absent)."""
    try:
        from zoneinfo import ZoneInfo
        return dt.datetime.now(ZoneInfo("Africa/Casablanca")).date()
    except Exception:  # noqa: BLE001
        return dt.datetime.now(dt.timezone(dt.timedelta(hours=1))).date()


def _date_litterale(noeud):
    """``_dt.date(2027, 2, 28)`` / ``date(2027, 2, 28)`` -> datetime.date, sinon None."""
    if not isinstance(noeud, ast.Call) or len(noeud.args) != 3:
        return None
    nom = noeud.func.attr if isinstance(noeud.func, ast.Attribute) else getattr(noeud.func, "id", "")
    if nom != "date":
        return None
    try:
        y, m, d = (a.value for a in noeud.args)
        return dt.date(y, m, d)
    except (AttributeError, TypeError, ValueError):
        return None


def echeances(racine_moteur: Path = None) -> list[tuple[str, str, dt.date]]:
    """[(fichier relatif, constante, fin de validite)] decouvertes dans le moteur."""
    racine_moteur = MOTEUR if racine_moteur is None else racine_moteur
    trouvees = []
    for chemin in sorted(racine_moteur.rglob("*.py")):
        if "tests" in chemin.parts or chemin.name.startswith("test_"):
            continue
        try:
            arbre = ast.parse(chemin.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for stmt in arbre.body:
            if not isinstance(stmt, ast.Assign) or len(stmt.targets) != 1:
                continue
            cible = stmt.targets[0]
            if not isinstance(cible, ast.Name):
                continue
            nom, valeur = cible.id, stmt.value
            rel = chemin.relative_to(racine_moteur).as_posix()
            if nom.endswith("_PERIODE") and isinstance(valeur, ast.Tuple) and len(valeur.elts) == 2:
                fin = _date_litterale(valeur.elts[1])
                if fin:
                    trouvees.append((rel, nom, fin))
            elif nom.endswith(SUFFIXES_DATE):
                fin = _date_litterale(valeur)
                if fin:
                    trouvees.append((rel, nom, fin))
            elif nom == "MILLESIME_COURANT" and isinstance(valeur, ast.Constant) \
                    and isinstance(valeur.value, int):
                trouvees.append((rel, nom, dt.date(valeur.value, 12, 31)))
    return trouvees


def verifier(date_du_jour: dt.date, racine_moteur: Path = None) -> list[str]:
    erreurs = []
    for rel, nom, fin in echeances(racine_moteur):
        reste = (fin - date_du_jour).days
        if reste <= FENETRE_JOURS:
            etat = (f"a expire le {fin.strftime('%d/%m/%Y')}" if reste < 0
                    else f"expire le {fin.strftime('%d/%m/%Y')} (dans {reste} j)")
            erreurs.append(
                f"{nom} ({rel}) {etat} : re-sourcer la decision reglementaire "
                f"(fondateur) avant l'echeance - le moteur ne doit jamais extrapoler.")
    return erreurs


def main(argv: list[str]) -> int:
    jour = aujourdhui()
    if "--date" in argv:
        jour = dt.date.fromisoformat(argv[argv.index("--date") + 1])
    erreurs = verifier(jour)
    for e in erreurs:
        print(f"ECHEC check_echeances_reglementaires : {e}")
    if not erreurs:
        trouvees = echeances()
        print(f"check_echeances_reglementaires : OK ({len(trouvees)} echeance(s) surveillee(s), "
              f"fenetre {FENETRE_JOURS} j, au {jour.isoformat()})")
    return 1 if erreurs else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

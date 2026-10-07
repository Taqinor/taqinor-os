#!/usr/bin/env python3
"""GARDE CI — ADOC147 : aucune surface portail livrée « côté serveur seulement ».

Chaque route SELF-SERVICE de ``apps/portail/urls.py`` (``mes-*``, ``mon-*``,
``ma-*``, ``client/*`` et ``ressources``) doit avoir (1) un appelant dans
``frontend/src/api/portailApi.js`` — l'URL ``/portail/<route>`` y figure — et
(2) cet appelant (sa propriété ``portailApi.<groupe>.<fonction>``) doit être
UTILISÉ par au moins un fichier non-test de ``frontend/src/features/portail/``.
Sinon la route est une surface sans écran (au rapport d'audit : 264 « sans écran
par oubli » dont celles du portail).

``check_ecrans_atteignables`` voit « écran ↔ menu », pas « route ↔ appelant API » ;
``rapport_backend_sombre`` est NON bloquant. Ce script est la porte BLOQUANTE du
portail.

Liste d'exceptions ``scripts/portail_surfaces_allow.txt`` (une route par ligne,
ex. ``mes-factures-fournisseur``) : surfaces volontairement sans écran (GATED,
ADOC149). Cliquet : une ligne devenue inutile (la route a un écran, ou n'existe
plus) fait AUSSI échouer.

Usage :
    python scripts/check_portail_surfaces.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
URLS_PATH = ROOT / "backend" / "django_core" / "apps" / "portail" / "urls.py"
API_PATH = ROOT / "frontend" / "src" / "api" / "portailApi.js"
FEATURES_DIR = ROOT / "frontend" / "src" / "features" / "portail"
ALLOWLIST_PATH = ROOT / "scripts" / "portail_surfaces_allow.txt"

_REGISTER_RE = re.compile(r"""register\(\s*r?['"]([^'"]+)['"]""")
_PATH_RE = re.compile(r"""\bpath\(\s*['"]([^'"]+)['"]""")
_SELF_SERVICE_RE = re.compile(r"^(?:mes-|mon-|ma-|client/|ressources$)")


def routes_self_service(texte: str) -> list:
    """Routes self-service déclarées (``router.register`` + ``path``), sans
    barre finale, dans l'ordre du fichier, sans doublon."""
    vues, out = set(), []
    for rx in (_REGISTER_RE, _PATH_RE):
        for m in rx.finditer(texte):
            route = m.group(1).strip("/")
            if route and route not in vues and _SELF_SERVICE_RE.match(route):
                vues.add(route)
                out.append(route)
    return out


def proprietes_par_route(js: str) -> dict:
    """{route: [chemin de propriété 'groupe.fonction', ...]} lu dans
    ``portailApi.js`` : chaque ligne qui porte l'URL ``/portail/<route>`` est
    rattachée à la propriété qui la contient (groupes d'objets suivis par
    indentation)."""
    pile, derniere, out = [], None, {}
    ouvre = re.compile(r"^(\s*)(\w+):\s*\{\s*(?://.*)?$")
    ferme = re.compile(r"^(\s*)\},?\s*(?://.*)?$")
    cle = re.compile(r"^\s*(\w+):")
    url = re.compile(r"/portail/([\w\-/]+)")
    for ligne in js.splitlines():
        m = ouvre.match(ligne)
        if m:
            pile.append((len(m.group(1)), m.group(2)))
            derniere = None
            continue
        m = ferme.match(ligne)
        if m and pile and len(m.group(1)) == pile[-1][0]:
            pile.pop()
            derniere = None
            continue
        m = cle.match(ligne)
        if m:
            derniere = m.group(1)
        for u in url.finditer(ligne):
            chemin = ".".join([k for _, k in pile] + ([derniere] if derniere else []))
            segments = u.group(1).strip("/")
            # une URL peut porter /<id>/<action>/ : on l'associe a chaque
            # prefixe de route possible (verifie ensuite contre les routes).
            parts = segments.split("/")
            for n in range(1, len(parts) + 1):
                out.setdefault("/".join(parts[:n]), set()).add(chemin)
    return {r: sorted(p) for r, p in out.items()}


def _texte_features() -> str:
    morceaux = []
    if FEATURES_DIR.is_dir():
        for chemin in sorted(FEATURES_DIR.rglob("*")):
            if chemin.suffix not in (".js", ".jsx", ".mjs"):
                continue
            if ".test." in chemin.name or chemin.name.endswith(".test.mjs"):
                continue
            try:
                morceaux.append(chemin.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                continue
    return "\n".join(morceaux)


def propriete_utilisee(chemin: str, texte: str) -> bool:
    if not chemin:
        return False
    return re.search(r"portailApi\." + re.escape(chemin) + r"(?![\w])", texte) is not None


def surfaces_sans_ecran() -> list:
    """[(route, motif)] des routes self-service sans appelant API utilisé."""
    if not URLS_PATH.is_file():
        return []
    routes = routes_self_service(URLS_PATH.read_text(encoding="utf-8"))
    api_js = API_PATH.read_text(encoding="utf-8") if API_PATH.is_file() else ""
    props = proprietes_par_route(api_js)
    texte = _texte_features()
    out = []
    for route in routes:
        chemins = props.get(route, [])
        if not chemins:
            out.append((route, "aucun appelant dans portailApi.js"))
        elif not any(propriete_utilisee(c, texte) for c in chemins):
            out.append((route, "appelant portailApi.js jamais utilisé par un écran "
                               f"({', '.join(chemins)})"))
    return out


def _load_allowlist() -> set:
    if not ALLOWLIST_PATH.is_file():
        return set()
    out = set()
    for ligne in ALLOWLIST_PATH.read_text(encoding="utf-8").splitlines():
        ligne = ligne.split("#", 1)[0].strip()
        if ligne:
            out.add(ligne.strip("/"))
    return out


def main() -> int:
    sans = surfaces_sans_ecran()
    allow = _load_allowlist()
    nouveaux = [(r, m) for r, m in sans if r not in allow]
    morts = sorted(allow - {r for r, _ in sans})
    if nouveaux:
        print("check_portail_surfaces : route portail self-service SANS écran :")
        for route, motif in nouveaux:
            print(f"  - {route} — {motif}")
        print("Livrez l'écran (portailApi.js + features/portail) ou, surface "
              "volontairement GATED, ajoutez la route à "
              "scripts/portail_surfaces_allow.txt.")
    if morts:
        print("check_portail_surfaces : lignes INUTILES de "
              "scripts/portail_surfaces_allow.txt (la route a un écran ou n'existe "
              "plus — retirez-les, cliquet décroissant) :")
        for route in morts:
            print(f"  - {route}")
    if nouveaux or morts:
        return 1
    print(f"check_portail_surfaces : OK — {len(allow)} surface(s) GATED "
          "listée(s), aucune route self-service sans écran.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Carte de l'ERP pour l'assistant IA — GÉNÉRÉE depuis le code, jamais à la main.

L4 assistant (Reda, 21/11/2026) : « some file like codemap should make the ai agent always aware ». Le manuel
(`backend/fastapi_ia/assistant/manuel.md`) dit les PROCÉDURES et se régénère par un skill ; cette carte dit ce
qui EXISTE (écrans et menus, actions de l'assistant, droits par rôle), lue dans le code par ce script déterministe
(aucun modèle), comme CODEMAP. La CI rejoue `--check` : un écran, une action ou un droit ajouté sans régénérer la
carte rend le job rouge.

Sources (lues comme du TEXTE, sans Django ni Node) :
  * menus : `frontend/src/features/*/module.config.jsx` (section `nav`, entrées `{ to, label, roles }`) ;
  * écrans et titres : `frontend/src/components/layout/routes.meta.js` (`['/chemin', 'Titre']`) et les
    `{ path: '/…' }` des modules et de `frontend/src/router/index.jsx` ;
  * actions : `backend/django_core/apps/*/agent_actions.py` et `apps/agent/registry.py` (AST : `AgentAction(...)`),
    `ACTIONS_DIRECTES` (D-COP-5) ;
  * rôles : `backend/django_core/apps/roles/golden/registre_permissions.json` (rôles système → codes, module de
    chaque code), golden gardé à jour par les tests de `apps/roles`.

Usage :
    python scripts/assistant_carte_erp.py            # écrit la carte
    python scripts/assistant_carte_erp.py --check    # 1 si la carte n'est pas à jour
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
FRONT = RACINE / "frontend" / "src"
DJANGO = RACINE / "backend" / "django_core"
SORTIE = RACINE / "backend" / "fastapi_ia" / "assistant" / "carte_erp.md"

#: Droits SENSIBLES dits par rôle (l'assistant redit ce qu'un rôle ne voit pas).
DROITS_SENSIBLES = ("prix_achat_voir", "marge_voir", "encaisser", "client_pii_voir",
                    "users_gerer", "roles_gerer")
#: Rôles portail : servis par un autre écran, jamais par l'assistant interne.
ROLES_EXCLUS_PREFIXE = ("Portail",)
#: Écrans hors application (publics, techniques).
CHEMINS_EXCLUS = re.compile(r"^/(landing|login|register|ui|reset|public|p/|proposition|$)")

_NAV_SECTION = re.compile(r"nav:\s*\{\s*label:\s*'([^']+)'")
_NAV_ITEM = re.compile(r"\{\s*to:\s*'([^']+)',\s*label:\s*'([^']+)'[^}]*?(?:roles:\s*\[([^\]]*)\])?[^}]*\}")
_TITRE = re.compile(r"\[\s*'(/[^']*)'\s*,\s*'([^']+)'\s*\]")
_CHEMIN = re.compile(r"path:\s*'(/[^']*)'")


def _lire(chemin: Path) -> str:
    return chemin.read_text(encoding="utf-8")


def menus() -> list[tuple[str, list[tuple[str, str, str]]]]:
    """[(section, [(chemin, libellé, rôles)])] dans l'ordre des fichiers de module."""
    sections = []
    for fichier in sorted(FRONT.glob("features/*/module.config.jsx")):
        texte = _lire(fichier)
        section = _NAV_SECTION.search(texte)
        if not section:
            continue
        debut = section.start()
        items = []
        for m in _NAV_ITEM.finditer(texte, debut):
            roles = ",".join(r.strip().strip("'\"") for r in (m.group(3) or "").split(",") if r.strip())
            items.append((m.group(1), m.group(2), roles))
        if items:
            sections.append((section.group(1), items))
    return sections


_ONGLET = re.compile(r"\{\s*key:\s*'([a-z_]+)',\s*label:\s*'([^']+)'")


def onglets_parametres() -> list[tuple[str, str]]:
    """Onglets de `/parametres` (« où je change X ? ») : `peConstants.js` et `ParametresEntreprise.jsx`."""
    vus = {}
    for nom in ("peConstants.js", "ParametresEntreprise.jsx"):
        for cle, libelle in _ONGLET.findall(_lire(FRONT / "pages/parametres" / nom)):
            vus.setdefault(cle, libelle)
    return sorted(vus.items(), key=lambda kv: kv[1].lower())


def titres() -> dict[str, str]:
    titres_ = {}
    for fichier in [FRONT / "components/layout/routes.meta.js", *sorted(FRONT.glob("features/*/module.config.jsx"))]:
        for chemin, titre in _TITRE.findall(_lire(fichier)):
            titres_.setdefault(chemin, titre)
    return titres_


def chemins() -> list[str]:
    vus = set()
    for fichier in [FRONT / "router/index.jsx", *sorted(FRONT.glob("features/*/module.config.jsx"))]:
        vus.update(_CHEMIN.findall(_lire(fichier)))
    return sorted(c for c in vus if not CHEMINS_EXCLUS.match(c))


def _valeur(noeud):
    try:
        return ast.literal_eval(noeud)
    except (ValueError, SyntaxError):
        return None


def _nom(noeud) -> str:
    return getattr(noeud, "id", None) or getattr(noeud, "attr", None) or ""


def actions() -> list[dict]:
    fichiers = sorted(DJANGO.glob("apps/*/agent_actions.py")) + [DJANGO / "apps/agent/registry.py"]
    vues = {}
    for fichier in fichiers:
        arbre = ast.parse(_lire(fichier))
        for noeud in ast.walk(arbre):
            if not (isinstance(noeud, ast.Call) and _nom(noeud.func) == "AgentAction"):
                continue
            kw = {k.arg: k.value for k in noeud.keywords if k.arg}
            cle = _valeur(kw["key"]) if "key" in kw else None
            if not isinstance(cle, str):
                continue
            methode = _valeur(kw["method"]) if "method" in kw else "GET"
            risque = _nom(kw["risk"]).replace("RISK_", "").lower() if "risk" in kw else "internal"
            vues[cle] = {
                "cle": cle,
                "libelle": _valeur(kw.get("label")) or cle,
                "methode": str(methode or "GET").upper(),
                "risque": risque or "internal",
                "permission": _valeur(kw.get("required_permission")) if "required_permission" in kw else None,
                "lecture": bool(_valeur(kw.get("lecture"))) if "lecture" in kw else False,
            }
    directes = _directes()
    for action in vues.values():
        action["geste"] = _geste(action, directes)
    return sorted(vues.values(), key=lambda a: a["cle"])


def _directes() -> set[str]:
    arbre = ast.parse(_lire(DJANGO / "apps/agent/registry.py"))
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Assign) and any(_nom(c) == "ACTIONS_DIRECTES" for c in noeud.targets):
            return set(_valeur(noeud.value.args[0]) or ())
    return set()


def _geste(action: dict, directes: set[str]) -> str:
    if action["methode"] == "GET" or action["lecture"]:
        return "lit"
    if action["risque"] == "internal" or (action["risque"] == "outward" and action["cle"] in directes):
        return "fait"
    return "carte"


def roles() -> tuple[list[tuple[str, list[str]]], dict[str, str]]:
    golden = json.loads(_lire(DJANGO / "apps/roles/golden/registre_permissions.json"))
    systeme = [(nom, sorted(codes)) for nom, codes in golden["registres_roles"]["CANONICAL_SYSTEM_ROLES"]
               if not nom.startswith(ROLES_EXCLUS_PREFIXE)]
    return systeme, golden["dicts"]["PERMISSION_MODULE"]


def carte() -> str:
    lignes = [
        "# Carte de l'ERP TAQINOR (générée — ne pas modifier à la main)",
        "",
        "Générée par `scripts/assistant_carte_erp.py` depuis le code (menus, écrans, actions de l'assistant, droits",
        "par rôle). Elle dit ce qui EXISTE ; le manuel dit comment s'en servir. Un écran absent d'ici n'existe pas :",
        "ne l'invente jamais. Gestes de l'assistant : `lit` (lecture), `fait` (exécuté directement), `carte`",
        "(proposition que l'utilisateur confirme). Un outil absent du catalogue de l'utilisateur lui est INTERDIT",
        "par son rôle : dis-lui quel droit manque et qui peut le donner (un administrateur), sans contourner.",
        "",
        "## 1. Menus (section → écran : libellé [rôles d'accès historiques])",
    ]
    for section, items in menus():
        lignes.append(f"- **{section}** : " + " ; ".join(
            f"`{c}` {l}" + (f" [{r}]" if r and r != "normal,responsable,admin" else "") for c, l, r in items))
    lignes += ["", "## 2. Tous les écrans de l'application (chemin — titre)"]
    titres_ = titres()
    lignes.append(" ; ".join(f"`{c}`" + (f" {titres_[c]}" if c in titres_ else "") for c in chemins()))
    lignes += ["", "## 2 bis. Onglets de `/parametres` (« où je change … ? » ; chaque onglet suit les droits du rôle)"]
    lignes.append(" ; ".join(f"{libelle} (`/parametres?onglet={cle}`)" for cle, libelle in onglets_parametres()))
    lignes += ["", "## 3. Actions de l'assistant par domaine (clé — libellé — geste — droit requis)"]
    par_domaine: dict[str, list[dict]] = {}
    for a in actions():
        par_domaine.setdefault(a["cle"].split(".")[0], []).append(a)
    for domaine in sorted(par_domaine):
        lignes.append(f"- **{domaine}** : " + " ; ".join(
            f"`{a['cle']}` {a['libelle']} ({a['geste']}" + (f", {a['permission']}" if a["permission"] else "") + ")"
            for a in par_domaine[domaine]))
    systeme, module_de = roles()
    lignes += ["", "## 4. Rôles système : modules ouverts et droits sensibles",
               "Un utilisateur n'obtient de l'assistant QUE ce que son rôle permet à l'écran ; un droit sensible",
               "absent = la donnée ne se donne pas (ni chiffre, ni estimation, ni calcul à partir d'autres chiffres)."]
    for nom, codes in systeme:
        modules = sorted({module_de[c] for c in codes if c in module_de})
        sensibles = [d for d in DROITS_SENSIBLES if d in codes]
        sans = [d for d in ("prix_achat_voir", "marge_voir") if d not in codes]
        lignes.append(f"- **{nom}** : modules {', '.join(modules) or 'aucun'} ; droits sensibles "
                      f"{', '.join(sensibles) or 'aucun'}" + (f" ; SANS {', '.join(sans)}" if sans else ""))
    return "\n".join(lignes) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="échoue si la carte n'est pas à jour")
    args = parser.parse_args(argv)
    attendu = carte()
    if args.check:
        actuel = SORTIE.read_text(encoding="utf-8") if SORTIE.exists() else ""
        if actuel != attendu:
            print("ECHEC : backend/fastapi_ia/assistant/carte_erp.md n'est plus à jour avec le code (écran, action "
                  "ou droit ajouté, retiré ou renommé).\nRégénérer : python scripts/assistant_carte_erp.py")
            return 1
        print(f"OK : carte de l'ERP à jour ({len(attendu)} caractères).")
        return 0
    SORTIE.write_text(attendu, encoding="utf-8", newline="\n")
    print(f"Carte écrite : {SORTIE.name} ({len(attendu)} caractères).")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Rapport MENSUEL « backend sombre » — NON BLOQUANT, jamais un rouge de CI.

POURQUOI CE N'EST PAS UNE GARDE (PACT27)
----------------------------------------
La classe « le backend existe, l'ecran manque » SUR-COMPTE structurellement, et
ce n'est pas un defaut de reglage : c'est une limite de principe de la mesure.
Trois familles entieres de ressources sont servies SANS qu'aucun `axios.get`
n'existe nulle part dans `frontend/src` — donc AUCUN extracteur d'appels ne les
verra jamais :

  * les portails PUBLICS ouverts par un lien (le client clique une URL recue par
    courriel, il n'y a pas d'ecran ERP en face) ;
  * les flux `calendar.ics` colles dans un agenda tiers (Google/Outlook les
    telecharge, pas le navigateur de l'utilisateur) ;
  * les PDF / exports ouverts par `window.open(...)` ou un `<a href>` direct.

En faire un rouge de CI reviendrait a exiger la suppression de fonctionnalites
CORRECTES, ou a couvrir la garde d'exceptions jusqu'a la rendre muette. Ce
fichier est donc un RAPPORT : il s'execute a la main, il imprime un chiffre, et
il rend TOUJOURS 0.

CE QU'IL APPORTE PAR RAPPORT AU BRUT
------------------------------------
Il applique au niveau ENDPOINT la distinction que `scripts/check_modules.py`
fait deja au niveau APP : une ressource declaree VOLONTAIREMENT sans ecran porte
un marqueur machine dans son `urls.py` :

    # headless: portail public ouvert par lien signe, aucun ecran ERP en face
    router.register('portail-devis', PortailDevisViewSet, basename='portail-devis')

Le marqueur se pose sur la ligne PRECEDANT la declaration (ou sur la meme
ligne). Sa raison est libre mais OBLIGATOIRE : un marqueur nu est refuse par le
rapport lui-meme (il serait un interrupteur, pas une intention).

Le chiffre PUBLIE est celui de la dette reelle — « sans ecran par OUBLI » —
jamais le brut. Le brut melange une dette a arbitrer avec des choix
d'architecture assumes, et un chiffre qui melange les deux ne se corrige pas :
il se subit.

Usage :
    python scripts/rapport_backend_sombre.py            # rapport lisible
    python scripts/rapport_backend_sombre.py --details  # + la liste complete
    python scripts/rapport_backend_sombre.py --json     # sortie machine
"""
from __future__ import annotations

import argparse
import ast
import json
import re
from pathlib import Path

import check_api_contract as contract
from check_api_contract import ANY, ROOT, normalise_route

APPS_ROOT = ROOT / "backend" / "django_core" / "apps"

# `# headless: <raison>` — la raison est obligatoire (au moins 3 caracteres).
MARQUEUR = re.compile(r"#\s*headless\s*:\s*(?P<raison>.*)$")
# Un marqueur nu (`# headless:`) n'est pas une intention : il est refuse.
RAISON_MINIMALE = 3


# ===========================================================================
# 1. Inventaire des ressources backend, avec leur module d'origine
# ===========================================================================

class InventaireRoutes(contract.BackendRoutes):
    """`BackendRoutes` + l'origine (module, ligne, litteral) de chaque ressource.

    La garde de contrat n'a pas besoin de savoir OU une ressource est declaree ;
    ce rapport, si : c'est la ligne du `urls.py` qui porte le marqueur
    d'intention.
    """

    def __init__(self):
        super().__init__()
        # chemin normalise (tuple) -> (module dotted, ligne, litteral brut)
        self.origines: dict[tuple, tuple] = {}

    def _routers(self, tree):
        """Comme le parent, mais chaque enregistrement garde son numero de ligne."""
        routers: dict[str, list] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if (isinstance(target, ast.Name) and isinstance(node.value, ast.Call)
                            and contract._call_name(node.value).endswith("Router")):
                        routers.setdefault(target.id, [])
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                    and node.func.attr == "register" and isinstance(node.func.value, ast.Name):
                var = node.func.value.id
                if not node.args:
                    continue
                prefix = contract._const_str(node.args[0])
                viewset = None
                if len(node.args) > 1:
                    target = node.args[1]
                    if isinstance(target, ast.Name):
                        viewset = target.id
                    elif isinstance(target, ast.Attribute):
                        viewset = target.attr
                routers.setdefault(var, []).append((prefix, viewset, node.lineno))
        return routers

    def _expand_router(self, registered, prefix, module):
        allege = []
        for raw, viewset, ligne in registered:
            allege.append((raw, viewset))
            if raw is None:
                continue
            segments, opaque = normalise_route(raw)
            if opaque:
                continue
            self.origines[prefix + tuple(segments)] = (module, ligne, raw)
        super()._expand_router(allege, prefix, module)


def _litteraux_de_module(module: str, tree) -> dict:
    """ligne -> litteral de chemin declare par un `path()`/`re_path()`."""
    out = {}
    if tree is None:
        return out
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and contract._call_name(node) in ("path", "re_path") \
                and node.args:
            litteral = contract._const_str(node.args[0])
            if litteral is not None:
                out[node.lineno] = litteral
    return out


# ===========================================================================
# 2. Marqueurs d'intention `# headless: <raison>`
# ===========================================================================

def marqueurs(racine: Path = None) -> tuple:
    """({(fichier, ligne de la declaration): raison}, [(fichier, ligne, probleme)]).

    Le marqueur vaut pour la declaration posee sur la MEME ligne (avant le
    `#`), sinon pour la premiere ligne non vide qui suit. C'est la LIGNE de la
    declaration qui sert de cle : elle est exacte, la ou un appariement par
    prefixe litteral confondrait deux enregistrements homonymes.
    """
    racine = APPS_ROOT if racine is None else racine
    trouves: dict[tuple, str] = {}
    problemes: list = []
    if not racine.is_dir():
        return trouves, problemes
    for fichier in sorted(racine.glob("*/urls.py")):
        lignes = fichier.read_text(encoding="utf-8", errors="replace").splitlines()
        relatif = (fichier.relative_to(ROOT).as_posix()
                   if fichier.is_relative_to(ROOT) else fichier.as_posix())
        for index, ligne in enumerate(lignes):
            trouve = MARQUEUR.search(ligne)
            if not trouve:
                continue
            raison = trouve.group("raison").strip()
            if len(raison) < RAISON_MINIMALE:
                problemes.append((relatif, index + 1,
                                  "marqueur `# headless:` sans raison — un "
                                  "marqueur nu est un interrupteur, pas une "
                                  "intention"))
                continue
            cible = None
            if re.search(r"""['"]""", ligne[:trouve.start()]):
                cible = index + 1
            else:
                for decalage, suivante in enumerate(lignes[index + 1:index + 4]):
                    if suivante.strip():
                        cible = index + 2 + decalage
                        break
            if cible is None:
                problemes.append((relatif, index + 1,
                                  "marqueur `# headless:` qui ne precede aucune "
                                  "declaration de route lisible"))
                continue
            trouves[(relatif, cible)] = raison
    return trouves, problemes


# ===========================================================================
# 3. Appels du frontend -> quelles ressources sont VUES par un ecran
# ===========================================================================

def chemins_appeles() -> set:
    extracteur = contract.FrontendCalls(contract.frontend_files())
    extracteur.collect()
    appels = set()
    for _, _, brut, mount in extracteur.calls:
        chemin = contract.normalise_call(brut, mount)
        if chemin is not None:
            appels.add(chemin)
    return appels


def _couvre(base: tuple, appel: tuple) -> bool:
    """L'appel frontend touche-t-il CETTE ressource (elle ou une sous-route) ?"""
    if len(appel) < len(base):
        return False
    return all(a == b or a == ANY or b == ANY for a, b in zip(appel, base))


# ===========================================================================
# 4. Le rapport
# ===========================================================================

def analyser():
    backend = InventaireRoutes()
    backend.build()
    poses, problemes = marqueurs()
    appels = chemins_appeles()

    # Ressources = bases de routeur + vues `path()` autonomes. On ecarte les
    # sous-routes (@action) : une @action n'est pas une ressource, elle suit
    # l'ecran de sa ressource.
    ressources: dict[tuple, tuple] = {}
    for base, (module, ligne, litteral) in backend.origines.items():
        ressources[base] = (module, ligne, litteral, "routeur")
    bases_routeur = set(ressources)
    for route, (module, _reference) in backend.views.items():
        if any(route[:len(base)] == base for base in bases_routeur if len(base) < len(route)):
            continue
        if route in ressources:
            continue
        _, tree = backend._module(module)
        litteraux = _litteraux_de_module(module, tree)
        ligne, litteral = 0, ""
        for candidat_ligne, candidat in sorted(litteraux.items()):
            segments, opaque = normalise_route(candidat)
            if opaque:
                continue
            if tuple(segments) and route[-len(segments):] == tuple(segments):
                ligne, litteral = candidat_ligne, candidat
                break
        ressources[route] = (module, ligne, litteral, "vue")

    # Une meme DECLARATION est servie sous plusieurs montages (`/api/django/…`
    # ET `/api/v1/…`). Elle ne compte qu'UNE fois : un alias de montage ne
    # double pas la dette, il la duplique a l'affichage.
    declarations: dict[tuple, dict] = {}
    for base in sorted(ressources):
        module, ligne, litteral, nature = ressources[base]
        fichier = _fichier_de_module(backend, module) or module
        cle = (fichier, ligne) if ligne else (fichier, litteral or base)
        entree = declarations.setdefault(cle, {
            "chemins": [],
            "fichier": fichier,
            "ligne": ligne,
            "nature": nature,
            "vue_par_un_ecran": False,
            "raison": poses.get((fichier, ligne)) if ligne else None,
        })
        entree["chemins"].append("/" + "/".join(base))
        if any(_couvre(base, appel) for appel in appels):
            entree["vue_par_un_ecran"] = True

    par_design, par_oubli, eclairees = [], [], 0
    for _, entree in sorted(declarations.items(), key=lambda item: str(item[0])):
        if entree["vue_par_un_ecran"]:
            eclairees += 1
            continue
        entree["chemin"] = entree["chemins"][0]
        (par_design if entree["raison"] else par_oubli).append(entree)

    return {
        "declarations": len(declarations),
        "eclairees": eclairees,
        "sans_ecran_par_design": par_design,
        "sans_ecran_par_oubli": par_oubli,
        "marqueurs_invalides": problemes,
    }


def _fichier_de_module(backend, module: str) -> str | None:
    chemin = backend._module(module)[0]
    if chemin is None:
        return None
    return Path(chemin).relative_to(ROOT).as_posix()


def imprimer(rapport: dict, details: bool) -> None:
    design = rapport["sans_ecran_par_design"]
    oubli = rapport["sans_ecran_par_oubli"]
    print("RAPPORT MENSUEL « backend sombre » — non bloquant (PACT27)")
    print("=" * 66)
    print(f"Declarations de ressource inventoriees : {rapport['declarations']}")
    print(f"  dont touchees par un ecran         : {rapport['eclairees']}")
    print(f"  dont SANS ECRAN PAR DESIGN         : {len(design)}"
          "   (marqueur `# headless:`, hors decompte)")
    print()
    print(f"  >>> DETTE PUBLIEE — sans ecran par OUBLI : {len(oubli)}")
    print()
    print("Le chiffre a publier est celui de la DETTE, jamais le brut "
          f"({len(design) + len(oubli)}) : ce dernier melange une dette a "
          "arbitrer\navec des choix d'architecture assumes (portails publics, "
          "flux .ics, PDF ouverts\npar window.open) qu'aucun extracteur "
          "d'appels axios ne pourra jamais voir.")

    if rapport["marqueurs_invalides"]:
        print()
        print("MARQUEURS INVALIDES (corriger — ils ne comptent pas comme une intention) :")
        for fichier, ligne, motif in rapport["marqueurs_invalides"]:
            print(f"  {fichier}:{ligne}  {motif}")

    if details:
        print()
        print(f"--- Sans ecran PAR DESIGN ({len(design)}) ---")
        for entree in design:
            print(f"  {entree['chemin']}")
            print(f"      {entree['fichier']}:{entree['ligne']} — {entree['raison']}")
        print()
        print(f"--- Sans ecran par OUBLI ({len(oubli)}) — la dette a arbitrer ---")
        for entree in oubli:
            print(f"  {entree['chemin']}   ({entree['fichier']}:{entree['ligne']})")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Rapport mensuel non bloquant des ressources backend sans ecran.")
    parser.add_argument("--details", action="store_true",
                        help="liste chaque ressource des deux categories")
    parser.add_argument("--json", action="store_true",
                        help="sortie machine (pour un tableau de bord)")
    args = parser.parse_args(argv)

    rapport = analyser()
    if args.json:
        print(json.dumps(rapport, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        imprimer(rapport, args.details)
    # RAPPORT, PAS GARDE : il ne rend jamais autre chose que 0.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

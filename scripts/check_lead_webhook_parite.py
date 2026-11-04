#!/usr/bin/env python3
"""QJR230 — PARITE MACHINE entre le contrat du tunnel et la lecture du webhook.

LE DEFAUT QUE CETTE GARDE FERME
-------------------------------
La correspondance « site -> CRM » a deux moities qui ne partagent aucun
fichier, aucun langage et aucune lane :

  * le REGISTRE du tunnel — `apps/web/src/lib/tunnel/champs.ts`, 69
    descripteurs — decide des noms de cles emis dans le corps du lead ;
  * la LECTURE — `apps/crm/webhooks.py::_map_payload_to_fields` (aide de
    `_extract_web_questionnaire`) — 350 lignes ecrites a la main, sans
    aucune parite machine avec le registre.

Une cle pouvait donc survivre a toute la chaine web et se PERDRE SANS TRACE a
l'arrivee : rien ne rougissait, ni cote site, ni cote CRM. C'est l'incident
PACT10 du 03/08/2026 rejoue sur la surface la plus visible du parcours.

CE QUE LA GARDE LIT — ET CE QU'ELLE NE LIT JAMAIS
-------------------------------------------------
Elle NOMME les deux cotes, mais elle ne lit JAMAIS le `.ts` directement (aucun
outil de ce depot ne lit le TypeScript, et en ecrire un ici serait un second
resolveur a maintenir). Le porteur qui apparie les deux moities est le contrat
committe `apps/crm/contract_samples/tunnel_webhook_keys.json` (QJR229), dont
les 69 cles sont DERIVEES du registre — la commande de regeneration est ecrite
dans son `notes.regeneration`. La garde compare donc :

    contrat committe   <->   `apps/crm/webhooks.py` lu en AST

CE QUE LA GARDE NE CONTROLE PAS, ET POURQUOI C'EST ECRIT ICI
------------------------------------------------------------
La direction inverse « une cle LUE par le code mais absente du contrat » n'est
PAS un rouge, et ce n'est pas un oubli : le webhook tolere aujourd'hui 92 cles
hors registre (mesure de cette garde le 31/08/2026) — jumeaux snake_case des
questions du tunnel, alias historiques (`phoneE164`, `marketMode`, `billKwh`,
`occupantType`, `projectTiming`…) et cles posees hors registre par
`buildLeadRecord` (`consentTimestamp`, `band`, `page`). En faire un rouge
exigerait une liste d'exclusion de 92 entrees qui se perimerait au premier
alias ajoute : la classe de panne « liste epinglee » que ce depot a deja payee
plusieurs fois. La moitie « le registre a une cle de plus que le contrat » se
verifie par la commande de regeneration du contrat, pas ici.

CE QUI EST UN ROUGE
-------------------
1. Une cle que le contrat declare TRAITEE (`colonne_lead` / `web_questionnaire`)
   et que le mapping ne lit pas — le defaut d'origine : une cle ajoutee au
   contrat que personne n'a cablee.
2. Une cle que le contrat declare REFUSEE (`refus`) et que le mapping lit
   quand meme — un refus qui n'est plus tenu.
3. Une cle que le contrat declare lue PAR LA VUE (`vue`) et que le mapping
   lit, ou qu'aucune fonction du module ne lit plus — une declaration qui ne
   verifie plus rien.
4. Un contrat incoherent avec lui-meme (destination inconnue, `champ_lead`
   manquant ou pose sur un refus).

Une cle deliberement ignoree s'ecrit DANS LE CONTRAT avec sa raison, jamais
par omission.

Usage : `python scripts/check_lead_webhook_parite.py`
Stdlib pure : ni base de donnees, ni docker, ni Django, ni node.
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEBHOOKS = ROOT / "backend" / "django_core" / "apps" / "crm" / "webhooks.py"
CONTRAT = (ROOT / "backend" / "django_core" / "apps" / "crm"
           / "contract_samples" / "tunnel_webhook_keys.json")

#: Les deux fonctions qui transforment le corps du site en champs `crm.Lead`.
#: `_map_payload_to_fields` APPELLE `_extract_web_questionnaire` : lire l'une
#: sans l'autre declarerait « non traitees » les 17 cles du questionnaire.
FONCTIONS_MAPPING = ("_map_payload_to_fields", "_extract_web_questionnaire")

#: Le nom du dictionnaire de charge utile dans ces fonctions.
PORTEURS = ("data",)

#: Les trois aides locales de `_extract_web_questionnaire`. Leurs DEUX premiers
#: arguments sont des noms de cles du payload : `_num('surfaceM2',
#: 'surface_m2')` lit `data.get('surfaceM2', data.get('surface_m2'))`.
AIDES = ("_num", "_choice", "_bool")

COLONNE = "colonne_lead"
BLOB = "web_questionnaire"
VUE = "vue"
REFUS = "refus"
TRAITEES = (COLONNE, BLOB)
DESTINATIONS = (COLONNE, BLOB, VUE, REFUS)


# ===========================================================================
# 1. Lecture AST : quelles cles du payload une fonction lit-elle ?
# ===========================================================================

def _texte(noeud):
    if isinstance(noeud, ast.Constant) and isinstance(noeud.value, str):
        return noeud.value
    return None


def _cles_de_boucle(noeud: ast.For) -> set:
    """`for key in ('utm_source', …): … data.get(key)` -> les cles du tuple.

    Etroit a dessein : il faut un tuple/liste de chaines LITTERALES, une
    variable de boucle simple, et un `data.get(<variable>)` dans le corps. Une
    boucle qui `pop()` un blob (`questionnaire.pop(equip_key)`) n'est PAS une
    lecture de payload et n'entre jamais ici.
    """
    if not isinstance(noeud.target, ast.Name) \
            or not isinstance(noeud.iter, (ast.Tuple, ast.List)):
        return set()
    valeurs = [_texte(element) for element in noeud.iter.elts]
    if not valeurs or any(valeur is None for valeur in valeurs):
        return set()
    variable = noeud.target.id
    for sous in ast.walk(noeud):
        if isinstance(sous, ast.Call) and isinstance(sous.func, ast.Attribute) \
                and sous.func.attr == "get" \
                and isinstance(sous.func.value, ast.Name) \
                and sous.func.value.id in PORTEURS and sous.args \
                and isinstance(sous.args[0], ast.Name) \
                and sous.args[0].id == variable:
            return set(valeurs)
    return set()


def cles_lues(noeud) -> set:
    """Les cles du payload que CETTE fonction lit, par lecture AST."""
    lues = set()
    for sous in ast.walk(noeud):
        if isinstance(sous, ast.Call):
            fonction = sous.func
            if isinstance(fonction, ast.Attribute) and fonction.attr == "get" \
                    and isinstance(fonction.value, ast.Name) \
                    and fonction.value.id in PORTEURS and sous.args:
                # `data.get('X')` ; `data.get('X', data.get('Y'))` — le second
                # argument est un DEFAUT, lui-meme visite par ast.walk.
                valeur = _texte(sous.args[0])
                if valeur:
                    lues.add(valeur)
            elif isinstance(fonction, ast.Name) and fonction.id in AIDES:
                for argument in sous.args[:2]:
                    valeur = _texte(argument)
                    if valeur:
                        lues.add(valeur)
        elif isinstance(sous, ast.Subscript) \
                and isinstance(sous.value, ast.Name) \
                and sous.value.id in PORTEURS:
            valeur = _texte(sous.slice)
            if valeur:
                lues.add(valeur)
        elif isinstance(sous, ast.Compare) and len(sous.ops) == 1 \
                and isinstance(sous.ops[0], ast.In) and sous.comparators \
                and isinstance(sous.comparators[0], ast.Name) \
                and sous.comparators[0].id in PORTEURS:
            valeur = _texte(sous.left)
            if valeur:
                lues.add(valeur)
        elif isinstance(sous, ast.For):
            lues |= _cles_de_boucle(sous)
    return lues


def lectures(source: str) -> tuple:
    """(cles lues par le mapping, cles lues par TOUT le module)."""
    arbre = ast.parse(source)
    par_fonction = {}
    for noeud in ast.walk(arbre):
        if isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef)):
            par_fonction.setdefault(noeud.name, set()).update(cles_lues(noeud))
    mapping = set()
    absentes = []
    for nom in FONCTIONS_MAPPING:
        if nom not in par_fonction:
            absentes.append(nom)
            continue
        mapping |= par_fonction[nom]
    module = set()
    for valeurs in par_fonction.values():
        module |= valeurs
    return mapping, module, absentes


# ===========================================================================
# 2. La garde
# ===========================================================================

def constats(contrat: dict, source: str) -> list:
    """[(cle, motif francais)] — tout ce qui a rompu la parite."""
    trouves = []
    cles = (contrat or {}).get("cles")
    if not isinstance(cles, dict) or not cles:
        return [("<contrat>",
                 "le contrat ne porte aucune table `cles` : "
                 f"regenerer {_relatif(CONTRAT)} (voir son `notes.regeneration`)")]

    mapping, module, absentes = lectures(source)
    for nom in absentes:
        trouves.append((
            f"<{nom}>",
            f"la fonction `{nom}` a disparu de {_relatif(WEBHOOKS)} : la garde "
            "ne peut plus rien verifier. Si elle a ete renommee, mettre a jour "
            "FONCTIONS_MAPPING dans cette garde."))
    if absentes:
        return trouves

    for cle, entree in cles.items():
        if not isinstance(entree, dict):
            trouves.append((cle, "l'entree du contrat n'est pas un objet"))
            continue
        destination = entree.get("destination")
        champ = entree.get("champ_lead")
        if destination not in DESTINATIONS:
            trouves.append((
                cle,
                f"destination inconnue {destination!r} : les seules valeurs "
                f"declarables sont {', '.join(DESTINATIONS)}"))
            continue
        if destination in TRAITEES and not champ:
            trouves.append((
                cle,
                f"declaree `{destination}` mais sans `champ_lead` : le contrat "
                "doit NOMMER le champ `crm.Lead` qui recoit la valeur"))
        if destination in (VUE, REFUS) and champ:
            trouves.append((
                cle,
                f"declaree `{destination}` mais elle NOMME un champ "
                f"`crm.Lead` ({champ!r}) : une cle refusee ou lue par la vue "
                "n'atterrit dans aucune colonne"))
        if destination == BLOB and not entree.get("cle_blob"):
            trouves.append((
                cle,
                "declaree `web_questionnaire` mais sans `cle_blob` : le "
                "contrat doit NOMMER la cle sous laquelle la valeur atterrit "
                "dans le blob `Lead.web_questionnaire`"))

        lue = cle in mapping
        if destination in TRAITEES and not lue:
            trouves.append((
                cle,
                f"le contrat la declare traitee (-> `{champ}`) mais "
                "`_map_payload_to_fields` ne la lit NULLE PART : la reponse du "
                "client se perd sans trace a l'arrivee. La cabler, ou la "
                "declarer `refus` DANS LE CONTRAT avec sa raison."))
        if destination == REFUS and lue:
            trouves.append((
                cle,
                "le contrat la declare REFUSEE mais `_map_payload_to_fields` "
                "la lit : le refus n'est plus tenu. Retirer la lecture, ou "
                "changer la declaration du contrat (et sa raison)."))
        if destination == VUE:
            if lue:
                trouves.append((
                    cle,
                    "le contrat la declare lue PAR LA VUE (aucune colonne "
                    "`crm.Lead`) mais `_map_payload_to_fields` la lit : "
                    "declarer `colonne_lead` et NOMMER le champ."))
            elif cle not in module:
                trouves.append((
                    cle,
                    f"le contrat la declare lue par la vue, mais AUCUNE "
                    f"fonction de {_relatif(WEBHOOKS)} ne la lit : la "
                    "declaration ne verifie plus rien. La declarer `refus` "
                    "avec sa raison, ou retablir la lecture."))
    return trouves


def _relatif(chemin: Path) -> str:
    try:
        return chemin.relative_to(ROOT).as_posix()
    except ValueError:  # pragma: no cover - chemin hors depot (tests)
        return chemin.name


def charger(chemin: Path):
    return json.loads(chemin.read_text(encoding="utf-8"))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Parite entre le contrat du tunnel et la lecture du webhook CRM.")
    parser.add_argument("--contrat", default=str(CONTRAT))
    parser.add_argument("--webhooks", default=str(WEBHOOKS))
    args = parser.parse_args(argv)

    try:
        contrat = charger(Path(args.contrat))
    except (OSError, ValueError) as erreur:
        print(f"ECHEC : contrat illisible ({args.contrat}) : {erreur}")
        return 1
    try:
        source = Path(args.webhooks).read_text(encoding="utf-8")
    except OSError as erreur:
        print(f"ECHEC : source illisible ({args.webhooks}) : {erreur}")
        return 1

    trouves = constats(contrat, source)
    if trouves:
        print(f"\nECHEC : {len(trouves)} cle(s) du tunnel ne sont plus en "
              "parite avec la lecture du webhook CRM.\n")
        for cle, motif in sorted(trouves):
            print(f"  {cle}")
            print(f"      {motif}")
        print("\nLe porteur partage des deux moities est "
              f"{_relatif(CONTRAT)} : une cle deliberement ignoree s'y ecrit "
              "AVEC SA RAISON, jamais par omission. Ne desactivez pas cette "
              "garde.")
        return 1

    total = len(contrat.get("cles") or {})
    print(f"OK : {total} cle(s) du registre du tunnel en parite avec "
          f"{_relatif(WEBHOOKS)}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Copilote vague 2 (FND4) — outils par domaine et chargeur ``outils_charger``.

Le moteur natif (claude + copilote allumé SEULEMENT) ne met dans le préfixe du
modèle que le NOYAU (``registry.NOYAU`` côté Django : ``noyau`` au catalogue)
et les outils fixes ; toute autre action d'un domaine connu est DIFFÉRÉE
(``defer_loading``) et s'ouvre par ``outils_charger(domaines=[…])``, qui rend
des blocs ``tool_reference`` SEULS (essai clé réelle FND0 : un texte mêlé est
un 400). Les consignes du domaine (``consignes_domaines``) suivent en bloc
texte APRÈS le ``tool_result``.

Domaine d'une action = premier segment de sa clé (convention des apps), plus
:data:`AUSSI_DANS` (une clé listée dans deux domaines : planifier une visite
ne doit pas coûter deux chargements). Une action d'un domaine hors
:data:`DOMAINES` (``ged``, ``automation``…) n'est jamais différée.

LangChain et Groq n'ont pas de chargeur : rien de ce module ne les concerne.
"""
from __future__ import annotations

import dataclasses
from typing import Optional

from app.services import consignes_domaines

NOM_CHARGEUR = "outils_charger"
DOMAINES_PAR_APPEL = 3

#: Domaines chargeables, dans l'ordre FIXE de l'index (= énumération du chargeur).
DOMAINES = ("crm", "ventes", "calepinage", "visites", "installations", "sav",
            "stock", "reporting", "taches", "adsengine")

#: Une clé listée aussi dans un autre domaine (plan R4 §A.3-14).
AUSSI_DANS = {
    "crm.visite.planifier": ("visites",),
    "crm.visite.message": ("visites",),
    "installations.chantier.commander_besoin": ("stock",),
}

#: Libellés FIXES de l'index (jamais générés).
LIBELLES = {
    "crm": "leads, fiche, suivi et touches, étapes, étiquettes, visite à planifier",
    "ventes": ("catalogue, devis (composer, lignes, taille, remise, PDF), état d'une vente, "
               "factures, impayés, paiements"),
    "calepinage": ("calepinages à traiter, état d'un calepinage, nombre de panneaux qui "
                   "tiennent, simulation, variantes, publication au devis"),
    "visites": ("agenda et charge des visites techniques, compte rendu ; replanifier, annuler, "
                "valider une visite"),
    "installations": ("chantiers (état, blocages, liste), créneaux et planification de la pose, "
                      "interventions, approvisionnement"),
    "sav": ("parc installé d'un client, garanties, tickets : ouvrir, planifier, démarrer, "
            "résoudre, clôturer, noter"),
    "stock": "niveaux de stock, mouvements, commandes fournisseur",
    "reporting": ("chiffre d'affaires d'un mois ou d'une période (signé, facturé, encaissé) — "
                  "toujours par ce domaine, jamais par une requête de données ni une métrique "
                  "sans période ; créances ; diagnostic"),
    "taches": "journée, tâches, projets, rythme",
    "adsengine": "publicité : dépense, annonces, campagnes",
}

ENTETE_INDEX = (
    "OUTILS PAR DOMAINE — une question qui porte sur un de ces domaines se "
    "traite avec SES outils : appelle d'abord outils_charger(domaines=[…]) "
    "(jusqu'à %d domaines en un appel), même si le point du matin, la fiche "
    "d'un lead ou une requête de données semblent suffire — ce ne sont que des "
    "extraits. Un domaine chargé le reste pour toute la conversation :" % DOMAINES_PAR_APPEL)

#: Écran (préfixe de route) -> domaine indiqué dans l'en-tête de tour.
ECRANS = (("/crm", "crm"), ("/ventes", "ventes"), ("/calepinage", "calepinage"),
          ("/visites", "visites"), ("/chantiers", "installations"),
          ("/interventions", "installations"), ("/planification", "installations"),
          ("/ma-journee", "installations"), ("/sav", "sav"), ("/equipements", "sav"),
          ("/stock", "stock"), ("/reporting", "reporting"), ("/rapports", "reporting"),
          ("/approbations", "reporting"), ("/taches", "taches"))


def domaines_de(action: dict) -> tuple:
    """Domaines d'une action du catalogue (vide : jamais différée)."""
    cle = str(action.get("key") or "")
    premier = cle.split(".", 1)[0]
    if premier not in DOMAINES:
        return ()
    return (premier,) + tuple(d for d in AUSSI_DANS.get(cle, ()) if d != premier)


def differer(outils: list, catalogue: list) -> tuple[list, dict]:
    """(outils, {domaine: [noms d'outils différés]}) : ``outils`` (un par action
    du ``catalogue``, même ordre) avec ``differe`` posé sur toute action hors
    du noyau qui a un domaine. Le noyau reste dans le préfixe."""
    sortie, par_domaine = [], {}
    for outil, action in zip(outils, catalogue):
        domaines = () if action.get("noyau") else domaines_de(action)
        for domaine in domaines:
            par_domaine.setdefault(domaine, []).append(outil.nom)
        sortie.append(dataclasses.replace(outil, differe=True) if domaines else outil)
    return sortie, {d: par_domaine[d] for d in DOMAINES if d in par_domaine}


def index_des_domaines(par_domaine: dict) -> str:
    """Bloc système stable (par compte) : une ligne par domaine différé."""
    lignes = [ENTETE_INDEX]
    lignes += ["- %s : %s" % (d, LIBELLES[d]) for d in DOMAINES if d in par_domaine]
    return "\n".join(lignes)


def domaine_de_l_ecran(ecran, par_domaine: dict) -> Optional[str]:
    """Domaine de l'écran ouvert, s'il est différé pour ce compte ; sinon None
    (l'en-tête de tour reste celui d'avant)."""
    if not isinstance(ecran, str):
        return None
    for prefixe, domaine in ECRANS:
        if ecran == prefixe or ecran.startswith((prefixe + "/", prefixe + "?")):
            return domaine if domaine in par_domaine else None
    return None


def _schema(domaines: list) -> dict:
    return {"type": "object", "properties": {"domaines": {
        "type": "array", "items": {"type": "string", "enum": list(domaines)},
        "minItems": 1, "maxItems": DOMAINES_PAR_APPEL, "uniqueItems": True,
        "description": "Domaines dont tu veux les outils (voir OUTILS PAR DOMAINE)."}},
        "required": ["domaines"], "additionalProperties": False}


def outil_charger(par_domaine: dict):
    """L'outil ``outils_charger`` du tour (``hors_budget`` : un appel qui ne
    fait que charger ne compte pas dans les 10 itérations)."""
    from app.services.moteur_natif import OutilNatif, ResultatOutil

    deja: set = set()

    def executer(args):
        demandes = (args or {}).get("domaines")
        demandes = demandes if isinstance(demandes, list) else [demandes]
        inconnus = [str(d)[:40] for d in demandes if d not in par_domaine]
        if inconnus or not demandes or len(demandes) > DOMAINES_PAR_APPEL:
            return ResultatOutil("Domaine inconnu ou trop de domaines : %s. Domaines possibles "
                                 "(%d au plus par appel) : %s." % (
                                     ", ".join(inconnus) or "aucun", DOMAINES_PAR_APPEL,
                                     ", ".join(par_domaine)), erreur=True)
        noms = [n for d in dict.fromkeys(demandes) for n in par_domaine[d]]
        neufs = [n for n in dict.fromkeys(noms) if n not in deja]
        if not neufs:
            return "Déjà chargé dans ce tour : appelle directement ses outils."
        deja.update(neufs)
        apres = [b for d in dict.fromkeys(demandes) for b in consignes_domaines.bloc_consignes(d)]
        return ResultatOutil([{"type": "tool_reference", "tool_name": n} for n in neufs],
                             apres=tuple(apres))

    return OutilNatif(
        NOM_CHARGEUR,
        "Charge les outils d'un à trois domaines de l'ERP (voir OUTILS PAR DOMAINE) ; "
        "ensuite appelle-les directement. Inutile de recharger un domaine déjà chargé "
        "dans cette conversation.",
        _schema(list(par_domaine)), executer, hors_budget=True)

"""Ligne « Installation clé en main » du document CLIENT C&I.

Décision fondateur (Reda, 26/10/2026) : sur un devis COMMERCIAL ou
INDUSTRIEL, le client lit UNE ligne « Installation clé en main » qui regroupe
toutes les prestations C&I (études et ingénierie, pose de la structure, pose
des modules, raccordement AC, mise en service, dossier de raccordement,
levage et accès, transport) — les lignes dont le produit porte un
``role_ci`` de ``moteur_ci.composition.PRESTATIONS_CI``, jamais reconnues à
leur désignation.

Quantité 1, P.U. HT = Σ (quantité × P.U. HT) des lignes regroupées ; une
ligne regroupée PAR TAUX de TVA (jamais une TVA mal dite). Le matériel reste
ligne à ligne. Le devis INTERNE (lignes ERP, générateur, marge, stock,
chantier) garde chaque prestation : ce regroupement est un fait de RENDU
seul — les totaux (``totaux_*``) ne sont jamais recalculés ici.

Module PUR : listes de dicts du builder → nouvelle liste, aucune base,
aucun statut touché (règle #4). Résidentiel et agricole : liste inchangée.

R2 (fondateur, 28/10/2026) — le MÊME regroupement sert le « Tableau de
protection AC/DC » (``ci/tableau.py``, rôles ``ROLES_TABLEAU_CI`` du moteur)
et, depuis R3, la « Supervision & comptage » (``ROLES_SUPERVISION_CI``) :
``regrouper_roles`` est la fonction générique, ``regrouper_installation`` en
est le cas « prestations ».
"""
from __future__ import annotations

import re
from decimal import Decimal

from apps.ventes.moteur_ci.composition import PRESTATIONS_CI

#: Les rôles C&I des prestations regroupées (une seule source : le moteur).
ROLES_INSTALLATION_CI = frozenset(cle for cle, _libelle in PRESTATIONS_CI)

#: Libellé de la ligne regroupée, dans la langue du document.
LIBELLE_INSTALLATION = {
    "fr": "Installation clé en main",
    "en": "Turnkey installation",
    "ar": "تركيب متكامل جاهز للتشغيل",
}

MODES_CI = ("commercial", "industriel")


def _dec(valeur):
    return Decimal(str(valeur or 0))


def sous_ligne(it):
    """R2 — le détail CLIENT d'une ligne regroupée : désignation, quantité,
    unité (jamais un prix : le prix est celui de la ligne regroupée)."""
    return {"designation": it.get("designation") or "",
            "quantite": float(_dec(it.get("quantite"))),
            "unite": it.get("unite") or ""}


def _remise_groupee(groupe, taux):
    """R2 (revue) — la remise GLOBALE répartie par le builder (QJRREM :
    ``pu_ht_remise`` / ``total_ht_remise`` / ``pu_ttc_remise`` /
    ``total_ttc_remise`` sur chaque item, ``conditions_commerciales
    ._annoter_remise``) SURVIT au regroupement : Σ des totaux remisés des
    composants ; un composant sans la clé compte au catalogue (le même repli
    que ``montants.total_ht_remise``). Quantité 1 ⇒ P.U. remisé = total
    remisé. Aucun item annoté ⇒ ``{}`` (les gabarits retombent sur le
    catalogue, comme pour toute ligne bâtie à la main)."""
    if not any(it.get("total_ht_remise") is not None for it in groupe):
        return {}
    coef = 1 + taux / 100
    ht = ttc = Decimal(0)
    for it in groupe:
        qte = _dec(it.get("quantite"))
        ht_it = (_dec(it["total_ht_remise"])
                 if it.get("total_ht_remise") is not None
                 else qte * _dec(it.get("prix_unit_ht")))
        ttc_it = (_dec(it["total_ttc_remise"])
                  if it.get("total_ttc_remise") is not None
                  else (ht_it * coef).quantize(Decimal("0.01")))
        ht, ttc = ht + ht_it, ttc + ttc_it
    return {"pu_ht_remise": float(ht), "total_ht_remise": float(ht),
            "pu_ttc_remise": float(ttc), "total_ttc_remise": float(ttc)}


def _ligne_groupee(groupe, langue, libelles, role_groupe, avec_sous_lignes):
    """La ligne unique d'un groupe de lignes au même taux de TVA."""
    total_ht = sum(_dec(it.get("quantite")) * _dec(it.get("prix_unit_ht"))
                   for it in groupe)
    taux = _dec(groupe[0].get("taux_tva"))
    total_ttc = (total_ht * (1 + taux / 100)).quantize(Decimal("0.01"))
    ligne = {
        "designation": libelles.get(langue) or libelles["fr"],
        "marque": "", "description": "", "garantie": "",
        "garantie_mois": None, "garantie_production_mois": None,
        "quantite": 1.0,
        "prix_unit_ht": float(total_ht),
        "prix_unit_ttc": float(total_ttc),
        "taux_tva": groupe[0].get("taux_tva"),
        "ordre": min((it.get("ordre") or 0) for it in groupe),
        "role_devis": None,
        "role_ci": role_groupe,
        "_produit_nom": "",
    }
    ligne.update(_remise_groupee(groupe, taux))
    if avec_sous_lignes:
        ligne["sous_lignes"] = [sous_ligne(it) for it in groupe]
    return ligne


def regrouper_roles(items, roles, libelles, role_groupe, langue="fr",
                    sous_lignes=False):
    """``items`` avec les lignes dont le ``role_ci`` est dans ``roles``
    regroupées (une ligne par taux de TVA, placée à la première ligne de ce
    taux, ``sous_lignes`` = détail des composants quand demandé). Sans ligne
    du groupe : ``items`` tel quel (même objet)."""
    items = items or []
    groupes = {}
    for it in items:
        if isinstance(it, dict) and it.get("role_ci") in roles:
            groupes.setdefault(it.get("taux_tva"), []).append(it)
    if not groupes:
        return items
    sortie, poses = [], set()
    for it in items:
        if not (isinstance(it, dict) and it.get("role_ci") in roles):
            sortie.append(it)
            continue
        taux = it.get("taux_tva")
        if taux not in poses:
            poses.add(taux)
            sortie.append(_ligne_groupee(groupes[taux], langue, libelles,
                                         role_groupe, sous_lignes))
    return sortie


def regrouper_installation(items, langue="fr"):
    """``items`` avec les prestations C&I regroupées (une ligne par taux de
    TVA, placée à la première prestation de ce taux). Sans prestation :
    ``items`` tel quel (même objet)."""
    return regrouper_roles(items, ROLES_INSTALLATION_CI, LIBELLE_INSTALLATION,
                           "installation_ci", langue)


def est_ci(data):
    return str((data or {}).get("mode_installation") or "").strip().lower() \
        in MODES_CI


#: CPDF (constat CCAT 28/10) — « C&I » des noms d'articles semés (« Coffret DC
#: C&I », « Disjoncteur … (C&I) ») : jargon interne, jamais lu par le client.
#: Brut ou déjà échappé pour le HTML (« C&amp;I »).
_JARGON_CI = re.compile(r"\s*\(C&(?:amp;)?I\)|\s+C&(?:amp;)?I\b")


def designation_client(texte):
    """CPDF — la désignation d'une ligne sans le mot interne « C&I »."""
    propre = _JARGON_CI.sub("", str(texte or "")).strip()
    return propre or texte


def _sans_jargon(it):
    """``it`` sans « C&I » dans sa désignation ni celles de ses sous-lignes
    (R2) ; l'objet d'origine quand rien n'est à retirer."""
    if not isinstance(it, dict):
        return it
    textes = [it.get("designation")] + [
        sl.get("designation") for sl in it.get("sous_lignes") or []
        if isinstance(sl, dict)]
    if not any(_JARGON_CI.search(str(t or "")) for t in textes):
        return it
    propre = dict(it, designation=designation_client(it.get("designation")))
    if it.get("sous_lignes"):
        propre["sous_lignes"] = [
            dict(sl, designation=designation_client(sl.get("designation")))
            if isinstance(sl, dict) else sl for sl in it["sous_lignes"]]
    return propre


def lignes_client(items, data):
    """Les lignes que le CLIENT lit : regroupées sur un devis C&I
    (``data['mode_installation']`` — « Tableau de protection AC/DC » R2, puis
    « Supervision & comptage » R3, puis « Installation clé en main »),
    désignations sans « C&I » (CPDF), ``items`` inchangé sinon."""
    if not est_ci(data):
        return items
    # frère : import local (cycle)
    from .tableau import regrouper_supervision, regrouper_tableau
    langue = (data or {}).get("langue_sortie") or "fr"
    lignes = regrouper_installation(
        regrouper_supervision(regrouper_tableau(items, langue), langue), langue)
    return [_sans_jargon(it) for it in lignes]


def regrouper_paniers(data, cles=("sans_items", "avec_items", "all_items")):
    """Charge utile CLIENT (``/proposition``) : chaque panier présent
    regroupé EN PLACE (une option = son propre regroupement). Hors C&I :
    rien ne change."""
    if not est_ci(data):
        return data
    for cle in cles:
        if data.get(cle):
            data[cle] = lignes_client(data[cle], data)
    # Fondateur 26/10/2026 — le panier de l'option « avec batterie » C&I
    # (``option_batterie.lignes``) est regroupé comme les autres.
    option = data.get("option_batterie")
    if isinstance(option, dict) and option.get("lignes"):
        option["lignes"] = lignes_client(option["lignes"], data)
    return data

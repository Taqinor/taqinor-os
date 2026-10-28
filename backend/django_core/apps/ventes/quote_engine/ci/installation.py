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


def _ligne_groupee(groupe, langue):
    """La ligne unique d'un groupe de prestations au même taux de TVA."""
    total_ht = sum(_dec(it.get("quantite")) * _dec(it.get("prix_unit_ht"))
                   for it in groupe)
    taux = _dec(groupe[0].get("taux_tva"))
    total_ttc = (total_ht * (1 + taux / 100)).quantize(Decimal("0.01"))
    return {
        "designation": LIBELLE_INSTALLATION.get(langue)
        or LIBELLE_INSTALLATION["fr"],
        "marque": "", "description": "", "garantie": "",
        "garantie_mois": None, "garantie_production_mois": None,
        "quantite": 1.0,
        "prix_unit_ht": float(total_ht),
        "prix_unit_ttc": float(total_ttc),
        "taux_tva": groupe[0].get("taux_tva"),
        "ordre": min((it.get("ordre") or 0) for it in groupe),
        "role_devis": None,
        "role_ci": "installation_ci",
        "_produit_nom": "",
    }


def regrouper_installation(items, langue="fr"):
    """``items`` avec les prestations C&I regroupées (une ligne par taux de
    TVA, placée à la première prestation de ce taux). Sans prestation :
    ``items`` tel quel (même objet)."""
    items = items or []
    groupes = {}
    for it in items:
        if isinstance(it, dict) and it.get("role_ci") in ROLES_INSTALLATION_CI:
            groupes.setdefault(it.get("taux_tva"), []).append(it)
    if not groupes:
        return items
    sortie, poses = [], set()
    for it in items:
        if not (isinstance(it, dict)
                and it.get("role_ci") in ROLES_INSTALLATION_CI):
            sortie.append(it)
            continue
        taux = it.get("taux_tva")
        if taux not in poses:
            poses.add(taux)
            sortie.append(_ligne_groupee(groupes[taux], langue))
    return sortie


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


def lignes_client(items, data):
    """Les lignes que le CLIENT lit : regroupées sur un devis C&I
    (``data['mode_installation']``), désignations sans « C&I » (CPDF),
    ``items`` inchangé sinon."""
    if not est_ci(data):
        return items
    lignes = regrouper_installation(items, (data or {}).get("langue_sortie")
                                    or "fr")
    return [dict(it, designation=designation_client(it.get("designation")))
            if isinstance(it, dict) and _JARGON_CI.search(
                str(it.get("designation") or "")) else it
            for it in lignes]


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

"""Lecteurs en aval (rôle/fiche) — LA classe d'une ligne de devis, LUE sur la ligne.

Règle du fondateur du 24/11/2026 : « un produit se reconnaît à son rôle et à sa
fiche avant son nom ». Elle s'applique UNE fois, quand la ligne est ÉCRITE et que
le produit est en main (``domain.lignes._role_a_la_creation`` : rôle déclaré,
fiche, puis nom), et la décision est RANGÉE sur la ligne
(``LigneDevis.role_devis``, la colonne que les paniers d'options lisent déjà).

Ici, tous les lecteurs aval (servabilité du PDF et du noyau des paniers, compte
de panneaux et watt, capacité batterie, étude électrique, lectures de lignes)
lisent la MÊME chose : le rôle RANGÉ de la ligne, sinon la règle d'aujourd'hui
(``repli`` : les mots-clés de la désignation), inchangée. Aucun lecteur ne relit
le rôle ni la fiche VIVANTS du produit : une retouche du catalogue après
l'écriture ne reclasse jamais une ligne. Zéro requête : c'est une colonne de la
ligne (ou la clé ``role_devis`` de l'item du moteur PDF).

« Nouveaux rendus seulement » (``regles_calcul.classe_par_role_ouverte``) : les
lecteurs qui ne lisaient que les mots-clés les gardent pour un devis envoyé
avant ``COUPURE_CLASSE_PAR_ROLE``, et pour toute ligne dont le devis n'est pas
connu SANS requête (passé par l'appelant, ou déjà chargé sur la ligne).
"""
from __future__ import annotations

PANNEAU = 'panneau'
BATTERIE = 'batterie'
RESEAU = 'onduleur_reseau'
HYBRIDE = 'onduleur_hybride'
AUTONOME = 'onduleur_offgrid'
#: Tout onduleur, quelle que soit sa famille.
ONDULEUR = 'onduleur'
#: Une ligne que son rôle range hors de toutes les classes ci-dessus.
AUTRE = 'autre'
FAMILLES_ONDULEUR = (RESEAU, HYBRIDE, AUTONOME)
CLASSES_DE_ROLE = (PANNEAU, BATTERIE) + FAMILLES_ONDULEUR


def classe_du_role(role_devis):
    """La classe d'un rôle du vocabulaire, :data:`AUTRE` pour un autre rôle,
    ``None`` sans rôle (ou hors vocabulaire). Fonction PURE."""
    from core.product_roles import role_declare

    role = role_declare(role_devis)
    if not role:
        return None
    return role if role in CLASSES_DE_ROLE else AUTRE


def verdict(declaree, classe, repli):
    """La ligne de classe ``declaree`` est-elle de la classe ``classe`` ?
    ``repli`` (sans argument) rend le verdict d'aujourd'hui. Fonction PURE."""
    if declaree is None or classe is None:
        return bool(repli())
    if declaree == AUTRE:
        return False
    if classe == ONDULEUR:
        return declaree in FAMILLES_ONDULEUR
    return declaree == classe


def classe_du_predicat(predicat):
    """La classe que demande un prédicat de ``solar_classification`` (ou ``None``)."""
    from apps.ventes import solar_classification as sc

    return {sc.is_panel: PANNEAU, sc.is_battery: BATTERIE,
            sc.is_hybrid_inverter: HYBRIDE, sc.is_reseau_inverter: RESEAU,
            sc.is_offgrid_inverter: AUTONOME, sc.is_any_inverter: ONDULEUR,
            sc.is_inverter: ONDULEUR}.get(predicat)


def en_cache(objet, champ):
    """Lire ``objet.champ`` ne fait aucune requête (relation chargée, ou doublure)."""
    est = getattr(getattr(type(objet), champ, None), 'is_cached', None)
    return True if est is None else bool(est(objet))


def devis_connu(ligne, devis=None):
    """Le devis de ``ligne`` SANS requête : celui passé, sinon le sien quand il est
    déjà chargé (une ligne lue par ``devis.lignes``) ; ``None`` sinon."""
    if devis is not None:
        return devis
    if isinstance(ligne, dict) or not en_cache(ligne, 'devis'):
        return None
    return getattr(ligne, 'devis', None)


def role_stocke(ligne, devis=None):
    """Le rôle RANGÉ sur ``ligne`` (objet ou item) quand ce devis le lit, sinon ``None``."""
    from core.product_roles import role_declare

    from apps.ventes.domain.regles_calcul import classe_par_role_ouverte

    connu = devis_connu(ligne, devis)
    if connu is None or not classe_par_role_ouverte(connu):
        return None
    brut = ligne.get('role_devis') if isinstance(ligne, dict) else getattr(ligne, 'role_devis', None)
    return role_declare(brut)


def role_de_ligne(ligne, repli, *, devis=None):
    """Le rôle d'une ligne pour un lecteur qui raisonne en RÔLES : le rôle rangé,
    sinon ``repli()`` (le classifieur d'aujourd'hui, ``classer_produit``)."""
    return role_stocke(ligne, devis) or repli()


def classe_de_ligne(ligne, classe, repli, *, devis=None):
    """LA question des lecteurs aval : ``ligne`` (objet ou item) est-elle de la
    classe ``classe`` (:data:`PANNEAU`, :data:`BATTERIE`, une famille d'onduleur,
    :data:`ONDULEUR`) ? Le rôle rangé, sinon ``repli()`` (mots-clés d'aujourd'hui)."""
    if classe is None:
        return bool(repli())
    return verdict(classe_du_role(role_stocke(ligne, devis)), classe, repli)


def est(ligne, predicat, repli, *, devis=None):
    """:func:`classe_de_ligne` pour la classe d'un prédicat de ``solar_classification``."""
    return classe_de_ligne(ligne, classe_du_predicat(predicat), repli, devis=devis)


def paires_portent(paires, predicat, devis=None):
    """Moteur PDF — une ligne de quantité > 0 de la classe de ``predicat`` parmi
    les couples ``(ligne, item)`` ; le repli lit le texte de l'item comme hier."""
    from apps.ventes.quote_engine.lignes_classement import _item_classement

    return any(est(li, predicat, lambda it=it: predicat(_item_classement(it)), devis=devis)
               and it["quantite"] > 0 for li, it in paires)

"""Lecteurs en aval (rôle/fiche) — LA classe d'une ligne de devis.

Règle du fondateur du 24/11/2026 : « un produit se reconnaît à son rôle et à sa
fiche avant son nom ». La composition l'applique déjà (``stock.etat_ci``,
``creation_calepinage.famille_onduleur_du_produit``) ; les LECTEURS d'une ligne
déjà posée (moteur PDF, noyau des paniers, étude électrique, lectures de
lignes) classaient encore par les seuls mots-clés de la désignation : un
onduleur hybride haute tension reconnu par son rôle, dont le nom ne dit pas
« hybride », devenait « autre » pour eux.

L'ordre, et rien d'autre :

1. le rôle DÉCLARÉ du produit lié (``Produit.role_devis``, ``role_declare``) :
   panneau / batterie / une famille d'onduleur — ou un AUTRE rôle (structure,
   câble…), qui exclut la ligne de ces classes ;
2. la FICHE du produit (``domain.classe_ligne_fiche``) : module ⇒ panneau,
   batterie ⇒ batterie, onduleur ⇒ onduleur, hybride quand la fiche publie un
   port batterie (D-HYB-1) — sinon la famille reste celle des mots-clés ;
3. la règle d'aujourd'hui (``repli``), INCHANGÉE.

Une ligne sans produit, ou dont le produit ne déclare aucun rôle et n'a pas de
fiche, rend EXACTEMENT le verdict d'aujourd'hui. « Nouveaux rendus seulement »
(``regles_calcul.classe_par_role_ouverte``) : un devis envoyé avant la coupure
garde les mots-clés.

CE MODULE NE SAIT QUE LE RÔLE (rang 1), et c'est voulu : il est lu par le noyau
des paniers (``utils.options``, sur le chemin de ``ventes.models``, contrats
import-linter) et par la servabilité du moteur PDF — deux lecteurs liés à
l'ARGENT, qui doivent rendre le même verdict sans requête : le rôle est une
colonne du produit qu'ils chargent déjà, alors que les listes qui calculent un
total ne préchargent pas les fiches (une fiche lue là ferait un N+1 par devis,
ou deux prix pour une vente entre le PDF et le noyau). Le rang de la fiche vit
à côté (``domain.classe_ligne_fiche``) et s'injecte par ``resoudre``.
"""
from __future__ import annotations

PANNEAU = 'panneau'
BATTERIE = 'batterie'
RESEAU = 'onduleur_reseau'
HYBRIDE = 'onduleur_hybride'
AUTONOME = 'onduleur_offgrid'
#: Un onduleur dont la famille n'est pas dite (fiche onduleur sans port batterie).
ONDULEUR = 'onduleur'
#: Une ligne que son rôle range hors de toutes les classes ci-dessus.
AUTRE = 'autre'
FAMILLES_ONDULEUR = (RESEAU, HYBRIDE, AUTONOME)
CLASSES_DE_ROLE = (PANNEAU, BATTERIE) + FAMILLES_ONDULEUR


def classe_du_role(role_devis):
    """La classe que le rôle DÉCLARÉ donne, :data:`AUTRE` pour un autre rôle
    du vocabulaire, ``None`` sans rôle. Fonction PURE."""
    from core.product_roles import role_declare

    role = role_declare(role_devis)
    if not role:
        return None
    return role if role in CLASSES_DE_ROLE else AUTRE


def verdict(declaree, classe, repli):
    """La ligne de classe ``declaree`` est-elle de la classe ``classe`` ?
    ``repli`` (sans argument) rend le verdict des mots-clés. Fonction PURE."""
    if declaree is None or classe is None:
        return bool(repli())
    if declaree == AUTRE:
        return False
    if declaree == ONDULEUR:
        return True if classe == ONDULEUR else (
            bool(repli()) if classe in FAMILLES_ONDULEUR else False)
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


def devis_de(ligne, devis=None):
    """Le devis de ``ligne`` : celui passé, sinon le sien (déjà chargé quand la
    ligne vient de ``devis.lignes``), ``None`` pour une ligne sans devis."""
    if devis is not None:
        return devis
    if en_cache(ligne, 'devis') or getattr(ligne, 'devis_id', None) is not None:
        return getattr(ligne, 'devis', None)
    return None


def _classe_par_le_role(ligne, devis):
    """Rang 1 seul : le rôle déclaré du produit lié (colonne déjà chargée)."""
    if hasattr(ligne, 'produit_id') and ligne.produit_id is None:
        return None
    return classe_du_role(getattr(getattr(ligne, 'produit', None), 'role_devis', None))


def classe_de_ligne(ligne, classe, repli, *, devis=None, resoudre=None):
    """LA question des lecteurs aval : ``ligne`` est-elle de la classe ``classe``
    (:data:`PANNEAU`, :data:`BATTERIE`, une famille d'onduleur, :data:`ONDULEUR`) ?
    ``repli`` : le verdict d'aujourd'hui (mots-clés), appelé seulement quand le
    produit ne dit rien — ou pour un devis fermé (envoyé avant
    ``regles_calcul.COUPURE_CLASSE_PAR_ROLE``). ``resoudre(ligne, devis)`` rend la
    classe déclarée (défaut : le rôle seul ; ``classe_ligne_fiche`` y ajoute la fiche)."""
    from apps.ventes.domain.regles_calcul import classe_par_role_ouverte

    devis = devis_de(ligne, devis)
    if classe is None or not classe_par_role_ouverte(devis):
        return bool(repli())
    return verdict((resoudre or _classe_par_le_role)(ligne, devis), classe, repli)


def paires_portent(paires, predicat, devis=None):
    """Moteur PDF — une ligne de quantité > 0 de la classe de ``predicat`` parmi
    les couples ``(ligne, item)`` ; le repli lit le texte de l'item comme hier
    (``_item_classement``). Rang du rôle seul (lié à l'argent, voir l'en-tête)."""
    from apps.ventes.quote_engine.lignes_classement import _item_classement

    classe = classe_du_predicat(predicat)
    return any(classe_de_ligne(li, classe, lambda it=it: predicat(_item_classement(it)),
                               devis=devis) and it["quantite"] > 0
               for li, it in paires)

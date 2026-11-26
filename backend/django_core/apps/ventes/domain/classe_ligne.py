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
2. la FICHE du produit (``stock.selectors.type_fiche_produit``) : module ⇒
   panneau, batterie ⇒ batterie, onduleur ⇒ onduleur, hybride quand la fiche
   publie un port batterie (``core.electrique.onduleurs.est_onduleur_hybride``,
   D-HYB-1) — sinon la famille reste celle des mots-clés ;
3. la règle d'aujourd'hui (``repli``), INCHANGÉE.

Une ligne sans produit, ou dont le produit ne déclare aucun rôle et n'a pas de
fiche, rend EXACTEMENT le verdict d'aujourd'hui. « Nouveaux rendus seulement »
(``regles_calcul.classe_par_role_ouverte``) : un devis envoyé avant la coupure
garde les mots-clés.

COÛT : le rôle est une colonne du produit, que tous les lecteurs chargent déjà.
La fiche est lue sur l'objet quand elle est chargée (``select_related`` /
préchargement) ; sinon UNE requête par devis (:func:`_carte_du_devis`, gardée
sur l'instance du devis), jamais une par ligne. ``fiche=False`` saute le rang
de la fiche : c'est le choix des lecteurs liés à l'ARGENT (servabilité des
options du PDF et du noyau ``utils.options``) — les listes qui calculent un
total ne préchargent pas les fiches, et une option servie par la fiche au PDF
mais pas au noyau ferait deux prix pour une vente.
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
_CLASSES_DE_ROLE = (PANNEAU, BATTERIE) + FAMILLES_ONDULEUR
_CLASSE_DE_FICHE = {'module': PANNEAU, 'batterie': BATTERIE, 'onduleur': ONDULEUR}
#: La carte ``{produit_id: classe}`` gardée sur l'instance du devis.
_CLE_CARTE = '_classe_par_role_produits'


def classe_declaree(role_devis=None, type_fiche='', ports_batterie_kw=(), nom=''):
    """La classe que le rôle puis la fiche donnent, ou ``None``. Fonction PURE."""
    from core.product_roles import role_declare

    role = role_declare(role_devis)
    if role:
        return role if role in _CLASSES_DE_ROLE else AUTRE
    classe = _CLASSE_DE_FICHE.get(str(type_fiche or '').strip())
    if classe != ONDULEUR:
        return classe
    from core.electrique.onduleurs import est_onduleur_hybride

    from apps.ventes.selectors_calepinage import autre_famille_d_onduleur_par_nom
    if est_onduleur_hybride('', ports_batterie_kw=ports_batterie_kw,
                            autre_famille_par_nom=autre_famille_d_onduleur_par_nom(nom)):
        return HYBRIDE
    return ONDULEUR


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


def _en_cache(objet, champ):
    """Lire ``objet.champ`` ne fait aucune requête (relation chargée, ou doublure)."""
    est = getattr(getattr(type(objet), champ, None), 'is_cached', None)
    return True if est is None else bool(est(objet))


def classe_du_produit(produit, *, fiche=True):
    """La classe que le rôle déclaré puis la fiche de ``produit`` donnent."""
    if produit is None:
        return None
    if not fiche:
        return classe_declaree(getattr(produit, 'role_devis', None))
    from apps.stock.selectors import specs_for_produit, type_fiche_produit
    try:
        type_fiche = type_fiche_produit(produit) or ''
    except AttributeError:  # doublure de fiche sans ``type_fiche`` : aucune fiche lisible
        type_fiche = ''
    specs = (specs_for_produit(produit) or {}) if type_fiche == 'onduleur' else {}
    return classe_declaree(getattr(produit, 'role_devis', None), type_fiche,
                           (specs.get('bat_max_charge_kw'), specs.get('bat_max_decharge_kw')),
                           getattr(produit, 'nom', '') or '')


def _carte_du_devis(devis, produit_id):
    """La classe du produit ``produit_id`` lue dans la carte du devis : les
    produits de TOUTES ses lignes en UNE requête (fiche jointe), gardée sur
    l'instance ; un produit absent de la carte (ligne ajoutée depuis) la complète."""
    from django.db.models import Q

    from apps.stock.selectors import produits_qs
    from apps.ventes.models import LigneDevis

    carte = devis.__dict__.setdefault(_CLE_CARTE, {})
    if produit_id not in carte:
        filtre = Q(pk=produit_id)
        if getattr(devis, 'pk', None) is not None:
            filtre |= Q(pk__in=LigneDevis.objects.filter(devis_id=devis.pk).values('produit_id'))
        for produit in produits_qs().filter(filtre).select_related('fiche_technique'):
            carte[produit.pk] = classe_du_produit(produit)
        carte.setdefault(produit_id, None)
    return carte[produit_id]


def _devis_de(ligne, devis):
    """Le devis de ``ligne`` : celui passé, sinon le sien (déjà chargé quand la
    ligne vient de ``devis.lignes``), ``None`` pour une ligne sans devis."""
    if devis is not None:
        return devis
    if _en_cache(ligne, 'devis') or getattr(ligne, 'devis_id', None) is not None:
        return getattr(ligne, 'devis', None)
    return None


def classe_de_produit_de_ligne(ligne, *, devis=None, fiche=True):
    """La classe que le produit lié de ``ligne`` déclare (rôle, puis fiche), ou ``None``."""
    if not hasattr(ligne, 'produit_id'):  # doublure : l'objet produit seul
        return classe_du_produit(getattr(ligne, 'produit', None), fiche=fiche)
    if ligne.produit_id is None:
        return None
    if not fiche or (_en_cache(ligne, 'produit') and _en_cache(ligne.produit, 'fiche_technique')):
        return classe_du_produit(ligne.produit, fiche=fiche)
    devis = _devis_de(ligne, devis)
    if devis is None:
        return classe_du_produit(ligne.produit)
    return _carte_du_devis(devis, ligne.produit_id)


def classe_de_ligne(ligne, classe, repli, *, devis=None, fiche=True):
    """LA question des lecteurs aval : ``ligne`` est-elle de la classe ``classe``
    (:data:`PANNEAU`, :data:`BATTERIE`, une famille d'onduleur, :data:`ONDULEUR`) ?
    ``repli`` : le verdict d'aujourd'hui (mots-clés), appelé seulement quand le
    rôle et la fiche ne disent rien — ou pour un devis fermé (envoyé avant
    :data:`regles_calcul.COUPURE_CLASSE_PAR_ROLE`)."""
    from apps.ventes.domain.regles_calcul import classe_par_role_ouverte

    if classe is None or not classe_par_role_ouverte(_devis_de(ligne, devis)):
        return bool(repli())
    return verdict(classe_de_produit_de_ligne(ligne, devis=devis, fiche=fiche), classe, repli)


def paires_portent(paires, predicat, devis=None):
    """Moteur PDF — une ligne de quantité > 0 de la classe de ``predicat`` parmi
    les couples ``(ligne, item)`` ; le repli lit le texte de l'item comme hier
    (``_item_classement``). Sans le rang de la fiche (lié à l'argent, voir l'en-tête)."""
    from apps.ventes.quote_engine.lignes_classement import _item_classement

    classe = classe_du_predicat(predicat)
    return any(classe_de_ligne(li, classe, lambda it=it: predicat(_item_classement(it)),
                               devis=devis, fiche=False) and it["quantite"] > 0
               for li, it in paires)

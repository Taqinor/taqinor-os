"""Lecteurs en aval (rôle/fiche) — le rang de la FICHE de ``domain.classe_ligne``.

Pour les lecteurs qui ne pilotent aucun argent (étude électrique, lectures de
lignes de ``domain.lignes``) : le rôle déclaré du produit, puis sa fiche lue par
le sélecteur du stock (``type_fiche_produit`` / ``specs_for_produit``, jamais
ses modèles), puis les mots-clés. Module à part : il lit le stock et le
calepinage, ce que le noyau des paniers (sur le chemin de ``ventes.models``) ne
doit pas faire (contrats import-linter).

COÛT : la fiche est lue sur l'objet quand elle est chargée (``select_related`` /
préchargement) ; sinon UNE requête par devis (:func:`_carte_du_devis`, gardée
sur l'instance du devis), jamais une par ligne.
"""
from __future__ import annotations

from apps.ventes.domain import classe_ligne as _cl

_CLASSE_DE_FICHE = {'module': _cl.PANNEAU, 'batterie': _cl.BATTERIE, 'onduleur': _cl.ONDULEUR}
#: La carte ``{produit_id: classe}`` gardée sur l'instance du devis.
_CLE_CARTE = '_classe_par_role_produits'


def classe_declaree(role_devis=None, type_fiche='', ports_batterie_kw=(), nom=''):
    """La classe que le rôle puis la fiche donnent, ou ``None``. Fonction PURE."""
    par_role = _cl.classe_du_role(role_devis)
    if par_role:
        return par_role
    classe = _CLASSE_DE_FICHE.get(str(type_fiche or '').strip())
    if classe != _cl.ONDULEUR:
        return classe
    from core.electrique.onduleurs import est_onduleur_hybride

    from apps.ventes.selectors_calepinage import autre_famille_d_onduleur_par_nom
    if est_onduleur_hybride('', ports_batterie_kw=ports_batterie_kw,
                            autre_famille_par_nom=autre_famille_d_onduleur_par_nom(nom)):
        return _cl.HYBRIDE
    return _cl.ONDULEUR


def classe_du_produit(produit):
    """La classe que le rôle déclaré puis la fiche de ``produit`` donnent."""
    if produit is None:
        return None
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


def classe_de_produit_de_ligne(ligne, devis=None):
    """La classe que le produit lié de ``ligne`` déclare (rôle, puis fiche), ou ``None``."""
    if not hasattr(ligne, 'produit_id'):  # doublure : l'objet produit seul
        return classe_du_produit(getattr(ligne, 'produit', None))
    if ligne.produit_id is None:
        return None
    if _cl.en_cache(ligne, 'produit') and _cl.en_cache(ligne.produit, 'fiche_technique'):
        return classe_du_produit(ligne.produit)
    devis = _cl.devis_de(ligne, devis)
    if devis is None:
        return classe_du_produit(ligne.produit)
    return _carte_du_devis(devis, ligne.produit_id)


def classe_de_ligne(ligne, classe, repli, *, devis=None):
    """:func:`domain.classe_ligne.classe_de_ligne` avec le rang de la fiche."""
    return _cl.classe_de_ligne(ligne, classe, repli, devis=devis,
                               resoudre=classe_de_produit_de_ligne)

"""D-ACAL-169 — LE panneau par défaut d'une société, lu par les autres apps (frontière : selectors).

Fondateur, 26/11/2026 : « always use 715w everywhere, and have somewhere in the stock to show the default used
pannels ». Un drapeau ``stock.Produit.panneau_par_defaut`` (au plus un par société, contrainte de base) désigne CE
panneau ; ce module dit aux appelants (devis automatique, assistant, C&I, pompage, calepinage — lanes suivantes) s'il
est UTILISABLE, et sinon POURQUOI. Contrat : ``contract_samples/panneau_par_defaut.json``.

Utilisable = désigné ET non archivé ET tarifé (prix de vente > 0, ``etat_ci._prix_vente_saisi``) ET toujours reconnu
comme un panneau ET sans contradiction entre le watt du nom et celui de la fiche (``desaccord_watt``). Sinon :
``None`` — l'appelant garde SA règle d'aujourd'hui (aucun 710 ni 715 écrit ici). Aucun prix ne sort d'ici :
un appelant qui veut le prix le lit par les sélecteurs qu'il utilise déjà.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

DESIGNE = 'designe'
AUCUN = 'aucun'
ARCHIVE = 'archive'
SANS_PRIX = 'sans_prix'
PAS_UN_PANNEAU = 'pas_un_panneau'
WATT_CONTRADICTOIRE = 'watt_contradictoire'
SOURCES = (DESIGNE, AUCUN, ARCHIVE, SANS_PRIX, PAS_UN_PANNEAU, WATT_CONTRADICTOIRE)

_REGLE_DU_JOUR = "les choix automatiques gardent leur règle d'aujourd'hui."
MOTIF_AUCUN = "Aucun panneau par défaut n'est désigné : " + _REGLE_DU_JOUR
_MOTIFS = {
    ARCHIVE: "Le panneau désigné « {nom} » est archivé : " + _REGLE_DU_JOUR,
    SANS_PRIX: "Le panneau désigné « {nom} » n'a pas de prix de vente : " + _REGLE_DU_JOUR,
    PAS_UN_PANNEAU: "Le produit désigné « {nom} » n'est plus reconnu comme un panneau : " + _REGLE_DU_JOUR,
}


def est_un_panneau(produit) -> bool:
    """Le produit est-il un PANNEAU ? Ordre de la maison : rôle DÉCLARÉ, puis fiche technique de type ``module``,
    puis catégorie et nom (``etat_ci._role_effectif`` = ``core.product_roles.role_effectif`` + mots-clés du moteur).
    Aucun classifieur neuf : les deux lecteurs existants, dans cet ordre."""
    from core.product_roles import role_declare

    from .etat_ci import _role_effectif
    from .selectors_fiche_technique import type_fiche_produit

    declare = role_declare(getattr(produit, 'role_devis', None))
    if declare:
        return declare == 'panneau'
    if type_fiche_produit(produit) == 'module':
        return True
    return _role_effectif(produit)[0] == 'panneau'


def source_du_produit(produit) -> str:
    """La ``source`` du contrat pour le produit DÉSIGNÉ (ou ``None`` : aucun désigné)."""
    from .etat_ci import _prix_vente_saisi

    if produit is None:
        return AUCUN
    if produit.is_archived:
        return ARCHIVE
    if not _prix_vente_saisi(produit):
        return SANS_PRIX
    if not est_un_panneau(produit):
        return PAS_UN_PANNEAU
    if desaccord_watt(produit) is not None:
        return WATT_CONTRADICTOIRE
    return DESIGNE


def _nombre(valeur):
    valeur = float(valeur)
    return int(valeur) if valeur.is_integer() else valeur


def watt_au_nom(produit):
    """Le wattage écrit dans le NOM (« 710 W », « 715Wc »), par la regex unique de la fondation
    (``core.product_roles.WATT_RE`` — ``solar_classification._WATT_RE`` en est l'alias), sinon ``None``."""
    from core.product_roles import WATT_RE

    trouve = WATT_RE.search(getattr(produit, 'nom', '') or '')
    return int(trouve.group(1)) if trouve else None


def watt_de_fiche(produit):
    """La puissance ``pmax_wc`` publiée sur la fiche technique MODULE (> 0), sinon ``None``."""
    from .selectors_fiche_technique import specs_for_produit

    try:
        pmax = (specs_for_produit(produit) or {}).get('pmax_wc')
    except Exception:  # fiche illisible : même repli que etat_ci.etat_panneau
        logger.warning('Fiche illisible pour le produit %s', getattr(produit, 'pk', None), exc_info=True)
        return None
    return _nombre(pmax) if pmax is not None and float(pmax) > 0 else None


def desaccord_watt(produit):
    """``(watt du nom, watt de la fiche)`` quand le produit porte LES DEUX et qu'ils diffèrent, sinon ``None``.

    Les moteurs de devis ne lisent pas le watt dans le même ordre (le résolveur résidentiel lit le nom d'abord,
    le C&I la seule fiche) : un « … 710 W » dont la fiche dit 715 vaudrait 710 pour l'un et 715 pour l'autre. Un
    tel produit ne peut donc pas être LE panneau par défaut."""
    au_nom, de_fiche = watt_au_nom(produit), watt_de_fiche(produit)
    if au_nom is None or de_fiche is None or float(au_nom) == float(de_fiche):
        return None
    return au_nom, de_fiche


def _texte(valeur):
    return str(valeur).replace('.', ',')


def phrase_desaccord_watt(au_nom, de_fiche):
    """La phrase du REFUS de l'action (dite sous le bouton de CE produit) qui nomme les deux valeurs et dit quoi
    corriger. Le motif du résumé, lu loin de la fiche, est ``motif_desaccord_watt`` (il nomme le produit)."""
    return (f"Le nom de ce produit dit {_texte(au_nom)} W et sa fiche technique {_texte(de_fiche)} Wc : "
            "corrigez l'un des deux, puis désignez-le.")


def motif_desaccord_watt(nom, au_nom, de_fiche):
    """D-ACAL-169 (rejeu) — le MOTIF du résumé pour un désigné au watt contradictoire : il NOMME le produit (la ligne
    du stock le lit telle quelle, loin de la fiche du produit), les deux valeurs, et ce qui s'applique d'ici là."""
    return (f"Le panneau désigné « {nom} » n'est pas utilisable : son nom dit {_texte(au_nom)} W et sa fiche "
            f"technique {_texte(de_fiche)} Wc. Corrigez l'un des deux ; d'ici là, {_REGLE_DU_JOUR}")


def watt_du_panneau(produit):
    """Puissance du panneau : ``pmax_wc`` de sa fiche MODULE, sinon le wattage lu au nom, sinon ``None``.

    Pour un panneau UTILISABLE les deux sources ne se contredisent jamais (``desaccord_watt`` le refuse) : l'ordre
    fiche-puis-nom donne alors la même valeur que nom-puis-fiche. Un moteur de devis prend malgré tout le watt de SA
    propre lecture de ce produit (son résolveur), jamais d'ici seulement."""
    de_fiche = watt_de_fiche(produit)
    return de_fiche if de_fiche is not None else watt_au_nom(produit)


def _produit_designe(company):
    from .models import Produit

    if company is None:
        return None
    return (Produit.objects.filter(company=company, panneau_par_defaut=True)
            .select_related('categorie', 'fiche_technique').first())


def panneau_par_defaut(company):
    """Le ``Produit`` panneau par défaut de ``company`` s'il est utilisable (source ``designe``), sinon ``None``."""
    produit = _produit_designe(company)
    return produit if source_du_produit(produit) == DESIGNE else None


def watt_panneau_par_defaut(company):
    """La puissance (Wc) du panneau par défaut utilisable, sinon ``None`` — l'appelant garde SON repli."""
    produit = panneau_par_defaut(company)
    return watt_du_panneau(produit) if produit is not None else None


def resume_du_produit(produit):
    """La forme du contrat pour le produit désigné (ou ``None``). Cinq clés, toujours."""
    source = source_du_produit(produit)
    if source != DESIGNE:
        if produit is None:
            motif = MOTIF_AUCUN
        elif source == WATT_CONTRADICTOIRE:
            motif = motif_desaccord_watt(produit.nom, *desaccord_watt(produit))
        else:
            motif = _MOTIFS[source].format(nom=produit.nom)
        return {'produit_id': None, 'nom': None, 'pmax_wc': None, 'source': source, 'motif': motif}
    return {'produit_id': produit.pk, 'nom': produit.nom, 'pmax_wc': watt_du_panneau(produit),
            'source': source, 'motif': None}


def resume_panneau_par_defaut(company):
    """``GET stock/panneau-par-defaut/`` — la forme ``contract_samples/panneau_par_defaut.json``."""
    return resume_du_produit(_produit_designe(company))

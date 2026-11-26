"""D-ACAL-169 — LE panneau par défaut d'une société, lu par les autres apps (frontière : selectors).

Fondateur, 26/11/2026 : « always use 715w everywhere, and have somewhere in the stock to show the default used
pannels ». Un drapeau ``stock.Produit.panneau_par_defaut`` (au plus un par société, contrainte de base) désigne CE
panneau ; ce module dit aux appelants (devis automatique, assistant, C&I, pompage, calepinage — lanes suivantes) s'il
est UTILISABLE, et sinon POURQUOI. Contrat : ``contract_samples/panneau_par_defaut.json``.

Utilisable = désigné ET non archivé ET tarifé (prix de vente > 0, ``etat_ci._prix_vente_saisi``) ET toujours reconnu
comme un panneau. Sinon : ``None`` — l'appelant garde SA règle d'aujourd'hui (aucun 710 ni 715 écrit ici). Aucun prix
ne sort d'ici : un appelant qui veut le prix le lit par les sélecteurs qu'il utilise déjà.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

DESIGNE = 'designe'
AUCUN = 'aucun'
ARCHIVE = 'archive'
SANS_PRIX = 'sans_prix'
PAS_UN_PANNEAU = 'pas_un_panneau'
SOURCES = (DESIGNE, AUCUN, ARCHIVE, SANS_PRIX, PAS_UN_PANNEAU)

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
    return DESIGNE


def watt_du_panneau(produit):
    """Puissance du panneau : ``pmax_wc`` de sa fiche MODULE, sinon le wattage lu au nom par le lecteur existant
    (``apps.ventes.solar_classification.parse_watt``, la regex unique de ``core.product_roles``), sinon ``None``."""
    from apps.ventes.solar_classification import parse_watt

    from .selectors_fiche_technique import specs_for_produit

    try:
        pmax = (specs_for_produit(produit) or {}).get('pmax_wc')
    except Exception:  # fiche illisible : même repli que etat_ci.etat_panneau
        logger.warning('Fiche illisible pour le produit %s', getattr(produit, 'pk', None), exc_info=True)
        pmax = None
    if pmax is not None and float(pmax) > 0:
        valeur = float(pmax)
        return int(valeur) if valeur.is_integer() else valeur
    return parse_watt(getattr(produit, 'nom', '') or '')


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
        motif = MOTIF_AUCUN if produit is None else _MOTIFS[source].format(nom=produit.nom)
        return {'produit_id': None, 'nom': None, 'pmax_wc': None, 'source': source, 'motif': motif}
    return {'produit_id': produit.pk, 'nom': produit.nom, 'pmax_wc': watt_du_panneau(produit),
            'source': source, 'motif': None}


def resume_panneau_par_defaut(company):
    """``GET stock/panneau-par-defaut/`` — la forme ``contract_samples/panneau_par_defaut.json``."""
    return resume_du_produit(_produit_designe(company))

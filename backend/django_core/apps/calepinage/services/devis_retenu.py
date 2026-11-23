"""ACAL1951-ACAL1956 — le calepinage d'un devis LIT la conception que ce devis a
retenue (demande du fondateur : « one engine, the CRM one »).

La conception vient d'UN sélecteur de ventes (``apps.ventes.selectors_calepinage.
conception_retenue_du_devis``, ACAL1950, contrat
``contract_samples/calepinage_conception_retenue.json``) : option retenue, module
et quantité, onduleurs, chaînes, production annuelle. Ce module n'en recalcule
rien et n'écrit rien sur le devis ; il ne range qu'une seule chose, dans le
``resultat`` du calepinage (écrivain unique ``services.resultat.
modifier_resultat``) : l'option que le dernier enregistrement du dessin visait.
"""
from __future__ import annotations

from . import pret_a_envoyer as _pret_a_envoyer  # H5 — une_fois_par_lecture

#: ACAL1951 — clé de ``Calepinage.resultat`` : ``{devis, option}`` que le dernier
#: enregistrement du dessin visait (absente sans devis lié).
CLE_OPTION_DESSINEE = 'option_dessinee'


def devis_lie_borne(calepinage):
    """Le devis lié au calepinage, borné à SA société, ou ``None``."""
    from apps.ventes.selectors import get_devis_by_pk

    devis_id = getattr(calepinage, 'devis_id', None)
    company = getattr(calepinage, 'company', None)
    if not devis_id or company is None:
        return None
    devis = get_devis_by_pk(devis_id)
    if devis is None or devis.company_id != company.pk:
        return None
    return devis


@_pret_a_envoyer.une_fois_par_lecture('conception_retenue')
def conception_du_devis_lie(calepinage, devis=None):
    """ACAL1950 — la conception retenue du devis lié (``devis`` déjà lu par
    l'appelant, sinon lu ici), ou ``None`` sans devis lié."""
    from apps.ventes.selectors_calepinage import conception_retenue_du_devis

    if devis is None:
        devis = devis_lie_borne(calepinage)
    return conception_retenue_du_devis(devis) if devis is not None else None


def cible_de_l_option_retenue(contexte_devis, devis):
    """ACAL1951 — la cible ``source: 'devis'`` de l'atelier : l'option RETENUE
    par le devis (plus l'option « sans » en dur). ``option`` dit laquelle.

    Le contexte ventes sert déjà les deux vues (``cible`` = option sans,
    ``cible_avec`` = option avec quand elle est servable, CTX3D) : on choisit,
    on ne recompte pas. Les clés de ``cible`` absentes de ``cible_avec``
    (``bill_kwh``) sont gardées."""
    from apps.ventes.selectors_calepinage import conception_retenue_du_devis

    conception = conception_retenue_du_devis(devis) if devis is not None else None
    option = (conception or {}).get('option') or 'sans'
    cible = dict(contexte_devis['cible'])
    if option == 'avec' and isinstance(contexte_devis.get('cible_avec'), dict):
        cible.update(contexte_devis['cible_avec'])
    return dict(cible, source='devis', refus=None, option=option)


def memoriser_option_dessinee(calepinage):
    """ACAL1951 — range ``{devis, option}`` visés par l'enregistrement du dessin
    dans ``resultat`` (retiré sans devis lié). N'écrit rien quand la valeur
    rangée est déjà la bonne. Rend la valeur rangée."""
    from .resultat import modifier_resultat

    conception = conception_du_devis_lie(calepinage)
    valeur = ({'devis': conception['devis'], 'option': conception['option']}
              if conception else None)
    if (getattr(calepinage, 'resultat', None) or {}).get(CLE_OPTION_DESSINEE) == valeur:
        return valeur

    def _poser(resultat):
        if valeur is None:
            resultat.pop(CLE_OPTION_DESSINEE, None)
        else:
            resultat[CLE_OPTION_DESSINEE] = valeur

    modifier_resultat(calepinage, _poser)
    return valeur


def _onduleur_retenu(conception):
    """ACAL1952 — la première ligne onduleur de l'option retenue, ou ``None``."""
    onduleurs = (conception or {}).get('onduleurs') or []
    return onduleurs[0] if onduleurs and onduleurs[0].get('produit') else None


def produits_retenus(calepinage, produits):
    """ACAL1952 — ``{rôle: produit}`` du devis lié : l'onduleur est celui de
    l'option RETENUE par le devis (plus la première ligne hors « avec ») ; les
    autres rôles restent ceux de l'agrégat ``equipements``."""
    onduleur = _onduleur_retenu(conception_du_devis_lie(calepinage))
    return dict(produits, onduleur=onduleur['produit']) if onduleur else produits


def _longueur_du_devis(conception):
    return ((conception or {}).get('chaines') or {}).get('longueur') or None


def options_avec_devis(options, calepinage, donnees):
    """ACAL1952 — les options du noyau complétées par le DEVIS : sans saisie,
    le nombre d'onduleurs et la longueur de chaîne sont ceux du devis lié. Une
    désignation d'onduleur SAISIE garde la main (le devis ne dimensionne plus
    un autre appareil) ; une option saisie n'est jamais remplacée."""
    if (donnees or {}).get('onduleur_produit') not in (None, ''):
        return options
    conception = conception_du_devis_lie(calepinage)
    onduleur = _onduleur_retenu(conception)
    if onduleur is None:
        return options
    options = dict(options)
    if 'nombre_onduleurs' not in options and onduleur['quantite'] >= 1:
        options['nombre_onduleurs'] = onduleur['quantite']
    if 'longueur_forcee' not in options and _longueur_du_devis(conception):
        options['longueur_forcee'] = _longueur_du_devis(conception)
    return options


def bloc_devis_retenu(calepinage, stockee, resolu):
    """ACAL1952 — le bloc ``devis_retenu`` de ``GET entree-electrique/`` : le
    matériel électrique que le devis lié a retenu (provenance « devis ») et les
    ÉCARTS d'une saisie contraire — des informations, jamais un refus : la
    saisie reste permise. ``None`` sans devis lié."""
    conception = conception_du_devis_lie(calepinage)
    if not conception:
        return None
    onduleur = _onduleur_retenu(conception)
    longueur = _longueur_du_devis(conception)
    saisie = stockee or {}
    reference = conception['reference']
    ecarts = []
    saisi = saisie.get('onduleur_produit')
    if onduleur and saisi not in (None, '') and str(saisi) != str(onduleur['produit']):
        designe = ((resolu or {}).get('designations') or {}).get('onduleur') or 'un autre onduleur'
        ecarts.append(f'Onduleur : « {designe} » désigné, « {onduleur["designation"]} » au devis {reference}.')
    for cle, devis_valeur, unite in (('nombre_onduleurs', (onduleur or {}).get('quantite'), 'onduleur(s)'),
                                     ('longueur_chaine_forcee', longueur, 'modules par chaîne')):
        valeur = saisie.get(cle)
        if valeur not in (None, '') and devis_valeur and str(valeur) != str(devis_valeur):
            ecarts.append(f'{valeur} {unite} saisi(s), {devis_valeur} au devis {reference}.')
    return {'devis': conception['devis'], 'reference': reference, 'statut': conception['statut'],
            'option': conception['option'], 'provenance': 'devis',
            'onduleur': ({'produit_id': onduleur['produit'], 'designation': onduleur['designation']}
                         if onduleur else None),
            'nombre_onduleurs': (onduleur or {}).get('quantite') or None,
            'longueur_chaine': longueur, 'ecarts': ecarts}

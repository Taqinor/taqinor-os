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


#: Mémoire de la conception lue, posée sur l'INSTANCE du calepinage (une requête) :
#: ``(devis_id, conception)`` — un re-lien change ``devis_id``, donc relit.
_MEMOIRE = '_acal1950_conception_retenue'


@_pret_a_envoyer.une_fois_par_lecture('conception_retenue')
def conception_du_devis_lie(calepinage, devis=None):
    """ACAL1950 — la conception retenue du devis lié (``devis`` déjà lu par
    l'appelant, sinon lu ici, borné à la société), ou ``None`` sans devis lié.
    Lue UNE fois par instance (budget de requêtes des écrans)."""
    from .equipements import conception_retenue, conception_retenue_par_id

    if devis is not None:
        return conception_retenue(devis)
    devis_id = getattr(calepinage, 'devis_id', None)
    memoire = getattr(calepinage, _MEMOIRE, None)
    if memoire is not None and memoire[0] == devis_id:
        return memoire[1]
    valeur = (conception_retenue_par_id(devis_id, getattr(calepinage, 'company', None))
              if devis_id else None)
    try:
        setattr(calepinage, _MEMOIRE, (devis_id, valeur))
    except AttributeError:  # double de test sans attributs libres : relu à chaque appel
        pass
    return valeur


def cible_de_l_option_retenue(contexte_devis, devis):
    """ACAL1951 — la cible ``source: 'devis'`` de l'atelier : l'option RETENUE
    par le devis (plus l'option « sans » en dur). ``option`` dit laquelle.

    Le contexte ventes sert déjà les deux vues (``cible`` = option sans,
    ``cible_avec`` = option avec quand elle est servable, CTX3D) : on choisit,
    on ne recompte pas. Les clés de ``cible`` absentes de ``cible_avec``
    (``bill_kwh``) sont gardées."""
    from .equipements import conception_retenue

    conception = conception_retenue(devis)
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


def _module_retenu(conception):
    module = (conception or {}).get('module')
    produit = module.get('produit') if isinstance(module, dict) else None
    return produit if produit not in (None, '') else None


def module_retenu_du_devis(calepinage):
    """Rejeu T3-VAGUEC2 — le produit MODULE de la conception retenue du devis
    lié (``apps.ventes.selectors_calepinage.conception_retenue_du_devis``),
    ou ``None`` sans devis lié ni ligne panneau : le module que l'atelier pose
    d'office, jamais un module d'essai du catalogue de même puissance."""
    return _module_retenu(conception_du_devis_lie(calepinage))


def produits_retenus(calepinage, produits):
    """ACAL1952 — ``{rôle: produit}`` du devis lié : l'onduleur ET le module
    sont ceux de l'option RETENUE par le devis (plus la première ligne hors
    « avec ») ; l'optimiseur reste celui de l'agrégat ``equipements``. Une
    désignation EXPLICITE de l'entrée garde la main (``resoudre_materiel`` ne
    lit le devis qu'à défaut)."""
    conception = conception_du_devis_lie(calepinage)
    retenus = dict(produits)
    onduleur = _onduleur_retenu(conception)
    if onduleur:
        retenus['onduleur'] = onduleur['produit']
    module = _module_retenu(conception)
    if module is not None:
        retenus['module'] = module
    return retenus


def _longueur_du_devis(conception):
    return ((conception or {}).get('chaines') or {}).get('longueur') or None


def longueur_du_devis_lie(calepinage):
    """ACAL1953 — la longueur de chaîne du devis lié (conception électrique
    rangée de l'option retenue), ou ``None`` : sans elle, aucun écart."""
    return _longueur_du_devis(conception_du_devis_lie(calepinage))


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


def bloc_production_devis(calepinage):
    """ACAL1956 (D-ACAL-90) — ``production_devis`` de ``GET resultat/`` : la
    production annuelle RETENUE PAR LE DEVIS (``conception_retenue_du_devis``,
    aucun recalcul) quand le calepinage est lié à un devis envoyé ou accepté —
    l'étape Résultats n'est jamais vide, même avant la simulation de la pose.
    ``{devis, reference, statut, production_annuelle_kwh, production_origine}``
    ou ``None`` (sans devis lié, ou devis encore brouillon)."""
    conception = conception_du_devis_lie(calepinage)
    if not conception or not conception['recu']:
        return None
    return {cle: conception[cle] for cle in ('devis', 'reference', 'statut',
                                             'production_annuelle_kwh', 'production_origine')}

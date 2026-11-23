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

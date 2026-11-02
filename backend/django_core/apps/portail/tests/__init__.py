"""Tests du portail."""


def corps_acceptation(devis, **corps):
    """ADVS20 — le corps d'une acceptation portail : ce que le client poste +
    l'empreinte du contenu qu'il a lu (clé ``empreinte_contenu`` de la liste)."""
    from apps.ventes.domain.modifiabilite import empreinte_contenu_signable

    return {'empreinte_contenu': empreinte_contenu_signable(devis), **corps}

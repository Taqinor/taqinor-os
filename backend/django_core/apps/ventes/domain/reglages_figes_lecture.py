"""ADVS2 (D-ADVS-1) — LECTURE de l'instantané des réglages figés à l'envoi.

Feuille pure, comme ``domain.kwh_lecture`` : aucun import. ``quote_engine.
lignes_classement`` (chargé par ``ventes.models`` via le noyau monnaie) la lit
sans tirer ``domain.envoi`` et ses services inter-apps (contrat import-linter
« Core domain models stay decoupled »). L'écriture reste dans ``domain.envoi``.
"""

#: Type de l'entrée de ``clauses_appliquees`` qui porte les réglages de rendu de
#: la société et les fiches produit des lignes, figés à l'envoi. Forme =
#: ``contract_samples/reglages_figes_envoi.json``. Jamais imprimée.
TYPE_REGLAGES_FIGES = 'reglages_figes'


def reglages_figes(devis):
    """L'instantané de l'envoi (forme de l'échantillon, sans ``type``), ou ``{}`` :
    brouillon (réglages du jour, même sur une V2 qui a hérité de l'entrée) ou
    devis envoyé avant ce gel."""
    if getattr(devis, 'statut', None) == 'brouillon':
        return {}
    for c in (getattr(devis, 'clauses_appliquees', None) or []):
        if isinstance(c, dict) and c.get('type') == TYPE_REGLAGES_FIGES:
            return {k: v for k, v in c.items() if k != 'type'}
    return {}

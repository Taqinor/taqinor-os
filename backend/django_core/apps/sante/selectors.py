"""Sélecteurs (lecture seule) du module ``apps.sante``.

Fonctions utilitaires que d'autres apps peuvent importer **via import local**
(dans le corps d'une fonction, jamais au niveau module) pour éviter les
dépendances cycliques et respecter les contrats d'import CI-enforced.
"""


def tarif_applicable(acte, convention):
    """NTSAN8 — tarif TTC applicable pour un acte, pour une convention
    donnée (ou ``None``).

    Lit ``GrilleTarifaire`` pour (convention, acte) si une ligne existe,
    sinon retombe sur ``ActeMedical.tarif_base_ttc``. Renvoie un dict
    ``{'tarif_ttc': Decimal, 'taux_prise_charge_pct': Decimal, 'source':
    'grille'|'base'}``.
    """
    from .models import GrilleTarifaire

    if convention is not None:
        grille = GrilleTarifaire.objects.filter(
            company=acte.company, convention=convention, acte=acte).first()
        if grille is not None:
            return {
                'tarif_ttc': grille.tarif_convention_ttc,
                'taux_prise_charge_pct': grille.taux_prise_charge_pct,
                'source': 'grille',
            }
    return {
        'tarif_ttc': acte.tarif_base_ttc,
        'taux_prise_charge_pct': 0,
        'source': 'base',
    }

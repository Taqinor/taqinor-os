"""ACAL645 — la règle de chaîne publiée, extraite de ``electrique.py``.

Extraction pure (aucun changement de comportement) : ``electrique.py``
(≥ 2 000 lignes) ne grossit pas pour la tâche qui compte les optimiseurs sur
les seuls modules marqués. Importée en tête de ``electrique.py`` sous l'ancien
nom ; ``_regle_de_chaine`` y reste et est lue à l'appel (import local : le
noyau de ce module ne dépend pas de ``electrique`` au chargement).
"""


def _regle_chaine_publiee(conception, optimiseur_specs, designation,
                          onduleur_sku=None):
    """La règle de chaîne appliquée — fiche module lue sur la conception."""
    from .electrique import _regle_de_chaine

    module = getattr(conception.entree, 'module', None)
    specs = ({'voc_v': module.voc_v, 'isc_a': module.isc_a,
              'pmax_wc': module.pmax_wc} if module is not None else {})
    return _regle_de_chaine(specs, None, optimiseur_specs,
                            designation=designation, onduleur_sku=onduleur_sku)

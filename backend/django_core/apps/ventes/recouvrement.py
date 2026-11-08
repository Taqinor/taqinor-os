"""Shim de ré-export — le recouvrement vit dans ``apps.facturation.recouvrement``.

ODX18 (App Facturation, étape 2) : le module (niveaux de relance, liste des
impayés, balance âgée, relevés clients, lettres de relance PDF, promesses et
paramétrage de relance) a été DÉPLACÉ tel quel vers ``apps.facturation``. Ce
fichier garde l'ancien chemin d'import ``apps.ventes.recouvrement`` (appelants
ventes, reporting, tests) strictement identique : ce sont les MÊMES objets, pas
des copies. Aucun changement de comportement.
"""
from apps.facturation.recouvrement import (
    NIVEAUX_RELANCE_DEFAUT,
    PROMESSE_HORIZON_JOURS_MAX,
    STATUTS_HORS_RELEVE,
    STATUTS_NON_RELANCABLES,
    VARIABLES_RELANCE,
    FollowupLevelViewSet,
    ParametrageRelanceClientViewSet,
    PromessePaiementViewSet,
    _PLACEHOLDER_RE,
    _current_level,
    _facture_due_rows,
    _levels,
    _niveau_dict,
    _niveau_suivant_ligne,
    _releve_data,
    _s,
    _scope,
    apercu_relance,
    balance_agee,
    client_releve,
    client_releve_pdf,
    client_score_comportement,
    ensure_default_followup_levels,
    facture_relancable,
    lettre_relance_pdf,
    montant_exigible,
    relances_list,
    rendre_message_relance,
    variables_relance,
)

__all__ = [
    'NIVEAUX_RELANCE_DEFAUT',
    'PROMESSE_HORIZON_JOURS_MAX',
    'STATUTS_HORS_RELEVE',
    'STATUTS_NON_RELANCABLES',
    'VARIABLES_RELANCE',
    'FollowupLevelViewSet',
    'ParametrageRelanceClientViewSet',
    'PromessePaiementViewSet',
    '_PLACEHOLDER_RE',
    '_current_level',
    '_facture_due_rows',
    '_levels',
    '_niveau_dict',
    '_niveau_suivant_ligne',
    '_releve_data',
    '_s',
    '_scope',
    'apercu_relance',
    'balance_agee',
    'client_releve',
    'client_releve_pdf',
    'client_score_comportement',
    'ensure_default_followup_levels',
    'facture_relancable',
    'lettre_relance_pdf',
    'montant_exigible',
    'relances_list',
    'rendre_message_relance',
    'variables_relance',
]

"""Selectors du module Facturation (``apps.facturation``).

Point d'entrée des LECTURES cross-app du domaine Facturation (CLAUDE.md : les
autres apps lisent ``facturation`` via ``apps.facturation.selectors`` ou par
string-FK, jamais via ``apps.facturation.models``).

Volontairement vide pour l'instant : les lectures cross-app existantes du solde
facture passent par ``apps.ventes.services``/``selectors`` (shims transitoires
ODX17). Ajouter ici une fonction de lecture fine dès qu'une autre app en aura
besoin — jamais un import direct de ``apps.facturation.models`` depuis
l'extérieur.
"""


#: APRF11 (C-APRF-025) — LES relations que lit ``Facture.montant_du`` (et
#: ``montant_paye``, ``total_ttc``, ``montant_exigible``) : lignes de la
#: facture, paiements, ventilations d'avances (+ statut du paiement source),
#: avoirs et notes de débit (+ leurs lignes, dont dépend leur TTC), retenues
#: subies (+ statut du paiement qui les porte). UNE liste, un seul
#: propriétaire.
RELATIONS_MONTANT_DU = (
    'lignes',
    'paiements',
    'affectations_paiement__paiement',
    'avoirs__lignes',
    'notes_debit__lignes',
    'retenues_subies__paiement',
)


def factures_avec_montant_du(qs):
    """APRF11 — ``qs`` (factures) préchargé de tout ce que lit
    ``montant_du`` : le reste dû de N factures coûte le même nombre de
    requêtes que celui de 3 (jamais une requête par facture)."""
    return qs.prefetch_related(*RELATIONS_MONTANT_DU)

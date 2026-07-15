"""Services du module Facturation (``apps.facturation``).

ODX18 — ré-export TRANSITOIRE des fonctions de service de facturation +
recouvrement qui vivent encore physiquement dans ``apps.ventes.services`` /
``apps.ventes.recouvrement`` (elles y étaient interleavées avec la logique
ventes). Ce module donne au reste du code (urls, appelants cross-app) un point
d'accès ``apps.facturation.services`` stable ; ODX22 re-logera le corps des
fonctions ici et retirera ce shim.

Invariants (rule #4) : les factures gardent leur PDF legacy — le flux
devis→facture reste orchestré ICI (frontière services), jamais par un import
direct des ViewSets/modèles. ``facturation`` lit crm/ventes/stock QUE via leurs
selectors/services ou par référence opaque.
"""

from apps.ventes.services import (  # noqa: F401
    abandonner_solde_facture,
    anomalies_emission_facture,
    consolider_factures,
    creer_facture_acompte_situation,
    creer_facture_classique,
    creer_facture_contrat,
    creer_facture_regie,
    dossier_contentieux_data,
    enregistrer_paiement,
    facture_montant_du,
    get_facture_or_none,
    ouvrir_dossier_contentieux,
    reset_relance_escalation,
    ventiler_avance,
)

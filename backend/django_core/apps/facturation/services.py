"""Services du module Facturation (``apps.facturation``) — façade d'écriture.

ODX18 — point d'accès STABLE ``apps.facturation.services`` aux fonctions de
service de facturation (émission, création de factures, encaissements,
avances, liens de paiement, rejet de paiement, abandon de solde, recouvrement
automatique). Leurs CORPS vivent encore dans ``apps/ventes/domain/``
(``facturation_ops``, ``encaissements``, ``recouvrement``) et sont exposés par
la surface ``apps.ventes.services`` : ce module les RÉ-EXPORTE tels quels
(mêmes objets, aucune copie, aucun changement de comportement). ODX22 re-logera
les corps ici ; les gardes qui épinglent ``apps/ventes/domain/*.py``
(ASTK129, AUD101, VNT9…) suivront ce déménagement-là.

Forme : une AFFECTATION de niveau module par nom (``nom = _ventes.nom``),
comme ``apps.ventes.services`` (QJR68). ``domain/facturation_vente`` (« Facturer
la vente », VNT26) n'est volontairement PAS ré-exporté ici.

Ordre d'import : ``apps.ventes.services`` ne lit jamais ce module → import en
tête sans cycle.

Invariants (rule #4) : les factures gardent leur PDF legacy ; rien ici ne
touche au moteur de devis ni aux statuts du devis. ``facturation`` lit
crm/ventes/stock QUE via leurs selectors/services ou par référence opaque.
"""
from apps.ventes import services as _ventes
# ASUP1 — rattrapage de l'instantané d'acheteur, lu par la commande
# ``figer_identite_acheteur``, la garde d'effacement (ASUP3) et l'anonymisation
# crm (ASUP2). Hors ``__all__`` : ``__all__`` ne liste que les noms aussi
# exposés par ``apps.ventes.services`` (ODX18, test de la façade).
from apps.ventes.domain.instantanes_facture import (  # noqa: F401 — ré-export de façade
    figer_identite_acheteur_manquante,
)

# ── Émission et création de factures (``domain/facturation_ops.py``) ──────────
StockInsuffisantError = _ventes.StockInsuffisantError
EmissionRefusee = _ventes.EmissionRefusee
emettre_facture = _ventes.emettre_facture
reserver_stock_devis_facture = _ventes.reserver_stock_devis_facture
creer_facture_contrat = _ventes.creer_facture_contrat
creer_facture_regie = _ventes.creer_facture_regie
creer_facture_acompte_situation = _ventes.creer_facture_acompte_situation
creer_facture_classique = _ventes.creer_facture_classique
creer_facture_consignation = _ventes.creer_facture_consignation
ajouter_lignes_frais_refactures = _ventes.ajouter_lignes_frais_refactures
calculer_date_echeance = _ventes.calculer_date_echeance
get_facture_or_none = _ventes.get_facture_or_none
facturables_pour_devis = _ventes.facturables_pour_devis
generer_facture_ticket_sav = _ventes.generer_facture_ticket_sav
generer_facture_intervention = _ventes.generer_facture_intervention

# ── Encaissements (``domain/encaissements.py``) ──────────────────────────────
AcompteAvantDelaiLegal = _ventes.AcompteAvantDelaiLegal
marquer_facture_soldee = _ventes.marquer_facture_soldee
enregistrer_paiement = _ventes.enregistrer_paiement
facture_montant_du = _ventes.facture_montant_du
affecter_encaissement_groupe = _ventes.affecter_encaissement_groupe
create_payment_link = _ventes.create_payment_link
public_url = _ventes.public_url
LinkError = _ventes.LinkError
expirer_liens_paiement_perimes = _ventes.expirer_liens_paiement_perimes
revoquer_lien_paiement = _ventes.revoquer_lien_paiement
qr_svg_for_facture_pdf = _ventes.qr_svg_for_facture_pdf
record_payment_from_link = _ventes.record_payment_from_link
enregistrer_avance = _ventes.enregistrer_avance
ventiler_avance = _ventes.ventiler_avance
enregistrer_paiement_avec_retenue = _ventes.enregistrer_paiement_avec_retenue
consolider_factures = _ventes.consolider_factures

# ── Recouvrement et contrôles d'émission (``domain/recouvrement.py``) ────────
RELANCE_AUTO_NOTE = _ventes.RELANCE_AUTO_NOTE
RELANCE_AUTO_NOTE_RESOLUE = _ventes.RELANCE_AUTO_NOTE_RESOLUE
reset_relance_escalation = _ventes.reset_relance_escalation
PaiementRejectError = _ventes.PaiementRejectError
rejeter_paiement = _ventes.rejeter_paiement
abandonner_solde_facture = _ventes.abandonner_solde_facture
anomalies_emission_facture = _ventes.anomalies_emission_facture
CreditHoldError = _ventes.CreditHoldError
verifier_credit_hold = _ventes.verifier_credit_hold

__all__ = [
    'StockInsuffisantError', 'EmissionRefusee', 'emettre_facture',
    'reserver_stock_devis_facture', 'creer_facture_contrat',
    'creer_facture_regie', 'creer_facture_acompte_situation',
    'creer_facture_classique', 'creer_facture_consignation',
    'ajouter_lignes_frais_refactures', 'calculer_date_echeance',
    'get_facture_or_none', 'facturables_pour_devis',
    'generer_facture_ticket_sav', 'generer_facture_intervention',
    'AcompteAvantDelaiLegal', 'marquer_facture_soldee', 'enregistrer_paiement',
    'facture_montant_du', 'affecter_encaissement_groupe',
    'create_payment_link', 'public_url', 'LinkError',
    'expirer_liens_paiement_perimes', 'revoquer_lien_paiement',
    'qr_svg_for_facture_pdf', 'record_payment_from_link',
    'enregistrer_avance', 'ventiler_avance',
    'enregistrer_paiement_avec_retenue', 'consolider_factures',
    'RELANCE_AUTO_NOTE', 'RELANCE_AUTO_NOTE_RESOLUE',
    'reset_relance_escalation', 'PaiementRejectError', 'rejeter_paiement',
    'abandonner_solde_facture', 'anomalies_emission_facture',
    'CreditHoldError', 'verifier_credit_hold',
]

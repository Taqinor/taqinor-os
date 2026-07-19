"""NTPLT12 — Catalogue central des événements métier + enveloppe versionnée.

Deux garanties pour un contrat d'intégration STABLE et documenté (les équipes
IT du client s'y appuient) :

1. ENVELOPPE VERSIONNÉE — chaque payload d'événement fiable (outbox NTPLT9)
   porte les champs standard ``ENVELOPE_KEYS`` : ``schema_version``,
   ``event_id``, ``company_id``, ``emitted_by``, ``occurred_at``.
   ``wrap_envelope(event, payload, ...)`` produit ce dictionnaire normalisé.

2. CATALOGUE — ``CATALOG`` associe chaque nom d'événement à sa VERSION, une
   DESCRIPTION et la liste des CLÉS de payload attendues. Un test de couverture
   (``core.event_coverage.uncatalogued_events``) échoue si un ``Signal`` déclaré
   dans ``core.events`` n'est pas au catalogue — le catalogue ne peut donc pas
   dériver silencieusement de la réalité du bus.

``core`` reste fondation : ce module n'importe aucune app métier (il ne fait que
décrire des noms d'événements).
"""
from __future__ import annotations

import uuid

# Champs standard de l'enveloppe versionnée (présents sur tout payload fiable).
ENVELOPE_KEYS = (
    'schema_version', 'event_id', 'company_id', 'emitted_by', 'occurred_at',
)

# Version d'enveloppe courante (incrémentée si la STRUCTURE de l'enveloppe
# change — jamais pour un changement de payload d'UN événement, qui bump la
# version de CET événement dans CATALOG).
ENVELOPE_VERSION = 1


def _e(description, payload, version=1):
    """Fabrique une entrée de catalogue normalisée."""
    return {'version': version, 'description': description,
            'payload': list(payload)}


# Catalogue : nom d'événement -> {version, description, payload (clés métier)}.
# Les clés d'ENVELOPPE (ENVELOPE_KEYS) s'ajoutent à ces clés métier sur les
# événements émis via l'outbox. Tout NOUVEAU signal de ``core.events`` DOIT
# recevoir une entrée ici (sinon le test de couverture échoue).
CATALOG = {
    'meta_lead_captured': _e(
        'Un lead Meta Lead Ads est capturé (webhook CRM).',
        ['lead', 'company', 'leadgen_id', 'ad_id', 'adset_id',
         'campaign_id', 'form_id', 'created_time', 'is_organic']),
    'lead_erased': _e(
        'Un lead CRM est effacé (droit à l\'oubli CNDP) — propage '
        'l\'anonymisation aux miroirs qui le référencent par STRING.',
        ['company', 'crm_lead_id', 'phone_key']),
    'devis_accepted': _e(
        'Un devis passe à « accepté ».',
        ['devis', 'user', 'ancien_statut']),
    'devis_sent': _e(
        'Un devis passe à « envoyé » (partage client).',
        ['devis', 'user', 'ancien_statut']),
    'devis_refused': _e(
        'Un devis passe à « refusé ».',
        ['devis', 'user', 'motif_refus', 'marquer_lead_perdu']),
    'devis_expired': _e(
        'Un devis envoyé bascule automatiquement en « expiré ».',
        ['devis', 'ancien_statut']),
    'document_pdf_generated': _e(
        'Un PDF de document a été généré.',
        ['instance', 'kind']),
    'payment_captured': _e(
        'Un paiement carte en ligne a été capturé.',
        ['transaction', 'company']),
    'reception_fournisseur_confirmee': _e(
        'Une réception fournisseur est confirmée.',
        ['reception', 'company', 'user']),
    'employe_sorti': _e(
        'Un employé quitte l’entreprise (sortie RH).',
        ['dossier', 'user', 'motif']),
    'conge_approuve': _e(
        'Une demande de congé est approuvée (ou annulée : annule=True).',
        ['demande', 'user', 'annule']),
    'contrat_signe': _e(
        'Un contrat est signé.',
        ['contrat', 'company', 'user']),
    'contrat_actif': _e(
        'Un contrat devient actif.',
        ['contrat', 'company', 'user']),
    'contrat_resilie': _e(
        'Un contrat est résilié.',
        ['contrat_id', 'company', 'date_effet']),
    'document_produit': _e(
        'Un document métier a été produit.',
        ['document', 'company', 'user']),
    'intervention_completed': _e(
        'Une intervention est marquée terminée.',
        ['intervention', 'company', 'user']),
    'facture_paid': _e(
        'Une facture est réglée (signal frère déprécié de facture_payee).',
        ['facture', 'company', 'montant']),
    'paiement_rejete': _e(
        'Un paiement est rejeté.',
        ['paiement', 'facture', 'montant', 'company']),
    'facture_emise': _e(
        'Une facture est émise.',
        ['instance', 'company']),
    'facture_payee': _e(
        'Une facture est réglée.',
        ['instance', 'company']),
    'facture_annulee': _e(
        'Une facture est annulée.',
        ['instance', 'company']),
    'bon_commande_cree': _e(
        'Un bon de commande est créé.',
        ['instance', 'company']),
    'paiement_enregistre': _e(
        'Un paiement client est enregistré.',
        ['instance', 'company']),
    'avoir_cree': _e(
        'Un avoir est créé.',
        ['instance', 'company']),
    'facture_fournisseur_creee': _e(
        'Une facture fournisseur est créée.',
        ['instance', 'company', 'user']),
    'paiement_fournisseur_enregistre': _e(
        'Un paiement fournisseur est enregistré.',
        ['instance', 'company']),
    'chantier_annule': _e(
        'Un chantier est annulé.',
        ['installation', 'company', 'user']),
    'effet_rejete': _e(
        'Un effet (LCN/chèque) est rejeté.',
        ['effet', 'company', 'frais', 'paiement_id']),
    'abonnement_monitoring_resilie': _e(
        'Un abonnement de monitoring est résilié.',
        ['abonnement', 'company', 'motif']),
    'chantier_receptionne': _e(
        'Un chantier est réceptionné.',
        ['installation', 'user', 'ancien_statut']),
    'ticket_resolu': _e(
        'Un ticket SAV bascule vers « résolu ».',
        ['ticket', 'company', 'user', 'ancien_statut']),
    'equipement_remplace': _e(
        'Un équipement SAV est marqué « remplacé ».',
        ['equipement', 'ticket', 'company', 'user']),
    'projet_status_change': _e(
        'Un projet change de statut.',
        ['projet', 'company', 'user', 'ancien_statut', 'nouveau_statut']),
    'incident_declared': _e(
        'Un incident QHSE est déclaré.',
        ['incident', 'company', 'user', 'gravite']),
    'document_statut_change': _e(
        'Un document métier (kit SCA30) change de statut.',
        ['instance', 'ancien_statut', 'nouveau_statut', 'user', 'company']),
    'lead_stage_changed': _e(
        "Un lead CRM change d'étape de pipeline (STAGES.py).",
        ['lead', 'old_stage', 'new_stage', 'user']),
    'budget_cycle_clos': _e(
        'Un cycle budgétaire FP&A (NTFPA29) bascule vers « clos ».',
        ['company', 'cycle_id', 'totaux']),
    'entite_created': _e(
        'Une entité intra-tenant (NTADM40) est créée.',
        ['entite', 'user']),
    'entite_deactivated': _e(
        'Une entité intra-tenant (NTADM40) est désactivée.',
        ['entite', 'user']),
    'appointment_effectue': _e(
        "Un rendez-vous CRM (Appointment) bascule vers « effectué ».",
        ['appointment', 'company', 'user', 'ancien_statut']),
}


def catalog_names() -> set:
    """Ensemble des noms d'événements présents au catalogue."""
    return set(CATALOG.keys())


def entry(event_name: str):
    """Entrée de catalogue d'un événement, ou ``None`` si absent."""
    return CATALOG.get(event_name)


def event_version(event_name: str) -> int:
    """Version d'un événement (défaut 1 si non catalogué)."""
    item = CATALOG.get(event_name)
    return item['version'] if item else 1


def wrap_envelope(event_name, payload=None, *, company_id=None,
                  emitted_by=None, occurred_at=None, event_id=None):
    """Enveloppe un payload métier avec les champs standard versionnés.

    Renvoie un dict = payload métier + ``ENVELOPE_KEYS``. ``event_id`` est
    généré (UUID4) si absent ; ``occurred_at`` est laissé tel quel (le
    producteur y met un ISO ou l'outbox le fixe). ``schema_version`` = version
    catalogue de l'événement.
    """
    envelope = dict(payload or {})
    envelope.update({
        'schema_version': event_version(event_name),
        'event_id': event_id or str(uuid.uuid4()),
        'company_id': company_id,
        'emitted_by': emitted_by,
        'occurred_at': occurred_at,
    })
    return envelope

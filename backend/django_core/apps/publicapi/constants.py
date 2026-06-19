"""Constantes partagées de l'API publique (N89).

Les scopes et les évènements vivent ici pour que le modèle, les permissions,
les serializers et les tests partagent une source unique. Identifiants en
anglais (code), libellés FR pour l'écran Paramètres.
"""

# ── Scopes (droits de lecture par objet métier) ──────────────────────────────
SCOPE_READ_LEADS = 'read:leads'
SCOPE_READ_DEVIS = 'read:devis'
SCOPE_READ_FACTURES = 'read:factures'
SCOPE_READ_CHANTIERS = 'read:chantiers'

# Ordre = ordre d'affichage dans l'écran Paramètres.
SCOPE_CHOICES = [
    (SCOPE_READ_LEADS, 'Lire les leads'),
    (SCOPE_READ_DEVIS, 'Lire les devis'),
    (SCOPE_READ_FACTURES, 'Lire les factures'),
    (SCOPE_READ_CHANTIERS, 'Lire les chantiers'),
]
ALL_SCOPES = [code for code, _ in SCOPE_CHOICES]


# ── Évènements webhook ───────────────────────────────────────────────────────
EVENT_LEAD_CREATED = 'lead.created'
EVENT_DEVIS_ACCEPTED = 'devis.accepted'
EVENT_CHANTIER_COMPLETED = 'chantier.completed'
EVENT_FACTURE_PAID = 'facture.paid'

EVENT_CHOICES = [
    (EVENT_LEAD_CREATED, 'Nouveau lead'),
    (EVENT_DEVIS_ACCEPTED, 'Devis accepté'),
    (EVENT_CHANTIER_COMPLETED, 'Chantier clôturé'),
    (EVENT_FACTURE_PAID, 'Facture payée'),
]
ALL_EVENTS = [code for code, _ in EVENT_CHOICES]

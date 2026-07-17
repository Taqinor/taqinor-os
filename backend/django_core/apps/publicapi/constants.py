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
# XSTK23 — lecture produits (disponibilité) : SKU/nom/marque/catégorie/quantité
# disponible UNIQUEMENT. Ni prix_achat ni prix_vente ni aucun coût.
SCOPE_READ_STOCK = 'read:stock'

# XPLT5 — scopes d'ÉCRITURE (créer/mettre à jour un lead, créer une activité).
# La société est TOUJOURS forcée depuis la clé (jamais du body) ; les stages
# viennent de STAGES.py (jamais hardcodés).
SCOPE_WRITE_LEADS = 'leads:write'
SCOPE_WRITE_ACTIVITIES = 'activities:write'

# Ordre = ordre d'affichage dans l'écran Paramètres.
SCOPE_CHOICES = [
    (SCOPE_READ_LEADS, 'Lire les leads'),
    (SCOPE_READ_DEVIS, 'Lire les devis'),
    (SCOPE_READ_FACTURES, 'Lire les factures'),
    (SCOPE_READ_CHANTIERS, 'Lire les chantiers'),
    (SCOPE_READ_STOCK, 'Lire le stock (disponibilité, sans coûts)'),
    (SCOPE_WRITE_LEADS, 'Créer/mettre à jour des leads'),
    (SCOPE_WRITE_ACTIVITIES, 'Créer des activités (notes) sur un lead'),
]
ALL_SCOPES = [code for code, _ in SCOPE_CHOICES]


# ── Évènements webhook ───────────────────────────────────────────────────────
EVENT_LEAD_CREATED = 'lead.created'
EVENT_LEAD_LOST = 'lead.lost'
EVENT_LEAD_STAGE_CHANGED = 'lead.stage_changed'
EVENT_DEVIS_SENT = 'devis.sent'
EVENT_DEVIS_ACCEPTED = 'devis.accepted'
EVENT_FACTURE_CREATED = 'facture.created'
EVENT_FACTURE_PAID = 'facture.paid'
EVENT_PAIEMENT_RECORDED = 'paiement.recorded'
EVENT_CHANTIER_COMPLETED = 'chantier.completed'
EVENT_INTERVENTION_COMPLETED = 'intervention.completed'
EVENT_TICKET_CREATED = 'ticket.created'
EVENT_TICKET_RESOLVED = 'ticket.resolved'
# XSTK23 — évènements inventaire.
EVENT_STOCK_SEUIL_ATTEINT = 'stock.seuil_atteint'
EVENT_LIVRAISON_LIVREE = 'livraison.livree'

EVENT_CHOICES = [
    (EVENT_LEAD_CREATED, 'Nouveau lead'),
    (EVENT_LEAD_LOST, 'Lead perdu'),
    (EVENT_LEAD_STAGE_CHANGED, "Lead — étape changée"),
    (EVENT_DEVIS_SENT, 'Devis envoyé'),
    (EVENT_DEVIS_ACCEPTED, 'Devis accepté'),
    (EVENT_FACTURE_CREATED, 'Facture créée'),
    (EVENT_FACTURE_PAID, 'Facture payée'),
    (EVENT_PAIEMENT_RECORDED, 'Paiement enregistré'),
    (EVENT_CHANTIER_COMPLETED, 'Chantier clôturé'),
    (EVENT_INTERVENTION_COMPLETED, 'Intervention terminée'),
    (EVENT_TICKET_CREATED, 'Ticket SAV créé'),
    (EVENT_TICKET_RESOLVED, 'Ticket SAV résolu'),
    (EVENT_STOCK_SEUIL_ATTEINT, 'Stock — seuil atteint'),
    (EVENT_LIVRAISON_LIVREE, 'Livraison — livrée'),
]
ALL_EVENTS = [code for code, _ in EVENT_CHOICES]


# ── NTAPI26 — environnement d'une clé (préfixe distinct, isolation bac à
# sable) ───────────────────────────────────────────────────────────────────
ENV_TEST = 'test'
ENV_LIVE = 'live'
ENV_CHOICES = [
    (ENV_TEST, 'Test (bac à sable, `tqk_test_…`)'),
    (ENV_LIVE, 'Live (données réelles, `tqk_live_…`)'),
]
ALL_ENVIRONMENTS = [code for code, _ in ENV_CHOICES]

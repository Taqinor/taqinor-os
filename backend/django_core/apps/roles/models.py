from django.db import models


ALL_PERMISSIONS = [
    'stock_voir',
    'stock_creer',
    'stock_modifier',
    'stock_supprimer',
    'stock_mouvement',
    'stock_export',
    'crm_voir',
    'crm_creer',
    'crm_modifier',
    'crm_supprimer',
    'crm_export',
    'crm_reassign',
    'ventes_voir',
    'ventes_creer',
    'ventes_modifier',
    'ventes_supprimer',
    'ventes_valider',
    'ventes_pdf',
    'ventes_export',
    'ventes_reassign',
    'installation_voir',
    'installation_gerer',
    'installation_export',
    'intervention_gerer',
    'technicien_assign',
    'equipement_voir',
    'equipement_gerer',
    'sav_voir',
    'sav_gerer',
    'sav_export',
    'sav_reassign',
    'parametres_voir',
    'parametres_modifier',
    'users_voir',
    'users_gerer',
    'roles_gerer',
    'reporting_voir',
    'reporting_export',
    # ── Comptabilité — séparation des tâches (COMPTA40) ──
    # Trois actions DISJOINTES du flux comptable : saisir une écriture, la
    # valider (second regard) et clôturer une période/exercice. La règle
    # « le saisisseur ne valide pas sa propre écriture » est posée en dur côté
    # service (``compta.services.valider_ecriture``) ; ces codes gouvernent QUI
    # a le droit d'accéder à chaque action. ``compta_cloturer`` est une action
    # de gouvernance réservée par défaut au palier direction.
    'compta_saisir',
    'compta_valider',
    'compta_cloturer',
    # ── Données sensibles & gouvernance (Feature D, 2026-06) ──
    # Voir les prix d'achat et la marge interne (générateur, stock). Accordée à
    # Directeur + Administrateur par défaut ; jamais sur un document client.
    'prix_achat_voir',
    # Voir le Journal d'activité (audit). Directeur uniquement par défaut.
    'journal_activite_voir',
    # ── Rémunération RH (Feature G, 2026-06) ──
    # Lire ET écrire la rémunération de base d'un employé (salaire, périodicité,
    # historique). Donnée paie sensible : réservée au palier RH (Directeur +
    # Administrateur par défaut) ; ne fuit jamais dans une sortie client.
    'salaires_voir',
    # ── Données sensibles (FG20) — groupe « Données sensibles » curé ──
    # Permissions de LECTURE qui DÉMASQUENT une donnée sensible dans les
    # sérialiseurs ; absentes → la donnée est masquée. ÉLEVÉES (octroi réservé à
    # l'admin). Repli légacy : un compte SANS rôle fin garde l'accès historique
    # (jamais de régression pour les comptes hérités).
    # `client_pii_voir` : voir les coordonnées personnelles du client/lead
    # (téléphone, email, adresse, WhatsApp, GPS). `marge_voir` : voir la marge
    # interne calculée (indicateur générateur). Distinct de `prix_achat_voir`
    # (prix d'achat brut), qui reste la garde du prix d'achat lui-même.
    'client_pii_voir',
    'marge_voir',
    # ── Portée de visibilité des enregistrements (Feature F) ──
    # Marqueurs de RÔLE (pas des cases « action ») : narrowing OPT-IN. Un rôle
    # SANS l'un de ces marqueurs voit tous les enregistrements de sa société
    # (comportement historique préservé — légacy, rôles personnalisés, admins).
    # `records_scope_equipe` : ses propres enregistrements + ceux de ses pairs
    # (même superviseur direct). `records_scope_sous_arbre` : les siens + tout
    # son sous-arbre (toute personne lui remontant, récursivement).
    'records_scope_equipe',
    'records_scope_sous_arbre',
]

# Permissions de portée : un rôle qui en porte une voit un sous-ensemble ; sans
# l'une d'elles, le rôle voit tout (par société). Source unique de vérité.
SCOPE_TEAM = 'records_scope_equipe'
SCOPE_SUBTREE = 'records_scope_sous_arbre'

# Permissions ÉLEVÉES (ERR5) : octroyer l'une d'elles donne le contrôle des
# rôles eux-mêmes (``roles_gerer`` = clé admin/escalade) ou l'accès aux données
# sensibles (prix d'achat/marge, journal d'audit). Un non-administrateur ne peut
# JAMAIS les ajouter à un rôle — sinon un Responsable s'auto-promeut
# Administrateur en cochant ``roles_gerer`` sur son propre rôle. Réservées au
# palier admin (porteur de ``roles_gerer``) côté serializer/vue.
ELEVATED_PERMISSIONS = frozenset({
    'roles_gerer',
    'prix_achat_voir',
    'journal_activite_voir',
    'salaires_voir',
    # FG20 — données sensibles : démasquer la marge interne est élevé (même
    # niveau que le prix d'achat). La PII client n'est PAS élevée : voir les
    # coordonnées d'un client est un besoin opérationnel courant (commercial),
    # donc ``client_pii_voir`` reste octroyable par un Responsable.
    'marge_voir',
})

RESPONSABLE_PERMISSIONS = [
    'stock_voir',
    'stock_creer',
    'stock_modifier',
    'stock_mouvement',
    'crm_voir',
    'crm_creer',
    'crm_modifier',
    'ventes_voir',
    'ventes_creer',
    'ventes_modifier',
    'ventes_valider',
    'ventes_pdf',
    # La Commerciale gère le flux chantier (création depuis devis, suivi,
    # interventions). L'admin garde le contrôle total (suppression).
    'installation_voir',
    'installation_gerer',
    'intervention_gerer',
    # SAV : la Commerciale consulte le parc d'équipements et ouvre/traite les
    # tickets après-vente. La GESTION du parc (ajout d'équipements) reste admin.
    'equipement_voir',
    'sav_voir',
    'sav_gerer',
    'parametres_voir',
    'users_voir',
    'reporting_voir',
    # COMPTA40 — le Responsable peut saisir ET valider des écritures (mais la
    # séparation des tâches empêche toujours de valider sa PROPRE saisie) ; la
    # clôture reste au palier direction/admin.
    'compta_saisir',
    'compta_valider',
    # FG20 — la Commerciale/Responsable voit les coordonnées client (besoin
    # opérationnel) ; comportement historique préservé.
    'client_pii_voir',
]

UTILISATEUR_PERMISSIONS = [
    'stock_voir',
    'crm_voir',
    'ventes_voir',
    'installation_voir',
    'equipement_voir',
    'sav_voir',
    'parametres_voir',
    'reporting_voir',
    # FG20 — préserve l'accès historique aux coordonnées client.
    'client_pii_voir',
]


# ── Les SEPT rôles (Feature D, 2026-06) ────────────────────────────────────
# Chacun reçoit les défauts ci-dessous ; TOUT reste éditable ensuite dans
# Paramètres (grille module × action). « Admin » = le rôle « Administrateur »
# existant (nom conservé pour la rétro-compatibilité données/tests). Les rôles
# système légacy « Responsable » et « Utilisateur » restent définis plus haut
# pour les comptes/données déjà en place ; ils voient tout (aucun marqueur de
# portée) — comportement historique préservé.

# Directeur : accès total, prix d'achat/marges, et le Journal d'activité.
# Aucun marqueur de portée → voit tous les enregistrements de la société.
DIRECTEUR_PERMISSIONS = [
    p for p in ALL_PERMISSIONS
    if p not in (SCOPE_TEAM, SCOPE_SUBTREE)
]

# Administrateur (= « Admin ») : comme le Directeur, MAIS sans le Journal
# d'activité par défaut (réservé Directeur, octroyable dans Paramètres).
ADMIN_PERMISSIONS = [
    p for p in DIRECTEUR_PERMISSIONS if p != 'journal_activite_voir'
]

# Commercial responsable : CRM/Ventes/SAV complets, peut réassigner leads/
# devis/tickets dans l'équipe ; voit son sous-arbre ; pas de prix d'achat.
COMMERCIAL_RESP_PERMISSIONS = [
    'crm_voir', 'crm_creer', 'crm_modifier', 'crm_supprimer', 'crm_export',
    'crm_reassign',
    'ventes_voir', 'ventes_creer', 'ventes_modifier', 'ventes_supprimer',
    'ventes_valider', 'ventes_pdf', 'ventes_export', 'ventes_reassign',
    'equipement_voir', 'sav_voir', 'sav_gerer', 'sav_export', 'sav_reassign',
    'parametres_voir', 'users_voir', 'reporting_voir', 'reporting_export',
    'client_pii_voir',  # FG20 — coordonnées client (besoin commercial).
    SCOPE_SUBTREE,
]

# Commercial : l'accès de la « Commerciale » d'aujourd'hui ; voit son équipe
# (pairs) ; pas de prix d'achat, pas de réassignation.
COMMERCIAL_PERMISSIONS = [
    'crm_voir', 'crm_creer', 'crm_modifier', 'crm_export',
    'ventes_voir', 'ventes_creer', 'ventes_modifier', 'ventes_valider',
    'ventes_pdf', 'ventes_export',
    'stock_voir', 'equipement_voir', 'sav_voir',
    'parametres_voir', 'reporting_voir',
    'client_pii_voir',  # FG20 — coordonnées client (besoin commercial).
    SCOPE_TEAM,
]

# Technicien responsable : Chantiers/SAV/Stock complets, assigne les
# techniciens ; voit son sous-arbre ; pas de prix d'achat.
TECHNICIEN_RESP_PERMISSIONS = [
    'installation_voir', 'installation_gerer', 'installation_export',
    'intervention_gerer', 'technicien_assign',
    'equipement_voir', 'equipement_gerer', 'sav_voir', 'sav_gerer',
    'sav_export', 'sav_reassign',
    'stock_voir', 'stock_creer', 'stock_modifier', 'stock_mouvement',
    'stock_export',
    'parametres_voir', 'users_voir', 'reporting_voir', 'reporting_export',
    'client_pii_voir',  # FG20 — coordonnées client (intervention terrain).
    SCOPE_SUBTREE,
]

# Technicien : Chantiers/Installations et SAV pour le travail assigné, Stock en
# vue + mouvements ; pas d'édition Ventes ; voit son équipe (pairs).
TECHNICIEN_PERMISSIONS = [
    'installation_voir', 'installation_gerer', 'intervention_gerer',
    'equipement_voir', 'sav_voir', 'sav_gerer',
    'stock_voir', 'stock_mouvement',
    'parametres_voir', 'reporting_voir',
    'client_pii_voir',  # FG20 — coordonnées client (intervention terrain).
    SCOPE_TEAM,
]

# Viewer : lecture seule partout dans sa portée ; aucune création/édition/
# suppression/export ; pas de prix d'achat. Portée = sa position dans l'arbre.
VIEWER_PERMISSIONS = [
    'stock_voir', 'crm_voir', 'ventes_voir', 'installation_voir',
    'equipement_voir', 'sav_voir', 'parametres_voir', 'reporting_voir',
    'client_pii_voir',  # FG20 — préserve l'accès historique aux coordonnées.
    SCOPE_TEAM,
]

# Registre canonique : (nom, permissions). Les trois premiers conservent les
# noms système historiques. Ordre = ordre d'affichage souhaité. Le seeder crée/
# met à jour ces rôles système pour chaque société (idempotent, additif).
CANONICAL_SYSTEM_ROLES = [
    ('Directeur', DIRECTEUR_PERMISSIONS),
    ('Administrateur', ADMIN_PERMISSIONS),
    ('Commercial responsable', COMMERCIAL_RESP_PERMISSIONS),
    ('Commercial', COMMERCIAL_PERMISSIONS),
    ('Technicien responsable', TECHNICIEN_RESP_PERMISSIONS),
    ('Technicien', TECHNICIEN_PERMISSIONS),
    ('Viewer', VIEWER_PERMISSIONS),
    # Rôles légacy conservés pour les comptes/données déjà en place.
    ('Responsable', RESPONSABLE_PERMISSIONS),
    ('Utilisateur', UTILISATEUR_PERMISSIONS),
]


class Role(models.Model):
    company = models.ForeignKey(
        'authentication.Company',  # app_label.ModelName
        on_delete=models.CASCADE,
        related_name='roles',
    )
    nom = models.CharField(max_length=100)
    permissions = models.JSONField(default=list)
    est_systeme = models.BooleanField(default=False)

    class Meta:
        unique_together = [('company', 'nom')]
        verbose_name = 'Rôle'
        verbose_name_plural = 'Rôles'
        ordering = ['company', 'nom']

    def __str__(self):
        return f'{self.company.nom} — {self.nom}'

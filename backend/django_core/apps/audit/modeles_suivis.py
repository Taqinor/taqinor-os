"""Registre des modèles suivis par le journal d'audit (TRACKED_MODELS, MODELES_SANS_UPDATE_GENERIQUE) — sorti de audit/signals.py par SPL305."""
# (app_label, ModelName) des objets métier suivis.
TRACKED_MODELS = [
    ('crm', 'Lead'),
    ('crm', 'Client'),
    ('ventes', 'Devis'),
    # ODX17 — Facture/Avoir/Paiement déplacés vers l'app ``facturation``
    # (state-only) : l'app_label suit le modèle pour que get_model résolve.
    ('facturation', 'Facture'),
    ('facturation', 'Avoir'),
    ('facturation', 'RelanceLog'),
    # FG15 — écritures « argent » : bon de commande client + encaissements.
    ('ventes', 'BonCommande'),
    ('facturation', 'Paiement'),
    ('installations', 'Installation'),
    ('installations', 'Intervention'),
    ('sav', 'Ticket'),
    ('sav', 'Equipement'),
    # FG15 — contrat de maintenance (engagement récurrent facturable).
    ('sav', 'ContratMaintenance'),
    ('stock', 'Produit'),
    ('stock', 'MouvementStock'),
    # WIR1 — RIB/coordonnées/conditions de paiement fournisseur alimentent
    # toute la chaîne achats déjà tracée (BCF/réceptions/factures/paiements
    # fournisseur) mais leur propre modification ne produisait aucune ligne
    # AuditLog (perte d'audit silencieuse, surface fraude).
    ('stock', 'Fournisseur'),
    # FG15 — chaîne achats fournisseur (argent sortant : commande → réception
    # → facture → paiement). ODX19 — déplacés de ``stock`` vers ``achats``.
    ('achats', 'BonCommandeFournisseur'),
    ('achats', 'ReceptionFournisseur'),
    ('achats', 'FactureFournisseur'),
    ('achats', 'PaiementFournisseur'),
    ('parametres', 'CompanyProfile'),
    ('authentication', 'CustomUser'),
    ('roles', 'Role'),
    # FG15 — sécurité : émission/révocation de clés API et de webhooks.
    ('publicapi', 'ApiKey'),
    ('publicapi', 'Webhook'),
    # SOLMVP (2026-09-21) — paie/kb/gestion_projet/btp_chantier/cpq/rh sont
    # des apps PARQUÉES (Groupe SOLMVP, MVP solaire) : ``models.py`` ne porte
    # plus aucune classe, donc leurs entrées ne résolvent plus
    # (``test_all_tracked_models_resolve``). Retirées d'ici comme leurs
    # modèles ; leurs lignes AuditLog historiques restent intactes (aucune
    # table touchée), et l'entrée reviendrait avec le module au retour
    # (docs/parked-modules.md).
    # AUD813 — le changelog produit est GLOBAL (aucune FK société) et republié
    # sans authentification par ``apps.publicapi`` : son écriture (désormais
    # réservée au superutilisateur) doit laisser une trace au Journal.
    ('core', 'ChangelogEntry'),
    # AUD809 — les trois REGISTRES LÉGAUX CNDP / loi 09-08 (consentement,
    # demandes de personnes concernées, registre des traitements) n'étaient
    # dans AUCUN mécanisme de traçabilité : une preuve de consentement pouvait
    # être fabriquée ou effacée sans laisser une ligne. Ils sont désormais
    # append-only côté API ET suivis ici — la création reste la seule écriture
    # possible, et elle est datée/attribuée.
    ('core', 'ConsentRecord'),
    ('core', 'DataSubjectRequest'),
    ('core', 'RegistreTraitement'),
    # CHT25 — RegulatoryDossier (dossier réglementaire 82-21/ONEE/ANRE, côté
    # ventes) n'avait AUCUN historique daté de ses transitions — contrairement
    # au chantier, tracé par son chatter. Dépôt, complément demandé,
    # approbation, refus… doivent laisser une ligne au Journal comme le reste
    # des pièces réglementaires déjà suivies ici.
    ('ventes', 'RegulatoryDossier'),
]

# ── UN SEUL ÉCRIVAIN PAR LIGNE D'AUDIT ─────────────────────────────────────
# Modèles suivis dont la MODIFICATION porte déjà un écrivain DÉDIÉ dans son
# app (``recorder.record_field_change`` appelé par la vue) : le diff générique
# ci-dessous n'est alors PAS écrit, sans quoi chaque modification laisserait
# DEUX lignes UPDATE (la dédiée, riche, et la générique) — un journal qui
# compte double n'est plus un journal.
#
# La CRÉATION, la SUPPRESSION et les changements de statut restent, eux,
# entièrement génériques : l'entrée du modèle dans ``TRACKED_MODELS`` garde
# tout son sens.
MODELES_SANS_UPDATE_GENERIQUE = {
    # AUD609 a inscrit ``PrixContractuel`` ici pour que sa SUPPRESSION laisse
    # enfin une trace (« Fix : PrixContractuel ajouté à TRACKED_MODELS pour que
    # son DELETE soit journalisé »). Sa MODIFICATION, elle, appartient depuis
    # NTCPQ46 à ``cpq.views.PrixContractuelViewSet.perform_update``, qui écrit
    # l'ancien et le nouveau prix, et SEULEMENT quand ``prix_ht`` a bougé —
    # une ligne plus précise que le diff générique, et la seule attendue.
    ('cpq', 'PrixContractuel'),
}

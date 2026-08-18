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
    'layout_finalise': _e(
        'La conception 3D d\'un devis est finalisée (création depuis un '
        'calepinage ou resynchronisation réussie) — aucun statut ne bouge.',
        ['devis', 'user']),
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
    # ZGED6 — le payload décrit le FICHIER produit (pas un objet « document »
    # déjà en base) : c'est ce que ``ged.receivers`` route vers le dossier GED
    # configuré pour la ``source``. WIR165 en a posé le premier émetteur réel
    # (``ventes.utils.pdf`` → source='ventes_facture'), d'où l'alignement de
    # ces clés sur les kwargs réellement envoyés.
    'document_produit': _e(
        "Une app émettrice a produit un fichier à centraliser en GED "
        "(routé par ``source`` via RoutageDocumentaire).",
        ['source', 'company', 'file', 'filename', 'reference', 'contexte',
         'uploaded_by']),
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
    'cycle_sterilisation_non_conforme': _e(
        'Un cycle de stérilisation (NTSAN23) est déclaré non conforme — '
        'QHSE ouvre une non-conformité liée.',
        ['cycle', 'company', 'user']),
    # WIR85 / XACC6 — émis par ``stock.services.record_stock_movement`` (le
    # SEUL point de création d'un ``MouvementStock``), synchroniquement et en
    # best-effort juste après l'écriture du mouvement. Abonné : compta
    # (inventaire permanent), doublement gated (COMPTA_AUTO_ECRITURES +
    # PlanComptable.inventaire_permanent, OFF par défaut).
    'mouvement_stock_enregistre': _e(
        "Un mouvement de stock (stock.MouvementStock) vient d'être "
        "enregistré — entrée, sortie ou ajustement.",
        ['instance', 'company']),
    # PVSYNC — émis par ``stock.views.produit.ProduitViewSet.perform_update``
    # (le seul point de mise à jour REST d'une référence), jamais par un
    # ``post_save`` de modèle. ``champs`` porte l'AVANT/APRÈS en chaînes : sans
    # l'ancienne valeur, un abonné ne peut plus distinguer une ligne de devis
    # restée au prix catalogue d'une ligne négociée. Abonné : ``ventes``
    # (resynchronisation des devis brouillon/envoyé).
    'produit_modifie': _e(
        "Une référence du catalogue change (désignation ou prix de vente) — "
        "les devis brouillon/envoyé qui la portent sont resynchronisés.",
        ['produit', 'company', 'user', 'champs']),
    # NTUX7 — alimente la corbeille transverse 30 jours (``apps.trash``) sans
    # qu'aucune app émettrice ne connaisse la corbeille.
    'record_soft_deleted': _e(
        "Un enregistrement métier est soft-supprimé (archivé/annulé) — "
        "alimente la corbeille transverse 30 jours.",
        ['instance', 'company', 'user', 'type_libelle', 'libelle', 'donnees']),
    # ODY25 — émis par ``core.feature_flags`` aux DEUX seuls sites qui écrivent
    # un ``ModuleToggle`` (activer_module / desactiver_module), sur
    # FRANCHISSEMENT uniquement et une fois PAR module réellement basculé (donc
    # autant d'événements que de modules touchés par une cascade). Abonné :
    # ``core`` lui-même (journal de la boutique via le chatter ARC8).
    'module_toggled': _e(
        "Une application est installée ou désinstallée pour une société "
        "(bascule d'un core.ModuleToggle).",
        ['toggle', 'company', 'module', 'actif', 'user', 'raison']),
    # AOF13 — les DEUX seuls événements du domaine « appel d'offres »
    # (``apps.ao``). Émis EXCLUSIVEMENT par ``apps.ao.services.changer_statut_ao``
    # (jamais d'un modèle ni d'une vue), sur FRANCHISSEMENT de statut. Abonné
    # réel : ``crm`` (``apps/crm/receivers.py``), qui avance l'étape du lead
    # lié — d'où l'intérêt de les cataloguer : une intégration cliente branche
    # son propre suivi d'offres dessus sans importer ``apps.ao``.
    'ao_depose': _e(
        "Un dossier d'appel d'offres est DÉPOSÉ (transition "
        "« prêt à déposer » → « déposé ») : l'offre est remise.",
        ['appel_offre', 'company', 'user', 'ancien_statut']),
    'ao_gagne': _e(
        "Un appel d'offres est ATTRIBUÉ (transition « déposé » → « gagné ») "
        "à l'ouverture des plis.",
        ['appel_offre', 'company', 'user', 'ancien_statut']),
    # NTCRM22 — émis par ``apps/crm/receivers.py`` à l'acceptation d'un devis
    # lié à un ``DealEnregistre`` APPROUVE. ``crm`` n'écrit jamais en compta :
    # l'événement est le seul canal pour qu'un module compta/paie matérialise
    # la commission (facture fournisseur, note de frais).
    'deal_commission_due': _e(
        "La commission d'un deal d'apporteur devient due (devis lié accepté).",
        ['company', 'deal_id', 'apporteur_id', 'montant']),
    # NTCRM27 — émis par ``apps/crm/services.detecter_signal_interet_salle_vente``
    # (≥3 consultations de la salle de vente en 48 h, lead en QUOTE_SENT).
    # Purement informationnel : JAMAIS un changement de stage automatique.
    'salle_vente_signal_interet': _e(
        "Une salle de vente est consultée de façon répétée (signal d'intérêt "
        "fort sur un lead en devis envoyé).",
        ['lead', 'salle', 'company']),
    # NTMKT34 — émis par
    # ``apps/marketing/services.recalculer_scores_maturite_inactivite`` quand
    # le recalcul quotidien (pénalité d'inactivité 30j) change effectivement
    # le score de maturité NTMKT18 d'un lead.
    'lead_maturite_changee': _e(
        'Le score de maturité marketing (NTMKT18) d\'un lead change lors du '
        'recalcul quotidien (pénalité d\'inactivité 30j, NTMKT34).',
        ['lead_id', 'company', 'ancienne_valeur', 'nouvelle_valeur']),
    # NTLOG44 (volet douane) — émis par
    # ``apps.douane.services.cloturer_dossier_export`` à la clôture d'un
    # DossierExport. Volet transport (ordre_transport_livre/
    # litige_transport_ouvert) hors périmètre de cette entrée.
    'dossier_export_cloture': _e(
        "Un dossier d'export douane (DossierExport) est clôturé.",
        ['dossier', 'company', 'user', 'ancien_statut']),
    # NTSCM39 — émis par ``apps.scm.services.
    # detecter_ruptures_imminentes_et_notifier`` (tâche beat NTSCM35).
    'scm_rupture_imminente_detectee': _e(
        'Un produit passe en rupture de stock imminente (tableau de bord '
        'réappro NTSCM7).',
        ['company', 'produit_id', 'produit_nom', 'rupture_date', 'quantite_suggeree']),
    # NTSCM39 — émis par ``apps.scm.services.avancer_statut_cycle`` à la
    # clôture d'un cycle S&OP.
    'scm_cycle_sop_cloture': _e(
        'Un cycle de planification S&OP (CyclePlanificationSOP) est clôturé.',
        ['cycle', 'user']),
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

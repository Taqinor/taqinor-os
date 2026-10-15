"""QJ6 + Lead → Client resolution.

QJ6 — recompute_lead_score(lead) persiste le score calculé sur le lead pour
permettre un tri pagination-safe (?ordering=-score). Appelé dans perform_create
et perform_update du LeadViewSet.

Lead → Client resolution (approach approved by the founder, 2026-06-12).

A quote always carries a Client; when it starts from a Lead the client is
resolved automatically, without ever creating duplicates:

  1. the lead is already linked to a client  → reuse that client;
  2. the lead has an email matching an existing client of the SAME company
     (case-insensitive)                      → link and reuse that client;
  3. otherwise                               → create a client from the lead's
     contact details and link it.

The resolved link is persisted on the lead, so every later quote from the
same lead reuses the same client. Everything stays tenant-scoped.
"""
import logging

from .leads_socle import (  # façade
    _company_fallback_managers,
    lead_notification_recipients,
    motif_refus_valide,
    user_and_superior_recipients,
    visite_point_eau_requise,
    visite_pro_avant_devis,
)

from .leads_doublons import (  # façade
    find_duplicates_by_contact,
    is_strong_identity_match,
    normalize_email,
    normalize_phone,
)

from .leads_consentement import enregistrer_consentements_intake_web  # façade

from .visites_rdv import public_booking_url, send_due_appointment_reminders  # façade

from .visites_retour_lead import journaliser_visite  # façade

from .cadence_messages import (  # façade
    _corps_pour_segment,
    _omettre_phrases_incompletes,
    message_pour_etape,
)

from .fiche_funnel import (  # façade
    _rang_funnel,
    ajuster_score_lead,
    appliquer_stage_lead,
    assigner_lead_a,
    avancer_stage_lead_vers,
    creer_relance_lead,
    poser_tag_lead,
    retirer_tag_lead,
)

from .cadence_plan import (  # façade
    _garde_cadence_contact,
    calculer_echeances_cadence,
    demarrer_cadence_contact,
    devis_envoyes_pour_relance,
)

from .clients_identite import (  # façade
    clients_par_ids,
    completer_client_depuis_acceptation,
    ecrire_identite_client,
    merge_clients,
    resolve_client_for_lead,
)

from .leads_score import maybe_assign_mql, recompute_lead_score  # façade

from .leads_notifications import notify_devis_opened, notify_new_lead  # façade

from .cadence_signaux import (  # façade
    CALLBACK_REQUESTED_MARKER,
    SIGNAL_PROPOSITION_ROUVERTE,
    noter_version_remplacee_ouverte,
    notifier_signal_lecture,
    notify_client_contact_request,
    notify_lead_callback_requested,
    poser_touche_signal_du_lead_id,
)

from .devis_chatter import (  # façade
    noter_devis_corrige,
    noter_devis_envoye,
    noter_devis_ouvert,
    noter_devis_reouvert,
)

from .clients_pilotage import (  # façade
    ajouter_specialite_partenaire,
    handle_parrainage_signup,
    poser_compteur_deploiements,
    soumettre_lead_partenaire,
)

from .fiche_ecritures import (  # façade
    CHAMP_AUTO_CADENCE,
    CHAMP_AUTO_INCHANGE,
    CHAMP_AUTO_INVALIDE,
    appliquer_champ_automatique,
    noter_touche_marketing,
)

from .fiche_archivage import delete_leads_for_company  # façade

from .leads_meta import (  # façade
    _apply_meta_form_extras,
    _meta_type_installation,
    _parse_meta_form_extras,
    backfill_meta_lead_attribution,
    create_lead_from_meta_lead_ads,
    create_minimal_lead_from_ctwa,
    fetch_meta_lead_node,
    import_external_notes_for_contact,
)

from .leads_intake import (  # façade
    create_draft_lead_from_ocr,
    create_lead_depuis_ticket,
    create_lead_from_evenement_marketing,
    finaliser_lead_importe,
    find_lead_by_email,
    find_lead_by_phone,
    reactivate_lead_on_new_touch,
    resolve_or_create_lead_from_whatsapp,
)

from .leads_attribution import default_responsable_for  # façade

from .fiche_api_publique import (  # façade
    PUBLIC_LEAD_WRITABLE_FIELDS,
    ajouter_note_lead,
    ajouter_note_lead_si_nouvelle,
    create_activity_from_public_api,
    create_lead_from_public_api,
    update_lead_from_public_api,
)

from .receivers_cadence import poser_tache_avenant  # façade

# T-TRACE — le traçage des visiteurs externes vit dans son propre module
# (``apps/crm/visites.py``) pour ne pas gonfler ce fichier déjà très long,
# mais il est RÉEXPORTÉ ici : `services` reste la porte d'entrée unique des
# écritures CRM (les accroches n'importent jamais `visites` directement).
from .visites import (  # réexport public délibéré
    COOKIE_APPAREIL,
    COOKIE_EQUIPE,
    alerter_appareil_partage,
    appareil_de_requete,
    appareils_equipe_ids,
    avec_direction,
    detecter_concurrent,
    domaine_cookies_equipe,
    enregistrer_appareil_equipe,
    enregistrer_visite_externe,
    est_appareil_equipe,
    historique_appareil,
    ip_de_requete,
    rattacher_visites_au_lead,
    requete_marquee_equipe,
    resume_historique_fr,
    tracer_et_correler,
    user_agent_de_requete,
    utilisateurs_direction,
)

# Noms ré-exportés volontairement (façade) : pas la surface complète du module.
__all__ = [
    'CALLBACK_REQUESTED_MARKER', 'CHAMP_AUTO_CADENCE', 'CHAMP_AUTO_INCHANGE', 'CHAMP_AUTO_INVALIDE',
    'COOKIE_APPAREIL', 'COOKIE_EQUIPE', 'PUBLIC_LEAD_WRITABLE_FIELDS',
    'SIGNAL_PROPOSITION_ROUVERTE', '_apply_meta_form_extras', '_company_fallback_managers',
    '_corps_pour_segment', '_garde_cadence_contact', '_meta_type_installation',
    '_omettre_phrases_incompletes', '_parse_meta_form_extras', '_rang_funnel', 'ajouter_note_lead',
    'ajouter_note_lead_si_nouvelle', 'ajouter_specialite_partenaire', 'ajuster_score_lead',
    'alerter_appareil_partage', 'appareil_de_requete', 'appareils_equipe_ids',
    'appliquer_champ_automatique', 'appliquer_stage_lead', 'assigner_lead_a',
    'avancer_stage_lead_vers', 'avec_direction', 'backfill_meta_lead_attribution',
    'calculer_echeances_cadence', 'clients_par_ids', 'completer_client_depuis_acceptation',
    'create_activity_from_public_api', 'create_draft_lead_from_ocr', 'create_lead_depuis_ticket',
    'create_lead_from_evenement_marketing', 'create_lead_from_meta_lead_ads',
    'create_lead_from_public_api', 'create_minimal_lead_from_ctwa', 'creer_relance_lead',
    'default_responsable_for', 'delete_leads_for_company', 'demarrer_cadence_contact',
    'detecter_concurrent', 'devis_envoyes_pour_relance', 'domaine_cookies_equipe',
    'ecrire_identite_client', 'enregistrer_appareil_equipe', 'enregistrer_consentements_intake_web',
    'enregistrer_visite_externe', 'est_appareil_equipe', 'fetch_meta_lead_node',
    'finaliser_lead_importe', 'find_duplicates_by_contact', 'find_lead_by_email',
    'find_lead_by_phone', 'handle_parrainage_signup', 'historique_appareil',
    'import_external_notes_for_contact', 'ip_de_requete', 'is_strong_identity_match',
    'journaliser_visite', 'lead_notification_recipients', 'maybe_assign_mql', 'merge_clients',
    'message_pour_etape', 'motif_refus_valide', 'normalize_email', 'normalize_phone',
    'noter_devis_corrige', 'noter_devis_envoye', 'noter_devis_ouvert', 'noter_devis_reouvert',
    'noter_touche_marketing', 'noter_version_remplacee_ouverte', 'notifier_signal_lecture',
    'notify_client_contact_request', 'notify_devis_opened', 'notify_lead_callback_requested',
    'notify_new_lead', 'poser_compteur_deploiements', 'poser_tache_avenant', 'poser_tag_lead',
    'poser_touche_signal_du_lead_id', 'public_booking_url', 'rattacher_visites_au_lead',
    'reactivate_lead_on_new_touch', 'recompute_lead_score', 'requete_marquee_equipe',
    'resolve_client_for_lead', 'resolve_or_create_lead_from_whatsapp', 'resume_historique_fr',
    'retirer_tag_lead', 'send_due_appointment_reminders', 'soumettre_lead_partenaire',
    'tracer_et_correler', 'update_lead_from_public_api', 'user_agent_de_requete',
    'user_and_superior_recipients', 'utilisateurs_direction', 'visite_point_eau_requise',
    'visite_pro_avant_devis',
]

logger = logging.getLogger(__name__)

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

from .leads_socle import (  # noqa: F401 — façade
    _company_fallback_managers,
    lead_notification_recipients,
    motif_refus_valide,
    user_and_superior_recipients,
    visite_point_eau_requise,
    visite_pro_avant_devis,
)

from .leads_doublons import (  # noqa: F401 — façade
    find_duplicates_by_contact,
    is_strong_identity_match,
    normalize_email,
    normalize_phone,
)

from .leads_consentement import enregistrer_consentements_intake_web  # noqa: F401 — façade

from .visites_rdv import public_booking_url, send_due_appointment_reminders  # noqa: F401 — façade

from .visites_retour_lead import journaliser_visite  # noqa: F401 — façade

from .cadence_messages import (  # noqa: F401 — façade
    _corps_pour_segment,
    _omettre_phrases_incompletes,
    message_pour_etape,
)

from .fiche_funnel import (  # noqa: F401 — façade
    _rang_funnel,
    ajuster_score_lead,
    appliquer_stage_lead,
    assigner_lead_a,
    avancer_stage_lead_vers,
    creer_relance_lead,
    poser_tag_lead,
    retirer_tag_lead,
)

from .cadence_plan import (  # noqa: F401 — façade
    _garde_cadence_contact,
    calculer_echeances_cadence,
    demarrer_cadence_contact,
    devis_envoyes_pour_relance,
)

from .clients_identite import (  # noqa: F401 — façade
    clients_par_ids,
    completer_client_depuis_acceptation,
    ecrire_identite_client,
    merge_clients,
    resolve_client_for_lead,
)

from .leads_score import maybe_assign_mql, recompute_lead_score  # noqa: F401 — façade

from .leads_notifications import notify_devis_opened, notify_new_lead  # noqa: F401 — façade

from .cadence_signaux import (  # noqa: F401 — façade
    CALLBACK_REQUESTED_MARKER,
    SIGNAL_PROPOSITION_ROUVERTE,
    noter_version_remplacee_ouverte,
    notifier_signal_lecture,
    notify_client_contact_request,
    notify_lead_callback_requested,
    poser_touche_signal_du_lead_id,
)

from .devis_chatter import (  # noqa: F401 — façade
    noter_devis_corrige,
    noter_devis_envoye,
    noter_devis_ouvert,
    noter_devis_reouvert,
)

from .clients_pilotage import (  # noqa: F401 — façade
    ajouter_specialite_partenaire,
    approuver_deal,
    rejeter_deal,
    handle_parrainage_signup,
    poser_compteur_deploiements,
    soumettre_lead_partenaire,
)

from .fiche_ecritures import (  # noqa: F401 — façade
    CHAMP_AUTO_CADENCE,
    CHAMP_AUTO_INCHANGE,
    CHAMP_AUTO_INVALIDE,
    appliquer_champ_automatique,
    noter_touche_marketing,
)

from .fiche_archivage import delete_leads_for_company  # noqa: F401 — façade

from .leads_meta import (  # noqa: F401 — façade
    _apply_meta_form_extras,
    _meta_type_installation,
    _parse_meta_form_extras,
    backfill_meta_lead_attribution,
    create_lead_from_meta_lead_ads,
    create_minimal_lead_from_ctwa,
    fetch_meta_lead_node,
    import_external_notes_for_contact,
)

from .leads_intake import (  # noqa: F401 — façade
    create_draft_lead_from_ocr,
    create_lead_depuis_ticket,
    create_lead_from_evenement_marketing,
    finaliser_lead_importe,
    find_lead_by_email,
    find_lead_by_phone,
    reactivate_lead_on_new_touch,
    resolve_or_create_lead_from_whatsapp,
)

from .leads_attribution import default_responsable_for  # noqa: F401 — façade

from .fiche_api_publique import (  # noqa: F401 — façade
    PUBLIC_LEAD_WRITABLE_FIELDS,
    ajouter_note_lead,
    ajouter_note_lead_si_nouvelle,
    create_activity_from_public_api,
    create_lead_from_public_api,
    update_lead_from_public_api,
)

# T-TRACE — le traçage des visiteurs externes vit dans son propre module
# (``apps/crm/visites.py``) pour ne pas gonfler ce fichier déjà très long,
# mais il est RÉEXPORTÉ ici : `services` reste la porte d'entrée unique des
# écritures CRM (les accroches n'importent jamais `visites` directement).
from .visites import (  # noqa: F401 — réexport public délibéré
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

logger = logging.getLogger(__name__)

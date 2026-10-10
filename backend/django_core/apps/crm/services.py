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
import datetime
import logging
import re as _re

from django.apps import apps as django_apps
from django.utils import timezone
from rest_framework.exceptions import ValidationError as DRFValidationError

# CRX26 — LA date MÉTIER (Africa/Casablanca), lue EXPLICITEMENT : elle ne dépend
# d'aucun réglage global. Avant AUD836, ``settings.TIME_ZONE`` valait ``'UTC'``
# et ``timezone.localdate()`` était en retard d'un jour entier une heure par
# nuit ; le réglage dit désormais la même chose, ce helper reste la garantie.
from core.dates import aujourd_hui_local


from . import activity, stages
from .models import Lead, LeadActivity, PointContact, RelanceEtape

from .leads_socle import MOTIF_BULK_CADENCE_ACTIVE, leads_avec_cadence_active
from .leads_socle import (  # noqa: F401 — façade
    _company_fallback_managers,
    lead_notification_recipients,
    motif_refus_valide,
    user_and_superior_recipients,
    visite_point_eau_requise,
    visite_pro_avant_devis,
)

from .leads_doublons import (
    _MERGE_FILL_FIELDS,
    _est_vide,
    find_duplicates_by_contact,
    normalize_phone,
)
from .leads_doublons import is_strong_identity_match, normalize_email  # noqa: F401 — façade

from .leads_attribution import default_responsable_for

from .leads_premier_contact import maybe_set_first_contacted_at

from .leads_consentement import (
    BASE_LEGALE_NON_COLLECTEE,
    BASE_LEGALE_SOLLICITATION,
    CONSENT_SOURCE_DOCUMENT,
    CONSENT_SOURCE_META_LEAD_ADS,
    CONSENT_SOURCE_WHATSAPP_ENTRANT,
    enregistrer_base_legale_lead,
)
from .leads_consentement import enregistrer_consentements_intake_web  # noqa: F401 — façade

from .visites_rdv import public_booking_url, send_due_appointment_reminders  # noqa: F401 — façade

from .visites_retour_lead import journaliser_visite  # noqa: F401 — façade

from .cadence_reperes import _CLOTURE_TAGS

from .cadence_messages import (  # noqa: F401 — façade
    _corps_pour_segment,
    _omettre_phrases_incompletes,
    message_pour_etape,
)

from .fiche_funnel import (
    _STAGE_CONTACTED,
    _bulk_stage_allowed,
    _emit_stage_changed,
    _rang_funnel,
    appliquer_stage_lead,
    avancer_stage_lead_vers,
    poser_tag_lead,
)
from .fiche_funnel import (  # noqa: F401 — façade
    ajuster_score_lead,
    assigner_lead_a,
    creer_relance_lead,
    retirer_tag_lead,
)

from .cadence_plan import (
    CadenceActiveConflit,
    _q_plan_ouvert,
    _recaler_file,
    calculer_echeances_cadence,
    demarrer_cadence_contact,
    initialiser_plan_relance,
    sync_relance_activity,
)
from .cadence_plan import (  # noqa: F401 — façade
    _garde_cadence_contact,
    arreter_cadence,
    devis_envoyes_pour_relance,
)

from .cadence_filet import assurer_prochaine_etape_apres_succes

from .cadence_touche import reprendre_cadence_apres_reouverture

from .clients_identite import _email_identite
from .clients_identite import (  # noqa: F401 — façade
    clients_par_ids,
    completer_client_depuis_acceptation,
    ecrire_identite_client,
    merge_clients,
    resolve_client_for_lead,
)

from .leads_score import recompute_lead_score
from .leads_score import maybe_assign_mql  # noqa: F401 — façade

from .leads_notifications import notify_new_lead
from .leads_notifications import notify_devis_opened  # noqa: F401 — façade

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
    handle_parrainage_signup,
    poser_compteur_deploiements,
    soumettre_lead_partenaire,
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


# ── YLEAD11 — Réactivation d'un lead perdu/COLD sur nouvelle touche entrante ──

def reactivate_lead_on_new_touch(lead, *, source='site web') -> bool:
    """YLEAD11 — Réactive ``lead`` s'il est actuellement PERDU ou COLD.

    Une nouvelle touche entrante (re-POST site web, nouveau message WhatsApp)
    sur un lead perdu/froid rouvre le cycle d'achat : lève ``perdu``,
    repositionne le funnel (AVANCE-SEULEMENT, jamais en arrière — donc un
    lead déjà ≥ CONTACTED et non perdu ne bouge pas) vers CONTACTED s'il
    avait déjà été contacté (``first_contacted_at`` posé), sinon NEW, et
    journalise une activité de réactivation. N'écrase JAMAIS l'attribution
    first-touch d'origine (ce service ne touche à aucun champ UTM/fbclid).
    Idempotent : un lead ni perdu ni COLD → no-op (False). Company-scopée par
    construction (opère sur l'instance ``lead`` déjà résolue dans SA société).
    """
    if lead is None:
        return False
    etait_perdu = bool(lead.perdu)
    etait_cold = lead.stage == stages.COLD
    if not etait_perdu and not etait_cold:
        return False

    if etait_perdu:
        lead.perdu = False
        lead.save(update_fields=['perdu'])

    cible = _STAGE_CONTACTED if lead.first_contacted_at else stages.NEW
    ancien_stage = None  # étape déjà ≥ cible — pas de changement d'étape.
    if _rang_funnel(lead.stage) < _rang_funnel(cible):
        etape_avant = lead.stage
        # ALEA2 — sortie du Froid/Perdu par le point de passage CANONIQUE
        # (CRX20) : écrit l'étape et émet `lead_stage_changed`.
        if appliquer_stage_lead(lead, cible):
            ancien_stage = etape_avant

    # ALEA2 — libellé lisible au chatter : « Nouvelle demande reçue (site
    # web) » / « (WhatsApp) ».
    body = f'auto — réactivation : Nouvelle demande reçue ({source})'
    LeadActivity.objects.create(
        company=lead.company, lead=lead, user=None,
        kind=LeadActivity.Kind.NOTE, body=body)
    if ancien_stage is not None:
        LeadActivity.objects.create(
            company=lead.company, lead=lead, user=None,
            kind=LeadActivity.Kind.MODIFICATION,
            field='stage', field_label='Étape',
            old_value=stages.STAGE_LABELS[ancien_stage],
            new_value=stages.STAGE_LABELS[cible],
            body=f'auto — réactivation ({source})',
        )
    # CAD107 — une réouverture pose une CADENCE DE REPRISE, quel que soit le
    # chemin. Best-effort : une nouvelle touche entrante ne doit jamais
    # échouer sur une cadence.
    try:
        reprendre_cadence_apres_reouverture(lead, None, origine=source)
    except Exception:  # noqa: BLE001
        logger.warning(
            'CAD107: reprise non posée après réactivation (lead #%s)',
            getattr(lead, 'pk', '?'), exc_info=True)
    return True


# ── ACRM35 — un geste de cadence à la fois par lead ─────────────────────────


# FG28 — SLA première prise de contact ────────────────────────────────────────


# ── CAD-B ── CAD106 ─────────────────────────────────────────────────────────

#: Le motif porté par une touche que la FUSION retire du plan. Statut
#: ANNULEE (CKP1 : annulation MOTEUR, jamais un saut humain) — sans quoi la
#: fusion compterait autant de manquements d'adhérence que de touches.
FUSION_TOUCHE_NOTE = 'annulée — fusion de fiches'


def relances_ouvertes_de(lead):
    """Les touches encore À FAIRE d'un lead (l'aperçu et la fusion comptent
    la même chose — jamais deux définitions)."""
    return lead.relance_etapes.filter(statut=RelanceEtape.Statut.A_FAIRE)


def reprendre_relances_apres_fusion(absorbed, survivor, user):
    """CAD106 — les relances SUIVENT le dossier quand deux fiches fusionnent.

    `merge_leads` déplaçait devis, chantiers, activités, pièces jointes et
    historique — et pas une seule relance. Les touches ouvertes restaient
    accrochées à une fiche ARCHIVÉE, donc invisibles dans la file (qui exclut
    les archivés), jamais passées en « annulée », et rien ne reposait de
    prochaine étape sur la survivante. Le cas est garanti d'arriver : le
    nouveau lead venait justement d'être privé de cadence par la garde
    « doublon ».

    Ce qu'on fait, et POURQUOI pas un simple déplacement : la survivante a
    souvent DÉJÀ une cadence active, et CADX interdit deux cadences en
    parallèle sur un lead. Les touches ouvertes de l'absorbée sont donc
    CLOSES en ANNULÉE avec le motif « fusion » — elles ne comptent alors
    comme un manquement nulle part (CKP1) — puis le FILET garantit à la
    survivante une prochaine étape, exactement comme à la reprise d'un lead
    dé-perdu (`unset_perdu`).

    Rend le nombre de touches retirées du plan de l'absorbée.
    """
    from django.utils import timezone

    ouvertes = list(relances_ouvertes_de(absorbed))
    if ouvertes:
        RelanceEtape.objects.filter(
            pk__in=[e.pk for e in ouvertes],
        ).update(statut=RelanceEtape.Statut.ANNULEE,
                 note=FUSION_TOUCHE_NOTE, traite_par=None,
                 traite_le=timezone.now())
        absorbed.relance_date = None
        absorbed.save(update_fields=['relance_date'])
    # QJ-INVARIANT — la survivante ne reste jamais sans prochaine étape.
    # Best-effort : une fusion n'échoue pas sur un filet.
    try:
        assurer_prochaine_etape_apres_succes(survivor, user)
    except Exception:  # noqa: BLE001
        logger.warning(
            'CAD106: filet non posé après fusion (lead #%s)',
            getattr(survivor, 'pk', '?'), exc_info=True)
    return len(ouvertes)


def _transferer_calepinages_apres_fusion(absorbed, survivor, user):
    """ACAL177 — fait suivre les calepinages de l'absorbé au survivant.

    Appel DIRECT du service ``apps.calepinage.services.liens.transferer_lead``
    (même patron que ``update_installation_lead`` : transactionnel, pas
    d'événement), import FONCTION-LOCAL (frontière inter-apps : jamais un
    modèle de calepinage). Sous-bloc ``atomic`` (savepoint) : un échec annule
    le seul transfert, la fusion continue, et le chatter du survivant le dit.
    """
    from django.db import transaction

    try:
        from apps.calepinage.services.liens import transferer_lead

        with transaction.atomic():
            transferer_lead(survivor.company, de_lead_id=absorbed.pk,
                            vers_lead_id=survivor.pk, user=user)
    except Exception:  # noqa: BLE001 — la fusion ne casse jamais ici
        logger.exception(
            'ACAL177 : calepinages du lead #%s non transférés vers #%s',
            absorbed.pk, survivor.pk)
        LeadActivity.objects.create(
            company=survivor.company, lead=survivor, user=user,
            kind=LeadActivity.Kind.NOTE,
            body=(f'Fusion : les calepinages du lead #{absorbed.pk} n\'ont '
                  'pas pu être rattachés à cette fiche — rattachez-les depuis '
                  'le module Calepinage.'))


def raison_refus_suppression(lead):
    """ACAL177 — LA garde de corbeille d'un lead, écrite UNE fois.

    Sert les DEUX chemins de suppression (``LeadViewSet.destroy`` et
    l'opération en masse ``delete``). Rend ``None`` si le lead peut partir en
    corbeille, sinon un dict ``{detail, [calepinages]}`` (corps du 409) :

    * des devis liés : on n'orpheline jamais de pièces financières ;
    * un calepinage OUVERT (non archivé) : refus qui le NOMME. Un calepinage
      archivé ne bloque pas.
    """
    if lead.devis.exists():
        return {'detail': "Ce lead a des devis liés. Supprimer le lead "
                          "détacherait ces pièces — archivez-le plutôt."}
    from apps.calepinage.selectors import calepinages_ouverts_du_lead

    ouverts = calepinages_ouverts_du_lead(lead.company, lead.pk)
    if ouverts:
        premier = ouverts[0]
        titre = (getattr(premier, 'titre', '') or '').strip() or 'sans titre'
        return {
            'detail': (f'Ce lead porte le calepinage « {titre} » '
                       f'(#{premier.pk}) : archivez-le d\'abord ou ouvrez-le '
                       'depuis le module Calepinage'),
            'calepinages': [c.pk for c in ouverts],
        }
    return None


def _nom_fiche_client(client):
    """ACRM40 — « Nom Prénom (#id) » d'une fiche client, pour la note."""
    nom = f"{client.nom or ''} {client.prenom or ''}".strip() or 'Client'
    return f'{nom} (#{client.pk})'


def merge_leads(survivor, others, user):
    """Fusionne `others` dans `survivor` SANS perte de données. Déplace devis,
    activités, pièces jointes, historique et chantiers ; complète les champs
    vides du survivant ; archive les leads absorbés avec une note. Ne laisse
    JAMAIS un devis/chantier orphelin. Tout est transactionnel.
    """
    from django.contrib.contenttypes.models import ContentType
    from django.db import transaction
    from django.utils import timezone

    others = [o for o in others if o.pk != survivor.pk
              and o.company_id == survivor.company_id]
    if not others:
        return survivor

    ct = ContentType.objects.get_for_model(Lead)
    relances_reprises = 0
    # ACRM40 (C-ACRM-035) — les fiches client DISTINCTES rencontrées : le
    # survivant garde la sienne, les devis de l'autre restent sur l'autre.
    deux_clients = []
    with transaction.atomic():
        for absorbed in others:
            if (survivor.client_id and absorbed.client_id
                    and survivor.client_id != absorbed.client_id):
                deux_clients.append((
                    absorbed.client,
                    list(absorbed.devis.filter(client_id=absorbed.client_id)
                         .order_by('pk').values_list('reference', flat=True))))
            # 1) Devis → survivant (related_name='devis').
            absorbed.devis.update(lead=survivor)
            # 2) Chantiers liés au lead → survivant (FK SET_NULL, on réassigne).
            try:
                from apps.installations.selectors import (
                    update_installation_lead,
                )
                update_installation_lead(absorbed, survivor)
            except Exception:
                pass
            # 2 bis) ACAL177 — les CALEPINAGES suivent le dossier (D06-T04).
            # Savepoint : un transfert qui échoue ne casse jamais la fusion,
            # mais il est tracé (journal + note au chatter du survivant).
            _transferer_calepinages_apres_fusion(absorbed, survivor, user)
            # 3) Activités + pièces jointes génériques → survivant.
            try:
                from apps.records.models import Activity, Attachment
                Activity.objects.filter(
                    content_type=ct, object_id=absorbed.id).update(
                    object_id=survivor.id)
                Attachment.objects.filter(
                    content_type=ct, object_id=absorbed.id).update(
                    object_id=survivor.id)
            except Exception:
                pass
            # 4) Historique chatter → survivant.
            LeadActivity.objects.filter(lead=absorbed).update(lead=survivor)
            # 4 bis) CAD106 — les RELANCES suivent le dossier : les touches
            # ouvertes de l'absorbée sortent de son plan (annulées « fusion »,
            # donc jamais comptées comme des manquements) et le filet garantit
            # une prochaine étape à la survivante.
            relances_reprises += reprendre_relances_apres_fusion(
                absorbed, survivor, user)
            # 5) Client : adopter celui de l'absorbé si le survivant n'en a pas.
            if not survivor.client_id and absorbed.client_id:
                survivor.client = absorbed.client
            # 6) Compléter les champs VIDES du survivant — ACRM13 : vide au
            # sens de ``_est_vide`` (un 0 saisi du survivant SURVIT).
            for field in _MERGE_FILL_FIELDS:
                cur = getattr(survivor, field, None)
                if _est_vide(survivor, field, cur):
                    val = getattr(absorbed, field, None)
                    if not _est_vide(absorbed, field, val):
                        setattr(survivor, field, val)
            # 7) Fusionner les tags (union).
            tags = set()
            for src in (survivor, absorbed):
                for t in (src.tags or '').split(','):
                    t = t.strip()
                    if t:
                        tags.add(t)
            if tags:
                survivor.tags = ', '.join(sorted(tags))[:500]
            # 8) Archiver l'absorbé (jamais supprimé).
            absorbed.is_archived = True
            absorbed.archived_by = user
            absorbed.archived_at = timezone.now()
            absorbed.note = ((absorbed.note or '') +
                             f'\n[Fusionné dans le lead #{survivor.id} '
                             f'par {getattr(user, "username", "?")}]').strip()
            absorbed.save()
            LeadActivity.objects.create(
                company=survivor.company, lead=survivor, user=user,
                kind=LeadActivity.Kind.NOTE,
                body=(f"Fusion : lead « {absorbed.nom} {absorbed.prenom or ''} »"
                      f" (#{absorbed.id}) absorbé dans cette fiche."))
        # ACRM40 — DEUX fiches client pour une même personne : la fusion le
        # DIT (chatter du survivant + ``survivor._clients_distincts`` que la
        # vue rend) ; la fusion des clients reste un geste humain (outil de
        # fusion de clients, NTDATA18) — jamais automatique.
        survivor._clients_distincts = []
        if deux_clients:
            gardee = survivor.client
            survivor._clients_distincts = [gardee.pk] + [
                client.pk for client, _refs in deux_clients]
            for client, refs in deux_clients:
                devis_txt = (f"devis {', '.join(refs)} rattachés" if refs
                             else 'aucun devis rattaché')
                LeadActivity.objects.create(
                    company=survivor.company, lead=survivor, user=user,
                    kind=LeadActivity.Kind.NOTE,
                    body=(f'Deux fiches client pour ce lead : '
                          f'{_nom_fiche_client(gardee)} (gardée) et '
                          f'{_nom_fiche_client(client)} ({devis_txt}) — à '
                          'fusionner (outil de fusion des clients).'))
        survivor.save()
    if relances_reprises:
        # CAD106 — la fusion DIT ce qu'elle a fait des relances : sans cette
        # ligne, des touches disparaissaient du plan sans un mot.
        LeadActivity.objects.create(
            company=survivor.company, lead=survivor, user=user,
            kind=LeadActivity.Kind.NOTE,
            body=(f'Fusion : {relances_reprises} relance(s) reprise(s) — '
                  'les touches des fiches absorbées sont retirées de leur '
                  'plan et le suivi continue sur cette fiche.'))
    # CRX33 — l'étape 6 complète les champs VIDES du survivant depuis les
    # absorbés (téléphone, e-mail, ville, facture, orientation…) : autant de
    # composantes du score. Sans ce recalcul, le survivant gardait le score
    # d'AVANT la fusion — une fiche enrichie restait « froide », et le badge
    # comme le tri mentaient jusqu'à la prochaine édition manuelle.
    recompute_lead_score(survivor)
    return survivor


def appliquer_plan_activite(*, lead, plan, user):
    """ZSAL2 — applique un :class:`~apps.crm.models.PlanActivite` à un lead.

    Crée une ``records.Activity`` par étape du plan, échéance = aujourd'hui +
    ``etape.delai_jours``, assignée à ``etape.assigne_par_defaut`` si posé
    sinon au owner du lead sinon à l'acteur. IDEMPOTENT par (lead, plan) : les
    activités déjà créées par une précédente application de CE plan sur CE
    lead sont retrouvées via ``summary`` + une marque dédiée dans ``note``
    (``[plan:<id>:<etape_id>]``) — une seconde application ne duplique rien et
    renvoie la liste déjà existante. Un plan archivé (``actif=False``) n'est
    jamais applicable (ValueError, traduit en 400 par la vue).

    Retourne la liste des ``records.Activity`` (créées ou déjà existantes,
    dans l'ordre des étapes).
    """
    if not plan.actif:
        raise ValueError("Ce plan d'activité est archivé et n'est plus applicable.")
    if plan.company_id != lead.company_id:
        raise ValueError("Plan hors de votre société.")

    from django.contrib.contenttypes.models import ContentType
    from apps.records.models import Activity

    ct = ContentType.objects.get_for_model(Lead)
    today = aujourd_hui_local()
    resultats = []
    for etape in plan.etapes.select_related(
            'activity_type', 'assigne_par_defaut').order_by('ordre', 'delai_jours'):
        marque = f'[plan:{plan.id}:{etape.id}]'
        existante = Activity.objects.filter(
            company=lead.company, content_type=ct, object_id=lead.id,
            note__contains=marque,
        ).first()
        if existante is not None:
            resultats.append(existante)
            continue
        assigne = etape.assigne_par_defaut or lead.owner or user
        from datetime import timedelta
        due = today + timedelta(days=etape.delai_jours)
        act = Activity.objects.create(
            company=lead.company, content_type=ct, object_id=lead.id,
            activity_type=etape.activity_type,
            summary=(etape.resume_defaut or etape.activity_type.nom)[:255],
            due_date=due,
            assigned_to=assigne,
            note=marque,
            created_by=user,
        )
        resultats.append(act)

    LeadActivity.objects.create(
        company=lead.company, lead=lead, user=user,
        kind=LeadActivity.Kind.NOTE,
        body=f"Plan d'activité « {plan.nom} » appliqué "
             f"({len(plan.etapes.all())} étape(s)).")
    return resultats


def create_draft_lead_from_ocr(*, company, user, fields) -> Lead:
    """FG106 — crée un LEAD brouillon à partir de champs extraits par l'OCR.

    Point d'entrée cross-app sanctionné (services.py) pour la passerelle
    OCR → CRM (apps.publicapi). La société vient TOUJOURS du serveur (jamais du
    corps), l'attribution du propriétaire suit la même règle que la création
    normale d'un lead, et la création est tracée dans le chatter. ``fields`` est
    le dict de données structurées OCR ; seuls des champs sûrs y sont lus —
    aucune confiance n'est accordée à des clés inattendues.

    Le lead reste à l'étape par défaut (NEW) : ce service CRÉE, il ne fait pas
    avancer le funnel.
    """
    fields = fields or {}
    nom = (fields.get('fournisseur') or fields.get('client') or '').strip()
    if not nom:
        raise ValueError("Aucun nom de fournisseur/client exploitable dans le document.")

    extra = {}
    # Même règle d'attribution que LeadViewSet.perform_create : un compte à
    # portée restreinte garde la propriété de ce qu'il crée.
    if user is not None and getattr(user, 'record_scope', None) and \
            user.record_scope() != 'all':
        extra['owner'] = user
    else:
        default = default_responsable_for(company)
        if default is not None:
            extra['owner'] = default

    lead = Lead.objects.create(
        company=company,
        nom=nom[:255],
        source=Lead.Source.OS_NATIVE,
        canal=Lead.Canal.AUTRE,
        **extra,
    )
    activity.log_creation(lead, user)
    # Note SYSTÈME (user=None) : annotation automatique, pas un contact manuel —
    # sinon le récepteur QJ7 ferait avancer le lead NEW → CONTACTED alors que ce
    # service CRÉE seulement et laisse le funnel à l'étape par défaut (NEW).
    activity.log_note(
        lead, None,
        "Lead créé depuis un document OCR (brouillon à compléter).")
    # CAD90 — données lues sur un document, jamais collectées auprès de la
    # personne par nous : c'est l'art. 5 §3 qui s'applique, et le registre
    # doit le dire au lieu de rester muet.
    enregistrer_base_legale_lead(
        lead, source=CONSENT_SOURCE_DOCUMENT,
        base_legale=BASE_LEGALE_NON_COLLECTEE)
    recompute_lead_score(lead)
    return lead


# ── XSAL8 — Scan de carte de visite (salon/chantier) → pré-remplissage ──────
#
# NE crée JAMAIS de lead : lit une photo, l'envoie à l'OCR EXISTANT
# (``core.ai.services.extract_document``, gabarit ``carte_visite`` — la même
# capacité que FG355/XRH23, key-gated ZHIPU_API_KEY, NO-OP-safe), et renvoie
# les champs reconnus pour PRÉ-REMPLIR le modal « Lead express » — la création
# reste TOUJOURS un geste explicite de l'utilisateur (bouton « Créer »).

# Mêmes octets magiques que ``apps.records.storage`` (jamais de nouvelle
# dépendance) : la carte de visite est une simple PHOTO (JPEG/PNG/WebP),
# jamais un PDF.
_CARTE_VISITE_MAX_BYTES = 8 * 1024 * 1024  # 8 Mo (photo mobile courante)
_CARTE_VISITE_MAGIC = {
    'image/png': lambda h: h[:8] == b'\x89PNG\r\n\x1a\n',
    'image/jpeg': lambda h: h[:3] == b'\xff\xd8\xff',
    'image/webp': lambda h: h[:4] == b'RIFF' and h[8:12] == b'WEBP',
}


class CarteVisiteScanUnavailable(Exception):
    """XSAL8 — levée quand l'OCR n'est pas configuré (503 douce côté vue) ou
    quand le fichier fourni n'est pas une image reconnue (400 côté vue)."""


def scan_carte_visite(*, company, file_bytes, mime_hint='', queryset=None):
    """XSAL8 — Extrait nom/société/téléphone/email d'une photo de carte de
    visite, PRÉ-VÉRIFIE les doublons, et renvoie un dict prêt à pré-remplir le
    modal « Lead express » — NE CRÉE JAMAIS de lead (l'utilisateur valide).

    Lève :class:`CarteVisiteScanUnavailable` si le fichier n'est pas une image
    reconnue (magic bytes) OU trop volumineux OU si aucun fournisseur OCR
    n'est configuré (``ZHIPU_API_KEY`` absent — dégradation propre, jamais
    d'appel réseau). Ne persiste JAMAIS l'image reçue au-delà du traitement en
    mémoire (aucun stockage MinIO — contrairement aux autres flux OCR qui
    rattachent le fichier en pièce jointe).

    ACRM7 (jumeau) — ``queryset`` borne la pré-vérification des doublons aux
    leads de la PORTÉE de l'appelant (``None`` = toute la société)."""
    if not file_bytes:
        raise CarteVisiteScanUnavailable('Aucune image fournie.')
    if len(file_bytes) > _CARTE_VISITE_MAX_BYTES:
        raise CarteVisiteScanUnavailable('Image trop volumineuse (max 8 Mo).')

    header = file_bytes[:12]
    mime = None
    for candidate_mime, test in _CARTE_VISITE_MAGIC.items():
        if test(header):
            mime = candidate_mime
            break
    if mime is None:
        raise CarteVisiteScanUnavailable(
            'Format non reconnu (JPEG, PNG ou WebP uniquement).')

    from core.ai.services import extract_document
    result = extract_document(
        content=file_bytes, mime_type=mime, schema='carte_visite')
    if not result.configured:
        raise CarteVisiteScanUnavailable(
            "Aucun fournisseur OCR n'est configuré (clé absente) — "
            'saisie manuelle requise.')

    data = result.data or {}
    nom = str(data.get('nom') or '').strip()[:255]
    prenom = str(data.get('prenom') or '').strip()[:255]
    societe = str(data.get('societe') or '').strip()[:255]
    telephone = str(data.get('telephone') or '').strip()[:50]
    email = str(data.get('email') or '').strip()[:254]

    doublons = []
    if telephone or email:
        dupes = find_duplicates_by_contact(
            company, phone=telephone or None, email=email or None,
            queryset=queryset)
        doublons = [
            {'id': d.id, 'nom': d.nom, 'prenom': d.prenom,
             'telephone': d.telephone, 'email': d.email}
            for d in dupes
        ]

    return {
        'nom': nom, 'prenom': prenom, 'societe': societe,
        'telephone': telephone, 'email': email,
        'doublons': doublons,
    }


# ── YLEAD8 — Rattacher l'inbound WhatsApp à un lead OUVERT existant ──────────

def resolve_or_create_lead_from_whatsapp(company, telephone, nom='',
                                         user=None) -> Lead:
    """YLEAD8 — Réutilise un lead OUVERT existant (même téléphone) au lieu de
    toujours créer un doublon sur un message WhatsApp entrant.

    « Ouvert » = non perdu (``Lead.perdu`` False) et non archivé
    (``archived_at`` NULL). Parmi les leads ouverts partageant ce téléphone,
    prend le plus récent ; journalise le message inbound dans SON chatter.

    YLEAD11 — si aucun lead OUVERT n'existe mais qu'un lead PERDU/COLD (non
    archivé) partage ce téléphone, il est RÉACTIVÉ (même règle que le
    webhook site : lève ``perdu``, repositionne NEW/CONTACTED avance-seul)
    plutôt que de créer un doublon — une nouvelle touche WhatsApp rouvre
    aussi le cycle d'achat.

    N'appelle ``create_draft_lead_from_ocr`` qu'en DERNIER RECOURS (aucun
    lead — ouvert ou réactivable — trouvé pour ce numéro) — c'est ce service
    qui doit être appelé par ``compta.services.capturer_message_whatsapp``,
    jamais l'inverse. Company-scopé ; gated en amont par l'appelant (NO-OP si
    WhatsApp OFF).
    """
    candidates = find_duplicates_by_contact(company, phone=telephone)
    non_archives = [c for c in candidates if c.archived_at is None]
    # ALEA2 — un lead au Froid (non perdu) n'est PAS « ouvert » : il est
    # réactivable, comme le perdu (alignement sur le webhook du site).
    ouverts = [lead_ for lead_ in non_archives
               if not lead_.perdu and lead_.stage != stages.COLD]
    if ouverts:
        lead = sorted(ouverts, key=lambda d: d.date_creation, reverse=True)[0]
        body = 'Nouveau message WhatsApp reçu'
        if nom:
            body += f' de {nom}'
        LeadActivity.objects.create(
            company=lead.company, lead=lead, user=user,
            kind=LeadActivity.Kind.NOTE, body=body)
        return lead

    # YLEAD11 — aucun lead ouvert : un lead perdu/COLD non archivé est
    # réactivé plutôt que dupliqué.
    reactivables = [lead_ for lead_ in non_archives
                    if lead_.perdu or lead_.stage == stages.COLD]
    if reactivables:
        lead = sorted(
            reactivables, key=lambda d: d.date_creation, reverse=True)[0]
        reactivate_lead_on_new_touch(lead, source='WhatsApp')
        return lead

    lead = create_draft_lead_from_ocr(
        company=company, user=user,
        fields={'client': nom or telephone})
    # create_draft_lead_from_ocr ne lit que fournisseur/client (nom) — le
    # téléphone/whatsapp est posé ICI pour que le PROCHAIN message du même
    # numéro retrouve ce lead via find_duplicates_by_contact (sinon YLEAD8
    # créerait un doublon à chaque message, ce que ce service existe pour
    # éviter). BUG RÉEL corrigé ici : Lead.save() recalcule
    # phone_normalise/email_normalise EN MÉMOIRE à chaque save() (avant
    # super().save()), mais save(update_fields=[...]) ne PERSISTE que les
    # colonnes listées — sans 'phone_normalise' ici, la colonne restait ''
    # en base malgré le téléphone posé, et find_duplicates_by_contact (qui
    # filtre sur phone_normalise) ne retrouvait jamais ce lead au message
    # suivant : chaque nouveau message du même numéro créait un DOUBLON.
    if telephone:
        lead.telephone = telephone
        lead.whatsapp = telephone
        lead.save(update_fields=['telephone', 'whatsapp', 'phone_normalise',
                                 'whatsapp_normalise'])
    return lead


# ── XMKT32 — Sync Meta Lead Ads → leads CRM (gated) ───────────────────────────

_META_LEAD_ADS_SYSTEM = 'meta_lead_ads'

# Marqueur d'idempotence de la note « réponses du formulaire » (une seule note
# par lead, quel que soit le nombre de retries webhook / passes du pull).
_META_FORM_NOTE_MARKER = '[Formulaire Meta]'


def _norm_form_text(value):
    """Minuscule, sans accents, underscores → espaces — les clés/valeurs des
    Instant Forms Meta arrivent en snake_case accentué (ex.
    ``quelle_est_votre_facture_moyenne_d'électricité_par_mois_?`` /
    ``entre_1000_dh_à_2000_dh``) ; ce normalisateur rend le matching tolérant
    aux variantes de wording entre formulaires."""
    import unicodedata

    text = unicodedata.normalize('NFKD', str(value or ''))
    text = ''.join(c for c in text if not unicodedata.combining(c))
    return text.replace('_', ' ').lower().strip()


# ── CAD-K ── CAD134 — le délai déclaré côté Meta, dans le champ DÉJÀ scoré ──
#
# Mots-clés → ``Lead.ProjectTimeline``, sur du texte libre normalisé par
# ``_norm_form_text``. TOLÉRANT (les libellés varient d'un Instant Form à
# l'autre) et SANS invention : un libellé non reconnu ne pose RIEN — mieux
# vaut un champ vide qu'un délai deviné, qui vaudrait des points au score.
# L'ORDRE compte : « le plus tôt possible » gagne avant « 3 mois ».
_META_TIMELINE_MOTS = (
    (('plus tot possible', 'ce mois', 'immediat', 'des que possible',
      'urgent'), Lead.ProjectTimeline.IMMEDIAT),
    (('renseigne', 'plus tard', 'pas presse', 'aucune idee', 'compare'),
     Lead.ProjectTimeline.PLUS_TARD),
    (('3 mois', 'trois mois'), Lead.ProjectTimeline.MOINS_3_MOIS),
    (('6 mois', 'six mois'), Lead.ProjectTimeline.MOINS_6_MOIS),
)


def _meta_project_timeline(valeur_normalisee):
    """CAD134 — le délai déclaré côté Meta en clé ``ProjectTimeline``, ou ''.

    ``valeur_normalisee`` est déjà passée par ``_norm_form_text``. Renvoie
    une chaîne VIDE quand rien n'est reconnu : on ne devine pas un délai."""
    texte = str(valeur_normalisee or '')
    for mots, cle in _META_TIMELINE_MOTS:
        if any(mot in texte for mot in mots):
            return cle
    return ''


# ── CIQ407 — formulaire Meta « pour mon entreprise » (D-CIQ-19) ─────────────
#
# Mots ENTIERS sur du texte normalisé (``_norm_form_text``). L'ORDRE compte :
# un mot d'industrie l'emporte sur « entreprise »/« société » (« Entreprise
# industrielle » est une usine) ; un cas qui touche deux segments que rien
# ne départage ne pose AUCUN type (il reste dans la note).
_META_MOTS_RESIDENTIEL = (r'villa', r'maison', r'appartement', r'domicile',
                          r'residen\w*')
_META_MOTS_INDUSTRIEL = (r'usine', r'industri\w*', r'atelier', r'hangar')
_META_MOTS_AGRICOLE = (r'ferme', r'agricole', r'pompage', r'puits')
#: Activité → ``Lead.categorie_commerciale`` (liste fermée du contrat CIQ1).
_META_CATEGORIES = (
    ((r'hotel', r'riad'), 'hotel'),
    ((r'restaurant', r'cafe', r'snack'), 'restaurant'),
    ((r'entrepot frigorifique', r'chambre froide', r'froid'), 'froid'),
    ((r'supermarche', r'magasin', r'commerce', r'boutique'), 'commerce'),
    ((r'bureau', r'bureaux'), 'bureau'),
    ((r'clinique', r'cabinet', r'sante', r'centre medical'), 'sante'),
    ((r'ecole', r'creche', r'lycee'), 'ecole'),
    ((r'hammam', r'spa', r'gym', r'salle de sport'), 'hammam'),
    ((r'boulangerie', r'patisserie'), 'boulangerie'),
)
_META_MOTS_COMMERCIAL = (r'entreprise', r'societe', r'local')
_META_MOTS_TRANCHE_OUVERTE = ('plus de', 'au dela', 'superieur', '>',
                              'more than', 'over')
#: TQ-F6 (10/2026) — « moins de X » : le plancher d'une facture est 0, la
#: réponse vaut donc la tranche FERMÉE 0–X (même convention de milieu que les
#: autres tranches fermées) — jamais X comme montant.
_META_MOTS_TRANCHE_OUVERTE_BASSE = ('moins de', 'inferieur', '<',
                                    'less than', 'under')


def _meta_mot_entier(texte, motifs):
    return any(_re.search(rf'\b{motif}\b', texte) for motif in motifs)


def _meta_categorie(valeur_normalisee):
    """CIQ407 — la catégorie commerciale d'une réponse, ou '' (mots entiers ;
    la première catégorie de la table qui répond gagne)."""
    for motifs, cle in _META_CATEGORIES:
        if _meta_mot_entier(valeur_normalisee, motifs):
            return cle
    return ''


def _meta_type_installation(valeur_normalisee):
    """CIQ407 — le segment d'une réponse « où installer », ou ''.

    Industrie AVANT entreprise/société ; « local » en mot entier seulement ;
    une activité commerciale reconnue (clinique, école…) vaut commercial. Un
    cas ambigu (résidentiel ou agricole ET autre chose) ne pose rien."""
    v = valeur_normalisee
    residentiel = _meta_mot_entier(v, _META_MOTS_RESIDENTIEL)
    industriel = _meta_mot_entier(v, _META_MOTS_INDUSTRIEL)
    agricole = _meta_mot_entier(v, _META_MOTS_AGRICOLE)
    commercial = (_meta_mot_entier(v, _META_MOTS_COMMERCIAL)
                  or bool(_meta_categorie(v)))
    pro = industriel or commercial
    if sum((residentiel, agricole, pro)) != 1:
        return ''
    if residentiel:
        return Lead.TypeInstallation.RESIDENTIEL
    if agricole:
        return Lead.TypeInstallation.AGRICOLE
    if industriel:
        return Lead.TypeInstallation.INDUSTRIEL
    return Lead.TypeInstallation.COMMERCIAL


def _meta_tranche_facture(valeur_normalisee, libelle):
    """CIQ407 (D-CIQ-19) — ``(montant, tranche)`` d'une réponse de facture.

    Tranche FERMÉE (deux nombres) : montant = milieu (inchangé) + tranche
    {min, max}. Tranche OUVERTE (« plus de X ») : AUCUN montant, tranche
    {X, None}. Nombre unique sans « plus de » : un montant, pas de tranche."""
    texte = _re.sub(r'(?<=\d)[\s.](?=\d{3}\b)', '', valeur_normalisee)
    nums = [int(n) for n in _re.findall(r'\d{3,6}', texte)]
    if len(nums) >= 2:
        bas, haut = sorted(nums[:2])
        return (bas + haut) // 2, {'min_mad': bas, 'max_mad': haut,
                                   'libelle': libelle, 'source': 'meta'}
    if nums:
        if any(mot in texte for mot in _META_MOTS_TRANCHE_OUVERTE):
            return None, {'min_mad': nums[0], 'max_mad': None,
                          'libelle': libelle, 'source': 'meta'}
        if any(mot in texte for mot in _META_MOTS_TRANCHE_OUVERTE_BASSE):
            return nums[0] // 2, {'min_mad': 0, 'max_mad': nums[0],
                                  'libelle': libelle, 'source': 'meta'}
        return nums[0], None
    return None, None


def _parse_meta_form_extras(field_data):
    """Réponses NON-contact du formulaire Meta → champs CRM structurés.

    Renvoie un dict : ``qa`` (paires question/réponse verbatim, pour la note
    chatter — rien n'est perdu), et selon les questions reconnues :
    ``facture_estimee`` (MAD/mois — milieu de tranche, ou borne pour une
    tranche ouverte « plus de X »), ``facture_declaree`` (réponse verbatim),
    ``type_installation`` (choix canonique du modèle), ``priorite`` (dérivée
    du délai déclaré : « le plus tôt possible » → haute, « je me renseigne » →
    basse, sinon normale)."""
    contact_keys = {'full_name', 'nom', 'name', 'first_name', 'email',
                    'phone_number', 'telephone', 'city', 'ville'}
    extras = {'qa': []}
    for entry in (field_data or []):
        raw_name = str(entry.get('name', '')).strip()
        if raw_name.lower() in contact_keys:
            continue
        values = entry.get('values') or []
        raw_value = str((values[0] if values else '') or '')
        if not raw_value:
            continue
        extras['qa'].append((raw_name, raw_value))
        # CIQ407 — raison sociale et fonction : champs Meta standard,
        # recopiés en remplissage seulement (et cités dans la note).
        if raw_name.lower() == 'company_name':
            extras['societe'] = raw_value.strip()[:255]
            continue
        if raw_name.lower() == 'job_title':
            extras['fonction_contact'] = raw_value.strip()[:120]
            continue
        q = _norm_form_text(raw_name)
        v = _norm_form_text(raw_value)
        if 'facture' in q:
            # CIQ407 (D-CIQ-19) — une tranche OUVERTE (« plus de 4000 dh »)
            # n'est JAMAIS un montant : elle va dans la tranche déclarée,
            # la facture reste vide.
            montant, tranche = _meta_tranche_facture(
                v, raw_value.replace('_', ' '))
            if montant is not None:
                extras['facture_estimee'] = montant
            if tranche is not None:
                extras['facture_tranche'] = tranche
            extras['facture_declaree'] = raw_value
        elif 'quand' in q or 'commencer' in q or 'delai' in q:
            if 'plus tot possible' in v or 'ce mois' in v or 'immediat' in v:
                extras['priorite'] = Lead.Priorite.HAUTE
            elif 'renseigne' in v or 'compare' in v:
                extras['priorite'] = Lead.Priorite.BASSE
            else:
                extras['priorite'] = Lead.Priorite.NORMALE
            # CAD134 (audit L3 du 21/09/2026) — LA MÊME PHRASE VAUT LE MÊME
            # SCORE DES DEUX CÔTÉS. Depuis le site, « je veux démarrer
            # immédiatement » devenait `project_timeline='immediat'` et valait
            # +8 au score ; depuis Meta, « le plus tôt possible » ne devenait
            # qu'une `priorite=haute` — absente de `compute_score`, donc ZÉRO
            # point, aucune remontée dans la file, aucun changement d'heure ni
            # de canal. Le webhook Meta écrit donc AUSSI `project_timeline`,
            # qui est déjà scoré ; la priorité reste le drapeau MANUEL du
            # commercial.
            #
            # Conversion TOLÉRANTE (ce sont des mots-clés sur du texte libre,
            # de qualité inégale) et TRACÉE : le libellé BRUT part dans
            # `extras['qa']`, que la note de formulaire recopie telle quelle —
            # un humain peut donc toujours relire ce que le client a coché.
            # Un délai non reconnu ne pose RIEN plutôt qu'une valeur inventée.
            extras['delai_declare'] = raw_value
            delai = _meta_project_timeline(v)
            if delai:
                extras['project_timeline'] = delai
        elif 'install' in q or 'logement' in q or 'type de bien' in q:
            # CIQ407 — industrie AVANT entreprise/société, mots entiers ; un
            # cas ambigu ne pose aucun type (il reste dans la note).
            segment = _meta_type_installation(v)
            if segment:
                extras['type_installation'] = segment
            categorie = _meta_categorie(v)
            if categorie and segment == Lead.TypeInstallation.COMMERCIAL:
                extras['categorie_commerciale'] = categorie
        elif 'contact' in q and ('prefer' in q or 'joindre' in q
                                 or 'comment' in q):
            # TQ-F6 (10/2026) — « Comment préférez-vous être contacté ? » →
            # la préférence EXPLICITE du lead (QW3), remplissage seulement.
            if 'whatsapp' in v:
                extras['contact_preference'] = (
                    Lead.ContactPreference.WHATSAPP_ONLY)
            elif 'appel' in v or 'telephone' in v or 'phone' in v:
                extras['contact_preference'] = Lead.ContactPreference.PHONE_OK
        elif _meta_mot_entier(v, (r'proprietaire', r'locataire')):
            # TQ-F6 — « Vous êtes : propriétaire / locataire » → ownership
            # (champ site CAD150, éditable avec provenance).
            extras['ownership'] = (
                Lead.Ownership.PROPRIETAIRE if 'proprietaire' in v
                else Lead.Ownership.LOCATAIRE)
        elif 'activite' in q or 'secteur' in q or 'etablissement' in q:
            # CIQ407 — question d'activité du formulaire modifié par Reda.
            categorie = _meta_categorie(v)
            if categorie:
                extras['categorie_commerciale'] = categorie
        else:
            # AGR410 — FORM-AGRI-1 : questions de pompage reconnues par
            # mots-clés (``_meta_reponse_agricole``).
            _meta_reponse_agricole(q, v, extras)
    # AGR410 — une question AGRICOLE pose le type agricole, seulement si le
    # formulaire n'a pas dit autre chose (et ``_apply_meta_form_extras`` ne
    # l'écrit que sur un type VIDE).
    if extras.pop('_agricole', False):
        extras.setdefault('type_installation',
                          Lead.TypeInstallation.AGRICOLE)
    return extras


# ── AGR410 — Formulaire Meta agricole (FORM-AGRI-1) ─────────────────────────
#
# Mots-clés sur du texte NORMALISÉ (``_norm_form_text``). Une TRANCHE ne
# devient JAMAIS un nombre (pas de milieu de tranche) : seule une réponse à
# nombre UNIQUE, sans « plus/moins/entre », remplit une colonne ; sinon la
# réponse reste dans la note, mot pour mot. Rien n'est jamais écrasé
# (``_apply_meta_form_extras``). Aucune création de campagne ici (règle #3).
_META_SOURCE_EAU_MOTS = (
    (('forage',), 'forage'),
    (('puits',), 'puits'),
    (('bassin',), 'bassin'),
    (('riviere', 'oued'), 'riviere'),
)
_META_ENERGIE_POMPE_MOTS = (
    (('pas de pompe', 'aucune', 'pas encore'), 'aucune'),
    # « gazoil » AVANT « gaz » : l'ordre de la table compte.
    (('gasoil', 'diesel', 'gazoil'), 'diesel'),
    (('butane', 'gaz'), 'butane'),
    (('electri', 'reseau', 'onee'), 'electrique'),
)
_META_MOTS_TRANCHE = ('plus', 'moins', 'entre', '>', '<', 'jusqu')


def _meta_nombre_unique(valeur_normalisee):
    """Le nombre d'une réponse à nombre UNIQUE, ou None (tranche / texte)."""
    from decimal import Decimal, InvalidOperation

    texte = str(valeur_normalisee or '')
    if any(mot in texte for mot in _META_MOTS_TRANCHE):
        return None
    nombres = _re.findall(r'\d+(?:[.,]\d+)?', texte.replace(' ', ''))
    if len(nombres) != 1:
        return None
    try:
        return Decimal(nombres[0].replace(',', '.'))
    except InvalidOperation:
        return None


def _meta_mot_cle(valeur_normalisee, table):
    for mots, cle in table:
        if any(mot in valeur_normalisee for mot in mots):
            return cle
    return ''


def _meta_reponse_agricole(q, v, extras):
    """AGR410 — une question de pompage du formulaire Meta → ``extras``.

    ``q``/``v`` déjà normalisés. Pose ``extras['_agricole']`` dès qu'une
    question agricole est reconnue, même si sa réponse ne remplit rien."""
    from decimal import Decimal

    if (('eau' in q and ('source' in q or 'vient' in q or 'provient' in q))
            or 'puits' in q or 'forage' in q):
        extras['_agricole'] = True
        source = _meta_mot_cle(v, _META_SOURCE_EAU_MOTS)
        if source:
            extras['source_eau'] = source
    elif 'pompe' in q and any(k in q for k in (
            'energie', 'fonctionne', 'marche', 'alimente', 'alimentation')):
        extras['_agricole'] = True
        energie = _meta_mot_cle(v, _META_ENERGIE_POMPE_MOTS)
        if energie:
            extras['pompe_alim_actuelle'] = energie
    elif 'hectare' in q or ('surface' in q and (
            'irrig' in q or 'cultiv' in q or 'terrain' in q
            or 'exploitation' in q)):
        extras['_agricole'] = True
        surface = _meta_nombre_unique(v)
        if surface is not None and surface < Decimal('10000000'):
            extras['surface_irriguee_ha'] = surface
    elif ('depense' in q or 'depensez' in q) and any(k in q for k in (
            'carburant', 'gasoil', 'butane', 'gaz', 'pompe', 'diesel')):
        extras['_agricole'] = True
        depense = _meta_nombre_unique(v)
        if depense is not None and depense < Decimal('100000000'):
            extras['depense_carburant_mad_mois'] = depense


def _apply_meta_form_extras(lead, extras):
    """Pose les champs structurés du formulaire SANS jamais écraser une valeur
    déjà présente (une saisie humaine gagne toujours sur l'auto-remplissage).
    ``priorite`` : posée seulement en « upgrade » (NORMALE par défaut → HAUTE
    déclarée) — jamais de downgrade automatique. Renvoie la liste des champs
    modifiés (vide si rien à faire)."""
    from decimal import Decimal

    changed = []
    # AGR410 — le type d'abord : sur un lead AGRICOLE, la tranche de facture
    # ne remplit PAS facture_hiver (elle gonflerait son score) — elle reste
    # dans la note seulement.
    if extras.get('type_installation') and not lead.type_installation:
        lead.type_installation = extras['type_installation']
        changed.append('type_installation')
    if (extras.get('facture_estimee') is not None and lead.facture_hiver is None
            and lead.type_installation != Lead.TypeInstallation.AGRICOLE):
        lead.facture_hiver = Decimal(int(extras['facture_estimee']))
        changed.append('facture_hiver')
    # CIQ407 (D-CIQ-19) — la tranche déclarée : toujours pour une tranche
    # OUVERTE (jamais un montant), en plus du milieu pour un PRO.
    tranche = extras.get('facture_tranche')
    if (tranche and lead.facture_tranche_declaree is None
            and lead.type_installation != Lead.TypeInstallation.AGRICOLE
            and (tranche['max_mad'] is None or lead.type_installation in (
                Lead.TypeInstallation.COMMERCIAL,
                Lead.TypeInstallation.INDUSTRIEL))):
        lead.facture_tranche_declaree = dict(tranche)
        changed.append('facture_tranche_declaree')
    # CIQ407 — activité, raison sociale, fonction : remplissage seulement.
    for champ in ('categorie_commerciale', 'societe', 'fonction_contact'):
        if extras.get(champ) and not getattr(lead, champ, None):
            setattr(lead, champ, extras[champ])
            changed.append(champ)
    # AGR410 — réponses de pompage : remplissage seulement, jamais
    # d'écrasement.
    for champ in ('source_eau', 'pompe_alim_actuelle', 'surface_irriguee_ha',
                  'depense_carburant_mad_mois'):
        if extras.get(champ) is not None and getattr(lead, champ) in (
                None, ''):
            setattr(lead, champ, extras[champ])
            changed.append(champ)
    if (extras.get('priorite') == Lead.Priorite.HAUTE
            and lead.priorite == Lead.Priorite.NORMALE):
        lead.priorite = Lead.Priorite.HAUTE
        changed.append('priorite')
    # CAD134 — le délai déclaré remplit le champ DÉJÀ scoré, et seulement
    # s'il est vide : un délai saisi à la main par la commerciale (ou venu du
    # site) n'est JAMAIS écrasé par un mot-clé lu sur du texte libre.
    if extras.get('project_timeline') and not getattr(
            lead, 'project_timeline', None):
        lead.project_timeline = extras['project_timeline']
        changed.append('project_timeline')
    # TQ-F6 (10/2026) — statut d'occupation et préférence de contact lus sur
    # le formulaire : remplissage seulement, jamais d'écrasement ; la
    # préférence est horodatée (QX15 : le SLA rappel court depuis sa pose).
    if extras.get('ownership') and not getattr(lead, 'ownership', None):
        lead.ownership = extras['ownership']
        changed.append('ownership')
    if (extras.get('contact_preference')
            and not getattr(lead, 'contact_preference', None)):
        lead.contact_preference = extras['contact_preference']
        lead.contact_preference_set_at = timezone.now()
        changed.extend(['contact_preference', 'contact_preference_set_at'])
    if lead.telephone and not lead.whatsapp:
        # Un lead Meta arrive par mobile : le même numéro sert de lien wa.me
        # pour la première prise de contact de Meryem.
        lead.whatsapp = lead.telephone
        changed.append('whatsapp')
    return changed


def _enrichir_meta_trace(lead, extras):
    """ACRM14 (C-ACRM-009) — applique ``_apply_meta_form_extras`` et
    JOURNALISE chaque champ écrit (une ligne MODIFICATION par champ :
    champ, ancienne → nouvelle valeur, acteur système) : un enrichissement
    automatique est visible au chatter comme toute autre écriture. Enregistre
    les champs modifiés et les rend."""
    from . import activity as _activity

    avant = {}
    for champ in ('type_installation', 'facture_hiver',
                  'facture_tranche_declaree', 'categorie_commerciale',
                  'societe', 'fonction_contact', 'source_eau',
                  'pompe_alim_actuelle', 'surface_irriguee_ha',
                  'depense_carburant_mad_mois', 'priorite', 'project_timeline',
                  'whatsapp', 'ownership', 'contact_preference'):
        avant[champ] = getattr(lead, champ, None)
    changed = _apply_meta_form_extras(lead, extras)
    if changed:
        lead.save(update_fields=changed)
        for champ in changed:
            if champ == 'contact_preference_set_at':
                continue   # horodatage technique, pas une donnée du client
            LeadActivity.objects.create(
                company=lead.company, lead=lead, user=None,
                kind=LeadActivity.Kind.MODIFICATION, field=champ,
                field_label=_activity.TRACKED_FIELDS.get(champ, champ),
                old_value=_activity._display(lead, champ, avant.get(champ)),
                new_value=_activity._display(
                    lead, champ, getattr(lead, champ, None)))
    return changed


def _meta_deja_enrichi(lead):
    """ACRM14 — la note « [Formulaire Meta] » (marqueur EXISTANT de
    ``_ensure_meta_form_note``) dit qu'une première passe a déjà enrichi ce
    lead : une passe suivante (rejeu webhook, pull) ne réécrit plus rien —
    une correction humaine faite entre-temps SURVIT."""
    return LeadActivity.objects.filter(
        lead=lead, body__startswith=_META_FORM_NOTE_MARKER).exists()


def _ensure_meta_form_note(lead, extras, form_id=''):
    """Une note chatter avec TOUTES les réponses verbatim du formulaire —
    rien n'est perdu, même les questions non reconnues. Idempotente par
    marqueur (retries webhook / re-passes du pull ne dupliquent jamais)."""
    if not extras.get('qa'):
        return
    if LeadActivity.objects.filter(
            lead=lead, body__startswith=_META_FORM_NOTE_MARKER).exists():
        return
    suffix = f' (formulaire {form_id})' if form_id else ''
    lines = [f'{_META_FORM_NOTE_MARKER} Réponses du prospect{suffix} :']
    for question, answer in extras['qa']:
        lines.append('• %s → %s' % (question.replace('_', ' '),
                                    answer.replace('_', ' ')))
    # AGR410 — sur un lead agricole, la facture n'est PAS pré-remplie : la
    # note ne le prétend pas (la réponse reste citée mot pour mot plus haut).
    if (extras.get('facture_estimee') is not None
            and lead.type_installation != Lead.TypeInstallation.AGRICOLE):
        lines.append(
            '(facture hiver pré-remplie à %s MAD depuis la tranche déclarée '
            '« %s » — à préciser au premier appel)'
            % (int(extras['facture_estimee']),
               extras.get('facture_declaree', '').replace('_', ' ')))
    elif (extras.get('facture_tranche') or {}).get('max_mad', 0) is None:
        # CIQ407 (D-CIQ-19) — tranche ouverte : AUCUN montant pré-rempli.
        lines.append(
            '(tranche ouverte « %s » : aucune facture pré-remplie — le '
            'montant réel est à demander au premier appel)'
            % extras.get('facture_declaree', '').replace('_', ' '))
    LeadActivity.objects.create(
        company=lead.company, lead=lead, user=None,
        kind=LeadActivity.Kind.NOTE, body='\n'.join(lines))


#: MRY0 (lot B) — bornes d'acceptation d'une ``created_time`` Meta : on ne
#: repose JAMAIS une date de création hors de cette fenêtre (une valeur
#: aberrante fausserait SLA et KPI aussi sûrement que l'heure du pull).
_META_CREATED_TIME_MAX_ANCIENNETE_JOURS = 90
_META_CREATED_TIME_MARGE_FUTUR_MINUTES = 5


def _parse_meta_created_time(brut):
    """``created_time`` Meta → datetime aware, ou ``None``.

    Deux formes réelles : ISO ``2026-09-03T11:04:04+0000`` (pull) et epoch
    secondes (webhook). Hors de la fenêtre ``[now - 90 j, now + 5 min]`` →
    ``None`` (refusée, jamais posée)."""
    import datetime as _dt

    from django.utils.dateparse import parse_datetime as _parse_dt

    if brut in (None, ''):
        return None
    moment = None
    if isinstance(brut, bool):
        return None
    if isinstance(brut, _dt.datetime):
        moment = brut
    elif isinstance(brut, (int, float)):
        try:
            moment = _dt.datetime.fromtimestamp(
                int(brut), tz=_dt.timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    else:
        texte = str(brut).strip()
        if texte.isdigit():
            try:
                moment = _dt.datetime.fromtimestamp(
                    int(texte), tz=_dt.timezone.utc)
            except (OverflowError, OSError, ValueError):
                return None
        else:
            try:
                moment = _parse_dt(texte)
            except ValueError:
                return None
    if moment is None:
        return None
    if timezone.is_naive(moment):
        moment = timezone.make_aware(moment, _dt.timezone.utc)
    maintenant = timezone.now()
    if moment > maintenant + _dt.timedelta(
            minutes=_META_CREATED_TIME_MARGE_FUTUR_MINUTES):
        return None
    if moment < maintenant - _dt.timedelta(
            days=_META_CREATED_TIME_MAX_ANCIENNETE_JOURS):
        return None
    return moment


def create_lead_from_meta_lead_ads(
        *, company, leadgen_id, field_data,
        ad_id='', adgroup_id='', form_id='', access_token='',
        created_time=None, origine='') -> Lead:
    """XMKT32 — Crée (ou dédupe sur) un lead depuis un formulaire Meta Lead Ads.

    Point d'entrée cross-app sanctionné (services.py), appelé par
    ``webhooks.meta_lead_ads_webhook`` une fois le lead récupéré via l'API
    officielle (jamais de scraping). ``field_data`` est la liste
    ``[{'name': ..., 'values': [...]}, ...]`` renvoyée par le Graph API pour
    ce ``leadgen_id`` — seuls des champs connus (nom/email/téléphone/ville)
    sont lus.

    Dédup — D-CRX1 (décision fondateur du 02/09/2026) : UNE SEULE couche.
      1. même ``leadgen_id`` déjà traité (idempotence webhook — retries Meta)
         → renvoie le lead existant, enrichi (backfill) depuis le formulaire.

    L'ancienne « Couche 2 (QJ8) » — téléphone/e-mail connu dans la société ⇒
    ABSORPTION de la touche dans le lead existant — est SUPPRIMÉE. Chaque
    touche Meta est une nouvelle demande et crée un NOUVEAU lead, exactement
    comme une soumission du site (règle fondateur du 18/08/2026, étendue à Meta
    le 02/09/2026). Aucun lead existant n'est plus écrit par ce chemin : le
    rapprochement se fait EN VISIBILITÉ, avec les deux mêmes primitives que le
    webhook site (aucune seconde implémentation) —
      • ``webhooks._flag_possible_duplicates`` pose UNE note chatter de doublon
        sur le NOUVEAU lead (les archivés y sont mentionnés, cf. QW11) ;
      • ``webhooks._pick_owner_from_duplicates`` fait HÉRITER le commercial du
        doublon le plus pertinent (parité QW11), pour qu'un même client ne soit
        jamais rappelé par deux commerciaux différents.
    Conséquence VOULUE : un contact connu mais ARCHIVÉ donne lui aussi un
    NOUVEAU lead — il est signalé dans la note sans transmettre son owner
    (l'absorption, elle, ressuscitait silencieusement la fiche au rebut).
    L'attribution (canal/utm/meta_ids) et ``external_system``/``external_id``
    se posent donc TOUJOURS sur le lead nouvellement créé.

    Attribution (ADSENG1) : ``canal=META_ADS``, ``utm_source='facebook'``.
    Meta ne pousse JAMAIS campaign_name/adset_name dans le webhook leadgen ; il
    pousse ``ad_id``/``adgroup_id``/``form_id`` — capturés ici en clés de
    jointure stables (``meta_ad_id``/``meta_adset_id``/``meta_campaign_id``/
    ``meta_form_id``). Les NOMS lisibles sont résolus via les miroirs adsengine
    (``adsengine.selectors.resolve_meta_ad_names`` — jamais un import des modèles
    adsengine), avec repli paresseux via l'API si ``access_token`` est fourni.
    ``utm_campaign`` porte le nom de campagne résolu ; ``utm_content`` suit la
    convention ``ad-<ad_id>`` (formalisée en ADSENG23) — jamais l'adset_name,
    toujours vide en prod.

    Best-effort côté séquence de bienvenue : XMKT1 (moteur d'exécution des
    séquences) n'est pas encore construit — aucune inscription automatique
    tant qu'il n'existe pas ; ce service reste le point d'accroche futur.

    MRY0 (lot B) — ``created_time`` : l'heure Meta RÉELLE de la soumission.
    Appliquée UNIQUEMENT à la création (jamais sur un lead déjà capturé) et
    seulement si elle tombe dans ``[now - 90 j, now + 5 min]``. ``date_creation``
    étant ``auto_now_add``, elle n'est pas posable au ``create()`` : on la
    repose par un ``update()`` ciblé. Sans elle, un lead rattrapé par le pull
    portait l'heure du beat (07:25) et faussait SLA, KPI premier contact et
    notifications. ``origine`` (texte libre, ex. « Meta Lead Ads (webhook) »)
    nomme le chemin d'entrée dans la ligne « création » du chatter.
    """
    fields = {}
    for entry in (field_data or []):
        name = str(entry.get('name', '')).strip().lower()
        values = entry.get('values') or []
        value = (values[0] if values else '') or ''
        if name in ('full_name', 'nom', 'name'):
            fields['nom'] = str(value)[:255]
        elif name == 'first_name':
            fields.setdefault('nom', str(value)[:255])
        elif name in ('email',):
            fields['email'] = str(value)[:254]
        elif name in ('phone_number', 'telephone'):
            fields['telephone'] = str(value)[:20]
        elif name in ('city', 'ville'):
            fields['ville'] = str(value)[:120]
    # Réponses métier du formulaire (facture, type d'installation, délai…) —
    # structurées vers les VRAIS champs CRM, verbatim conservé en note.
    extras = _parse_meta_form_extras(field_data)

    # ── Couche 1 : idempotence sur le leadgen_id (retries webhook Meta) ──────
    # Un lead déjà capturé n'est PAS renvoyé tel quel : il est ENRICHI
    # (backfill) depuis les réponses du formulaire — champs vides uniquement,
    # jamais un écrasement de saisie humaine. C'est ce chemin qui remplit les
    # leads importés avant que le mapping complet n'existe.
    existing = Lead.objects.filter(
        company=company, external_system=_META_LEAD_ADS_SYSTEM,
        external_id=str(leadgen_id)).first()
    if existing is not None:
        # ACRM14 — UNE seule passe d'enrichissement : déjà enrichi (note
        # « [Formulaire Meta] » présente) → aucune écriture, la saisie
        # humaine faite depuis la première passe gagne.
        if _meta_deja_enrichi(existing):
            return existing
        _enrichir_meta_trace(existing, extras)
        if fields.get('ville') and not existing.ville:
            existing.ville = fields['ville']
            existing.save(update_fields=['ville'])
        _ensure_meta_form_note(existing, extras, form_id=str(form_id or ''))
        return existing

    nom = (fields.get('nom') or '').strip() or 'Lead Meta Ads'
    telephone = fields.get('telephone') or ''
    # ACRM38 — l'e-mail du formulaire Meta est nettoyé et validé comme
    # celui du site (``_clean_email``) : un « ' ' » n'est jamais une identité.
    from .webhooks import _clean_email
    email = _clean_email(fields.get('email')) or ''

    # ── D-CRX1 : plus AUCUNE absorption ─────────────────────────────────────
    # Les doublons sont cherchés ICI, AVANT la création, pour DEUX usages
    # strictement en lecture : (a) l'héritage du commercial (QW11) qui doit
    # être décidé avant le round-robin, (b) la note de signalement posée après
    # la création. Aucun lead existant n'est modifié sur ce chemin. Une seule
    # requête, réutilisée par les deux (jamais deux fois la même).
    dupes = []
    if telephone or email:
        dupes = find_duplicates_by_contact(
            company, phone=telephone or None, email=email or None)

    # ADSENG1 — identifiants Meta natifs (clés de jointure stables) + noms
    # résolus via les miroirs adsengine (jamais un import des modèles adsengine).
    ad_id = str(ad_id or '')
    adgroup_id = str(adgroup_id or '')
    form_id = str(form_id or '')
    from apps.adsengine.selectors import resolve_meta_ad_names
    names = resolve_meta_ad_names(
        company, ad_id=ad_id, adgroup_id=adgroup_id, access_token=access_token)

    utm_source = 'facebook'
    utm_campaign = (names.get('campaign_name') or '')[:300] or None
    # Convention ADSENG23 : utm_content = ad-<ad_id> (jamais l'adset_name).
    utm_content = f'ad-{ad_id}'[:300] if ad_id else None
    meta_ad_id = ad_id[:64] or None
    meta_adset_id = adgroup_id[:64] or None
    meta_campaign_id = (names.get('campaign_id') or '')[:64] or None
    meta_form_id = form_id[:64] or None

    # QW11 (parité site) — l'héritage du commercial se décide AVANT le
    # round-robin : un lead qui EST un doublon n'entre pas dans l'attribution
    # normale, il revient au commercial qui suit déjà ce contact. Les deux
    # filtres d'éligibilité (doublon non archivé, owner actif+habilité) sont
    # DANS ``_pick_owner_from_duplicates`` — jamais redécidés ici.
    from .webhooks import _flag_possible_duplicates, _pick_owner_from_duplicates

    extra = {}
    inherited_owner, inherited_from = _pick_owner_from_duplicates(
        dupes, telephone=telephone, email=email, company=company)
    if inherited_owner is not None:
        extra['owner'] = inherited_owner
    else:
        # CIQ416 — le type lu sur le formulaire route un lead pro vers son
        # responsable désigné (sinon : comportement inchangé).
        default = default_responsable_for(
            company,
            lead_attrs={'type_installation': extras.get('type_installation')})
        if default is not None:
            extra['owner'] = default
    # À la CRÉATION, le délai déclaré pose la priorité pleinement (haute,
    # normale ou basse) ; en enrichissement (leads existants), seule la
    # montée NORMALE→HAUTE est automatique (_apply_meta_form_extras).
    if extras.get('priorite'):
        extra['priorite'] = extras['priorite']
    # CAD134 — et le MÊME délai déclaré pose `project_timeline`, le champ que
    # `compute_score` lit déjà : depuis Meta la phrase « le plus tôt possible »
    # valait zéro point, contre +8 pour la même phrase venue du site.
    if extras.get('project_timeline'):
        extra['project_timeline'] = extras['project_timeline']
    lead = Lead.objects.create(
        company=company,
        nom=nom,
        email=email or None,
        telephone=telephone or None,
        ville=fields.get('ville') or None,
        source=Lead.Source.META_LEAD_ADS,
        canal=Lead.Canal.META_ADS,
        utm_source=utm_source,
        utm_campaign=utm_campaign,
        utm_content=utm_content,
        meta_ad_id=meta_ad_id,
        meta_adset_id=meta_adset_id,
        meta_campaign_id=meta_campaign_id,
        meta_form_id=meta_form_id,
        external_system=_META_LEAD_ADS_SYSTEM,
        external_id=str(leadgen_id),
        **extra,
    )
    # Réponses métier du formulaire → champs structurés (facture hiver,
    # type d'installation, priorité selon le délai déclaré, wa.me).
    # ACRM14 — chaque champ écrit est journalisé (ancien → nouveau).
    _enrichir_meta_trace(lead, extras)
    # MRY0 (lot B) — vraie date d'arrivée : ``date_creation`` est
    # ``auto_now_add`` (models.py), donc jamais posable au ``create()``.
    moment_meta = _parse_meta_created_time(created_time)
    if moment_meta is not None:
        Lead.objects.filter(pk=lead.pk).update(date_creation=moment_meta)
        lead.refresh_from_db(fields=['date_creation'])
    activity.log_creation(lead, None, origine=origine)
    LeadActivity.objects.create(
        company=lead.company, lead=lead, user=None,
        kind=LeadActivity.Kind.NOTE,
        body='Lead créé depuis Meta Lead Ads (formulaire Facebook/Instagram).')
    _ensure_meta_form_note(lead, extras, form_id=str(form_id or ''))
    # CAD90 — la cohorte Meta n'avait aucune entrée au registre : ses données
    # ne sont pas collectées auprès de la personne par nous (art. 5 §3), et
    # l'horodatage tracé est celui de l'arrivée RÉELLE, jamais celui du beat.
    enregistrer_base_legale_lead(
        lead, source=CONSENT_SOURCE_META_LEAD_ADS,
        base_legale=BASE_LEGALE_NON_COLLECTEE,
        occurred_at=moment_meta or lead.date_creation)
    # D-CRX1 — signalement du doublon EN VISIBILITÉ (jamais une fusion), avec
    # la mention de l'héritage quand il a eu lieu. Réutilise ``dupes`` déjà
    # calculés (jamais une 2e requête). Best-effort, comme côté site : un
    # rapprochement en échec ne remet jamais la capture du lead en cause.
    try:
        _flag_possible_duplicates(
            lead, telephone=telephone, email=email, dupes=dupes,
            inherited_owner=inherited_owner, inherited_from=inherited_from)
    except Exception as _exc:  # noqa: BLE001 — best-effort
        logger.warning(
            'create_lead_from_meta_lead_ads: note de doublon échouée '
            '(lead #%s) : %s', lead.pk, _exc)
    try:
        notify_new_lead(lead)
    except Exception:  # noqa: BLE001 — best-effort
        pass

    # MRY6 — démarrage EXPLICITE de la cadence de contact. Best-effort :
    # une cadence en échec ne fait JAMAIS échouer la création du lead.
    demarrer_cadence_contact(lead, origine='meta_lead_ads')
    recompute_lead_score(lead)
    return lead


def import_external_notes_for_contact(company, *, phone=None, email=None,
                                      notes):
    """Importe des notes EXTERNES (ex. chatter Odoo) dans le chatter du lead
    correspondant — point d'entrée cross-app sanctionné (services.py), appelé
    par la commande ``adsengine.odoo_import_notes``.

    ``notes`` : liste de paires ``(marker, body)`` — ``marker`` est le préfixe
    d'idempotence du corps (ex. ``[Odoo note 123]``) : une note déjà importée
    (même marqueur sur ce lead) n'est JAMAIS dupliquée, la commande est
    re-exécutable à volonté.

    Matching : téléphone puis email, via les mêmes colonnes normalisées que le
    reste du CRM (``find_duplicates_by_contact``) ; prend le lead le plus
    récent. Renvoie ``(matched: bool, created: int)`` — aucun lead n'est créé
    ici (les leads sans correspondance attendent la migration complète)."""
    dupes = find_duplicates_by_contact(
        company, phone=phone or None, email=email or None)
    if not dupes:
        return False, 0
    lead = sorted(dupes, key=lambda d: d.date_creation, reverse=True)[0]
    created = 0
    for marker, body in notes:
        if not (body or '').strip():
            continue
        if LeadActivity.objects.filter(
                lead=lead, body__startswith=marker).exists():
            continue
        LeadActivity.objects.create(
            company=lead.company, lead=lead, user=None,
            kind=LeadActivity.Kind.NOTE, body=body)
        created += 1
    return True, created


def create_minimal_lead_from_ctwa(*, company, phone, ad_id='') -> Lead:
    """PUB27 — Crée (ou dédupe sur) un Lead minimal pour une conversation
    WhatsApp/CTWA entrante SANS lead préalable.

    Point d'entrée cross-app WRITE sanctionné (services.py — jamais un import
    des modèles crm côté adsengine) : appelé par
    ``apps.adsengine.whatsapp_webhook`` quand ``_lead_id_for_phone`` ne trouve
    AUCUN lead pour le téléphone d'un message entrant portant un ``referral``
    CTWA (Click-to-WhatsApp) — jusqu'ici, ce cas laissait le ``CtwaReferral``
    orphelin (``crm_lead_id=None``) et l'attribution par ad était perdue.

    Dédupliqué par TÉLÉPHONE (``find_duplicates_by_contact`` — mêmes colonnes
    normalisées QW10 que le reste du CRM, indexées) : un second message de la
    même conversation (ou un prospect déjà connu par un autre canal) ne crée
    JAMAIS de doublon — renvoie le lead existant le plus récent tel quel, sans
    l'altérer (« referral avec lead → comportement inchangé »).

    Env-gated COMME le webhook : cette fonction n'est jamais appelée hors de
    ``WhatsAppCloudWebhookView.post`` (gardé par
    ``WHATSAPP_CLOUD_VERIFY_TOKEN``/``WHATSAPP_CLOUD_APP_SECRET`` — sans les
    deux, le webhook répond 404 et n'atteint jamais ce chemin), donc aucun
    flag séparé n'est nécessaire ici.

    Attribution : ``canal=WHATSAPP_CTWA``, ``meta_ad_id`` posé quand
    ``ad_id`` est fourni (même colonne de jointure que ADSENG1/XMKT32 — la
    variante Meta reste résolvable par ``apps.adsengine.attribution``).
    ``source=OS_NATIVE`` (créé nativement dans l'ERP — CTWA n'est pas un
    import, contrairement à ``META_LEAD_ADS``)."""
    phone = (phone or '').strip()
    if not phone or company is None:
        return None

    dupes = find_duplicates_by_contact(company, phone=phone)
    if dupes:
        return sorted(dupes, key=lambda d: d.date_creation, reverse=True)[0]

    extra = {}
    default = default_responsable_for(company)
    if default is not None:
        extra['owner'] = default
    ad_id = str(ad_id or '')[:64] or None
    lead = Lead.objects.create(
        company=company,
        nom='Lead WhatsApp/CTWA',
        telephone=phone,
        source=Lead.Source.OS_NATIVE,
        canal=Lead.Canal.WHATSAPP_CTWA,
        meta_ad_id=ad_id,
        **extra,
    )
    activity.log_creation(lead, None)
    LeadActivity.objects.create(
        company=lead.company, lead=lead, user=None,
        kind=LeadActivity.Kind.NOTE,
        body='Lead créé depuis une conversation WhatsApp/CTWA entrante '
             '(aucun lead préalable trouvé pour ce numéro).',
    )
    # CAD90 — la personne a ÉCRIT la première : relation précontractuelle à
    # sa demande. Le registre le dit, plutôt que de rester muet sur un lead
    # dont la touche n°1 partira justement sur WhatsApp.
    enregistrer_base_legale_lead(
        lead, source=CONSENT_SOURCE_WHATSAPP_ENTRANT,
        base_legale=BASE_LEGALE_SOLLICITATION)
    try:
        notify_new_lead(lead)
    except Exception:  # noqa: BLE001 — best-effort
        pass
    # MRY6 — démarrage EXPLICITE de la cadence de contact. Best-effort :
    # une cadence en échec ne fait JAMAIS échouer la création du lead.
    demarrer_cadence_contact(lead, origine='ctwa')
    recompute_lead_score(lead)
    return lead


def fetch_meta_lead_node(leadgen_id, access_token):  # pragma: no cover - réseau
    """ADSENG1 — Récupère les identifiants natifs (ad_id/adgroup_id/form_id) du
    nœud lead Meta via le Graph API officiel, pour le backfill.

    Isolé en fonction module (jamais dans ``webhooks.py`` — inchangé hors
    mapping) pour rester simulable en test (monkeypatch). Renvoie le dict brut
    ou lève sur échec (capté par l'appelant, best-effort par lead).

    CRX5 — la version de l'API vient de la SOURCE UNIQUE partagée
    (``apps.adsengine.api_version.GRAPH_BASE_URL``), jamais d'un littéral :
    la « v25.0 » codée en dur ici était la dernière copie divergente du
    dépôt, et c'est exactement de cette façon que la v19.0 du webhook est
    restée morte en production pendant des mois (ADSENG2). Constante plain —
    aucun modèle adsengine n'est importé.
    """
    import json
    import urllib.parse
    import urllib.request

    from apps.adsengine.api_version import GRAPH_BASE_URL

    qs = urllib.parse.urlencode({
        'fields': 'ad_id,adgroup_id,form_id',
        'access_token': access_token,
    })
    url = f'{GRAPH_BASE_URL}/{leadgen_id}?{qs}'
    with urllib.request.urlopen(url, timeout=10) as resp:  # noqa: S310
        return json.loads(resp.read().decode('utf-8'))


def backfill_meta_lead_attribution(
        *, company=None, access_token='', fetch_fn=None, limit=None):
    """ADSENG1 — Rétro-remplit l'attribution par variante des leads Lead Ads
    EXISTANTS (créés avant qu'on capture ad_id/adgroup_id/form_id).

    Pour chaque ``Lead`` de source ``meta_lead_ads`` dont ``meta_ad_id`` est
    encore vide, récupère ses identifiants natifs (ad_id/adgroup_id/form_id)
    depuis le nœud lead Meta via ``fetch_fn(leadgen_id, access_token)`` (défaut :
    ``services.fetch_meta_lead_node``, juste au-dessus — CRX5 : la docstring
    nommait ``webhooks.fetch_meta_lead_node``, qui n'a jamais existé et
    envoyait le lecteur chercher dans le mauvais module ; injectable/simulable
    en test), les
    stocke, résout les noms via les miroirs adsengine, et remplit ``utm_content``
    = ``ad-<ad_id>`` + ``utm_campaign`` = nom de campagne résolu.

    IDEMPOTENT : un lead déjà backfillé (``meta_ad_id`` non vide) est sauté ; une
    seconde exécution ne change rien. Best-effort par lead : un échec réseau sur
    un lead n'interrompt jamais le lot (loggé, sauté). Scopé société si
    ``company`` fourni. Renvoie ``{'scanned', 'updated', 'skipped', 'failed'}``.
    """
    import logging
    from django.db.models import Q
    from apps.adsengine.selectors import resolve_meta_ad_names

    if fetch_fn is None:
        fetch_fn = fetch_meta_lead_node
    _log = logging.getLogger(__name__)

    qs = Lead.objects.filter(
        external_system=_META_LEAD_ADS_SYSTEM,
        external_id__isnull=False,
    ).filter(
        Q(meta_ad_id__isnull=True) | Q(meta_ad_id=''),
    )
    if company is not None:
        qs = qs.filter(company=company)
    qs = qs.order_by('id')
    if limit:
        qs = qs[:limit]

    stats = {'scanned': 0, 'updated': 0, 'skipped': 0, 'failed': 0}
    for lead in qs:
        stats['scanned'] += 1
        try:
            node = fetch_fn(lead.external_id, access_token) or {}
        except Exception as exc:  # noqa: BLE001 — un lead ne bloque pas le lot
            stats['failed'] += 1
            _log.warning(
                'backfill_meta_lead_attribution: fetch échoué (lead #%s) : %s',
                lead.pk, exc)
            continue
        ad_id = str(node.get('ad_id') or '')
        adgroup_id = str(node.get('adgroup_id') or node.get('adset_id') or '')
        form_id = str(node.get('form_id') or '')
        if not ad_id:
            stats['skipped'] += 1
            continue
        names = resolve_meta_ad_names(
            lead.company, ad_id=ad_id, adgroup_id=adgroup_id,
            access_token=access_token)
        lead.meta_ad_id = ad_id[:64]
        lead.meta_adset_id = adgroup_id[:64] or lead.meta_adset_id
        lead.meta_form_id = form_id[:64] or lead.meta_form_id
        campaign_id = (names.get('campaign_id') or '')[:64]
        if campaign_id and not lead.meta_campaign_id:
            lead.meta_campaign_id = campaign_id
        # utm_content = ad-<ad_id> (convention ADSENG23) ; remplit sans écraser
        # une valeur déjà posée par un autre canal (first-touch préservée).
        if not lead.utm_content:
            lead.utm_content = f'ad-{ad_id}'[:300]
        campaign_name = (names.get('campaign_name') or '')[:300]
        if campaign_name and not lead.utm_campaign:
            lead.utm_campaign = campaign_name
        lead.save()
        stats['updated'] += 1
    return stats


# ── XMKT37 — Livechat / assistant IA de qualification (ERP-side) ─────────────

def create_lead_from_livechat(*, company, nom, telephone='', email='',
                              transcript_text='') -> Lead:
    """XMKT37 — Crée (ou dédupe sur) un lead dès que nom + contact sont captés
    par une session de livechat public.

    Point d'entrée cross-app sanctionné (services.py), appelé par
    ``apps.crm.public_chat_views``. Dédup (QJ8) par téléphone/email dans la
    société avant de créer (comme le webhook site) ; canal ``livechat``,
    stage NEW (STAGES.py, jamais hardcodé — ``Lead.stage`` a NEW pour
    défaut). Le transcript complet est collé en note chatter (``LeadActivity``).
    """
    nom = (nom or '').strip()[:255] or 'Prospect livechat'
    telephone = (telephone or '').strip()[:20]
    email = (email or '').strip()[:254]

    lead = None
    if telephone or email:
        dupes = find_duplicates_by_contact(
            company, phone=telephone or None, email=email or None)
        if dupes:
            lead = sorted(dupes, key=lambda d: d.date_creation, reverse=True)[0]

    if lead is None:
        extra = {}
        default = default_responsable_for(company)
        if default is not None:
            extra['owner'] = default
        lead = Lead.objects.create(
            company=company,
            nom=nom,
            telephone=telephone or None,
            email=email or None,
            canal=Lead.Canal.AUTRE,
            **extra,
        )
        activity.log_creation(lead, None)
        try:
            notify_new_lead(lead)
        except Exception:  # noqa: BLE001 — best-effort
            pass
        # MRY6 — même démarrage explicite que les autres créateurs vivants.
        demarrer_cadence_contact(lead, origine='livechat')
    else:
        changed = False
        if telephone and not lead.telephone:
            lead.telephone = telephone
            changed = True
        if email and not lead.email:
            lead.email = email
            changed = True
        if changed:
            lead.save()

    if transcript_text:
        LeadActivity.objects.create(
            company=lead.company, lead=lead, user=None,
            kind=LeadActivity.Kind.NOTE,
            body=f'Transcript livechat :\n{transcript_text}')

    recompute_lead_score(lead)
    return lead


def noter_touche_marketing(lead, message, *, ordre=0, cout=None):
    """XMKT16 — Consigne un événement marketing significatif (envoi/ouverture/
    clic de campagne, étape de séquence exécutée, réponse WhatsApp entrante)
    dans le chatter du lead (``LeadActivity``) + le journal d'attribution
    multi-touch FG204 (``PointContact``). Appelé par le module marketing de
    compta — jamais d'import du modèle CRM depuis compta, ce point d'entrée
    reste dans ``apps.crm.services`` comme toutes les écritures cross-app.

    Le canal réutilise ``Lead.Canal.AUTRE`` (aucun nouveau vocabulaire de
    canal n'est inventé) ; ``message`` porte le libellé lisible de
    l'événement (ex. « Campagne X envoyée »), stocké aussi dans
    ``PointContact.detail`` pour l'attribution.
    """
    LeadActivity.objects.create(
        company=lead.company, lead=lead, user=None,
        kind=LeadActivity.Kind.NOTE, body=message)
    return PointContact.objects.create(
        company=lead.company, lead=lead, canal=Lead.Canal.AUTRE,
        source='marketing', date_contact=timezone.now(),
        ordre=ordre, detail=message, cout=cout)


# ── YLEAD10 — Fast-lane comportemental : FOLLOW_UP à l'ouverture du devis ────


# ── QJ2 — Speed-to-lead : notifications vendeur avec lien wa.me ──────────────


# ── CAD-K ── CAD135 — les signaux de lecture remontent au LEAD ──────────────
#
# Audit L3 du 21/09/2026. Quand un client revient plusieurs fois sur la même
# section (le prix, l'étude), le système écrit lui-même « signal de friction,
# un appel peut débloquer la décision » — dans l'historique du DEVIS, sans
# aucune notification. Même sort pour « a commencé à lire en détail ».
# Personne ne les lit, sauf à ouvrir cet onglet par hasard.
#
# Ces deux signaux empruntent désormais le MÊME chemin que « devis ouvert » :
# une ligne dans le chatter du LEAD et une notification au responsable, avec
# le lien pour appeler. La note côté DEVIS reste écrite — elle appartient à
# l'historique du document, ce point d'entrée ne la remplace pas.
#
# NUANCE ASSUMÉE (round 2) : « le signal le plus prédictif » reste une
# HYPOTHÈSE tant que CAD87 ne l'a pas mesuré. Rien ici ne classe, ne priorise
# ni ne réordonne quoi que ce soit : on rend un fait visible, c'est tout.


# ─────────────────────────────────────────────────────────────────────────────
# Actions EN MASSE sur les leads (T3) — multi-sélection liste/kanban.
#
# Toute la logique métier vit ici (les vues restent fines) : règles du funnel
# (jamais en arrière, jamais un lead Perdu, réactivation du Froid), journal
# Historique par lead marqué « en masse », et garde-fous (devis liés bloquent la
# suppression). Tout est borné à la société de l'utilisateur appelant.
# ─────────────────────────────────────────────────────────────────────────────


# ── QJ20 — Site-visit appointment service ────────────────────────────────────


# ── XKB33 — WhatsApp entrant → chatter du lead/client ────────────────────────

def find_lead_by_phone(company, telephone):
    """Lead de `company` dont téléphone OU whatsapp correspond (normalisé).

    Point d'entrée cross-app sanctionné pour `apps.notifications` (webhook BSP
    WhatsApp) : matching par numéro SANS jamais exposer les modèles crm.
    Renvoie le lead le plus RÉCEMMENT créé en cas de doublon, ou None."""
    key = normalize_phone(telephone)
    if not key:
        return None
    candidates = [
        lead for lead in Lead.objects.filter(company=company)
        .order_by('-date_creation')
        if normalize_phone(lead.telephone) == key
        or normalize_phone(lead.whatsapp) == key
    ]
    return candidates[0] if candidates else None


def find_lead_by_email(company, email):
    """NTAPI15 — Lead de `company` dont l'email correspond (insensible à la
    casse). Point d'entrée cross-app sanctionné pour `apps.publicapi` (dédup
    upsert de l'import bulk) — jamais d'import direct de `Lead` ailleurs.
    Renvoie le lead le plus RÉCEMMENT créé en cas de doublon, ou None."""
    # ACRM38 (jumeau) — la même clé que l'identité client.
    email = _email_identite(email)
    if not email:
        return None
    return (
        Lead.objects.filter(company=company, email__iexact=email)
        .order_by('-date_creation')
        .first()
    )


# ── ZSAV8 — Convertir un ticket SAV en opportunité CRM ──────────────────────
# apps.sav ne peut PAS importer apps.crm.models directement (règle de
# modularité CLAUDE.md) : cette fonction est son unique porte d'entrée pour
# créer un lead depuis un ticket (upsell/remplacement).

def create_lead_depuis_ticket(*, company, user, client, contexte=''):
    """ZSAV8 — Crée (ou réutilise) un lead CRM depuis un ticket SAV.

    Réutilise un lead OUVERT (stage != COLD, non archivé) déjà lié à ce
    ``client`` plutôt que d'en créer un doublon. Sinon, crée un nouveau lead
    au stade ``NEW`` (STAGES.py, jamais codé en dur), pré-rempli avec
    l'identité du client + ``contexte`` en description.

    La note de ``contexte`` est attribuée au SYSTÈME (``user=None``) et non à
    l'utilisateur appelant : le récepteur QJ7
    (``_avancer_stage_on_contact_activity``) ne fait avancer NEW -> CONTACTED
    que sur un premier contact MANUEL (``instance.user is not None``), donc une
    note système laisse le lead au stade ``NEW`` attendu par ZSAV8 tout en
    conservant la trace « Créé depuis le ticket SAV … » sur le chatter du lead.

    Renvoie ``(lead, created)``."""
    # ACRM43 — la docstring dit « non archivé » : un lead archivé n'est
    # jamais réutilisé (nouveau lead à la place).
    existant = (
        Lead.objects
        .filter(company=company, client=client, is_archived=False)
        .exclude(stage=stages.COLD)
        .order_by('-date_creation')
        .first())
    if existant is not None:
        contexte_existant = (contexte or '').strip()
        if contexte_existant:
            # ACRM43 — le contexte du ticket est tracé au chatter du lead
            # réutilisé (note SYSTÈME, même règle QJ7 que la création).
            activity.log_note(existant, None, contexte_existant)
        return existant, False

    lead = Lead.objects.create(
        company=company,
        nom=f'{client.nom} {client.prenom or ""}'.strip() or client.nom,
        prenom=client.prenom or None,
        email=client.email or None,
        telephone=client.telephone or None,
        client=client,
        canal=Lead.Canal.AUTRE,
        stage=stages.NEW,
    )
    activity.log_creation(lead, user)
    contexte = (contexte or '').strip()
    if contexte:
        # Note SYSTÈME (user=None) : garde le lead au stade NEW (le récepteur
        # QJ7 ignore les activités système), tout en traçant l'origine.
        activity.log_note(lead, None, contexte)
    return lead, True


# ── XMKT4 — écriture de consentement marketing pour un lead ────────────────
# Point d'entrée UNIQUE pour poser un ``core.ConsentRecord`` depuis un lead
# (jamais d'écriture directe de compta/parametres dans core.ConsentRecord au
# nom d'un lead — cette fonction reste la porte d'entrée crm).


# ── XMKT19 — Actions CRM exécutables depuis une étape de séquence ──────────
# Point d'entrée UNIQUE pour qu'une ``EtapeSequence`` (module marketing de
# compta) exécute une action CRM au lieu d'un message — jamais d'import
# direct du modèle crm depuis compta ; chaque fonction journalise le chatter
# (``LeadActivity``) via ``activity``, jamais silencieuse.


# ── XMKT28 — Lead depuis une inscription à un événement marketing ──────────

def create_lead_from_evenement_marketing(
        *, company, nom, telephone='', email='', evenement_nom='') -> Lead:
    """XMKT28 — Crée (ou dédupe sur) un lead dès qu'un inscrit à un
    ``EvenementMarketing`` (module marketing de compta) est capturé. Même
    pattern que ``create_lead_from_livechat`` (XMKT37) : dédup par
    téléphone/email dans la société avant de créer, canal ``AUTRE``, stage
    NEW (défaut du champ).
    """
    nom = (nom or '').strip()[:255] or 'Prospect événement'
    telephone = (telephone or '').strip()[:20]
    email = (email or '').strip()[:254]

    lead = None
    if telephone or email:
        dupes = find_duplicates_by_contact(
            company, phone=telephone or None, email=email or None)
        if dupes:
            lead = sorted(dupes, key=lambda d: d.date_creation, reverse=True)[0]

    if lead is None:
        extra = {}
        default = default_responsable_for(company)
        if default is not None:
            extra['owner'] = default
        lead = Lead.objects.create(
            company=company,
            nom=nom,
            telephone=telephone or None,
            email=email or None,
            canal=Lead.Canal.AUTRE,
            **extra,
        )
        activity.log_creation(lead, None)
        # MRY6 — un inscrit d'événement marketing est une demande réelle.
        demarrer_cadence_contact(lead, origine='evenement_marketing')
    else:
        changed = False
        if telephone and not lead.telephone:
            lead.telephone = telephone
            changed = True
        if email and not lead.email:
            lead.email = email
            changed = True
        if changed:
            lead.save()

    if evenement_nom:
        activity.log_note(
            lead, None, f'Inscrit à l\'événement « {evenement_nom} »')
    recompute_lead_score(lead)
    return lead


# ── XPLT5 — API publique en ÉCRITURE (leads:write / activities:write) ───────
# Point d'entrée cross-app sanctionné (services.py) pour `apps.publicapi` :
# la société vient TOUJOURS de l'appelant (résolue depuis la clé API, jamais
# du corps), jamais acceptée en argument depuis les données utilisateur.

PUBLIC_LEAD_WRITABLE_FIELDS = (
    'nom', 'prenom', 'societe', 'email', 'telephone', 'ville',
    'canal', 'priorite', 'type_installation', 'stage',
)


def create_lead_from_public_api(*, company, fields):
    """XPLT5 — crée un lead depuis l'API publique en écriture.

    ``fields`` est filtré à la liste blanche ``PUBLIC_LEAD_WRITABLE_FIELDS``
    (un champ non listé est silencieusement ignoré — jamais 500). ``stage``,
    s'il est fourni, doit être une clé canonique STAGES.py valide (sinon
    ``ValueError`` — jamais de nouvelle liste d'étapes, jamais hardcodée) ;
    absent, le lead prend le défaut du modèle (NEW). ``nom`` est obligatoire.
    Company forcée serveur, jamais du body. Journalise la création
    (``LeadActivity``, acteur système) comme tout autre point d'entrée."""
    clean = {k: v for k, v in (fields or {}).items()
             if k in PUBLIC_LEAD_WRITABLE_FIELDS and v not in (None, '')}
    nom = (clean.pop('nom', '') or '').strip()
    if not nom:
        raise ValueError("Le champ « nom » est obligatoire.")
    stage = clean.pop('stage', None)
    if stage is not None and stage not in stages.STAGES:
        raise ValueError(
            f'Étape inconnue : {stage!r} (STAGES.py = {stages.STAGES}).')
    lead = Lead.objects.create(
        company=company, nom=nom,
        stage=stage or stages.NEW,
        **clean,
    )
    activity.log_creation(lead, None)
    # MRY6 — l'API publique crée de VRAIES demandes (formulaire partenaire,
    # intégration) : elles entrent dans la cadence comme les autres.
    demarrer_cadence_contact(lead, origine='api_publique')
    return lead


#: CRX21 — colonnes DÉRIVÉES recalculées par ``Lead.save()`` (QW10). Sans
#: elles dans ``update_fields``, un changement de téléphone/email n'est PAS
#: répercuté sur les colonnes indexées de dédup : le lead reste trouvable par
#: son ANCIEN numéro et invisible sous le nouveau. Même table que
#: ``LeadViewSet.COLONNES_DERIVEES`` (views.py) — la parité est le sujet de la
#: tâche : l'API publique écrit les mêmes leads que l'écran.
PUBLIC_LEAD_COLONNES_DERIVEES = {'telephone': 'phone_normalise',
                                 'email': 'email_normalise'}


def update_lead_from_public_api(*, company, lead_id, fields):
    """XPLT5 — met à jour un lead EXISTANT DE CETTE SOCIÉTÉ depuis l'API
    publique en écriture. Lève ``Lead.DoesNotExist`` si le lead n'appartient
    pas (ou plus) à ``company`` — jamais de fuite cross-tenant. Champs
    filtrés à la même liste blanche que la création ; ``stage`` validé contre
    STAGES.py. Journalise chaque champ changé (chatter, acteur système).

    CRX21 — PARITÉ avec le PATCH de l'écran (``LeadViewSet.perform_update``),
    qui manquait entièrement à ce chemin :

    * **verrou du lead perdu** — un lead marqué perdu ne change pas d'étape,
      pas même par une intégration (le ``LeadSerializer`` refuse déjà, et ce
      verrou PRÉCÈDE toute échappatoire) ;
    * **garde funnel** ``_bulk_stage_allowed`` — une intégration ne recule ni
      ne rouvre un pipeline. Il n'y a PAS ici l'échappatoire ``confirme_recul``
      de l'écran : elle suppose une confirmation HUMAINE devant un lead nommé,
      qu'aucun appel machine ne peut donner ;
    * **les 4 effets internes** de ``perform_update`` : émission de
      ``lead_stage_changed``, ``first_contacted_at`` (FG28), recalcul du score
      (QJ6) et synchronisation de l'activité de relance ;
    * **colonnes dérivées** (``phone_normalise``/``email_normalise``) ajoutées
      à ``update_fields`` quand leur source change — sinon la dédup indexée
      devient aveugle après un changement de téléphone (chemins publicapi bulk
      ET PATCH unitaire).

    Lève ``ValueError`` (traduit en 400 par les vues publiques) sur une étape
    inconnue, un lead perdu, ou un recul de funnel.
    """
    lead = Lead.objects.get(company=company, pk=lead_id)
    clean = {k: v for k, v in (fields or {}).items()
             if k in PUBLIC_LEAD_WRITABLE_FIELDS}
    stage = clean.get('stage')
    # ACRM58 — ``stage`` présent mais vide (null comme '') : erreur SOUS LE
    # CHAMP (400 ``{stage: [...]}``), jamais un IntegrityError (500). Une
    # ValidationError DRF (pas un ValueError) pour que la vue publique la
    # rende telle quelle, champ nommé ; l'import en masse l'inscrit en ligne
    # en erreur.
    if 'stage' in clean and stage in (None, ''):
        raise DRFValidationError(
            {'stage': ["L'étape ne peut pas être vide."]})
    if stage is not None and stage not in stages.STAGES:
        raise ValueError(
            f'Étape inconnue : {stage!r} (STAGES.py = {stages.STAGES}).')
    if stage is not None and stage != lead.stage:
        if lead.perdu:
            raise ValueError('Lead perdu — étape non modifiable.')
        if not _bulk_stage_allowed(lead.stage, stage):
            raise ValueError("On ne recule pas une étape.")
    old = Lead.objects.get(pk=lead.pk)
    changed_fields = []
    for field, value in clean.items():
        if value in (None, '') and field != 'stage':
            continue
        if getattr(lead, field) != value:
            setattr(lead, field, value)
            changed_fields.append(field)
    if changed_fields:
        ecrits = list(changed_fields)
        for source, derivee in PUBLIC_LEAD_COLONNES_DERIVEES.items():
            if source in changed_fields:
                ecrits.append(derivee)
        lead.save(update_fields=ecrits)
        activity.log_changes(old, lead, None)
        # Les 4 effets du PATCH de l'écran, dans le même ordre. Tous sont
        # best-effort par construction (chacun catche pour son compte) : une
        # intégration ne doit jamais échouer sur un effet secondaire.
        sync_relance_activity(lead, None)
        maybe_set_first_contacted_at(old, lead)
        recompute_lead_score(lead)
        _emit_stage_changed(lead, old.stage, lead.stage, user=None)
    return lead


def create_activity_from_public_api(*, company, lead_id, body):
    """XPLT5 — ajoute une note (activité chatter) sur un lead DE CETTE
    SOCIÉTÉ depuis l'API publique en écriture. Lève ``Lead.DoesNotExist`` si
    hors société (jamais de fuite cross-tenant). ``body`` ne peut être vide."""
    lead = Lead.objects.get(company=company, pk=lead_id)
    body = (body or '').strip()
    if not body:
        raise ValueError("Le champ « body » est obligatoire.")
    return activity.log_note(lead, None, body)


def ajouter_note_lead(*, company, lead_id, user, body):
    """NTMOB1 — ajoute une note (activité chatter) sur un lead DE CETTE
    SOCIÉTÉ, avec l'utilisateur ACTEUR (contrairement à
    ``create_activity_from_public_api``, qui journalise sans acteur).

    Point d'entrée cross-app pour rejouer une note posée hors-ligne sans
    importer ``apps.crm.models``/``views``. Lève ``Lead.DoesNotExist`` hors
    société (jamais de fuite cross-tenant) et ``ValueError`` sur un corps vide.
    """
    lead = Lead.objects.get(company=company, pk=lead_id)
    body = (body or '').strip()
    if not body:
        raise ValueError("Le champ « body » est obligatoire.")
    return activity.log_note(lead, user, body)


def ajouter_note_lead_si_nouvelle(*, company, lead_id, user, body):
    """Comme :func:`ajouter_note_lead`, mais SANS RÉPÉTER un corps identique.

    Rend l'activité créée, ou ``None`` si le lead porte DÉJÀ une note au corps
    exactement identique.

    POURQUOI ELLE EXISTE (F6, 29/08/2026). L'auto-pipeline du tunnel doit
    laisser une trace quand le moteur REFUSE de chiffrer un lead — sans quoi le
    commercial constate seulement que « hier ces leads recevaient un devis ».
    Mais le refus RELÂCHE la marque de dédup (une donnée manquante aujourd'hui
    ne doit pas fermer le lead pour toujours) : chaque nouvelle livraison du
    webhook rejoue donc le même refus, et une note par rejeu ensevelirait
    l'historique du lead sous le même paragraphe. La note est donc posée une
    fois par MOTIF : le motif change ⇒ une nouvelle note ; le motif se répète
    ⇒ silence.

    La comparaison porte sur le CORPS et rien d'autre — c'est lui que le
    commercial lit, et c'est lui qui nomme le champ manquant.
    """
    lead = Lead.objects.get(company=company, pk=lead_id)
    body = (body or '').strip()
    if not body:
        raise ValueError("Le champ « body » est obligatoire.")
    deja = LeadActivity.objects.filter(
        company=company, lead=lead, kind=LeadActivity.Kind.NOTE,
        body=body).exists()
    if deja:
        return None
    return activity.log_note(lead, user, body)


# CAD72 (21/09/2026) — le SECOND catalogue « parrainage » de YSERV11 a
# disparu d'ici. Un dictionnaire de textes par défaut + un générateur
# `get_or_create_*` vivaient ici, semant une SECONDE ligne
# `crm.MessageTemplate` au premier usage — texte FR promettant une
# récompense FERME, et texte darija TRANSCRIT EN ALPHABET LATIN (chiffres
# pour des lettres arabes — « 3 »/« 9 »), alors que le catalogue darija
# validé (`parametres.MESSAGE_TEMPLATE_DEFAULTS_DARIJA`) est écrit en
# arabe, relu par un natif le 04/09/2026. Leur seul appelant vivait dans
# `apps/compta/services.py` (flux NPS), retiré quand `compta` a été mis en
# coquille par le drain SOLMVP (`apps/compta/` n'a plus de `services.py`) —
# plus aucun appelant (grep sur tout le backend). Le catalogue UNIQUE pour
# les messages client est désormais `parametres.MessageTemplate` (clé
# `parrainage`, déjà validée dans `docs/crm/messages_meryem.md`, rendue par
# `message_pour_etape` comme n'importe quelle autre touche) — voir
# `tests_cad72_parrainage_catalogue_unique.py`.


# ─────────────────────────────────────────────────────────────────────────────
# QX42 — Rétention PII des copies brutes d'intake (registre YOPSB10, core.retention)
#
# `WebsiteLeadPayload` (PII brute + IP) et `ChatSessionPublique`
# s'accumulaient INDÉFINIMENT. ACRM19 — l'effacement d'un lead
# (`dsr_provider.anonymiser_lead`, DSR ET rétention) caviarde désormais LUI-MÊME
# ces copies brutes : les purges par âge ci-dessous ne sont plus le seul
# rempart, seulement le ménage de fond. Le framework générique existe (`core.retention`)
# mais son registre est VIDE — aucune app n'y enregistre de politique. Ceci
# enregistre la politique CRM (voir `CrmConfig.ready()`), fenêtre par défaut
# 180 jours, override founder via `WEBSITE_LEAD_PAYLOAD_RETENTION_DAYS` /
# `CHAT_SESSION_RETENTION_DAYS` (settings/.env — même patron que les autres
# constantes founder-configurables de ce module, ex.
# `WEBSITE_LEAD_WEBHOOK_SECRET`). 0/négatif désactive la purge (conservation
# illimitée, comportement actuel inchangé).


# ─────────────────────────────────────────────────────────────────────────────
# YOPSB11 — Archivage par lots de `LeadActivity` (chatter à forte croissance)
#
# Le chatter (`LeadActivity`) est append-only et grossit sans borne, alourdissant
# le chemin chaud. `archiver_anciens(now, jours)` DÉPLACE les entrées plus
# vieilles que `jours` vers la table froide `LeadActivityArchive` (par lots de
# 5 000, un commit par lot — jamais de transaction géante) puis les supprime de
# la table vive. Fenêtre par défaut 0 = OFF (aucun archivage, comportement
# inchangé) ; réglage via `CRM_LEADACTIVITY_ARCHIVE_DAYS`. La politique est
# enregistrée dans le registre partagé YOPSB10 depuis `CrmConfig.ready()`.

DEFAULT_LEADACTIVITY_ARCHIVE_DAYS = 0


def _leadactivity_to_archive(row):
    """Mappe une `LeadActivity` vive vers les champs de `LeadActivityArchive`
    (FK dénormalisées en identifiants entiers — archive froide indépendante)."""
    return {
        'original_id': row.pk,
        'company_id': row.company_id,
        'lead_id': row.lead_id,
        'kind': row.kind,
        'field': row.field,
        'field_label': row.field_label,
        'old_value': row.old_value,
        'new_value': row.new_value,
        'body': row.body,
        'outcome': row.outcome,
        'attachment_id': row.attachment_id,
        'bulk': row.bulk,
        'user_id': row.user_id,
        'created_at': row.created_at,
    }


def archiver_anciens(now, jours, apply_=True):
    """YOPSB11 — archive les `LeadActivity` plus vieilles que `jours`.

    Déplacement par lots de 5 000 (un commit par lot) vers `LeadActivityArchive`
    puis suppression de la table vive. `jours <= 0` (défaut OFF) → 0, rien ne
    bouge. `apply_=False` (dry-run du registre) → compte sans déplacer. Renvoie
    le nombre d'entrées archivées."""
    from core.retention import archive_old_rows
    from .models import LeadActivity, LeadActivityArchive

    return archive_old_rows(
        LeadActivity, LeadActivityArchive, _leadactivity_to_archive,
        cutoff_field='created_at', now=now, jours=jours, apply_=apply_,
    )


class SuppressionLeadsRefusee(Exception):
    """``delete_leads_for_company`` appelée sur une société qui n'est PAS un
    bac à sable — la suppression est refusée AVANT toute écriture."""


def _est_societe_bac_a_sable(company):
    """True uniquement si ``company`` est la société-JUMELLE d'un
    ``publicapi.SandboxTenant`` (jamais la société réelle propriétaire).

    Lecture par le registre Django (``apps.get_model``) et non par un import
    statique : le domaine ``crm`` ne se couple pas au satellite ``publicapi``
    (aucune nouvelle arête d'import, aucun cycle de chargement — c'est
    ``publicapi`` qui appelle ``crm``, jamais l'inverse). La garde échoue
    FERMÉ : app absente, société inconnue ou ``None`` → False → refus.
    """
    if company is None:
        return False
    company_pk = getattr(company, 'pk', company)
    if company_pk is None:
        return False
    try:
        SandboxTenant = django_apps.get_model('publicapi', 'SandboxTenant')
        return SandboxTenant.objects.filter(
            sandbox_company_id=company_pk).exists()
    except (LookupError, TypeError, ValueError):
        # App absente, ou identifiant non convertible (slug, objet exotique) :
        # on ne PROUVE pas que c'est un bac à sable → refus.
        return False


def delete_leads_for_company(company):
    """NTAPI27 — supprime TOUS les leads de ``company``. Point d'entrée
    d'ÉCRITURE cross-app sanctionné pour ``apps.publicapi`` (reset du bac à
    sable API). Renvoie le nombre supprimé.

    DÉFENSE EN PROFONDEUR (garde posée ICI, pas seulement chez l'appelant) :
    c'est une suppression DURE — elle contourne la corbeille/soft-delete, il
    n'existe donc NI trace NI annulation. Le seul appelant légitime
    (``publicapi.services.reset_sandbox``) vise toujours
    ``tenant.sandbox_company``, mais un unique ``SandboxTenant`` mal pointé
    suffirait à détruire le pipeline commercial RÉEL sans recours. La fonction
    REFUSE donc de s'exécuter — bruyamment, avant la moindre écriture — tant
    que la société cible n'est pas prouvée société-jumelle d'un bac à sable.
    """
    from .models import Lead

    if not _est_societe_bac_a_sable(company):
        raise SuppressionLeadsRefusee(
            "Suppression de masse REFUSÉE : la société ciblée (%r) n'est pas "
            "un bac à sable — aucun SandboxTenant ne la désigne comme "
            "société-jumelle. `delete_leads_for_company` supprime "
            "DÉFINITIVEMENT tous les leads (suppression dure, sans corbeille "
            "ni annulation) et reste réservée au reset du bac à sable API."
            % (getattr(company, 'pk', company),))

    qs = Lead.objects.filter(company=company)
    count = qs.count()
    qs.delete()
    return count


# ── NTMIG28 — miroir du compteur de déploiements d'un partenaire ────────────


# ---------------------------------------------------------------------------
# AUD518 — Effets de CRÉATION d'un lead importé (dataimport)
# ---------------------------------------------------------------------------


def finaliser_lead_importe(lead, *, user=None, lead_attrs=None):
    """AUD518 — applique à un lead IMPORTÉ les effets de création du chemin
    MANUEL, dont il était intégralement privé.

    ``apps.dataimport`` faisait ``Lead.objects.create(company=…, **f)`` et
    s'arrêtait là : pas d'``owner`` (donc un lead invisible de l'écran « mes
    leads »), aucune ``LeadActivity`` de création (aucune trace, et le sweep
    d'inactivité sans point de départ), ``score`` figé à 0 (donc jamais
    évalué MQL). Ce point d'entrée est le SEUL que ``dataimport`` appelle :
    la frontière cross-app est respectée (aucun import de ``crm.activity`` ni
    du modèle depuis l'app d'import).

    Trois effets, dans l'ordre du chemin manuel
    (``LeadViewSet.perform_create``) :

    1. OWNER — même règle exactement : un utilisateur à portée restreinte
       garde la propriété de ce qu'il crée, sinon le responsable par défaut
       de la société (territoires NTCRM1 puis repli round-robin XSAL11) est
       résolu depuis les attributs de la ligne. Un ``owner`` déjà posé par le
       fichier n'est JAMAIS écrasé.
    2. CHATTER — ``activity.log_creation`` (l'app d'import n'y touche pas
       elle-même).
    3. SCORE — ``recompute_lead_score``, qui évalue aussi le passage MQL
       (``maybe_assign_mql``). Déjà best-effort en interne.

    Renvoie le lead.
    """
    from . import activity

    if not lead.owner_id:
        proprietaire = None
        portee = getattr(user, 'record_scope', None)
        if user is not None and callable(portee) and portee() != 'all':
            proprietaire = user
        else:
            proprietaire = default_responsable_for(
                lead.company, lead_attrs=lead_attrs)
        if proprietaire is not None:
            lead.owner = proprietaire
            lead.save(update_fields=['owner'])

    activity.log_creation(lead, user)
    recompute_lead_score(lead)
    return lead


# ── MRY30 — PLACEMENT DES ANCIENS LEADS DANS LES CADENCES DU MOTEUR ──────────
#
# Le moteur de relances ne démarre que sur les leads qui ARRIVENT. Le
# portefeuille déjà présent — plusieurs centaines de dossiers, dont les 930
# leads du miroir Odoo — resterait donc sans aucune cadence, et le bénéfice
# n'arriverait qu'au fil des semaines. Décision fondateur du 06/09/2026 :
# « tous les anciens leads non Froid sont traités ; le moteur décide à quelle
# étape des six appels chacun se trouve ».
#
# Trois différences assumées avec la reprise MRY23
# (`demarrer_cadences_existantes`, qui reste en place et ne change pas) :
#
#   1. le MIROIR ODOO EST INCLUS. `_garde_cadence_contact` refuse
#      `source == ODOO_IMPORT_TEST` — garde juste pour un démarrage AUTOMATIQUE
#      à la création (elle empêche un import de 930 lignes d'inonder la file),
#      fausse pour un placement DEMANDÉ à la main sur ce même portefeuille.
#      C'est pourquoi ce service appelle `initialiser_plan_relance`
#      directement et JAMAIS `demarrer_cadence_contact` ;
#   2. il n'y a pas de fenêtre d'éligibilité qui laisse des leads de côté :
#      un dossier trop ancien pour être relancé n'est pas ignoré, il est mis
#      en DORMANCE explicite (Froid + étiquette + réveil étalé) ;
#   3. l'aperçu et l'application partagent LE MÊME CALCUL — sans partager
#      les écritures. L'aperçu était une exécution complète dans une
#      transaction annulée : fidèle, mais il matérialisait les touches des
#      277 candidats pour les jeter aussitôt, soit plus de 20 s pendant
#      lesquelles le navigateur abandonnait (deux 499 dans nginx le
#      07/09/2026, sur le clic « Aperçu » du Cockpit). Il est désormais un
#      CALCUL PUR : mêmes décisions, mêmes créneaux, mêmes dates — obtenus
#      par `calculer_echeances_cadence`, la fonction que l'application
#      utilise elle aussi pour créer les touches. Un dry-run qui recalcule
#      « à côté » finit toujours par annoncer autre chose que ce que --apply
#      fait ; partager la FONCTION donne la même garantie que partager
#      l'exécution, pour le prix d'un calcul ;
#   4. l'application se fait PAR LOTS de `limite` leads (défaut 40), l'écran
#      rappelant tant que `restants > 0`. Écrire 277 dossiers d'un trait
#      dépassait le délai du navigateur exactement comme l'aperçu.

#: Au-delà de ce silence, un dossier n'est plus « en cours » : lui envoyer la
#: touche J+1 d'une cadence positionnée serait un message hors sujet. Il part
#: en dormance (réveil), pas en relance.
PLACEMENT_FENETRE_JOURS = 14

#: Réveils démarrés par JOUR OUVRÉ. Lancer 200 réveils le même matin
#: saturerait la journée de Meryem et ferait partir 200 messages en rafale
#: depuis le même numéro — le meilleur moyen de se faire signaler comme spam.
PLACEMENT_REVEILS_PAR_JOUR = 8

#: Les huit créneaux du matin, 20 minutes d'écart (10 h 00 → 12 h 20). Chacun
#: passe ensuite par `horaires.prochain_creneau_appel` au canal `whatsapp`
#: (une cadence de réveil s'ouvre par un message) : un créneau hors fenêtre
#: est recalé, jamais gardé tel quel. La pause du vendredi ne le concerne pas
#: — elle ne vaut que pour les appels (07/09/2026).
PLACEMENT_CRENEAUX = tuple(
    datetime.time(10 + (rang * 20) // 60, (rang * 20) % 60)
    for rang in range(PLACEMENT_REVEILS_PAR_JOUR))

#: Délai (jours) de la PREMIÈRE touche de réveil, quand la société n'a pas
#: encore de gabarit `reveil` en base. Le créneau étalé est la date visée pour
#: cette première touche : `depart = créneau − ce délai`.
PLACEMENT_REVEIL_DELAI_JOURS = 30

#: MRY30 — l'étiquette du dormant JAMAIS CHIFFRÉ. Le pendant « Devis sans
#: suite » existe déjà (`_CLOTURE_TAGS['apres_devis']`) : on le RÉUTILISE
#: plutôt que d'écrire un second libellé qui divergerait.
_PLACEMENT_TAG_JAMAIS_CHIFFRE = 'Jamais chiffré'

#: MRY30 — pour un dormant « devis sans suite », les deux touches de réveil
#: DOIVENT parler d'une proposition reçue (A1 puis A3) : ces leads ont bien
#: reçu un devis — dans Odoo — même sans devis ERP, et
#: `_adapter_gabarits_reveil` (qui ne lit que les devis ERP) choisirait
#: sinon le message « jamais chiffré », faux pour eux.
_PLACEMENT_CLES_REVEIL_DEVIS = ('reveil_a1', 'reveil_a3')

#: MRY30 — marque de la note chatter. Elle NOMME la décision fondateur du
#: 06/09/2026 qui a créé ce placement ; ce n'est pas la date d'exécution (déjà
#: portée par l'horodatage de l'activité) — un texte fixe, donc lisible et
#: vérifiable à l'identique quel que soit le jour du passage.
PLACEMENT_MARQUEUR = 'moteur, 06/09/2026'

#: Les cinq décisions possibles, DANS L'ORDRE du contrat
#: `contract_samples/placement_anciens_leads.json` : (code, libellé, cadence).
PLACEMENT_DECISIONS = (
    ('contact_complete',
     "Contact — depuis la première touche (Message d'identité)", 'contact'),
    ('contact_positionne',
     "Contact — positionné selon l'ancienneté, touches passées sautées",
     'contact'),
    ('apres_devis_positionne',
     'Après devis — positionné depuis l\'envoi, touches passées sautées',
     'apres_devis'),
    ('dormant_devis',
     'Dormant — Froid, tag « Devis sans suite », réveil étalé', 'reveil'),
    ('dormant_jamais_chiffre',
     'Dormant — Froid, tag « Jamais chiffré », réveil étalé', 'reveil'),
)

_PLACEMENT_CADENCES = {code: cadence for code, _, cadence in PLACEMENT_DECISIONS}

#: Le code de dormance de CHAQUE famille : c'est le repli d'une cadence
#: positionnée dont TOUTES les touches sont déjà passées (rien à faire demain
#: = un dossier dormant, pas une cadence vide).
_PLACEMENT_REPLI_DORMANT = {
    'contact_positionne': 'dormant_jamais_chiffre',
    'apres_devis_positionne': 'dormant_devis',
}

#: L'étiquette posée par chaque code de dormance.
_PLACEMENT_TAGS = {
    'dormant_devis': _CLOTURE_TAGS['apres_devis'],
    'dormant_jamais_chiffre': _PLACEMENT_TAG_JAMAIS_CHIFFRE,
}

#: Note portée par une touche déjà échue au moment du placement. La REJOUER
#: enverrait aujourd'hui le message du J+1 d'il y a dix jours.
PLACEMENT_NOTE_PASSEE = 'passée avant le moteur'

#: Leads placés PAR APPEL d'application. 277 dossiers d'un trait, c'est
#: plusieurs milliers d'écritures dans une seule requête HTTP — au-delà du
#: délai du navigateur (20 s côté axios), donc un 499 et un placement dont
#: personne ne sait ce qu'il a fait. L'écran rappelle jusqu'à `restants == 0`.
PLACEMENT_LOT_DEFAUT = 40

#: Borne haute de `limite` : au-delà, on retombe dans le cas qui a produit le
#: 499. Ce n'est pas un réglage de confort, c'est la garde.
PLACEMENT_LOT_MAX = 200

#: Lignes détaillées du rapport. Ce sont les SEULES à être datées : calculer
#: l'échéance des 270 autres coûterait le prix qu'on vient justement de
#: supprimer, pour un écran qui n'en montre que vingt.
PLACEMENT_APERCU_MAX = 20


#: ACRM47/ACRM61 — message de la réponse 503 ``{detail}`` (contrat
#: ``placement_anciens_leads.json``, ``exemple_erreur``).
PLACEMENT_DEVIS_ILLISIBLES = (
    "Lecture des devis acceptés indisponible : placement suspendu, rien "
    "n'a été appliqué")


class PlacementImpossible(Exception):
    """Un lead retenu n'a finalement pas pu être placé (cadence vide, gabarit
    absent…). Comptée dans ``erreurs`` du rapport, jamais propagée : le
    placement est best-effort LEAD PAR LEAD — un dossier bancal n'empêche
    jamais les 276 autres d'être traités."""


def _placement_moment(valeur):
    """Normalise une ancre en datetime AWARE (une ``date`` comparée à un
    datetime lèverait ``TypeError`` au premier lead)."""
    from . import horaires

    if valeur is None:
        return None
    if not isinstance(valeur, datetime.datetime):
        return datetime.datetime.combine(
            valeur, datetime.time(0, 0), tzinfo=horaires.CASABLANCA)
    if timezone.is_naive(valeur):
        return timezone.make_aware(valeur, datetime.timezone.utc)
    return valeur


def _placement_derniers_par_lead(qs):
    """``{lead_id: created_at}`` du plus récent de chaque lead — UNE requête."""
    from django.db.models import Max
    return {
        ligne['lead_id']: ligne['dernier']
        for ligne in qs.values('lead_id').annotate(dernier=Max('created_at'))
    }


def _placement_devis_du_lot(company, lead_ids):
    """Les deux lectures cross-app du placement, via ``ventes.selectors``
    (jamais ``ventes.models`` — frontière M3) : les leads à devis ACCEPTÉ (à
    écarter) et le dernier devis ENVOYÉ de chacun (qui date la cadence).

    ACRM47 — échoue FERMÉ : si ``ventes`` est illisible, la garde « devis
    accepté » ne peut plus écarter les signés — continuer enverrait au Froid
    un client qui a dit oui. ``PlacementImpossible`` (message français) est
    levée AVANT toute écriture : la vue répond 503 ``{detail}``, la commande
    sort en erreur, rien n'est appliqué."""
    try:
        from apps.ventes.selectors import (
            dernier_devis_envoye_par_lead, leads_avec_devis_accepte)
        return (leads_avec_devis_accepte(company, lead_ids),
                dernier_devis_envoye_par_lead(company, lead_ids))
    except Exception as exc:  # noqa: BLE001 — journalisé puis échec fermé
        logger.warning(
            'MRY30: devis illisibles (société %s)',
            getattr(company, 'pk', '?'), exc_info=True)
        raise PlacementImpossible(PLACEMENT_DEVIS_ILLISIBLES) from exc


def _decider_placements(company, maintenant, gabarits=None,
                        leads_en_portee=None):
    """Phase de DÉCISION : QUI est candidat, QUI est écarté, QUELLE décision
    s'applique à chacun — et, pour les cadences positionnées, s'il leur reste
    seulement une touche à faire (sinon elles basculent en dormance ici même,
    cf. ``_trancher_cadence_positionnee``).

    N'écrit AUCUNE donnée métier — pas une touche, pas une étiquette, pas un
    changement d'étape. Seule exception, pré-existante et assumée :
    ``CadenceRelanceEtape.cadence_pour`` seede le GABARIT d'une société qui
    n'en a pas encore (un référentiel de paramètres, jamais un dossier).

    Renvoie ``(decisions, ignores, total_candidats)``. Chaque décision est un
    dictionnaire de travail que l'étalement puis l'exécution complètent
    (``creneau``…) — jamais un modèle enregistré."""
    gabarits = gabarits or _placement_gabarits(company)
    base = Lead.objects.filter(
        company=company, is_archived=False, perdu=False,
        ne_plus_contacter=False,
    ).exclude(stage__in=[stages.COLD, stages.SIGNED])
    # ALEA25 — appelé depuis l'API, le placement est BORNÉ par la portée de
    # l'utilisateur (``LeadViewSet._leads_en_portee``) : un Commercial ne
    # voit ni ne place les leads d'un collègue hors équipe. ``None`` (la
    # commande de gestion) = toute la société, comme avant.
    if leads_en_portee is not None:
        base = base.filter(pk__in=leads_en_portee.values('pk'))
    candidats = list(base.order_by('pk'))
    total = len(candidats)
    # ACRM61/ACRM20 — ``rappel_manuel_a_venir`` : entier, jamais null.
    ignores = {'deja_en_cadence': 0, 'devis_accepte_non_signe': 0,
               'rappel_manuel_a_venir': 0}
    if not candidats:
        return [], ignores, total
    # ACRM20 — date LOCALE du jour (Africa/Casablanca) du moment de décision.
    aujourdhui = timezone.localtime(maintenant).date()

    ids = [lead.pk for lead in candidats]
    # Le moteur TIENT déjà ces dossiers : une seconde cadence dessus, ce sont
    # deux séries de messages parallèles à la même personne.
    # ACRM46 — seul un plan OUVERT (touche À FAIRE, prédicat partagé avec
    # ``initialiser_plan_relance``) tient le lead : des touches toutes closes
    # (faites/sautées/annulées) le rendent candidat au placement.
    deja = set(RelanceEtape.objects.filter(
        _q_plan_ouvert(), company=company, lead_id__in=ids)
        .values_list('lead_id', flat=True))
    acceptes, envoyes = _placement_devis_du_lot(company, ids)

    humaines = _placement_derniers_par_lead(
        LeadActivity.objects.filter(lead_id__in=ids, user__isnull=False)
        .exclude(kind__in=[LeadActivity.Kind.CREATION,
                           LeadActivity.Kind.MODIFICATION]))
    etapes_stage = _placement_derniers_par_lead(
        LeadActivity.objects.filter(lead_id__in=ids, field='stage'))

    decisions = []
    for lead in candidats:
        if lead.pk in deja:
            ignores['deja_en_cadence'] += 1
            continue
        if lead.pk in acceptes:
            # Un devis accepté attend un passage en Signé À LA MAIN, pas une
            # relance : demander « alors, ce devis ? » à quelqu'un qui a dit
            # oui est le pire message du portefeuille.
            ignores['devis_accepte_non_signe'] += 1
            continue
        if lead.relance_date is not None and lead.relance_date >= aujourdhui:
            # ACRM20 — un rappel MANUEL à venir (posé par la commerciale) tient
            # le lead hors dormance : jamais de Froid, d'étiquette ni de
            # Réveil, et sa ``relance_date`` n'est jamais remplacée.
            ignores['rappel_manuel_a_venir'] += 1
            continue
        devis = envoyes.get(lead.pk)
        # L'ANCRE : le dernier signe de vie du dossier, quelle qu'en soit la
        # nature. La seule date de création ferait passer pour dormant un lead
        # rappelé hier ; la seule dernière activité raterait un devis parti
        # sans qu'on note rien.
        ancre = _placement_moment(lead.date_creation)
        for candidate in (humaines.get(lead.pk), etapes_stage.get(lead.pk),
                          getattr(devis, 'date_envoi', None)):
            candidate = _placement_moment(candidate)
            if candidate is not None and (ancre is None or candidate > ancre):
                ancre = candidate
        ancre = ancre or maintenant
        jours = (maintenant - ancre).days
        recent = jours <= PLACEMENT_FENETRE_JOURS

        if devis is not None:
            # Un devis ERP ENVOYÉ date la cadence, quel que soit son âge : le
            # suivi part de l'envoi RÉEL et les touches déjà passées seront
            # sautées. S'il n'en reste aucune, le repli dormant s'en charge.
            code, depart = 'apres_devis_positionne', devis.date_envoi
        elif lead.stage in (stages.QUOTE_SENT, stages.FOLLOW_UP):
            code, depart = (('apres_devis_positionne', ancre) if recent
                            else ('dormant_devis', None))
        elif lead.stage == stages.CONTACTED:
            code, depart = (('contact_positionne', ancre) if recent
                            else ('dormant_jamais_chiffre', None))
        else:  # NEW — le seul restant (Froid et Signé sont exclus en amont).
            code, depart = (('contact_complete', maintenant) if recent
                            else ('dormant_jamais_chiffre', None))

        entree = {
            'lead': lead,
            'code': code,
            'cadence': _PLACEMENT_CADENCES[code],
            'depart': _placement_moment(depart),
            'devis': devis if code == 'apres_devis_positionne' else None,
            'positionne': code in _PLACEMENT_REPLI_DORMANT,
            'ancre': ancre,
            'jours': jours,
            'nom': f'{lead.nom} {lead.prenom or ""}'.strip(),
            'stage_libelle': stages.STAGE_LABELS.get(lead.stage, lead.stage),
            'source': lead.source or '',
            'creneau': None,
            'prochaine_touche': '',
            'prochaine_le': None,
        }
        if entree['positionne']:
            _trancher_cadence_positionnee(entree, maintenant, gabarits)
        decisions.append(entree)
    return decisions, ignores, total


def _echeances_best_effort(lead, cadence, depart, gabarits):
    """``calculer_echeances_cadence`` en mode best-effort : une liste vide au
    lieu d'une exception.

    Le placement est best-effort LEAD PAR LEAD (`PlacementImpossible`) : un
    dossier dont les horaires ou le gabarit se lisent mal ne doit pas faire
    tomber l'aperçu des 276 autres — c'est-à-dire toute la carte."""
    try:
        return calculer_echeances_cadence(lead, cadence, depart,
                                          gabarits=gabarits(cadence))
    except Exception:  # noqa: BLE001 — un dossier bancal n'arrête rien
        logger.warning('MRY30: échéances illisibles (lead #%s, cadence %s)',
                       getattr(lead, 'pk', '?'), cadence, exc_info=True)
        return []


def _trancher_cadence_positionnee(entree, maintenant, gabarits):
    """Date une cadence positionnée — ou la BASCULE en dormance.

    Une cadence positionnée dont TOUTES les touches sont déjà échues ne
    relancerait personne : elle bascule sur la dormance de sa famille. Cette
    bascule change un CHIFFRE que la carte affiche (`par_etape`), elle
    appartient donc à la DÉCISION, pas à l'exécution — sinon l'aperçu
    annoncerait « après devis : 30 » là où l'application écrirait « dormants :
    30 », et le second clic montrerait autre chose que le premier. C'est la
    leçon de MRY23, tirée un cran plus tôt.

    C'est le SEUL calcul d'échéances mené pour toute une famille — et il ne
    concerne que les positionnés (42 sur 270 en production) : une cadence
    complète part de maintenant et un dormant de son créneau, ni l'une ni
    l'autre n'a de touche passée à examiner."""
    echeances = _echeances_best_effort(
        entree['lead'], entree['cadence'], entree['depart'], gabarits)
    if not echeances:
        # Gabarit vide ou illisible : la cadence n'est pas « intégralement
        # passée », elle est INCONNUE. Basculer tout un portefeuille au froid
        # sur un référentiel absent serait la pire lecture de ce silence ;
        # l'exécution comptera ces leads en `erreurs`, ce qui est la vérité.
        return
    futures = [(echeance, gabarit.ordre, gabarit)
               for gabarit, echeance in echeances if echeance >= maintenant]
    if futures:
        echeance, _, gabarit = min(futures, key=lambda ligne: ligne[:2])
        entree['prochaine_touche'] = gabarit.libelle or ''
        entree['prochaine_le'] = echeance
        return
    entree.update(code=_PLACEMENT_REPLI_DORMANT[entree['code']],
                  cadence='reveil', positionne=False, devis=None, depart=None)


def _placement_gabarits(company):
    """``cadence -> gabarit`` mémorisé pour la durée d'UN placement.

    Sans cette mémoire, chaque lead relisait (et seedait) sa cadence : 270
    allers-retours pour trois réponses possibles."""
    cache = {}

    def lire(cadence):
        if cadence not in cache:
            try:
                from apps.parametres.models_relance import CadenceRelanceEtape
                cache[cadence] = CadenceRelanceEtape.cadence_pour(
                    company, cadence)
            except Exception:  # noqa: BLE001 — jamais bloquant
                logger.warning('MRY30: gabarit « %s » illisible', cadence,
                               exc_info=True)
                cache[cadence] = []
        return cache[cadence]

    return lire


def _placement_gabarit_reveil(company, gabarits=None):
    """Le PREMIER barreau actif du gabarit « réveil » de la société.

    Trois réponses d'une seule lecture : son ``delai_jours`` (pour remonter le
    départ jusqu'au créneau visé), son ``ordre`` (pour reconnaître les réveils
    DÉJÀ posés, cf. `_placement_occupation_reveils`) et son ``libelle`` (la
    touche que l'aperçu annonce pour un dormant, « Réveil J30 » par défaut).
    ``None`` si le gabarit est illisible — le placement continue alors sur les
    valeurs de repli plutôt que d'échouer en bloc."""
    lire = gabarits or _placement_gabarits(company)
    barreaux = lire('reveil')
    return barreaux[0] if barreaux else None


def _placement_occupation_reveils(company, jour_zero, gabarit):
    """``{jour local: premières touches de réveil DÉJÀ posées}``, à partir de
    ``jour_zero``.

    Sans elle, chaque lot d'application recommencerait la file au premier
    créneau : le lot 2 poserait ses huit réveils SUR ceux du lot 1 — seize
    messages le même matin depuis le même numéro, précisément ce que
    l'étalement existe pour empêcher. Et l'aperçu lancé entre deux lots
    annoncerait des créneaux déjà pris.

    Ne compte que le PREMIER barreau (``ordre``) : c'est lui qu'on étale ; le
    J60 suit mécaniquement."""
    from collections import Counter

    ordre = getattr(gabarit, 'ordre', None)
    if ordre is None:
        return Counter()
    return Counter(
        RelanceEtape.objects.filter(
            company=company, cadence='reveil', ordre=ordre,
            statut=RelanceEtape.Statut.A_FAIRE, due_date__gte=jour_zero,
        ).values_list('due_date', flat=True))


def _etaler_reveils(dormants, company, maintenant, *, gabarit=None):
    """Pose ``creneau`` (et le ``depart`` qui en découle) sur chaque dormant,
    8 par jour ouvré, LES ANCRES LES PLUS RÉCENTES D'ABORD.

    L'ordre n'est pas cosmétique : le dossier dont on a eu des nouvelles la
    semaine dernière a bien plus de chances de répondre que celui qui dort
    depuis huit mois — c'est lui qui doit occuper les premiers créneaux.

    Le premier jour est AUJOURD'HUI si la fenêtre d'appel n'est pas déjà
    close, sinon le prochain jour ouvré : ``prochain_creneau_appel`` répond
    exactement à cette question. Les jours déjà PLEINS (réveils posés par un
    lot précédent) sont sautés, et un jour partiellement occupé reprend au
    créneau suivant : la file se PROLONGE, elle ne recommence jamais.

    N'écrit rien : renvoie les dormants DANS L'ORDRE d'étalement."""
    from apps.notifications.calendar_utils import ajouter_jours_ouvres

    from . import horaires

    if not dormants:
        return []
    if gabarit is None:
        gabarit = _placement_gabarit_reveil(company)
    delai = (getattr(gabarit, 'delai_jours', None)
             or PLACEMENT_REVEIL_DELAI_JOURS)
    # Une cadence « réveil » commence par un MESSAGE WhatsApp : sa fenêtre est
    # celle des messages (08:30), pas celle des appels (09:00) — 07/09/2026.
    base = horaires.prochain_creneau_appel(
        maintenant, company, canal='whatsapp')
    base_locale = base.astimezone(horaires.CASABLANCA)
    jour_zero = base_locale.date()
    if base_locale.time() > PLACEMENT_CRENEAUX[0]:
        # Les créneaux du jour (10 h-12 h 20) sont déjà derrière nous : un
        # placement lancé l'après-midi commence le PROCHAIN jour ouvré, jamais
        # avec des touches « en retard » à la seconde où elles naissent.
        jour_zero = ajouter_jours_ouvres(jour_zero, 1, company)
    occupation = _placement_occupation_reveils(company, jour_zero, gabarit)
    ordonnes = sorted(dormants,
                      key=lambda e: (e['ancre'], e['lead'].pk), reverse=True)
    jour = jour_zero
    for entree in ordonnes:
        while occupation[jour] >= PLACEMENT_REVEILS_PAR_JOUR:
            jour = ajouter_jours_ouvres(jour, 1, company)
        rang = occupation[jour]
        occupation[jour] += 1
        creneau = horaires.prochain_creneau_appel(
            datetime.datetime.combine(
                jour, PLACEMENT_CRENEAUX[rang], tzinfo=horaires.CASABLANCA),
            company, canal='whatsapp')
        entree['creneau'] = creneau
        # La cadence « réveil » place sa première touche à J+`delai` : on
        # remonte donc le départ d'autant pour qu'elle tombe SUR le créneau.
        entree['depart'] = creneau - datetime.timedelta(days=delai)
    return ordonnes


def _placement_touches_creees(lead, cadence, devis=None):
    """Les touches de CETTE cadence, relues triées par échéance."""
    from django.db.models import F
    qs = lead.relance_etapes.filter(cadence=cadence)
    if devis is not None:
        qs = qs.filter(devis=devis)
    return list(qs.order_by(F('due_at').asc(nulls_last=True), 'due_date',
                            'ordre'))


def _placer_cadence_positionnee(entree, *, user, maintenant):
    """Cadence `contact`/`apres_devis` datée depuis l'ancre (ou l'envoi du
    devis), touches déjà échues ANNULÉES (CKP1 — c'est le MOTEUR qui les
    retire, pas un commercial : ``traite_par`` reste NULL).

    Les touches passées sont annulées par un UPDATE direct, jamais par
    ``marquer_etape_relance`` : celui-ci journalise une ligne de chatter par
    touche (dix lignes « touche sautée » sur un dossier qu'on vient à peine de
    reprendre) et, sur la DERNIÈRE, déclencherait ``cloturer_cadence`` — le
    lead partirait au froid étiqueté « injoignable » à la seconde même où on
    l'inscrit dans la cadence.

    Renvoie ``True`` si une touche reste À FAIRE, ``False`` si la cadence est
    intégralement passée. Ce second cas est désormais TRANCHÉ EN AMONT par
    ``_trancher_cadence_positionnee`` (l'aperçu doit annoncer la bascule) : le
    voir ici est une anomalie, que l'appelant compte en ``erreurs``. La remise
    en état reste néanmoins écrite, parce qu'elle doit être exacte le jour où
    elle sert."""
    lead = entree['lead']
    # Photo d'AVANT : de quoi défaire proprement si la cadence s'avère
    # intégralement passée (voir plus bas). Un rappel posé à la main par un
    # commercial ne doit pas disparaître dans l'opération.
    relance_avant = lead.relance_date
    activites_avant = set(lead.activites.values_list('pk', flat=True))

    try:
        etapes = initialiser_plan_relance(
            lead, user, cadence=entree['cadence'], depart=entree['depart'],
            devis=entree['devis'])
    except CadenceActiveConflit as exc:
        raise PlacementImpossible(str(exc))
    if not etapes:
        raise PlacementImpossible(
            f'aucune touche créée (cadence {entree["cadence"]})')
    if not entree['positionne']:
        return True

    passees = [e.pk for e in etapes
               if e.due_at is not None and e.due_at < maintenant]
    if passees:
        RelanceEtape.objects.filter(
            pk__in=passees, statut=RelanceEtape.Statut.A_FAIRE,
        ).update(statut=RelanceEtape.Statut.ANNULEE,
                 note=PLACEMENT_NOTE_PASSEE, traite_par=None,
                 traite_le=maintenant)
    if len(passees) >= len(etapes):
        # Rien ne reste à faire : cette cadence ne relancerait personne. On
        # défait TOUT ce qu'on vient de créer — touches, note « Plan de
        # relance initialisé » (elle annoncerait un plan qui n'existe plus) et
        # `relance_date` — puis l'appelant compte l'anomalie. Sans cette
        # remise en état, le lead gardait une échéance de relance pointant sur
        # une touche supprimée : un rappel fantôme, en retard pour toujours.
        RelanceEtape.objects.filter(pk__in=[e.pk for e in etapes]).delete()
        lead.activites.exclude(pk__in=activites_avant).delete()
        lead.relance_date = relance_avant
        lead.save(update_fields=['relance_date'])
        sync_relance_activity(lead, user)
        return False

    # `initialiser_plan_relance` a pointé `relance_date` sur la PREMIÈRE
    # touche — celle qu'on vient peut-être de sauter. On la recale sur la
    # prochaine réellement à faire, exactement comme `marquer_etape_relance`.
    # ACRM37 — par LE recalage unique (une touche au moins reste ouverte ici).
    _recaler_file(lead, user)
    return True


def _placer_dormant(entree, *, user):
    """Dormance explicite : Froid + étiquette qui dit POURQUOI + cadence de
    réveil posée sur le créneau étalé.

    Froid est un PARKING, pas une perte (même garantie que ``cloturer_cadence``
    MRY11) : aucun motif de perte n'est posé, ``Lead.perdu`` n'est jamais
    touché."""
    lead = entree['lead']
    avancer_stage_lead_vers(lead, user, stages.COLD)
    tag = _PLACEMENT_TAGS.get(entree['code'])
    if tag:
        poser_tag_lead(lead, user, tag)
    try:
        etapes = initialiser_plan_relance(
            lead, user, cadence='reveil', depart=entree['depart'])
    except CadenceActiveConflit as exc:
        raise PlacementImpossible(str(exc))
    if not etapes:
        raise PlacementImpossible('aucune touche de réveil créée')
    if entree['code'] == 'dormant_devis':
        for etape, cle in zip(sorted(etapes, key=lambda e: e.ordre),
                              _PLACEMENT_CLES_REVEIL_DEVIS):
            if etape.template_cle != cle:
                etape.template_cle = cle
                etape.save(update_fields=['template_cle'])
    return True


def _placer_un(entree, *, user, maintenant):
    """Place UN lead, puis journalise la touche qui l'attend."""
    if entree['cadence'] != 'reveil':
        if not _placer_cadence_positionnee(
                entree, user=user, maintenant=maintenant):
            # La DÉCISION a déjà vérifié qu'une touche restait à faire
            # (`_trancher_cadence_positionnee`) : si la matérialisation dit le
            # contraire, c'est une anomalie — comptée, jamais silencieuse.
            raise PlacementImpossible(
                'cadence intégralement passée après décision')
    else:
        _placer_dormant(entree, user=user)

    lead = entree['lead']
    touches = _placement_touches_creees(
        lead, entree['cadence'], devis=entree['devis'])
    a_faire = [e for e in touches if e.statut == RelanceEtape.Statut.A_FAIRE]
    reference = (a_faire or touches or [None])[0]
    # Le libellé est relu sur la touche RÉELLEMENT créée : la décision ne date
    # que les vingt lignes de l'aperçu, et cette note doit nommer la bonne
    # touche pour les 250 autres aussi.
    libelle = (getattr(reference, 'libelle', '') or ''
               or entree['prochaine_touche'])
    # FG28/MRY19 — note SYSTÈME (``user=None``), JAMAIS l'utilisateur qui a
    # lancé le placement. Le récepteur QJ7 (`_avancer_stage_on_contact_
    # activity`) fait avancer NEW → CONTACTED et stampe `first_contacted_at`
    # sur toute note portant un `user` : posée avec l'acteur, cette ligne
    # aurait déclaré « contactés » les leads NEW qu'on vient justement
    # d'inscrire dans la cadence de PREMIER contact — 270 dossiers marqués
    # joints sans qu'un humain ait décroché, et le KPI de premier contact
    # faussé du même coup. Même choix, trois lignes plus haut, que la note de
    # `initialiser_plan_relance`. QUI a lancé le placement reste tracé : par
    # les lignes de modification (étape, étiquette), qui portent l'acteur.
    LeadActivity.objects.create(
        company=lead.company, lead=lead, user=None,
        kind=LeadActivity.Kind.NOTE,
        body=f'Placé dans la cadence {entree["cadence"]} à la touche '
             f'« {libelle} » ({PLACEMENT_MARQUEUR}).')
    return True


def _placement_ordre(decisions, company, maintenant, *, gabarit=None):
    """L'ordre de traitement d'un lot : les cadences vivantes (les dossiers
    les plus RÉCENTS d'abord), puis les dormants dans leur ordre d'étalement.

    L'étalement est calculé ICI, pour tout le monde et dans les deux modes :
    c'est lui qui donne son créneau à chaque dormant, donc `reveils_jusqu_au`
    et la date affichée par l'aperçu. Borner le lot APRÈS cet ordre garantit
    que le lot 1 prend bien les premiers créneaux et le lot 2 les suivants."""
    dormants = _etaler_reveils(
        [e for e in decisions if e['cadence'] == 'reveil'], company,
        maintenant, gabarit=gabarit)
    vivants = sorted([e for e in decisions if e['cadence'] != 'reveil'],
                     key=lambda e: (e['jours'], e['lead'].pk))
    return vivants + dormants


def _dater_apercu(decisions, maintenant, *, gabarits, gabarit_reveil):
    """Donne sa touche et sa date à CHACUNE des vingt lignes de l'aperçu —
    et à elles seules.

    C'est le cœur de la correction du 07/09 : dater les 270 décisions
    revenait à matérialiser 270 cadences (le dry-run en transaction annulée),
    alors que le rapport n'en montre que vingt. Les positionnées sont déjà
    datées par la décision (elle devait, de toute façon, savoir s'il leur
    restait une touche) ; restent les cadences complètes, calculées ici, et
    les dormants, dont la date EST leur créneau étalé."""
    for entree in sorted(
            decisions,
            key=lambda e: (e['jours'], e['lead'].pk))[:PLACEMENT_APERCU_MAX]:
        if entree['prochaine_le'] is not None:
            continue
        if entree['cadence'] == 'reveil':
            entree['prochaine_touche'] = (
                getattr(gabarit_reveil, 'libelle', '') or '')
            entree['prochaine_le'] = entree['creneau']
            continue
        echeances = _echeances_best_effort(
            entree['lead'], entree['cadence'], entree['depart'], gabarits)
        futures = [(echeance, gabarit.ordre, gabarit)
                   for gabarit, echeance in echeances
                   if echeance >= maintenant]
        if futures:
            echeance, _, gabarit = min(futures, key=lambda ligne: ligne[:2])
            entree['prochaine_touche'] = gabarit.libelle or ''
            entree['prochaine_le'] = echeance


def _executer_placements(entrees, *, user, maintenant):
    """Exécute les décisions du LOT, lead par lead, best-effort.

    ``entrees`` arrive déjà ordonné et borné (`_placement_ordre`, `limite`) :
    cette fonction ne décide plus rien — elle pose ce que la décision a
    tranché. Renvoie ``(applique, erreurs)``."""
    from django.db import transaction

    applique = erreurs = 0
    for entree in entrees:
        try:
            with transaction.atomic():
                _placer_un(entree, user=user, maintenant=maintenant)
        except Exception:  # noqa: BLE001 — un dossier bancal n'arrête rien
            logger.warning(
                'MRY30: placement échoué (lead #%s, code %s)',
                entree['lead'].pk, entree['code'], exc_info=True)
            erreurs += 1
            continue
        applique += 1
    return applique, erreurs


def _rapport_placement(decisions, ignores, total, *, apply, applique, erreurs,
                       restants):
    """Le rapport, forme ``contract_samples/placement_anciens_leads.json``."""
    from . import horaires

    par_code = {}
    for entree in decisions:
        par_code[entree['code']] = par_code.get(entree['code'], 0) + 1
    par_etape = [
        {'code': code, 'libelle': libelle, 'cadence': cadence,
         'nombre': par_code[code]}
        for code, libelle, cadence in PLACEMENT_DECISIONS if code in par_code
    ]
    apercu = [
        {
            'lead': entree['lead'].pk,
            'nom': entree['nom'],
            'stage_libelle': entree['stage_libelle'],
            'source': entree['source'],
            'ancre': entree['ancre'].astimezone(
                horaires.CASABLANCA).date().isoformat(),
            'jours': entree['jours'],
            'code': entree['code'],
            'cadence': entree['cadence'],
            'prochaine_touche': entree['prochaine_touche'],
            'prochaine_le': (
                entree['prochaine_le'].astimezone(
                    horaires.CASABLANCA).isoformat()
                if entree['prochaine_le'] is not None else None),
        }
        for entree in sorted(
            decisions,
            key=lambda e: (e['jours'], e['lead'].pk))[:PLACEMENT_APERCU_MAX]
    ]
    creneaux = [e['creneau'] for e in decisions if e['creneau'] is not None]
    return {
        'apply': bool(apply),
        'total_candidats': total,
        'a_placer': len(decisions),
        'ignores': ignores,
        'par_etape': par_etape,
        'apercu': apercu,
        'reveils_jusqu_au': (
            max(creneaux).astimezone(horaires.CASABLANCA).date().isoformat()
            if creneaux else None),
        'applique': applique,
        'erreurs': erreurs,
        'restants': restants,
    }


def _placement_limite(limite):
    """``limite`` bornée à [1, PLACEMENT_LOT_MAX] (défaut PLACEMENT_LOT_DEFAUT).

    La vue REFUSE une valeur hors bornes (400) : ce garde-fou-ci protège les
    appelants internes (commande, tâche) d'un lot de 100 000 leads."""
    if limite is None:
        return PLACEMENT_LOT_DEFAUT
    return max(1, min(int(limite), PLACEMENT_LOT_MAX))


def placer_anciens_leads(company, user, *, apply=False, maintenant=None,
                         limite=None, leads_en_portee=None):
    """Enveloppe de `_placer_anciens_leads_sans_cache` sous `horaires.cache_local()` :
    profil société et jours ouvrés lus UNE fois pour toute l'opération. Sans
    cela, dater les touches de 272 leads coûtait ~7 000 requêtes et 24 s en
    production (07/09/2026), au-delà du délai du navigateur."""
    from . import horaires
    with horaires.cache_local():
        return _placer_anciens_leads_sans_cache(
            company, user, apply=apply, maintenant=maintenant, limite=limite,
            leads_en_portee=leads_en_portee)


def _placer_anciens_leads_sans_cache(company, user, *, apply=False,
                                     maintenant=None, limite=None,
                                     leads_en_portee=None):
    """MRY30 — Place les anciens leads d'une société dans les cadences du
    moteur de relances. Rapport = ``contract_samples/placement_anciens_leads``.

    ``apply=False`` (défaut) est un CALCUL PUR : aucune écriture, aucune
    transaction, aucun rollback. L'aperçu partage le CALCUL de l'application
    — ``calculer_echeances_cadence`` pour les dates, ``_etaler_reveils`` pour
    les créneaux, ``_decider_placements`` pour les codes — et c'est ce partage
    qui le rend fidèle, comme l'était l'ancienne exécution en transaction
    annulée. Celle-ci matérialisait en revanche les touches des 277 candidats
    pour les jeter aussitôt : plus de 20 s, donc un 499 (le navigateur
    abandonne à 20 s) et un écran qui n'affichait jamais rien — l'incident du
    07/09/2026. Les vingt lignes de l'aperçu sont les seules datées.

    ``apply=True`` place AU PLUS ``limite`` leads (défaut 40), dans l'ordre
    d'`_placement_ordre` : les cadences vivantes des dossiers les plus récents
    d'abord, puis les dormants dans leur ordre d'étalement. Chaque lead est
    posé sous son propre ``transaction.atomic`` : son échec est journalisé et
    compté dans ``erreurs``, il n'annule jamais les autres. La réponse porte
    ``restants`` ; l'écran (et la commande) rappellent jusqu'à ce qu'il tombe
    à zéro. IDEMPOTENT : les leads du lot précédent reviennent en
    ``deja_en_cadence``, et l'étalement REPREND à la suite des réveils déjà
    posés — jamais au premier créneau du jour.

    ``par_etape``, ``apercu`` et ``reveils_jusqu_au`` décrivent l'ensemble
    RESTANT au DÉBUT de l'appel : ce qu'un aperçu montrerait à cette seconde,
    dans les deux modes."""
    maintenant = maintenant or timezone.now()
    gabarits = _placement_gabarits(company)
    decisions, ignores, total = _decider_placements(
        company, maintenant, gabarits, leads_en_portee=leads_en_portee)
    # Lu SEULEMENT s'il y a un dormant : `cadence_pour` seede la cadence
    # absente, et une société sans aucun dormant n'a aucune raison de voir
    # naître un gabarit de réveil au passage d'un aperçu.
    gabarit_reveil = (
        _placement_gabarit_reveil(company, gabarits)
        if any(e['cadence'] == 'reveil' for e in decisions) else None)
    ordre = _placement_ordre(decisions, company, maintenant,
                             gabarit=gabarit_reveil)
    _dater_apercu(decisions, maintenant, gabarits=gabarits,
                  gabarit_reveil=gabarit_reveil)
    rapport = _rapport_placement(
        decisions, ignores, total, apply=apply, applique=0, erreurs=0,
        restants=len(decisions))
    if not apply:
        return rapport
    applique, erreurs = _executer_placements(
        ordre[:_placement_limite(limite)], user=user, maintenant=maintenant)
    rapport['applique'] = applique
    rapport['erreurs'] = erreurs
    rapport['restants'] = max(0, len(decisions) - applique - erreurs)
    return rapport


# ── VISITE-CADENCE — LE SUIVI COMMERCIAL RÉAGIT À LA VISITE ──────────────────
#
# Ordre fondateur du 15/09/2026. La visite technique se place APRÈS l'envoi du
# devis, comme outil de closing. Trois conséquences, et elles vivent ICI (pas
# dans les récepteurs, qui restent minces et se contentent d'appeler) :
#
#   * quand un RENDEZ-VOUS est pris, les messages génériques de relance se
#     TAISENT jusqu'après la visite — continuer à demander « le PDF s'ouvre
#     bien ? » à quelqu'un qui reçoit le technicien jeudi est le genre de
#     faute qui décrédibilise tout le suivi — et deux gestes utiles les
#     remplacent en attendant ;
#
#     AMENDEMENT FONDATEUR (15/09/2026) — ils se TAISENT, ils ne MEURENT PAS.
#     La première écriture de ce lot ANNULAIT la cadence après-devis : le lead
#     perdait sa place dans le protocole, et une visite qui n'aboutit pas
#     laissait un dossier sans suivi (ou, pire, exigeait un REDÉMARRAGE de
#     cadence — un client reprenant le plan au barreau 1 après avoir déjà reçu
#     neuf messages). On DÉCALE désormais : la touche pendante, tout ce qui la
#     suit, ET l'ancre de la cadence glissent jusqu'après le débrief. Le lead
#     garde sa POSITION EXACTE (même ordre, même libellé, même reste de plan) ;
#     si la visite ne donne rien, le suivi reprend tout seul là où il en était.
#     Aucun `initialiser_plan_relance` n'est appelé sur un lead qui a déjà des
#     étapes après-devis : il n'y a JAMAIS de restart.
#   * quand le technicien repart, le RESPONSABLE doit rappeler sous 24-48 h,
#     tant que la visite est fraîche ;
#   * le TEXTE LIBRE du terrain entre dans l'historique du lead : c'est
#     souvent la seule trace de ce que le client a dit sur place.
#
# Aucune de ces fonctions ne touche ``Lead.stage`` : le statut d'une visite est
# un layer DOCUMENT, jamais une étape de funnel (``STAGES.py`` intact).


# ── VT1 — CHATTER AUTOMATIQUE DE LA VISITE TECHNIQUE TERRAIN ─────────────────
#
# Le chatter du lead (``LeadActivity``) est le journal COMMUN de tout ce qui
# arrive à un lead : la visite technique y écrit ses quatre moments — création,
# terminaison, feu vert, renvoi — plutôt que d'ouvrir un second historique.
# L'auteur et la société viennent TOUJOURS du serveur (jamais du corps de
# requête), comme le reste du chatter.


# ── AGR522 — DOSSIER DE SUBVENTION FDA : LE RAPPEL DES 3 MOIS ───────────────
#
# Guide FDA 2024 (p.22-23, tableau « Délais ») : « Demande de subvention —
# 3 mois à compter de la date de l'approbation préalable », après la
# RÉALISATION. Au passage à « accordé », une étape MANUELLE datée est posée
# pour le lendemain (filet hors gabarit — jamais une touche de cadence,
# CAD124). Ce délai n'est JAMAIS écrit au client.


# ── NTDATA18 — FUSION SUPERVISÉE DE CLIENTS ─────────────────────────────────
#
# Sur le modèle de `merge_leads` ci-dessus, mais pour `Client` : le détecteur
# (`dataquality.services.doublons_clients`) PROPOSE, un humain DÉCIDE, et cette
# fonction exécute. Jamais de fusion automatique.
#
# TROIS GARANTIES DURES :
#
# 1. AUCUNE SUPPRESSION. Le doublon n'est jamais effacé : il est NEUTRALISÉ.
#    `Client` ne porte pas (encore) de drapeau d'archivage — ajouter une
#    colonne supposerait une migration `crm`, hors du périmètre de cette
#    tâche. On utilise donc le mécanisme EXISTANT prévu pour ça :
#    `avertissement_bloquant` (une garde serveur refuse dès lors l'acceptation
#    et la facturation d'un devis pour ce client, patron XFAC28) + un
#    avertissement lisible, + un marqueur `custom_data['fusionne_dans']` qui
#    trace la cible et la date. La fiche reste consultable, son historique
#    intact, et la fusion est intégralement réversible à la main.
#
# 2. AUCUN ORPHELIN. Tout ce qui pointait le doublon pointe le survivant —
#    non pas une liste de quatre modèles écrite à la main (le dépôt compte
#    plus de trente FK vers `Client`), mais le parcours des relations inverses
#    déclarées par Django (`core.merge.repointer_relations`, la MÊME mécanique
#    que la fusion fournisseur/produit de `stock` — jamais une seconde
#    implémentation). Chaque relation est repointée dans son PROPRE point de
#    sauvegarde : une contrainte d'unicité qui refuse (le survivant a déjà sa
#    limite de crédit, par exemple) annule CETTE relation seule et le rapport
#    la NOMME, au lieu de faire échouer toute la fusion en silence.
#
# 3. AUCUN IMPORT D'APP ÉTRANGÈRE. Le parcours passe par l'API `_meta` de
#    Django, donc `crm` n'importe ni `ventes`, ni `facturation`, ni
#    `installations`, ni `sav`.


# ── CAD-G ── CAD74 — réveil saisonnier (`reveil_b`) ────────────────────────
# Le câblage vit dans `apps/crm/cadence_reveil_saison.py` (module autonome —
# ce fichier est partagé par des dizaines de tâches). Ces deux passe-plats
# sont le point d'entrée attendu par les appelants de `services` ; ils ne
# dupliquent aucune logique. Crochet planifié : AUCUN aujourd'hui — la pose
# se déclenche par un appel explicite, jamais à l'insu de la commerciale.


# ── CAD-I ── CAD90 — le registre couvre TOUTES les créations de lead ────────
#
# Audit L3 du 21/09/2026. ``enregistrer_consentement_lead`` n'était appelée
# que depuis le webhook du formulaire du site : un lead créé à la main par la
# commerciale (appel entrant, WhatsApp reçu au salon), un lead Meta Lead Ads
# ou un lead venu d'un document n'écrivaient RIEN au registre
# ``core.ConsentRecord`` — alors que la cadence démarre quand même et que sa
# touche n°1 est un WhatsApp, le canal le plus encadré.
#
# CE QUE ``granted`` VEUT DIRE ICI, ET CE QU'IL NE VEUT PAS DIRE. Il dit
# seulement si un CONSENTEMENT A ÉTÉ RECUEILLI — jamais si le traitement est
# licite. Sur ces chemins, aucune case n'a été cochée par la personne : la
# licéité vient de la BASE LÉGALE, tracée dans ``source``. Écrire
# ``granted=True`` pour faire joli fabriquerait une preuve fausse, ce qui est
# pire qu'une preuve absente (même raison que ``ip_confirmation`` laissée
# vide par l'intake web).
#
# LES DEUX BASES, SUR TEXTE PRIMAIRE (extraction du round 2 de l'audit, PDF
# adala.justice.gov.ma) :
#   * données NON collectées auprès de la personne (Meta, import, document) —
#     loi 09-08 art. 5 §3, avec l'information due « par tous moyens » de
#     l'art. 34 du décret 2-09-165 ;
#   * la personne a elle-même SOLLICITÉ le contact (appel entrant, message
#     WhatsApp, demande au salon) — relation précontractuelle à sa demande,
#     loi 09-08 art. 5. Le CNDP distingue les deux, le registre aussi.


# ── CAD-K ── CAD129 — « rappelez-moi » entre dans la FILE, pas dans la cloche ─
#
# Audit L3 du 21/09/2026. Un clic « rappelez-moi » écrivait une note, notifiait
# le responsable et son supérieur, et posait la préférence « joignable par
# téléphone » — mais ne créait AUCUNE touche. Si la notification est noyée dans
# la cloche, la demande la plus forte qu'un prospect puisse faire disparaît.
#
# LA RÈGLE : décaler, jamais redémarrer. Quand le lead a déjà un plan en cours,
# on RAMÈNE sa prochaine touche au prochain créneau d'appel et tout le reste du
# plan glisse du MÊME delta (``reporter_prochaine_touche`` le fait déjà, ancre
# comprise) : le lead garde sa position dans le protocole, on ne fabrique pas un
# second plan concurrent. Quand il n'a plus aucune touche ouverte (cadence
# terminée ou arrêtée), on pose UNE touche — une seule, jamais un plan.


#: APAR51 — les issues de ``appliquer_champ_automatique``.
CHAMP_AUTO_APPLIQUE = 'applique'
CHAMP_AUTO_INCHANGE = 'inchange'
CHAMP_AUTO_INVALIDE = 'invalide'
CHAMP_AUTO_CADENCE = 'cadence_active'


def appliquer_champ_automatique(lead, champ, valeur, user=None):
    """APAR51 (C-APAR-032) — LA porte d'écriture d'un champ de lead par une
    AUTOMATISATION (règle SET_FIELD, action serveur, assignation) : la même
    discipline que le geste manuel.

    * la valeur est VALIDÉE par le champ du modèle (choix, longueur, type) —
      hors choix ⇒ ``(CHAMP_AUTO_INVALIDE, motif)``, rien n'est écrit ;
    * ``relance_date`` sur un lead à CADENCE ACTIVE ⇒ refus CAD49
      (``(CHAMP_AUTO_CADENCE, MOTIF_BULK_CADENCE_ACTIVE)``) : la date vient
      de la prochaine touche du plan ;
    * une valeur égale ⇒ ``(CHAMP_AUTO_INCHANGE, '')`` ;
    * sinon le champ est écrit et UNE ligne MODIFICATION (ancien → nouveau)
      entre au chatter, l'acteur étant ``user`` (la règle).

    ``champ='owner'`` accepte un utilisateur (ou son identifiant) de la
    société du lead. Rend ``(issue, motif)``."""
    from django.core.exceptions import ValidationError

    from . import activity as _activity

    try:
        champ_modele = Lead._meta.get_field(champ)
    except Exception:  # noqa: BLE001
        return CHAMP_AUTO_INVALIDE, f'Champ « {champ} » inconnu.'
    if champ == 'owner':
        from django.contrib.auth import get_user_model
        pk = getattr(valeur, 'pk', valeur)
        cible = get_user_model().objects.filter(
            pk=pk, company=lead.company).first() if pk else None
        if cible is None:
            return CHAMP_AUTO_INVALIDE, 'Utilisateur cible inconnu.'
        ancien = lead.owner
        if ancien is not None and ancien.pk == cible.pk:
            return CHAMP_AUTO_INCHANGE, ''
        lead.owner = cible
        lead.save(update_fields=['owner'])
        LeadActivity.objects.create(
            company=lead.company, lead=lead, user=user,
            kind=LeadActivity.Kind.MODIFICATION, field='owner',
            field_label=_activity.TRACKED_FIELDS.get('owner', 'owner'),
            old_value=_activity._display(lead, 'owner', ancien),
            new_value=_activity._display(lead, 'owner', cible))
        return CHAMP_AUTO_APPLIQUE, ''
    try:
        propre = champ_modele.clean(valeur, lead)
    except ValidationError as exc:
        hors_choix = bool(getattr(champ_modele, 'choices', None))
        detail = '; '.join(exc.messages)
        return CHAMP_AUTO_INVALIDE, (
            f'Valeur hors choix pour « {champ} » : {valeur!r}.' if hors_choix
            else f'Valeur invalide pour « {champ} » : {detail}')
    if champ == 'relance_date' and leads_avec_cadence_active(
            lead.company, [lead.pk]):
        return CHAMP_AUTO_CADENCE, MOTIF_BULK_CADENCE_ACTIVE
    ancien = getattr(lead, champ, None)
    if ancien == propre:
        return CHAMP_AUTO_INCHANGE, ''
    setattr(lead, champ, propre)
    lead.save(update_fields=[champ])
    LeadActivity.objects.create(
        company=lead.company, lead=lead, user=user,
        kind=LeadActivity.Kind.MODIFICATION, field=champ,
        field_label=_activity.TRACKED_FIELDS.get(champ, champ),
        old_value=_activity._display(lead, champ, ancien),
        new_value=_activity._display(lead, champ, propre))
    if champ == 'relance_date':
        sync_relance_activity(lead, user)
    return CHAMP_AUTO_APPLIQUE, ''


# ── CAD-A ── RÉPONSES DE TOUCHE : ce que le client DIT décide de la suite ─────
#
# Audit L3 du 21/09/2026. Les réponses offertes sur une touche se limitaient
# aux issues de ``LeadActivity.OUTCOMES`` (joint / non joint / à rappeler /
# refus / intéressé / visite acceptée) : « arrêtez de m'appeler », « plus
# tard », « c'est une question de prix », « refaites-moi le devis », « on
# décide en famille » n'avaient AUCUN bouton, et la commerciale choisissait
# l'issue la moins fausse — dont la suite automatique était, elle, fausse.
#
# LA RÈGLE. Une RÉPONSE est une clé connue du SERVEUR, jamais une nouvelle
# valeur d'énumération : elle se traduit en une issue EXISTANTE (aucune
# migration), une note typée (la phrase du client, telle qu'elle est comptée
# dans le chatter) et UN effet — celui que le client a demandé. L'écran
# n'envoie que la clé ; l'issue est dérivée ICI, et nulle part ailleurs.


# ── CAD-A ── CAD7 — « Question de prix — veut négocier » ────────────────────


# ── CAD158 — « votre facture, c'est pour un mois ou pour deux ? » ───────────
#
# Le moteur (`apps/ventes/etude_horaire.py`, inversion au barème) lit
# `facture_hiver` comme un montant MENSUEL : un client qui donne le montant de
# sa facture BIMESTRIELLE faussait tout l'aval (niveau de facture, économie).
# Décision fondateur du 21/09/2026 (Q24) : le montant est ramené au mois AU
# MOMENT DE LA SAISIE, et aucun champ « périodicité » n'est stocké.

def refus_periodicite_facture(periodicite):
    """CAD158 — le message (FR, qui NOMME le champ) si ``periodicite`` n'est
    pas une période connue, sinon ``None``."""
    if periodicite in Lead.PERIODICITES_FACTURE:
        return None
    choix = ' ou '.join(f'« {cle} »' for cle in Lead.PERIODICITES_FACTURE)
    return (f'« Période de la facture » : {choix} attendu '
            f'(reçu « {periodicite} »).')


def facture_au_mois(montant, periodicite):
    """CAD158 — le montant MENSUEL d'une facture déclarée sur ``periodicite``
    (``mensuelle`` : inchangé ; ``bimestrielle`` : divisé par deux), arrondi
    au centime selon la convention monétaire (moitié vers le haut).

    ``None`` reste ``None`` : aucun montant n'est jamais inventé."""
    from decimal import Decimal

    from core.money import quantize_mad

    if montant is None or montant == '':
        return None
    mois = Lead.PERIODICITES_FACTURE[periodicite]
    return quantize_mad(Decimal(str(montant)) / Decimal(mois))


# ── CAD164 — le LOCATAIRE : demander le propriétaire, sinon « Perdu — Locataire »
#
# Décision fondateur du 21/09/2026 : on demande le propriétaire ; s'il est
# joignable, on crée SA fiche, LIÉE à celle du locataire (le locataire reste le
# prescripteur : son prénom passe par la variable `{prescripteur}` du texte
# d'origine « recommandation », CAD127 — jamais en dur) ; sinon on clôt avec
# le motif EXISTANT « Locataire ». Aucune valeur d'énumération neuve : le motif
# existe (`MotifPerte`), le canal « Référence » aussi, et le lien entre les deux
# fiches est une NOTE d'historique de chaque côté — jamais une fusion
# automatique (conduite `FLUX_LOCATAIRE` du script d'appel).

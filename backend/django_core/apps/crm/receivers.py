"""Récepteurs d'événements métier (M6).

Abonne le CRM aux événements du cœur métier exposés par ``core.events``, pour
réagir à des changements d'état déclenchés par d'autres apps (ex. ``ventes``)
sans que celles-ci importent le CRM. Câblé au démarrage par ``CrmConfig.ready``.

ARC37 — s'abonne aussi à ``ticket_resolu`` (``sav`` devient émetteur du bus) :
pose une note chatter ARC8 (``records.services.log_note``) sur le
``crm.Client`` lié au ticket, sans jamais importer ``apps.sav``.
"""
import logging

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from core.events import (
    appointment_effectue,
    devis_acceptation_annulee,
    devis_accepted,
    devis_refused,
    devis_sent,
    facture_emise,
    layout_finalise,
    lead_created,
    lead_stage_changed,
    salle_vente_signal_interet,
    ticket_resolu,
    visite_planifiee,
    visite_terminee,
    visite_validee,
)

from . import receivers_cadence, receivers_clients
from .models import (
    Appointment,
    Lead,
    LeadActivity,
)
from .services import arreter_cadence, ISSUES_CLIENT_JOINT
from .fiche_funnel import (
    _CONTACT_KINDS,
    avancer_stage_new_vers_contacted,
    avancer_stage_sur_reponse_devis,
    avancer_stage_pour_devis,
    signaler_mismatch_signe_sur_refus,
)
from .cadence_reperes import est_note_de_report, est_note_de_touche_sautee
from .leads_premier_contact import marquer_premier_contact

logger = logging.getLogger(__name__)


def _point_de_sauvegarde(fn):
    """ADEV54 — un abonné BEST-EFFORT d'un événement devis tourne dans son
    PROPRE point de sauvegarde (``transaction.atomic()``) : une erreur base y
    est annulée seule et journalisée, jamais propagée à la transaction de
    l'émetteur (la signature reste enregistrée, les autres abonnés tournent)."""
    import functools

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        from django.db import transaction
        try:
            with transaction.atomic():
                return fn(*args, **kwargs)
        except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
            logger.warning('ADEV54 : abonné %s en échec (isolé)',
                           fn.__name__, exc_info=True)
            return None
    return wrapper


def _lever_perdu_sur_signature(devis, ancien_statut, user):
    """ADEV63 — lève ``perdu`` quand le devis du lead vient d'être accepté.

    N'agit que sur la transition vers « accepté » d'un devis qui porte un
    lead perdu ; un objet devis minimal (sans lead) est ignoré. Écrit UNE
    entrée de chatter « relevé de Perdu : devis signé <référence> »."""
    if getattr(devis, 'statut', None) == ancien_statut:
        return
    lead = getattr(devis, 'lead', None)
    if lead is None or not lead.perdu:
        return
    lead.perdu = False
    lead.save(update_fields=['perdu'])
    LeadActivity.objects.create(
        company=lead.company, lead=lead, user=user,
        kind=LeadActivity.Kind.MODIFICATION,
        field='perdu', field_label='Perdu',
        old_value='Oui', new_value='Non',
        body=f"relevé de Perdu : devis signé {devis.reference}")


@receiver(devis_accepted, dispatch_uid="crm_advance_stage_on_devis_accepted")
def _avancer_stage_on_devis_accepted(sender, devis, user, ancien_statut,
                                     **kwargs):
    """À l'acceptation d'un devis, avance l'étape du lead (→ SIGNED).

    Remplace, à l'identique, l'appel direct ``ventes → crm.services`` qui était
    fait au site d'acceptation : même règle (ne recule jamais, ignore les leads
    perdus), désormais déclenchée par l'événement ``devis_accepted``.
    """
    # ADEV63 (D-ADEV-5 = (a)) — la signature d'un devis dont le lead est
    # PERDU lève « Perdu » AVANT l'avancée d'étape (qui ignore les perdus) :
    # le lead passe à Signé, avec une entrée de chatter.
    _lever_perdu_sur_signature(devis, ancien_statut, user)
    avancer_stage_pour_devis(devis, ancien_statut, devis.statut, user)


@receiver(devis_accepted,
          dispatch_uid="crm_stop_relance_on_devis_accepted")
def _relais_arreter_cadence_on_devis_accepted(**kwargs):
    return receivers_cadence._arreter_cadence_on_devis_accepted(**kwargs)


@receiver(devis_accepted, dispatch_uid="crm_deal_commission_on_devis_accepted")
@_point_de_sauvegarde
def _relais_calculer_commission_deal_on_devis_accepted(**kwargs):
    return receivers_clients._calculer_commission_deal_on_devis_accepted(**kwargs)
    # ALEA3 (D-ALEA-3) — plus aucune émission de ``deal_commission_due`` : le
    # signal n'avait AUCUN abonné (le module compta est parqué). Le comptable
    # lit les commissions dues par ``deals-enregistres/a-payer/`` (inchangé).
    # QJR560 : un recalcul sur révision (V2 d’un devis signé) reste une mise
    # à jour du montant, jamais une seconde commission.


@receiver(devis_acceptation_annulee,
          dispatch_uid="crm_defaire_acceptation_on_acceptation_annulee")
def _defaire_acceptation_on_acceptation_annulee(sender, devis, user,
                                                **kwargs):
    """Décision fondateur (08/10/2026) — l'acceptation du devis est annulée
    (le lead sort de « Signé » par une action utilisateur). Le CRM défait SES
    effets d'acceptation, dans la transaction de dés-acceptation (aucun
    filet : une erreur annule tout) :

    * NTCRM22 — la commission du deal passée « À payer » par CETTE vente
      revient « Approuvé », montant dû effacé (aucun état « payé » n'existe :
      rien à bloquer) — seulement si le lead n'a plus aucun devis accepté ;
    * QX35/CRX34 — le parrainage passé « Converti » revient « En attente »
      quand le filleul n'a plus aucun devis accepté (« Récompense versée »
      n'est jamais touchée : c'est un geste humain déjà accompli) ;
    * note au chatter du lead (qui, quel devis, quelle option). Les cadences
      arrêtées à la signature (MRY9) ne sont PAS relancées automatiquement :
      la note le dit, l'humain replanifie.

    Le lien de parrainage CRX38 (une notification déjà partie) et
    l'avancement d'étape (le lead sort déjà de « Signé ») n'ont rien à
    défaire."""
    from apps.ventes.selectors import devis_acceptes_actifs

    from .models import DealEnregistre, Parrainage

    company = getattr(devis, 'company', None)
    if company is None:
        return
    lead_id = getattr(devis, 'lead_id', None)
    client_id = getattr(devis, 'client_id', None)

    if lead_id and not devis_acceptes_actifs(
            company, lead_id=lead_id, exclure_id=devis.pk):
        (DealEnregistre.objects
         .filter(company=company, lead_id=lead_id,
                 statut=DealEnregistre.Statut.A_PAYER)
         .update(statut=DealEnregistre.Statut.APPROUVE,
                 montant_commission_du=None))

    from django.db.models import Q
    appariement = Q(pk__in=[])
    if lead_id:
        appariement |= Q(filleul_lead_id=lead_id)
    if client_id:
        appariement |= Q(filleul_client_id=client_id)
    for parrainage in Parrainage.objects.filter(
            appariement, company=company,
            statut=Parrainage.Statut.CONVERTI):
        encore = devis_acceptes_actifs(
            company, lead_id=parrainage.filleul_lead_id,
            exclure_id=devis.pk) if parrainage.filleul_lead_id else []
        if not encore and parrainage.filleul_client_id:
            encore = devis_acceptes_actifs(
                company, client_id=parrainage.filleul_client_id,
                exclure_id=devis.pk)
        if encore:
            continue
        parrainage.statut = Parrainage.Statut.EN_ATTENTE
        parrainage.save(update_fields=['statut'])

    if lead_id:
        lead = Lead.objects.filter(pk=lead_id, company=company).first()
        if lead is not None:
            from . import activity as crm_activity
            qui = getattr(user, 'username', None) or 'le système'
            option = kwargs.get('option_acceptee') or ''
            crm_activity.log_note(
                lead, user,
                f"Acceptation du devis {devis.reference} annulée par {qui}"
                + (f' (option {option})' if option else '')
                + ' — le devis repasse « Envoyé » ; ce que la signature avait '
                'créé automatiquement (chantier, commission, contrat) est '
                'défait. La preuve de signature du client est conservée. Les '
                'relances arrêtées à la signature ne reprennent pas seules : '
                'replanifiez si besoin.')


@receiver(devis_sent, dispatch_uid="crm_plan_apres_devis_on_devis_sent")
@_point_de_sauvegarde
def _relais_planifier_apres_devis_on_devis_sent(**kwargs):
    return receivers_cadence._planifier_apres_devis_on_devis_sent(**kwargs)


@receiver(devis_refused, dispatch_uid="crm_stop_apres_devis_on_devis_refused")
@_point_de_sauvegarde
def _relais_arreter_apres_devis_on_devis_refused(**kwargs):
    return receivers_cadence._arreter_apres_devis_on_devis_refused(**kwargs)


@receiver(devis_sent, dispatch_uid="crm_advance_stage_on_devis_sent")
def _avancer_stage_on_devis_sent(sender, devis, user, ancien_statut,
                                 **kwargs):
    """À l'ENVOI d'un devis (U4), avance l'étape du lead (→ QUOTE_SENT).

    Même câblage que ``devis_accepted`` : ``avancer_stage_pour_devis`` ne recule
    jamais le funnel et ignore les leads perdus, donc l'avance vers QUOTE_SENT
    est sûre et idempotente (un lead déjà ≥ QUOTE_SENT ne bouge pas).
    """
    avancer_stage_pour_devis(devis, ancien_statut, devis.statut, user)


@receiver(layout_finalise, dispatch_uid="crm_note_chatter_on_layout_finalise")
def _noter_conception_on_layout_finalise(sender, devis, user=None, **kwargs):
    """PV79 — pose une note au chatter du lead quand la toiture est finalisée.

    « Conception 3D finalisée — X kWc » : la commerciale voit dans
    l'historique du lead que la toiture a été dessinée (ou redessinée), sans
    avoir à ouvrir le devis. Même câblage que ``devis_sent`` — c'est le BUS qui
    porte l'information, ``ventes`` n'importe jamais ``crm``.

    No-op quand le devis n'a pas de lead (un devis client direct n'a pas de
    chatter de lead à alimenter). La puissance est lue par le SÉLECTEUR
    ``ventes`` (PV78) : jamais un import de ses modèles ; absente, la note se
    contente de dire que la conception est finalisée — jamais un « 0 kWc »
    fabriqué.
    """
    if not getattr(devis, 'lead_id', None):
        return
    from .models import Lead
    lead = Lead.objects.filter(
        pk=devis.lead_id, company_id=getattr(devis, 'company_id', None)).first()
    if lead is None:
        return

    kwc = None
    try:
        from .selectors import conception_3d_du_lead
        kwc = (conception_3d_du_lead(lead) or {}).get('kwc')
    except Exception:  # noqa: BLE001 — une puissance illisible ne bloque rien
        kwc = None
    if kwc:
        corps = ('Conception 3D finalisée — %s kWc'
                 % ('%.2f' % float(kwc)).rstrip('0').rstrip('.').replace(
                     '.', ','))
    else:
        corps = 'Conception 3D finalisée'

    LeadActivity.objects.create(
        company=lead.company, lead=lead, kind=LeadActivity.Kind.NOTE,
        body=corps, user=user)


@receiver(devis_refused, dispatch_uid="crm_mark_lead_perdu_on_devis_refused")
def _marquer_lead_perdu_on_devis_refused(sender, devis, user, motif_refus,
                                         **kwargs):
    """FG44 — au refus d'un devis (optionnel), marque le lead perdu (perdu=True).

    Ne s'active que si le devis a un lead associé et que ``marquer_lead_perdu``
    est True dans les kwargs (la vue envoie ce paramètre si l'utilisateur a coché
    la case). Le motif de refus du devis devient le motif_perte du lead.
    """
    if not getattr(devis, 'lead_id', None):
        return
    marquer = kwargs.get('marquer_lead_perdu', False)
    if not marquer:
        return
    # Import local pour éviter les cycles (CRM n'importe pas ventes.models).
    from .models import Lead
    try:
        lead = Lead.objects.get(pk=devis.lead_id, company=devis.company)
    except Lead.DoesNotExist:
        return
    if lead.perdu:
        return  # Déjà perdu, ne pas écraser.
    from . import activity as crm_activity
    old_perdu = lead.perdu
    old_motif = lead.motif_perte
    lead.perdu = True
    # MRY22 — le TROISIÈME chemin vers « perdu ». Le refus d'un devis peut
    # arriver sans motif saisi : on retombe alors sur « Devis refusé » plutôt
    # que d'écrire NULL, sinon ce chemin serait le seul à produire des pertes
    # sans raison — exactement ce que les deux autres refusent désormais.
    lead.motif_perte = (motif_refus or '')[:255] or 'Devis refusé'
    lead.save(update_fields=['perdu', 'motif_perte'])
    crm_activity.log_bulk_change(lead, user, 'perdu', old_perdu, True)
    if lead.motif_perte != old_motif:
        crm_activity.log_bulk_change(lead, user, 'motif_perte',
                                     old_motif, lead.motif_perte)
    # MRY9 (c) — troisième chemin vers « perdu » : il arrête les relances
    # comme les deux autres. Une seule fonction, jamais une variante locale.
    arreter_cadence(lead, user=user,
                    motif=(motif_refus or 'devis refusé'))


@receiver(devis_accepted, dispatch_uid="crm_flip_parrainage_converti_on_devis_accepted")
def _relais_flip_parrainage_converti_on_devis_accepted(**kwargs):
    return receivers_clients._flip_parrainage_converti_on_devis_accepted(**kwargs)


@receiver(devis_accepted, dispatch_uid="crm_lien_parrainage_on_devis_accepted")
def _relais_proposer_lien_parrainage_on_devis_accepted(**kwargs):
    return receivers_clients._proposer_lien_parrainage_on_devis_accepted(**kwargs)


@receiver(devis_refused, dispatch_uid="crm_signal_signe_sans_devis_actif")
def _signaler_signe_sans_devis_actif(sender, devis, user, motif_refus,
                                     **kwargs):
    """U11 — au refus d'un devis, signale (sans reculer l'étape) si le lead reste
    coincé à SIGNED sans aucun devis accepté actif (« signé fantôme »).

    Indépendant de la case « marquer le lead perdu » : la cohérence du funnel
    doit être signalée que l'utilisateur coche ou non cette case. Conforme à la
    règle #2 (le funnel est une couche permanente, séparée des statuts DOCUMENT —
    on NE recule JAMAIS l'étape à l'aveugle).
    """
    if not getattr(devis, 'lead_id', None):
        return
    signaler_mismatch_signe_sur_refus(devis, user)


# ── QJ7 — Avance automatique NEW → CONTACTED au premier contact ──────────────

@receiver(post_save, sender=LeadActivity,
          dispatch_uid="crm_advance_stage_new_vers_contacted_on_activity")
def _avancer_stage_on_contact_activity(sender, instance, created, **kwargs):
    """QJ7 — Quand la PREMIÈRE activité de contact (NOTE/APPEL/EMAIL) est créée
    sur un lead NEW (et non perdu), avance l'étape vers CONTACTED — une seule fois.

    Intra-CRM : utilise ``post_save`` sur ``LeadActivity`` (pas de bus cross-app).
    Le garde-fou « ne recule jamais » et « ignore les leads perdus » est délégué à
    ``avancer_stage_new_vers_contacted`` dans ``services.py``.
    """
    if not created:
        return  # mise à jour, pas une nouvelle activité
    if instance.kind not in _CONTACT_KINDS:
        return  # CREATION ou MODIFICATION ne déclenchent pas l'avancée
    if instance.user is None:
        return  # uniquement un contact MANUEL d'un utilisateur (pas auto/système)
    lead = instance.lead
    # RÈGLE FONDATEUR 07/09/2026 — le funnel ne bouge que sur une RÉPONSE
    # CONFIRMÉE de Meryem : « joint » / « intéressé ». Une simple note, un
    # appel sans réponse ou un WhatsApp ENVOYÉ ne déplacent plus l'étape
    # (l'ancien « auto — premier contact » sur toute activité est mort) ;
    # le KPI de premier contact, lui, reste horodaté (MRY19).
    # CAD131 (audit L3 du 21/09/2026) — SAUTER une touche n'est PAS une
    # tentative : rien n'est sorti vers le client, et la note que le saut
    # écrit posait pourtant `first_contacted_at`. Sauter la toute première
    # touche satisfaisait donc la promesse « rappelé en moins de N minutes »
    # ET éteignait l'escalade, qui n'agit que sur les leads SANS horodatage.
    # La reconnaissance vit dans `services` — là où la note est ÉCRITE.
    # COCKPIT-CONTRÔLE B4 (30/09/2026) — même trou, autre porte : la note
    # d'un REPORT (« Rappel demandé le … reportée. ») ou d'une MISE EN VEILLE
    # n'est pas une tentative non plus — reporter la première touche d'un
    # lead neuf ne l'horodate plus et n'éteint plus l'escalade.
    if est_note_de_touche_sautee(instance) or est_note_de_report(instance):
        return
    marquer_premier_contact(lead)
    # Décision fondateur du 24/09/2026 (relevé du 25/09) — « visite acceptée »
    # est une réponse CONFIRMÉE au même titre que « joint » : le client a été
    # joint, et il a même dit oui à un rendez-vous. Un lead Nouveau qui
    # acceptait la visite au premier appel restait Nouveau.
    if (instance.outcome or '').strip() in ISSUES_CLIENT_JOINT:
        avancer_stage_new_vers_contacted(lead, instance.user)
        # QJ-FUNNEL (fondateur 09/09/2026) — le cran suivant du funnel, même
        # doctrine et MÊME périmètre de kinds qu'au-dessus (rien d'élargi) :
        # une réponse « joint »/« intéressé » journalisée après l'envoi de la
        # proposition passe le lead « Devis envoyé » → « Relance ». Gardes
        # d'étape exactes dans le service (un lead à CONTACTED ne saute
        # jamais d'étape ; jamais en arrière) — les deux appels sont
        # mutuellement exclusifs par construction.
        avancer_stage_sur_reponse_devis(lead, instance.user)


@receiver(post_save, sender=LeadActivity,
          dispatch_uid="crm_stop_contact_cadence_on_outcome")
def _relais_arreter_cadence_on_outcome(**kwargs):
    return receivers_cadence._arreter_cadence_on_outcome(**kwargs)


@receiver(lead_stage_changed,
          dispatch_uid="crm_stop_relance_on_stage_signed_or_cold")
def _relais_arreter_cadence_on_stage_change(**kwargs):
    return receivers_cadence._arreter_cadence_on_stage_change(**kwargs)


@receiver(lead_stage_changed, dispatch_uid="crm_generate_playbook_progress_on_stage_change")
def _relais_generer_playbook_progress_on_stage_change(**kwargs):
    return receivers_clients._generer_playbook_progress_on_stage_change(**kwargs)


@receiver(ticket_resolu, dispatch_uid="crm_chatter_on_ticket_resolu")
def _chatter_on_ticket_resolu(sender, ticket, company, user, ancien_statut,
                              **kwargs):
    """ARC37 — à la résolution d'un ticket SAV, pose une note chatter ARC8 sur
    le ``crm.Client`` lié (``sav.Ticket.client`` — lien direct, jamais un
    import d'``apps.sav.models``, uniquement l'instance déjà portée par le
    signal). Best-effort : une erreur ici ne doit jamais remonter (la
    résolution, côté ``sav``, est déjà actée)."""
    client = getattr(ticket, 'client', None)
    if client is None:
        return
    try:
        from apps.records.services import log_note

        log_note(
            client, user,
            f'Ticket SAV {ticket.reference} résolu.',
            company=company)
    except Exception:  # noqa: BLE001 — best-effort, ne casse jamais
        logger.warning(
            'ARC37 : chatter ARC8 échoué sur ticket_resolu pour ticket #%s',
            getattr(ticket, 'pk', '?'), exc_info=True)


# ── PUB30 — appointment_effectue : transition GÉNUINE Appointment → EFFECTUE ──
# Intra-CRM (comme le récepteur QJ7 sur LeadActivity ci-dessus), pas un
# abonnement M6 — CE module ÉMET ici l'événement dont ``adsengine`` (jamais
# importé par crm) s'abonne dans SON PROPRE apps.py/receivers.py, pour pousser
# un événement CAPI dédié (même famille/gating que ADSENG32).

_APPOINTMENT_OLD_STATUT_ATTR = '_pub30_old_statut'


@receiver(pre_save, sender=Appointment,
          dispatch_uid="crm_capture_appointment_old_statut")
def _capture_appointment_old_statut(sender, instance, **kwargs):
    """Capture l'ANCIEN statut (la base porte encore l'ancienne valeur) avant
    le save — un Appointment neuf (pas de pk) → ancien statut None."""
    old = None
    if getattr(instance, 'pk', None):
        old = (Appointment.objects
               .filter(pk=instance.pk)
               .values_list('statut', flat=True)
               .first())
    setattr(instance, _APPOINTMENT_OLD_STATUT_ATTR, old)


@receiver(post_save, sender=Appointment,
          dispatch_uid="crm_emit_appointment_effectue")
def _emit_appointment_effectue_on_transition(sender, instance, created,
                                             **kwargs):
    """Sur une transition GÉNUINE vers EFFECTUE, émet ``appointment_effectue``.

    Un save qui laisse le statut inchangé (ex. édition des notes d'un RDV déjà
    EFFECTUE) ne réémet JAMAIS — même garde que ADSENG32
    (``capi_crm._emit_on_stage_change``). Best-effort : un abonné en échec ne
    casse jamais le save du rendez-vous."""
    new_statut = getattr(instance, 'statut', None)
    if new_statut != Appointment.Statut.EFFECTUE:
        return
    old_statut = getattr(instance, _APPOINTMENT_OLD_STATUT_ATTR, None)
    if not created and old_statut == new_statut:
        return  # save sans changement de statut → rien à émettre.
    try:
        appointment_effectue.send(
            sender='crm.Appointment', appointment=instance,
            company=instance.company, user=None, ancien_statut=old_statut)
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.warning(
            'PUB30 : émission appointment_effectue échouée pour le '
            'rendez-vous #%s', getattr(instance, 'pk', '?'), exc_info=True)


@receiver(post_save, sender=Lead, dispatch_uid='crm_emit_lead_created')
def _emit_lead_created(sender, instance, created, **kwargs):
    """NTGRC9 — émet ``core.events.lead_created`` à la CRÉATION d'un lead.

    Quelle que soit la porte d'entrée (saisie, webhook site, import). Le CRM
    ne sait RIEN de ses abonnés (aujourd'hui : la conformité GRC, qui alerte
    le DPO si la personne avait retiré son consentement). Best-effort : un
    abonné en échec ne casse jamais la création du lead.
    """
    if not created:
        return
    try:
        lead_created.send(
            sender='crm.Lead', lead=instance,
            company=getattr(instance, 'company', None))
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.warning(
            'NTGRC9 : émission lead_created échouée pour le lead #%s',
            getattr(instance, 'pk', '?'), exc_info=True)


# ── VTA5 — LE FEU VERT D'UNE VISITE TERRAIN REDESCEND SUR LE LEAD ────────────
#
# ``apps.visites`` a émis ``visite_validee`` ; c'est ICI que le CRM décide ce
# qu'il en fait. Avant VTA5, l'app visites écrivait elle-même sur ``crm.Lead``
# — le dernier écrit direct de la visite vers le CRM. Il n'en reste aucun : le
# lead voyage en ``lead_id`` (entier), le récap arrive tout fait
# (``visites.selectors.recap_visite_terrain`` reste la seule source de la
# phrase, donc la règle « zéro chiffre inventé » est tenue d'un seul côté).
#
# Aucune étape de funnel ne bouge : ``STAGES.py`` n'est pas touché — le statut
# de visite est un layer DOCUMENT interne.

@receiver(visite_validee, dispatch_uid="crm_retour_lead_on_visite_validee")
def _relais_retour_lead_on_visite_validee(**kwargs):
    return receivers_cadence._retour_lead_on_visite_validee(**kwargs)


# ── VISITE-CADENCE — LE SUIVI COMMERCIAL RÉAGIT À LA VISITE ──────────────────
#
# Ordre fondateur du 15/09/2026 : la visite technique se place APRÈS l'envoi du
# devis, comme outil de closing. Jusqu'ici le suivi l'IGNORAIT : on pouvait
# caler un rendez-vous chez un client et continuer à lui envoyer « le PDF
# s'ouvre bien ? », puis laisser le technicien repartir sans que personne ne
# rappelle. Ces deux récepteurs ferment les deux trous.
#
# Même montage que ``visite_validee`` au-dessus : ``apps.visites`` ÉMET, le CRM
# DÉCIDE, le lead voyage en ``lead_id`` (entier). Les récepteurs restent MINCES
# — toute la règle métier vit dans ``services.py`` (testable sans bus) — et
# best-effort : l'action du terrain est DÉJÀ actée quand on arrive ici.
#
# Aucun des deux ne touche ``STAGES.py`` : le statut d'une visite est un layer
# DOCUMENT interne, jamais une étape de funnel.

@receiver(visite_planifiee, dispatch_uid="crm_suivi_on_visite_planifiee")
def _relais_suivi_on_visite_planifiee(**kwargs):
    return receivers_cadence._suivi_on_visite_planifiee(**kwargs)


@receiver(visite_terminee, dispatch_uid="crm_suivi_on_visite_terminee")
def _relais_suivi_on_visite_terminee(**kwargs):
    return receivers_cadence._suivi_on_visite_terminee(**kwargs)


# ── CAD-E ── CAD61 — une facture ÉMISE ne déclenche AUCUNE relance ─────────


@receiver(facture_emise, dispatch_uid="crm_cad61_trace_facture_emise")
def _relais_tracer_facture_emise_sur_le_lead(**kwargs):
    return receivers_cadence._tracer_facture_emise_sur_le_lead(**kwargs)


# ── ALEA3 (D-ALEA-3) — salle de vente : l'intérêt signalé NOTIFIE le responsable
#
# ``salle_vente_signal_interet`` était un seam sans abonné : la note au
# chatter existait, mais personne n'était prévenu. Le responsable du lead
# (``owner``) reçoit UNE notification par jour LOCAL et par salle. Personne
# n'est notifié quand le lead n'a pas de responsable (jamais au hasard).


def _debut_jour_local():
    """Minuit du jour LOCAL (Africa/Casablanca), en datetime aware."""
    from core.dates import maintenant_local

    return maintenant_local().replace(
        hour=0, minute=0, second=0, microsecond=0)


@receiver(salle_vente_signal_interet,
          dispatch_uid='crm_notifier_interet_salle_vente')
def _notifier_responsable_interet_salle(sender, lead, salle, company,
                                        **kwargs):
    """Notifie le responsable du lead qu'une salle de vente montre un intérêt
    fort. Idempotent par (destinataire, salle, jour local). Best-effort."""
    try:
        destinataire = getattr(lead, 'owner', None)
        if destinataire is None or not destinataire.is_active:
            return
        from apps.notifications.models import Notification
        from apps.notifications.services import notify
        from apps.notifications.types_evenements import EventType

        titre = (f'Intérêt signalé — salle de vente « {salle.titre} » '
                 f'(#{salle.pk})')[:255]
        if Notification.objects.filter(
                recipient=destinataire, event_type=EventType.DEVIS_OPENED,
                title=titre, created_at__gte=_debut_jour_local()).exists():
            return
        nom = ' '.join(p for p in (getattr(lead, 'prenom', '') or '',
                                   getattr(lead, 'nom', '') or '') if p)
        notify(
            user=destinataire,
            event_type=EventType.DEVIS_OPENED,
            title=titre,
            body=(f'{nom or "Le client"} a consulté la salle de vente '
                  'plusieurs fois : bon moment pour le rappeler.'),
            link=f'/crm/leads?lead={lead.pk}',
            company=company,
        )
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.warning(
            'ALEA3 : notification « intérêt signalé » échouée (lead #%s)',
            getattr(lead, 'pk', '?'), exc_info=True)

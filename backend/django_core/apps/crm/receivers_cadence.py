"""SPL95 — corps des récepteurs de CADENCE (déplacés de ``receivers.py``).

Move only : corps et noms inchangés, SANS décorateur. Le câblage (``@receiver``,
``dispatch_uid``, ordre de connexion) reste dans ``receivers.py``, qui garde un
relais d'une ligne par récepteur parti.
"""

import datetime
import logging

from django.utils import timezone

from . import stages
from .cadence_config import CLE_DECIDER_SUITE, CLE_DEVIS_MODIFIE
from .models import Lead, LeadActivity
from .services import (
    CADENCES_ARRETEES_PAR_ISSUE,
    CAUSE_RDV_REFUS,
    OUTCOME_VISITE_ACCEPTEE,
    _poser_etape_de_filet,
    _recaler_file,
    annuler_etapes_moteur_ouvertes,
    annuler_rendez_vous_sur_arret,
    appliquer_retour_visite,
    appliquer_visite_planifiee,
    arreter_cadence,
    arreter_cadence_du_lead_id,
    assurer_prochaine_etape_apres_succes,
    avancer_stage_lead_vers,
    ecrire_retour_lead_visite,
    est_cloture_d_etape_visite,
    est_derniere_touche_du_suivi,
    initialiser_plan_relance,
    journaliser_visite,
    phrase_notification_retour_visite,
    poser_filet_visite_a_planifier,
    q_visite,
    touche_close_de,
)

logger = logging.getLogger(__name__)


LIBELLE_FAIRE_SIGNER_AVENANT = 'Faire signer l’avenant'


def _a_un_predecesseur_accepte(devis):
    """ADEV57 — vrai si une version que ``devis`` REMPLACE (chaîne de
    révision) est au statut accepté. Lecture via les sélecteurs ventes."""
    from apps.ventes.selectors import (
        devis_predecesseurs_revision_ids, get_devis_by_pk, is_devis_accepte)
    for pk in devis_predecesseurs_revision_ids(devis):
        ancien = get_devis_by_pk(pk)
        if ancien is not None and is_devis_accepte(ancien):
            return True
    return False


def _poser_tache_avenant(lead, devis, user):
    """ADEV57 — UNE tâche « faire signer l’avenant » (étape de filet,
    idempotente : une étape déjà ouverte est déplacée, jamais doublée)."""
    reference = getattr(devis, 'reference', '') or '?'
    etape = _poser_etape_de_filet(
        lead, libelle=LIBELLE_FAIRE_SIGNER_AVENANT, canal='appel',
        vise=timezone.now() + datetime.timedelta(days=1),
        note=(f'Posée automatiquement : la révision {reference} d’un devis '
              'accepté est envoyée — avenant à faire signer, aucune cadence '
              'de relance commerciale.'))
    _recaler_file(lead, user)
    return etape


def _arreter_cadence_on_devis_accepted(sender, devis, user, ancien_statut,
                                       **kwargs):
    """MRY9 (a) — un devis accepté ARRÊTE toutes les cadences du lead.

    Sans cela, le client qui vient de signer continue de recevoir les
    messages « votre proposition est valable jusqu'au … » : la faute la plus
    visible qu'un CRM puisse commettre. Best-effort — jamais d'exception vers
    l'acceptation, qui est déjà actée."""
    arreter_cadence_du_lead_id(
        getattr(devis, 'lead_id', None), company=getattr(devis, 'company', None),
        user=user, motif='devis accepté')


def _planifier_apres_devis_on_devis_sent(sender, devis, user, ancien_statut,
                                         **kwargs):
    """MRY7 — L'ENVOI d'un devis bascule le lead sur la cadence « après devis ».

    Deux gestes, dans cet ordre : la prise de contact s'ARRÊTE (son but est
    atteint — le prospect a son chiffrage), puis le suivi de proposition
    DÉMARRE, daté depuis la date d'envoi réelle et non depuis maintenant.

    UNE SEULE cadence après-devis par LEAD à la fois : quand plusieurs devis
    d'un même lead partent ensemble (``whatsapp_devis`` boucle sur la
    sélection), le deuxième ne crée rien — sinon le client recevrait deux
    séries de messages parallèles pour un seul dossier. Le fait est journalisé
    plutôt que silencieux.

    Best-effort : ne fait jamais retomber un envoi déjà acté."""
    lead_id = getattr(devis, 'lead_id', None)
    if not lead_id:
        return
    try:
        from .models import Lead
        lead = Lead.objects.filter(
            pk=lead_id, company=getattr(devis, 'company', None)).first()
        if lead is None:
            return
        # ADEV57 (D-ADEV-6 (a), fondateur 08/10/2026) — le devis envoyé
        # RÉVISE un devis déjà ACCEPTÉ (avenant) : le client a signé, aucune
        # cadence de relance commerciale ne s'ouvre ; une seule tâche
        # interne « faire signer l'avenant » est posée. Prédécesseurs lus
        # par les sélecteurs ventes (jamais ses modèles).
        if _a_un_predecesseur_accepte(devis):
            _poser_tache_avenant(lead, devis, user)
            return
        # RELANCE-SUITE (08/09/2026) — l'envoi ferme aussi l'étape générique
        # « préparer et envoyer le devis » / « appeler le client » devenue
        # sans objet : le plan après-devis prend la suite.
        arreter_cadence(lead, user=user, motif='devis envoyé',
                        cadences=['contact', 'generique'])
        # SUIVI E1 (30/09/2026) — l'étape « Préparer le devis modifié »
        # encore ouverte a rempli son office : le devis modifié part.
        if annuler_etapes_moteur_ouvertes(lead, CLE_DEVIS_MODIFIE,
                                          note='devis envoyé'):
            # SUIVI I6 — l'annulation passe par un ``update()`` : sans
            # recalage, ``relance_date`` pointait encore sur l'étape annulée
            # quand elle était la plus proche (``initialiser_plan_relance``
            # ne l'avance que si elle est plus TARDIVE que sa première
            # touche).
            _recaler_file(lead, user)
        # SUIVI E1 — seuls les BARREAUX du protocole après-devis sont « un
        # suivi en cours » : une étape de VISITE ouverte (planifier,
        # confirmer, débrief — cadence `apres_devis`, devis souvent NULL, donc
        # jamais écartée par `.exclude(devis_id=…)`) bloquait le démarrage du
        # suivi de proposition, et le devis partait sans aucune relance.
        barreaux_ouverts = lead.relance_etapes.filter(
            cadence='apres_devis', statut='a_faire').exclude(q_visite())
        deja = barreaux_ouverts.exclude(devis_id=devis.pk).first()
        # QJR561 — la RÉVISION envoyée reprend le suivi de la version qu'elle
        # remplace : les barreaux ouverts des prédécesseurs (sélecteur ventes,
        # jamais ses modèles) sont RE-POINTÉS sur ce devis, sans redater. La
        # branche « aucune seconde série » reste pour un AUTRE devis du lead.
        if deja is not None and deja.devis_id:
            from apps.ventes.selectors import (
                devis_predecesseurs_revision_ids)
            predecesseurs = devis_predecesseurs_revision_ids(devis)
            if deja.devis_id in predecesseurs:
                barreaux_ouverts.filter(
                    devis_id__in=predecesseurs).update(devis_id=devis.pk)
                LeadActivity.objects.create(
                    company=lead.company, lead=lead, user=user,
                    kind=LeadActivity.Kind.NOTE,
                    body=('Suivi repris sur la révision '
                          f'{getattr(devis, "reference", "") or "?"}.'))
                deja = barreaux_ouverts.exclude(devis_id=devis.pk).first()
                if deja is None:
                    return
        if deja is not None:
            reference = getattr(deja.devis, 'reference', '') or '?'
            LeadActivity.objects.create(
                company=lead.company, lead=lead, user=user,
                kind=LeadActivity.Kind.NOTE,
                body=('Cadence après devis déjà en cours pour '
                      f'{reference} — aucune seconde série lancée.'))
            return
        # QJR660 (décision fondateur 01/10/2026) — le MÊME devis déjà suivi
        # (corrigé sur place, D-QJR5-1) garde la cadence d'ORIGINE, ancrée sur
        # son premier envoi : rien n'est proposé, rien n'est redaté.
        if barreaux_ouverts.filter(devis_id=devis.pk).exists():
            return
        etapes = initialiser_plan_relance(
            lead, user, cadence='apres_devis',
            depart=getattr(devis, 'date_envoi', None), devis=devis)
        # M2 (revue Fable 07/09/2026) — société sans gabarit après-devis (ou
        # barreaux tous écartés) : le plan est vide et la prise de contact
        # vient d'être arrêtée — sans filet, le lead sortait de toutes les
        # files. L'étape générique tient l'invariant Froid-ou-Signé.
        if not any(getattr(e, 'statut', '') == 'a_faire' for e in etapes):
            assurer_prochaine_etape_apres_succes(lead, user)
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.warning(
            "MRY7: cadence après devis non planifiée (devis #%s)",
            getattr(devis, 'pk', '?'), exc_info=True)


def _arreter_apres_devis_on_devis_refused(sender, devis, user, motif_refus,
                                          **kwargs):
    """MRY7 — Un devis REFUSÉ arrête sa cadence de suivi, même quand le lead
    n'est PAS marqué perdu.

    C'est le cas par défaut (`marquer_lead_perdu` non coché) : le lead reste
    vivant — on lui refera peut-être une offre — mais continuer à lui demander
    « alors, ce PDF ? » sur une proposition qu'il vient de refuser serait
    absurde. Distinct du receveur « perdu », qui ne se déclenche pas ici."""
    lead_id = getattr(devis, 'lead_id', None)
    if not lead_id:
        return
    try:
        from .models import Lead, RelanceEtape
        lead = Lead.objects.filter(
            pk=lead_id, company=getattr(devis, 'company', None)).first()
        if lead is None:
            return
        if RelanceEtape.objects.filter(
                devis_id=devis.pk,
                statut=RelanceEtape.Statut.A_FAIRE).exists():
            arreter_cadence(lead, user=user,
                            motif=(motif_refus or 'devis refusé'),
                            cadences=['apres_devis'])
        # QJ-INVARIANT — le lead reste VIVANT après ce refus (pas marqué
        # perdu) : une étape « décider la suite » le garde dans les files —
        # sa liste de relances ne se termine que par Froid ou Signé. Jamais
        # le plan après-devis (relancer la proposition refusée).
        # PARAM-CADENCE — l'étape « décider la suite » est une CLÉ du
        # gabarit « Après l'appel » : la société la renomme dans Paramètres.
        assurer_prochaine_etape_apres_succes(
            lead, user, cle=CLE_DECIDER_SUITE, avec_plan_devis=False)
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.warning(
            "MRY7: arrêt de la cadence après devis échoué (devis #%s)",
            getattr(devis, 'pk', '?'), exc_info=True)


def _arreter_cadence_on_outcome(sender, instance, created, **kwargs):
    """MRY9 (e) — l'ISSUE d'un appel arrête la bonne cadence, et elle seule.

    * `joint` / `interesse` → arrête `contact` : le but de la prise de contact
      est atteint. La cadence APRÈS DEVIS, elle, continue — un client joint
      reste à relancer sur sa proposition. RELANCE-SUITE (fondateur
      08/09/2026) : la suite posée par le filet suit le CANAL de la touche —
      message répondu → « appeler le client » ; appel fait → « préparer et
      envoyer le devis » ; le plan après-devis attend l'ENVOI du devis.
      SUIVI E22 (30/09/2026) — sur la DERNIÈRE touche du suivi de
      proposition (lue sur la touche close, ``touche_close_de``) : « décider
      la suite », pour demain, jamais l'étape devis d'un devis déjà parti.
    * `refus` → arrête `contact` ET `apres_devis`, SANS marquer le lead perdu :
      « perdu » est une décision humaine qui exige un motif (MRY22), pas un
      effet de bord d'un appel.
    * `visite_acceptee` (décision fondateur du 24/09/2026) → arrête `contact`
      et `reveil` exactement comme `joint` (un dormant qui accepte la visite
      sort du Froid), mais la suite n'est pas l'étape générique : c'est
      « Planifier la visite technique convenue », pour aujourd'hui.

    Seule une activité créée par un HUMAIN compte (``user`` non nul) — une
    ligne système ne décide pas d'un arrêt."""
    if not created or instance.user is None:
        return
    issue = (instance.outcome or '').strip()
    # M1 (revue Fable 07/09/2026) — la cadence ``reveil`` est arrêtée comme
    # les autres : un client JOINT au réveil J30 ne doit pas recevoir le J60,
    # et un refus au réveil termine les réveils (le dossier reste au Froid).
    # CAD1 — la liste des cadences arrêtées est lue dans `services`
    # (``CADENCES_ARRETEES_PAR_ISSUE``), d'où la matérialisation réactive la
    # lit aussi : une seule table, donc plus de divergence possible entre
    # « ce que l'arrêt fait » et « ce que la suite croit qu'il a fait ».
    cadences = list(CADENCES_ARRETEES_PAR_ISSUE.get(issue, ()))
    if not cadences:
        return
    if issue in ('joint', 'interesse'):
        motif = 'joint'
    elif issue == OUTCOME_VISITE_ACCEPTEE:
        motif = 'visite acceptée'
    else:
        motif = 'refus au téléphone'
    try:
        arreter_cadence(instance.lead, user=instance.user, motif=motif,
                        cadences=cadences)
        # QJ-INVARIANT — si l'arrêt (ou l'absence de toute cadence) laisse le
        # lead SANS prochaine étape, le filet en pose une : un client joint ne
        # disparaît jamais des files, et un REFUS téléphonique laisse une
        # étape « décider la suite » — la décision (perdu + motif, MRY22)
        # reste humaine, mais le dossier reste visible en attendant.
        if issue in ('joint', 'interesse', OUTCOME_VISITE_ACCEPTEE):
            # M1 — un client joint pendant un RÉVEIL sort du parking : COLD
            # est rangé SOUS toute étape active (rang -1), l'avance vers
            # CONTACTED est donc légitime et réactive le dossier — sans quoi
            # la garde COLD du filet le laisserait figé au Froid sans suite.
            # 24/09/2026 — même chose pour un dormant qui ACCEPTE LA VISITE :
            # resté au Froid, plus aucun filet ne le relèverait après elle.
            instance.lead.refresh_from_db(fields=['stage'])
            if instance.lead.stage == stages.COLD:
                avancer_stage_lead_vers(
                    instance.lead, instance.user, stages.CONTACTED)
        if issue == OUTCOME_VISITE_ACCEPTEE:
            # 24/09/2026 — la seule suite utile est de CALER la visite, pour
            # aujourd'hui (no-op si un rendez-vous est déjà calé). Posée ICI
            # pour que l'issue saisie au journal d'appel de la fiche (aucune
            # touche close) ait la même suite qu'au « Fait » d'une touche ;
            # sur ce second chemin, ``marquer_etape_relance`` repasse derrière
            # (idempotent par libellé : l'étape est déplacée, jamais doublée).
            poser_filet_visite_a_planifier(instance.lead, instance.user)
        elif issue in ('joint', 'interesse'):
            # RELANCE-SUITE (08/09/2026) — la suite dépend du CANAL de la
            # touche : message répondu → l'appeler ; appel fait → préparer
            # et envoyer le devis. Le plan après-devis, lui, ne démarre qu'à
            # l'ENVOI du devis (jamais sur un brouillon).
            # CAD2 — la clôture d'une étape de VISITE (débrief, confirmation,
            # devis modifié) ne DÉMARRE jamais le suivi de proposition : le
            # filet le poursuit s'il a déjà servi, sinon il pose son étape.
            # SUIVI E4 (30/09/2026) — et elle n'est jamais « il a répondu au
            # message » : une confirmation de visite close par WhatsApp ne
            # fait pas poser « Appeler le client — il a répondu au message »
            # (le canal de la touche ne décide pas de sa suite).
            if est_derniere_touche_du_suivi(touche_close_de(instance)):
                # SUIVI E22 (décision fondateur du 30/09/2026) — client joint
                # sur la DERNIÈRE touche du suivi de proposition : le devis
                # est déjà parti, « Préparer et envoyer le devis » (ou
                # « l'appeler ») n'a plus de sens. « Décider la suite » est
                # posée pour demain, comme après un refus — sans plan devis ;
                # le dossier garde son étape (« Relance »).
                assurer_prochaine_etape_apres_succes(
                    instance.lead, instance.user,
                    cle=CLE_DECIDER_SUITE, avec_plan_devis=False)
            else:
                visite = est_cloture_d_etape_visite(instance)
                assurer_prochaine_etape_apres_succes(
                    instance.lead, instance.user,
                    canal_touche=None if visite else instance.kind,
                    demarrer_plan=not visite)
        elif issue == 'refuse':
            # SUIVI E21 (30/09/2026) — le refus arrête les relances ET le
            # rendez-vous de visite en attente : le technicien ne se déplace
            # pas chez un client qui vient de refuser (best-effort, note au
            # chatter quand un rendez-vous est réellement annulé).
            annuler_rendez_vous_sur_arret(
                instance.lead, instance.user, cause=CAUSE_RDV_REFUS)
            assurer_prochaine_etape_apres_succes(
                instance.lead, instance.user,
                cle=CLE_DECIDER_SUITE, avec_plan_devis=False)
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.warning(
            "MRY9: arrêt de cadence échoué sur l'issue « %s » (lead #%s)",
            issue, getattr(instance, 'lead_id', '?'), exc_info=True)


def _arreter_cadence_on_stage_change(sender, lead, old_stage, new_stage, user,
                                     **kwargs):
    """MRY9 (b) — SIGNED arrête TOUT ; COLD arrête `contact` et `apres_devis`.

    COLD est un PARKING, pas une perte : les réveils J30/J60 y sont posés par
    MRY11 — on ne les arrête donc pas ici, sinon un lead mis au froid ne
    serait plus jamais réveillé. Best-effort : ne bloque jamais la transition
    d'étape déjà actée par l'émetteur."""
    try:
        if new_stage == stages.SIGNED:
            arreter_cadence(lead, user=user, motif='lead signé')
        elif new_stage == stages.COLD:
            arreter_cadence(lead, user=user, motif='lead passé en froid',
                            cadences=['contact', 'apres_devis'])
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.warning(
            "MRY9: arrêt de cadence échoué au changement d'étape du lead #%s",
            getattr(lead, 'pk', '?'), exc_info=True)


def _retour_lead_on_visite_validee(sender, visite, lead_id, user, recap,
                                   **kwargs):
    """Pose ``visite_effectuee`` + le récap sur la fiche, et la note chatter.

    Idempotence reconduite à l'identique : le récap n'est APPENDU que s'il
    n'est pas déjà présent (``recap not in existantes``), donc une
    re-validation ne le duplique pas et une note écrite à la main n'est jamais
    écrasée. L'auteur de la note est l'utilisateur AGISSANT, transporté par
    l'événement — jamais déduit.

    Best-effort : la visite est DÉJÀ validée quand on arrive ici ; un retour
    lead en échec ne doit pas défaire une décision humaine actée.
    """
    from .models import Lead

    try:
        lead = Lead.objects.filter(pk=lead_id).first()
        if lead is not None:
            ecrire_retour_lead_visite(
                lead, recap, visite_id=getattr(visite, "pk", None))
        journaliser_visite(visite, user, 'validee')
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.warning(
            'VTA5 : retour lead du feu vert de visite échoué pour le lead '
            '#%s', lead_id, exc_info=True)
    # AGR413 — les mesures du point d'eau (kwarg ``mesures_point_eau``, vide
    # pour une visite toiture) remontent sur les colonnes du lead : la mesure
    # remplace la déclaration. Lead borné à la société de la visite.
    # Best-effort comme VTA5 : la visite est déjà validée.
    mesures = kwargs.get('mesures_point_eau')
    if mesures:
        try:
            from .services import appliquer_mesures_point_eau
            lead = Lead.objects.filter(
                pk=lead_id, company_id=visite.company_id).first()
            if lead is not None:
                appliquer_mesures_point_eau(lead, mesures, user)
        except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
            logger.warning(
                'AGR413 : retour des mesures du point d\'eau échoué pour le '
                'lead #%s', lead_id, exc_info=True)
    # CIQ607 — le relevé C&I (kwarg ``releve_ci``, vide hors gabarit ``ci``)
    # remonte au lead : la mesure remplace la déclaration, avec sa
    # provenance. Lead borné à la société de la visite ; best-effort.
    releve_ci = kwargs.get('releve_ci')
    if releve_ci:
        try:
            from .services import appliquer_releve_ci
            lead = Lead.objects.filter(
                pk=lead_id, company_id=visite.company_id).first()
            if lead is not None:
                appliquer_releve_ci(lead, releve_ci, user)
        except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
            logger.warning(
                'CIQ607 : retour du relevé C&I échoué pour le lead #%s',
                lead_id, exc_info=True)


def _suivi_on_visite_planifiee(sender, visite, lead_id, user, date_prevue,
                               commercial_nom='', **kwargs):
    """Un rendez-vous est posé (ou déplacé) : la cadence s'y recale.

    AMENDEMENT FONDATEUR (15/09/2026) — « recale » veut dire DÉCALE, pas
    annule : le plan après-devis glisse jusqu'après le débrief et le lead garde
    sa position exacte dans le protocole. Aucune cadence n'est jamais
    redémarrée."""
    try:
        lead = Lead.objects.filter(pk=lead_id).first()
        if lead is None:
            return
        appliquer_visite_planifiee(
            lead, user, date_prevue, commercial_nom=commercial_nom)
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.warning(
            'VISITE-CADENCE : recalage du suivi échoué à la planification '
            'du lead #%s', lead_id, exc_info=True)


def _suivi_on_visite_terminee(sender, visite, lead_id, user, retour,
                              qualification=None, **kwargs):
    """Le technicien est reparti : son retour redescend, et on rappelle.

    Sa QUALIFICATION du client ouvre la note (amendement fondateur n°2) et
    décide de la suite : le débrief se cale sur le moment de rappel qu'il a
    convenu sur place, et devient « préparer le devis modifié » quand le devis
    doit être repris.

    Le retour TEXTE LIBRE entre dans l'historique du lead (il est souvent la
    seule trace de ce que le client a dit sur place), ``visite_effectuee`` est
    posé, et le RESPONSABLE du lead reçoit la notification « rappeler sous
    24-48 h ».

    La notification part du CRM et de lui seul : c'est lui qui connaît le
    ``owner`` d'un lead — ``apps.visites`` n'a aucun moyen (ni aucun droit) de
    le savoir."""
    try:
        lead = Lead.objects.filter(pk=lead_id).first()
        if lead is None:
            return
        auteur = ''
        if user is not None:
            auteur = (user.get_full_name() or user.username or '')
        etape = appliquer_retour_visite(lead, user, retour, auteur=auteur,
                                        qualification=qualification)
        _notifier_responsable_retour_visite(lead, user, etape)
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.warning(
            'VISITE-CADENCE : retour terrain non traité pour le lead #%s',
            lead_id, exc_info=True)


def _notifier_responsable_retour_visite(lead, acteur, etape=None):
    """Prévient le RESPONSABLE du lead de la suite du retour terrain.

    ``etape`` : ce que ``appliquer_retour_visite`` a RENDU — le texte le lit
    (``services.phrase_notification_retour_visite``) : « rappeler sous
    24-48 h » après un devis parti, « préparer et envoyer le devis pour le
    JJ/MM » sans devis (décision fondateur du 24/09/2026, relevé du 25/09).

    Personne d'autre : ni la direction (ce n'est pas une alerte), ni le
    commercial terrain (il vient de faire la visite). Lead sans responsable, ou
    responsable = l'acteur ⇒ rien à envoyer, pas une notification à soi-même.
    Best-effort — une cloche en échec ne défait pas une visite terminée."""
    destinataire = getattr(lead, 'owner', None)
    if destinataire is None:
        return None
    if acteur is not None and getattr(acteur, 'id', None) == destinataire.id:
        return None
    try:
        from apps.notifications.services import notify

        return notify(
            destinataire, 'visite_retour_terrain',
            f'Retour de visite — {lead}',
            body=phrase_notification_retour_visite(etape),
            link=f'/crm/leads/{lead.pk}', company=lead.company)
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.warning(
            'VISITE-CADENCE : notification de retour de visite non envoyée '
            '(lead #%s)', getattr(lead, 'pk', '?'), exc_info=True)
        return None


#: Le texte de la trace, tel que la commerciale le lit au chatter.
FACTURE_EMISE_TRACE = (
    'Facture {reference} émise — hors protocole de suivi : aucune touche de '
    'relance n’est ouverte (la facture part après la signature).')


def _tracer_facture_emise_sur_le_lead(sender, instance, company, **kwargs):
    """CAD61 — la facture envoyée se contente d'UNE LIGNE au chatter.

    [TRANCHÉ 21/09/2026] Une facture partie hors cadence ne produisait ni
    événement, ni réponse, ni touche : le dossier restait muet. Mais elle ne
    doit rien DÉCLENCHER non plus — elle part APRÈS la signature, donc hors du
    protocole de suivi. La décision fondateur est exactement celle-ci : une
    trace, rien de plus.

    L'autre moitié de la décision — « le client envoie quelque chose » — se
    traite par le geste « pièce reçue » de CAD101 (il attache le document,
    clôt la touche ouverte et pose « préparer le devis »). Il n'est PAS
    dupliqué ici : ce récepteur n'ouvre, ne clôt et ne modifie aucune touche.

    Garde-fou : la note est SYSTÈME (``user=None``) — une note portée par un
    utilisateur compterait comme un contact manuel (QJ7) et ferait bouger le
    funnel sur un simple envoi de facture. Best-effort : ne fait jamais
    retomber une émission déjà actée.
    """
    client_id = getattr(instance, 'client_id', None)
    if not client_id or company is None:
        return
    try:
        lead = (Lead.objects
                .filter(company=company, client_id=client_id,
                        is_archived=False)
                .order_by('-date_creation', '-id').first())
        if lead is None:
            return
        LeadActivity.objects.create(
            company=lead.company, lead=lead, user=None,
            kind=LeadActivity.Kind.NOTE,
            body=FACTURE_EMISE_TRACE.format(
                reference=getattr(instance, 'reference', '') or '?'))
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.warning(
            'CAD61: trace de facture non écrite (facture #%s)',
            getattr(instance, 'pk', '?'), exc_info=True)

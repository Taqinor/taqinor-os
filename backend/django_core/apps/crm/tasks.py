"""Tâches Celery de l'app CRM — auto-découvertes par `erp_agentique.celery`
(`app.autodiscover_tasks()`), aucun enregistrement manuel requis.
"""
from celery import shared_task


@shared_task(name='crm.recycler_leads_non_travailles')
def recycler_leads_non_travailles_task():
    """YLEAD14 — Enveloppe Celery Beat de la commande de gestion homonyme.

    Planifiée dans ``erp_agentique/celery.py`` (``beat_schedule``). Délègue
    entièrement à la commande de gestion (même logique, testable en dehors de
    Celery via ``manage.py recycler_leads_non_travailles``).
    """
    from apps.crm.management.commands.recycler_leads_non_travailles import (
        recycler_leads_non_travailles,
    )
    escalated, deassigned = recycler_leads_non_travailles()
    return {'escalated': escalated, 'deassigned': deassigned}


@shared_task(name='crm.escalader_rappels_demandes')
def escalader_rappels_demandes_task():
    """QW4 — Enveloppe Celery Beat de la commande de gestion homonyme.

    Planifiée dans ``erp_agentique/celery.py`` (``beat_schedule``). Escalade
    les rappels demandés (``contact_preference=phone_ok``) non actionnés au-
    delà du SLA rappel — plus serré que le SLA générique premier-contact de
    ``recycler_leads_non_travailles``. Même patron : réutilise entièrement la
    commande de gestion (testable hors Celery via
    ``manage.py escalader_rappels_demandes``).
    """
    from apps.crm.management.commands.escalader_rappels_demandes import (
        escalader_rappels_demandes,
    )
    escalated = escalader_rappels_demandes()
    return {'escalated': escalated}


@shared_task(name='crm.snapshot_forecast_hebdo')
def snapshot_forecast_hebdo_task():
    """NTCRM6 — Enveloppe Celery Beat de la commande de gestion homonyme.

    Planifiée dans ``erp_agentique/celery.py`` (``beat_schedule``). Crée/
    upsert le snapshot forecast hebdomadaire (idempotent par semaine ISO +
    owner). Même patron : réutilise entièrement la commande de gestion
    (testable hors Celery via ``manage.py snapshot_forecast_hebdo``).
    """
    from apps.crm.management.commands.snapshot_forecast_hebdo import (
        snapshot_forecast_hebdo,
    )
    nb = snapshot_forecast_hebdo()
    return {'snapshots': nb}


@shared_task(name='crm.recalculer_scores_obsoletes')
def recalculer_scores_obsoletes_task():
    """CRX22 — Enveloppe Celery Beat du rafraîchissement quotidien des scores.

    Planifiée dans ``erp_agentique/celery.py`` (``beat_schedule``). Le score
    n'était recalculé qu'à l'édition : la décote de RÉCENCE ne s'appliquait
    donc jamais aux leads dormants, qui gardaient le score de leur premier
    jour. Délègue entièrement au service (testable hors Celery via
    ``apps.crm.services.recalculer_scores_obsoletes``).
    """
    from apps.crm.leads_score import recalculer_scores_obsoletes

    return recalculer_scores_obsoletes()


#: MRY0 (lot C) — verrou anti-double-run du miroir Odoo (la passe complète dure
#: plusieurs minutes ; le beat tourne toutes les 30 min).
_ODOO_SYNC_LOCK = 'crm.sync_odoo_leads.lock'
_ODOO_SYNC_LOCK_TIMEOUT = 1500


@shared_task(name='crm.sync_odoo_leads')
def sync_odoo_leads_task():
    """MRY0 (lot C) — Enveloppe Celery Beat du miroir Odoo → ERP.

    AACQ97 (D-AACQ, 08/10/2026) — n'est PLUS planifiée au beat : la synchro
    Odoo est MANUELLE (lancement à la main uniquement), l'ERP fait foi.

    Le miroir n'était planifié NULLE PART (ni cron, ni timer, ni beat) : la
    dernière passe datait du 01/09/2026 et le cockpit de Meryem décrochait
    silencieusement. NO-OP PROPRE quand la config Odoo est incomplète ou que
    ``ODOO_SYNC_COMPANY_SLUG`` est vide — jamais un slug en dur. Verrou cache
    contre deux passes simultanées. Odoo reste en LECTURE SEULE (JSON-2).

    JAMAIS d'alignement des étapes (décision fondateur 08/10/2026) : les
    leads se traitent dans l'ERP, seule une action humaine y change l'étape.
    La passe planifiée transmet TOUJOURS ``--no-align`` (elle ne fait que
    rapatrier/importer) ; l'alignement sur le pipeline Odoo ne se fait qu'à
    la main, sur demande de Reda :
    ``manage.py sync_odoo_leads --company <slug>``.
    Incident : la passe ramenait en « Nouveau » tout lead mis en « Froid »
    (Froid est classé sous Nouveau → pris pour une avance), 27 leads touchés.
    """
    import io
    import logging
    import os

    from django.core.cache import cache
    from django.core.management import call_command

    from apps.crm.odoo_sync import OdooConfig

    logger = logging.getLogger(__name__)
    if OdooConfig().incomplete:
        logger.info('crm.sync_odoo_leads: config Odoo absente — no-op.')
        return {'skipped': 'config'}
    slug = (os.environ.get('ODOO_SYNC_COMPANY_SLUG', '') or '').strip()
    if not slug:
        logger.info(
            'crm.sync_odoo_leads: ODOO_SYNC_COMPANY_SLUG vide — no-op.')
        return {'skipped': 'company'}
    if not cache.add(_ODOO_SYNC_LOCK, 1, timeout=_ODOO_SYNC_LOCK_TIMEOUT):
        logger.info('crm.sync_odoo_leads: passe déjà en cours — no-op.')
        return {'skipped': 'lock'}
    sortie = io.StringIO()
    try:
        options = {'company': slug, 'stdout': sortie, 'no_align': True}
        call_command('sync_odoo_leads', **options)
    finally:
        cache.delete(_ODOO_SYNC_LOCK)
    rapport = sortie.getvalue()
    logger.info('crm.sync_odoo_leads: %s', rapport.replace('\n', ' | '))
    return {'rapport': rapport}


@shared_task(name='crm.notifier_relances_dues')
def notifier_relances_dues_task():
    """MRY17 — Enveloppe Celery Beat du digest 08:30 des touches dues.

    Planifiée dans ``erp_agentique/celery.py`` (``beat_schedule``). Délègue
    entièrement à la commande de gestion (même logique, testable hors Celery
    via ``manage.py notifier_relances_dues``). Idempotente par jour ET par
    destinataire — indispensable avec ``acks_late``, qui peut relancer une
    tâche après un crash worker."""
    from apps.crm.management.commands.notifier_relances_dues import (
        notifier_relances_dues,
    )
    envoyes, destinataires = notifier_relances_dues()
    return {'digests': envoyes, 'destinataires': destinataires}


@shared_task(name='crm.escalader_premier_contact')
def escalader_premier_contact_task():
    """MRY17 — Enveloppe Celery Beat de l'escalade « premier contact ».

    Toutes les 5 minutes. Idempotente PAR LEAD (marqueur en note chatter) :
    sans elle, la même alerte repartirait à chaque passage jusqu'au rappel."""
    from apps.crm.management.commands.escalader_premier_contact import (
        escalader_premier_contact,
    )
    return {'escalades': escalader_premier_contact()}


@shared_task(name='crm.bilan_hebdo_relances')
def bilan_hebdo_relances_task():
    """MRY21 — Enveloppe Celery Beat du bilan hebdomadaire (lundi 07:00).

    Le seul moment où quelqu'un regarde le moteur DE HAUT plutôt que touche
    par touche : sans lui, une cadence qui dérape resterait invisible jusqu'au
    trimestre. Délègue entièrement à la commande de gestion."""
    from apps.crm.management.commands.bilan_hebdo_relances import (
        bilan_hebdo_relances,
    )
    return {'bilans': bilan_hebdo_relances()}


#: ALEA1 — plafond de dormants examinés par société et par passage (la touche
#: reste UNE par an et par dormant ; ce plafond borne seulement le coût d'un
#: passage, le reste est pris aux passages suivants de la saison).
REVEILS_SAISONNIERS_LIMITE_PAR_PASSAGE = 200


@shared_task(name='crm.poser_reveils_saisonniers')
def poser_reveils_saisonniers_task(
        limite=REVEILS_SAISONNIERS_LIMITE_PAR_PASSAGE):
    """ALEA1 (D-ALEA-1, option a) — Enveloppe Celery Beat du réveil
    saisonnier CAD74 (`reveil_b`).

    Planifiée dans ``erp_agentique/celery.py`` (``beat_schedule``) : un
    passage quotidien borné juin → septembre. Balaye les sociétés ACTIVES
    seulement (``authentication.selectors.active_companies``) et délègue à
    ``apps.crm.services.poser_reveils_saisonniers`` — idempotent : UNE touche
    par dormant et par an, hors saison rien n'est posé. N'envoie aucun
    message : la touche suit la cadence normale (envoi manuel)."""
    import logging

    from authentication.selectors import active_companies

    from apps.crm.cadence_plan import poser_reveils_saisonniers

    logger = logging.getLogger(__name__)
    posees = 0
    for company in active_companies():
        try:
            posees += len(poser_reveils_saisonniers(company, limite=limite))
        except Exception:  # noqa: BLE001 — une société n'arrête pas les autres
            logger.warning('ALEA1 : réveil saisonnier en échec (société #%s)',
                           company.pk, exc_info=True)
    return {'posees': posees}


# ── VT9 / VTA3 — ALIAS DE TÂCHE, FENÊTRE DE DÉPLOIEMENT ──────────────────────
#
# L'assemblage des photos du toit a déménagé dans ``apps.visites.tasks`` sous
# le nom ``visites.assembler_photos_toit``. Cet alias garde l'ANCIEN nom
# joignable : au moment du déploiement, des messages portant
# ``crm.assembler_photos_toit`` peuvent encore être en vol dans Redis, et un
# worker neuf qui ne connaîtrait plus ce nom les rejetterait en silence — une
# visite resterait « assemblage en cours » pour toujours. À retirer au
# prochain groupe, une fois la file drainée.


@shared_task(name='crm.assembler_photos_toit')
def assembler_photos_toit_task(visite_id):
    """Alias déprécié — délègue à ``visites.assembler_photos_toit``."""
    from apps.visites.tasks import assembler_photos_toit_task as nouvelle

    return nouvelle(visite_id)

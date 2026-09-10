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
    from apps.crm.services import recalculer_scores_obsoletes

    return recalculer_scores_obsoletes()


#: MRY0 (lot C) — verrou anti-double-run du miroir Odoo (la passe complète dure
#: plusieurs minutes ; le beat tourne toutes les 30 min).
_ODOO_SYNC_LOCK = 'crm.sync_odoo_leads.lock'
_ODOO_SYNC_LOCK_TIMEOUT = 1500


@shared_task(name='crm.sync_odoo_leads')
def sync_odoo_leads_task():
    """MRY0 (lot C) — Enveloppe Celery Beat du miroir Odoo → ERP.

    Le miroir n'était planifié NULLE PART (ni cron, ni timer, ni beat) : la
    dernière passe datait du 01/09/2026 et le cockpit de Meryem décrochait
    silencieusement. NO-OP PROPRE quand la config Odoo est incomplète ou que
    ``ODOO_SYNC_COMPANY_SLUG`` est vide — jamais un slug en dur. Verrou cache
    contre deux passes simultanées. Odoo reste en LECTURE SEULE (JSON-2).

    ``ODOO_SYNC_ALIGN=0`` transmet ``--no-align`` : on rapatrie les leads sans
    aligner le pipeline ERP sur Odoo (le jour où Meryem travaille dans l'ERP).
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
        options = {'company': slug, 'stdout': sortie}
        if (os.environ.get('ODOO_SYNC_ALIGN', '1') or '1').strip() == '0':
            options['no_align'] = True
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


# ── VT9 — ASSEMBLAGE DES PHOTOS DU TOIT ──────────────────────────────────────
#
# Les photos du slot « toiture » sont recousues en UNE image (panorama OpenCV)
# qui servira de texture réaliste au calepinage (VT11). CE N'EST PAS DE LA 3D :
# la reconstruction d'un plan de toit depuis des photos prises AU SOL ne marche
# physiquement pas (le pan n'est jamais vu de deux points de vue) — voie
# écartée par le fondateur ; on assemble, on ne reconstruit pas.
#
# ``cv2`` est importé PARESSEUSEMENT, dans la fonction : le démarrage de Django
# ne doit jamais dépendre de la présence d'OpenCV (dépendance libre
# ``opencv-python-headless``, absente d'un environnement minimal).
#
# HONNÊTETÉ DES ÉCHECS : le stitching échoue quand les photos ne se recouvrent
# pas assez. Le message le DIT, en français, et propose la suite concrète —
# jamais un « erreur technique » opaque, jamais un résultat inventé.

#: Messages d'échec, en français, orientés « quoi faire maintenant ».
ASSEMBLAGE_MESSAGES = {
    'pas_assez': (
        "Il faut au moins deux photos du toit pour les assembler. Prenez "
        "plusieurs vues qui se chevauchent, ou choisissez UNE photo comme "
        "texture."),
    'recouvrement': (
        "Les photos du toit ne se recouvrent pas assez pour être assemblées "
        "(il faut environ la moitié de l'image en commun d'une photo à la "
        "suivante). Reprenez un balayage lent depuis un point haut, avec un "
        "fort recouvrement — ou choisissez UNE seule photo comme texture."),
    'illisible': (
        "Une des photos du toit n'a pas pu être lue. Reprenez-la, puis "
        "relancez l'assemblage."),
    'indisponible': (
        "L'assemblage des photos n'est pas disponible sur ce serveur "
        "(bibliothèque d'images absente). Choisissez UNE photo comme texture "
        "en attendant."),
    'echec': (
        "L'assemblage des photos du toit a échoué. Reprenez des photos qui se "
        "chevauchent nettement, ou choisissez UNE seule photo comme texture."),
}


def _photos_toiture(visite):
    """Les octets des photos SERVIES du slot toiture, dans l'ordre de prise."""
    from apps.records.storage import fetch_attachment

    from . import visite_checklist as checklist

    codes = [slot['code'] for slot in checklist.slots()
             if slot['categorie'] == 'toiture']
    medias = (visite.medias
              .filter(slot_code__in=codes, a_refaire=False)
              .select_related('attachment')
              .order_by('id'))
    octets = []
    for media in medias:
        data, erreur = fetch_attachment(media.attachment.file_key)
        if erreur or not data:
            return None
        octets.append(data)
    return octets


def _assembler(octets):
    """(image PNG assemblée, None) ou (None, clé de message d'échec).

    Import de ``cv2``/``numpy`` PARESSEUX : une absence de la bibliothèque est
    un échec MÉTIER annoncé, jamais un crash au démarrage.
    """
    try:
        import cv2
        import numpy as np
    except Exception:
        return None, 'indisponible'

    images = []
    for data in octets:
        image = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            return None, 'illisible'
        images.append(image)

    stitcher = cv2.Stitcher_create(cv2.Stitcher_PANORAMA)
    code, panorama = stitcher.stitch(images)
    if code != cv2.Stitcher_OK or panorama is None:
        if code == getattr(cv2, 'Stitcher_ERR_NEED_MORE_IMGS', 1):
            return None, 'recouvrement'
        return None, 'echec'
    ok, encode = cv2.imencode('.png', panorama)
    if not ok:
        return None, 'echec'
    return encode.tobytes(), None


@shared_task(name='crm.assembler_photos_toit')
def assembler_photos_toit_task(visite_id):
    """VT9 — assemble les photos du toit d'UNE visite. Idempotent, sans crash.

    La machine d'états est la seule sortie visible : ``en_cours`` (posé par
    l'API avant l'envoi) → ``ok`` (avec ``photo_toit_key``) ou ``echec`` (avec
    un message honnête). Aucune exception ne remonte à Celery : un échec est
    une INFORMATION rendue au commercial, pas une tâche à rejouer en boucle.
    """
    from django.core.files.base import ContentFile

    from apps.records.storage import store_attachment

    from .models import VisiteTerrain

    visite = VisiteTerrain.objects.filter(pk=visite_id).first()
    if visite is None:
        return {'visite': visite_id, 'etat': 'introuvable'}

    def _echec(cle):
        visite.assemblage_etat = VisiteTerrain.Assemblage.ECHEC
        visite.assemblage_erreur = ASSEMBLAGE_MESSAGES[cle]
        visite.save(update_fields=['assemblage_etat', 'assemblage_erreur'])
        return {'visite': visite_id, 'etat': 'echec', 'motif': cle}

    octets = _photos_toiture(visite)
    if octets is None:
        return _echec('illisible')
    if len(octets) < 2:
        return _echec('pas_assez')

    try:
        image, cle = _assembler(octets)
    except Exception:  # pragma: no cover - défensif : jamais un 500 silencieux
        return _echec('echec')
    if image is None:
        return _echec(cle)

    fichier = ContentFile(image, name=f'toit-visite-{visite.pk}.png')
    meta, message = store_attachment(fichier, company=visite.company)
    if meta is None:
        return _echec('echec')

    visite.photo_toit_key = meta['file_key']
    visite.assemblage_etat = VisiteTerrain.Assemblage.OK
    visite.assemblage_erreur = ''
    visite.save(update_fields=['photo_toit_key', 'assemblage_etat',
                               'assemblage_erreur'])
    return {'visite': visite_id, 'etat': 'ok'}

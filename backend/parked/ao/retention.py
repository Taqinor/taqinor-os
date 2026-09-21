"""AOF168 — Politiques de RÉTENTION des artefacts d'appels d'offres.

Ce que ce module purge, et pourquoi c'est le bon périmètre
---------------------------------------------------------
Un dossier d'appel d'offres accumule des artefacts LOURDS et à durée de vie
COURTE : photos de relevé de toiture, images annotées de questions, plans
sources scannés. Une fois le marché perdu ou abandonné, ces fichiers ne servent
plus à rien — mais leur suppression est irréversible et le dossier reste
opposable, alors rien n'est purgé par défaut.

Ce que ce module NE purge JAMAIS, et pourquoi
---------------------------------------------
* **Aucune ligne métier.** Ni l'appel d'offres, ni le relevé, ni la question,
  ni une variante de calepinage, ni un bordereau. Un dossier déposé reste
  reconstituable : ce sont les FICHIERS qui partent, jamais la preuve.
* **Aucun AO en cours ni gagné.** Seuls ``perdu`` et ``abandonne`` sont
  éligibles. Purger les pièces d'un marché EN EXÉCUTION serait détruire les
  pièces d'un chantier en cours.
* **Rien par défaut.** Chaque fenêtre vaut ``0`` = OFF tant que le fondateur
  n'a pas posé un réglage. Une purge activée « par surprise » sur une mise à
  jour serait la pire régression possible de ce module.

Contrat du registre partagé (YOPSB10, ``core.retention``) : chaque politique
est ``sweep(now, apply_) -> int``. ``apply_=False`` est un DRY-RUN — elle
compte ce qu'elle SUPPRIMERAIT sans rien toucher. Le scoping par société est de
la responsabilité de la politique : ici il est naturel (chaque objet AO porte
son ``company``), et le balayage traverse toutes les sociétés comme le prévoit
``run_all_policies``.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

__all__ = [
    'DEFAULT_PHOTOS_RELEVE_PURGE_DAYS', 'DEFAULT_IMAGES_QUESTIONS_PURGE_DAYS',
    'DEFAULT_PLANS_SOURCE_PURGE_DAYS', 'STATUTS_PURGEABLES',
    'purger_photos_releve', 'purger_images_questions',
    'purger_plans_source', 'POLITIQUES',
]

#: Fenêtres par défaut, en jours. **0 = OFF** — rien n'est purgé tant que le
#: fondateur n'a pas posé ``AO_*_PURGE_DAYS`` dans les réglages.
DEFAULT_PHOTOS_RELEVE_PURGE_DAYS = 0
DEFAULT_IMAGES_QUESTIONS_PURGE_DAYS = 0
DEFAULT_PLANS_SOURCE_PURGE_DAYS = 0

#: SEULS ces statuts d'appel d'offres rendent leurs artefacts purgeables.
#: ``gagne`` en est ABSENT à dessein : c'est un marché en exécution.
STATUTS_PURGEABLES = ('perdu', 'abandonne')


def _cutoff(now, jours):
    """Date de coupure, ou ``None`` quand la fenêtre est OFF (``jours <= 0``)."""
    from datetime import timedelta

    if not jours or jours <= 0:
        return None
    return now - timedelta(days=int(jours))


def _ao_purgeables(now, jours):
    """AO clos (perdu/abandonné) dont la coupure est franchie, ou ``None``.

    La coupure est mesurée sur ``date_creation``, PAS sur une date de clôture :
    ``AppelOffre`` n'en porte aucune aujourd'hui. C'est délibérément le choix
    CONSERVATEUR — la date de création est toujours antérieure ou égale à la
    clôture, donc la fenêtre réellement observée est toujours PLUS LONGUE que
    celle demandée, jamais plus courte. Le jour où un champ de clôture
    existera, basculer dessus RACCOURCIRA la rétention : ce sera un changement
    de comportement à annoncer, pas un détail.
    """
    from .models import AppelOffre

    cutoff = _cutoff(now, jours)
    if cutoff is None:
        return None
    return AppelOffre.objects.filter(
        statut__in=STATUTS_PURGEABLES, date_creation__lt=cutoff)


def purger_photos_releve(now, jours, apply_=True):
    """Détache et supprime les PHOTOS des relevés d'AO clos.

    Le ``ReleveAO`` lui-même est CONSERVÉ : sa date, ses participants et sa
    mention de cartouche restent la base opposable du plan. Seules les images
    partent — ce sont elles qui pèsent, pas la preuve.
    """
    from apps.records.models import Attachment

    from .models import ReleveAO

    aos = _ao_purgeables(now, jours)
    if aos is None:
        return 0
    releves = ReleveAO.objects.filter(appel_offre__in=aos)
    ids = set()
    for releve in releves.prefetch_related('photos'):
        ids.update(photo.pk for photo in releve.photos.all())
    if not ids:
        return 0
    if not apply_:
        return len(ids)
    for releve in releves:
        releve.photos.clear()
    Attachment.objects.filter(pk__in=ids).delete()
    logger.info('ao.retention: %d photo(s) de relevé purgée(s)', len(ids))
    return len(ids)


def purger_images_questions(now, jours, apply_=True):
    """Détache et supprime les IMAGES ANNOTÉES des questions d'AO clos.

    La question, son impact chiffré, sa réponse et sa décision RESTENT : c'est
    l'historique qui explique un compte. Seul le PNG annoté disparaît.
    """
    from apps.records.models import Attachment

    from .models import QuestionAO

    aos = _ao_purgeables(now, jours)
    if aos is None:
        return 0
    questions = QuestionAO.objects.filter(
        serie__appel_offre__in=aos).exclude(image__isnull=True)
    ids = set(questions.values_list('image_id', flat=True))
    if not ids:
        return 0
    if not apply_:
        return len(ids)
    questions.update(image=None)
    Attachment.objects.filter(pk__in=ids).delete()
    logger.info('ao.retention: %d image(s) de question purgée(s)', len(ids))
    return len(ids)


def purger_plans_source(now, jours, apply_=True):
    """Détache et supprime les FICHIERS des plans sources d'AO clos.

    Le ``PlanSource`` reste (calibrage, empreinte SHA-256, provenance) : c'est
    ce qui permet de dire de quel document venait une cote. Le scan, lui, part.

    ``PlanSource`` n'a PAS de FK directe vers l'appel d'offres : il pend d'une
    toiture OU d'un bâtiment (les deux nullables). On remonte donc par les deux
    chemins — un plan rattaché par le seul bâtiment serait sinon oublié.
    """
    from django.db.models import Q

    from apps.records.models import Attachment

    from .models import PlanSource

    aos = _ao_purgeables(now, jours)
    if aos is None:
        return 0
    plans = (PlanSource.objects
             .filter(Q(batiment__appel_offre__in=aos)
                     | Q(toiture__batiment__appel_offre__in=aos))
             .exclude(attachment__isnull=True))
    ids = set(plans.values_list('attachment_id', flat=True))
    if not ids:
        return 0
    if not apply_:
        return len(ids)
    plans.update(attachment=None)
    Attachment.objects.filter(pk__in=ids).delete()
    logger.info('ao.retention: %d plan(s) source purgé(s)', len(ids))
    return len(ids)


#: Nom de politique -> (fonction, nom du réglage, défaut). Une SEULE source :
#: ``apps.py`` boucle dessus, et le test la relit — impossible d'enregistrer
#: une politique que la documentation ignore, ou l'inverse.
POLITIQUES = (
    ('ao_photos_releve', purger_photos_releve,
     'AO_PHOTOS_RELEVE_PURGE_DAYS', DEFAULT_PHOTOS_RELEVE_PURGE_DAYS),
    ('ao_images_questions', purger_images_questions,
     'AO_IMAGES_QUESTIONS_PURGE_DAYS', DEFAULT_IMAGES_QUESTIONS_PURGE_DAYS),
    ('ao_plans_source', purger_plans_source,
     'AO_PLANS_SOURCE_PURGE_DAYS', DEFAULT_PLANS_SOURCE_PURGE_DAYS),
)


def register():
    """Enregistre les politiques AO dans le registre partagé (idempotent)."""
    from core.retention import register_retention_policy, setting_days

    for nom, fonction, reglage, defaut in POLITIQUES:
        register_retention_policy(
            nom,
            (lambda f, r, d: lambda now, apply_: f(
                now, setting_days(r, d), apply_))(fonction, reglage, defaut),
        )

"""Sélecteurs de lecture de ``records`` (point d'entrée cross-app) — TCH16.

L'app Tâches (``apps.taches``) lit ici les activités ERP d'un utilisateur sans
importer ``records.models`` ni ``records.views`` : Ma journée, la conversion des
à-faire personnels, l'indicateur « peut clore » d'une ligne d'activité.

Aucune règle n'est recopiée : le report (snooze) est celui de
``ActivityViewSet.mine`` / ``ma_file``, l'exclusion des cibles archivées est
``views.sans_cibles_archivees``, la clôture est la permission même de
``POST records/activities/<id>/done/`` (``IsResponsableOrAdmin`` sur
``ActivityViewSet``). Tout est filtré par la société ET par l'utilisateur ; un
à-faire personnel n'est rendu qu'à son CRÉATEUR, même s'il est assigné à un
autre (XKB4). ``records`` reste une app de FONDATION : aucun import d'une app
métier ici.
"""
from types import SimpleNamespace

from django.db import models
from django.utils import timezone

from .models import Activity


def _activites_de(user):
    """Activités de la société de ``user`` (aucune sans société)."""
    company_id = getattr(user, 'company_id', None)
    if not company_id or not getattr(user, 'pk', None):
        return Activity.objects.none()
    return Activity.objects.filter(company_id=company_id)


def activites_ouvertes_pour(user, jusquau=None):
    """Activités ERP OUVERTES de ``user`` dues au plus tard ``jusquau``.

    Mêmes lignes que ``mine`` (assignées à ``user``, non faites, report échu,
    lead cible archivé ou supprimé exclu) restreintes à ``due_date <= jusquau``
    (une activité sans date n'y est jamais), MOINS les à-faire personnels créés
    par un autre (XKB4). ``jusquau`` vaut aujourd'hui par défaut. Rend un
    ``QuerySet`` dans l'ordre du modèle (faites, échéance, id)."""
    from .views import sans_cibles_archivees

    if jusquau is None:
        jusquau = timezone.localdate()
    qs = _activites_de(user).select_related(
        'activity_type', 'content_type').filter(
        assigned_to_id=user.pk, done=False, due_date__lte=jusquau)
    # Règle de report de ``mine`` (views.py, VX85(a)) : échu = réapparu.
    qs = qs.filter(
        models.Q(snoozed_until__isnull=True)
        | models.Q(snoozed_until__lte=timezone.now().date()))
    qs = qs.exclude(
        models.Q(personnelle=True) & ~models.Q(created_by_id=user.pk))
    return sans_cibles_archivees(qs)


def nb_a_faire_personnels(user):
    """Nombre d'à-faire personnels CONVERTIBLES de ``user`` : créés par lui,
    assignés à lui, non faits (un à-faire assigné à un collègue reste dans
    Activités, D-TCH-1)."""
    return _activites_de(user).filter(
        personnelle=True, created_by_id=user.pk, assigned_to_id=user.pk,
        done=False).count()


def peut_cloturer_activites(user):
    """Vrai ssi ``POST records/activities/<id>/done/`` n'est pas refusé (403)
    à ``user`` : la permission même de la vue, jamais une copie."""
    from .views import ActivityViewSet

    vue = ActivityViewSet()
    vue.action = 'marquer_fait'  # l'action DRF de ``done/``
    requete = SimpleNamespace(user=user, method='POST')
    return all(p.has_permission(requete, vue) for p in vue.get_permissions())


def a_faire_personnels_de(user, ids=None):
    """TCH73 — à-faire personnels CRÉÉS par ``user`` dans sa société, dans
    TOUS leurs états (faits, assignés à un collègue compris) : la conversion
    en tâches y lit ses raisons de refus. ``ids`` restreint aux identifiants
    donnés. Jamais l'à-faire d'un autre créateur (XKB4)."""
    qs = _activites_de(user).filter(personnelle=True, created_by_id=user.pk)
    return qs if ids is None else qs.filter(pk__in=list(ids))

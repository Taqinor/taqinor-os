"""Tâches planifiées (Celery Beat) de l'app CPQ.

Toute la logique de temps raisonne en date CIVILE (``timezone.localdate()``),
comme ``apps/ventes/scheduled.py`` (même famille de jobs, même fuseau
Africa/Casablanca posé globalement par ``erp_agentique.celery``). Chaque tâche
est SÛRE à ré-exécuter (idempotente) et jamais destructive au-delà de ce que sa
docstring décrit explicitement.
"""
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


def _activity_type(company, nom, *, icone='clock', ordre=90):
    """Réutilise/crée un ``records.ActivityType`` nommé pour la société
    (même patron que ``ventes.scheduled._dispatch_relance_canal``)."""
    from apps.records.models import ActivityType
    atype = ActivityType.objects.filter(company=company, nom=nom).first()
    if atype is None:
        atype = ActivityType.objects.create(
            company=company, nom=nom, icone=icone, ordre=ordre,
            est_systeme=True)
    return atype


@shared_task(name='cpq.expire_prix_contractuels')
def expire_prix_contractuels():
    """NTCPQ32 — pour chaque ``PrixContractuel`` dont ``date_fin`` est
    dépassée, pose UNE ``records.Activity`` de rappel (« Prix contractuel
    expiré ») assignée au commercial responsable du client (créateur du prix
    négocié, à défaut créateur du client) — jamais de suppression, jamais
    d'email automatique non demandé.

    Idempotent : une seule activité par prix expiré, quel que soit le nombre
    de fois où le job tourne (dédup via ``content_type``/``object_id`` sur le
    même ``ActivityType``). Renvoie le nombre d'activités posées."""
    from django.contrib.contenttypes.models import ContentType
    from django.utils import timezone
    from apps.records.models import Activity
    from .models import PrixContractuel

    today = timezone.localdate()
    ct = ContentType.objects.get_for_model(PrixContractuel)
    poses = 0

    candidats = (PrixContractuel.objects
                 .filter(date_fin__isnull=False, date_fin__lt=today)
                 .select_related('client', 'created_by', 'produit'))
    for prix in candidats:
        deja = Activity.objects.filter(
            content_type=ct, object_id=prix.id,
            summary='Prix contractuel expiré').exists()
        if deja:
            continue
        atype = _activity_type(prix.company, 'Prix contractuel expiré')
        assigned_to = prix.created_by or getattr(
            prix.client, 'created_by', None)
        Activity.objects.create(
            company=prix.company, content_type=ct, object_id=prix.id,
            activity_type=atype,
            summary='Prix contractuel expiré',
            note=(f"Le prix négocié de {prix.prix_ht} pour "
                  f"{getattr(prix.client, 'nom', prix.client_id)} / "
                  f"{getattr(prix.produit, 'nom', prix.produit_id)} a expiré "
                  f"le {prix.date_fin.isoformat()}."),
            due_date=today, assigned_to=assigned_to)
        poses += 1

    logger.info('cpq.expire_prix_contractuels: %s activité(s) posée(s)', poses)
    return poses

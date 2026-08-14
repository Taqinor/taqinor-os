"""Tâches planifiées (Celery Beat) de l'app CPQ.

Toute la logique de temps raisonne en date CIVILE (``timezone.localdate()``),
comme ``apps/ventes/scheduled.py`` (même famille de jobs, même fuseau
Africa/Casablanca posé globalement par ``erp_agentique.celery``). Chaque tâche
est SÛRE à ré-exécuter (idempotente) et jamais destructive au-delà de ce que sa
docstring décrit explicitement.
"""
import logging
from datetime import timedelta

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


@shared_task(name='cpq.relancer_approbations_en_attente')
def relancer_approbations_en_attente():
    """NTCPQ33 — parcourt les ``EtapeApprobationDevis`` ``en_attente`` depuis
    plus de ``N`` jours (``ParametresCPQ.delai_relance_approbation_jours``,
    défaut 2) et envoie une notification ``apps.notifications`` à
    l'approbateur assigné.

    Idempotent via ``derniere_relance_le`` sur l'étape : jamais plus d'une
    relance par 24h par étape, même si le job tourne plusieurs fois le même
    jour. Une étape sans approbateur assigné (personne n'a encore réclamé
    l'étape) est ignorée — rien à notifier. Renvoie le nombre de relances
    envoyées."""
    from django.utils import timezone
    from apps.notifications.models import EventType
    from apps.notifications.services import notify
    from .models import EtapeApprobationDevis, ParametresCPQ

    now = timezone.now()
    relances = 0

    candidates = (EtapeApprobationDevis.objects
                  .filter(statut=EtapeApprobationDevis.Statut.EN_ATTENTE)
                  .select_related('devis', 'company', 'approbateur'))
    for etape in candidates:
        if etape.approbateur_id is None:
            continue
        delai = ParametresCPQ.get_or_default(
            etape.company).delai_relance_approbation_jours
        seuil = etape.date_creation + timedelta(days=delai)
        if now < seuil:
            continue
        if (etape.derniere_relance_le is not None
                and (now - etape.derniere_relance_le) < timedelta(hours=24)):
            continue
        try:
            devis_ref = getattr(etape.devis, 'reference', etape.devis_id)
            notify(
                etape.approbateur, EventType.APPROVAL_REMINDER,
                f'Approbation en attente — devis {devis_ref}',
                body=(f"L'étape {etape.niveau} d'approbation de remise du "
                      f"devis {devis_ref} attend votre décision depuis "
                      f"plus de {delai} jour(s)."),
                link=f'/ventes/devis?devis={etape.devis_id}',
                company=etape.company)
        except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
            logger.exception(
                'cpq.relancer_approbations_en_attente: notify échoué '
                '(étape %s)', etape.id)
            continue
        etape.derniere_relance_le = now
        etape.save(update_fields=['derniere_relance_le'])
        relances += 1

    logger.info(
        'cpq.relancer_approbations_en_attente: %s relance(s) envoyée(s)',
        relances)
    return relances


# NTCPQ34 — inactivité au-delà de laquelle une session configurateur sans
# devis lié est purgeable (jours). Une session ayant abouti à un devis (même
# brouillon) n'est JAMAIS purgée, quel que soit son âge.
PURGE_SESSION_INACTIVITE_JOURS = 30


@shared_task(name='cpq.purger_sessions_configurateur_abandonnees')
def purger_sessions_configurateur_abandonnees():
    """NTCPQ34 — supprime les ``SessionConfigurateur``/``ReponseConfigurateur``
    (NTCPQ9) inactives depuis plus de
    ``PURGE_SESSION_INACTIVITE_JOURS`` jours SANS devis généré (NTCPQ10).

    Ne touche JAMAIS une session ayant abouti à un devis (``devis_id`` non
    nul), même brouillon — purge additive-safe : aucune donnée métier
    engagée n'est jamais perdue. Renvoie le nombre de sessions supprimées."""
    from django.utils import timezone
    from .models import SessionConfigurateur

    seuil = timezone.now() - timedelta(days=PURGE_SESSION_INACTIVITE_JOURS)
    candidates = SessionConfigurateur.objects.filter(
        devis__isnull=True, updated_at__lt=seuil)
    count = candidates.count()
    if count:
        candidates.delete()

    logger.info(
        'cpq.purger_sessions_configurateur_abandonnees: %s session(s) '
        'purgée(s)', count)
    return count

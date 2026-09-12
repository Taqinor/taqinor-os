"""Tâches planifiées (Celery beat) du module PAIE.

Autodécouvert par ``erp_agentique.celery`` (``autodiscover_tasks()``) ; les
entrées ``beat_schedule`` et le routage vers la file ``scheduled`` vivent dans
``erp_agentique/celery.py`` et ``erp_agentique/settings/base.py``.

Multi-tenant : chaque balayage boucle sur les sociétés ACTIVES
(``authentication.selectors.active_companies()`` — AUD415/SCA19 : un tenant
suspendu ou en fermeture n'est plus balayé), jamais une société lue d'un corps
de requête. Une exception sur une société n'empêche jamais les suivantes
(best-effort, journalisée).

DONNÉE SENSIBLE — aucune de ces tâches ne journalise ni ne notifie un MONTANT
de salaire : les messages nomment une échéance ou un profil, jamais une somme.
"""
import logging
from datetime import timedelta

from celery import shared_task

logger = logging.getLogger(__name__)

#: Fenêtres de rappel avant la date limite d'une déclaration (J-7, J-3, J-0).
#: Chaque seuil notifie AU PLUS UNE FOIS par échéance — l'idempotence est
#: portée par une entrée de chatter ``records`` (aucun modèle paie dédié,
#: aucune migration).
SEUILS_RAPPEL_ECHEANCE = (7, 3, 0)

#: Préfixe du marqueur d'idempotence posé sur le chatter de l'échéance.
CHAMP_RAPPEL_ECHEANCE = 'rappel_echeance_j'

EVENEMENT_RAPPEL_ECHEANCE = 'paie_echeance_rappel'


def _destinataires_paie(company, event_type):
    """Destinataires d'une notification paie : ``paie_gerer`` + repli manager.

    L'UNION de deux ensembles, dédupliquée :

    * les titulaires du rôle fin ``paie_gerer`` (ce que la tâche vise) ;
    * le routage standard ``notifications.resolve_recipients`` (règles de
      routage de la société, à défaut les managers actifs) — le repli
      historique déjà utilisé par les autres notifications de la paie.
    """
    from django.contrib.auth import get_user_model

    from apps.notifications import services as notif_services

    utilisateurs = {}
    for user in notif_services.resolve_recipients(company, event_type):
        utilisateurs[user.pk] = user
    User = get_user_model()
    for user in User.objects.filter(
            company=company, is_active=True,
            role__permissions__contains=['paie_gerer']).select_related('role'):
        utilisateurs[user.pk] = user
    return list(utilisateurs.values())


def _rappel_deja_pose(echeance, seuil):
    """Vrai si le rappel de ce SEUIL a déjà été posé pour cette échéance.

    Le marqueur est une entrée de chatter ``records`` (ARC8) sur l'échéance :
    pas de modèle paie dédié, pas de migration, et la trace reste lisible par
    un humain dans l'historique de l'objet.
    """
    from django.contrib.contenttypes.models import ContentType

    from apps.records.models import Activity

    ct = ContentType.objects.get_for_model(echeance.__class__)
    return Activity.objects.filter(
        content_type=ct, object_id=echeance.pk,
        field=f'{CHAMP_RAPPEL_ECHEANCE}{seuil}',
    ).exists()


def rappeler_echeances_declaratives_company(company, *, today=None):
    """Rappels J-7/J-3/J-0 des échéances déclaratives d'UNE société (NTPAY25).

    Sélectionne les ``EcheanceDeclarative`` dont la ``date_limite`` tombe
    EXACTEMENT dans l'une des fenêtres et qui ne sont pas encore déposées
    (``statut`` ≠ déposée/payée, cf. NTPAY5). Pour chacune, notifie les
    gestionnaires de paie UNE SEULE FOIS par jour-seuil : le marqueur de
    chatter rend le re-run du lendemain (ou d'un rattrapage manuel)
    strictement sans effet.

    ``today`` est injectable (tests déterministes). Renvoie la liste des
    ``(echeance, seuil)`` réellement notifiés.
    """
    from django.utils import timezone as dj_timezone

    from apps.notifications import services as notif_services
    from apps.records import services as records_services

    from .models import EcheanceDeclarative

    if today is None:
        today = dj_timezone.localdate()

    dates_cibles = {
        today + timedelta(days=seuil): seuil
        for seuil in SEUILS_RAPPEL_ECHEANCE
    }
    echeances = (
        EcheanceDeclarative.objects
        .filter(company=company, date_limite__in=list(dates_cibles))
        .exclude(statut__in=[EcheanceDeclarative.STATUT_DEPOSEE,
                             EcheanceDeclarative.STATUT_PAYEE])
        .select_related('periode')
    )

    notifies = []
    for echeance in echeances:
        seuil = dates_cibles[echeance.date_limite]
        if _rappel_deja_pose(echeance, seuil):
            continue
        libelle = echeance.get_type_echeance_display()
        periode = echeance.periode
        quand = ("aujourd'hui" if seuil == 0 else f'dans {seuil} jour(s)')
        titre = f'Échéance paie {libelle} — à déposer {quand}'
        corps = (
            f'Période {periode.mois:02d}/{periode.annee} — date limite '
            f'{echeance.date_limite}. Aucun dépôt enregistré à ce jour.')
        try:
            notif_services.notify_many(
                _destinataires_paie(company, EVENEMENT_RAPPEL_ECHEANCE),
                EVENEMENT_RAPPEL_ECHEANCE, title=titre, body=corps,
                company=company)
        except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
            logger.warning(
                'paie.rappeler_echeances_declaratives : notification échouée '
                "pour l'échéance #%s", echeance.pk, exc_info=True)
        # Le marqueur est posé MÊME si la diffusion a échoué : sans quoi un
        # canal en panne re-notifierait tous les jours la même échéance.
        records_services.log_activity(
            echeance, 'note', company=company,
            field=f'{CHAMP_RAPPEL_ECHEANCE}{seuil}',
            field_label=f'Rappel J-{seuil}',
            body=f'{titre} — {corps}')
        notifies.append((echeance, seuil))
    return notifies


@shared_task(name='paie.rappeler_echeances_declaratives')
def rappeler_echeances_declaratives():
    """NTPAY25 — balayage quotidien des échéances déclaratives à venir.

    ``EcheanceDeclarative`` (XPAI6) suivait le calendrier mais rien ne
    prévenait PROACTIVEMENT : on découvrait le retard une fois dépassé
    (``notifier_echeances_en_retard``). Ce balayage prévient AVANT.
    """
    from authentication.selectors import active_companies

    total = 0
    for company in active_companies():  # AUD415/SCA19 — pas les suspendus
        try:
            total += len(rappeler_echeances_declaratives_company(company))
        except Exception:  # noqa: BLE001 — une société ne bloque pas les autres
            logger.warning(
                'paie.rappeler_echeances_declaratives : échec pour la '
                'société #%s', getattr(company, 'pk', '?'), exc_info=True)
    return total

"""NTIDE40 — digest (récapitulatif) du feedback produit non-lu (canal
founder, ``apps.innovation.FeedbackProduit``), par thème.

Une SEULE tâche Celery Beat (``feedback_digest_run``) tourne QUOTIDIENNEMENT ;
pour chaque société ayant ``InnovationSettings.feedback_digest_actif=True``
(désactivé par défaut, NTIDE7 pattern), elle notifie les gérants/staff SAUF
si la fréquence configurée est ``hebdo`` ET que ce n'est pas lundi (même
principe que ``apps.notifications.digests`` N76, mais gating PAR SOCIÉTÉ au
lieu d'un couple de tâches beat quotidien+hebdo séparées — une société ne
peut avoir qu'UNE fréquence à la fois).

DÉFENSIF : une société en erreur n'interrompt jamais les suivantes (même
convention que ``apps.notifications.digests._run_digest``). NO-OP silencieux
si aucun feedback non-lu (jamais de notification vide)."""
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


def _societes_digest_actif():
    """(company, reglages) pour chaque société ayant activé le digest
    feedback produit (NTIDE7/NTIDE40). Liste vide si erreur ou aucune."""
    try:
        from .models import InnovationSettings

        qs = (InnovationSettings.objects
              .filter(feedback_digest_actif=True, company__actif=True)
              .select_related('company'))
        return [(r.company, r) for r in qs]
    except Exception:  # pragma: no cover - défensif
        logger.warning(
            'feedback_digest: chargement des sociétés impossible', exc_info=True)
        return []


def _destinataires(company):
    """Gérants/staff destinataires (même patron que
    ``apps.notifications.digests._recipients``)."""
    try:
        from authentication.models import CustomUser
        base = CustomUser.objects.filter(company=company, is_active=True)
        managers = [
            u for u in base
            if getattr(u, 'is_admin_role', False)
            or getattr(u, 'role_tier', None) in ('admin', 'responsable')
        ]
        return managers or list(base)
    except Exception:  # pragma: no cover - défensif
        logger.warning(
            'feedback_digest: chargement des destinataires impossible',
            exc_info=True)
        return []


def _format_body(resume):
    lignes = ['Feedback produit NON-LU, par thème :', '']
    for r in resume:
        if r['non_lus'] <= 0:
            continue
        lignes.append(
            f"• {r['theme_display']} : {r['non_lus']} non-lu(s) "
            f"({r['total']} au total)")
        for titre in r['exemples'][:2]:
            lignes.append(f'   — {titre}')
    return '\n'.join(lignes)


@shared_task(name='innovation.feedback_digest_run')
def feedback_digest_run():
    """NTIDE40 — récapitulatif du feedback non-lu, gated par société via
    ``InnovationSettings.feedback_digest_actif``/``feedback_digest_frequence``.
    Renvoie le nombre de notifications émises."""
    from django.utils import timezone

    from . import selectors
    from .models import InnovationSettings

    today_is_monday = timezone.now().weekday() == 0
    emitted = 0
    for company, reglages in _societes_digest_actif():
        try:
            if (reglages.feedback_digest_frequence
                    == InnovationSettings.Frequence.HEBDO
                    and not today_is_monday):
                continue
            resume = selectors.feedback_by_theme(company)
            non_lus_total = sum(r['non_lus'] for r in resume)
            if non_lus_total <= 0:
                continue
            destinataires = _destinataires(company)
            if not destinataires:
                continue

            from apps.notifications.models import EventType
            from apps.notifications.services import notify

            body = _format_body(resume)
            for user in destinataires:
                if notify(
                        user, EventType.FEEDBACK_DIGEST,
                        'Récapitulatif feedback produit', body=body,
                        link='/innovation/tableau-bord',
                        company=company) is not None:
                    emitted += 1
        except Exception:  # pragma: no cover - défensif par société
            logger.warning('feedback_digest: échec pour la société %s',
                           getattr(company, 'pk', None), exc_info=True)
            continue
    logger.info('feedback_digest_run: %s notification(s) émise(s)', emitted)
    return emitted

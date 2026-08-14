"""NTLOG38 — Beat Celery quotidien : rappel J-3 sur les `EtapeTransport` en
retard (`date_prevue` dépassée, `statut_etape` != fait).

Notifie le responsable transport (repli responsables/admins actifs de la
société, motif `apps.sav.tasks._responsables`), best-effort, UNE SEULE fois
par étape et par jour (idempotence : une `Notification` déjà émise le jour
même pour cette étape ne redéclenche jamais un doublon — vérifié par
`link`+`created_at__date`).

Autodécouvert par `erp_agentique.celery` (`autodiscover_tasks()`), comme
`apps.sav.tasks`/`apps.flotte.tasks`.

Multi-tenant : boucle par société active (`active_companies()`, SCA19) ; une
société qui échoue n'empêche jamais les suivantes (best-effort, journalisé).
"""
import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)

_EVENT_TYPE = 'transport_etape_retard'


def _lien_etape(etape):
    """Lien stable vers l'ordre parent d'une étape — DOUBLE comme clé
    d'idempotence (une `Notification` du jour portant ce même lien =
    étape déjà notifiée aujourd'hui, motif documenté en tête de module)."""
    return f'/transport/ordres?ordre={etape.ordre_id}&etape={etape.id}'


def _responsables(company):
    """Responsables/admins actifs de la société (destinataires de la
    notification). Repli sur tous les actifs si aucun palier trouvé — même
    logique que `apps.sav.tasks._responsables`."""
    try:
        from authentication.models import CustomUser
        base = list(CustomUser.objects.filter(company=company, is_active=True))
    except Exception:  # pragma: no cover - défensif
        return []
    managers = [
        u for u in base
        if getattr(u, 'is_admin_role', False)
        or getattr(u, 'role_tier', None) in ('admin', 'responsable')
    ]
    return managers or base


@shared_task(name='transport.check_etapes_transport_retard')
def check_etapes_transport_retard():
    """NTLOG38 — pour chaque société active, notifie le(s) responsable(s)
    transport de chaque `EtapeTransport` en retard (`date_prevue` < demain,
    `statut_etape` != fait), au plus UNE fois par étape par jour."""
    from authentication.selectors import active_companies

    from apps.notifications.models import Notification
    from apps.notifications.services import notify

    from .models import EtapeTransport

    today = timezone.localdate()
    total_societes = 0
    total_notifiees = 0

    for company in active_companies():
        try:
            etapes_retard = list(
                EtapeTransport.objects.filter(
                    company=company, date_prevue__lt=today,
                ).exclude(statut_etape=EtapeTransport.StatutEtape.FAIT)
                .select_related('ordre'))
        except Exception:  # pragma: no cover - défensif, isolation société
            logger.warning(
                'transport.check_etapes_transport_retard: échec société %s',
                company.pk, exc_info=True)
            continue
        total_societes += 1
        if not etapes_retard:
            continue

        responsables = _responsables(company)
        for etape in etapes_retard:
            lien = _lien_etape(etape)
            deja_notifiee = Notification.objects.filter(
                company=company, event_type=_EVENT_TYPE, link=lien,
                created_at__date=today).exists()
            if deja_notifiee:
                continue

            titre = (
                f"Étape de transport en retard — "
                f"{etape.ordre.numero or f'#{etape.ordre_id}'}")
            corps = (
                f"L'étape {etape.sequence} ({etape.get_type_etape_display()}) "
                f"prévue le {etape.date_prevue} n'est toujours pas clôturée.")
            for user in responsables:
                try:
                    notify(
                        user, _EVENT_TYPE, titre, body=corps, link=lien,
                        company=company)
                except Exception:  # pragma: no cover - défensif
                    logger.warning(
                        'transport.check_etapes_transport_retard: '
                        'notification échouée vers %s', user, exc_info=True)
            total_notifiees += 1

    logger.info(
        'transport.check_etapes_transport_retard: %s société(s) traitée(s), '
        '%s étape(s) notifiée(s)', total_societes, total_notifiees)
    return {'societes': total_societes, 'etapes_notifiees': total_notifiees}


# ── NTLOG39 — Beat mensuel : archivage (jamais suppression) des ordres ──────
# livrés anciens.

@shared_task(name='transport.archiver_ordres_transport_anciens')
def archiver_ordres_transport_anciens():
    """NTLOG39 — pour chaque société active, marque `archive=True` les
    `OrdreTransport` en statut LIVRÉ dont `updated_at` (dernière mise à jour
    — pour un ordre livré non retouché depuis, cela correspond à son passage
    en LIVRE via `services.recalculer_statut_ordre`) dépasse
    `ParametresTransport.archive_ordres_apres_mois` mois (défaut 24). JAMAIS
    de suppression physique — seulement exclu des listes par défaut
    (`OrdreTransportViewSet.get_queryset`, `?inclure_archives=1` pour les
    revoir). Idempotent : un ordre déjà archivé n'est pas re-traité."""
    from authentication.selectors import active_companies

    from .models import OrdreTransport, ParametresTransport

    total_societes = 0
    total_archives = 0
    maintenant = timezone.now()

    for company in active_companies():
        try:
            seuil_mois = ParametresTransport.for_company(
                company).archive_ordres_apres_mois
            seuil_date = maintenant - timezone.timedelta(days=seuil_mois * 30)
            nb = OrdreTransport.objects.filter(
                company=company, statut=OrdreTransport.Statut.LIVRE,
                archive=False, updated_at__lt=seuil_date,
            ).update(archive=True)
        except Exception:  # pragma: no cover - défensif, isolation société
            logger.warning(
                'transport.archiver_ordres_transport_anciens: échec société '
                '%s', company.pk, exc_info=True)
            continue
        total_societes += 1
        total_archives += nb

    logger.info(
        'transport.archiver_ordres_transport_anciens: %s société(s) '
        'traitée(s), %s ordre(s) archivé(s)', total_societes, total_archives)
    return {'societes': total_societes, 'ordres_archives': total_archives}

"""GED25 — Tâches Celery de la GED (purge automatique de la corbeille).

Autodécouvert par `erp_agentique.celery` (`autodiscover_tasks()`), comme
`apps.ventes.tasks`. Toute la logique métier vit dans `services` (testable sans
Celery) ; ces tâches ne sont qu'une fine enveloppe planifiable.

POLITIQUE DE SÛRETÉ (GED25) :
  * DRY-RUN PAR DÉFAUT. La tâche planifiée ne SUPPRIME RIEN tant que
    `settings.GED_PURGE_AUTO_APPLY` n'est pas explicitement vrai. Par défaut
    elle se contente de COMPTER/LOGGER ce qui SERAIT purgé (signal, jamais
    destructif) — exactement l'esprit « dry-run d'abord » du plan.
  * Elle ne purge QUE des documents DÉJÀ en corbeille (GED26) ayant dépassé le
    délai de grâce, et RE-VÉRIFIE les gardes légales (GED23 write-once /
    GED24 legal hold) par document avant tout effacement (jamais une 500).
  * Multi-tenant : chaque société est traitée bornée à ses propres documents.
"""
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name='ged.purge_corbeille_echue')
def purge_corbeille_echue():
    """GED25 — Purge planifiée de la corbeille échue (DRY-RUN sauf opt-in).

    Délègue à `services.purger_corbeille_toutes_societes`. L'effacement réel
    n'a lieu QUE si `settings.GED_PURGE_AUTO_APPLY` est vrai ; sinon c'est un
    dry-run pur (rien n'est effacé). Idempotent et safe à ré-exécuter. Renvoie
    le dict de synthèse agrégé (sociétés concernées, éligibles, purgés,
    protégés)."""
    from django.conf import settings

    from . import services

    apply = bool(getattr(settings, 'GED_PURGE_AUTO_APPLY', False))
    result = services.purger_corbeille_toutes_societes(apply=apply)
    logger.info(
        'ged.purge_corbeille_echue: dry_run=%s, %d éligible(s), '
        '%d purgé(s), %d protégé(s) (legal/archive)',
        result['dry_run'], result['eligibles'],
        result['purges'], result['proteges'])
    return result


@shared_task(name='ged.signature_relances_expiration')
def signature_relances_expiration():
    """XGED2 — Balayage quotidien : relances de signataires dus + expiration
    des demandes échues (une société à la fois, jamais destructif : n'annule
    QUE des demandes déjà `en_attente` avec `expires_at` dépassée)."""
    from authentication.selectors import active_companies

    from . import services

    total_relances = 0
    total_expirees = 0
    for company in active_companies():  # SCA19 — exclut les tenants suspendus
        try:
            total_relances += len(services.relancer_signataires_dus(company))
            total_expirees += services.expirer_demandes_echues(company)
        except Exception:  # pragma: no cover - défensif, une société KO
            # n'interrompt jamais les suivantes.
            logger.warning(
                'ged.signature_relances_expiration: échec société %s',
                company.pk, exc_info=True)
    logger.info(
        'ged.signature_relances_expiration: %d relance(s), %d expiration(s)',
        total_relances, total_expirees)
    return {'relances': total_relances, 'expirations': total_expirees}


@shared_task(name='ged.verifier_integrite_archives')
def verifier_integrite_archives_task():
    """XGED6 — Contrôle périodique d'intégrité des archives légales (GED23),
    une société à la fois. Journalise chaque contrôle et notifie les admins
    (best-effort) en cas d'altération détectée — jamais destructif."""
    from authentication.selectors import active_companies

    from . import services

    total = {'total': 0, 'ok': 0, 'altere': 0, 'indisponible': 0}
    for company in active_companies():  # SCA19 — exclut les tenants suspendus
        try:
            res = services.verifier_integrite_archives(company)
            for key in total:
                total[key] += res[key]
        except Exception:  # pragma: no cover - défensif, une société KO
            # n'interrompt jamais les suivantes.
            logger.warning(
                'ged.verifier_integrite_archives: échec société %s',
                company.pk, exc_info=True)
    logger.info(
        'ged.verifier_integrite_archives: %d contrôlé(s), %d intègre(s), '
        '%d altéré(s), %d indisponible(s)',
        total['total'], total['ok'], total['altere'], total['indisponible'])
    return total


@shared_task(name='ged.notifier_emetteurs_expiration_signature')
def notifier_emetteurs_expiration_signature():
    """ZGED14 — Balayage quotidien : notifie les ÉMETTEURS de demandes de
    signature `en_attente` dont l'expiration approche (une société à la
    fois, jamais destructif — complète XGED2 qui ne couvre que le SIGNATAIRE).
    Best-effort par société : une société KO n'interrompt jamais les
    suivantes."""
    from authentication.selectors import active_companies

    from . import services

    total = 0
    for company in active_companies():  # SCA19 — exclut les tenants suspendus
        try:
            total += services.notifier_emetteur_expiration_proche(company)
        except Exception:  # pragma: no cover - défensif, une société KO
            # n'interrompt jamais les suivantes.
            logger.warning(
                'ged.notifier_emetteurs_expiration_signature: échec société %s',
                company.pk, exc_info=True)
    logger.info(
        'ged.notifier_emetteurs_expiration_signature: %d notification(s)',
        total)
    return {'notifications': total}


@shared_task(name='ged.poll_mail_intake')
def poll_mail_intake_task():
    """XGED9 — Relève l'ingestion email→GED de chaque société active.

    KEY-GATED : `services.mail_intake_enabled()` no-op propre sans le flag.
    Une société KO n'interrompt jamais les suivantes."""
    from authentication.selectors import active_companies

    from . import services

    if not services.mail_intake_enabled():
        return {'fetched': 0, 'imported': 0}
    total = {'fetched': 0, 'imported': 0}
    for company in active_companies():  # SCA19 — exclut les tenants suspendus
        try:
            res = services.poll_mail_intake(company)
            total['fetched'] += res['fetched']
            total['imported'] += res['imported']
        except Exception:  # pragma: no cover - défensif, une société KO
            # n'interrompt jamais les suivantes.
            logger.warning(
                'ged.poll_mail_intake: échec société %s', company.pk,
                exc_info=True)
    logger.info(
        'ged.poll_mail_intake: %d relevé(s), %d importé(s)',
        total['fetched'], total['imported'])
    return total

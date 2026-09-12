"""NTAPI11 — désactivation automatique d'un endpoint webhook MORT + alerte.

Le problème réel : une intégration cliente change d'URL, le endpoint répond 404
pour toujours, et l'ERP continue de lui POSTer chaque évènement — indéfiniment,
en silence. Après un seuil d'échecs CONSÉCUTIFS sur une fenêtre glissante
(défaut 20 sur 24 h, tous deux configurables), le webhook est désactivé
(``enabled=False``, ``disabled_reason``/``disabled_at`` renseignés) et l'admin
du tenant est averti via ``notifications.services.notify()``.

DEUX GARDE-FOUS QUI FONT TOUTE LA DIFFÉRENCE

* **Consécutifs, pas cumulés.** Un endpoint qui échoue 20 fois puis répond 200
  est SAIN : un compteur cumulé finirait par tuer n'importe quelle intégration
  vivante au bout de quelques mois. On ne regarde donc que la queue de
  livraisons depuis le dernier SUCCÈS — un seul succès remet le compteur à zéro.
* **La réactivation est MANUELLE.** Rien ne remet un webhook en service tout
  seul : une remise automatique reproduirait exactement la boucle qu'on vient
  d'arrêter. ``reactiver_webhook()`` est l'unique chemin, et il efface les deux
  champs de traçabilité.

Best-effort de bout en bout : ce module est appelé DEPUIS le chemin de
livraison ; une erreur ici ne doit jamais faire échouer une livraison ni
l'enregistrement métier d'origine.
"""
from __future__ import annotations

import logging

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

# Seuil d'échecs CONSÉCUTIFS avant désactivation automatique, et fenêtre
# glissante d'observation (heures). Réglables par déploiement ; 0 (ou négatif)
# sur le seuil = mécanisme DÉSACTIVÉ (aucun webhook n'est jamais coupé).
DEFAULT_AUTO_DISABLE_THRESHOLD = 20
DEFAULT_AUTO_DISABLE_WINDOW_HOURS = 24


def _seuil():
    return int(getattr(settings, 'WEBHOOK_AUTO_DISABLE_THRESHOLD',
                       DEFAULT_AUTO_DISABLE_THRESHOLD) or 0)


def _fenetre_heures():
    return int(getattr(settings, 'WEBHOOK_AUTO_DISABLE_WINDOW_HOURS',
                       DEFAULT_AUTO_DISABLE_WINDOW_HOURS)
               or DEFAULT_AUTO_DISABLE_WINDOW_HOURS)


def echecs_consecutifs(webhook, *, now=None, fenetre_heures=None):
    """Nombre de livraisons en échec DEPUIS le dernier succès, dans la fenêtre.

    Un statut ``SUCCESS`` (même ancien, tant qu'il est dans la fenêtre) coupe
    le décompte : l'endpoint a prouvé qu'il répondait. ``EN_ECHEC`` (abandon
    définitif NTAPI8) compte comme un échec, au même titre que ``FAILED``.
    """
    from datetime import timedelta

    from .models import WebhookDelivery

    now = now or timezone.now()
    heures = fenetre_heures if fenetre_heures is not None else _fenetre_heures()
    depuis = now - timedelta(hours=heures)
    statuts = list(
        WebhookDelivery.objects
        .filter(webhook=webhook, created_at__gte=depuis)
        .order_by('-created_at', '-id')
        .values_list('status', flat=True)[:max(1, _seuil() or 1) * 4]
    )
    compte = 0
    for statut in statuts:
        if statut == WebhookDelivery.Statut.SUCCESS:
            break
        compte += 1
    return compte


def evaluer_sante(webhook, *, now=None):
    """Désactive ``webhook`` s'il a franchi le seuil d'échecs consécutifs.

    Renvoie ``True`` si CET appel vient de le désactiver, ``False`` sinon
    (endpoint sain, déjà désactivé, ou mécanisme éteint). Idempotent : un
    webhook déjà ``enabled=False`` n'est jamais re-notifié.
    """
    seuil = _seuil()
    if seuil <= 0 or not webhook.enabled:
        return False

    compte = echecs_consecutifs(webhook, now=now)
    if compte < seuil:
        return False

    now = now or timezone.now()
    heures = _fenetre_heures()
    raison = (
        f'Désactivation automatique : {compte} échecs consécutifs de '
        f'livraison sur les {heures} dernières heures (seuil {seuil}). '
        f'Réactivation manuelle requise après correction de l’URL cible.'
    )
    webhook.enabled = False
    webhook.disabled_reason = raison
    webhook.disabled_at = now
    webhook.save(update_fields=['enabled', 'disabled_reason', 'disabled_at'])
    _alerter_admins(webhook, compte, heures)
    return True


def reactiver_webhook(webhook, *, user=None):
    """Réactivation MANUELLE explicite : remet ``enabled=True`` et efface la
    traçabilité de désactivation automatique. Jamais appelée par un automate."""
    webhook.enabled = True
    webhook.disabled_reason = ''
    webhook.disabled_at = None
    webhook.save(update_fields=['enabled', 'disabled_reason', 'disabled_at'])
    return webhook


def _alerter_admins(webhook, compte, heures):
    """Notifie les admins du tenant. Best-effort : un canal indisponible ne
    doit jamais empêcher la DÉSACTIVATION elle-même (qui, elle, protège la
    cible et l'ERP)."""
    try:
        from apps.notifications.models import EventType
        from apps.notifications.services import notify_many, resolve_recipients

        cible = webhook.label or webhook.target_url
        destinataires = resolve_recipients(
            webhook.company, EventType.API_WEBHOOK_DESACTIVE)
        notify_many(
            destinataires,
            EventType.API_WEBHOOK_DESACTIVE,
            f'Webhook désactivé automatiquement — {cible}',
            body=(
                f'{compte} échecs consécutifs de livraison sur les {heures} '
                f'dernières heures. Les évènements ne sont plus envoyés vers '
                f'cette adresse. Corrigez l’URL puis réactivez le webhook '
                f'depuis Paramètres → API & Webhooks.'),
            link='/parametres/api',
            company=webhook.company,
        )
    except Exception:  # noqa: BLE001 — jamais bloquant
        logger.exception(
            'Alerte de désactivation webhook %s non émise', webhook.pk)


def apres_livraison(webhook, statut):
    """Point d'accroche appelé après CHAQUE tentative journalisée.

    Ne fait rien sur un succès (le compteur d'échecs consécutifs est de toute
    façon remis à zéro par la présence de ce succès dans le journal). Ne lève
    jamais."""
    try:
        from .models import WebhookDelivery

        if statut == WebhookDelivery.Statut.SUCCESS:
            return False
        return evaluer_sante(webhook)
    except Exception:  # noqa: BLE001 — jamais bloquant pour la livraison
        logger.exception('Évaluation de santé du webhook %s échouée',
                         getattr(webhook, 'pk', None))
        return False

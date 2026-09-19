"""NTAPI38 — écriture et purge du journal d'appels de l'API publique.

Le pendant « diagnostic » des compteurs de quota (``core.api_usage``, FG398) :
là où ceux-ci répondent « combien d'appels ce mois », celui-ci répond « quel
chemin, quel statut, combien de temps, quel ``request_id`` ». C'est la matière
première du tableau de bord de monitoring NTAPI39.

BEST-EFFORT DE BOUT EN BOUT. Journaliser est une COURTOISIE d'observabilité :
une base indisponible sur cette table ne doit jamais transformer un GET
parfaitement légitime en 500 (et surtout pas fermer l'API publique). Même
politique que ``auth._safe`` pour les compteurs de quota.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Rétention par défaut d'une société SANS plan d'API enregistré : 0 = OFF, rien
# n'est jamais purgé (même convention que le flux d'évènements NTAPI17).
DEFAULT_API_CALL_LOG_RETENTION_DAYS = 0

# Longueurs des colonnes : tronquer ICI plutôt que laisser la base lever une
# DataError sur un chemin exotique (un 500 provoqué par le journal serait le
# comble).
MAX_METHODE = 10
MAX_CHEMIN = 512
MAX_REQUEST_ID = 64


def enregistrer(*, company_id, api_key_id=None, methode='', chemin='',
                statut=0, latence_ms=0, request_id='', taille_payload=0):
    """Ajoute une ligne au journal. Renvoie l'instance ou ``None``.

    ``company_id`` absent ⇒ rien n'est écrit : un appel non authentifié
    n'appartient à AUCUNE société, et l'inscrire quelque part exigerait
    d'inventer un propriétaire.
    """
    from .models import ApiCallLog

    if not company_id:
        return None
    try:
        return ApiCallLog.objects.create(
            company_id=company_id,
            api_key_id=api_key_id,
            methode=(methode or '')[:MAX_METHODE],
            chemin=(chemin or '')[:MAX_CHEMIN],
            statut=int(statut or 0),
            latence_ms=max(0, int(latence_ms or 0)),
            request_id=(request_id or '')[:MAX_REQUEST_ID],
            taille_payload=max(0, int(taille_payload or 0)),
        )
    except Exception:  # noqa: BLE001 — jamais bloquant pour la requête
        logger.exception(
            "Journal d'appels API : écriture impossible (%s %s)",
            methode, chemin)
        return None


def purger_appels(now, apply_=True):
    """Purge, PAR SOCIÉTÉ, les appels plus vieux que sa rétention.

    La borne vient du plan de la société (``ApiUsagePlan.
    retention_livraisons_jours``, NTAPI7) : ce journal est le MÊME matériau
    qu'une livraison webhook ou qu'une entrée du flux d'évènements (une trace
    d'échange sortant/entrant) et suit donc la MÊME borne — jamais une
    troisième notion de rétention à régler ailleurs. Une société sans plan
    retombe sur ``API_CALL_LOG_RETENTION_DAYS`` (défaut 0 = OFF).

    ``apply_=False`` (dry-run) compte sans supprimer. Renvoie le nombre
    d'appels concernés.
    """
    from datetime import timedelta

    from core.models import ApiUsagePlan
    from core.retention import setting_days

    from .models import ApiCallLog

    defaut = setting_days('API_CALL_LOG_RETENTION_DAYS',
                          DEFAULT_API_CALL_LOG_RETENTION_DAYS)
    jours_par_societe = dict(
        ApiUsagePlan.objects.filter(actif=True).values_list(
            'company_id', 'retention_livraisons_jours'))
    total = 0
    # `order_by()` VIDE avant `distinct()` : sans lui, l'ordering de `Meta`
    # (`-created_at, -id`) réinjecte ces colonnes dans le SELECT et la
    # distinction porte sur le TUPLE — on itérerait une fois par APPEL au lieu
    # d'une fois par société (piège Django documenté sur
    # `values_list().distinct()`).
    societes = ApiCallLog.objects.order_by().values_list(
        'company_id', flat=True).distinct()
    for company_id in societes:
        jours = jours_par_societe.get(company_id, defaut)
        if not jours or jours <= 0:
            continue  # rétention illimitée pour cette société
        limite = now - timedelta(days=jours)
        qs = ApiCallLog.objects.filter(
            company_id=company_id, created_at__lt=limite)
        compte = qs.count()
        if compte and apply_:
            qs.delete()
        total += compte
    return total

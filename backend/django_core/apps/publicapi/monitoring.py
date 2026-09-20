"""NTAPI39 — agrégats du tableau de bord « API & Intégrations » (admin tenant).

Trois journaux DÉJÀ tenus par l'app, recoupés en un seul objet :
``ApiCallLog`` (NTAPI38 — volume, taux d'erreur, latences, top endpoints),
``WebhookDelivery`` (santé des abonnements sur 24 h) et ``BulkJob``
(NTAPI14/15 — jobs récents). Aucune nouvelle table, aucun compteur dénormalisé :
tout est calculé à la lecture, donc jamais désynchronisé de la réalité.

TOUT EST SCOPÉ SOCIÉTÉ. Chaque requête filtre sur la ``company`` passée par la
vue (elle-même prise sur l'utilisateur connecté, jamais sur le corps de requête).

LES PERCENTILES SANS DÉPENDANCE NI CHARGEMENT EN MÉMOIRE. Django n'a pas
d'agrégat ``PERCENTILE_CONT``, et charger 7 jours de latences en Python pour en
trier la liste coûterait d'autant plus cher que le tenant est actif — c'est-à-dire
exactement quand l'écran sert. On lit donc la valeur AU RANG voulu par un
``ORDER BY latence_ms OFFSET n LIMIT 1`` : une seule ligne remonte, et le calcul
reste identique sur PostgreSQL comme sur SQLite.
"""
from __future__ import annotations

from datetime import timedelta

from django.db.models import Avg, Count, Q
from django.utils import timezone

# Fenêtre par défaut du tableau de bord : 7 jours (le critère NTAPI39 —
# « son taux d'erreur et sa latence p95 sur 7 j »).
FENETRE_JOURS_DEFAUT = 7
FENETRE_JOURS_MAX = 90
# Fenêtre dédiée à la santé des webhooks : 24 h (un endpoint mort se voit
# maintenant, pas noyé dans une semaine de succès).
FENETRE_WEBHOOKS_HEURES = 24
TOP_ENDPOINTS = 5
JOBS_RECENTS = 10


def _percentile(queryset, champ, fraction):
    """Valeur de ``champ`` au rang ``fraction`` (0..1) — ``None`` si vide.

    Rang « nearest-rank » sur ``n - 1`` : p50 d'un seul appel est CET appel, et
    p95 ne dépasse jamais le dernier rang existant."""
    total = queryset.count()
    if not total:
        return None
    rang = int(round(fraction * (total - 1)))
    rang = max(0, min(rang, total - 1))
    valeur = (queryset.order_by(champ)
              .values_list(champ, flat=True)[rang:rang + 1])
    return next(iter(valeur), None)


def _pct(part, total):
    """Pourcentage arrondi à 0,1 — ``0.0`` quand il n'y a rien à diviser."""
    if not total:
        return 0.0
    return round(100.0 * part / total, 1)


def appels(company, *, depuis):
    """Volume, taux d'erreur, latences et répartition par statut."""
    from .models import ApiCallLog

    qs = ApiCallLog.objects.filter(company=company, created_at__gte=depuis)
    agrege = qs.aggregate(
        total=Count('id'),
        erreurs=Count('id', filter=Q(statut__gte=400)),
        erreurs_4xx=Count('id', filter=Q(statut__gte=400, statut__lt=500)),
        erreurs_5xx=Count('id', filter=Q(statut__gte=500)),
        latence_moyenne=Avg('latence_ms'),
    )
    total = agrege['total']
    moyenne = agrege['latence_moyenne']
    return {
        'total': total,
        'erreurs': agrege['erreurs'],
        'erreurs_4xx': agrege['erreurs_4xx'],
        'erreurs_5xx': agrege['erreurs_5xx'],
        'taux_erreur_pct': _pct(agrege['erreurs'], total),
        'latence_moyenne_ms': int(round(moyenne)) if moyenne is not None else None,
        'latence_p50_ms': _percentile(qs, 'latence_ms', 0.50),
        'latence_p95_ms': _percentile(qs, 'latence_ms', 0.95),
    }


def top_endpoints(company, *, depuis, limite=TOP_ENDPOINTS):
    """Chemins les plus appelés, avec leur propre taux d'erreur.

    Le taux PAR endpoint est ce qui rend l'écran actionnable : un pic global de
    4xx ne dit pas lequel des cinq endpoints d'une intégration a cassé."""
    from .models import ApiCallLog

    lignes = (ApiCallLog.objects
              .filter(company=company, created_at__gte=depuis)
              .values('chemin')
              .annotate(appels=Count('id'),
                        erreurs=Count('id', filter=Q(statut__gte=400)),
                        latence_moyenne=Avg('latence_ms'))
              .order_by('-appels', 'chemin')[:limite])
    resultat = []
    for ligne in lignes:
        moyenne = ligne['latence_moyenne']
        resultat.append({
            'chemin': ligne['chemin'],
            'appels': ligne['appels'],
            'erreurs': ligne['erreurs'],
            'taux_erreur_pct': _pct(ligne['erreurs'], ligne['appels']),
            'latence_moyenne_ms': (
                int(round(moyenne)) if moyenne is not None else None),
        })
    return resultat


def sante_webhooks(company, *, depuis_24h):
    """Succès/échecs des livraisons sur 24 h + webhooks désactivés.

    ``en_echec`` (échec DÉFINITIF, NTAPI8) est compté À PART de ``failed``
    (encore retentable) : les deux ne demandent pas la même action à l'admin —
    l'un patiente, l'autre exige d'aller voir sa cible."""
    from .models import Webhook, WebhookDelivery

    livraisons = WebhookDelivery.objects.filter(
        company=company, created_at__gte=depuis_24h)
    agrege = livraisons.aggregate(
        total=Count('id'),
        succes=Count('id', filter=Q(status=WebhookDelivery.Statut.SUCCESS)),
        echecs=Count('id', filter=Q(status=WebhookDelivery.Statut.FAILED)),
        echecs_definitifs=Count(
            'id', filter=Q(status=WebhookDelivery.Statut.EN_ECHEC)),
    )
    total = agrege['total']
    en_echec = agrege['echecs'] + agrege['echecs_definitifs']
    webhooks = Webhook.objects.filter(company=company)
    return {
        'livraisons_24h': total,
        'succes_24h': agrege['succes'],
        'echecs_24h': agrege['echecs'],
        'echecs_definitifs_24h': agrege['echecs_definitifs'],
        'taux_echec_pct': _pct(en_echec, total),
        'webhooks_actifs': webhooks.filter(enabled=True).count(),
        'webhooks_desactives': webhooks.filter(enabled=False).count(),
    }


def jobs_recents(company, *, limite=JOBS_RECENTS):
    """Derniers jobs bulk + le compte de ceux encore en cours/en file.

    Les jobs ne sont PAS bornés à la fenêtre : un import lancé il y a dix jours
    et toujours `en_cours` est exactement ce qu'un admin doit voir."""
    from .models import BulkJob

    qs = BulkJob.objects.filter(company=company)
    derniers = [
        {
            'id': job.id,
            'type': job.type,
            'entite': job.entite,
            'statut': job.statut,
            'progression_pct': job.progression_pct,
            'traites': job.traites,
            'erreurs': job.erreurs,
            'created_at': job.created_at.isoformat(),
        }
        for job in qs.order_by('-created_at')[:limite]
    ]
    return {
        'en_cours': qs.filter(statut__in=(BulkJob.STATUT_EN_FILE,
                                          BulkJob.STATUT_EN_COURS)).count(),
        'en_echec': qs.filter(statut=BulkJob.STATUT_ECHEC).count(),
        'derniers': derniers,
    }


def tableau_de_bord(company, *, jours=FENETRE_JOURS_DEFAUT, maintenant=None):
    """Objet complet servi par ``GET /api/django/publicapi/monitoring/``."""
    maintenant = maintenant or timezone.now()
    jours = max(1, min(int(jours or FENETRE_JOURS_DEFAUT), FENETRE_JOURS_MAX))
    depuis = maintenant - timedelta(days=jours)
    depuis_24h = maintenant - timedelta(hours=FENETRE_WEBHOOKS_HEURES)
    return {
        'fenetre_jours': jours,
        'depuis': depuis.isoformat(),
        'appels': appels(company, depuis=depuis),
        'top_endpoints': top_endpoints(company, depuis=depuis),
        'webhooks': sante_webhooks(company, depuis_24h=depuis_24h),
        'jobs': jobs_recents(company),
    }

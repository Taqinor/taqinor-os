"""NTOBS8 — page « Limites & usage » unifiée (lecture seule).

Aujourd'hui les quotas existent en SILOS non visibles au tenant :
``publicapi.ApiKey``/FG398 (limites par clé, pas de vue consolidée),
``ged.QuotaStockage``/GED36 (GED seulement, pas d'écran dédié). Ce module
agrège, en LECTURE SEULE, AUCUN NOUVEAU MODÈLE DE QUOTA — réutilise les
champs/compteurs existants.

``core`` reste une couche de FONDATION (contrat import-linter
``core-foundation-is-a-base-layer``) : ``apps.ged``/``apps.publicapi`` ne sont
PAS des apps de fondation exemptées (contrairement à ``apps.parametres``) —
leurs MODÈLES sont donc résolus par ``django.apps.apps.get_model`` (jamais un
import statique), et leurs petits calculs d'agrégation (usage de stockage) sont
RECALCULÉS ici sur le modèle brut plutôt que d'importer leur fonction de
service (qui, elle, resterait un import interdit même en local — grimp voit
tout import statique, quel que soit son emplacement dans le fichier).
``apps.parametres`` EST une app de fondation exemptée (CLAUDE.md) : son
modèle ``CompanyProfile`` est lu directement pour la limite de sièges.
"""
from __future__ import annotations

from django.apps import apps as django_apps
from django.conf import settings
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

# Copié depuis ``apps.dataimport.views.MAX_UPLOAD_BYTES`` (5 Mo) — jamais un
# import statique de ``apps.dataimport`` (app non-fondation). Si cette
# constante change côté dataimport, la mettre à jour ICI AUSSI (un test
# dédié peut comparer les deux valeurs pour détecter une dérive).
IMPORT_MAX_UPLOAD_BYTES = 5 * 1024 * 1024


def _usage_ged(company):
    """Octets utilisés / quota GED de la société (GED36, lecture seule)."""
    try:
        version_model = django_apps.get_model('ged', 'DocumentVersion')
        quota_model = django_apps.get_model('ged', 'QuotaStockage')
    except LookupError:
        return None

    from django.db.models import Sum
    agg = version_model.objects.filter(company=company).aggregate(
        total=Sum('size'))
    utilise = int(agg['total'] or 0)

    quota_row = quota_model.objects.filter(company=company).first()
    if quota_row is not None:
        quota = quota_row.quota_octets
    else:
        quota = int(getattr(settings, 'GED_QUOTA_DEFAUT_OCTETS', 0) or 0)

    return {
        'nom': 'Stockage documentaire',
        'utilise': utilise,
        'limite': quota or None,  # 0/None = illimité
        'unite': 'octets',
    }


def _usage_api(company):
    """Requêtes API du mois, agrégées par clé (FG398, lecture seule)."""
    try:
        from . import api_usage
    except ImportError:
        return None

    total_mois = api_usage.usage_mois(company)
    plan = api_usage.plan_pour_societe_id(company.id)
    limite = plan.quota_par_mois if plan and plan.quota_par_mois else None

    par_cle = []
    try:
        from .models import ApiUsageRecord
        key_model = django_apps.get_model('publicapi', 'ApiKey')
        debut_mois = timezone.now().date().replace(day=1)
        from django.db.models import Sum
        rows = (
            ApiUsageRecord.objects
            .filter(company=company, jour__gte=debut_mois)
            .values('api_key_id')
            .annotate(total=Sum('nb_requetes'))
        )
        labels = dict(
            key_model.objects.filter(
                id__in=[r['api_key_id'] for r in rows])
            .values_list('id', 'label'))
        par_cle = [
            {'cle': labels.get(r['api_key_id'], f'#{r["api_key_id"]}'),
             'requetes': r['total']}
            for r in rows
        ]
    except LookupError:
        pass

    return {
        'nom': 'Requêtes API (mois courant)',
        'utilise': total_mois,
        'limite': limite,
        'unite': 'requêtes',
        'par_cle': par_cle,
    }


def _usage_import_csv():
    """Taille max d'import CSV/XLSX (constante existante, exposée telle
    quelle — ce N'EST PAS un usage courant/limite consommable, juste une
    borne technique fixe)."""
    return {
        'nom': 'Taille max import CSV/XLSX',
        'utilise': None,
        'limite': IMPORT_MAX_UPLOAD_BYTES,
        'unite': 'octets',
    }


def _usage_utilisateurs(company):
    """Utilisateurs actifs vs limite de plan (``CompanyProfile.nb_sieges_max``
    — ``apps.parametres`` est une app de fondation exemptée). ``None`` de
    limite = illimité (aucun plan de sièges défini)."""
    from authentication.models import CustomUser
    from apps.parametres.models import CompanyProfile

    actifs = CustomUser.objects.filter(company=company, is_active=True).count()
    profile = CompanyProfile.objects.filter(company=company).first()
    limite = profile.nb_sieges_max if profile else None

    return {
        'nom': 'Utilisateurs actifs',
        'utilise': actifs,
        'limite': limite,
        'unite': 'comptes',
    }


def usage_summary(company):
    """NTOBS8 — agrège au moins 3 ressources réelles, en lecture seule,
    AUCUN nouveau modèle de quota. Chaque ressource dont la source est
    indisponible est simplement OMISE (jamais une valeur inventée)."""
    ressources = []
    for calc in (
        lambda: _usage_ged(company),
        lambda: _usage_api(company),
        _usage_import_csv,
        lambda: _usage_utilisateurs(company),
    ):
        try:
            res = calc()
        except Exception:  # noqa: BLE001 — best-effort, une source KO n'en bloque pas d'autres
            res = None
        if res is not None:
            ressources.append(res)

    return {'ressources': ressources, 'genere_le': timezone.now().isoformat()}


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def usage_view(request):
    """GET /api/django/core/usage/ — scopé société de l'appelant."""
    return Response(usage_summary(request.user.company))


# ── NTOBS13 — notification proactive avant qu'un quota ne soit atteint ────
#
# Réutilise ENTIÈREMENT le canal ``notifications.notify()`` existant (aucun
# nouveau canal). Anti-spam : le dernier seuil notifié par (société,
# ressource) est mémorisé en cache Django (TTL 24h) — franchir 80% notifie
# une fois, franchir 100% notifie à nouveau (seuil différent), redescendre
# sous 80% efface la mémoire pour permettre une notification future si le
# seuil est refranchi (jamais un blocage permanent).

QUOTA_ALERT_CACHE_TTL_SECONDS = 60 * 60 * 24
QUOTA_ALERT_THRESHOLDS = (100, 80)  # ordre décroissant : le plus haut d'abord


def _quota_alert_cache_key(company_id, ressource_nom):
    return f'usage_quota_notified:{company_id}:{ressource_nom}'


def _notifier_seuil_quota(company, ressource, seuil, pct):
    try:
        from apps.notifications.models import EventType
        from apps.notifications.services import notify
        from .maintenance_windows import admins_cibles
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        return
    titre = f"{ressource['nom']} atteint {int(pct)}% du quota"
    for admin in admins_cibles(company):
        try:
            notify(
                admin, EventType.USAGE_QUOTA_SEUIL_FRANCHI, titre,
                body=f"Votre {ressource['nom'].lower()} atteint {int(pct)}% "
                     'du quota.',
                company=company,
            )
        except Exception:  # noqa: BLE001
            continue


def notifier_seuils_usage(now=None):
    """NTOBS13 — job beat quotidien : notifie chaque société active dont une
    ressource mesurée franchit 80% ou 100% de sa limite."""
    from django.core.cache import cache

    from authentication.models import Company

    notifies = 0
    for company in Company.objects.filter(actif=True):
        summary = usage_summary(company)
        for ressource in summary['ressources']:
            limite = ressource.get('limite')
            utilise = ressource.get('utilise')
            if not limite or utilise is None:
                continue
            pct = 100.0 * utilise / limite
            key = _quota_alert_cache_key(company.id, ressource['nom'])
            dernier_seuil = cache.get(key)

            if pct < 80:
                if dernier_seuil is not None:
                    cache.delete(key)
                continue

            for seuil in QUOTA_ALERT_THRESHOLDS:
                if pct >= seuil and dernier_seuil != seuil:
                    _notifier_seuil_quota(company, ressource, seuil, pct)
                    cache.set(key, seuil, QUOTA_ALERT_CACHE_TTL_SECONDS)
                    notifies += 1
                    break
    return notifies

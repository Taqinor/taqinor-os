"""FG398 — Plans de tarif API & analytics d'usage.

Couche de FONDATION : porte le QUOTA (``ApiUsagePlan``) et le COMPTEUR d'usage
(``ApiUsageRecord``) des clés d'API, SANS que ``core`` n'importe l'app satellite
``publicapi`` (contrat import-linter ``core-foundation-is-a-base-layer``). La clé
est désignée par string-FK ``'publicapi.ApiKey'`` ; ``publicapi`` appelle
l'enregistreur ci-dessous au moment d'authentifier une requête — jamais
l'inverse.

Conception
----------

* ``plan_pour_societe(company)`` — renvoie (ou crée) le plan de quota d'une
  société (défauts du palier « gratuit »).
* ``enregistrer_usage(api_key, *, erreur=False, when=None)`` — incrémente, de
  façon atomique, le compteur du jour pour ``(api_key, jour)`` (get_or_create +
  F()). La société est déduite de la clé (jamais du corps de requête).
* ``quota_depasse(api_key, when=None)`` — vrai si le quota journalier OU mensuel
  du plan de la société est atteint (0 = illimité). Le débit/minute reste géré
  par le throttle DRF existant ; ici on borne le VOLUME.
* ``analytics(company, depuis=None, jusqu_a=None)`` — agrège l'usage de la
  société (par clé + total) pour la vue d'usage.

Aucune importation d'app domaine : la clé d'API est résolue via
``django.apps.apps.get_model('publicapi', 'ApiKey')`` (référence paresseuse).
"""
from __future__ import annotations

from datetime import timedelta

from django.db.models import F, Sum
from django.utils import timezone

from .models import ApiUsagePlan, ApiUsageRecord


def plan_pour_societe(company):
    """Plan de quota de la société (créé avec les défauts si absent)."""
    plan, _ = ApiUsagePlan.objects.get_or_create(company=company)
    return plan


def enregistrer_usage(api_key, *, erreur=False, when=None):
    """Incrémente le compteur d'usage du jour pour une clé d'API.

    Atomique via ``get_or_create`` + ``F()`` (pas de course de lecture-écriture).
    La société est déduite de la clé — jamais d'un corps de requête.
    """
    jour = (when or timezone.now()).date()
    record, created = ApiUsageRecord.objects.get_or_create(
        api_key=api_key, jour=jour,
        defaults={'company_id': api_key.company_id})
    updates = {'nb_requetes': F('nb_requetes') + 1}
    if erreur:
        updates['nb_erreurs'] = F('nb_erreurs') + 1
    ApiUsageRecord.objects.filter(pk=record.pk).update(**updates)
    return record


def usage_jour(company, jour=None):
    """Nombre total de requêtes de la société pour un jour donné."""
    jour = jour or timezone.now().date()
    agg = ApiUsageRecord.objects.filter(
        company=company, jour=jour).aggregate(total=Sum('nb_requetes'))
    return agg['total'] or 0


def usage_mois(company, ref=None):
    """Nombre total de requêtes de la société sur le mois courant."""
    ref = (ref or timezone.now()).date()
    debut = ref.replace(day=1)
    agg = ApiUsageRecord.objects.filter(
        company=company, jour__gte=debut,
        jour__lte=ref).aggregate(total=Sum('nb_requetes'))
    return agg['total'] or 0


def quota_depasse(api_key, when=None):
    """Vrai si le quota de VOLUME (jour ou mois) de la société est atteint.

    0 = illimité. Le débit/minute reste géré par le throttle DRF existant.
    """
    when = when or timezone.now()
    plan = plan_pour_societe_id(api_key.company_id)
    if plan is None or not plan.actif:
        return False
    if plan.quota_par_jour and usage_jour(
            api_key.company, when.date()) >= plan.quota_par_jour:
        return True
    if plan.quota_par_mois and usage_mois(
            api_key.company, when) >= plan.quota_par_mois:
        return True
    return False


def plan_pour_societe_id(company_id):
    """Plan de quota par identifiant de société (sans création)."""
    return ApiUsagePlan.objects.filter(company_id=company_id).first()


def analytics(company, depuis=None, jusqu_a=None):
    """Agrège l'usage d'une société (par clé + total) sur une fenêtre.

    Par défaut : les 30 derniers jours. Renvoie un dict JSON-sérialisable.
    """
    jusqu_a = jusqu_a or timezone.now().date()
    depuis = depuis or (jusqu_a - timedelta(days=30))
    qs = ApiUsageRecord.objects.filter(
        company=company, jour__gte=depuis, jour__lte=jusqu_a)
    par_cle = list(
        qs.values('api_key', 'api_key__label')
          .annotate(requetes=Sum('nb_requetes'), erreurs=Sum('nb_erreurs'))
          .order_by('-requetes'))
    total = qs.aggregate(requetes=Sum('nb_requetes'),
                         erreurs=Sum('nb_erreurs'))
    return {
        'depuis': depuis.isoformat(),
        'jusqu_a': jusqu_a.isoformat(),
        'total_requetes': total['requetes'] or 0,
        'total_erreurs': total['erreurs'] or 0,
        'par_cle': [
            {
                'api_key': r['api_key'],
                'label': r['api_key__label'],
                'requetes': r['requetes'] or 0,
                'erreurs': r['erreurs'] or 0,
            }
            for r in par_cle
        ],
    }

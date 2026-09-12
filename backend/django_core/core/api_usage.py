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


# NTAPI6 — nom demandé par le plan pour l'enregistreur consommé par le throttle
# de ``publicapi``. Alias STRICT de ``enregistrer_usage`` (jamais une seconde
# implémentation qui pourrait diverger) : l'app publique câble ``record_call``,
# le reste du dépôt garde le nom FR historique.
record_call = enregistrer_usage


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


# ── NTAPI6 — état de quota exposé en en-têtes `X-RateLimit-*` ────────────────
#
# Le plan borne TROIS fenêtres : minute (débit), jour et mois (volume). Les
# en-têtes standards n'en décrivent qu'UNE — on expose donc systématiquement la
# PLUS CONTRAIGNANTE (celle dont il reste le moins), pour qu'un client qui
# respecte l'en-tête ne se prenne jamais un 429 surprise sur une autre fenêtre.
# 0 = illimité (fenêtre ignorée), exactement comme `quota_depasse`.

def _fin_du_mois(ref):
    """Premier instant du mois SUIVANT (borne de réinitialisation mensuelle)."""
    from datetime import datetime, time as dt_time

    jour = ref.date().replace(day=1)
    mois_suivant = (jour.replace(day=28) + timedelta(days=4)).replace(day=1)
    naive = datetime.combine(mois_suivant, dt_time.min)
    return timezone.make_aware(naive, ref.tzinfo) if timezone.is_aware(ref) \
        else naive


def _fin_du_jour(ref):
    """Premier instant du jour SUIVANT (borne de réinitialisation journalière)."""
    from datetime import datetime, time as dt_time

    naive = datetime.combine(ref.date() + timedelta(days=1), dt_time.min)
    return timezone.make_aware(naive, ref.tzinfo) if timezone.is_aware(ref) \
        else naive


def etat_quota(api_key, when=None):
    """État de quota de VOLUME de la société d'une clé, prêt pour les en-têtes.

    Renvoie ``None`` quand aucune borne de volume ne s'applique (pas de plan,
    plan inactif, ou quotas à 0 = illimité) — l'appelant retombe alors sur la
    fenêtre de DÉBIT du throttle DRF, seule limite en vigueur.

    Sinon un dict ``{'limit', 'remaining', 'reset', 'retry_after',
    'fenetre'}`` où ``reset`` est un epoch (secondes) et ``retry_after`` le
    nombre de secondes à attendre. ``remaining`` n'est jamais négatif.
    """
    when = when or timezone.now()
    plan = plan_pour_societe_id(api_key.company_id)
    if plan is None or not plan.actif:
        return None

    fenetres = []
    if plan.quota_par_jour:
        fenetres.append((
            'jour', plan.quota_par_jour,
            usage_jour(api_key.company, when.date()), _fin_du_jour(when)))
    if plan.quota_par_mois:
        fenetres.append((
            'mois', plan.quota_par_mois,
            usage_mois(api_key.company, when), _fin_du_mois(when)))
    if not fenetres:
        return None

    # La plus contraignante = celle dont il reste le moins.
    nom, limite, consomme, reset_at = min(
        fenetres, key=lambda f: f[1] - f[2])
    restant = max(0, limite - consomme)
    retry_after = max(1, int((reset_at - when).total_seconds()))
    return {
        'limit': limite,
        'remaining': restant,
        'reset': int(reset_at.timestamp()),
        'retry_after': retry_after,
        'fenetre': nom,
    }


def limite_par_minute(api_key):
    """Débit/minute du plan de la société (``None`` = pas de borne propre).

    NTAPI6 — le throttle DRF de ``publicapi`` lit CETTE valeur plutôt qu'un
    taux codé en dur : le plan (``ApiUsagePlan``) est la source de vérité des
    limites, comme le dit sa docstring. ``quota_burst`` s'ajoute à la borne
    (marge de rafale tolérée). 0 = illimité → ``None`` (le taux DRF configuré
    reste en vigueur, comportement historique).
    """
    plan = plan_pour_societe_id(api_key.company_id)
    if plan is None or not plan.actif or not plan.quota_par_minute:
        return None
    return plan.quota_par_minute + (plan.quota_burst or 0)


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

"""NTAI1/NTAI2 — Puits d'écriture du journal d'usage IA + agrégats + budget.

Côté APP de la paire posée par ``core.ai.usage`` (côté FONDATION) : core mesure
et appelle un puits ; c'est ici que la ligne est écrite, agrégée, et que le
budget mensuel de la société est calculé.

Rien ici n'est appelé par un client HTTP en écriture : le journal est
alimenté UNIQUEMENT par les appels IA réels, et la lecture est un agrégat
scopé société.
"""
from __future__ import annotations

import logging
from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

logger = logging.getLogger(__name__)

#: Fenêtre par défaut de l'agrégat d'usage (jours).
USAGE_FENETRE_JOURS = 30


# ─────────────────────────────────────────────────────────────────────────────
# Puits — écrit une ligne par appel IA réel
# ─────────────────────────────────────────────────────────────────────────────

#: 1 MAD = 1 000 000 micro-MAD (unité de stockage EXACTE du coût — voir
#: ``LlmUsageRecord.cost_estimated_micro_mad``).
MICRO_PAR_MAD = Decimal('1000000')


def en_micro_mad(montant) -> int:
    """Convertit un montant MAD (Decimal) en micro-MAD entier."""
    return int((Decimal(montant or 0) * MICRO_PAR_MAD).to_integral_value())


def en_mad(micro) -> Decimal:
    """Convertit des micro-MAD (entier) en MAD (Decimal, 6 décimales)."""
    return (Decimal(micro or 0) / MICRO_PAR_MAD).quantize(Decimal('0.000001'))


def enregistrer_usage(*, company_id, capability, provider, feature_key='',
                      prompt_tokens=0, completion_tokens=0,
                      cost_estimated=Decimal('0'), cout_tarife=False,
                      latency_ms=0, success=True, error=''):
    """Puits appelé par ``core.ai.usage.record_usage`` — best-effort.

    La société vient du CONTEXTE d'appel posé côté serveur ; une société
    inconnue n'arrive jamais ici (core ne journalise pas sans elle).
    ``cost_estimated`` arrive en MAD et est stocké en micro-MAD entier."""
    from .models import LlmUsageRecord

    return LlmUsageRecord.objects.create(
        company_id=company_id,
        capability=capability,
        provider=provider,
        feature_key=feature_key or '',
        prompt_tokens=prompt_tokens or 0,
        completion_tokens=completion_tokens or 0,
        cost_estimated_micro_mad=en_micro_mad(cost_estimated),
        cout_tarife=bool(cout_tarife),
        latency_ms=latency_ms or 0,
        success=bool(success),
        message=(error or '')[:255],
    )


def connect_usage_sink():
    """Branche le puits sur la fondation (appelé par ``apps.py::ready()``)."""
    from core.ai.usage import register_usage_sink

    register_usage_sink(enregistrer_usage)


# ─────────────────────────────────────────────────────────────────────────────
# Agrégats de lecture (endpoint NTAI1)
# ─────────────────────────────────────────────────────────────────────────────

def _lignes(company, *, since=None, feature=''):
    """Queryset des usages de ``company`` — TOUJOURS scopé société."""
    from .models import LlmUsageRecord

    qs = LlmUsageRecord.objects.filter(company=company)
    if since is not None:
        qs = qs.filter(created_at__date__gte=since)
    if feature:
        qs = qs.filter(feature_key=feature)
    return qs


def _bloc(agg: dict) -> dict:
    """Met en forme un agrégat brut (montants en chaîne — pas de flottant)."""
    return {
        'appels': agg.get('appels') or 0,
        'echecs': agg.get('echecs') or 0,
        'prompt_tokens': agg.get('prompt_tokens') or 0,
        'completion_tokens': agg.get('completion_tokens') or 0,
        'cout_mad': str(en_mad(agg.get('cout') or 0)),
        # Nombre d'appels dont le coût est INCONNU (aucun tarif configuré) :
        # sans lui, un total de 0 MAD se lirait à tort comme « gratuit ».
        'appels_sans_tarif': agg.get('sans_tarif') or 0,
    }


_FILTRE_ECHEC = Q(success=False)
_FILTRE_SANS_TARIF = Q(cout_tarife=False)

_AGREGATS = {
    'appels': Count('id'),
    'prompt_tokens': Sum('prompt_tokens'),
    'completion_tokens': Sum('completion_tokens'),
    'cout': Sum('cost_estimated_micro_mad'),
}


def _annoter(qs):
    """Ajoute les compteurs dérivés (échecs, appels sans tarif)."""
    return qs.annotate(
        **_AGREGATS,
        echecs=Count('id', filter=_FILTRE_ECHEC),
        sans_tarif=Count('id', filter=_FILTRE_SANS_TARIF),
    )


def agreger_usage(company, *, since=None, feature='') -> dict:
    """Agrégats d'usage IA d'une société, par JOUR / FEATURE / FOURNISSEUR.

    ``since`` (date) borne la fenêtre — 30 jours par défaut côté vue.
    ``feature`` filtre sur une feature précise. Aucun agrégat ne traverse la
    frontière société : le queryset part de ``company``.
    """
    base = _lignes(company, since=since, feature=feature)

    total = _annoter(base.values('company_id')).first() or {}
    par_jour = [
        {'jour': ligne['jour'].isoformat(), **_bloc(ligne)}
        for ligne in _annoter(
            base.annotate(jour=TruncDate('created_at')).values('jour')
        ).order_by('jour')
    ]
    par_feature = [
        {'feature': ligne['feature_key'] or '(non précisée)', **_bloc(ligne)}
        for ligne in _annoter(base.values('feature_key')).order_by('feature_key')
    ]
    par_fournisseur = [
        {'fournisseur': ligne['provider'], 'capacite': ligne['capability'],
         **_bloc(ligne)}
        for ligne in _annoter(
            base.values('provider', 'capability')
        ).order_by('provider', 'capability')
    ]

    bloc_total = _bloc(total)
    return {
        'depuis': since.isoformat() if since else None,
        'feature': feature or '',
        'totaux': bloc_total,
        # Vrai seulement si TOUS les appels de la fenêtre portent un tarif :
        # sinon le montant est un PLANCHER, pas le coût réel (« zéro chiffre
        # inventé » — on ne complète pas les trous par une estimation).
        'cout_complet': bloc_total['appels'] > 0
        and bloc_total['appels_sans_tarif'] == 0,
        'par_jour': par_jour,
        'par_feature': par_feature,
        'par_fournisseur': par_fournisseur,
    }


def fenetre_par_defaut():
    """Date de début par défaut de l'agrégat (30 jours en arrière)."""
    return timezone.localdate() - timedelta(days=USAGE_FENETRE_JOURS)


# ─────────────────────────────────────────────────────────────────────────────
# NTAI6 — Métriques par capacité (santé des capacités IA)
# ─────────────────────────────────────────────────────────────────────────────

#: Nombre d'appels récents examinés pour la latence médiane (borne le coût de
#: la lecture : une société active accumule vite des dizaines de milliers de
#: lignes, et la médiane d'un échantillon récent dit mieux « comment ça va
#: MAINTENANT » qu'une médiane historique).
LATENCE_ECHANTILLON = 200


def _mediane(valeurs) -> int | None:
    valeurs = sorted(v for v in valeurs if v is not None)
    if not valeurs:
        return None
    milieu = len(valeurs) // 2
    if len(valeurs) % 2:
        return int(valeurs[milieu])
    return int((valeurs[milieu - 1] + valeurs[milieu]) / 2)


def metriques_capacites(company) -> dict:
    """``{capacité: {appels, latence_p50_ms, derniere_erreur, ...}}``.

    Calculateur enregistré auprès de ``core.ai.usage.capability_metrics``.
    Une capacité JAMAIS appelée est absente du dict : l'écran affiche « aucune
    mesure » au lieu d'un zéro qui se lirait comme « tout va bien »."""
    from .models import LlmUsageRecord

    mesures = {}
    base = LlmUsageRecord.objects.filter(company=company)
    for capability in base.values_list('capability', flat=True).distinct():
        lignes = base.filter(capability=capability)
        latences = list(
            lignes.filter(success=True)
            .order_by('-created_at')
            .values_list('latency_ms', flat=True)[:LATENCE_ECHANTILLON])
        echec = lignes.filter(success=False).order_by('-created_at').first()
        mesures[capability] = {
            'appels': lignes.count(),
            'latence_p50_ms': _mediane(latences),
            'derniere_erreur': (echec.message or '') if echec else '',
            'derniere_erreur_le': (echec.created_at.isoformat()
                                   if echec else None),
        }
    return mesures


def connect_stats_provider():
    """Branche le calculateur de métriques sur la fondation (``apps.py``)."""
    from core.ai.usage import register_usage_stats_provider

    register_usage_stats_provider(metriques_capacites)


# ─────────────────────────────────────────────────────────────────────────────
# NTAI2 — Budget mensuel + coupe-circuit
# ─────────────────────────────────────────────────────────────────────────────

def depense_du_mois(company, *, premier_du_mois=None) -> Decimal:
    """Dépense IA CONNUE de la société depuis le 1er du mois, en MAD.

    « Connue » : seuls les appels dont le fournisseur avait un tarif configuré
    portent un coût. Les autres valent 0 — on ne complète jamais un trou par
    une estimation, donc le coupe-circuit ne peut pas se déclencher sur un
    chiffre inventé."""
    if premier_du_mois is None:
        premier_du_mois = timezone.localdate().replace(day=1)
    total = _lignes(company, since=premier_du_mois).aggregate(
        micro=Sum('cost_estimated_micro_mad'))['micro'] or 0
    return en_mad(total)


def statut_budget(company):
    """Calculateur enregistré auprès de ``core.ai.usage.budget_status``.

    Accepte une ``Company`` ou un id (le contexte d'appel ne porte qu'un id).
    Renvoie un ``BudgetStatus`` ; alerte au franchissement du seuil, une seule
    fois par mois. Ne lève jamais côté appelant : ``core`` encapsule déjà, mais
    l'alerte elle-même est best-effort ici."""
    from core.ai.usage import BudgetStatus

    from .models import LlmBudget

    filtre = ({'company_id': company} if isinstance(company, int)
              else {'company': company})
    budget = LlmBudget.objects.filter(actif=True, **filtre).first()
    if budget is None:
        return BudgetStatus()

    periode = timezone.localdate().strftime('%Y-%m')
    plafond = Decimal(budget.montant_mensuel_mad or 0)
    depense = depense_du_mois(budget.company)
    pourcentage = (float(depense / plafond * 100) if plafond > 0 else 0.0)
    depasse = plafond > 0 and depense >= plafond
    alerte = plafond > 0 and pourcentage >= float(budget.seuil_alerte_pct or 0)

    if alerte and budget.alerte_periode != periode:
        _alerter_budget(budget=budget, depense=depense, pourcentage=pourcentage,
                        periode=periode)

    return BudgetStatus(
        configured=True, plafond=plafond, depense=depense,
        pourcentage=pourcentage, depasse=depasse, alerte=alerte,
        periode=periode)


def _alerter_budget(*, budget, depense, pourcentage, periode):
    """Prévient les responsables du franchissement du seuil — best-effort.

    Réutilise ``EventType.MONITORING_RAPPORT`` (même choix que l'alerte de
    dérive NTAI29) : aucun nouveau type d'événement n'est ajouté ici, il
    vivrait dans une app hors périmètre. L'échec d'une notification ne doit
    jamais casser l'appel IA qui l'a déclenchée."""
    try:
        from django.contrib.auth import get_user_model

        from apps.notifications.models import EventType
        from apps.notifications.services import notify_many

        User = get_user_model()
        destinataires = list(User.objects.filter(
            company=budget.company, is_active=True,
            role_legacy__in=['responsable', 'admin']))
        if destinataires:
            notify_many(
                destinataires, EventType.MONITORING_RAPPORT,
                'Budget IA : seuil d\'alerte atteint',
                body=(f'{depense} MAD consommés ce mois sur un plafond de '
                      f'{budget.montant_mensuel_mad} MAD '
                      f'({pourcentage:.0f} %). Au-delà de 100 %, les '
                      'fonctions génératives se mettent en veille.'),
                company=budget.company)
        budget.alerte_periode = periode
        budget.save(update_fields=['alerte_periode', 'updated_at'])
    except Exception:  # noqa: BLE001 — l'alerte ne casse jamais l'appel IA
        logger.warning('ai_governance: alerte de budget non émise (société %s)',
                       getattr(budget, 'company_id', None), exc_info=True)


def connect_budget_provider():
    """Branche le calculateur de budget sur la fondation (``apps.py``)."""
    from core.ai.usage import register_budget_provider

    register_budget_provider(statut_budget)

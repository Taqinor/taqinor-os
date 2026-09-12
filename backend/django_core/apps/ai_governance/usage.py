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

def enregistrer_usage(*, company_id, capability, provider, feature_key='',
                      prompt_tokens=0, completion_tokens=0,
                      cost_estimated=Decimal('0'), cout_tarife=False,
                      latency_ms=0, success=True, error=''):
    """Puits appelé par ``core.ai.usage.record_usage`` — best-effort.

    La société vient du CONTEXTE d'appel posé côté serveur ; une société
    inconnue n'arrive jamais ici (core ne journalise pas sans elle)."""
    from .models import LlmUsageRecord

    return LlmUsageRecord.objects.create(
        company_id=company_id,
        capability=capability,
        provider=provider,
        feature_key=feature_key or '',
        prompt_tokens=prompt_tokens or 0,
        completion_tokens=completion_tokens or 0,
        cost_estimated=cost_estimated or Decimal('0'),
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
        'cout_mad': str(agg.get('cout') or Decimal('0')),
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
    'cout': Sum('cost_estimated'),
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

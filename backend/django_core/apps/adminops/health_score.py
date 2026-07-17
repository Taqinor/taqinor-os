"""NTADM5 — Health score du tenant, strictement scopé `company`.

Trois sous-scores 0-100 pondérés à parts égales : complétude de la config
obligatoire, taux d'usage récent (30 jours), volume de données de qualité.
Chaque sous-score se dégrade PROPREMENT (jamais d'exception) si une source
n'est pas disponible — `try/except` neutre plutôt qu'un score cassé.
"""
from __future__ import annotations

from datetime import timedelta

from django.utils import timezone


def _score_completude(company):
    """CompanyProfile renseigné (+40) + ≥1 rôle custom (+30) + ≥1 template
    de message/email (+30). `parametres`/`roles` sont des apps de fondation
    — import direct autorisé (pas de détour selectors.py requis)."""
    score = 0
    try:
        from apps.parametres.models_company import CompanyProfile
        profile = CompanyProfile.objects.filter(company=company).first()
        if profile and (getattr(profile, 'nom', '') or getattr(profile, 'raison_sociale', '')):
            score += 40
    except Exception:
        pass
    try:
        from apps.roles.models import Role
        if Role.objects.filter(company=company, est_systeme=False).exists():
            score += 30
    except Exception:
        pass
    try:
        from apps.parametres.models_messages import MessageTemplate
        if MessageTemplate.objects.filter(company=company).exists():
            score += 30
        else:
            from apps.parametres.models_email import EmailTemplate
            if EmailTemplate.objects.filter(company=company).exists():
                score += 30
    except Exception:
        pass
    return min(score, 100)


def _score_usage(company, jours=30):
    """Taux d'usage : nombre d'entrées `audit.AuditLog` sur `jours` jours,
    normalisé (50 événements = 100 %, plafonné)."""
    try:
        from apps.audit.models import AuditLog
        depuis = timezone.now() - timedelta(days=jours)
        n = AuditLog.objects.filter(
            company=company, created_at__gte=depuis).count()
        return min(int(n / 50 * 100), 100)
    except Exception:
        return 0


def _score_qualite(company):
    """Volume de données de qualité : présence de devis/factures (signe
    d'usage réel) — proxy conservateur via les selectors `ventes` publics
    (jamais un import direct de `ventes.models`, app cœur métier)."""
    try:
        from apps.ventes.selectors import compter_devis, compter_factures
        nb_devis = compter_devis(company)
        nb_factures = compter_factures(company)
        score = 0
        if nb_devis:
            score += 50
        if nb_factures:
            score += 50
        return score
    except Exception:
        return 0


def calculer_health_score(company):
    """NTADM5 — renvoie `{'score': int, 'sous_scores': {...}, 'recommandations': [...]}`.

    Calcul strictement scopé société — aucune donnée cross-tenant."""
    sc_completude = _score_completude(company)
    sc_usage = _score_usage(company)
    sc_qualite = _score_qualite(company)
    score = round((sc_completude + sc_usage + sc_qualite) / 3)

    recommandations = []
    if sc_completude < 100:
        recommandations.append(
            'Complétez le profil société, créez un rôle personnalisé et un '
            'modèle de message pour renforcer la configuration de base.')
    if sc_usage < 50:
        recommandations.append(
            "L'usage récent de l'ERP est faible — encouragez l'équipe à "
            'utiliser les modules actifs.')
    if sc_qualite < 100:
        recommandations.append(
            'Créez vos premiers devis/factures pour activer le suivi '
            'qualité des données.')
    return {
        'score': score,
        'sous_scores': {
            'completude': sc_completude,
            'usage': sc_usage,
            'qualite': sc_qualite,
        },
        'recommandations': recommandations[:3],
    }

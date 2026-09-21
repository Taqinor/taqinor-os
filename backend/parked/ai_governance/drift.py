"""NTAI29 — Surveillance de dérive (drift) des features & prédictions.

PUR ET OFFLINE : le Population Stability Index se calcule avec la seule
bibliothèque standard (``math.log``) — aucun appel LLM, aucune dépendance
nouvelle, aucun coût. Un scorer dont la population d'entrée dérive rend des
prédictions silencieusement moins fiables ; ce module rend cette dérive
VISIBLE et la notifie.

Les distributions ne sont PAS calculées ici : chaque source de features
s'enregistre via :func:`register_distribution_provider` (patron « déclarer une
fois » du dépôt). Sans fournisseur enregistré, la tâche mensuelle est un no-op
propre — elle n'invente aucune donnée.
"""
from __future__ import annotations

import logging
import math

logger = logging.getLogger(__name__)

#: Seuil d'alerte usuel du PSI : < 0,10 stable · 0,10-0,25 dérive modérée ·
#: > 0,25 dérive significative (convention de place, retenue comme défaut).
PSI_SEUIL_ALERTE = 0.25

#: Proportion plancher substituée à un bucket vide — évite un log(0) infini
#: tout en gardant le PSI comparable d'un mois à l'autre.
_EPSILON = 1e-6

#: {nom du modèle: callable(company) -> {bucket: effectif|proportion}}.
_DISTRIBUTION_PROVIDERS: dict = {}


def register_distribution_provider(modele: str, fonction) -> None:
    """Déclare la source de distribution des features d'un scorer.

    ``fonction(company)`` renvoie un dict ``{bucket: nombre}`` (effectifs ou
    proportions — :func:`normaliser_distribution` s'en charge). Idempotent :
    ré-enregistrer la même clé remplace le fournisseur.
    """
    _DISTRIBUTION_PROVIDERS[str(modele)] = fonction


def distribution_providers() -> dict:
    """Copie du registre (lecture seule pour les appelants)."""
    return dict(_DISTRIBUTION_PROVIDERS)


def normaliser_distribution(distribution) -> dict:
    """Convertit ``{bucket: effectif}`` en proportions sommant à 1.

    Un dict vide, ou dont le total est nul, renvoie ``{}`` (aucune dérive
    calculable — jamais une division par zéro).
    """
    if not isinstance(distribution, dict):
        return {}
    valeurs = {}
    for bucket, brut in distribution.items():
        try:
            valeur = float(brut)
        except (TypeError, ValueError):
            continue
        if valeur < 0:
            continue
        valeurs[str(bucket)] = valeur
    total = sum(valeurs.values())
    if total <= 0:
        return {}
    return {bucket: valeur / total for bucket, valeur in valeurs.items()}


def psi(baseline, courant) -> float:
    """Population Stability Index entre deux distributions.

    ``PSI = Σ (p_courant − p_baseline) × ln(p_courant / p_baseline)`` sur
    l'UNION des buckets. Toujours ≥ 0 ; 0 = distributions identiques. Renvoie
    0.0 si l'une des deux est vide (rien à comparer).
    """
    ref = normaliser_distribution(baseline)
    obs = normaliser_distribution(courant)
    if not ref or not obs:
        return 0.0
    total = 0.0
    for bucket in set(ref) | set(obs):
        p_ref = max(ref.get(bucket, 0.0), _EPSILON)
        p_obs = max(obs.get(bucket, 0.0), _EPSILON)
        total += (p_obs - p_ref) * math.log(p_obs / p_ref)
    # Les arrondis flottants peuvent produire un -0.0 : le PSI est positif.
    return max(total, 0.0)


def baseline_pour(company, modele):
    """Snapshot de référence d'un couple (société, modèle), ou ``None``."""
    from .models import DriftSnapshot

    return (DriftSnapshot.objects
            .filter(company=company, modele=modele, est_baseline=True)
            .order_by('-date', '-id')
            .first())


def enregistrer_snapshot(*, company, modele, distribution, date,
                         seuil=PSI_SEUIL_ALERTE, notifier=True):
    """Enregistre un snapshot mensuel et notifie si la dérive dépasse ``seuil``.

    Le PREMIER snapshot d'un couple (société, modèle) devient la BASELINE
    (``psi`` 0, aucune alerte). Les suivants portent leur PSI vis-à-vis d'elle.
    Idempotent sur (société, modèle, date) : ré-exécuter le mois courant met à
    jour le snapshot au lieu d'en empiler un second.
    """
    from .models import DriftSnapshot

    proportions = normaliser_distribution(distribution)
    reference = baseline_pour(company, modele)
    est_baseline = reference is None
    valeur_psi = 0.0 if est_baseline else psi(
        reference.distribution_json, proportions)

    snapshot, _cree = DriftSnapshot.objects.update_or_create(
        company=company, modele=modele, date=date,
        defaults={
            'distribution_json': proportions,
            'psi': valeur_psi,
            'est_baseline': est_baseline,
            'alerte_emise': False,
        })

    if notifier and not est_baseline and valeur_psi > seuil:
        _alerter_drift(company=company, snapshot=snapshot, seuil=seuil)
    return snapshot


def _alerter_drift(*, company, snapshot, seuil):
    """Notifie best-effort les responsables — jamais d'exception remontée.

    Réutilise l'``EventType.MONITORING_RAPPORT`` existant : une dérive de
    modèle est un signal de SUPERVISION technique. Aucun nouveau type
    d'événement n'est ajouté ici (il vivrait dans une app hors périmètre).
    """
    try:
        from django.contrib.auth import get_user_model
        from apps.notifications.models import EventType
        from apps.notifications.services import notify_many

        User = get_user_model()
        destinataires = list(User.objects.filter(
            company=company, is_active=True,
            role_legacy__in=['responsable', 'admin']))
        if not destinataires:
            return
        notify_many(
            destinataires, EventType.MONITORING_RAPPORT,
            f'Dérive détectée sur le modèle « {snapshot.modele} »',
            body=(f'PSI {snapshot.psi:.2f} au-dessus du seuil {seuil:.2f} '
                  f'sur la période du {snapshot.date}. Les prédictions de ce '
                  'scorer sont peut-être moins fiables.'),
            company=company)
        snapshot.alerte_emise = True
        snapshot.save(update_fields=['alerte_emise', 'updated_at'])
    except Exception:  # noqa: BLE001 — l'alerte ne doit jamais casser le calcul
        logger.warning('ai_governance: alerte de dérive non émise (société %s)',
                       getattr(company, 'id', None), exc_info=True)

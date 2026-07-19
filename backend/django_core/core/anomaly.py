"""FG360 — Détection d'anomalies (stock / paiements / fraude), fondation pure.

Deux couches, toutes deux SANS import d'app métier (core reste une couche de
base — contrat import-linter ``core-foundation-is-a-base-layer``) :

  1. :func:`scan_for_outliers` — détection STATISTIQUE pure (z-score) sur une
     liste de points fournie par l'app appelante depuis sa couche selectors.
     Aucune dépendance externe : uniquement la librairie standard. Ne touche pas
     la base, ne crée aucun ``AnomalyFlag`` — renvoie des CANDIDATS.

  2. :func:`record_anomaly` / :func:`record_outliers` — matérialisent un
     :class:`core.models.AnomalyFlag` par candidat, en IMPOSANT toujours la
     société côté serveur (multi-tenant : ``company`` n'est jamais accepté d'un
     corps de requête). Idempotence légère : on ne ré-ouvre pas un flag déjà
     ouvert pour le même (société, sujet, métrique).

L'app métier (stock/ventes…) câble un scan planifié (Celery beat / commande)
qui : (a) lit ses données via ses selectors, (b) appelle ``scan_for_outliers``,
(c) persiste via ``record_outliers`` pour SA société. core ne planifie rien
lui-même — il fournit le moteur générique.

WIR140 — ``adsengine.anomaly`` est un moteur SÉPARÉ et DÉLIBÉRÉMENT distinct de
ce socle (ratios relatifs SMB, pas de z-score ; ``AnomalyEvent`` ad-spécifique,
pas ``AnomalyFlag``). Il ne consomme pas ce module et ne doit pas — voir
``docs/engine/anomaly-engine-separation.md``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from statistics import mean, pstdev
from typing import Any, Iterable


@dataclass
class OutlierCandidate:
    """Un point jugé aberrant par :func:`scan_for_outliers`."""

    subject_id: str
    value: float
    expected: float          # moyenne de la série
    score: float             # z-score signé (écart standardisé)
    direction: str           # 'haut' | 'bas'
    label: str = ''          # libellé lisible du sujet (facultatif)
    meta: dict = field(default_factory=dict)


def scan_for_outliers(
    points: Iterable[dict],
    *,
    value_key: str = 'value',
    id_key: str = 'id',
    label_key: str = 'label',
    z_threshold: float = 3.0,
    min_points: int = 4,
) -> list[OutlierCandidate]:
    """Repère les valeurs aberrantes d'une série par z-score.

    ``points`` : itérable de dicts ``{id, value, label?, ...}`` fourni par
    l'app appelante (jamais importée ici). Une valeur est aberrante si la valeur
    absolue de son z-score (``(x - moyenne) / écart-type``) dépasse
    ``z_threshold``. En dessous de ``min_points`` points exploitables ou si
    l'écart-type est nul (toutes valeurs égales), aucune anomalie n'est signalée
    — pas de faux positif sur un échantillon trop petit.

    Renvoie la liste des :class:`OutlierCandidate`, triée du plus aberrant au
    moins aberrant. Pur, déterministe, sans appel réseau ni base de données.
    """
    rows: list[tuple[Any, float, str, dict]] = []
    for p in points or []:
        raw = p.get(value_key)
        try:
            val = float(raw)
        except (TypeError, ValueError):
            continue
        rows.append((
            p.get(id_key),
            val,
            str(p.get(label_key) or ''),
            p,
        ))

    if len(rows) < min_points:
        return []

    values = [r[1] for r in rows]
    mu = mean(values)
    sigma = pstdev(values)
    if sigma == 0:
        return []

    out: list[OutlierCandidate] = []
    for sid, val, label, raw in rows:
        z = (val - mu) / sigma
        if abs(z) >= z_threshold:
            out.append(OutlierCandidate(
                subject_id='' if sid is None else str(sid),
                value=val,
                expected=round(mu, 6),
                score=round(z, 4),
                direction='haut' if z > 0 else 'bas',
                label=label,
                meta={k: v for k, v in raw.items()
                      if k not in (value_key, id_key, label_key)},
            ))
    out.sort(key=lambda c: abs(c.score), reverse=True)
    return out


def _severity_for(score: float) -> str:
    """Gravité dérivée de l'amplitude du z-score."""
    from core.models import AnomalyFlag
    a = abs(score)
    if a >= 5:
        return AnomalyFlag.SEVERITY_CRITIQUE
    if a >= 4:
        return AnomalyFlag.SEVERITY_AVERTISSEMENT
    return AnomalyFlag.SEVERITY_INFO


def record_anomaly(
    *,
    company,
    message: str,
    category: str = 'autre',
    severity: str | None = None,
    subject_type: str = '',
    subject_id: str = '',
    metric: str = '',
    value: float | None = None,
    expected: float | None = None,
    score: float | None = None,
    detail: dict | None = None,
    dedupe: bool = True,
):
    """Matérialise un :class:`core.models.AnomalyFlag`, société IMPOSÉE.

    ``company`` est toujours fourni par l'appelant serveur (jamais d'un corps de
    requête). Si ``dedupe`` (défaut), on ne crée pas de doublon tant qu'un flag
    OUVERT existe déjà pour le même (société, sujet, métrique) — on renvoie
    l'existant. Renvoie le ``AnomalyFlag`` (créé ou réutilisé)."""
    from core.models import AnomalyFlag

    if severity is None:
        severity = (_severity_for(score) if score is not None
                    else AnomalyFlag.SEVERITY_AVERTISSEMENT)

    if dedupe:
        existing = AnomalyFlag.objects.filter(
            company=company,
            subject_type=subject_type,
            subject_id=subject_id,
            metric=metric,
            status=AnomalyFlag.STATUS_OUVERT,
        ).first()
        if existing is not None:
            return existing

    return AnomalyFlag.objects.create(
        company=company,
        message=message,
        category=category,
        severity=severity,
        subject_type=subject_type,
        subject_id=subject_id,
        metric=metric,
        value=value,
        expected=expected,
        score=score,
        detail=detail or {},
    )


def record_outliers(
    candidates: Iterable[OutlierCandidate],
    *,
    company,
    category: str = 'autre',
    subject_type: str = '',
    metric: str = '',
    dedupe: bool = True,
) -> list:
    """Persiste une liste de :class:`OutlierCandidate` en ``AnomalyFlag``.

    Société imposée. Compose un message FR par candidat. Renvoie la liste des
    flags créés/réutilisés."""
    flags = []
    for c in candidates or []:
        libelle = c.label or c.subject_id or 'sujet'
        sens = 'anormalement élevé' if c.direction == 'haut' else 'anormalement bas'
        message = f'{libelle} : {sens} (z={c.score})'
        flags.append(record_anomaly(
            company=company,
            message=message[:255],
            category=category,
            subject_type=subject_type,
            subject_id=c.subject_id,
            metric=metric,
            value=c.value,
            expected=c.expected,
            score=c.score,
            detail=c.meta,
            dedupe=dedupe,
        ))
    return flags

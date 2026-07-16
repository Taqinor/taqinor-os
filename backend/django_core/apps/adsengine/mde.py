"""ADSENG13 — Service MDE / puissance (l'arithmétique dd-science-core §1 en code).

Le régime bas-volume de Taqinor (§0) rend la plupart des barreaux de l'entonnoir
statistiquement SOMBRES. Ce module met en code la « table de réalité » du dossier
(§1.3) : combien d'effet est seulement DÉTECTABLE à un volume donné, à 7/14/28
jours, et la durée estimée pour un effet cible. Consommé par la validation de plan
de vol (ADSENG28) et l'affichage console (P7).

Formules (§1.2), deux proportions indépendantes, α = 0.05 bilatéral, puissance
0.80, split égal, 2 bras ::

    n_par_bras = (z_{1-α/2}+z_{1-β})² · [p₁(1-p₁)+p₂(1-p₂)] / (p₂-p₁)²
    δ_MDE      ≈ (z_{1-α/2}+z_{1-β}) · √( 2·p(1-p)/n )
    MDE_relatif = δ_MDE / p

avec z_{0.975}=1.9600, z_{0.80}=0.8416 (⇒ somme = 2.8016, carré = 7.849). Le rung
signature relève de Poisson (≈3 signatures/mois) : sa CI 95 % exacte est fournie
(pure ``math``, aucune dépendance scipy). Fonctions pures, zéro I/O.
"""
from __future__ import annotations

import math

# Quantiles normaux (dd-science-core §1.2). Codés en dur = les valeurs EXACTES
# du dossier (jamais recalculées, pour reproduire la table à la décimale près).
Z_ALPHA_HALF = 1.9600   # z_{1-α/2}, α = 0.05
Z_POWER = 0.8416        # z_{1-β},   puissance 0.80
Z_SUM = Z_ALPHA_HALF + Z_POWER          # 2.8016
Z_SUM_SQ = Z_SUM * Z_SUM                 # 7.849 (à la 3e décimale)

DEFAULT_HORIZONS = (7, 14, 28)          # jours (§1.3)


def sample_size_per_arm(p1, p2, z_sum=Z_SUM):
    """Taille d'échantillon par bras pour détecter ``p1`` vs ``p2`` (§1.2).

    ``n = z_sum² · [p1(1-p1) + p2(1-p2)] / (p2-p1)²``. Lève ``ValueError`` si
    ``p1 == p2`` (aucun effet à détecter). Fonction pure.
    """
    if p1 == p2:
        raise ValueError("p1 et p2 identiques : aucun effet à détecter.")
    num = z_sum * z_sum * (p1 * (1 - p1) + p2 * (1 - p2))
    return num / ((p2 - p1) ** 2)


def mde_absolute(p, n, z_sum=Z_SUM):
    """Effet ABSOLU minimal détectable (δ, en points de proportion) à ``n``
    essais/bras (§1.2, approximation variance-poolée). Fonction pure."""
    if n <= 0:
        raise ValueError("n doit être > 0.")
    return z_sum * math.sqrt(2 * p * (1 - p) / n)


def mde_relative(p, n, z_sum=Z_SUM):
    """Effet RELATIF minimal détectable (δ/p, fraction) à ``n`` essais/bras.

    Multiplier par 100 pour un pourcentage. Fonction pure.
    """
    if p <= 0:
        raise ValueError("p doit être > 0.")
    return mde_absolute(p, n, z_sum) / p


def mde_by_horizon(p, daily_trials_per_arm, horizons=DEFAULT_HORIZONS,
                   z_sum=Z_SUM):
    """MDE relatif d'un barreau à chaque horizon (§1.3).

    ``n = daily_trials_per_arm × jours``. Renvoie ``{jours: mde_relatif}``
    (fraction). Fonction pure.
    """
    out = {}
    for days in horizons:
        n = daily_trials_per_arm * days
        out[days] = mde_relative(p, n, z_sum) if n > 0 else float('inf')
    return out


def days_to_detect(p, target_relative, daily_trials_per_arm, z_sum=Z_SUM):
    """Durée (jours) pour détecter un effet relatif cible à un débit donné.

    Inverse la formule MDE : ``n = z_sum²·2·p(1-p) / (target_relative·p)²`` puis
    ``jours = n / daily_trials_per_arm`` (arrondi au jour supérieur). Fonction
    pure. Lève ``ValueError`` sur des entrées non positives.
    """
    if target_relative <= 0 or p <= 0 or daily_trials_per_arm <= 0:
        raise ValueError("Entrées strictement positives requises.")
    delta = target_relative * p
    n = z_sum * z_sum * 2 * p * (1 - p) / (delta * delta)
    return math.ceil(n / daily_trials_per_arm)


# ── Poisson : le rung signature (≈ 3 signatures/mois) — §1.3. ────────────────

def _gammainc_lower_regularized(a, x):
    """P(a, x) — gamma incomplète inférieure régularisée (Numerical Recipes).

    Série pour ``x < a+1``, fraction continue sinon. Pure ``math``.
    """
    if x <= 0:
        return 0.0
    gln = math.lgamma(a)
    if x < a + 1:
        # Développement en série.
        ap = a
        total = 1.0 / a
        term = total
        for _ in range(1000):
            ap += 1
            term *= x / ap
            total += term
            if abs(term) < abs(total) * 1e-15:
                break
        return total * math.exp(-x + a * math.log(x) - gln)
    # Fraction continue (Lentz) pour Q(a,x) = 1 - P(a,x).
    tiny = 1e-300
    b = x + 1 - a
    c = 1.0 / tiny
    d = 1.0 / b
    h = d
    for i in range(1, 1000):
        an = -i * (i - a)
        b += 2
        d = an * d + b
        if abs(d) < tiny:
            d = tiny
        c = b + an / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-15:
            break
    q = math.exp(-x + a * math.log(x) - gln) * h
    return 1.0 - q


def _chi2_ppf(q, df):
    """Quantile (inverse CDF) de la loi du χ² à ``df`` degrés de liberté.

    χ²(q, df) = 2·gammaincinv(df/2, q) ; on inverse P(df/2, x/2) = q par bissection
    (P est monotone croissante en x). Pure ``math``. Reproduit les quantiles du
    dossier (χ²(0.025,6)≈1.237, χ²(0.975,8)≈17.535).
    """
    if q <= 0:
        return 0.0
    a = df / 2.0
    lo, hi = 0.0, 1.0
    # Étend la borne haute jusqu'à dépasser q.
    while _gammainc_lower_regularized(a, hi / 2.0) < q and hi < 1e6:
        hi *= 2
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if _gammainc_lower_regularized(a, mid / 2.0) < q:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def poisson_ci(k, confidence=0.95):
    """CI exacte (relations χ²) du paramètre λ d'un comptage de Poisson ``k``.

    dd-science-core §1.3 : pour ``k=3`` signatures/mois, la CI 95 % exacte est
    ``[0.62, 8.77]`` — un seul comptage de signatures est indistinguable entre
    « à peine ça marche » et « 3× mieux ». Borne basse = χ²(α/2, 2k)/2 (0 si
    ``k=0``), borne haute = χ²(1-α/2, 2k+2)/2. Renvoie ``(low, high)``. Pure.
    """
    k = int(k)
    alpha = 1 - confidence
    low = 0.0 if k == 0 else 0.5 * _chi2_ppf(alpha / 2.0, 2 * k)
    high = 0.5 * _chi2_ppf(1 - alpha / 2.0, 2 * k + 2)
    return (low, high)


# ── La table de référence du dossier (§1.3), comme DONNÉES. ──────────────────
# Chaque rung : (p, {jours: n_par_bras}) — n = moitié du volume de l'entonnoir
# sur la fenêtre, à 100 MAD/jour (§1.1). Le test doré vérifie que
# ``mde_relative`` reproduit EXACTEMENT les pourcentages du dossier (§1.3/appendice).
REFERENCE_TABLE = {
    'ctr': {'p': 0.02, 'n': {7: 6300, 14: 12600, 28: 25200}},
    'click_to_conversation': {'p': 0.65, 'n': {7: 126, 14: 252, 28: 504}},
    'conversation_to_qualified': {'p': 0.07, 'n': {7: 84, 14: 168, 28: 336}},
    'qualified_to_signature': {'p': 0.06, 'n': {7: 5.7, 14: 11.5, 28: 23}},
}


def reference_relative_mde_pct():
    """Reproduit la table §1.3 : ``{rung: {jours: MDE_relatif_%_arrondi_1déc}}``.

    Fonction pure — le test doré compare aux pourcentages EXACTS du dossier.
    """
    out = {}
    for rung, spec in REFERENCE_TABLE.items():
        p = spec['p']
        out[rung] = {days: round(mde_relative(p, n) * 100, 1)
                     for days, n in spec['n'].items()}
    return out

"""ASG8 — Priors hiérarchiques INTRA-tenant (démarrage à froid, §3.4 / §6).

Un nœud NEUF n'a pas de données propres. Plutôt que de partir d'un prior uniforme
Beta(1,1) aveugle, il EMPRUNTE aux agrégats de ses frères/de sa catégorie DANS LA
MÊME société (pattern « partial pooling » / empirical Bayes — AISTATS 2022 ;
Amazon KDD 2024, −12,7% CPC en prod). Le prior est un ajustement **méthode des
moments** d'une Beta sur les moyennes des nœuds frères, puis **plafonné** à ::

    κ_max = min(50, ~1 semaine d'événements)

de sorte que la **donnée locale DOMINE en ~1 semaine** (§3.4) : le prior n'est
jamais assez lourd pour retarder la convergence vers le vrai taux du nœud.

**INVARIANT DUR (§6) : l'héritage ne traverse JAMAIS une frontière de société.**
Le cross-tenant (modèle Varos/Triple Whale) reste GATED (compliance Meta) — ce
module lit UNIQUEMENT ``node.company``. Toute la mécanique est pure (méthode des
moments, plafonnement) sauf ``inherit_prior`` qui lit les frères en base et écrit
le prior du nœud neuf.
"""
from __future__ import annotations

import logging
import statistics

logger = logging.getLogger(__name__)

# Plafond dur de concentration (§3.4) : un prior ne vaut jamais plus de 50
# pseudo-événements, quelle que soit la richesse de la catégorie.
KAPPA_HARD_CAP = 50.0

# Bornes numériques pour éviter les moyennes dégénérées (0 ou 1 exacts).
_EPS = 1e-6


def kappa_max(weekly_events):
    """``κ_max = min(50, ~1 semaine d'événements)`` (§3.4).

    Garantit que la donnée locale (≈ ``weekly_events`` en une semaine) pèse au
    moins autant que le prior — donc domine en ~1 semaine. ``weekly_events`` est
    borné à ≥ 1 (un prior a au moins un pseudo-événement de poids).
    """
    return min(KAPPA_HARD_CAP, max(1.0, float(weekly_events)))


def method_of_moments(mean, variance):
    """Ajustement méthode des moments d'une Beta sur ``(moyenne, variance)``.

    ``κ = mean·(1−mean)/variance − 1`` ; ``α = mean·κ`` ; ``β = (1−mean)·κ``. Une
    variance ≥ ``mean(1−mean)`` (sur-dispersion au-delà de la borne de Bernoulli)
    donne ``κ ≤ 0`` : on renvoie alors un prior TRÈS faible (κ→0⁺), la donnée
    prend tout. Renvoie ``(alpha, beta)`` bruts (non plafonnés). Fonction pure.
    """
    m = min(1.0 - _EPS, max(_EPS, mean))
    if variance <= 0:
        # Aucune dispersion observée : concentration maximale (plafonnée en aval).
        kappa = KAPPA_HARD_CAP
    else:
        kappa = m * (1.0 - m) / variance - 1.0
    kappa = max(_EPS, kappa)
    return (m * kappa, (1.0 - m) * kappa)


def cap_concentration(alpha, beta, cap):
    """Plafonne la concentration ``κ = α+β`` à ``cap`` en PRÉSERVANT la moyenne.

    Si ``α+β ≤ cap`` : inchangé. Sinon rééchelonne ``(α, β)`` pour que
    ``α+β = cap`` sans bouger ``α/(α+β)``. Fonction pure.
    """
    total = alpha + beta
    if total <= cap or total <= 0:
        return (alpha, beta)
    scale = cap / total
    return (alpha * scale, beta * scale)


def fit_prior(means, *, weekly_events):
    """Prior Beta hérité depuis les moyennes des frères, plafonné (§3.4). Pure.

    ``means`` : liste des moyennes de taux des nœuds frères/catégorie (mêmes
    société). Méthode des moments (mean/variance de l'échantillon) → plafonné à
    ``κ_max = min(50, weekly_events)``. Un seul frère (ou variance nulle) → prior
    centré sur cette moyenne, plafonné. ``means`` vide → prior uniforme Beta(1,1).
    Renvoie ``(alpha0, beta0)``.
    """
    vals = [min(1.0 - _EPS, max(_EPS, float(x))) for x in means]
    if not vals:
        return (1.0, 1.0)
    m = statistics.fmean(vals)
    var = statistics.variance(vals) if len(vals) >= 2 else 0.0
    alpha, beta = method_of_moments(m, var)
    return cap_concentration(alpha, beta, kappa_max(weekly_events))


# ── Couche modèle (I/O) — INTRA-tenant STRICT ─────────────────────────────────
def _sibling_means(node, category_nodes=None):
    """Moyennes de taux des frères d'un nœud, DANS SA SOCIÉTÉ uniquement.

    Par défaut : les autres nœuds de la MÊME société ET même classe (la
    « catégorie »), non retirés, hors le nœud lui-même. ``category_nodes`` permet
    d'élargir explicitement (ex. cross-catégorie intra-tenant : agricole héritant
    du résidentiel) — mais l'appelant reste responsable de ne fournir QUE des
    nœuds de la même société ; on RE-FILTRE ici par sécurité (invariant §6).
    """
    from .models import AssumptionNode

    if category_nodes is None:
        category_nodes = AssumptionNode.objects.filter(
            company=node.company, classe=node.classe).exclude(
            statut=AssumptionNode.Statut.RETIRED)
    means = []
    for sib in category_nodes:
        # INVARIANT DUR : jamais un frère d'une autre société (§6).
        if sib.company_id != node.company_id:
            continue
        if sib.pk == node.pk:
            continue
        total = sib.alpha + sib.beta
        if total <= 0:
            continue
        means.append(sib.alpha / total)
    return means


def inherit_prior(node, *, weekly_events, category_nodes=None, apply=True):
    """Pose sur ``node`` un prior hérité de ses frères intra-tenant (§3.4).

    Ajuste ``(alpha0, beta0)`` par méthode des moments sur les moyennes des frères
    (MÊME société), plafonné à ``κ_max``. Si ``apply`` et que le nœud est encore
    « à froid » (posterior == prior actuel, aucune donnée), le posterior
    ``(alpha, beta)`` est ré-ancré sur le nouveau prior. **Ne traverse JAMAIS une
    frontière de société** (invariant §6, re-filtré dans ``_sibling_means``).
    Renvoie ``(alpha0, beta0)``.
    """
    means = _sibling_means(node, category_nodes=category_nodes)
    alpha0, beta0 = fit_prior(means, weekly_events=weekly_events)

    if apply:
        was_cold = (node.alpha == node.alpha0 and node.beta == node.beta0)
        node.alpha0, node.beta0 = alpha0, beta0
        fields = ['alpha0', 'beta0', 'updated_at']
        if was_cold:
            # Nœud neuf sans données : le posterior redémarre sur le prior hérité.
            node.alpha, node.beta = alpha0, beta0
            fields = ['alpha', 'beta', 'alpha0', 'beta0', 'updated_at']
        node.save(update_fields=fields)

    logger.info(
        'priors.inherit_prior: nœud=%s société=%s frères=%s prior=(%.3f, %.3f)',
        node.pk, node.company_id, len(means), alpha0, beta0)
    return (alpha0, beta0)


def posterior_after_events(alpha0, beta0, successes, trials):
    """Posterior Beta après ``successes`` succès sur ``trials`` essais (conjugué).

    ``(α, β) = (α₀ + succès, β₀ + échecs)``. Sert aux tests de convergence
    (§3.4 : la donnée locale domine en ~1 semaine). Fonction pure.
    """
    failures = max(0, trials - successes)
    return (alpha0 + successes, beta0 + failures)

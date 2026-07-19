"""ASG3 — Scoreur Value-of-Information + ordonnanceur de l'arbre (§3.3).

Le cœur de l'arbre vivant : quand un slot de test s'ouvre, le moteur teste
``argmax VoI`` — pas la phase suivante d'un calendrier fixe. La formule (§3.3) ::

    VoI_j = S_j · U_j · R_j · T_j / C_j

  * **S** — enjeux : part du budget (pondérée revenu) que la réponse pilote
    (``AssumptionNode.enjeux_s`` ∈ [0,1]).
  * **U** — incertitude : ``U = 1 − |2·P(meilleur) − 1|``, RECALCULÉE chaque
    semaine depuis le posterior OUBLIÉ (ASG2). C'est LE terme qui regonfle quand
    un nœud vieillit — sans lui, la file ne re-fait jamais surface aux nœuds
    périmés et tout l'oubli §3.2 devient décoratif. ``P(meilleur)`` = probabilité
    (bandit Thompson, ``bandit.prob_best``) que le posterior du nœud batte son
    champion de référence (par défaut son propre prior Beta(α₀,β₀) : « ce nœud
    est-il encore distinguable de sa croyance de base ? »). Un posterior net et
    fort ⇒ P proche de 0/1 ⇒ U bas ; un posterior oublié qui recolle au prior ⇒
    P proche de 0.5 ⇒ U haut ⇒ le nœud re-gagne la file.
  * **R** — pertinence-décision : une réponse changerait-elle une action ?
    (``AssumptionNode.pertinence_r`` ∈ [0,1] ; un nœud « intéressant sans
    conséquence » score 0).
  * **T** — testabilité : ``T = clip(δ_plausible / δ_MDE, 0, 1)`` via le service
    MDE (``mde.mde_absolute`` aux volumes courants). Le CLIP est ce qui empêche le
    moteur de viser l'intestable : un barreau au MDE infaisable (signature/
    qualifié) a ``T ≈ 0`` et ne gagne JAMAIS la file (§1, correction n°1).
  * **C** — coût : semaines × part de budget du test.

Ordonnanceur : ``schedule_next`` calcule le VoI de chaque nœud candidat de la
société, prend l'argmax, et écrit un ``DecisionLog`` OBLIGATOIRE (auditabilité,
ASG3) — aucune sélection sans trace. Multi-tenant : les candidats sont bornés à la
société de l'expérience, jamais élargis.

Il **remplace la transition de phase FIXE du FlightRunner (ASG5 §5) derrière un
flag** : le drapeau cache ``voi_scheduler_active`` (OFF par défaut, miroir de
``flightrunner.is_autonomy_active``). Quand il est ON, ``FlightRunner.advance_phase``
désactive la fenêtre calendaire et laisse la file VoI gouverner ; quand il est OFF,
le comportement calendaire historique est byte-identique.

Le cœur mathématique (``uncertainty``/``testability``/``voi_score``) est **pur** :
déterministe sous ``seed``, zéro I/O.
"""
from __future__ import annotations

import logging

from django.core.cache import cache

from . import bandit, mde

logger = logging.getLogger(__name__)

# TTL du drapeau d'ordonnanceur VoI en cache (30 j) — survit aux redémarrages
# tant qu'un humain ne le retire pas, exactement comme le drapeau d'autonomie.
VOI_SCHEDULER_TTL = 60 * 60 * 24 * 30


# ── Drapeau d'ordonnanceur VoI PAR société (cache — jamais un champ modèle) ────
# Miroir de ``flightrunner.is_autonomy_active`` : OFF par défaut. ON = la file VoI
# remplace la transition de phase calendaire fixe (§5). Aucune migration : un
# champ modèle n'est PAS le périmètre de cette lane (règle : cache flag).
def _voi_key(company):
    return f'adsengine:voi_scheduler:{company.pk}'


def voi_scheduler_active(company):
    """Vrai si l'ordonnanceur VoI est ACTIVÉ pour cette société (OFF par défaut)."""
    return bool(cache.get(_voi_key(company)))


def set_voi_scheduler_active(company, active):
    """Pose/retire le drapeau d'ordonnanceur VoI (OFF par défaut)."""
    if active:
        cache.set(_voi_key(company), True, VOI_SCHEDULER_TTL)
    else:
        cache.delete(_voi_key(company))


# ── Cœur mathématique PUR (§3.3) ──────────────────────────────────────────────
def prob_node_best(alpha, beta, champ_alpha, champ_beta, *,
                   k=bandit.DEFAULT_K, seed=bandit.DEFAULT_SEED):
    """P(le posterior Beta(α,β) du nœud batte son champion Beta(α_c,β_c)).

    Thompson Monte-Carlo (``bandit.prob_best`` sur 2 bras) — déterministe sous
    ``seed``. Fonction pure.
    """
    weights = bandit.prob_best(
        [(alpha, beta), (champ_alpha, champ_beta)], k=k, seed=seed)
    return float(weights[0])


def uncertainty(alpha, beta, champ_alpha, champ_beta, *,
                k=bandit.DEFAULT_K, seed=bandit.DEFAULT_SEED):
    """Incertitude ``U = 1 − |2·P(meilleur) − 1|`` (§3.3).

    Maximale (U=1) quand ``P(meilleur)=0.5`` (le nœud est indistinguable de son
    champion — plus incertain), nulle (U=0) quand ``P`` vaut 0 ou 1 (tranché).
    Déterministe sous ``seed``. Fonction pure.
    """
    p = prob_node_best(alpha, beta, champ_alpha, champ_beta, k=k, seed=seed)
    return 1.0 - abs(2.0 * p - 1.0)


def testability(delta_plausible, p, n, *, z_sum=mde.Z_SUM):
    """Testabilité ``T = clip(δ_plausible / δ_MDE, 0, 1)`` (§3.3).

    ``δ_MDE`` = effet absolu minimal détectable à ``n`` essais/bras au taux de
    base ``p`` (``mde.mde_absolute``). Un barreau dont l'effet plausible est
    au-dessus du MDE (δ_plausible ≥ δ_MDE) est PLEINEMENT testable (T=1) ; un
    barreau au MDE infaisable a ``T ≈ 0`` (le clip qui écrase le score des
    barreaux intestables — signature/qualifié). ``n ≤ 0`` ou ``δ_plausible ≤ 0``
    ⇒ T = 0. Fonction pure.
    """
    if n <= 0 or delta_plausible <= 0:
        return 0.0
    delta_mde = mde.mde_absolute(p, n, z_sum=z_sum)
    if delta_mde <= 0:
        return 1.0
    ratio = delta_plausible / delta_mde
    return max(0.0, min(1.0, ratio))


def voi_score(S, U, R, T, C):
    """VoI par dirham ``S·U·R·T / C`` (§3.3). Fonction pure.

    ``C ≤ 0`` ⇒ ``ValueError`` (un test a toujours un coût strictement positif).
    """
    if C <= 0:
        raise ValueError("Le coût C doit être strictement positif.")
    return (S * U * R * T) / C


# ── Scoring d'un nœud (lit le nœud, calcul pur) ───────────────────────────────
def _champion_for(node, champ_alpha, champ_beta):
    """Champion de référence pour U : l'override fourni, sinon le PRIOR du nœud
    (Beta(α₀,β₀)) — « le nœud est-il encore distinguable de sa croyance de base ? »."""
    ca = node.alpha0 if champ_alpha is None else champ_alpha
    cb = node.beta0 if champ_beta is None else champ_beta
    return ca, cb


def score_node(node, *, delta_plausible, p, n, cost,
               champ_alpha=None, champ_beta=None,
               k=bandit.DEFAULT_K, seed=bandit.DEFAULT_SEED):
    """VoI d'un nœud + ses composantes (§3.3).

    ``S``/``R`` viennent du nœud (``enjeux_s``/``pertinence_r``) ; ``U`` du
    posterior oublié vs le champion ; ``T`` du MDE (``delta_plausible``/``p``/``n``
    aux volumes courants) ; ``C`` = ``cost``. Renvoie un dict JSON-sûr
    ``{voi, S, U, R, T, C, p_best}``. Déterministe sous ``seed``.
    """
    ca, cb = _champion_for(node, champ_alpha, champ_beta)
    p_best = prob_node_best(node.alpha, node.beta, ca, cb, k=k, seed=seed)
    U = 1.0 - abs(2.0 * p_best - 1.0)
    T = testability(delta_plausible, p, n)
    S = float(node.enjeux_s)
    R = float(node.pertinence_r)
    voi = voi_score(S, U, R, T, cost)
    return {
        'voi': voi, 'S': S, 'U': U, 'R': R, 'T': T, 'C': float(cost),
        'p_best': p_best,
    }


# ── Ordonnanceur (I/O) ────────────────────────────────────────────────────────
def _candidate_nodes(company):
    """Nœuds candidats d'une société : tout sauf RETIRED (un nœud retiré ne
    revient jamais dans la file). Société-scopé, jamais élargi."""
    from .models import AssumptionNode
    return list(
        AssumptionNode.objects.filter(company=company)
        .exclude(statut=AssumptionNode.Statut.RETIRED))


def rank_candidates(company, params, *, champ=None,
                    k=bandit.DEFAULT_K, seed=bandit.DEFAULT_SEED):
    """Classe les nœuds candidats d'une société par VoI décroissant (§3.3).

    ``params`` : ``{node_pk: {'delta_plausible', 'p', 'n', 'cost'}}`` — le contexte
    MDE/coût par nœud aux volumes courants (fourni par l'appelant : rien n'est
    stocké sur le modèle). Un nœud sans entrée ``params`` est IGNORÉ (on ne peut
    pas dimensionner ce qu'on ne connaît pas). ``champ`` : override optionnel
    ``(alpha, beta)`` du champion commun. Renvoie ``[(node, score_dict), ...]``
    trié par ``voi`` décroissant (départage stable par ``-node.pk``).
    """
    champ_alpha = champ[0] if champ else None
    champ_beta = champ[1] if champ else None
    scored = []
    for node in _candidate_nodes(company):
        ctx = params.get(node.pk)
        if not ctx:
            continue
        score = score_node(
            node,
            delta_plausible=ctx['delta_plausible'], p=ctx['p'], n=ctx['n'],
            cost=ctx['cost'], champ_alpha=champ_alpha, champ_beta=champ_beta,
            k=k, seed=seed)
        scored.append((node, score))
    scored.sort(key=lambda pair: (pair[1]['voi'], pair[0].pk), reverse=True)
    return scored


def schedule_next(company, *, experiment, params, champ=None,
                  k=bandit.DEFAULT_K, seed=bandit.DEFAULT_SEED):
    """Ouvre un slot : sélectionne le nœud ``argmax VoI`` + ``DecisionLog`` OBLIGÉ.

    Calcule le VoI de chaque candidat (``rank_candidates``), prend l'argmax, et
    écrit un ``DecisionLog`` (ASG3 : aucune sélection sans trace) rattaché à
    ``experiment``. ``experiment.company`` DOIT être la ``company`` passée
    (invariant multi-tenant). Renvoie ``{'winner', 'score', 'ranking', 'log'}``
    (``winner``/``score``/``log`` valent ``None`` si aucun candidat testable).
    """
    if experiment.company_id != company.id:
        raise ValueError(
            "L'expérience doit appartenir à la société de l'ordonnanceur.")

    from . import decisionlog

    ranking = rank_candidates(company, params, champ=champ, k=k, seed=seed)
    if not ranking:
        # Aucun candidat testable : on trace quand même l'ouverture de slot vide.
        log = decisionlog.log_decision(
            experiment,
            inputs={'candidates': [], 'seed': int(seed), 'k': int(k)},
            posteriors={}, allocations={'winner_node_id': None},
            summary_fr="File VoI vide : aucun nœud testable à ordonnancer.")
        return {'winner': None, 'score': None, 'ranking': [], 'log': log}

    winner, winner_score = ranking[0]
    candidates = [
        {
            'node_id': node.pk,
            'enonce_fr': node.enonce_fr[:80],
            'classe': node.classe,
            'voi': round(score['voi'], 6),
            'S': round(score['S'], 4), 'U': round(score['U'], 4),
            'R': round(score['R'], 4), 'T': round(score['T'], 4),
            'C': round(score['C'], 4), 'p_best': round(score['p_best'], 4),
        }
        for node, score in ranking
    ]
    posteriors = {
        str(node.pk): [float(node.alpha), float(node.beta)]
        for node, _ in ranking
    }
    allocations = {
        'winner_node_id': winner.pk,
        'voi_scores': {str(node.pk): round(score['voi'], 6)
                       for node, score in ranking},
    }
    summary_fr = (
        f"Slot ouvert : nœud « {winner.enonce_fr[:60]} » choisi "
        f"(VoI={winner_score['voi']:.4f} = S{winner_score['S']:.2f}·"
        f"U{winner_score['U']:.2f}·R{winner_score['R']:.2f}·"
        f"T{winner_score['T']:.2f}/C{winner_score['C']:.2f}).")
    log = decisionlog.log_decision(
        experiment,
        inputs={'candidates': candidates, 'seed': int(seed), 'k': int(k)},
        posteriors=posteriors, allocations=allocations, summary_fr=summary_fr)
    logger.info(
        'voi.schedule_next: société=%s nœud gagnant=%s VoI=%.4f',
        company.pk, winner.pk, winner_score['voi'])
    return {'winner': winner, 'score': winner_score,
            'ranking': ranking, 'log': log}

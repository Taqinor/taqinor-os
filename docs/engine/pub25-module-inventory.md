# PUB25 — Inventaire de statut des modules « morts » de `apps/adsengine`

Statué le 2026-07-19. Objectif : **zéro module silencieusement mort** — chaque
module non câblé porte désormais un statut EXPLICITE (bloc `STATUT (PUB25 …)` dans
sa propre docstring). Aucun retrait sauf doublon AVÉRÉ (preuve grep) — aucun ne
l'était.

Méthode de preuve (par module, exécuté depuis `backend/django_core/apps/adsengine`) :

```
grep -rn "from \.<mod> import\|from \. import .*<mod>\|import <mod>\b\|<mod>\." \
  --include=*.py . | grep -v "^./tests/" | grep -v "^./<mod>.py:"
```

| Module | Appelant PRODUCTION ? | Verdict PUB25 |
|---|---|---|
| `authority.py` (ADSENG11) | Aucun (tests seuls) | **Documenté** — en attente du branchement de la table d'autorité dans le moteur de décision. |
| `dco.py` (ADSENG29) | Aucun (tests seuls) | **Documenté** — en attente d'un flux de création qui consulte l'arbitre DCO au cold-start. |
| `priors.py` (ASG8) | Aucun (tests seuls) | **Documenté** — en attente de la consommation des priors hiérarchiques par l'ordonnanceur VoI (aujourd'hui `voi._champion_for` = prior propre du nœud). |
| `seeding.py` (ASG5) | Aucun (tests seuls) | **Documenté + CONSERVÉ** — PAS un doublon : seul seed de l'ARBRE (les 4 commandes `seed_*` sèment faits / synthétique / config, jamais ce YAML §4). En attente de la commande de semis jour-0. |
| `cohorts.py` (SIG3) | Aucun (le `signature_cohorts` de `reporting.py` est une AUTRE fonction) | **Documenté** — non pris par PUB1 ; en attente de la lecture du filigrane de maturité par l'allocation/les garde-fous (`signal_guards.cpl_guard` a déjà sa propre maturation). |
| `assumption_graph.py` (ASG4) | Simulateur uniquement (`simulator.py`) | **Documenté** — cascade non déclenchée en PROD ; en attente d'un point de déclenchement réel (p.ex. évidence PUB18 significative → invalider les nœuds liés). |
| `policy_lint_config.py` (AGEN5) | `policy_lint.py` (lui-même non câblé au pipeline prod) | **Documenté** — en attente de l'insertion de `policy_lint` dans le pipeline `tier_router`/génération. |

## Remarques

- **`policy_lint.py`** (le moteur qui consomme `policy_lint_config`) est lui aussi
  non câblé en production : `generation.generate_grounded_variants` (câblé par
  PUB16) fait sa PROPRE garde d'ancrage numérique et n'invoque pas encore
  `policy_lint`. Les deux se débloqueront ensemble.
- **Aucun retrait** effectué : aucun module n'est un doublon avéré. `seeding.py`,
  soupçonné doublon dans le plan, est explicitement CONSERVÉ (preuve ci-dessus).
- Modules déjà câblés par ce même lot (pour mémoire, hors périmètre PUB25) :
  `rewards.py` (PUB15, beat), `generation.py` (PUB16, endpoint+tâche),
  `voi.py`/`schedule_next` (PUB17, `FlightRunner.advance_phase`),
  `reconciliation.run_daily_reconciliation` (PUB19, beat), et le nouveau writer
  `evidence.py` (PUB18).

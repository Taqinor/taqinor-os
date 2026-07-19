# WIR140 — `adsengine.anomaly` vs `core.anomaly` : dossier de DÉCISION

> **Décision : SÉPARATION DÉLIBÉRÉE — conservée.** `apps/adsengine/anomaly.py`
> ne consomme PAS le socle `core.anomaly`, et ne doit pas le faire. Les deux
> moteurs répondent à deux régimes statistiques et deux modèles de persistance
> différents ; les fusionner régresserait le design explicite dd-guardian §B.

## Les deux moteurs

| | `core.anomaly` (FG360) | `adsengine.anomaly` (ADSENG16) |
|---|---|---|
| Méthode | **z-score** (`scan_for_outliers`), écart standardisé sur une série | **ratios relatifs** (±2×, médiane 7/14 j), seuils à deux niveaux, statut Meta |
| Régime | séries DENSES (stock/paiements, n ≥ 4 exploitables) | données SMB ÉPARSES (5-15 leads/semaine) |
| Persistance | `core.models.AnomalyFlag` (générique : subject_type/metric/score) | `adsengine.models.AnomalyEvent` (kind ads, entity_meta_id, `rule_policy`, `alert`) |
| Sévérité | dérivée de l'amplitude du z-score | dérivée des règles métier (chute = CRITICAL, pic = WARNING…) |
| Lacune de données | renvoie 0 candidat (silencieux) | `insufficient_data` qui **ALERTE toujours** (info), jamais un skip muet (piège Madgicx, dd-guardian §B6) |

## Pourquoi la séparation est la bonne décision

1. **Le z-score n'a aucun sens à 5-15 leads/semaine.** dd-guardian §B2 le pose
   noir sur blanc : un écart-type sur n=2 est « pire qu'inutile ». Les bandes de
   `adsengine.anomaly` sont des RATIOS simples, explicables en une phrase FR au
   fondateur — pas des écarts standardisés. Réexprimer « dépense > 3× la médiane
   7 j » ou « annonce refusée par Meta » via `scan_for_outliers` (qui n'attend
   qu'une série numérique et un seuil z) est impossible sans dénaturer les
   détecteurs (zéro-delivery à deux niveaux, statut de révision, fatigue
   créative fréquence×CTR n'ont pas de forme « série → z-score »).

2. **Le socle ALERTE en silence, l'ads engine JAMAIS.** `core.anomaly` renvoie
   simplement moins de candidats quand l'échantillon est petit ; `adsengine`
   DOIT au contraire émettre un signal `insufficient_data` visible (le fondateur
   ne doit jamais croire « tout va bien » alors que la donnée manque). Ce
   comportement est le cœur du design dd-guardian et ne peut pas être délégué au
   socle.

3. **Persistances non fongibles.** `AnomalyEvent` porte des champs propres au
   domaine publicitaire (`kind`, `entity_meta_id`, lien `rule_policy`, lien
   `alert` du moteur de règles) absents de `AnomalyFlag`. Le socle resterait de
   toute façon incapable de matérialiser la trace attendue par `rules_engine`.

## Conséquence pour le code

- Les deux modules gardent chacun leur propre fonction `record_anomaly`
  (matérialisant respectivement `AnomalyFlag` et `AnomalyEvent`).
- `apps/adsengine/anomaly.py` **n'importe pas** `core.anomaly` — un test de garde
  (`test_anomaly.py::AnomalyEngineSeparationTests`) échoue si un futur
  refactor l'y rattache par mégarde.
- La dormance des flags génériques est traitée séparément (NTDATA42) et ne
  concerne que `core.anomaly` / `AnomalyFlag`.

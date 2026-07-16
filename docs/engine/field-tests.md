# Protocole de tests terrain du moteur publicitaire (ADSENG37)

> Les 7 inconnues que **seul le compte Meta réel** peut trancher (dd-meta-mechanics §j).
> Chaque test est un **micro-test SÛR** : budget plafonné, structures **PAUSED d'abord**
> (règle #3), **un seul facteur changé à la fois**. Aucun test ne dépense un budget réel
> large ni n'active quoi que ce soit sans un unpause **humain**.

## Garde-fous communs (constantes de config, jamais en dur)

Lus depuis `apps/adsengine/field_tests.py` :

| Garde-fou | Constante | Valeur |
|-----------|-----------|--------|
| Budget quotidien plafonné par test | `MICRO_TEST_MAX_DAILY_BUDGET_MAD` | 30 MAD |
| Toute structure naît PAUSED | `MICRO_TEST_START_PAUSED` | `True` |
| Un seul facteur par test | `MICRO_TEST_ONE_FACTOR_AT_A_TIME` | `True` |

**Règle d'or** : on crée la structure de test **PAUSED**, on l'unpause **à la main** pour
la fenêtre du test, on lit le résultat, on **repause à la main**. Le moteur ne dé-pause
jamais par programme (invariant #3).

## Où atterrissent les résultats

Chaque test résout une ou plusieurs **constantes de config** dans
`apps/adsengine/field_tests.py` (`CONSTANTS`). Tant qu'un test n'a pas tourné, sa
constante porte `source='research'` (borne documentaire non vérifiée). Une fois le test
fait, on met à jour **la valeur + `source='field_test'` dans cette table** — jamais un
littéral en dur ailleurs. Le reste du moteur lit `field_tests.value(<clé>)`.

`field_tests.pending_keys()` liste à tout instant les inconnues encore ouvertes.

---

## FT1 — Seuils exacts de reset d'apprentissage

**Inconnue** : le % de variation de budget et le nombre de conversions qui (re)déclenchent
la phase d'apprentissage. Recherche : ~20 % de budget / ~50 conversions par 7 j, **non
vérifié** ; une source unique évoque un durcissement « Andromeda » en avril 2026.

**Constantes** : `learning_reset_budget_pct` (20 %), `learning_reset_conversions` (50 / 7 j).

**Protocole (micro-test)** :
1. Créer 1 campagne + 1 ad set **PAUSED**, budget ≤ 30 MAD/j, une seule ad.
2. Unpause à la main ; laisser sortir de l'apprentissage.
3. Appliquer **une** hausse de budget de **+10 %** ; observer `effective_status` /
   le label « Apprentissage » avant/après.
4. Répéter à **+15 %** puis **+25 %** (un facteur à la fois) pour encadrer le vrai seuil.
5. Repauser à la main. Consigner le seuil observé → `learning_reset_budget_pct`.

**Note liée** : vérifier aussi si l'action d'une *règle automatisée* (`CHANGE_BUDGET`)
compte comme « edit significatif » (même observation qu'à l'étape 3).

**Premier test — à blanc (dry)** : protocole **écrit et prêt**, **pas encore exécuté**.
Résultat attendu à consigner : le plus petit % qui fait réapparaître le label
« Apprentissage ». Statut actuel : `source='research'` (valeur 20 % conservée par prudence,
et le pas moteur reste **plus conservateur** — ≤ 15 %, cf. `budget_applier`).

## FT2 — Viabilité d'un split-test à petit budget

**Inconnue** : le budget minimum réel pour que le Split Testing API / les Experiments natifs
rendent un résultat non dégénéré. Folklore ~20-50 $/j/variante ; guidance Meta ~100 $/j/
variante — au-dessus de tout notre budget.

**Constante** : `split_test_min_budget_mad` (200 MAD/j/variante).

**Protocole** : lancer **un** `SPLIT_TEST_V2` au budget réel de Taqinor (PAUSED puis unpause
humain) sur 2 semaines ; lire les chiffres de puissance/confiance que Meta **rapporte
lui-même**. Cela répond directement « l'outil est-il utilisable à notre échelle ? ».

## FT3 — Défauts des enhancements créatifs Advantage+

**Inconnue** : le `enroll_status` par défaut de chaque flag `degrees_of_freedom_spec`.
Politique produit : **no-fake-footage** → tout enhancement doit être **forcé OFF**.

**Constante** : `advantage_enhancement_default_on` (`True` par prudence → on force OFF).

**Protocole** : créer **un** `AdCreative` (PAUSED) avec `degrees_of_freedom_spec` **omis**,
relire l'objet, inspecter ce que Meta a supposé. Consigner les défauts réels.

## FT4 — Granularité du reporting DCO

**Inconnue** : le reporting DCO remonte-t-il par **asset** ou seulement par **ad** ? Détermine
si l'attribution par variante (ADSENG6) reste fiable sous DCO.

**Constante** : `dco_reporting_granularity` (`None` — inconnue).

**Protocole** : activer DCO sur **une** ad de test (PAUSED puis unpause humain, budget ≤ 30
MAD/j), lire les insights et vérifier la présence d'une ventilation par asset.

## FT5 — Coûts réels du Business-Use-Case (rate limiting)

**Inconnue** : le vrai barème de points BUC (coût lecture vs écriture) — divergence non
résolue entre dossiers.

**Constantes** : `buc_read_cost_points` (1), `buc_write_cost_points` (3).

**Protocole** : comparer l'en-tête `X-Business-Use-Case-Usage`
(`call_count`/`total_cputime`) après **un** appel lecture vs **un** appel écriture réels.

## FT6 — Rotation intra-ad-set (« Even Rotation »)

**Inconnue** : « Even Rotation » entre plusieurs ads d'un même ad set est-il encore un champ
réglable par API en 2026 ?

**Constante** : `even_rotation_api_settable` (`None` — inconnue).

**Protocole** : créer 2 ads dans **un** ad set **sans** toucher au réglage de rotation
(PAUSED puis unpause humain, budget ≤ 30 MAD/j) ; observer sur quelques jours si la dépense
se répartit également ou se concentre.

## FT7 — Gating par palier d'accès (vérification business)

**Inconnue** : le niveau de vérification business / palier d'accès gate-t-il spécifiquement
`adrules_library` ou `ad_studies` (au-delà du CRUD de campagne, confirmé atteignable) ?

**Constantes** : `access_tier_gates_rules_library`, `access_tier_gates_ad_studies` (`None`).

**Protocole** : tenter **un** POST `adrules_library` et **un** POST `ad_studies` sur le compte
réel ; consigner s'ils réussissent au palier courant.

---

## Après un test

1. Mettre à jour la (les) constante(s) dans `apps/adsengine/field_tests.py` : nouvelle
   `value` + `source='field_test'`.
2. Vérifier que `field_tests.is_field_tested(<clé>)` est vrai et que la clé sort de
   `pending_keys()`.
3. Ne **jamais** dupliquer la valeur en dur dans un autre module — les consommateurs lisent
   `field_tests.value(<clé>)`.

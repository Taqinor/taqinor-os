# Vérifie AANA — contre-visite de clôture du groupe analyse (X7), 11/10/2026

Commande `vérifie AANA` (METHODE §C.4.2, skill audit §5), déclenchée par `audit_registre.py --du` : le groupe compte
**48 tâches cochées sur 51** constructibles (**94 %**) ; la contre-visite (proche clôture, ≥ 50 %) est due, première du
groupe. 9ᵉ de la boucle (ordre par nombre de tâches cochées décroissant).

La contre-visite n'a rien construit, n'a lancé aucun deploy, n'a rien écrit (lecture seule, sans pile).

## 0. Préconditions

- **SHA.** `origin/main` = `94c2ef70b` (re-fetch en début d'itération). Branche de claim : `verifie-aana`.
- **Registre.** X7 `analyse`, groupe AANA, propriétaire majoritaire `PLAN_AUDIT_ANALYSE.md` (44), plus deploy (3) et lead (1).
- **Inventaire (déterministe).** 51 tâches AANA, 48 `[x]`.
- **Échantillon (graine = SHA `94c2ef70b`).** Toutes les P0/S1 cochées (11) + 25 % du reste (9 sur 37). Total :
  **20 tâches**.

## 1. Vérificateurs (20 agents frais, opus, effort élevé, lecture seule, même répertoire)

Un vérificateur frais par tâche (jamais l'auteur), un seul workflow fan-out.

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **20** | AANA1, 2, 3, 4, 6, 9, 12, 13, 15, 19, 20, 22, 26, 30, 34, 35, 41, 45, 46, 52 |
| partiel / non-fait / faux / régression / déjà-présent | 0 | — |

**Constats S1-S2 : 0.** Pas de critique Fable. Aucune tâche v3 `ÉCARTS` à déposer.

Points saillants des tâches jugées ok (agent SQL, étanchéité, KPI) :

- **AANA2/3/4 (sécurité de l'agent SQL NL→SQL).** La « preuve par regex » est remplacée par une réécriture d'arbre
  `sqlglot` : chaque table lue devient `(SELECT * FROM <t> WHERE company_id=<jeton>)`, liste BLANCHE de fonctions
  fail-closed, projection ligne entière (`row_to_json`/`alias.*`) refusée sur les tables sensibles (mots de passe, TOTP,
  `prix_achat`). Seul le SQL régénéré est exécuté (point d'entrée unique) ; tests comportementaux sur Postgres réel à deux
  sociétés, jumeaux regex supprimés.
- **AANA1 (taux d'acceptation du dashboard).** `taux_acceptation_pct = round(acceptés/total×100,1)`, `None` si 0 devis,
  queryset scopé société ; contrat `dashboard.json` servi et validé par `check_api_shapes`.
- **AANA6 (agent SQL désactivé en prod sans rôle dédié).** En prod sans `SQL_AGENT_DB_USER`, l'agent répond 503 nommant la
  variable, le LLM n'est jamais atteint ; plus de repli silencieux sur le rôle propriétaire. Test comportemental (503,
  `calls==[]`).
- **AANA9 (import : mapping de champs sensibles refusé).** `company_id`/`owner_id`/`is_deleted` absents de `FIELD_MAPS` ;
  save → 400 sans persistance, apply les ignore ; company forcée serveur ; jumeau IA filtre la même liste blanche.

## 2. Tests nommés

- Les 20 tâches ont un test nommé **présent et comportemental** (assert sur la valeur calculée/servie, Postgres réel pour
  l'agent SQL). Les mentions de leçons (AANA13/45/52) sont des notes de vérificateurs sans divergence — verdict ok.
  Non rejoués localement (lecture seule, sans pile) : raisonnés par lecture ; vert de la CI de `94c2ef70b`.

## 3. Sondes

Aucune sonde déposée : aucun écart retenu. Les clauses d'étanchéité de l'agent SQL et d'exactitude des KPI ont été jugées
tenues par lecture du code de production (réécriture AST scopée société, dénominateurs corrects).

## 4. Écarts retenus

**Aucun.** 20/20 ok, 0 S1-S2, 0 S3.

## 5. Optionnel (non déposé)

- AANA6 : commentaire périmé `sql_agent_service.py:1116-1117` (« Retombe sur DATABASE_URL ») — chemin court-circuité par le
  503, sans impact comportemental.

## 6. Couverture et non-couvert

- **Couvert.** 20 tâches sur 48 cochées (toutes les P0/S1 + 25 %). Commits, tests nommés, code de production, contrats.
- **Non couvert.** Les 28 autres tâches cochées ; aucun aller-retour en direct (lecture seule, sans pile).
- **Statut du registre.** Après ce dépôt : 48/51 cochées (94 %), contre-visite **sans écart S1-S2**. La clôture stricte
  (≥ 95 %) et la sortie du cycle (deux contre-visites consécutives à zéro S1-S2) restent dues plus tard.

## 7. Coût

- 20 vérificateurs opus (effort élevé) : **≈ 1,61 M de jetons**, 303 appels d'outil, ≈ 25 min. Aucun appel Fable.
- Orchestrateur : échantillon déterministe, triage des 20 verdicts, rédaction.

<!-- verifie | groupe: AANA | pct: 94 | ecarts_s1_s2: 0 -->

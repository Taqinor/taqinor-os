# Vérifie APRF — contre-visite mi-parcours du groupe performance (X6), 11/10/2026

Commande `vérifie APRF` (METHODE §C.4.2, skill audit §5), déclenchée par `audit_registre.py --du` : le groupe compte
**33 tâches cochées sur 42** constructibles (**78 %**) ; la contre-visite de **mi-parcours** (≥ 50 %) est due, première du
groupe. 12ᵉ de la boucle (ordre par nombre de tâches cochées décroissant). Groupe PERFORMANCE : vérificateurs attentifs aux
budgets de requêtes (CaptureQueriesContext à deux tailles), au préchargement réellement consommé, et à l'absence d'écriture
sur un chemin de lecture.

La contre-visite n'a rien construit, n'a lancé aucun deploy, n'a rien écrit (lecture seule, sans pile).

## 0. Préconditions

- **SHA.** `origin/main` = `0d5ebcfb6` (re-fetch en début d'itération). Branche de claim : `verifie-aprf`.
- **Registre.** X6 `performance`, groupe APRF, tâches réparties sur 13 plans (transverse 7, devis 5, stock 4…).
- **Inventaire (déterministe).** 42 tâches APRF, 33 `[x]`.
- **Échantillon (graine = SHA `0d5ebcfb6`).** 0 P0/S1 cochée + 25 % du reste (8 sur 33). Total : **8 tâches**.

## 1. Vérificateurs (8 agents frais, opus, effort élevé, lecture seule, même répertoire)

Un vérificateur frais par tâche (jamais l'auteur), un seul workflow fan-out.

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **8** | APRF2, 6, 7, 10, 15, 19, 33, 34 |
| partiel / non-fait / faux / régression / déjà-présent | 0 | — |

**Constats S1-S2 : 0.** Pas de critique Fable. Aucune tâche v3 `ÉCARTS` à déposer.

Points saillants des tâches jugées ok (budget de requêtes, préchargement) :

- **APRF2 (mémoïsation `TariffSettings.get`).** Mémoïsation par requête (clé par société), consommée par tous les
  appelants ; test CaptureQueriesContext (10 lectures = 1 requête en scope, save() d'une autre instance relu frais).
- **APRF7 / APRF15 (préchargement `devis_avec_totaux`).** `prefetch_related('lignes__produit')` réellement consommé par
  `lignes_avec_produit` (pas de prefetch mort) ; requêtes CONSTANTES à 5 vs 15 (et 3 vs 15) devis ; `ids=[]` refusé 400 à
  l'export (plus « toute la société »).
- **APRF10 (SLA : plus de `.exists()` par lead).** Les lead_id déjà escaladés lus en UNE requête/société puis testés en
  mémoire ; coût indépendant du stock dormant ; jumeau rappels couvert ; `dry_run` → aucune écriture sur le chemin budget.

## 2. Tests nommés

- Les 8 tâches ont un test nommé **présent et comportemental** (`CaptureQueriesContext` à deux tailles, requêtes
  constantes, zéro écriture, égalité au centime vs lecture non préchargée). Non rejoués localement (lecture seule, sans
  pile) : raisonnés par lecture ; vert de la CI de `0d5ebcfb6`.

## 3. Sondes

Aucune sonde déposée : aucun écart retenu. Les budgets de requêtes et l'absence d'écriture sur les GET ont été jugés tenus
par lecture du code de production et des tests comportementaux.

## 4. Écarts retenus

**Aucun.** 8/8 ok, 0 S1-S2, 0 S3.

## 5. Optionnel (non déposé)

- Néant de significatif : aucun verdict n'a signalé de leçon violée.

## 6. Couverture et non-couvert

- **Couvert.** 8 tâches sur 33 cochées (0 P0/S1 au groupe + 25 %). Commits, tests comportementaux de budget, code de prod.
- **Non couvert.** Les 25 autres tâches cochées ; aucun aller-retour en direct (lecture seule) — la preuve live du groupe
  est APRF42 (acceptation).
- **Statut du registre.** Après ce dépôt : 33/42 cochées (78 %), contre-visite mi-parcours **sans écart S1-S2**. La clôture
  (≥ 95 %) et la sortie du cycle restent dues plus tard.

## 7. Coût

- 8 vérificateurs opus (effort élevé) : **≈ 0,67 M de jetons**, 137 appels d'outil, ≈ 17 min. Aucun appel Fable.
- Orchestrateur : échantillon déterministe, triage des 8 verdicts, rédaction.

<!-- verifie | groupe: APRF | pct: 78 | ecarts_s1_s2: 0 -->

# Vérifie AANA — contre-visite des correctifs de l'unité X7 « analyse », 10/11/2026

Commande `loop audit` (10/11). La contre-visite du 04/11 (`docs/audits/2026-11-04-analyse-verifie.md`) avait trouvé 3 écarts
S1-S2 et déposé 11 tâches d'écart (AANA80-90) ; 9 ont été construites et cochées depuis, sans jamais être relues.
Contre-visite lancée à la main (le script de registre ne la redemande pas). Rien n'a été construit ni déployé.

## 0. Préconditions

- **SHA.** `origin/main` = `c1a99568a`. Branche de claim : `verifie-correctifs-lot1-1011`.
- **Registre.** X7 `analyse`, groupe AANA, 87 tâches cochées sur 88.
- **Échantillon.** Les 9 tâches d'écart cochées : AANA80, 82, 83, 84, 85, 86, 87, 88, 89. Les 2 autres (AANA81, bloquée ;
  AANA90, acceptation) ne sont pas cochées : listées en §6, non vérifiées.
- **Pile locale.** Aucune ; verdicts par lecture des commits, du code sur `origin/main`, des tests nommés et des traces de
  rejeu du 04/11 ; un test de script lancé sur l'hôte.

## 1. Vérificateur (1 lot, opus, effort élevé, frais, même répertoire)

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **9** | AANA80, 82, 83, 84, 85, 86, 87, 88, 89 |
| partiel / non-fait / faux / régression | **0** | — |

Écarts S1-S2 du 04/11 : **2 fermés sur 3**. Fermés : la marge d'un devis à deux options et à plusieurs villas (chiffre
d'affaires de l'option retenue, coût des quantités vendues), lue par la rentabilité, les commissions et le coût de revient
(AANA80, le S1) ; les colonnes d'import annoncées mais jamais lues, retirées (AANA82). Le troisième (l'assistant qui
additionnait les lignes d'un devis, AANA81) est corrigé dans le code, mais sa tâche reste bloquée sur sa preuve en direct
(fournisseur d'IA refusant la clé) : elle n'est pas cochée et n'a pas été vérifiée.

## 2. Tests nommés

Tous présents et comportementaux (chiffres fixes, requêtes HTTP, réimport). Deux tests réalignés par AANA80 tirent leur
attente de la source plutôt que d'un chiffre fixe ; le nouveau test, lui, garde des chiffres fixes.

## 3. Sondes

Les cinq sondes de la contre-visite du 04/11 demandent Django : lues, non rejouées. Les traces de rejeu du 04/11
(`docs/audits/acceptation/AANA/traces/`) ne reproduisent plus l'écart S1.

## 4. Écarts retenus

Aucun sur les tâches cochées.

## 5. Optionnel (non déposé)

- AANA81 (ouverte) : son test est sauté sur l'hôte (dépendance absente) et n'est pas dans la liste des tests du service d'IA
  jouée à chaque PR : il ne tourne que la nuit. Le motif qui repère la somme des lignes ne voit pas l'ordre inverse des
  facteurs. À traiter avec la tâche.
- AANA89 : le total d'un devis pour un projet ne multiplie pas par le nombre de villas (hors du texte ; application parquée).

## 6. Couverture et sortie de cycle

- **Couvert.** Les 9 tâches d'écart cochées ; lecture du code, des commits, des tests et des traces.
- **Non couvert, tâches encore ouvertes.** AANA81 (bloquée sur sa preuve en direct), AANA90 (acceptation, à l'orchestrateur
  d'une session avec pile locale).
- **Non couvert, reste.** Les 78 autres tâches cochées ; aucune sonde ni test Django rejoué.
- **Statut.** Aucun écart sur les tâches cochées, mais un écart S2 du 04/11 reste ouvert (AANA81, non cochée) : le marqueur en
  garde 1 et AANA reste « construit » jusqu'à ce que cette tâche soit cochée puis relue.

## 7. Coût

- 1 vérificateur (opus, effort élevé) ≈ 0,2 M de jetons ; aucun appel Fable.

<!-- verifie | groupe: AANA | pct: 98 | ecarts_s1_s2: 1 -->

# Vérifie ASUP — contre-visite de mi-parcours du parcours PF10 « suppression et archivage », 13/11/2026

Commande `loop audit` (13/11). L'audit de parcours PF10 (11/11, PR #1366) avait déposé ASUP1-55. Première contre-visite du
groupe, due à mi-parcours (11 tâches cochées sur 12 constructibles). Rien n'a été construit ni déployé.

## 0. Préconditions

- **SHA.** `origin/main` = `bbe833192`. Branche de claim : `verifie-pf-1311`.
- **Registre.** PF10 `suppression-archivage`, groupe ASUP, 11 tâches cochées sur 12 constructibles (91 %).
- **Échantillon.** Sur précision du fondateur (13/11 : pousser le parallélisme), les **11 tâches cochées** sont relues, pas
  seulement le tirage de 8 : ASUP16, 19, 20, 21, 22, 23, 50, 51, 53, 54, 55. Aucune tâche P0 / S1 n'est cochée.
- **Méthode.** Lecture des commits, du code sur `origin/main` et des tests nommés ; une sonde hôte rejouée. Aucune pile, aucun
  test Django lancé, aucune production consultée.

## 1. Vérificateur (1 lot, opus, effort élevé, frais)

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **11** | ASUP16, 19, 20, 21, 22, 23, 50, 51, 53, 54, 55 |
| partiel / non-fait / faux / régression / déjà-présent | **0** | — |

Commits relus : ASUP16 `f54555049c`, ASUP19 `83056c4636`, ASUP20 `791b4fa316`, ASUP21 `414a631694` et `c5b9efa73c`,
ASUP22 `52cb72290c`, ASUP23 `e8363fce3d`, ASUP50 `f0a49f5fb8`, ASUP51 `34a56cdd3e`, ASUP53 `cda458a854`, ASUP54 `0b82448ac4`,
ASUP55 `57ae06fa37` et `2d5cdd1ecd`. Les jumeaux et les routes `/api/v1` ont été relus.

## 2. Tests nommés

Les onze tests nommés existent et sont comportementaux : appel HTTP ou vrai service, rôles réels, état relu en base. Le cas
« produit actif » d'ASUP53 n'est joué que par le sérialiseur (voir §5).

## 3. Sondes et preuve en direct

- Aucune tâche cochée ne porte de sonde propre (constats lus). La sonde 015 du dossier PF10 (même cause qu'ASUP51), rejouée
  sur l'hôte : `repro: False`, code 0.
- **Le S1 du dossier n'est pas fermé.** « Anonymiser (RGPD) » d'un client facturé : aucune tâche cochée ne le ferme. Il est
  porté par ASUP1 et ASUP3 (`docs/plans/PLAN_AUDIT_FACTURATION.md`) et ASUP2 (`docs/plans/PLAN_AUDIT_LEAD.md`), toutes
  bloquées sur leur preuve en direct. Le code est sur l'arbre (l'acheteur est figé avant l'effacement), non vérifié ici. La
  sonde 001 du dossier ne tourne plus sur l'hôte (`ModuleNotFoundError apps.facturation`, import ajouté par ASUP2) : à
  rejouer sur la pile par l'orchestrateur qui jouera l'acceptation.
- Les décisions D-ASUP-1 à D-ASUP-6 restent ouvertes ; aucune ne conditionne le S1.

## 4. Écarts retenus

Aucun sur les tâches cochées.

## 5. Optionnel (non déposé)

- `CLAUDE.md` dit encore que le seeder archive les six coffrets estimés ; périmé depuis ASUP55.
- D-ASUP-2 liste encore ASUP55, pourtant cochée.
- Le test d'ASUP53 vérifie le cas « produit actif » par le sérialiseur seul, pas par un PATCH 200.
- Le correctif de CI d'ASUP21 a ajouté une quinzaine de lignes dans le viewset des tickets.
- Fonctions d'appel mortes côté écran et un commentaire « archivez-le » périmé sur la ligne de devis.

## 6. Couverture et sortie de cycle

- **Couvert.** Les 11 tâches cochées : code, commits, tests nommés, jumeaux.
- **Non couvert.** Aucun test Django lancé (la preuve des tests est la CI de `main`) ; aucun rejeu navigateur ; ASUP1, 2, 3
  (le S1) et les tâches en attente de décision.
- **Statut.** Zéro écart S1-S2 sur les tâches cochées. Le groupe n'est pas « construit » : la contre-visite de clôture reste
  due quand le S1 sera coché.

## 7. Coût

- 1 vérificateur (opus, effort élevé) ≈ 0,2 M de jetons ; aucun appel Fable.

<!-- verifie | groupe: ASUP | pct: 91 | ecarts_s1_s2: 0 -->

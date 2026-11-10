# Vérifie ASTK — contre-visite des correctifs de l'unité J3 « stock », 10/11/2026

Commande `loop audit` (10/11). La contre-visite du 04/11 (`docs/audits/2026-11-04-stock-verifie.md`) avait trouvé 3 écarts
S1-S2 ; les 7 tâches d'écart ASTK257-263 ont été construites et cochées depuis, sans jamais être relues. Le script de registre
ne redemande pas de contre-visite après des écarts corrigés : celle-ci est lancée à la main. Rien n'a été construit ni déployé.

## 0. Préconditions

- **SHA.** `origin/main` = `c1a99568a`. Branche de claim : `verifie-correctifs-lot1-1011`.
- **Registre.** J3 `stock`, groupe ASTK, 208 tâches cochées sur 208.
- **Échantillon.** Les 7 tâches d'écart du 04/11, toutes cochées : ASTK257, 258, 259, 260, 261, 262, 263.
- **Pile locale.** Aucune ; verdicts par lecture des commits, du code sur `origin/main` et des tests nommés.

## 1. Vérificateur (1 lot, opus, effort élevé, frais, même répertoire)

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **7** | ASTK257, 258, 259, 260, 261, 262, 263 |
| partiel / non-fait / faux / régression | **0** | — |

Les trois écarts S1-S2 du 04/11 sont fermés : après une facture ou un acompte, la saisie de pose ne ressort plus le stock une
seconde fois (ASTK257-258) ; une livraison directe au chantier après facture ne sort que le reliquat (ASTK259) ; une facture
d'acompte annulée fait rentrer le stock et rouvre la réservation, et la sortie de l'étape « Signé » n'est plus refusée
(ASTK262-263). Cherché sans défaut trouvé : double retour par avoir, entrées écrites par d'autres chemins, signal émis hors
transaction, correctif défait par un commit postérieur.

## 2. Tests nommés

Tous présents et comportementaux (stock relu, réponse HTTP). Aucun test affaibli. Le test d'ASTK259 simule la facture par un
appel direct au lieu de la route d'émission ; la route est couverte par le rejeu d'acceptation du 04/11. Aucun test rejoué en
local (CI d'abord).

## 3. Sondes

Les six sondes de la contre-visite du 04/11 demandent Django : lues, non rejouées. Les traces d'acceptation du 04/11
(`docs/audits/acceptation/ASTK/`) montrent les parcours « acompte puis pose » et « acompte, commande directe, pose » passés, et
le rejeu de la sonde de l'acompte annulé sans reproduction.

## 4. Écarts retenus

Aucun.

## 5. Optionnel (non déposé)

- La trace de la sonde de l'acompte annulé porte un en-tête « verdict : ÉCART » alors que son résultat ne reproduit plus :
  libellé périmé de l'outil d'enregistrement.
- Par décision du fondateur (aucune garde « matériel posé »), une facture annulée après la pose fait rentrer le stock jusqu'à
  la facture suivante.
- Un avoir de retour client n'est pas déduit des sorties de la vente (avoir puis pose : cas limite non sondé).
- Le cas d'un devis révisé (nouvelle référence) dans la somme des sorties de la vente n'a pas été examiné.

## 6. Couverture et sortie de cycle

- **Couvert.** Les 7 tâches d'écart ; lecture du code, des commits, des tests et des traces d'acceptation.
- **Non couvert.** Les 201 autres tâches cochées (échantillonnées par les contre-visites précédentes) ; aucune sonde rejouée ;
  aucun rejeu navigateur.
- **Statut.** 0 écart S1-S2 ⇒ ASTK passe « vérifié ».

## 7. Coût

- 1 vérificateur (opus, effort élevé) ≈ 0,2 M de jetons ; aucun appel Fable.

<!-- verifie | groupe: ASTK | pct: 100 | ecarts_s1_s2: 0 -->

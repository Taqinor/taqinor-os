# Vérifie ATOT — contre-visite des correctifs de l'unité X2 « totaux », 10/11/2026

Commande `loop audit` (10/11). La contre-visite du 04/11 (`docs/audits/2026-11-04-totaux-verifie.md`) avait trouvé 1 écart S2 ;
les 7 tâches d'écart ATOT56-62 ont été construites et cochées depuis, sans jamais être relues. Contre-visite des correctifs
(METHODE §C.4 point 6). Rien n'a été construit ni déployé.

## 0. Préconditions

- **SHA.** `origin/main` = `c1a99568a`. Branche de claim : `verifie-correctifs-lot3-1011`.
- **Registre.** X2 `totaux`, groupe ATOT, 58 tâches cochées sur 58.
- **Échantillon.** Les 7 tâches d'écart du 04/11, toutes cochées : ATOT56 à ATOT62.
- **Pile locale.** Aucune ; verdicts par lecture des commits, du code sur `origin/main`, des tests nommés et de
  l'enregistrement d'acceptation du 05/11 ; la garde des formes d'API lancée sur l'hôte (verte).

## 1. Vérificateur (1 lot, opus, effort élevé, frais, même répertoire)

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **7** | ATOT56, 57, 58, 59, 60, 61, 62 |
| partiel / non-fait / faux / régression | **0** | — |

L'écart S2 du 04/11 est fermé : un avoir sur une facture à plusieurs taux de TVA est borné taux par taux à ce qui reste
créditable, et rien n'est écrit quand le plafond est dépassé (ATOT56) ; le chemin du prix négocié passe par le même
constructeur. Tiennent aussi : l'invariant de double facturation (ATOT57), le verrou d'émission de deux factures simultanées
(ATOT58), l'avoir de révision à confirmer servi à l'écran et confirmé par sa route, avec le même montant des deux côtés
(ATOT59 à ATOT62).

## 2. Tests nommés

Tous présents et comportementaux, non modifiés depuis leur commit ; verts dans la CI de la PR qui les a portés. Le test de
course d'ATOT58 (deux fils) n'a pas de trace d'un passage rouge avant correctif : la gravité « argent » de cette course n'a
été ni prouvée ni infirmée. Deux refus prévus (ATOT59, ATOT62) ne sont couverts que par l'acceptation en direct ou la lecture.

## 3. Sondes

Les sondes de la contre-visite du 04/11 demandent Django : deux lues, deux non lues, aucune rejouée. L'enregistrement
d'acceptation du 05/11 (`docs/audits/acceptation/ATOT/`) donne la sonde de l'écart S2 sans reproduction. Une sonde est
devenue injouable : elle importe des vues déplacées depuis vers l'application de facturation.

## 4. Écarts retenus

Aucun.

## 5. Optionnel (non déposé)

- ATOT56 garde une fonction que la tâche demandait de supprimer (justifié dans le commit ; sans effet sur les montants).
- ATOT57 : après une révision à la baisse avec avoir confirmé, l'invariant laisse passer une facturation jusqu'au total de
  la première version (dessin écrit dans la tâche).
- La sonde de la course d'émission est à réaligner sur le nouvel emplacement des vues.

## 6. Couverture et sortie de cycle

- **Couvert.** Les 7 tâches d'écart ; lecture du code, des commits, des tests et de l'enregistrement d'acceptation.
- **Non couvert.** Les 51 autres tâches cochées (échantillonnées par les contre-visites précédentes) ; aucune sonde ni test
  Django rejoué.
- **Statut.** 0 écart S1-S2 ⇒ ATOT passe « vérifié ».

## 7. Coût

- 1 vérificateur (opus, effort élevé) ≈ 0,2 M de jetons ; aucun appel Fable.

<!-- verifie | groupe: ATOT | pct: 100 | ecarts_s1_s2: 0 -->

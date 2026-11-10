# Vérifie AGNR — contre-visite des correctifs de l'unité D4 « générateur », 10/11/2026

Commande `loop audit` (10/11). La contre-visite du 04/11 (`docs/audits/2026-11-04-générateur-verifie.md`) avait trouvé 2 écarts
S1-S2 ; les 13 tâches d'écart AGNR63-75 ont été construites et cochées depuis, sans jamais être relues. Contre-visite des
correctifs (METHODE §C.4 point 6). Rien n'a été construit ni déployé.

## 0. Préconditions

- **SHA.** `origin/main` = `c1a99568a`. Branche de claim : `verifie-correctifs-lot3-1011`.
- **Registre.** D4 `générateur`, groupe AGNR, 76 tâches cochées sur 76.
- **Échantillon.** Les 13 tâches d'écart du 04/11, toutes cochées : AGNR63 à AGNR75.
- **Pile locale.** Aucune ; verdicts par lecture des commits, du code sur `origin/main`, des tests nommés et des traces
  d'acceptation du 05/11 ; deux tests sans dépendance lancés sur l'hôte (13 et 6 réussis), une garde rejouée.

## 1. Vérificateur (1 lot, opus, effort élevé, frais, même répertoire)

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **12** | AGNR64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75 |
| partiel | **1** | AGNR63 (deux gestes qui changent le total ne repassent pas l'échéancier par la règle) |
| non-fait / faux / régression | **0** | — |

AGNR63 à 68 ont été relues par le vérificateur ; AGNR69 à 75 par un second lecteur qu'il a mandaté, dont le retour est repris
sans contre-vérification. Les deux écarts S1-S2 du 04/11 sont fermés : plus aucune tranche d'échéancier négative ni case
coupée sans avertissement sur les nouveaux rendus — le geste est rebasé ou refusé, l'impression est bornée au reste, un devis
envoyé avant garde son rendu (AGNR63 à 66) ; une série de factures qui mélange des mois saisis et estimés bloque
l'enregistrement en nommant le mois (AGNR67).

## 2. Tests nommés

Tous présents. Ceux du serveur sont comportementaux (vraies routes, valeurs fixes). Trois tests d'écran (AGNR67, 68, 73) ne
font que lire le source par expressions régulières : un changement qui casse le comportement sans toucher ces motifs resterait
vert ; AGNR68 n'a aucune preuve en direct.

## 3. Sondes

Les sondes de la contre-visite du 04/11 demandent Django ou les dépendances du navigateur : lues, non rejouées. Les traces
d'acceptation du 05/11 ne reproduisent plus l'écart S1 ; l'écran d'AGNR67 a été vu passé le 05/11.

## 4. Écarts retenus

| C-id | Tâche d'origine | Grav. | Écart | Sonde | Tâches |
|---|---|---|---|---|---|
| C-AGNR-VER5-063 | AGNR63 | S3 | « reprendre les valeurs du lead » et la révision d'un devis commercial après visite changent le total sans repasser l'échéancier par la règle : l'impression reste bornée, mais l'échéancier enregistré peut rester hors règle (une tranche à zéro disparaît du texte des conditions) ; seul un devis envoyé avant le nouveau niveau de règles pourrait montrer un chiffre faux — déduit, non reproduit | STATIQUE (lecture) | AGNR77 |
| C-AGNR-VER5-067 | AGNR67, AGNR68, AGNR73 | S3 | le comportement à l'écran n'est testé que par lecture du source | STATIQUE (lecture) | AGNR78 |

Aucun écart S1-S2 : ni seconde lentille ni critique (METHODE §C.4).

## 5. Optionnel (non déposé)

- AGNR74 : quand les deux options ont le même nombre de panneaux mais une puissance unitaire différente, le prix au kWc divise
  par la puissance de l'option sans batterie (même règle que le serveur).
- AGNR69, AGNR70 : un calcul jumeau prend encore la puissance de la première ligne ; il est ignoré en mode automatique, son
  affichage à l'écran n'a pas été vérifié.

## 6. Couverture et sortie de cycle

- **Couvert.** Les 13 tâches d'écart ; lecture du code, des commits, des tests et des traces.
- **Non couvert.** Les 63 autres tâches cochées (échantillonnées par les contre-visites précédentes) ; aucune sonde rejouée ;
  la persistance d'AGNR67 (enregistrer puis rouvrir) ; l'endroit où le vendeur voit l'avertissement d'AGNR66.
- **Statut.** 0 écart S1-S2 ⇒ AGNR passe « vérifié » ; restent les tâches d'écart S3.

## 7. Coût

- 1 vérificateur + 1 rédacteur (opus, effort élevé) ≈ 0,5 M de jetons ; aucun appel Fable.

<!-- verifie | groupe: AGNR | pct: 100 | ecarts_s1_s2: 0 -->

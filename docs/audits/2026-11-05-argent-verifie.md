# Vérifie AARG — contre-visite de clôture du parcours PA4 « argent », 05/11/2026

Commande `loop audit` (reprise du 05/11). La contre-visite de mi-parcours du 04/11 (82 %) avait déposé AARG59-62 ; le groupe
compte 60 tâches cochées sur 62 (AARG44, AARG50 ouvertes, 97 %) : la clôture est due. La contre-visite n'a rien construit, n'a
lancé aucun deploy, n'a rien écrit en prod ; la prod a été LUE (requêtes en lecture seule, accord permanent) par la seconde
lentille du S1. Pile locale partagée (code du conteneur en retard sur `main`, sans effet sur les chemins sondés) ; chaque sonde
tourne en transaction annulée.

## 0. Préconditions

- **SHA.** `origin/main` = `2781a2049`. Branche de claim : `verifie-aarg-0511`.
- **Registre.** PA4 `argent`, groupe AARG, 62 tâches, 60 `[x]`.
- **Échantillon (graine = SHA `2781a2049`).** Les 8 P0/S1 cochées + AARG59-62 (écarts du 04/11) + 13 tirées = **25 tâches**,
  3 lots.
- **Déjà déposé, non redéposé.** ATOT56-62 (avoirs multi-taux, émission concurrente), ASEC67-68 (émission et avoir sans
  `encaisser`), AGNR63-66, ACVI102.

## 1. Vérificateurs (3 lots, opus, effort élevé, frais, même répertoire)

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **21** | AARG1, 4, 7, 8, 10, 11, 12, 13, 16, 19, 21, 24, 28, 31, 32, 38, 41, 52, 54, 59, 60 |
| partiel | **4** | AARG2 (jumeau : retenues non rendues à la restauration), AARG18 (jumeau : la mise à jour d'un BC saute la garde de version), AARG61 (jumeau : retard affiché), AARG62 (échec d'envoi muet) |
| non-fait / faux / régression | **0** | — |

Écarts du 04/11 : AARG59 et AARG61 cochés « déjà présents » — le code vient bien de commits sur `main` (ticks posés par une
autre session) ; AARG59 fermé (sonde VER1-107 rejouée), AARG60 tient, AARG62 partiel.

## 2. Tests nommés

Tous présents dans un module existant et non affaiblis (les commits postérieurs n'ajoutent que des lignes). Test faible :
AARG62 (ne vérifie pas la réponse en cas d'échec). Aucun test rejoué en local (CI d'abord).

## 3. Sondes

| Sonde | Tâche | Verdict |
|---|---|---|
| `docs/audits/sondes/AARG/C-AARG-VER5-001.py` | AARG2 | REPRO : facture soldée par paiement + RAS, annulée puis restaurée ⇒ « émise », dû 200, relançable |
| `docs/audits/sondes/AARG/C-AARG-VER5-002.py` | critique | REPRO : facture annulée, vente refacturée, puis avoir miroir annulé ⇒ deux factures vivantes, 2 400 dus pour 1 200 |
| `docs/audits/sondes/AARG/C-AARG-VER5-003.py` | critique | REPRO : Admin RH lit lignes de facture, prévision de trésorerie, tableau de bord et encours client |
| `docs/audits/sondes/AARG/C-AARG-VER5-010.py` | AARG62 | REPRO : relance manuelle en échec ⇒ 200 muet, niveau consommé |
| `docs/audits/sondes/AARG/C-AARG-VER5-011.py` | AARG12 | REPRO : Admin RH lit relances, balance âgée et relevé client |
| `docs/audits/sondes/AARG/C-AARG-VER5-020.py` | AARG18 | REPRO : BC en attente re-pointé vers une version remplacée ⇒ stock sorti deux fois |

## 4. Écarts retenus

| C-id | Tâche d'origine | Grav. | Écart | Sonde | Tâches |
|---|---|---|---|---|---|
| C-AARG-VER5-002 | critique | S1 | restaurer une facture annulée (annulation de son avoir miroir) ne vérifie pas que la vente a été refacturée : deux créances pour une vente | REPRO | AARG63 |
| C-AARG-VER5-001 | AARG2 | S1 | la restauration ne rend pas les retenues neutralisées (ni la sortie de stock, ni la réservation) : dû faux et relancé ; prod : jamais arrivé | REPRO (+ L2, prod lue) | AARG64 |
| C-AARG-VER5-011 | AARG12 | S2 | relances, balance âgée, relevé client et ses PDF lisibles par tout rôle | REPRO | AARG65 |
| C-AARG-VER5-003 | critique | S2 | lignes de facture, prévision de trésorerie, tableau de bord et encours client lisibles par tout rôle | REPRO | AARG66, AARG67 |
| C-AARG-VER5-020 | AARG18 | S2 | la mise à jour d'un BC le re-pointe vers une version remplacée | REPRO | AARG68 |
| C-AARG-VER5-010 | AARG62 | S3 | une relance manuelle en échec consomme un niveau de la cadence sans le dire | REPRO | AARG69 |
| C-AARG-VER5-012 | AARG61 | S3 | retard et échéance affichés sur une ancienne facture sans échéance ignorent le délai du client | lecture | AARG70 |

Seconde lentille sur le S1 des retenues : maintenu, exposition faible (aucune retenue ni restauration en prod au 05/11),
élargi à la sortie de stock et à la réservation. Critique Fable (1) : inventaire des effets de l'annulation que la restauration
ne rejoue pas, lectures d'argent ouvertes, gardes de création absentes des mises à jour.

## 5. Optionnel (non déposé)

- Les liens de paiement fermés par l'annulation ne sont jamais rouverts ; les escomptes mis à zéro ne sont pas rétablis.
- Relevé client : les avances sont filtrées par créateur (un Commercial « soi » voit un solde égal au dû).
- La mise à jour d'un BC ne distingue pas les BC annulés dans son contrôle « BC existant » (refus à tort possible).
- Une facture brouillon re-pointée vers une version remplacée n'a pas été vérifiée.

## 6. Couverture et sortie de cycle

- **Couvert.** 25 tâches sur 60 cochées ; 6 sondes jouées (et 1 rejouée) ; prod lue pour le S1.
- **Non couvert.** Les 35 autres tâches cochées ; aucun rejeu navigateur ; variantes « transférer » et « rembourser » de
  l'annulation non jouées.
- **Statut.** 2 écarts S1 et 3 S2 ⇒ AARG reste dans le cycle : prochaine clôture due quand AARG63-70 seront cochées.

## 7. Coût

- 3 vérificateurs + 1 seconde lentille + 1 lot de sondes de critique (opus, effort élevé) ≈ 1,2 M de jetons ; 1 critique Fable
  ≈ 0,2 M ; 1 rédacteur.

<!-- verifie | groupe: AARG | pct: 97 | ecarts_s1_s2: 5 -->

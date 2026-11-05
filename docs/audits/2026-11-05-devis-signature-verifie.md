# Vérifie ADVS — contre-visite de clôture du parcours PA3 devis → signature, 05/11/2026

Commande `loop audit` (reprise du 04-05/11). La contre-visite de mi-parcours du 04/11 (77 %) avait déposé ADVS45-46 ; le groupe
compte 45 tâches cochées sur 47 (ADVS41, ADVS47 ouvertes, 96 %) : la clôture est due. La contre-visite n'a rien construit, n'a
lancé aucun deploy, n'a rien écrit en prod. Pile locale partagée (code du conteneur en retard sur `main`, sans effet sur les
fichiers sondés) ; chaque sonde tourne en transaction annulée.

## 0. Préconditions

- **SHA.** `origin/main` = `2781a2049`. Branche de claim : `verifie-advs-0511`.
- **Registre.** PA3 `devis-signature`, groupe ADVS, 47 tâches, 45 `[x]`.
- **Échantillon (graine = SHA `2781a2049`).** Les 9 P0/S1 cochées + ADVS45 (46 tirée) + 9 tirées = **19 tâches**, 2 lots.
- **Déjà déposé, non redéposé.** ACVI102 (garde d'opposition au même point d'envoi), ATOT56-62, AGNR63-66, ASEC67-68.

## 1. Vérificateurs (2 lots, opus, effort élevé, frais, même répertoire)

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **18** | ADVS1, 2, 3, 4, 5, 6, 8, 10, 12, 16, 17, 19, 22, 25, 34, 35, 45, 46 |
| partiel | **1** | ADVS26 (tient pour son Then ; l'envoi saute la même garde) |
| non-fait / faux / régression | **0** | — |

Écarts du 04/11 : ADVS45 fermé (sonde VER1-101 rejouée : 0 clé changée à la page publique), ADVS46 fermé (miroir écran rejoué
sous node : 13 cas, 0 écart). ADVS22 cochée « déjà présente » : le code vient bien de commits sur `main`.

## 2. Tests nommés

Tous présents dans un module existant. Aucun test rejoué en local (CI d'abord).

## 3. Sondes

| Sonde | Tâche | Verdict |
|---|---|---|
| `docs/audits/sondes/ADVS/C-ADVS-VER5-001.py` | ADVS26 | REPRO : lead passé à 46 kWh pour 10 000 MAD, l'enregistrement refuse mais le lien de partage envoie |
| `docs/audits/sondes/ADVS/C-ADVS-VER5-002.py` | ADVS3 | conforme : 3 × 833,33 HT ⇒ 3 000,00 TTC |
| `docs/audits/sondes/ADVS/C-ADVS-022.py` (rejouée) | ADVS16 | REPRO pour l'écart : envoi « les deux » ⇒ sœur restée brouillon, aucun comparatif à la page client |

## 4. Écarts retenus

| C-id | Tâche d'origine | Grav. | Écart | Sonde | Tâches |
|---|---|---|---|---|---|
| C-ADVS-VER5-001 | ADVS26 | S2 | l'envoi d'un brouillon ne relit pas la garde « kWh déclaré contredit par les factures » (règle fondateur du 30/09) | REPRO | ADVS48 (après ACVI102, même point d'envoi) |
| C-ADVS-VER5-010 | ADVS16 | S3 | un envoi « les deux gammes » laisse la sœur en brouillon ; D-ADVS-VER5-1 = envoyer les deux | REPRO (rejeu) | ADVS49 |

Aucun S1 : ni seconde lentille ni critique Fable (METHODE §C.4).

## 5. Optionnel (non déposé)

- `replace-lines` répond 400 sur un kWh contredit là où la création et le calepinage répondent 409.
- ADVS46 : l'écran lit le rôle quel que soit le niveau de règles (le serveur à partir du niveau 10) ; cas rare (S4).

## 6. Couverture et sortie de cycle

- **Couvert.** 19 tâches sur 45 cochées ; 2 sondes jouées et 3 rejouées dans la pile locale.
- **Non couvert.** Les 26 autres tâches cochées ; aucun rejeu navigateur.
- **Statut.** 1 écart S2 ⇒ ADVS reste dans le cycle : prochaine clôture due quand ADVS48-49 seront cochées.

## 7. Coût

- 2 vérificateurs (opus, effort élevé) ≈ 0,45 M de jetons ; 1 rédacteur ; aucun appel Fable (aucun S1).

<!-- verifie | groupe: ADVS | pct: 96 | ecarts_s1_s2: 1 -->

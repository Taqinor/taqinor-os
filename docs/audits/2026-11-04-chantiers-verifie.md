# Vérifie ACHT — 4ᵉ contre-visite de clôture du groupe chantiers (J2), 04/11/2026

Commande `loop audit` (reprise du 04/11). Les écarts du 01/11 (ACHT124-129) sont cochés : 114 tâches sur 114, la clôture est
de nouveau due. La contre-visite n'a rien construit, n'a lancé aucun deploy, n'a rien écrit en prod. Pile locale partagée
avec d'autres sessions ; chaque sonde tourne en transaction annulée.

## 0. Préconditions

- **SHA.** `origin/main` = `fcbed3760`. Branche de claim : `verifie-acht-0411`.
- **Registre.** J2 `chantiers`, groupe ACHT, 114 tâches, 114 `[x]`.
- **Échantillon (graine = SHA `fcbed3760`).** Les 10 P0/S1 cochées + ACHT124-128 (écarts du 01/11 ; ACHT129 déjà P0/S1)
  + 26 tirées = **41 tâches**, 5 lots.
- **Déjà déposé, non redéposé.** Audits de parcours PA1/PA3/PA4 (ACVI, ADVS, AARG) ; contre-visites ASTK, ADOC, AMOT du
  même jour.

## 1. Vérificateurs (5 lots, opus, effort élevé, frais, même répertoire)

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **32** | ACHT1, 2, 3, 9, 10, 17, 25, 26, 28, 29, 31, 35, 42, 44, 45, 49, 52, 54, 57, 64, 69, 74, 75, 76, 108, 110, 122, 125-129 |
| déjà-présent (conforme) | **1** | ACHT68 (construit par APDF38) |
| partiel | **8** | ACHT32, 38, 50, 72, 107, 124 (jumeau ou clause manquante), ACHT53 (test statique), ACHT99 (oracles 5/7/10 « NA ») |
| non-fait / faux / régression | **0** | — |

Écarts du 01/11 : ACHT125-129 fermés (sonde VER-201 rejouée : fin de garantie indépendante de l'ordre) ; ACHT124 tient pour
une saisie, pas pour la deuxième saisie hors ligne de la même ligne. ACHT53 et ACHT99 : faiblesses déjà relevées le 30/10 et
le 01/11, sans défaut de code (sonde VER4-001 : 34 couples, 0 fuite multi-société).

## 2. Tests nommés

Tous présents dans un module existant (ACHT68 : couvert par `tests_apdf_photos_page_publique.py`). Aucun test rejoué en local
(CI d'abord).

## 3. Sondes

| Sonde | Tâche | Verdict |
|---|---|---|
| `docs/audits/sondes/ACHT/C-ACHT-VER4-001.py` | ACHT52-53 | conforme (34 couples sans fuite ; témoin `kit` OneToOne refusé par unicité) |
| `docs/audits/sondes/ACHT/C-ACHT-VER4-010.py` | ACHT124 | REPRO : deuxième saisie hors ligne de la même ligne ⇒ faux conflit |
| `docs/audits/sondes/ACHT/C-ACHT-VER4-020.py` | ACHT32 | REPRO : horloge −1 an ⇒ 8 760 h de main-d'œuvre ; retour avant arrivée ⇒ génération de facture cassée |
| `docs/audits/sondes/ACHT/C-ACHT-VER4-030.py` | ACHT38 | REPRO : glisser-déposer de l'Agenda ⇒ RDV resté confirmé, aucun report tracé |
| `docs/audits/sondes/ACHT/C-ACHT-VER4-031.py` | ACHT50 | REPRO : l'Agenda montre au technicien un chantier hors de sa portée |
| `docs/audits/sondes/ACHT/C-ACHT-VER4-032.py` | lecture de la sonde 031 | REPRO : technicien et commercial déplacent par l'Agenda une intervention et une pose qu'ils ne peuvent pas ouvrir (404 en lecture, 200 en écriture) |
| `docs/audits/sondes/ACHT/C-ACHT-VER4-040.py` | ACHT107 | REPRO : sortie de géorepérage restée ouverte après un lot de rattrapage |
| `docs/audits/sondes/ACHT/C-ACHT-VER4-041.py` | ACHT72 | REPRO : outil coché resté « en intervention » après changement de kit |

## 4. Écarts retenus

| C-id | Tâche d'origine | Grav. | Écart | Sonde | Tâches |
|---|---|---|---|---|---|
| C-ACHT-VER4-020 | ACHT32 | S2 | l'heure saisie hors ligne n'a ni borne basse ni ordre : main-d'œuvre absurde sur la facture brouillon, ou durée négative qui casse la génération | REPRO | ACHT130 (synchro), ACHT131 (durée) |
| C-ACHT-VER4-032 | ACHT50 | S2 | l'Agenda écrit hors portée : un technicien ou un commercial déplace la date d'une intervention ou d'une pose qu'il ne voit pas | REPRO | ACHT137 |
| C-ACHT-VER4-010 | ACHT124 | S3 | deuxième saisie hors ligne d'une même ligne rejouée en faux conflit | REPRO | ACHT132 |
| C-ACHT-VER4-040 | ACHT107 | S3 | après un lot de rattrapage, la sortie suivante n'est ni journalisée ni notifiée | REPRO | ACHT133 |
| C-ACHT-VER4-041 | ACHT72 | S3 | outil sorti jamais rendu quand le kit change | REPRO | ACHT134 |
| C-ACHT-VER4-030 | ACHT38 | S3 | le déplacement depuis l'Agenda saute la replanification (RDV non déconfirmé, report non compté) | REPRO | ACHT135 |
| C-ACHT-VER4-031 | ACHT50 | S3 | l'Agenda ignore la portée des listes ; D-ACHT-VER4-1 = même portée que les listes | REPRO | ACHT136 |

Aucun S1 : ni seconde lentille ni critique Fable (METHODE §C.4). La facture n'a pas besoin de garde propre : une durée
`None` saute déjà la ligne de main-d'œuvre.

## 5. Optionnel (non déposé)

- ACHT2 : `mise-en-service` sur un chantier annulé déjà réceptionné passe la garde (déjà noté le 01/11, sans effet d'argent).
- ACHT9 : deux « Commander » simultanés sans verrou ; ACHT72 : `cocher_outil_ligne` sans `select_for_update` (non sondables).
- ACHT126 : `signature_validation.py` cite encore `motif_override_signature` à l'écran de signature (S4).
- ACHT31 : note « forme_serveur_provisoire » périmée dans `field_sync_ops.json` ; `_client_ts` dans le corps d'une op sans
  `client_ts` ⇒ 500 (corps forgé seulement).

## 6. Couverture et sortie de cycle

- **Couvert.** 41 tâches sur 114 cochées ; 8 sondes jouées (et VER-201 rejouée) dans la pile locale.
- **Non couvert.** Les 73 autres tâches cochées ; aucun rejeu navigateur ; effet à l'écran du glisser-déposer non vu.
- **Statut.** 2 écarts S2 ⇒ ACHT reste dans le cycle : prochaine clôture due quand ACHT130-137 seront cochées.

## 7. Coût

- 5 vérificateurs (opus, effort élevé) ≈ 1,1 M de jetons ; 1 rédacteur ; aucun appel Fable (aucun S1).

<!-- verifie | groupe: ACHT | pct: 100 | ecarts_s1_s2: 2 -->

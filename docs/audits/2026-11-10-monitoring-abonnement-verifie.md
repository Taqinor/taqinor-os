# Vérifie AMON — contre-visite de clôture du parcours PA7 « monitoring et abonnement », 10/11/2026

Commande `loop audit` (10/11). L'audit de parcours PA7 (08/11, PR #1298) avait déposé AMON1-96 ; le groupe compte 50 tâches
cochées sur 50 (100 %) : la clôture est due. La contre-visite n'a rien construit, n'a lancé aucun deploy, n'a rien écrit en
prod.

## 0. Préconditions

- **SHA.** `origin/main` = `a54515178` (relectures) ; branche de claim `verifie-amon-1011`, ouverte sur `7839dcdb2` (même code).
- **Registre.** PA7 `monitoring-abonnement`, groupe AMON, 50 tâches, 50 `[x]` (construites dans la PR #1303).
- **Échantillon (graine = SHA `a54515178`).** Les 5 P0 / P1 / S1 cochées + 12 tirées (25 % des 45 autres) = **17 tâches**, 2 lots.
- **Pile locale.** Le conteneur partagé monte le checkout principal, en retard de 5 994 commits sur `main` : AUCUNE sonde n'est
  rejouée ni écrite. Chaque verdict repose sur le commit, le code sur `origin/main` et le test nommé ; les chiffres des écarts
  sont des recalculs en Python pur de la logique lue (poids mensuels réels de `quote_engine/constants.py`), obtenus séparément
  par la seconde lentille et par la critique. Prod non relue (dernière lecture le 07/11 : 0 relevé, 0 abonnement, 0 garantie).

## 1. Vérificateurs (2 lots, opus, effort élevé, frais, même répertoire)

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **14** | AMON1, 3, 20, 22, 26, 35, 42, 43, 44, 47, 84, 90, 91, 92 |
| partiel | **3** | AMON21, 29, 40 |
| non-fait / faux / régression | **0** | — |

AMON43 tient son Then ; son jumeau du rapport client (renvoyé à AMON21, qui ne l'a pas repris) est l'écart 043 ci-dessous.

## 2. Tests nommés

Tous présents dans un module existant et comportementaux ; aucun test affaibli. Les cas absents sont exactement ceux des
écarts : AMON21 n'a que des relevés allant jusqu'à aujourd'hui (jamais « dernier relevé avant aujourd'hui », `period_kwh` jamais
relu) ; AMON40 ne teste « aucun relevé » que sur le statut, pas sur le rapport ; aucun test ne relit `availability_pct` quand une
immobilisation existe. AMON44 : le mutant « base = max » survit probablement. Aucun test rejoué en local (CI d'abord).

## 3. Sondes (dossier PA7, lues, non rejouées)

| Sonde | Tâche | Verdict |
|---|---|---|
| 001-L2, 003, 020 (+ L2), 021 (+ L2), 022 (+ L2), 040, 043 | AMON1, 3, 20, 21, 22, 40, 43 | lecture : passeraient à repro False |
| 001 (première version) | AMON1 | lecture : plante à l'import (fonction supprimée par AMON22) |
| 026 | AMON26 | lecture : repro False grâce à AMON22 ; n'exerce plus la rechute (seul le test prouve AMON26) |
| 042 | AMON42 | lecture : repro False pour une autre raison (société sans facteur CO₂ ⇒ 409 partout) : sans valeur de preuve |
| 045 | AMON47, AMON92 | lecture : plante (abonnement créé sur un chantier hors parc, refusé depuis AMON11) |

## 4. Écarts retenus

| C-id | Tâche d'origine | Grav. | Écart | Sonde | Tâches |
|---|---|---|---|---|---|
| C-AMON-VER1-021 | AMON21, AMON22 | S1 | rapport O&M client non borné à la couverture des relevés : PR 60,66 % au lieu de ≈ 100 le 15/11 pour un système sain relevé jusqu'en octobre, « Production période 0 kWh », « Dégradation −33,78 %/an » (−92,80 pour un système à jour saisi par relevés de 30 j), salissure et nettoyage recommandés à tort | STATIQUE (lecture + recalcul, 2 lectures indépendantes) | AMON97, 98, 99 |
| C-AMON-VER1-021 | AMON21, AMON22, AMON29 | S3 | mêmes fenêtres sur les écrans internes : historique mensuel à plat, PR du parc ≈ 93 %, indice de suivi 90,28 % « sous garantie », pertes catégorisées sur 365 j fixes | STATIQUE (lecture) | AMON100, 101, 102, 103 |
| C-AMON-VER1-043 | AMON43, AMON21 | S1 | le rapport client imprime « Disponibilité 100,00 % » (jours avec relevé) à côté d'un onduleur immobilisé (51,61 % côté SAV) ; l'interne nomme cette grandeur « indice de suivi » | STATIQUE (lecture + recalcul) | AMON108 |
| C-AMON-VER1-040 | AMON40 | S1 si la garantie de production est autorisée (éteinte par défaut, route sans écran), S2 sinon | rapport de garantie : « Pénalité cumulée 10 787,84 MAD » sans aucun relevé ; garanti courant jusqu'à aujourd'hui quand les relevés s'arrêtent (3 857,73 MAD), statut compris | STATIQUE (lecture + recalcul) | AMON104, 105 |
| C-AMON-VER1-040 | AMON40, AMON22 | S3 | relevé à cheval compté en entier dans l'année ou le mois de sa date de début | STATIQUE (lecture) | AMON106 |
| C-AMON-VER1-040 | AMON29, AMON40 | décision | garanti proraté à plat contre attendu au profil mensuel : pénalité d'hiver sur un système sain | STATIQUE (lecture + recalcul) | AMON107 (GATED D-AMON-3) |
| C-AMON-VER1-041 | AMON41 | S3 | pastille d'impact : « 0,0 t CO₂ évitées » inventé quand aucun facteur n'est réglé | STATIQUE (lecture) | AMON109 |

Seconde lentille (opus, fraîche) sur les trois S1 candidats : 3 maintenus, 2 élargis, 0 réfuté ; le troisième requalifié de
« deux calculs » en « libellé faux ». Critique de complétude (Fable, 1 appel) : 7 trous, tous repris ci-dessus (2 S1, 5 S3) ; 4
tâches non échantillonnées relues et tenues (AMON31, 41, 89, 94). Cause commune des S1 : des renvois croisés entre tâches
(« hors périmètre : AMON<n> ») que la tâche visée n'a pas repris.

## 5. Optionnel (non déposé)

- AMON20 : la vue des fenêtres de maintenance (`core/maintenance_windows.py`) garde le contournement « admin voit toutes les
  sociétés » ; à trier par la prochaine passe sécurité.
- AMON21 : le dénominateur de disponibilité inclut aujourd'hui (un système neuf relevé jusqu'à hier passe sous 98 %).
- AMON35 : mois du titre de notification en anglais (« August 2026 ») ; AMON3 : PATCH d'une note sur un ancien relevé qui
  déborde aujourd'hui refusé en 409.
- AMON42 : deux premières émissions concurrentes de certificats non sérialisées ; AMON47 : un seul document GED par système,
  seule l'adresse principale du client acceptée.
- Certificat carbone : facteur courant imprimé à côté de tonnes figées si le PDF GED manque ; PDF d'un certificat annulé sans
  mention « annulé ».
- AMON108 porte un `@after` vers AMON101 et AMON102 imposé par le planificateur (règle front / back d'une même vague), sans
  dépendance de code.

## 6. Couverture et sortie de cycle

- **Couvert.** 17 tâches échantillonnées + 4 relues par la critique, sur 50 cochées ; lecture du code, des commits et des tests.
- **Non couvert.** 29 tâches cochées ; aucune sonde rejouée ni écrite pour les S1 (pile locale en retard) : le test rouge
  d'abord de chaque tâche est la première preuve exécutée ; aucun rejeu navigateur ; rendu PDF non vu.
- **Statut.** 3 écarts S1 ⇒ AMON reste « construit » ; nouvelle contre-visite après la coche d'AMON97 à 106, 108 et 109.
- **Outil.** `scripts/audit_tache.py` plante sur une ancre JSX ; `audit_registre.py --du` met plusieurs minutes (garde
  d'acceptation lancée groupe par groupe).

## 7. Coût

- 2 vérificateurs + 1 seconde lentille + 1 rédacteur (opus, effort élevé) ≈ 0,98 M de jetons ; 1 critique Fable ≈ 0,26 M :
  elle a trouvé les 2 S1 que l'échantillon ne voyait pas (dégradation et salissure du rapport client, prorata du garanti).

<!-- verifie | groupe: AMON | pct: 100 | ecarts_s1_s2: 3 -->

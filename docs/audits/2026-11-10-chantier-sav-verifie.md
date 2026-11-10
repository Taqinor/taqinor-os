# Vérifie ACSV — contre-visite de clôture du parcours PA5 « chantier → SAV », 10/11/2026

Commande `loop audit` (10/11). L'audit de parcours PA5 (07/11, PR #1297) avait déposé ACSV1-106 ; le groupe compte 72 tâches
cochées sur 72 (100 %) : la clôture est due, et c'est le groupe dû le plus construit. La contre-visite n'a rien construit, n'a
lancé aucun deploy, n'a rien écrit en prod.

## 0. Préconditions

- **SHA.** `origin/main` = `a54515178`. Branche de claim : `verifie-acsv-1011`.
- **Registre.** PA5 `chantier-sav`, groupe ACSV, 72 tâches, 72 `[x]` (construites dans la PR #1303).
- **Échantillon (graine = SHA `a54515178`).** Les 8 P0 / S1 cochées + 16 tirées (25 % des 64 autres) = **24 tâches**, 3 lots de 8.
- **Pile locale.** Le conteneur partagé monte le checkout principal, en retard de 5 994 commits sur `main` : les sondes ne sont
  PAS rejouées ; chaque verdict repose sur le commit, le code sur `origin/main`, le test nommé et la CI verte du merge (#1303),
  recoupés avec les enregistrements d'acceptation `docs/audits/acceptation/ACSV/2026-11-08-*.md`.

## 1. Vérificateurs (3 lots, opus, effort élevé, frais, même répertoire)

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **19** | ACSV4, 14, 21, 23, 24, 30, 31, 34, 39, 51, 53, 55, 56, 59, 70, 71, 91, 100, 101 |
| partiel | **5** | ACSV50, 52, 54, 57, 67 |
| non-fait / faux / régression | **0** | — |

ACSV56 avait été rendue « partielle » par son vérificateur (refus 409 porté par la clé `statut`, sans `detail`) ; la relecture
du rédacteur l'a réfutée : `core/conflit_etat.py::ConflitEtat` ajoute lui-même `detail`, que l'écran « Équipements » lit en
premier. Elle est comptée ok.

## 2. Tests nommés

Tous présents dans un module existant et comportementaux (état relu en base ou réponse HTTP) ; aucun test affaibli par les
commits. Deux tests ne portent pas tout leur Then : ACSV52 (poses séquentielles : le mutant « relire hors verrou » passe vert)
et ACSV21 (la boucle sur le parc tourne sur un parc vide ; le code, lui, tient le Then). ACSV50 ne crée aucune intervention de
pose terminée, ce qui cachait l'écart ci-dessous. Aucun test rejoué en local (CI d'abord).

## 3. Sondes

| Sonde | Tâche | Verdict |
|---|---|---|
| `docs/audits/sondes/ACSV/C-ACSV-005.py`, `-041.py`, `-040.py` (+ -L2), `-061.py`, `-063.py`, `-064.py`, `-065.py`, `-066.py`, `-067.py`, `-069.py` | ACSV4, 31, 30, 51, 53, 54, 55, 56, 57, 59 | lecture : passeraient à repro False |
| `docs/audits/sondes/ACSV/C-ACSV-060.py` | ACSV50 | lecture : repro False, mais elle ne termine pas l'intervention de pose (ne voit pas l'écart) |
| `docs/audits/sondes/ACSV/C-ACSV-062.py` (+ -L2) | ACSV52 | lecture : resteraient faussement REPRO (crochet sur une seule connexion, qu'aucun verrou ne bloque) |
| `docs/audits/sondes/ACSV/C-ACSV-083.py` | ACSV67 | lecture : repro False sur les trois routes nommées ; ne voit pas l'action de masse |
| `docs/audits/sondes/ACSV/C-ACSV-020.py`, `-080.py` | ACSV91, 100 | lecture : repro False, mais elles sondent ACSV15 et ACSV64, pas ces tâches |

## 4. Écarts retenus

| C-id | Tâche d'origine | Grav. | Écart | Sonde | Tâches |
|---|---|---|---|---|---|
| C-ACSV-VER1-064 | ACSV54 | S2 | la couverture et la date d'ouverture ne sont réservées au responsable qu'au PATCH : à la création, un Technicien fixe « garantie » (ou une date ancienne) et « Facturer » rend des lignes à 0 DH ; aucun écran n'envoie ces champs (API seule) | STATIQUE (lecture) | ACSV107 |
| C-ACSV-VER1-083 | ACSV67 | S3 | l'annulation en masse et le PATCH `annule` contournent la garde « prêt d'équipement en cours » (et la suite des interventions d'ACSV65) | STATIQUE (lecture) | ACSV108 |
| C-ACSV-VER1-060 | ACSV50, ACSV51 | S3 | ticket né d'une réserve après une pose terminée : « Facturer » rend 403 récidive au lieu du 409 « garantie à confirmer » ; l'argent reste protégé (409 après override) | STATIQUE (lecture) | ACSV109 |
| C-ACSV-VER1-062 | ACSV52 | S3 | le test de pose concurrente est séquentiel : retirer le verrou laisse la CI verte (code correct, preuve absente) | STATIQUE (lecture) | ACSV110 |
| C-ACSV-VER1-067 | ACSV57 | S4 | le refus de fusion cite l'identifiant interne de la facture, pas sa référence | STATIQUE (lecture) | — (cosmétique) |

Aucun S1 : ni seconde lentille ni critique Fable (METHODE §C.4). Les quatre tâches sont chez le propriétaire `sav`
(`docs/plans/PLAN_AUDIT_SAV.md`, section « ACSV — ÉCARTS vérifie 2026-11-10 »).

## 5. Optionnel (non déposé)

- ACSV53 : « Créer un devis » de réparation et le contrôle « à facturer » de la clôture (ACSV60) ne lisent que les pièces du
  ticket, pas les consommations de fiche d'intervention ; une ligne de fiche à quantité 0 peut sortir « ×0 » sur la facture.
- ACSV57 × ACSV54 : un brouillon de facture supprimé ne vide pas le pointeur du ticket, qui reste alors non fusionnable.
- ACSV50 : `marquer_recidive` compte l'intervention de pose comme « réparation d'origine » d'un ticket de réserve (question de
  règle, hors du correctif ACSV109).
- ACSV31 : la clé interne `date_reception_defaite` vit dans `custom_data`, écrivable par PATCH d'API (aucun écran ne l'écrit).
- ACSV21 : date de mise en service future ou mal formée non bornée ; ACSV14 : drapeau `annulation_deplacement` non lié au
  déplacement d'origine ; ACSV91 : la relecture du panneau remet les brouillons à zéro pendant un enregistrement.
- ACSV30 : budget « lignes nettes » dépassé (≈ 70 pour 25) ; ACSV59 : le texte disait 400, le code garde le 409 (texte faux).
- Preuves en direct non couvertes par un enregistrement : ACSV21, 23, 24, 70, 100, 101 (tâches « API seulement »).

## 6. Couverture et sortie de cycle

- **Couvert.** 24 tâches sur 72 cochées ; lecture du code, des commits et des tests sur `origin/main`.
- **Non couvert.** Les 48 autres tâches cochées ; aucune sonde rejouée (pile locale en retard) ; aucun rejeu navigateur ; l'état
  de la CI du merge #1303 n'a pas été relu par les vérificateurs.
- **Statut.** 1 écart S2 (ACSV107) ⇒ ACSV reste « construit » ; il passe « vérifié » à la contre-visite qui suivra la coche
  d'ACSV107 à ACSV110.
- **Outil.** `scripts/audit_tache.py` : `listes-figees` plante sur une ancre `fichier::symbole` et `appelants` compte 0 écran
  pour une action de masse appelée par `TicketsPage.jsx` ; clauses comblées par grep, résultats écrits dans les tâches.

## 7. Coût

- 3 vérificateurs + 1 rédacteur (opus, effort élevé) ≈ 0,92 M de jetons ; aucun appel Fable (aucun S1).

## 8. Contre-visite des correctifs, le même jour (base `c1a99568a`)

Les tâches d'écart déposées ci-dessus ont été construites dans la journée (PR #1316). Un vérificateur frais (opus, effort
élevé) a relu les trois qui sont cochées (METHODE §C.4 point 6) : **ACSV107, ACSV109, ACSV110 : ok**.

- **Écart S2 fermé.** À la création d'un ticket, la couverture et la date d'ouverture ne se choisissent plus depuis la requête
  (ACSV107) : refus pour le rôle sans droit, date du jour imposée, valeur relue en base ; aucun autre code n'écrit la
  couverture.
- ACSV109 : le refus de facturer un ticket sous garantie de chantier passe avant le cas de la récidive (simple déplacement,
  un seul service pour les trois appelants). ACSV110 : deux poses de pièce simultanées ne sortent plus le stock deux fois
  (test à deux connexions réelles).
- **Non cochée, non vérifiée.** ACSV108 (S3) : code livré, bloquée sur sa preuve en direct.
- **Tests.** Présents et comportementaux, verts dans la CI de la PR #1316, non retouchés depuis. Les trois tâches demandaient
  la sortie rouge de leur mutant : aucun mutant n'a été exécuté (dit dans les commits) ; seule la version saine est prouvée.
- **Optionnel.** Sur un ticket sans équipement daté, un technicien peut cocher « sous garantie » à la main : le ticket est
  alors couvert et « Facturer » produit une facture à zéro. L'écran est conçu pour cette saisie et aucune décision du
  fondateur n'a été trouvée sur ce point : règle à confirmer, non comptée comme écart.
- **Statut.** Plus aucun écart S1-S2 ouvert ⇒ ACSV passe « vérifié » pour sa part construite.

<!-- verifie | groupe: ACSV | pct: 100 | ecarts_s1_s2: 0 -->

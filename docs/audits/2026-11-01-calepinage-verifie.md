# Vérifie ACAL — seconde contre-visite de clôture du groupe calepinage (D3), 01/11/2026

Commande `vérifie ACAL` (METHODE §C.4.2, skill audit §5), lancée par la session d'orchestration de `loop audit`. La
contre-visite précédente, du 10/10 (`docs/audits/2026-10-10-calepinage-verifie.md`), avait déposé 13 écarts (ACAL353 à
ACAL365, dont 6 S1-S2). Toutes ces tâches sont maintenant cochées, ou `[BLOCKED]` sur leur seule acceptation en direct avec
le code construit (ACAL355, 356, 357, 364). La seconde contre-visite de clôture est donc due.
`audit_registre.py --du` ne la liste pas : sa règle ignore les contre-visites dues après le drainage des écarts.

Pour chaque tâche tirée, on rapproche le texte, le ou les commits, le test nommé et le code de `main`, avec les 7 critères de
`docs/claude-memory/lecons-construction-qjr5.md`. Chaque écart S1-S2 est prouvé par une sonde jouée en transaction annulée,
ou par un rejeu vitest de l'atelier pour le code purement front. Les écarts confirmés deviennent des tâches v3 dans le plan
du propriétaire des fichiers.

La contre-visite n'a rien construit, n'a lancé aucun deploy et n'a rien lu ni écrit en production.

## 0. Préconditions

- **SHA.** Échantillon tiré sur `origin/main` = `56d5b623a` (PR #1197). Branche `verifie-acal-cloture-2`, rebasée pour la PR
  sur `origin/main` du moment.
- **Registre.** D3 `calepinage`, groupe ACAL, dossier `docs/audits/2026-10-04-calepinage.md`.
- **Inventaire.** 365 tâches ACAL dans les plans. 359 sont cochées, et 3 de plus sont construites mais `[BLOCKED]` sur leur
  acceptation (ACAL355-357), soit 362 tâches construites.
- **Échantillon (graine = SHA `56d5b623a`) : 48 tâches**, le plafond.
  - **Les 13 tâches ÉCART du 10/10**, toutes : ACAL353 à 365. ACAL364 a été ajoutée à la main, car son étiquette `[BLOCKED]`
    ne porte pas le mot « construit ».
  - **Les tâches P0/S1 cochées.** Il y en a 68, au-delà du plafond. Les 20 jamais tirées le 10/10 passent d'abord ; les
    15 autres places vont à des tâches déjà tirées le 10/10, re-vérifiées sur le code actuel.
  - **25 % du reste : 0 tâche**, le plafond étant atteint. ACAL264 a cédé sa place à ACAL364, puisque son écart du 10/10
    (ACAL358) est dans l'échantillon.
  - **Liste :** ACAL1, 4, 8, 23-26, 31, 32, 35, 36, 38-43, 45, 47, 50, 61, 63, 90, 95, 106, 117, 146, 148, 252, 259, 313,
    316, 319, 343, 346, 353-365.
- **Pile des sondes.** Pile locale partagée `erp-agentique-*`, conteneur `erp-agentique-django_core-1`, qui monte le
  checkout principal (au même SHA). La machine était saturée (16 Go, jusqu'à 0,8 Go libres ; moteur Docker en échec 500,
  puis redémarré par la session d'orchestration). Après le redémarrage, toutes les sondes sont passées une par une par le
  verrou partagé `.claude/sonde-slot.sh`.
  - Les échecs Docker n'ont jamais compté comme verdict : base « en cours de démarrage », code 137, erreur du verrou. Ces
    sondes ont été rejouées.
  - Chaque sonde a fini en transaction annulée : base inchangée, 0 mail, 0 tâche Celery.

## 1. Vérificateurs (8 agents frais, opus, effort élevé, lecture seule, même répertoire, 6 tâches chacun)

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **35** | ACAL1, 8, 23, 24, 25, 26, 31, 35, 36, 38, 39, 40, 43, 45, 47, 50, 61, 95, 106, 117, 252, 259, 313, 316, 319, 353, 354, 355, 357, 358, 360, 361, 362, 363, 365 |
| partiel | **12** | ACAL32 (S3), 41 (S4), 42 (S3), 63 (**S1**), 90 (S4), 146 (S2), 148 (S2), 343 (S3), 346 (S3), 356 (S3), 359 (S4), 364 (S3) |
| régression | **1** | ACAL4 (S3) |
| non-fait / faux / déjà-présent | 0 | — |

- **Les écarts du 10/10 sont fermés.** Les sondes C-ACAL-VER-001, 002, 003 et 005 ne reproduisent plus (§2). ACAL353 et 354
  répondent 409 sans rien écrire. ACAL358 alerte sur le pan B (sonde C-ACAL-VER2-21 non reproduite par le chemin réel).
  ACAL362 : les deux mutants ont été exécutés sur l'hôte, et tous deux échouent.
- **Textes vieillis, code juste** (pas d'écart) : ACAL38 (la clause sur `sync-layout/` a été dépassée par ACAL96), ACAL45,
  ACAL361 et ACAL32 (from-layout répond 409 depuis ENF11, plus 422).
- **Preuve en direct (L7).** ACAL41, ACAL90 et la plupart des tâches « ok » sont dans la dette gelée
  `docs/audits/acceptation/ACAL/_dette.yml`, ce qui est conforme à la règle de couverture. La moitié écran d'ACAL355-357 et
  d'ACAL364 reste bloquée par la clé de carte absente de la pile locale.
- **Tests rejoués.** Vitest de l'atelier et de l'écran, un fichier à la fois, sous jonction `node_modules` :
  - PanneauVersions 10/10, useDocumentCalepinage 12/12, prefill.roundtrip 11/11, electrique3d 41/41 ;
  - FicheCalepinage 63/63, BoutonDevis 25/25, PanneauSeries 22/22, saisie_pente 19/19 ;
  - PanneauAllees.portee 5/5, allerRetourDocument 4/4, userJourneyPro11 4/4.

  Côté hôte : SimpleTestCase ACAL358 6/6 et ACAL362 5/5 (avec un faux `weasyprint`) ; gardes
  `check_calepinage_cles_document.py`, `check_calepinage_ecrivains_layout.py`, `check_contrats_calepinage_deux_moities.py`
  et `check_api_shapes.py` vertes. Les tests Django à base n'ont pas été rejoués : la base de test partagée est réservée, et
  la CI de `main` les couvre.

## 2. Sondes et rejeux

| Sonde | Tâche | Verdict | Observé (code de `main`, transaction annulée) |
|---|---|---|---|
| `C-ACAL-VER-001.py` | ACAL353 | non reproduit | « sync 409 panneaux 12->12 ttc 68900.00->68900.00 » (refus nommé de la surface sans `moduleWc`) |
| `C-ACAL-VER-002.py` | ACAL354 | non reproduit | « sync 409 panneaux {15108: 12}->{15108: 12} ttc 49700.00->49700.00 » |
| `C-ACAL-VER-003.py` | ACAL360 | non reproduit | « GET 200 empreinte=None ; section 200 » sur calepinage vierge |
| `C-ACAL-VER-004.py` | ACAL253 | REPRO en démo | « calepinage modifié=True, conception_divergente False->True ». Même constat que le 10/10 : la prod lue alors n'avait aucun calepinage migré lié à un devis. **Sans tâche.** |
| `C-ACAL-VER-005.py` | ACAL358 | non reproduit | « pan B kWc [4.0] chaîné à Vmp/module [41.6], alerte=True » |
| `C-ACAL-VER2-61.py` | ACAL63 | **REPRO** | « création [(15124, 8), (15125, 4)] ttc 47900.00 ; sync 200 -> [(15124, 5), (15124, 8), (15125, 0)] ttc 52500.00 » |
| `C-ACAL-VER2-71.py` | ACAL148 | **REPRO** | « avant=86 apres_retrait=None purge={6285: 1} apres_purge=86 » |
| `C-ACAL-VER2-72.py` | ACAL146 | **REPRO** | « base={'source': 'pvgis', …} pvgis_dans_rapport=True meteonorm_dans_rapport=False » |
| `C-ACAL-VER2-41.py` | ACAL4, 32 | REPRO | « from-layout 409 {'hors_reseau': …} ; module 422 {'hors_reseau': …} » : ni `detail` ni `errors` |
| `C-ACAL-VER2-51.py` | ACAL42 | REPRO | « agricole: est_verrouille=False porte=passe design-context 200 modifiable=False », idem multi-villa |
| `C-ACAL-VER2-81.py` | ACAL346 | REPRO | « kwc_devis 8.8 … CAL_KWC_DEVIS_VS_CALEPINAGE: [{kwc_calepinage 11.52, ecart_ratio 0.2361}] » sur un devis cohérent |
| `C-ACAL-VER2-21.py` | ACAL358 | non reproduit | alerte « Pan « B » : module « Module 400 B » sans fiche produit — chaîné avec la fiche « Module 550 » » |

**Rejeux vitest de l'atelier** (code front, sans sonde Python possible ; fichiers de rejeu non committés : leurs tests sont
repris comme « Test rouge d'abord » des tâches).

| Rejeu | Tâche | Verdict | Sortie |
|---|---|---|---|
| Pente → section `zones` | hors texte (ACAL26, ACAL252) | **REPRO** | « hydratationDeSection(zones) = {} » ; z1 reste à 15° quand le serveur a écrit 35° ; « AssertionError: expected 15 to be 35 » |
| Rouvrir puis ajouter un horizon | ACAL356 | REPRO | carte 70310 → 57296, mais la production enregistrée reste 25433 |
| Mutants de la garde des écrivains | ACAL364 | REPRO | appel `…enregistrerLayoutCalepinage(` ajouté : 1 erreur ; appel `…Conditionnel(` ajouté : 0 erreur |

## 3. Seconde lentille (opus, effort élevé, contexte frais)

- **ACAL356 : déclassé de S1 à S3.** Le mécanisme est confirmé : un rejeu rejoué par la lentille donne la même sortie.
  Mais sur les rendus aux règles corrigées, le PDF imprime la production du moteur de devis, pas celle du document :
  `quote_engine/etude_chiffrage.py` garde `roi["prod_kwh"]` quand `_corrige`. Le chiffre non dératé n'atteint que les devis
  aux anciennes règles (déjà envoyés), la production attendue du monitoring (via `production_attendue_pour_devis`) et des
  écrans internes. Écart retenu en S3 (ACAL367).
- **ACAL63 : S1 maintenu, puisque la sonde est REPRO.** Montant faux et produit faux à la resynchronisation : 13 panneaux
  de 550 W vendus au lieu de 8 × 550 W + 5 × 450 W, soit 52 500,00 TTC au lieu du bon total. La critique Fable a jugé ce
  constat (§5).

## 4. Écarts retenus

| Tâche | Constat | Écart de | Gravité | Cause | Preuve | Plan |
|---|---|---|---|---|---|---|
| ACAL374 | C-ACAL-VER2-61 | ACAL63 | **S1** | L6-jumeau (« la plus grosse ligne libre » prise par un modèle sans fiche) | sonde REPRO | DEVIS |
| ACAL366 | C-ACAL-VER2-91 | ACAL26, ACAL252 | **S2** | clause-manquante (section `zones` inconnue de l'hydratation : la pente écrite est réécrite sans 409) | vitest REPRO | CALEPINAGE |
| ACAL375 | C-ACAL-VER2-71 | ACAL148 | **S2** | L2-persistance (le fichier météo retiré revient après la purge de la corbeille) | sonde REPRO | CALEPINAGE |
| ACAL376 | C-ACAL-VER2-72 | ACAL146 | **S2** | L4-appelant (le rapport client dit PVGIS sur un fichier fournisseur) | sonde REPRO | CALEPINAGE |
| ACAL367 | C-ACAL-VER2-22 | ACAL356 | S3 | L5-test-affaibli (rouvert + horizon : production non dératée) | vitest REPRO + lentille | CALEPINAGE |
| ACAL368 | C-ACAL-VER2-41 | ACAL4 | S3 | régression (contrat `devis_from_layout.json` encore en 422) | sonde | DEVIS |
| ACAL369 | C-ACAL-VER2-41 | ACAL32 | S3 | L4-appelant (`httpMessage` ne lit pas `hors_reseau` : message générique) | sonde | CALEPINAGE |
| ACAL370 | C-ACAL-VER2-31 | ACAL364 | S3 | L5-test-affaibli (la garde ignore le seul écrivain restant) | mutants exécutés | DEPLOY |
| ACAL371 | C-ACAL-VER2-82 | ACAL343 | S3 | clause-manquante (deux clés gelées en dette au lieu d'échouer) | garde exécutée | TRANSVERSE (@atomique) |
| ACAL372 | C-ACAL-VER2-81 | ACAL346 | S3 | L6-jumeau (kWc de l'outil à 720 W au lieu des fiches : fausse alerte nocturne) | sonde | MOTEUR |
| ACAL373 | C-ACAL-VER2-51 | ACAL42 | S3 | clause-manquante (écran en lecture seule, porte d'écriture ouverte : agricole, multi-villa) | sonde | CALEPINAGE |

**4 écarts S1-S2** (1 S1, 3 S2) et 7 S3. Les tâches sont au format v3, sous `### ACAL — ÉCARTS vérifie 2026-11-01 · format
v3` dans chaque plan. ACAL368 est le contrat d'abord, seul ; ACAL369 porte `@after: ACAL368`. ACAL371 va dans
`PLAN_AUDIT_TRANSVERSE.md` : la garde échoue sur une entrée d'allowlist morte, donc le schéma et l'allowlist changent dans le
même commit.

**Chiffres client.** ACAL374 change les lignes et le total d'un devis resynchronisé, et ACAL376 change la provenance imprimée
dans le rapport d'étude. Ces deux changements valent **seulement pour les nouveaux rendus ou les nouvelles
resynchronisations** : un devis envoyé garde ce que le client a reçu (règle du 08/10). ACAL375 ajoute un champ
(migration additive, SCHEMA).

**Aucune nouvelle tâche d'acceptation.** ACAL351 reste l'acceptation unique du groupe ; chaque tâche nomme son étape PA2.

## 5. Critique de complétude (1 appel Fable, effort élevé)

Un S1 subsistant, la critique Fable unique a été jouée, en contexte frais et lecture seule.

- **ACAL374 confirmé S1.** La boucle de `_reconcilier_panneaux_par_modele` suit l'ordre du document. Un modèle sans fiche
  prend la plus grosse ligne panneau libre, quel que soit son produit. La fiche désignée, traitée ensuite, recrée alors sa
  ligne.
  Les jumeaux sont sains :
  - la création (`composition_residentielle`) compose une ligne par modèle ;
  - `offres_tailles` et `overrides` ne touchent que les lignes batterie ;
  - `lignes.py` et `composition.py` ne font que lire.

  Le correctif retenu (fiche désignée d'abord, tri stable) ferme le cas sondé et l'ordre inverse.
- **Spot-check des « ok »** : ACAL354, 40 et 353 tiennent sur leurs clauses. Le titre d'ACAL353, « sans rien écrire », est
  inexact sur la route `sync-layout/`. `ecrire_conception_du_devis` enregistre le calepinage avant la resynchronisation du
  devis, donc le document refusé reste stocké. C'est un choix de conception délibéré (commentaire « La conception reste
  enregistrée ») ; le devis, lui, est intact. Noté S3, sans tâche.
- **Trou rattaché à ACAL373.** `sync-layout/` et `POST layout/` côté ventes passent par `enregistrer_layout` et
  `verifier_ecriture_autorisee`, donc ACAL373 les ferme. La porte qui reste ouverte est la resynchronisation du module,
  `calepinage/services/devis.py::resynchroniser_devis` : elle n'a qu'un refus de statut. Elle est ajoutée aux Files
  d'ACAL373, et `reconcilier` ne fait qu'avertir sur un devis agricole.
- **Gravités confirmées** : ACAL366, 375 et 376 en S2, ACAL367 en S3. Le « second cas » d'ACAL367 (document stocké déjà
  ombré) est le cas courant : il est soumis à décision (§6).
- **Erreurs factuelles corrigées dans les tâches** :
  - ACAL373 désignait la mauvaise porte comme jumeau ;
  - ACAL373 nommait `PLACE['calepinage']` au lieu de la liste `PAR_PROPRIETAIRE['calepinage']` ;
  - ACAL375 situait `RETENTION_JOURS` dans `trash/services.py`, alors qu'il est défini dans `trash/models.py`.

  Tous les autres ancrages des 11 tâches existent. Aucune clause « Si (a)/(b) ».
- **Apport net** : une porte d'écriture fermée en plus (le `sync-devis/` du module), une décision ouverte au lieu d'un cas
  perdu, et trois corrections de texte.

## 6. Décisions

- **D-ACAL-VER2-1** (Reda, 02/11/2026, question interactive) : réponse **« Signature du dératé »**. La production stockée
  porte une signature des entrées d'ombrage. À la réouverture, si la signature manque ou diffère, l'atelier recalcule et
  dérate. Un document inchangé reste octet-identique, donc ACAL31 est conservé. Inscrite dans `docs/audits/decisions.yml`
  et dans ACAL367, dont le périmètre couvre maintenant ce second cas.

## 7. Optionnel (non déposé)

- **ACAL359 (S4).** `FichesIncompletes.jsx::MaterielDuCalcul` montre la liste par pan dès deux lignes, même quand le champ
  n'a qu'un seul module.
- **ACAL31.** Le test d'exécution ACAL31 d'`estimatorRuntimePro10Pro11.test.ts` dépasse le délai de 5 s par défaut au
  démarrage à froid (environ 5,0 s par cas), mais passe avec un délai plus long. C'est un risque de flaky en CI.
- **ACAL42.** `AtelierPanneaux.test.jsx` simule un motif que le serveur n'envoie jamais. Le commentaire de
  `apps/calepinage/apps.py` est périmé.
- **ACAL90.** `remplacer_lignes` marque « retirée à la main » une classe abandonnée par une recomposition automatique
  (révision après visite C&I). Non sondé.
- **ACAL353.** `_ecrire_conception` écrit le calepinage avant de resynchroniser le devis. Sur un 409, la conception reste
  peut-être enregistrée alors que le devis est inchangé. Non vérifié.
- **ACAL355.** `offres_tailles._layout_de_la_taille` garde les `zones[i].result` de l'ancienne taille. Soupçon S3, non sondé.
- **ACAL368.** `openapi_docs.py::DevisErreurFromLayout` ne déclare pas `hors_reseau`.
- **ACAL346.** `docs/claude-memory/qa-coherence-auditor.md` ne cite pas les trois règles `CAL_*`. Ce point est porté par
  ACAL372.

## 8. Couverture et non-couvert

- **Couvert.** 48 tâches sur 362 construites : les 13 écarts du 10/10, puis 35 des 68 P0/S1, dont les 20 jamais tirées.
  Les vérificateurs ont rapproché commits, tests nommés et code de `main`. Les sondes ont été rejouées : 5 anciennes et 8
  nouvelles. Trois rejeux vitest.
- **Non couvert.**
  - Les 314 autres tâches construites, dont 33 P0/S1.
  - Les tests Django à base de données (laissés à la CI).
  - Aucun aller-retour à l'écran : la clé de carte manque à la pile locale, et ACAL351 reste ouverte.
  - L'effet de la pente réécrite (ACAL366) sur la production n'a pas été mesuré.
- **Statut du registre.** Après ce dépôt : 359 tâches cochées sur 376 (95 %), ACAL366 à 376 ajoutées. Cette contre-visite
  de clôture porte **4 écarts S1-S2** : le cycle n'est pas sorti, il faut deux contre-visites consécutives à zéro S1-S2.

## 9. Coût

- 8 vérificateurs opus (effort élevé) : environ 1,6 M de jetons.
- 1 rejeu vitest opus et 1 seconde lentille opus : environ 0,3 M.
- 1 critique Fable (effort élevé).
- 1 rédacteur opus : 11 tâches v3, environ 0,43 M.
- Orchestrateur :
  - échantillon déterministe et triage des 48 verdicts ;
  - 13 sondes jouées une par une par le verrou, après le redémarrage de Docker ;
  - 1 sonde réécrite pour APDF (`C-APDF-VER2-01`).
- H0 S0 O11 F1 · jetons sous-agents environ 2,5 M

<!-- verifie | groupe: ACAL | pct: 95 | ecarts_s1_s2: 4 -->

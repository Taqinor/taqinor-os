# Vérifie AMOT — contre-visite de clôture du groupe moteur (D2), 31/10/2026

Commande `vérifie AMOT` (METHODE §C.4.2, skill audit §5), lancée par `loop audit` (deuxième itération). Après le merge de
la contre-visite ACHT (PR #1180), `audit_registre.py --du` liste quatre groupes dus en clôture (≥ 95 %) : AMOT 96/100,
ASEC 54/54, AGNR 47/48, ATOT 35/35. Ils se jouent par nombre de tâches cochées décroissant : AMOT passe en premier. La
contre-visite précédente, du 11/10 (`docs/audits/2026-10-11-moteur-verifie.md`), était à mi-parcours.

Pour chaque tâche de l'échantillon, on rapproche le texte, le ou les commits, le test nommé et le code de `main` avec les
7 critères de `docs/claude-memory/lecons-construction-qjr5.md`. Chaque écart S1-S2 est prouvé par une sonde exécutée en
transaction annulée. Les écarts confirmés sont déposés en tâches v3 dans le plan du propriétaire des fichiers.

La contre-visite n'a rien construit, n'a lancé aucun deploy et n'a rien lu ni écrit en production. Toute correction
déposée reste gardée par le niveau de règles du devis : un devis envoyé garde ce qu'il a imprimé
(`docs/claude-memory/devis-envoyes-nouveaux-rendus.md`).

## 0. Préconditions

- **SHA.** `origin/main` = `d57c36964` (PR #1178), re-fetch en début d'itération. Branche de claim : `verifie-amot-cloture`
  (commit vide, poussé).
- **Registre.** D2 `moteur`, groupe AMOT, dossier `docs/audits/2026-10-08-moteur.md`, 96/100 cochées. Restent ouvertes
  AMOT54, AMOT64, AMOT65, AMOT78 (`[BLOCKED]`, fausse prémisse ; son objet est couvert par RHOR6).
- **Inventaire (déterministe).** 96 tâches AMOT `[x]` : 54 dans `PLAN_AUDIT_MOTEUR.md`, 32 dans
  `PLAN_AUDIT_TRANSVERSE.md`, 4 dans `PLAN_AUDIT_DEVIS.md`, 3 dans `PLAN_AUDIT_DEPLOY.md`, 2 dans
  `PLAN_AUDIT_FACTURATION.md`, 1 dans `PLAN_AUDIT_GENERATEUR.md`.
- **Échantillon (graine = SHA `d57c36964f18ac8ddc4f7b8d80bf4dcbb4bce903`).** Les 25 tâches cochées portant S1 ou P0
  (AMOT8, 10, 11, 15-19, 29, 30, 35, 48, 57-60, 69, 70, 72, 73, 79, 80, 86, 90, 99), plus 25 % du reste tirées par
  `random.Random(int(sha, 16)).sample` sur les ids triés (17 sur 71) : AMOT1, 2, 22, 24, 28, 34, 39, 41, 42, 44, 49, 53,
  55, 62, 71, 83, 94. Total : **42 tâches**.
- **Pile des sondes.** Conteneur jetable `sonde-verifie-amot` sur l'image `erp-agentique-django_core`, code de `main`
  copié par `git archive` ; base de démo partagée, 0 migration en attente. Sondes Python en transaction annulée (0 mail,
  0 tâche Celery, base inchangée) ; une sonde Node sur les fonctions pures du front.

## 1. Vérificateurs (11 agents frais, opus, effort élevé, lecture seule, même répertoire, 3 à 4 tâches chacun)

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **35** | AMOT1, 2, 8, 10, 11, 15, 16, 17, 18, 19, 22, 24, 28, 30, 34, 35, 41, 42, 48, 53, 55, 57, 58, 59, 69, 70, 71, 73, 79, 80, 83, 86, 90, 94, 99 |
| partiel | **6** | AMOT29 (S1), AMOT39 (S2 + S3), AMOT44 (S3), AMOT49 (S3 ×2), AMOT60 (S3), AMOT62 (S3) |
| régression | **1** | AMOT72 (S2, introduite par RPDF12) |
| non-fait / faux / déjà-présent | 0 | — |

Changements postérieurs jugés voulus, pas des régressions : les gardes « règles d'origine » (`calcul_corrige`,
`regles_calcul`) qui laissent un devis envoyé tel qu'imprimé (décision du 08/10) ; la ligne « Statut de l'étude : offre
ferme » retirée (C&I préliminaire, décision du 26/10) ; « tarif à renseigner » devenu « tarif sur demande »
(D-ACI-17=a) ; le PDF industriel ne dit plus le repli « journées moyennes » (règle du 26/10 « rien d'incertain côté
client »).

## 2. Sondes (3 REPRO)

| Sonde | Tâche | Observé (code de `main`) |
|---|---|---|
| `docs/audits/sondes/AMOT/C-AMOT-VER-003.py` | AMOT29 | prix 90 000, économie horaire 6 500, onduleur 15 000 : curseur public **16,0** ans, palier d'échelle **18,8**, carte « avec » **16,8** (= `roi_a`) |
| `docs/audits/sondes/AMOT/C-AMOT-VER-004.py` | AMOT39 | kWh annuel déclaré + relevé de 12 factures : le moteur retient `kwh_annuel`, la synthèse étiquette la source **« factures »** |
| `docs/audits/sondes/AMOT/C-AMOT-VER-005.mjs` | AMOT72 | remise 10 %, onduleur 24 000 : écran du générateur **16,5** ans / gain 55 603, PDF (provision payée) **16,1** / 58 003 |

Les constats C-AMOT-VER-001 et -002 appartiennent à la contre-visite du 11/10 ; la numérotation continue à -003.

## 3. Écarts retenus

| Constat | Tâche | Écart de | Crit. | Grav. | Emplacement | Observé → attendu | Sonde |
|---|---|---|---|---|---|---|---|
| C-AMOT-VER-003 | AMOT102 | AMOT29 | C3 | S1 | `apps/ventes/domain/dimensionnement_devis.py::_payback_publie_palier` | forfait de rendement sur une économie horaire déjà nette, sans rendement prouvé, TVA 1,2 codée en dur → arguments de `calculate_savings_roi` ; palier retenu = `roi_a` | `docs/audits/sondes/AMOT/C-AMOT-VER-003.py` |
| C-AMOT-VER-003 | AMOT103 | AMOT29 | C3 | S1 | `apps/ventes/public/payload_batterie.py::_balayage_stockage_publique` | même forfait et aucune provision d'onduleur : le curseur de `/proposition` contredit `roi_a` → curseur à la position offerte = `roi_a` | `docs/audits/sondes/AMOT/C-AMOT-VER-003.py` |
| C-AMOT-VER-004 | AMOT104 | AMOT39 | C10 | S2 | `apps/ventes/domain/etude_ci.py::_consommation` | feuille retenue calculée mais jamais persistée → persistée dans l'étude (contrat d'abord) | `docs/audits/sondes/AMOT/C-AMOT-VER-004.py` |
| C-AMOT-VER-004 | AMOT105 | AMOT39 | C10 | S2 | `apps/ventes/quote_engine/ci/synthese.py::_bloc_baseline_source` | ordre de feuilles différent du moteur (source « factures » imprimée, montants seuls « interpolés », courbe mesurée seule « non résolue ») ; jumeau `industriel/cover.py::_CLES_CONSO` → lecture de la feuille persistée | `docs/audits/sondes/AMOT/C-AMOT-VER-004.py` |
| C-AMOT-VER-005 | AMOT106 | AMOT72 | C3 | S2 | `frontend/src/features/ventes/calc/roi.js::paybackMoteurHoraire` (appel de `useApercuEtude.js`) | provision d'onduleur non remisée sur les deux branches de l'écran → remise comme `_cout_onduleur_paye` au niveau ≥ 3 | `docs/audits/sondes/AMOT/C-AMOT-VER-005.mjs` |
| C-AMOT-VER-006 | AMOT107 | critique | C3 | S3 | `apps/ventes/offres_tailles.py::_carte_du_devis` | repli de la carte Recommandé « avec » sans stockage ni provision → `_cf_args` | STATIQUE |
| C-AMOT-VER-007 | AMOT108 | critique | C9 | S3 | `apps/ventes/offres_tailles.py::_cf_args` | provision toujours remisée, même pour un devis au niveau 2 dont le PDF ne la remise pas → remise conditionnée au niveau de règles | STATIQUE |
| C-AMOT-VER-008 | AMOT109 | AMOT49 | C8 | S3 | `apps/ventes/coherence/regles_invariants.py::_CLES_PRIX_VENTE` | `pu_ttc_remise` / `total_ttc_remise` non exemptés (1 522 faux positifs) ; règle pompage classée sur la seule désignation → exemptés, même texte que le moteur | STATIQUE |
| C-AMOT-VER-009 | AMOT110 | AMOT44 | C1 | S3 | `apps/ventes/quote_engine/agricole/pages.py::_sous_tolerance` | « de votre besoin » sur un besoin FAO-56 → réservé au besoin déclaré | STATIQUE |
| C-AMOT-VER-010 | AMOT111 | AMOT22 | C1 | S4 | `apps/ventes/quote_engine/i18n_labels.py` (`lg_methode_etude`) | « Simulation établie et le profil… » → « … établie sur le profil… » | STATIQUE |
| C-AMOT-VER-011 | AMOT112 | AMOT60 | C3 | S3 | `apps/ventes/extra_docs_views.py::lettre_relance_premium` | mise en demeure premium sur une facture brouillon → porte `recouvrement.facture_relancable` | STATIQUE |
| C-AMOT-VER-012 | AMOT113 | AMOT62 | C10 | S3 | `apps/ventes/tests/test_amot62_ci_options_divergentes.py::CiOptionsDivergentesTests` | source imposée moquée, devis sans variantes → devis réel variantés, rendu commercial et industriel | STATIQUE |

**Constats S1-S2 : 3** (1 S1, 2 S2), tous reproduits. AMOT114 clôt la section (acceptation en direct, jamais confiée à une
lane). Routage par propriétaire : moteur (`PLAN_AUDIT_MOTEUR.md`) AMOT102, 105, 107-109, 111, 114 ; transverse (`PLAN_AUDIT_TRANSVERSE.md`, `(@atomique: moteur, devis)`) AMOT110, car son nouveau libellé entre dans le masque fermé `_CLES_AGQ` d'un module de test du devis ; devis
(`PLAN_AUDIT_DEVIS.md`) AMOT103, 104, 113 ; générateur (`PLAN_AUDIT_GENERATEUR.md`) AMOT106 ; facturation
(`PLAN_AUDIT_FACTURATION.md`) AMOT112. Les corrections de payback (AMOT102, 103, 107) changent des chiffres de `/proposition` : AMOT103 porte le niveau de règles suivant (migration du devis), AMOT102 et AMOT107 l'attendent (`@after`).

C-AMOT-VER-003 touche deux propriétaires (`dimensionnement_devis.py` au moteur, `payload_batterie.py` au devis) : chaque
moitié corrige son propre appel, d'où deux tâches indépendantes. C-AMOT-VER-004 passe par un contrat : le devis persiste
la feuille retenue (AMOT104), le moteur la lit (AMOT105, `@after`).

## 4. Seconde lentille et critique de complétude

- **Seconde lentille sur le S1** (opus, effort élevé, contexte frais, voies différentes de la sonde). C-AMOT-VER-003
  **MAINTENU (S1)** :
  - `etude_horaire.simuler_batterie_jour` borne la restitution par le rendement, donc l'économie d'un palier est déjà
    nette et le forfait la frappe une seconde fois ;
  - le curseur et l'échelle sont affichés sur `/proposition`, à côté de `roi_a`, au même prix ;
  - aucune décision ne justifie deux définitions, et le chemin par défaut (niveau de règles 5, devis avec batterie) y
    passe.

  Second jeu de chiffres :

  | Prix / économie / onduleur | Curseur | Échelle | `roi_a` (= carte « avec ») |
  |---|---|---|---|
  | 120 000 / 9 000 / 20 000 | 15,4 | 18,0 | 16,2 |
  | 60 000 / 5 200 / 12 000 | 13,2 | 16,0 | 14,3 |

  La seconde lentille ajoute que le curseur oublie aussi la provision d'onduleur : ses deux erreurs vont en sens inverse.
- **Critique de complétude (1 appel Fable, effort élevé).** Elle a cartographié tous les appelants de `payback_publiable`,
  `compute_cashflow_payback`, `paybackMoteurHoraire` et `computeROI`, front et `apps/web` compris.
  - Rattachés aux constats :
    - provision d'onduleur à TVA 1,2 codée en dur et `battery_roundtrip` absent sur les paliers → AMOT102 et AMOT103 ;
    - branche miroir local `computeROI` de l'écran → AMOT106 ;
    - `industriel/cover.py::_CLES_CONSO` → AMOT105.
  - Nouveaux, déposés : la carte de repli de `_carte_du_devis` (AMOT107), la provision remisée pour un devis au niveau 2
    (AMOT108).
  - Spot-check des « ok » argent AMOT8, AMOT48 et AMOT59 : mécanismes en place. La clause « payback recalculé sur ce
    prix » d'AMOT59 est satisfaite à la lettre et fausse au fond : c'est C-AMOT-VER-003, dont le critère devient
    « palier offert = `roi_a` au dixième ».
  - `apps/web` ne recalcule aucun payback (passe-plat des clés servies).

## 5. Optionnel (non déposé)

- **AMOT10.** Un document rétréci par un scénario STOCKÉ, avec l'autre option signée, voit encore son `display_total`
  réécrit par QJR401 (hors du texte de la tâche).
- **AMOT15.** Une `economies_annuelles` écrite par la synchro du calepinage passerait en « économie saisie ». Aucun
  producteur actuel n'a été trouvé dans `frontend/src` : chemin probablement mort, à compter en lecture prod.
- **AMOT16.** Un rôle C&I `pose_*` posé sans le mot « pose » dans la désignation n'est pas compté (cartes résidentielles
  seulement).
- **AMOT24.** Des pourcentages de TVA restent hors de `pct_fr` (`residential/options.py`, `commercial/equip.py`,
  `agricole/pages.py`). Aucun écart visible avec les taux marocains entiers.
- **AMOT35.** `public/payload_economie.py::_bankable_headline` sert la P50 sans la règle ; aucun lecteur front.
- **AMOT48.** La règle nocturne ne saute pas les devis aux règles d'origine (3 violations sur la démo).
- **AMOT53.** Un devis agricole en une-page signé au domicile imprime l'annexe, le document agricole de 3 pages jamais.
  Par ailleurs, CLAUDE.md dit « 'onepage' = 1 » sans mentionner la 2ᵉ page d'annexe.
- **AMOT57.** Un tiret long « hors–réseau » n'est pas normalisé. « Câble AC onduleur off-grid » est classé
  différemment entre JS et Python (désignation hypothétique).
- **AMOT59.** La pilule « retenu » de l'échelle n'est pas ancrée sur `totaux_avec.ttc` (environ 100 MAD d'écart possible).
- **AMOT69.** Le taux de TVA de la fiche produit l'emporte sur un devis à 0 % explicite. Règle métier antérieure : à
  poser au fondateur si l'exonération doit primer.
- **AMOT71.** Pas de ligne `SpecifiedTradeAllowanceCharge` pour la remise (module Factur-X non branché).
- **AMOT73.** La garde ne couvre pas la forme ternaire `x if x else 20`.
- **AMOT19, AMOT70.** Échéancier sans tranche solde, ou tranche C&I sans jalon : cas limites non rejoués.
- **AMOT99.** Chaque jour type de charge est croisé avec tous les jours du mois de production (espérance).
- **Tests plus faibles que leur clause, comportement prouvé ailleurs** (preuve en direct ou autre module) : AMOT18,
  AMOT34, AMOT42, AMOT58, AMOT86.

## 6. Couverture et non-couvert

- **Couvert.** 42 tâches sur 96 cochées (toutes les S1/P0 + 25 %), commits, tests nommés, code de `main`, décisions
  D-AMOT-* / D-ACI-* / D-AGR-*. Exécutions :
  - par les vérificateurs, sur l'hôte : SimpleTestCase C&I, tests node de parité (154 et 6 verts), fonctions pures
    (`bankable`, `facturx`, `regles_invariants`), rendu résidentiel hors base ;
  - par l'orchestrateur : 3 sondes jouées.
- **Non couvert.** Les 54 autres tâches cochées ; les TestCase Django (une base est requise : la CI de `main` est verte
  sur `d57c36964`) ; aucun aller-retour en direct à l'écran (AMOT114 ouverte).
- **Statut du registre.** Après ce dépôt : 96 cochées sur 112 constructibles (86 %, AMOT102-114 ajoutées), contre-visite
  de clôture **avec 3 écarts S1-S2** → statut calculé `audité` ; le cycle n'est pas sorti.

## 7. Coût

- 11 vérificateurs opus (effort élevé) : ≈ 2,3 M de jetons. 1 seconde lentille opus : ≈ 0,15 M. 1 critique Fable
  (effort élevé) : ≈ 0,19 M — elle a ajouté deux trous déposés (AMOT107, AMOT108) et étendu les deux S1-S2 de la même
  famille à leurs jumeaux. 1 rédacteur opus : 13 tâches v3.
- La limite d'usage hebdomadaire a interrompu la seconde lentille et la critique, reprises ensuite.
- H0 S0 O13 F1 · jetons sous-agents ≈ 2,9 M

<!-- verifie | groupe: AMOT | pct: 96 | ecarts_s1_s2: 3 -->

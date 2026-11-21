# Consolidation du tour 1 — module calepinage (go-deep L5)

« Before reporting progress, audit each claim against a tool result from this session. Only report work you can point to
evidence for; if something is not yet verified, say so explicitly. If tests fail, say so with the output. »

Entrées : `registre/constats/T1-{F1,S1,B1,S2,T1}.jsonl` (136), `registre/evenements/T1-orchestrateur-rejeu.jsonl` (14 rejeux,
14 confirmés), `T1/*.md`, contrat § 5 de `docs/audits/2026-11-20-calepinage-l5.md`, code `da49cb55b` lu dans le worktree
(ancêtre de HEAD). Lecture du code : 5 vérificateurs sonnet en lecture seule (`T1/consol-work/{WA,EA,RS,RG,DG}.jsonl`), revue
et arbitrage ici (couvertures re-vérifiées sur le texte des tâches ACAL, priorités, classes ; 6 causes re-greppées).
Sorties : `registre/evenements/T1-consolidation.jsonl` (136 lignes, script `registre.md` § 6 : 0 ligne refusée),
`registre/classes.jsonl` (10), `T1/classes/K-*.md` (10), `backlog/D7-constats-tour1.md` (22 fiches). Aucun fichier du dépôt
modifié, aucun test exécuté : toute « preuve rouge » ci-dessous est ATTENDUE, non mesurée.

## (a) Comptes
- Verdicts : retenu 98 · doublon 32 · écarté hors périmètre 3 (B1-025, T1-025, T1-026 : barre/recherche de l'ERP,
  propriétaire deploy) · écarté faux 2 (T1-007 : le brouillon local existe — `frontend/src/features/calepinage/brouillon.js`,
  bandeau « Reprendre » de `ToitureDesign.jsx::brouillonPropose` ; T1-016 : la rétractation elle-même) · à reproduire 1
  (F1-026 productible de Marrakech : `apps/web/src/lib/estimatorBrainV2.ts::specificYieldPvgis14` lu, valeur PVGIS non
  recoupée → ACAL474) · écarté artefact 0 (aucun constat n'est dû à l'instrument ; la partie « 145 s sans effet » de B1-004
  est l'absence de Celery, le reste du constat tient).
- Gravité des retenus : S1 7 · S2 42 · S3 46 · S4 3. Priorités des retenus : P0 7 · P1 40 · P2 39 · P3 12.
  P0 = S1-005, S1-018, F1-030, S1-007, F1-027 (chiffre que voit le client, /proposal) + S1-024, S1-025 (saisie perdue → devis
  faux). Sévérité changée : F1-004/F1-024 S1 → P1 (libellé interne ; document et devis justes, rejeu) ; F1-020/F1-031 S1 →
  P1 (pièce technique, pas de chiffre client) ; S1-023 S1 → P1 (l'économie n'est pas imprimée) ; B1-004/S2-005 P0 → P1.
- Lanes (retenus) : atelier-erp 23 · style 13 · atelier-web 12 · réglages 11 · électrique 10 · résultats 10 · documents 9 ·
  mobile 7 · simulation 3. Propriétaires (retenus) : calepinage 93 · web 2 (F1-023 `estimatorBrainCommun.ts`, S1-018
  `estimatorBrainV2.ts`) · lead 2 · moteur 1 (S1-017). Par fichier de correction, devis possède aussi `pipeline.py` et
  `composition.py` (D7-01 t3, D7-07).
- Par relecteur (vus / retenus) : F1 32/29 · S1 27/22 · S2 25/18 · B1 25/15 · T1 27/14 (les doublons comptent « non retenus »).

## (b) Retenus par classe puis par lane (cause → correction ; détail ligne par ligne dans le registre)
| Classe (fiche) | Constats (dont doublons) | Cause racine lue | Correction (fiche) |
|---|---|---|---|
| K-GRANDEUR-UNIQUE | 10 : S1-005, S1-018, S1-017, S1-020, F1-004, F1-024*, F1-013, F1-029→DOC, S2-016, F1-026 | `RP/optimizer.ts::renderLiveWinner` ≠ `RP/zones.ts::liveActiveResult` ; `VD/geometrie.py::orientation_du_pan` ; `roofPro2.ts::PANEL2_WATT` ; `estimatorBrainV2.ts::annualSavingsMad` ≠ `ventes/economie.py::_donnees_du_devis` ; `SV/electrique.py::_rapport_publication` | D7-01, D7-02, D7-10, CAP-D6-05 |
| K-DEFAUT-CHOIX | 10 : S1-007, F1-027, F1-023, F1-008, B1-004, S2-005*, S2-020, S2-022, S2-023, S2-024 | `SV/devis.py::generer_devis` (aucune garde de taille) ; `ModeTerrain.helpers.js::demandeMoteur` → `politique_pas.py::AlleeFixe` ; `estimatorBrainCommun.ts::departageBase` | D7-04, D7-05, D7-08, D7-21 |
| K-DOC-GEOMETRIE | 5 : F1-020, F1-031, F1-021, F1-030, F1-028 | `SV/planche.py::_dessin_des_modules`/`_echelle_nommee`/`_etendue`, `SV/export_dxf.py::_rectangle`, `VD/geometrie.py::pans_du_document` | D7-03, D7-09 |
| K-IMPASSE | 14 : S2-001, S2-002, S2-010*, F1-016, F1-017, F1-032, F1-005, F1-025, S1-009, S1-001, S1-027, S1-012, S2-013, S2-017 | `norme_electrique` écrivable par PATCH seulement ; `PanneauMasseLestage.jsx::CHEMIN_REGLAGES` ; `SV/simulation.py::controler_meteo` | D7-11, D7-12, D7-15, ACAL436 |
| K-JARGON | 24 (10 doublons) | `SV/norme.py::norme_applicable` ×3 modules ; `SV/ombrage_chaines.py` ; `Bibliotheque.jsx::Section` ; `atelier/onglets.js::groupesOnglets` | CAP-D6-03 t4, D7-18, ACAL393 |
| K-ACTION-ENFOUIE | 14 | ordre de rendu `TD::ToitureDesign` ; `#rp9-finish` sous la carte ; `RT::go3DView` | ACAL399/401/402/420/435, D7-16 |
| K-RETOUR-FAUX | 21 (8 doublons) | `SV/documents/__init__.py::inventaire_des_documents` ; `production/TapisHoraire.jsx::charger` ; `api/axios.js::REQUEST_TIMEOUT_MS` ; `TD::enregistrerCalepinage` (`httpMessage(0)`) | D7-13, D7-14, CAP-D6-04/05 |
| K-GESTE | 10 (4 doublons) | `RT::map.on('wheel')` (`e.lngLat`) ; `BuilderDom.jsx` puce plein écran sur la pile MapLibre ; pas de `cooperativeGestures` | D7-14, ACAL423 |
| K-STYLE | 18 (4 doublons) | `roofbuilder.css::.rp9-host` palette littérale ; `RT::ensureSetbackInputs` classes sans règle | ACAL427-432/438/479, D7-19 |
| K-SAISIE-PERDUE | 4 : S1-023, S1-024, S1-025, S2-018 | `contexteAtelier.js::contexteCalepinageVersPayload` ; `RT::clearEditorState` ; `RT::map.on('dblclick')` ; `SV/variantes.py::CHAMPS_COPIES` | D7-06, D7-17 |
Sans classe : F1-011, F1-012, F1-015, B1-016 (contenu électrique : CAP-D3-21, CAP-D3-03, D7-20). Les classes attendues par
le brief sont toutes CONFIRMÉES par le code ; ajoutées : K-STYLE, K-SAISIE-PERDUE (classe 4 du rejeu).

## (c) Identifiants partagés que les corrections toucheront (lecteurs : `git grep -l` sur `da49cb55b`)
| Identifiant | Type | Lecteurs (hors le fichier qui l'écrit) | Attention |
|---|---|---|---|
| `rp9-reco-panels`, `rp9-areas-total-panels`, `rp9-reco-savings` | id DOM | `apps/web/src/pages/preview/toiture-3d-pro-11.astro`, `TD`, 3 goldens `FC/__golden__/toitureDesign.*.html`, `e2e/acceptation/acal6.spec.js` (savings) | site public = web |
| `rp9-finish` | id DOM | `RT`, `RP/captureBoot.ts`, pages publiques `ar|en/devis/mon-toit.astro`, `DevisMonToitFinish.astro`, `lib/tunnel/carte.ts` | déplacer = casser le tunnel public |
| `rp9-results` | id DOM | `RT`, `RP/matrix.ts`, `RP/optimizer.ts`, `e2e/calepinage-parcours.spec.js`, goldens | |
| `rp9-plein-ecran-toggle` | testid | `BuilderDom.jsx`, `ToitureDesign.test.jsx`, 3 goldens | |
| `rp9-obs-height`, `rp9-heatmap-toggle` | id DOM | `RP/obstaclesUi.ts` ; `RP/shadingUi.ts` + page publique preview | à MONTER dans `BuilderDom.jsx` |
| `cal-enregistrer-calepinage` | testid | `TD`, `ToitureDesign.calepinage.test.jsx`, `e2e/acceptation/acal.spec.js`, `acal6.spec.js`, goldens | barre fixe ACAL399 |
| `cal-devis-ouvrir`, `cal-devis-indetermine` | testid | `BoutonDevis.jsx/.test.jsx`, `E2E_HOOKS.md`, `e2eHooks.test.mjs` | cible → `/ventes/devis?devis=<id>` |
| `calx249-publiable` | testid | `VerdictElectrique.jsx/.test.jsx` | |
| `publiable` | clé d'API (`verdict_publiable`) | `SV/autoconsommation.py`, tests `test_acal_verdict_unique.py`, `test_calx248_verdict_publiable.py`, `test_acal_raccordement_unique.py`, `test_calx206_polystring.py`, `test_calx217_incident_isc_regimes.py` | ajouter un état, ne pas retirer la clé |
| `motif_indisponible` | clé d'API | `contract_samples/calepinage_documents.json`, `calepinage_sorties.json`, `views/documents.py`, tests `test_cal175_sorties.py`, `test_calx291_contrat_documents.py`, `test_calx321_manque_par_document.py`, `test_acal_resultat_servi_livrables.py` | contrat d'abord |
| `export-csv/?quoi=horaire` → 409 | route + code | `SV/export_csv.py`, `contract_samples/calepinage_serie_horaire.json`, `apps/web/src/lib/proposition.ts`, tests `test_acal_export_csv_fraicheur.py`… ; `cal-tapis*` : `TapisHoraire.jsx/.test`, `PanneauProduction.test.jsx`, `E2E_HOOKS.md` | |
| `production_annuelle` (etude_params) | clé | `apps/web` : `lib/proposition.ts`, `lib/tailleDetail.ts`, `lib/offresTailles.ts`, `components/proposition/ci/SectionAutoconso.astro`, `pages/proposition/[...token].astro`, `contract_samples/proposal_data.json`, `taille_detail.json` ; `installations/contract_samples/recette_ci.json` ; tests calepinage `test_acal_ecart_devis.py`, `test_calx5_simulation.py`, `test_calx70_*` | page CLIENT publique (web) |
| `rowAzimuthDeg`, `poseSurfaces` | clés du document | `contract_samples/roof_layout_v2.schema.json`, `ventes/contract_samples/proposal_data.json`, `apps/web/src/contract_samples/proposal_data.json`, `RP/poseSurfaces.ts`, `RP/panStats.ts`, `RP/hydratation.ts`, `lib/proposition.ts`, tests `test_acal_compte_surfaces_pose_partout.py`, `test_acal_parite_compte_modules.py`, `test_calx87_pose_facade.py` | convention = contrat d'abord (PACT10) |
| `norme_electrique` | champ | `contract_samples/parametres_calepinage.json`, `site_imagerie.json`, `models.py`, `selectors.py`, `SV/{electrique,norme,parametres}.py` | écran à créer (D7-11) |
| `calx48-lien-reglages`, `acal52-lien-reglages`, `calx362-lien-reglages-zone`, `cal-biblio-lien-reglages` | testid (liens sans ancre) | leurs tests respectifs assertent `href="/calepinage/reglages"` | les tests changent avec l'ancre |
| HTTP 409 `simuler/` (`MOTIF_SANS_PAN_EQUIPE`, `MeteoIndecise`), 409 approbation (`champ='decision'`, `calx349-erreur-decision`), 409 `devis/auto/`, 400 réglages | codes | `PanneauProduction.jsx`, `Approbation.jsx/.test`, `LeadWorkspace.jsx`, `ReglagesSimulation.jsx` | |
| `REQUEST_TIMEOUT_MS` = 20 000 | constante | `api/axios.js`, `api/axiosVX55Timeout.test.mjs` (assert littéral) | timeout PROPRE au téléchargement |

## (d) Déjà couverts (52 liens : 27 tâches ACAL, 25 fiches CAP) et maquettes
- ACAL : B1-001, T1-017 → ACAL430 · B1-005 → 428 · B1-006 → 427 · B1-007 → 402 · B1-019, T1-018 → 432 · B1-020 → 438 ·
  F1-003 → 435 (partiel : recadrage auto en D7-16) · S1-010, F1-022, T1-002 → 393 · F1-026 → 474 · F1-032 → 436 ·
  S1-002 → 420 (partiel : « Terminer » en D7-16) · S1-013, S1-014, T1-001 → 399 (ordre Générer/Enregistrer : D7-16) ·
  S1-022, S2-006 → 403 · B1-012 → 405 · S2-020 → 404 · S2-005 → 397 · T1-004, T1-010 → 423 · T1-012 → 401 · T1-022 → 409.
- CAP : F1-004, F1-024, F1-006, S1-006, F1-007 → CAP-D6-05 · S1-007 (promue P0 : D7-05), S1-008, S1-009, F1-010, S2-003,
  B1-014 → CAP-D6-04 · F1-014, S1-019, B1-003, B1-015, S2-004, S1-026 → CAP-D6-03 · S1-001, S1-027, S1-011, S1-015 →
  CAP-D6-06 · F1-011 → CAP-D3-21 · F1-015 → CAP-D3-03 · F1-025 → CAP-D2-16 · T1-021 → CAP-D6-17.
- Une tâche planifiée IRRÉALISABLE en l'état : ACAL397 « fini quand un clic sur norme électrique atterrit sur le réglage de
  la norme » — ce réglage n'existe sur aucun écran (S2-001, cause lue) → D7-11 t1 doit la précéder (`@after`).
- Maquettes (`docs/audits/l5-calepinage/maquettes/*.dc.html`, lues par grep de texte) : AUCUN constat ne contredit un choix
  de maquette ; elles appuient les corrections (« 22° · face sud — À confirmer, valeur de départ » = ACAL417 ; « Couvrir la
  facture — Recommandé » contre E-O 35° = D7-08 ; « 12 × 580 Wc = 6,96 kWc, le même chiffre sur tous les écrans » = D7-01/02 ;
  « Prêt à envoyer ? 1 point à régler » = CAP-D6-04 ; schéma jusqu'au compteur et au réseau = D7-20 ; photos à étiquettes au
  téléphone = CAP-D6-17). Point de vigilance : `Main.dc.html` propose « double-cliquez sur un bord » (édition) — la correction
  S1-025 (double-clic pendant le TRACÉ) ne doit pas le casser.

## (e) Corrections non couvertes → `backlog/D7-constats-tour1.md` (22 fiches, P0 d'abord : D7-01 … D7-07). Les cinq
observations du rejeu non constatées par un relecteur y sont marquées « vu au rejeu » : REJEU-NEW-1 (D7-04),
REJEU-NEW-2 (D7-01), REJEU-NEW-3 (D7-07, règle produit à confirmer), REJEU-NEW-4 (D7-08), REJEU-NEW-5 (D7-13, = F1-018).

## Choix tranchés ici (règle écrite, jamais une décision de Reda — à redire au rapport)
| # | Choix | Retenu | Règle | Réversible par |
|---|---|---|---|---|
| 1 | Module de départ de l'atelier | le 1er module actif du catalogue société, « à confirmer » (D7-02) | le plus simple, maquette (une seule puissance) | réglage société « module par défaut » |
| 2 | Devis sans facture | confirmation, jamais blocage (D7-05) | D-ACAL-9 conservé | retirer la question |
| 3 | « Partir d'un modèle » | copie matériel + saisies (D7-17) — contredit ACAL117 : À CONFIRMER avec Reda avant la tâche 1 | le plus simple | option du dialogue |

## Contrat de sortie — mesures du tour 1 (K1, K2, K6, K7, K9)
| K | Seuil | Mesuré au tour 1 (fichiers des relecteurs) | État |
|---|---|---|---|
| K1 | 0 constat S1-S2 ouvert | 49 retenus S1-S2 (S1 7, S2 42) ; 64 en comptant doublons et à-reproduire | loin |
| K2 | ≤ 3 S3 ouverts par écran | atelier Toit/Panneaux 23 · Réglages 6 · Électrique 5 · Bibliothèque 3 · Résultats 3 · autres ≤ 2 (classement par le champ `ecran`, approximatif) | 3 écrans au-dessus |
| K6 | ≤ 5 étapes, 0 saisie technique, contrôles au 1er écran ≈ base | S1 : 104 contrôles (31 au 1er écran) → 143 après tracé ; 21 → 48 champs ; aucun résultat simulé atteignable sans quitter l'atelier : 3 allers-retours et 3 réglages société (F1-017), module à désigner (S2-005), 35 réglages sur 37 vides sans valeur proposée (S2-006) ; atelier à 7,4-7,5 écrans (13,2 au téléphone) | non atteint |
| K7 | 0 classe héritée ; tailles et cibles ≥ 44 px ; thème suivi | B1 : 26 styles de boutons, 6 rayons, 17 tailles de texte, plus petit 9,6 px, 184 cibles sur 197 < 44 px (90 < 32 px), l'atelier ne change qu'à 3,94 % entre clair et sombre ; T1 : 15 cibles < 32 px au téléphone | non atteint |
| K9 | 0 violation axe | axe NON exécuté au tour 1 ; contrastes mesurés à la main sous 4,5:1 : 2,72 (titres du rail), 1,1-1,4 (listes en clair), 1,23 (Plein écran), 1,51, 2,94, 3,52 | non mesuré (≥ 6 échecs manuels) |

## Non tranché (dit tel quel)
- Causes « probables » seulement : T1-013, B1-011, T1-027 (scene3d/panelTexture/layoutEditor non relus en entier) ;
  T1-009/T1-014 (geste d'un doigt) ; F1-011, F1-012, B1-016-018 ; S2-015, S2-016, S2-017, S2-019, S2-024 ; S1-002 ; B1-005,
  B1-020 ; T1-021, T1-025 ; S1-005 partie devis et S1-018 (probables au rejeu). À relire avant leur correction.
- Jumeaux non vérifiés : `plan_cablage.py::_coins`, `Ombriere.jsx` « 180 = sud », `roofToolShared.ts` dblclick,
  `contexteToDevisPayload` sans facture, `views/sorties.py`/`export_projet.py` « Aucune conception ».
- Propriétaire de `frontend/src/api/axios.js` non résolu (D7-13 t4).
- REJEU-NEW-3 : la règle produit « structures + socles » n'est écrite nulle part — erreur ou convention, à trancher par devis.
- S1 des relecteurs : 9. Rejoués et confirmés : 8 (F1-004, F1-020, F1-024, F1-027, F1-030, F1-031, S1-017, S1-023).
  Non rejoué : T1-T1-007 — écarté sur la rétractation du relecteur (T1-T1-016) et le code du brouillon local ; aucun S1
  retenu ne reste à rejouer. Les 6 autres rejeux portent sur des S2 (S1-005, S1-007, S1-018, S1-020, S1-025, F1-010).

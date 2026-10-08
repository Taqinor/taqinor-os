# Audit D4 « générateur » — dossier d'évaluation (L2, contre-visite QJR5, 08/10/2026)

Unité **D4** (écran générateur de devis + calcul solaire côté écran), groupe **AGNR**, niveau **L2**. Claim : branche `audit-D4`.

Méthode : `docs/audits/METHODE.md` v2. Sorties brutes (lanes, verdicts, sondes) : scratchpad de la session — ici la
commande, le SHA et un extrait court seulement.

## 1. Charte (phase 1)
SHA lu : origin/main (branche audit-D4). Pile locale : checkout `C:\dev\taqinor-os` (détaché sur un origin/main récent) ; le
front servi sur http://localhost (rebuild du 07/10) ; `C:\dev\taqinor-os\frontend\node_modules` présent : les vérificateurs
peuvent y lancer `npx vitest run <fichier>` ou `node <script>.mjs` sur le code de cette checkout (dire son SHA : `git -C C:\dev\taqinor-os log -1`).

## Système et frontière
D4 possède : `frontend/src/pages/ventes/DevisGenerator.jsx` (5 545 l.), `frontend/src/pages/ventes/generator/**` (≈ 3 200 l.),
`frontend/src/features/ventes/solar.js` (2 730 l.), `solar*.test.*`, `autoQuote.js`. `docs/ownership.yml` PRIME. Lu seulement :
le moteur serveur (`quote_engine/builder.py`, `solar_classification`, `etude_horaire`, `dimensionnement`), `ventesApi.js`, internes
de `apps/web/src/pages/proposition/[...token].astro`, `apps/web/src/scripts/roof-tool-pro11.ts`.

## Règles maison
Écran 100 % TTC ; le formulaire ne snap ni ne rejette JAMAIS un nombre tapé (`noValidate`, `step="any"` partout — gardé par un
test) ; l'indicateur de marge (`prix_achat`) est GÉNÉRATEUR SEULEMENT, jamais dans une sortie client ; mots-clés de classification
`solar.js` alignés sur `quote_engine/builder.py` ; pompage : HMT + débit → plus petite pompe à courbe suffisante, VEICHI assorti,
afficheur SI22, m³/jour calculé UNE fois à la création, aucun onduleur ni batterie, aucun produit sans prix auto-rempli ; jamais un
chiffre inventé. Erreur sous le champ + bandeau qui le nomme ; normaliser plutôt que refuser. Décisions D-QJR5-1..15 (PLAN2
Groupe QJR5), D-CIQ, D-AGR, D-ASTK-1.

## NE PAS REFAIRE
Tâches ouvertes sur ces fichiers : SPL (découpe de DevisGenerator.jsx / solar.js, PLAN_AUDIT_TRANSVERSE + PLAN_AUDIT_DEVIS),
ATOT/ACAL/ALEA/ADEV/AMOT (PLAN_AUDIT_GENERATEUR, TRANSVERSE), CIQ/AGR (PLAN.md), ERR-QAH-* (ERROR_PLAN). Les audits J1b
(ADEV, dossier `docs/audits/2026-10-07-devis.md`) et D2 (AMOT, `docs/audits/2026-10-08-moteur.md`) viennent de déposer des
tâches qui touchent la parité écran ↔ serveur : CITER, jamais redéposer. Toute tâche nomme le SYMBOLE (la chaîne SPL déplace le code).

## Critères retenus
C1, C2, C3, C4, C6, C7, C8, C9, C10, C13.

## Étapes (identifiants stables)
- P1 ouverture : P1.1 nouveau devis depuis lead / client, P1.2 édition (`?edit=<id>`) — réhydratation exacte (mode, option
  recommandée, wattage, structure, factures, lignes, notes, sections, overrides), P1.3 profil de site / préréglages.
- P2 saisie : P2.1 lignes (prix TTC, quantité, remise, TVA par ligne), P2.2 jamais de snap/rejet, P2.3 sections/notes, P2.4 marge.
- P3 calculs écran : P3.1 dimensionnement résidentiel (solar.js), P3.2 C&I (étude), P3.3 pompage (courbe, VFD, m³/jour),
  P3.4 auto-remplissage depuis le stock (autoQuote), P3.5 économies / payback affichés.
- P4 enregistrement : P4.1 payload (replace-lines, etude-params, overrides) = ce que l'écran montre, P4.2 aller-retour
  enregistrer → rouvrir → enregistrer sans toucher ⇒ objet serveur identique, P4.3 erreurs serveur sous le champ.
- P5 parité : P5.1 chiffres écran = objet serveur = `/proposal`, P5.2 mots-clés JS = serveur.

## Scénarios H×H
- Pour chaque mode (résidentiel, commercial, industriel, agricole) : créer → enregistrer → rouvrir → enregistrer sans toucher ⇒
  objet serveur identique (hors normalisation de premier enregistrement constatée au live J1b) ; le total TTC écran = total serveur.
- Taper « 1234,567 » / « 0,5 » / un prix à 3 décimales : jamais arrondi ni refusé ; stocké tel quel (ou normalisé et signalé).
- Mêmes entrées dans `solar.js` et dans le moteur serveur (node vs python) ⇒ mêmes kWc, panneaux, onduleur, économie annuelle.
- Pompage : 0 onduleur, 0 batterie, m³/jour = débit@HMT × heures et omis pour pompe sans courbe.

## Détecteurs (scout)
`python scripts/check_tests_source_regex.py` ; `python scripts/check_ecrans_atteignables.py` ; `python scripts/check_api_contract.py` ;
`python scripts/check_modes_marche.py` ; `python scripts/check_parked_apps.py` ;
`python scripts/check_ownership.py --owner-of frontend/src/pages/ventes/DevisGenerator.jsx frontend/src/features/ventes/solar.js` ;
`cd C:\dev\taqinor-os\frontend && npx eslint src/pages/ventes/DevisGenerator.jsx src/pages/ventes/generator src/features/ventes/solar.js src/features/ventes/autoQuote.js` ;
`cd C:\dev\taqinor-os\frontend && npx vitest run src/features/ventes/solar` (résumé pass/fail) ;
grep `step=` / `noValidate` / `toFixed(` / `Math.round(` dans les fichiers possédés ; grep `window.confirm|window.alert|alert(` .

## 2. Plan des lanes et coût (phase 3)
| Ronde | Lanes (modèle / effort) |
|---|---|
| Scouts | détecteurs, dédoublonnage (haiku / low) |
| R2 jugement | LGEN1 DevisGenerator 1-1850 ouverture/réhydratation · LGEN2 1850-3700 lignes/recalcul · LGEN3 3700-5545 enregistrement (sonnet/high) · LSOLAR1 calculs solar.js · LSOLAR2 classification/auto-remplissage/pompage (opus/high) · LPANELS generator/** (sonnet/medium) |
| R3 porte empirique | VA (opus/high : LSOLAR1, LSOLAR2, LPANELS) · VB (opus/high : LGEN1-3) — jamais l'auteur ; node sur le code de la checkout + sondes HTTP en transaction annulée |
| Tâches | 1 rédacteur (opus/high) |
| Critique | 1 critique de complétude (opus/high) — aucun appel Fable |

12 agents, ≈ 3,5 M jetons de sous-agents.

## 3. Manifeste de couverture (phase 4)
**Détecteurs** (scout) : 13/13 exécutés, exit 0 — `check_tests_source_regex`, `check_ecrans_atteignables`, `check_api_contract`,
`check_modes_marche`, `check_parked_apps`, `check_ownership`, `eslint` sur les fichiers possédés, `vitest run src/features/ventes/solar`
(206/206 verts), grep `step="any"` (systématique), `noValidate` (présent), `toFixed`/`Math.round` (affichage), aucune boîte native.
Tous verts alors que 28 constats se reproduisent (4 S1).

**Fichiers lus / non lus par lane** (extrait ; liste complète au scratchpad) :
- **LGEN1** :
  Fichiers / plages LUS :
  - `frontend/src/pages/ventes/DevisGenerator.jsx` : l. 1-1850 (ma plage) lues INTÉGRALEMENT, plus, hors plage, 1849-2320, 2312-2404, 2400-2640, 2636-2766, 2955-3110,
  3103-3283, 3280-3700, 4140-4330, 4495-4545, 5030-5100 ; NON lues : l. 2766-2955 (composition locale/serveur, `handleAutoFill`), 3700-4140 (rendu du bandeau d'édition, rail, barre d'actions),
  4330-4495, 4545-5030, 5100-5545 (JSX des cartes Paramètres techniques / Simulation / pied d'édition) hors des questions de la lane.
  - `frontend/src/features/ventes/quote/` : `etatDevis.js` (intégral), `reouverture.js` (intégral), `lignesEcran.js` (intégral), `sizingReducer.js` (l. 60-465), `profilCi.js` (l. 120-260).
  - `frontend/src/features/ventes/etudeHorairePreviewPur.js` (l. 1-120), `etudePompagePreviewPur.js` (l. 224-268), `solar.js` (l. 997-1050, 1175-1190, 1449-1460, 1523-1580).
  - `frontend/src/pages/ventes/DevisGeneratorScenarioDefaut.test.jsx`, `DevisGeneratorTarif.test.jsx`, `DevisGeneratorBrouillonEdition.test.jsx` (harnais), `generator/CarteEcheancier.jsx` (ids), `PanneauAgricole.jsx` (l. 555-600), `ui/Combobox.jsx` (l. 78-90).
- **LGEN2** :
  LU en entier : `frontend/src/pages/ventes/DevisGenerator.jsx` l.1850-3700 (applyLead, applySiteProfile, applyClient, runAutoQuote, chargeur `?edit=`, réglages société, syncBillEstimator, setLine, refreshTarif, onProduitChange, onQuantiteChange, renameAsNewProduct, lignes/sections/notes, villas, recomposerLignes, avecQuantitesFigees, handlePresetApplied, appliquerCompositionServeur, handleAutoFill, recalculerDimensionnement, validate, choixEcran, entreesReellesEcran, persisterDevis, revenirAVersion, handleSubmit).
  LU en plages : `DevisGenerator.jsx` l.556-670 (registre de surcharges), 5365-5385 (bandeau pompes sans prix) ; `features/ventes/solar.js` l.1430-1500, 1690-1900 ; `features/ventes/quote/lignesEcran.js` (entier) ; `features/ventes/quote/overrides.js` l.170-228 ; `features/ventes/quote/etudeMarcheBloc.js` l.321-380 ; `pages/ventes/DevisLineRow.jsx` (grep des champs éditables) ; `pages/ventes/generator/LigneTable.jsx` (grep) ; `pages/ventes/DevisGeneratorTarif.test.jsx` l.1-110 ; serveur : `apps/ventes/views/liste_prix.py` l.110-200, `domain/tarification.py` l.85-123, `models.py` `LignePrixListe`, `domain/historique_config.py` l.61-121 ; contrôles de plan : `docs/plans/PLAN_AUDIT_TRANSVERSE.md` (ATOT20, ATOT28), `PLAN_AUDIT_DEVIS.md`, `PLAN_AUDIT_GENERATEUR.md` (grep d'ID).
  EXÉCUTÉ : `node` sur `solar.js` (`fusionnerRecomposition`, `ttcFromHt`, `ttcExactFromHt`, `htFromTtc`) — scripts `p1.mjs`, `p2.mjs`, `p3.mjs` dans le scratchpad de la lane.
  NON LU (de ma surface) : `DevisGenerator.jsx` l.1-1849 et 3700-5545 (autres lanes) ; `generator/**` hors LigneTable (grep seulement) ; `features/ventes/solar.js` hors plages ci-dessus (dont `computeAutoSizing`, `autoFillLines`, calcul de marge l.2679 vu en grep seulement) ; `autoQuote.js` ; `quote/etatDevis.js` (le mappeur `devisVersEtat`/`etatVersEcritures` n'a pas été relu : on a seulement vérifié par grep qu'il appelle `lignesEcranVersPayload`) ; `ProduitPicker`.
  NON EXÉCUTÉ : aucune sonde DB, aucun vitest, aucune capture (lane de lecture). Chaque constat porte sa sonde pour le vérificateur ; LGEN2-1, 2, 4, 5, 6 attendent une exécution (vitest/Django), LGEN2-3 est déjà exécuté côté fonction pure.
- **LGEN3** :
  LU (plages exactes) :
  - `frontend/src/pages/ventes/DevisGenerator.jsx` : 490-690 (finish, jeton, registre), 940-1100 (instantané brouillon, restauration), 1188-1215, 1263-1420 (ROI / multiPreview), 1704-1712, 2005-2200 (chargeur `?edit=`, réglages société), 2665-2700, 3095-3230 (validate), 3262-3700 (choixEcran, entreesReellesEcran, etatEcran, persisterDevis, revenirAVersion, handleSubmit, ouvrirConception3D), 3696-4100 (KPI, succès, form, bannières), 4496-4526 (curseur), 4900-4935, 5095-5545 (tailles, lignes, presets, historique, surcharges, pied, rail, dialogues). Les plages 4100-4496, 4526-4900 et 4935-5095 de la surface 3700-5545 n'ont été que GREPÉES (inputs `type=number`, erreurs, `pompe*`), non lues ligne à ligne : KPI pompage / étude industrielle / graphique et blocs `Panneau*` rendus par props.
  - `pages/ventes/generator/RailArgent.jsx` 36-125, `PanneauAgricole.jsx` 555-605, `LigneTable.jsx` 100-125 (+ greps inputs sur tous les `generator/*.jsx`).
  - `features/ventes/quote/etatDevis.js` 40-145, 260-365 ; `lignesEcran.js` 1-173 ; `etudeMarcheBloc.js` 1-100, 290-320 ; `profilCi.js` 213-303 (partiel).
  - `features/ventes/solar.js` : `optionTotalsTTC` 1653-1702, `multiPropertyPreviewTTC` 1903-1950, `controlerFacturesSaisies` 995-1015, `htFromTtc` / `ttcExactFromHt` 1455-1482, `discountForTarget` 2657-2664.
  - `ui/Button.jsx` 55-123, `lib/apiError.js` 1-92, `api/axios.js` 10-131, `api/ventesApi.js` 55-110.
  - Backend (lecture seule, pour les contrats) : `apps/ventes/views/devis_edition.py` 36-480, `views/devis_etudes.py` 120-410, `domain/lignes.py` 905-1103, `domain/etude_schema.py` 100-150, 400, 495-635, `domain/historique_config.py` 1-100, `domain/modifiabilite.py` 35-115, `domain/pompage.py` 744-764 / 893-940, `core/idempotency.py` 1-60 / 160-200, `models.py` 76-92 / 165-170 / 1770-1780, `serializers.py` 853-935 (champs).
- **LPANELS** :
  Lus en entier : `RailArgent.jsx`, `CarteEcheancier.jsx`, `CarteEconomieCi.jsx`, `CarteEconomiePompage.jsx`, `CarteEconomiePompageInterne.jsx`,
  `CarteMetrique.jsx`, `CarteResultatCi.jsx`, `CarteFacturesElectriques.jsx`, `LigneTable.jsx`, `PanneauResidentiel.jsx`, `PanneauCommercial.jsx`,
  `PanneauIndustriel.jsx`, `PanneauAgricole.jsx` (1-741), `VoletInterneEconomieCi.jsx`, `BlocEtudeReseau.jsx` (38-430 ; en-tête 1-37 via aperçu).
  Lus pour le contexte (hors surface, lecture ciblée) : `DevisGenerator.jsx` 975-1000, 1300-1420, 1560-1640, 1740-1752, 2298-2312, 2685-2708, 3176-3192, 3258-3326, 3360-3376, 3700-3762, 4900-5060, 5160-5185, 5465-5490 ;
  `features/ventes/echeancierEdition.js` 1-150 ; `features/ventes/quote/etudeMarcheBloc.js` 140-228, 395-440 ; `features/ventes/quote/etatDevis.js` 296-330 ;
  `features/ventes/quote/profilCi.js` (lignes revente) ; `features/ventes/solar.js` 1690-1712, 2659-2730 ; `backend/.../utils/echeancier.py` 1-80, 100-200, 265-420, 695-770 ;
  `stock/serializers.py` 335-364 ; `authentication/models.py` 490-545 ; `contract_samples/etude_pompage_preview.json` (exemple_pvgis_indisponible, regles_sorties).
- **LSOLAR1** :
  LU :
  - `frontend/src/features/ventes/solar.js` 1-1460 (intégral sur la plage de la lane) ; 1490-1515, 1564-1570, 1655-1670, 1740-1750, 2500-2510,
  2590-2595, 2700-2720 (grep ciblés : frères).
  - `frontend/src/pages/ventes/DevisGenerator.jsx` 115-175, 1290-1312, 1340-1440, 1520-1660, 1895-1955, 2160-2215, 2270-2310, 2700-2720,
  3310-3360, 4608-4622, 4880-5110 (appelants des calculs et rendu de l'aperçu).
  - `frontend/src/features/ventes/etudeHorairePreviewPur.js` 20-90 ; `features/ventes/autoQuote.js` 130-160 ; `features/ventes/quote/etatDevis.js` 286-295 ;
  `pages/ventes/generator/CarteFacturesElectriques.jsx` 95-150.
- **LSOLAR2** :
  LUS : `solar.js` 1060-1212 (prédicats de ligne/produit), 1316-1449, 1444-1660, 2085-2730 (en entier : index, table par
  défaut, `autoFillLines`, pompage résiduel, prix/kWc, coût d'achat, disponibilité « avec ») ; 165-195 (`estimerMois`),
  907-917 (`consoAnnuelleDepuisFactures`) ; `autoQuote.js` en entier ; `etudeMarcheBloc.js` 1-30, 321-339 ;
  `etudePompagePreviewPur.js` 224-268 ; `DevisGenerator.jsx` 870-930, 940-970, 1085-1200, 1205-1240, 1436-1458, 2170-2195,
  2660-2690, 2800-2850, 3135-3175, 3368-3392, 3735-3750 ; `PanneauAgricole.jsx` 520-600 ; `DevisTab.jsx` 165-190, 595-650 ;
  serveur (lu seulement) : `solar_classification.py` 1-222, `domain/catalogue.py` 240-247, 690-811, `core/product_roles.py`
  343-386, `utils/options.py` 59-123, 197-300, `builder.py` 765-800, 925-952, 2498-2572, 3784-3795, `creation_auto.py`

## 4. Run live (phase 4-c/4-d)
- Même écran que le walkthrough J1b (dossier `docs/audits/2026-10-07-devis.md` §4, L1) : `/ventes/devis/nouveau?edit=78`
  (résidentiel, 2 options), « Enregistrer les modifications » sans retouche, deux fois, instantané serveur avant/après :
  normalisation au 1er enregistrement d'un devis semé (`prix_par_kwc`, `ligne_composee`, `etude_params.puissance_kwc`), puis
  contenu identique au 2e (seuls les id de lignes changent). Aucune saisie manuelle perdue sur ce cas.
- Les autres constats (liste de prix HT écrite en TTC, factures d'un lead portées sur un autre, recomposition qui efface TVA/
  remise, enregistrement partiel annoncé comme réussi…) sont prouvés par les sondes node / HTTP des vérificateurs VA et VB
  (transactions annulées) — PAS rejoués à l'écran dans cet audit : la tâche d'acceptation live du groupe les rejoue.

## 5. Registre des constats (phase 4 → 6)


## RÉFUTÉS (avec argument)
Aucun constat de lane n'a été réfuté par V_VA ni V_VB. Hypothèses réfutées par les lanes elles-mêmes (code lu ou exécuté), à ne pas rouvrir :
- Réhydratation `?edit=` de mode, option recommandée, wattage, structure, hors-réseau, composition libre, villas, remise, TVA, note, prix
  cible, échéancier, conditions, tarif déclaré, éco C&I, distributeur, 12 factures, pompage v2 : relus puis ré-écrits identiquement
  (`etatDevis.js:140-265`, `etatDevis.test.mjs` 13/13) — LGEN1.
- Scénario / recommandation écrasés à l'ouverture : non, `REOUVERTURE` ferme `touche.scenario` (`sizingReducer.js:406-408`) — LGEN1.
- Aperçu horaire d'édition sur la facture du lead : non, avec `devis` dans le corps le serveur lit le devis (`etude_horaire_view.py:340-373`) — LGEN1.
- Re-dimensionnement à l'ouverture : non, `attenteMoteur` n'est armé que par `LEAD_APPLIQUE`/`PROFIL_SITE_APPLIQUE` — LGEN1.
- Double-clic = double POST : non, `ui/Button.jsx:75-90` verrou par `ref` + `setSaving(true)` dans le même tick — LGEN3.
- `noValidate` / `step="any"` manquant : non, scan node de tous les `type="number"` du générateur et de `generator/*` — LGEN3, LPANELS, détecteurs.
- `window.confirm|alert|prompt` : 0 occurrence (détecteur 13).
- `prix_achat` dans un payload : non, aucun envoi (`grep prix_achat`, `lignesEcranVersPayload` sans champ d'achat) — LGEN2, LPANELS.
- Classifieurs de PRODUIT JS ≠ serveur : non, 0 divergence sur 155 désignations × 13 colonnes ; `computeCashflowPayback`, `twoBillsSavings`,
  `kwhDepuisFactureMad`, `factureMad`, `autoconsoAvecRatio`, `productibleForCity`, `computeROI` au modèle « factures » : 0 écart sur
  20 000 à 30 000 cas tirés (LSOLAR1, LSOLAR2) — les écarts AGNR viennent des ENTRÉES, pas des formules.
- Pompage écran : plus aucun dimensionnement JS ; ni onduleur ni batterie possibles ; kit sans prix ⇒ ligne sans produit (LSOLAR2).
- Calcul local d'un chiffre que le serveur sert, dans `generator/**` : non, les cartes C&I/pompage ne font que formater (LPANELS).

## PLAUSIBLES (non promus — aucune sonde ne les a confirmés)
- `dayUsagePct: parseInt(dDayUsage) || 50` : « 62,5 » tronqué à 62, un 0 tapé devient 50 (LSOLAR1 OPTIONNEL) — absorbé si AGNR26 retire le curseur.
- Ville du productible : écran sur `selectedLead.ville_effective` vivante, serveur sur `etude_params.ville_calcul` figée (QJR591) — écart
  possible du repli local d'un devis rouvert après correction de ville (LSOLAR1).
- Distributeur choisi sans aucune conso : écran au tarif 1,75, serveur à 0,916 (QJR156) — rare (LSOLAR1).
- `getProfile` répondant > 1,5 s après le devis ⇒ `remiseMax` change après la capture de référence ⇒ `dirty=true` sans geste (LGEN1 O2).
- `validate()` en édition compare la facture d'hiver COURANTE du lead à la série stockée : second clic exigé sans retouche (LGEN1 O5, friction).
- Un `pose()` qui saute les `undefined` au rechargement après recomposition serveur peut laisser un état d'écran périmé (LGEN3 Couverture).
- Remise saisie à 150 ⇒ total 0, à −5 ⇒ majoration, sans avertissement hors `remiseMax` (LGEN3 probe1) — à trancher par le fondateur si besoin.

## OPTIONNEL (S4 ou durcissement — jamais une tâche sans décision)
- LSOLAR2-7 (V_VA S3 → S4) : code mort `buildEtudePompage` (`autoQuote.js:28-46`) et `computeBuyCost` (`solar.js:2690-2693`, tenu en vie
  par `calculs_golden.mjs`). À ajouter à la liste épinglée par ADEV69 quand elle sera construite.
- C-LGEN2-7 (V_VB S3 → S4) : `tauxTvaOf(produit, tvaStandard)` jamais appelé avec le 2ᵉ argument ; condition absente de toutes les données
  (taux standard = 20 sur les sociétés 1, 40, 43 ; 0 produit sans TVA sur 193). À rattacher à ATOT20.
- Arrondi du cumul de cashflow `Math.round` vs `round` Python : 66 cumuls à 1 MAD sur 30 000 cas, 0 payback différent ; sorties
  `cashflow_*`/`net_gain_*` de `computeROI` sans consommateur (LSOLAR1).
- `htFromTtc` normalise sans le dire un TTC à 3 décimales (« 1234.567 » relu 1234.57) — règle « normaliser et signaler » (LGEN2 O1).
- `parseInt(nombreProprietes)` : 2,5 villas ⇒ 2 ; repasser « villas → aucun → villas » efface les rattachements ; libellé de la boîte
  `avecQuantitesFigees` incomplet ; `refreshTarif` = 1 requête par ligne à chaque ajout (LGEN2 O2-O5).
- Dates « aujourd'hui » en UTC dans le générateur (`DevisGenerator.jsx:1749, 2693`, `PanneauAgricole`, `CarteEconomiePompage`) — couvert
  par la garde de classe ADEV73 (liste figée).
- `applyPrixCible` remet la remise à 0 sans message quand le prix cible dépasse le brut ; marge « TTC » incluant la TVA collectée ;
  permission `marge_voir` non consultée (pas de fuite : `prix_achat` déjà filtré par `prix_achat_voir`) ; hypothèses de `ResultatPompage`
  en clés techniques ; « sur  ans » sans horizon (LPANELS O-2 à O-6).
- `tensionRaccordement`, `consoMensuelle`, `etat.villeCi`, `etat.gammeNom` écrits sans lecteur (LGEN1 O1) — la garde AGNR41 les listera.
- `forcerSansJeton` resté levé après un `validate()` refusé ; `PATCH etude-params`/`overrides` sans `expected_updated_at` ; bandeau
  d'erreur sans `role="alert"` ; pas de garde de ré-entrance entre « Enregistrer » et « Concevoir en 3D » ; total absent du panneau de
  succès en édition (LGEN3 O1-O6).
- Mots-clés « Wi-Fi » vs `wifi` dans les classifieurs de rôle ; « Kit fixation panneaux » classé panneau des deux côtés ;
  `createAutoQuote` résidentiel ne remet pas `alertes` à `[]` ; `defaultProductLines` posées en agricole (LSOLAR2).
- Documentation périmée : SPL201 vise un moteur pompage JS qui n'existe plus (solar.js = 2 730 l.) ; CLAUDE.md « Pompage sizing … `solar.js
  debitAtHmt` … heures (editable, default 7 h) » ne décrit plus le code depuis AGR114/AGR130 — signalé au fondateur, hors périmètre d'un audit.

## 6. Couverture non atteinte et limites (phase 6)
Voir l’en-tête du groupe (Non couvert) dans le plan du propriétaire.

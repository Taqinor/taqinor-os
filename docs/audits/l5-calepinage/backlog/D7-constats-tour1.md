# D7 — Corrections issues des constats du tour 1 (consolidation, 21/11/2026)

Dépôt lu en LECTURE SEULE : `C:\dev\taqinor-os\.claude\worktrees\calpinage-module-enhance-04bba5`, code servi aux relecteurs
`da49cb55b` (ancêtre de HEAD, code inchangé depuis). Aucun fichier du dépôt modifié, aucun test lancé, aucun docker.
Source : `registre/evenements/T1-consolidation.jsonl` (un verdict par constat, cause `fichier::symbole`), causes de record
du rejeu `T1/rejeu.md`. Chemins courts comme D6 : `SV` = `backend/django_core/apps/calepinage/services`, `FC` =
`frontend/src/features/calepinage`, `RP` = `apps/web/src/scripts/roofPro11`, `RT` = `apps/web/src/scripts/roof-tool-pro11.ts`,
`VD` = `backend/django_core/apps/ventes/domain`, `TD` = `frontend/src/pages/ventes/ToitureDesign.jsx`.

Ce fichier ne porte QUE ce qu'aucune tâche ACAL382-490 ni aucune fiche CAP-D1…D6 ne couvre déjà (liste des couverts :
`T1/consolidation.md` § d). Quand une fiche existante couvre la moitié, la fiche D7 ne prend que l'autre moitié et le dit.
Ordre : P0 (chiffre faux que voit le client, ou saisie perdue) puis S1-S2 puis le reste. « Test rouge » = test à écrire
AVANT la correction, attendu rouge sur `da49cb55b` — aucun n'a été exécuté dans cette consolidation.
Rappel de périmètre (contrat L5 § 5) : le PDF `/proposal`, le moteur de devis et l'argent sont HORS du périmètre de la
campagne ; les fiches qui les touchent sont routées au plan de leur propriétaire (`check_ownership.py --owner-of`) et ne
changent que les NOUVEAUX rendus (mémoire « devis envoyés : nouveaux rendus seulement », 08/10).

---

## A. P0 — chiffre faux visible du client ou saisie perdue

### CAP-D7-01 — Une seule production, de la carte de l'atelier au PDF /proposal
- **Constats** : T1-S1-005 (S2, rejeu confirmé : carte 93 504 / Total + document 98 574 / PDF 111 420 kWh/an) ;
  « vu au rejeu, non constaté par un relecteur » : REJEU-NEW-2 (même devis : `production_annuelle` 40 424 = zone seule,
  kWc 154,78 = zone + champ, PDF 235 266). Classe K-GRANDEUR-UNIQUE.
- **Cause** (lue sauf mention) : `RP/optimizer.ts::renderLiveWinner` écrête DC/AC, `RP/zones.ts::liveActiveResult` non
  (et c'est lui qui est enregistré) ; le devis recalcule sur `VD/geometrie.py::orientation_du_pan`, qui décrit une pose
  est-ouest par la pente/face par défaut du toit (22°, Sud) — probable (rejeu) ; `VD/pipeline.py::ecrire_etude_params`
  lit la production du résultat RACINE (toit seul) alors que le kWc vient de `pans_du_document` (toit + sol) — lue (DG).
- **Après correction, l'utilisateur voit** : un seul chiffre de production dans la carte, le Total et l'onglet ; le devis
  et le PDF portent celui de la conception (ou l'écart nommé par `BandeauProvenanceProduction.jsx::EcartDevis`, D-ACAL-6).
- **Test rouge** : golden ACAL382 « toit plat E-O 15° » : carte = Total = `zones[0].result.annualKwh` ; `etude_params.toiture.pans`
  porte deux jambes E-O 15° (jamais 22° Sud) ; projet toit + champ : `production_annuelle` couvre les deux surfaces.
- **Tâches** (une chose chacune) :
  1. `liveActiveResult` applique le même écrêtage DC/AC que `renderLiveWinner` ; fini quand le golden E-O lit un seul
     nombre. `RP/zones.ts` — **calepinage**.
  2. `orientation_du_pan` rend les deux jambes posées d'une pose E-O (inclinaison et azimut POSÉS) ; fini quand le résumé
     API et `etude_params.toiture.pans` d'un E-O 15° ne disent plus « Sud 22° ». `VD/geometrie.py` — **calepinage**.
  3. `ecrire_etude_params` somme la production de toutes les surfaces chiffrées ; fini quand le devis du projet toit + champ
     a `production_annuelle` cohérente avec ses kWc. `VD/pipeline.py` — **devis** → `PLAN_AUDIT_DEVIS.md`. Lecteurs à
     prévenir : `apps/web` proposition (`lib/proposition.ts`, `components/proposition/ci/SectionAutoconso.astro`,
     `contract_samples/proposal_data.json`) — **web**.
- **Recouvre** : CAP-D6-05 t3 (cartes Recommandation/Total) — la tâche 1 ici EST cette t3 ; ne pas la construire deux fois.
- **Priorité** : P0.

### CAP-D7-02 — Plus de module « 720 Wc par défaut » hors catalogue
- **Constats** : T1-S1-018 (S2, rejeu : écran 72 kWc / 720 W, devis et PDF 71 kWc « Canadian Solar 710 W » jamais choisi),
  T1-B1-004 (S2 : « Lancer la simulation » refusé 409 « aucun pan ne porte modules et puissance crête » alors que
  l'atelier affiche 261 × 720 W), T1-S2-005 (doublon). Classe K-DEFAUT-CHOIX / K-GRANDEUR-UNIQUE.
- **Cause** (lue) : `apps/web/src/lib/roofPro2.ts::PANEL2_WATT` = 720 sert l'atelier quand aucun module n'est choisi, sans
  rien écrire dans `modules[]` ; `SV/chaines.py::bloc_pose` ne prend le kWc que d'un produit du stock ou de
  `modules[].pmaxWc` → `SV/simulation.py::verifier_simulable` lève `MOTIF_SANS_PAN_EQUIPE` ; la composition ventes prend le
  premier 710 W du catalogue.
- **Après** : l'atelier part du module catalogue que le devis composera (le premier module actif de la société, nommé
  « module de départ — à confirmer ») ; kWc, simulation et devis lisent le même `moduleId`.
- **Test rouge** : document émis d'une séance sans choix de module (golden ACAL383) : `modules[0].moduleId` non vide et
  `pmaxWc` = celui du devis ; `verifier_simulable` passe.
- **Tâches** :
  1. Au démarrage, poser comme module du pan le module de départ servi par `design-context` (catalogue société) au lieu de
     `PANEL2_WATT` ; fini quand le document émis porte `moduleId`. `RP/context.ts`, `FC/atelier/useAtelierBoot.js` — **calepinage**.
  2. Si le document porte un module que la composition ne trouve pas, `generer_devis` refuse en nommant l'écart au lieu de
     substituer ; fini quand un test de génération le prouve. `SV/devis.py` — **calepinage**.
  3. Le site public garde son 720 W (`roofPro2.ts` = **web**, aucune édition ici).
- **Recouvre** : CAP-D6-05 t1 (libellé « N × 710 W ») reste à faire tel quel.
- **Priorité** : P0.

### CAP-D7-03 — Le champ au sol compté une fois, avec son module
- **Constats** : T1-F1-030 (S1, rejeu : DEV-202611-0009 = 218 modules = 42 zone + 176 terrain ; F1 : 400 = 224 + 176,
  1 089 500 MAD pour un besoin de ~50 kWc), T1-F1-028 (S2 : trois modèles d'un champ au sol, « plan du moteur non reçu »),
  T1-F1-029 (S2 : 710 Wc saisi, « puissance du module non renseignée »). Classe K-DOC-GEOMETRIE.
- **Cause** (lue) : `VD/geometrie.py::pans_du_document` additionne tous les pans et toutes les `poseSurfaces` (D-ACAL-5
  « sol = pan ») sans question ; la composition prend le premier module catalogue, pas celui du Terrain ;
  `RP/poseSurfaces.ts::saisirSurface` crée une surface sans bloc moteur ; `RP/zones.ts::renderAreasPanel` appelle
  `computeSiteStats(stats, ctx.surfacesPose)` sans `moduleFor`.
- **Après** : avant « Générer le devis », une ligne « Surfaces chiffrées : Zone 1 (42) · Champ au sol 1 (176) » avec une case
  par surface ; chaque surface composée avec SON module ; le tableau Site donne le kWc du champ.
- **Test rouge** : layout zone + champ → `pans_du_document` + case « champ seul » = 176 modules ; `computeSiteStats` rend un
  kWc non nul quand `moduleWc` = 710.
- **Tâches** : 1. choix des surfaces chiffrées (contrat de `generer-devis` + `FC/BoutonDevis.jsx`) — **calepinage** ;
  2. composition par surface avec son module (`VD/geometrie.py`) — **calepinage** ; 3. `moduleFor` passé à
  `computeSiteStats` (`RP/zones.ts`) — **calepinage** ; 4. « Enregistrer le contour tracé » envoie la demande moteur
  (`RP/poseSurfaces.ts`) — **calepinage**.
- **Priorité** : P0 (tâches 1-2), P1 (3-4).

### CAP-D7-04 — Champ au sol : un pas qui ne s'ombre pas, une seule convention d'azimut
- **Constats** : T1-F1-027 (S1, rejeu : 176 modules, vides de 0,60 m entre rangées de 4,3 m à 25°, aucun avertissement,
  chiffré au devis) ; « vu au rejeu, non constaté par un relecteur » : REJEU-NEW-1 (rangées « 180 = sud » lues face 270°
  Ouest par le serveur). Classe K-DEFAUT-CHOIX / K-DOC-GEOMETRIE.
- **Cause** (lue) : `FC/ModeTerrain.helpers.js::demandeMoteur` envoie `type: 'polygone'`, pente 0, sans latitude →
  `core/calepinage/politique_pas.py::AlleeFixe` (0,60 m), jamais `core/calepinage/surfaces/sol.py::SurfaceSol.politique_pas`
  (AntiOmbrage) ; `VD/geometrie.py::pans_du_document` : FACE = `rowAzimuthDeg` + 90 alors que `FC/ModeTerrain.jsx` libelle
  « Orientation des rangées (°, 180 = sud) ». Jumeau à vérifier : `FC/Ombriere.jsx` « 180 = sud » (`flowAzimuthDeg`).
- **Après** : le Terrain calcule un pas anti-ombrage (angle limite affiché) ; une allée imposée qui ombre affiche
  « la rangée N ombre la suivante de X % en hiver » ; 180 saisi = face sud partout.
- **Test rouge** : 30 × 22 m, 25°, 2 modules portrait à Agadir → pas ≥ pas anti-ombrage de `sol.py` ; `pans_du_document`
  d'une surface `rowAzimuthDeg` 180 rend une face 180.
- **Tâches** : 1. `demandeMoteur` envoie une surface `sol` avec latitude (`FC/ModeTerrain.helpers.js`) — **calepinage** ;
  2. avertissement d'ombrage mutuel quand l'allée est imposée (`FC/ModeTerrain.jsx`) — **calepinage** ; 3. une convention :
  `rowAzimuthDeg` = direction de FACE (libellé) ou serveur aligné — choisir UNE et la poser dans
  `contract_samples/roof_layout_v2.schema.json` (contrat d'abord, PACT10 ; lecteurs : `RP/poseSurfaces.ts`,
  `apps/ventes/contract_samples/proposal_data.json`, `apps/web/src/contract_samples/proposal_data.json` — **web**,
  tests `test_acal_compte_surfaces_pose_partout.py`, `test_acal_parite_compte_modules.py`, `test_calx87_pose_facade.py`).
- **Priorité** : P0.

### CAP-D7-05 — Un devis sans facture ne remplit pas le toit en silence (extraire CAP-D6-04 t3 en tête)
- **Constats** : T1-S1-007 (S2, rejeu : DEV-202611-0007 à 168 800 MAD / 34 kWc pendant que l'écran dit « Données
  insuffisantes » ; S1 : 513 800 MAD / 131 kWc pour une villa). Classe K-DEFAUT-CHOIX.
- **Cause** (lue) : `SV/devis.py::generer_devis` enchaîne feu vert, garde électrique, génération ; aucune garde de
  dimensionnement (le refus `MOTIF_FACTURE_ABSENTE` d'`apps/ventes/domain/taille.py` ne sert qu'au devis automatique) ;
  `_garde_kwh_declare` est muette sans facture.
- **Après** : « Aucune facture : le devis remplit le toit (34 kWc, 168 800 MAD). Confirmer ou renseigner la facture » —
  une confirmation, jamais un blocage (D-ACAL-9 inchangé).
- **Test rouge** : `generer_devis` sur un lead sans facture ni taille → réponse 409 « confirmation requise » portant le kWc ;
  avec `confirmer_taille=true` → 201.
- **Tâches** : 1. garde « taille non dimensionnée » dans `generer_devis` (`SV/devis.py`) — **calepinage** ;
  2. la question dans `FC/BoutonDevis.jsx` (même panneau que CAP-D6-04 t4) — **calepinage**.
- **Recouvre** : CAP-D6-04 t3 (ligne « taille sans facture » du panneau « prêt à envoyer ») — cette fiche en est la
  version P0 à construire d'abord ; CAP-D6-04 t3 la lira ensuite.
- **Priorité** : P0.

### CAP-D7-06 — Les saisies arrivent jusqu'au calcul (facture, cible, dernier coin)
- **Constats** : T1-S1-023 (S1, rejeu : facture 900 MAD, couverture « — », 0 MAD), T1-S1-024 (S2 : Effacer → 60 panneaux
  au lieu des 4 de la facture, devis DEV-202611-0003 généré à 60), T1-S1-025 (S2, rejeu : double-clic → triangle, ~194 → ~97 m²).
  Classe K-SAISIE-PERDUE.
- **Cause** (lue) : `FC/atelier/contexteAtelier.js::contexteCalepinageVersPayload` ne passe que panneaux/panel_watt/scenario,
  et le DOM du mode calepinage n'a pas `#rp9-bill` (`RT::monthlyBill` = 0) ; `RT::clearEditorState` (appelé par `reset`)
  remet `neededPanels = 0`, `neededAuto = true` ; `RT::map.on('dblclick')` appelle `cancelPendingVertex()` puis `close()`.
- **Après** : couverture et économies calculées depuis la facture du lead ; Effacer garde la cible ; le double-clic pose
  le dernier coin et ferme.
- **Test rouge** : `ToitureDesignCibleAvec.test.mjs` : le payload calepinage porte la conso annuelle du lead ; test
  `roofPro11` : `reset()` garde `neededPanels` hydraté ; dblclick après 3 clics → 4 sommets.
- **Tâches** : 1. servir la conso annuelle du lead (kWh + source) dans `design-context` et la poser en `ctx.prodTarget`
  (`FC/atelier/contexteAtelier.js`, mode calepinage ET `contexteToDevisPayload`) — **calepinage** ; 2. `clearEditorState`
  ne touche pas la cible hydratée (`RT`) — **calepinage** ; 3. dblclick : `flushPendingVertex` si loin du dernier sommet,
  puis fermer (`RT`) — **calepinage** ; jumeau `apps/web/src/scripts/roofToolShared.ts` (simulateurs publics) — **web**,
  à vérifier puis router.
- **Priorité** : P0 (2, 3), P1 (1 — l'économie n'est pas imprimée au PDF).

### CAP-D7-07 — Structures acier et socles seulement pour la pose qui en a besoin (vu au rejeu)
- **Constats** : « vu au rejeu, non constaté par un relecteur » : REJEU-NEW-3 (DEV-202611-0007, toit en pente affleurant,
  PDF p.2 « Structures acier × 48, Socles × 96 »). Classe K-DEFAUT-CHOIX.
- **Cause** (lue, DG) : `VD/composition.py::quantites_derivees_du_compte` rend `{'structure': N, 'socle': 2N}` sans
  condition de pose ; rien ne distingue affleurant / lesté.
- **À trancher avant de coder** : la règle produit (« structure » = kit de fixation pour toute pose ?) n'est pas écrite ;
  à confirmer par le propriétaire devis avant correction.
- **Après** : un toit en pente affleurant ne porte pas de socles lestés ; le kit de fixation suit la pose.
- **Test rouge** : composition d'un layout `flush` → aucune ligne « Socles ».
- **Tâches** : 1. `quantites_derivees_du_compte(nb, pose)` — **devis** → `PLAN_AUDIT_DEVIS.md`.
- **Priorité** : P0 si la règle confirme l'erreur (visible au PDF), sinon écarté.

## B. S1-S2 internes (P1)

### CAP-D7-08 — Recommandation de départ constructible (pas d'Est-Ouest 35° ni 0°)
- **Constats** : T1-F1-023 (S2 : E-O 35° « recommandé », +17 % de modules pour +1,4 % d'énergie) ; « vu au rejeu » :
  REJEU-NEW-4 (« Est-Ouest 0° »). Classe K-DEFAUT-CHOIX.
- **Cause** (lue) : `apps/web/src/lib/estimatorBrainCommun.ts::departageBase` garde le maximum d'énergie POSÉE sans
  critère de matériel ; `apps/web/src/lib/estimatorBrainV7.ts::tiltCandidates` rend `matrixTiltGrid(lat)` (base 0,5,10…)
  pour toutes les familles alors que V6 limite E-O à [10, 12, 15].
- **Après** : la carte recommande « Couvrir la facture » (maquette `Panneaux.dc.html`) avec kWh/kWc affiché ; E-O
  seulement à 10-15°.
- **Test rouge** : toit plat 163 m² Marrakech → recommandation ≠ E-O 35° ; aucune candidate E-O sous 10°.
- **Tâches** : 1. bornes E-O dans `tiltCandidates` (`estimatorBrainV7.ts` — **calepinage**) ; 2. départage à énergie par
  module ou à cible (`estimatorBrainCommun.ts` — **web**, partagé avec le simulateur public : router au plan web).
- **Priorité** : P1.

### CAP-D7-09 — Planche, DXF et plan de câblage dessinés dans le vrai sens, à la vraie échelle
- **Constats** : T1-F1-020 (S1, rejeu : modules couchés à 45 % de recouvrement, réel ≈ 1/52 imprimé « 1/100 »),
  T1-F1-031 (S1, rejeu : DXF 48 × 2,384 × 1,303 m au pas 1,323 m, TOITURE en double), T1-F1-021 (S2 : cotes générales =
  toit + obstacles hors pan). Classe K-DOC-GEOMETRIE. Sévérité S1 du relecteur ramenée à P1 : pièce technique interne,
  pas de chiffre client (le rejeu le note « non client »).
- **Cause** (lue) : `SV/planche.py::_dessin_des_modules` et `SV/export_dxf.py::_rectangle` (long côté en X, aucune
  orientation dans `geometry`) ; `SV/planche.py::_echelle_nommee` (arrondit la mention, pas le dessin) ; `SV/planche.py::_etendue` ;
  jumeau `SV/documents/plan_cablage.py::_coins`.
- **Après** : modules comptables d'un coup d'œil, jamais superposés ; « 1/50 » imprimé = 1/50 mesuré ; cotes du toit.
- **Test rouge** : dans `apps/calepinage/tests/test_cal175_sorties.py`, golden portrait 30° : aucun recouvrement de
  rectangles (PDF et DXF), échelle mesurée = imprimée, une seule polyligne TOITURE.
- **Tâches** : 1. enregistrer l'orientation portrait/paysage dans `zones[].geometry` (`RP/zones.ts` + schéma
  `roof_layout_v2.schema.json`, contrat d'abord) ; 2. une fonction d'emprise orientée partagée (planche, DXF, câblage) ;
  3. dessiner à l'échelle normalisée choisie ; 4. `_etendue` = toit seul + obstacle hors pan signalé ; 5. TOITURE sans
  doublon — tous **calepinage**.
- **Priorité** : P1.

### CAP-D7-10 — Un seul verdict électrique, trois états, et une seule saisie des phases
- **Constats** : T1-S1-020 (S2 : « Publiable » à l'onglet, « indéterminé » au cadre, « conforme » au résumé), T1-F1-013
  (S3 : phases saisies à deux endroits). Lié : T1-F1-010 (couvert par CAP-D6-04 t2 pour l'agrégat). Classe K-GRANDEUR-UNIQUE.
- **Cause** : `SV/electrique.py::_rapport_publication` (NON_VERIFIABLE hors `refusants`) — lue ; `FC/BoutonDevis.jsx`
  (bloc `cal-devis-indetermine`) ; `SV/assistant.py::_bloc_electrique` — probable ; `SV/raccordement.py` lit les phases de la
  saisie de raccordement, `FC/electrique/SaisiesElectriques.jsx` en écrit une autre — probable.
- **Après** : onglet, cadre de génération et résumé disent la même chose : « Prêt », « À compléter : 11 points »,
  « Bloquant : 1 ».
- **Test rouge** : étendre `apps/calepinage/tests/test_acal_verdict_unique.py` : calepinage sans matériel → les trois
  lectures rendent « à compléter » ; `test_acal_raccordement_unique.py` : phases saisies une fois, lues par schéma et verdict.
- **Tâches** : 1. état à trois valeurs servi (`SV/electrique.py`, sans changer D-ACAL-9) ; 2. `VerdictElectrique.jsx` lit cet
  état (testid `calx249-publiable` → à renommer avec son test) ; 3. une seule clé `phases` (`SV/raccordement.py`) — **calepinage**.
- **Priorité** : P1.

### CAP-D7-11 — Les réglages que les messages demandent existent (norme, lestage, dégagements)
- **Constats** : T1-S2-001 (S2 : aucun écran pour la norme électrique), T1-S2-010 (doublon), T1-S2-002 (S2 : « Aller aux
  réglages de lestage » → page sans lestage), T1-S2-023 (S3 : pesanteur et masse volumique de l'air demandées). Classe K-IMPASSE.
- **Cause** (lue) : `ParametresCalepinage.norme_electrique` n'est écrivable que par PATCH (`views/parametres.py`) ;
  `FC/commun/Provenance.jsx` lecture seule ; `FC/atelier/PanneauMasseLestage.jsx::CHEMIN_REGLAGES` = `/calepinage/reglages`
  (`FC/reglages/ReglagesSimulation.jsx` sans clé de lestage) ; `SV/lestage.py::PARAMETRES` liste les constantes.
- **Après** : une section « Norme et raccordement » (liste des normes du dépôt + « aucune »), une section « Lestage » (vent,
  terrain, coefficients, frottement) dans Réglages ; les liens y atterrissent sur le champ ; constantes physiques fixes.
- **Test rouge** : `PanneauMasseLestage.test.jsx` : le lien porte l'ancre d'un champ monté ; `ReglagesSimulation.test` : le
  champ `norme_electrique` est présent ; `lestage.py` n'exige plus `acceleration_pesanteur_m_s2`.
- **Tâches** : 1. champ norme ; 2. section lestage ; 3. dégagements depuis Sources ; 4. constantes fixes (`SV/lestage.py`) —
  **calepinage**. **Prérequis d'ACAL397** (« fini quand un clic sur norme électrique atterrit sur le réglage de la norme » :
  irréalisable sans la tâche 1) → `@after` à poser sur ACAL397.
- **Priorité** : P1.

### CAP-D7-12 — La simulation atteignable : un « tmy » qui aboutit, tous les manques d'un coup
- **Constats** : T1-F1-016 (S2 : « tmy » proposé, refusé « horizontale seule »), T1-F1-017 (S2 : 3 allers-retours, une clé
  par refus), T1-S1-016 (doublon). Classe K-IMPASSE.
- **Cause** (lue) : `SV/simulation.py::controler_meteo` refuse tout `tmy` sans fichier (ACAL454-456 ne couvrent que le
  fichier déposé) ; `SV/chaine_pertes.py::decision_meteo` + `_fenetre_pluriannuelle` lèvent un refus à la fois ; lien
  `/calepinage/reglages` sans ancre alors que `MeteoIndecise.champ` est servi.
- **Après** : un seul refus liste toutes les clés manquantes, chaque ligne ouvre son champ ; « tmy » grisé avec sa raison
  tant que la transposition PVGIS n'existe pas.
- **Test rouge** : réglages vides → UN 409 portant `manquants[]` de longueur ≥ 3.
- **Tâches** : 1. refus agrégé (`SV/chaine_pertes.py`) ; 2. ancre `#calx69-<cle>` dans le lien (`FC/production/PanneauProduction.jsx`,
  `BandeauProvenanceProduction.jsx`) ; 3. option `tmy` désactivée avec motif (`FC/reglages/ReglagesSimulation.jsx`) — **calepinage**.
- **Priorité** : P1.

### CAP-D7-13 — Des retours vrais (Documents, export horaire, téléchargement, hors ligne, approbation)
- **Constats** : T1-S2-011 (S2) + T1-T1-019, T1-B1-024 (S3) ; T1-F1-018 (S3) + T1-S1-021, T1-B1-023, T1-T1-020 et
  « vu au rejeu » REJEU-NEW-5 ; T1-F1-019 (S2) ; T1-T1-015 (S2) ; T1-S2-012 (S2) ; T1-S2-015 (S2) ; T1-S2-021 (S3).
  Classe K-RETOUR-FAUX.
- **Causes** (lues) : `SV/documents/__init__.py::inventaire_des_documents` (motif unique `MOTIF_SANS_CONCEPTION_DOCUMENT` quand
  seul `resultat` manque ; jumeaux `views/sorties.py::SANS_CONCEPTION`, `SV/export_projet.py::MOTIF_SANS_CONCEPTION`) ;
  `FC/AtelierPanneaux.jsx` (`detail` non relu après enregistrement) ; `FC/production/TapisHoraire.jsx::charger` (export-csv au
  montage) ; `frontend/src/api/axios.js::REQUEST_TIMEOUT_MS` sur `calepinageApi.js::telechargerDocument` ;
  `TD::enregistrerCalepinage` (`httpMessage(code ?? 0)`, pas d'outbox) ; `SV/approbation.py::MESSAGE_AUTO_APPROBATION`
  (`champ='decision'`) + `FC/atelier/Approbation.jsx` (×3) ; `FC/reglages/ReglagesSimulation.jsx` (une erreur, en haut) ;
  `apps/calepinage/selectors.py::_condition_recherche`.
- **Après** : « Conception enregistrée ✓ — il manque le calcul [Lancer] » ; aucun 409 à l'ouverture de Production ; un PDF
  long affiche « Rendu en cours… » ; hors ligne « enregistré sur ce téléphone, envoi au retour » ET l'envoi ; l'auteur voit
  « En attente d'un autre relecteur » (sauf exception approbateur seul D-ACAL 07/10) ; toutes les erreurs de réglage près du
  bouton ; recherche par le titre affiché.
- **Test rouge** : un par retour, chacun dans le module de test existant du fichier (inventaire « enregistré non simulé » ;
  `TapisHoraire.test.jsx` sans `simule` → aucun appel ; timeout propre au téléchargement ; etc.).
- **Tâches** (une chacune, toutes **calepinage**, sauf `axios.js` : propriétaire à résoudre) : 1. motif « simulation
  manquante » (+ 2 jumeaux) ; 2. relire la fiche après enregistrement ; 3. `charger` seulement si `simule` ; 4. timeout
  propre aux documents (laisser `REQUEST_TIMEOUT_MS` global — `axiosVX55Timeout.test.mjs` l'assert) ; 5. message hors ligne +
  file d'envoi du layout ; 6. boutons d'approbation selon l'auteur ; 7. erreurs de réglages listées au bouton ; 8. recherche
  par titre de repli.
- **Priorité** : P1 (1, 3, 4, 5), P2 (le reste).

### CAP-D7-14 — Gestes de carte : molette, plein écran, un doigt
- **Constats** : T1-F1-001 (S2) + T1-S1-004 ; T1-F1-002 (S3) + T1-B1-002, T1-T1-003 ; T1-T1-008 (S2) + T1-T1-024 ;
  T1-T1-009 (S2) + T1-T1-014. Classe K-GESTE.
- **Cause** (lue sauf mention) : `RT::map.on('wheel')` lit `e.lngLat` (absent) avant de tester Alt ;
  `FC/atelier/BuilderDom.jsx` pose `rp9-plein-ecran-toggle` en `absolute right-3 top-3` sur la pile MapLibre
  `top-right` ; `FC/pleinEcran.js` (repli CSS jamais lu, boîte `#rp9-map` 327×0) ; aucun `cooperativeGestures` sur la carte
  de l'atelier (seul `RP/viewerFullBoot.ts`) — probable pour le geste d'un doigt.
- **Après** : la molette zoome sans erreur ; « + » zoome ; au téléphone le plein écran remplit l'écran ; un doigt fait
  défiler la page, deux doigts la carte (ou plein écran), un coin se déplace à l'appui maintenu.
- **Test rouge** : `frontend/e2e/calepinage_tactile.spec.js` (existante) + spec ACAL482 : une ligne par geste de la matrice
  `K-GESTE` ; vitest du handler wheel sans `lngLat`.
- **Tâches** : 1. garde `e.lngLat` (`RT`) ; 2. placer la puce plein écran hors de la pile (`BuilderDom.jsx`) ; 3. repli plein
  écran CSS lu (`FC/pleinEcran.js`, `FC/atelier/useAtelierVues.js`) ; 4. `cooperativeGestures` en tactile (`RT`) — **calepinage**.
- **Priorité** : P1.

### CAP-D7-15 — Hauteur d'obstacle saisissable
- **Constats** : T1-F1-005 (S2 : aucune hauteur → une cheminée n'ombre jamais). Classe K-IMPASSE. (Le bouton d'ombrage,
  T1-F1-032, est ACAL436.)
- **Cause** (lue) : `RP/obstaclesUi.ts::obsHeightEl` lit `#rp9-obs-height`, que `FC/atelier/BuilderDom.jsx` ne monte pas.
- **Après** : le panneau d'un obstacle porte « Hauteur (m) » ; l'accès solaire en tient compte.
- **Test rouge** : `BuilderDom` rendu contient `#rp9-obs-height` ; un obstacle de 1,2 m baisse l'accès solaire du module voisin.
- **Tâches** : monter le champ (`BuilderDom.jsx`) — **calepinage**. `@after` aucune ; avant ACAL436 pour que la carte d'accès
  solaire ait des hauteurs.
- **Priorité** : P1.

### CAP-D7-16 — Restes des actions enfouies (ce que ACAL399/420/435 ne disent pas)
- **Constats** : T1-S1-002 (S2 : « Terminer le tracé » sous la flottaison — ACAL420 ne met que la consigne), T1-S1-014
  (S2 : « Générer » avant « Enregistrer » — ACAL399 ne règle pas l'ordre), T1-F1-003 (S2 : pas de recadrage après
  fermeture — ACAL435 donne le bouton Dessus, pas le cadrage), T1-T1-023 (S3 : 8 filtres au téléphone), T1-T1-027 (S3,
  probable : fenêtre « Déplacer les panneaux » cachée jusqu'au rechargement). Classe K-ACTION-ENFOUIE.
- **Cause** : `FC/atelier/BuilderDom.jsx` (`#rp9-finish` sous la carte `h-[56vh]`) ; ordre de rendu de `TD::ToitureDesign` ;
  `RT::go3DView` (easeTo pitch 58 sans fit) ; `FC/CalepinageList.jsx` ; `RP/layoutEditor.ts::renderLayoutPanel` (probable).
- **Après** : « Terminer » sur la carte ; « Enregistrer » avant « Créer le devis » dans la barre fixe ; la caméra cadre le toit
  fermé ; filtres repliés sous 768 px ; la fenêtre de disposition paraît dès le toit fermé.
- **Test rouge** : spec de mesures ACAL385, cases « visible sans défiler » ; vitest `renderLayoutPanel` après `close()`.
- **Tâches** : une par ligne ci-dessus — **calepinage** (`@after ACAL399` pour l'ordre, `@after ACAL420` pour Terminer).
- **Priorité** : P1 (S1-002, S1-014, F1-003), P2 (le reste).

### CAP-D7-17 — Un modèle de société porte le matériel et les réglages électriques
- **Constats** : T1-S2-018 (S2 : le modèle copie le contour d'un toit de Casablanca, pas le module ni l'onduleur ni les
  températures), T1-S2-017 (S2 : favoris = identifiants tapés), T1-S2-019 (S3 : préréglage « champ = valeur » sans liste).
  Classe K-SAISIE-PERDUE / K-IMPASSE.
- **Cause** (lue) : `SV/variantes.py::CHAMPS_COPIES` = (`roof_layout`, `layout_hash`, `pertes`) ; le matériel vit dans
  `resultat['entree_electrique']` ; `FC/Bibliotheque.jsx` (formulaire favoris et préréglages en texte libre).
- **Choix tranché ici (règle « le plus simple pour l'utilisateur », jamais une décision de Reda)** : un « Partir d'un modèle »
  recopie matériel + saisies électriques + pertes ; la géométrie reste copiée seulement si le lead est le même bâtiment.
  Réversible : une option du dialogue. Coût si faux : une société qui voulait la géométrie la recoche. ACAL117 a fixé la
  règle actuelle → à confirmer avec Reda AVANT la tâche 1.
- **Après** : un nouveau calepinage depuis un modèle a déjà son module, son onduleur et ses températures ; favoris choisis
  dans deux listes du catalogue.
- **Tâches** : 1. copier `entree_electrique` (`SV/variantes.py`) ; 2. sélecteurs catalogue des favoris (`FC/Bibliotheque.jsx`) ;
  3. liste des champs admis d'un préréglage (`SV/presets.py` → écran) — **calepinage**.
- **Priorité** : P1 (1-2), P2 (3).

## C. S3-S4 (P2-P3)

### CAP-D7-18 — Jargon et répétitions que CAP-D6-03 t4 ne couvre pas
- **Constats** : T1-B1-010, T1-B1-013 (+ S2-008), T1-S2-007, T1-S1-003 (+ B1-022, T1-005), T1-B1-019, T1-S2-025, T1-T1-006,
  T1-T1-022 (avec ACAL409). Classe K-JARGON.
- **Causes** (lues) : `RP/zones.ts::largeurAlleeDepuisReglages` + `SV/degagements.py::largeur_allee_circulation` (clé
  `degagements.allees_circulation.?`) ; `FC/Bibliotheque.jsx::Section` (`sousTitre` « (CAL197) »…) + `SV/profils_types.py`
  (chemin du dépôt) ; `FC/reglages/ReglagesSimulation.jsx::ChampValeur` (valeur d'énumération brute) ;
  `views/calepinages.py::_avertissements` répète `contexteAtelier.js::libelleCibleEstimee` ; `FC/FicheCalepinage.jsx` ;
  `FC/atelier/useAtelierBoot.js::bootCalepinage` (« Calepinage Calepinage ») ; `FC/RaccourcisAtelier.jsx` (tactile).
- **Test rouge** : la garde de CAP-D6-03 t4 étendue aux textes listés (aucun `::`, `.py`, `[]`, `?.`, code `CAL\d+`).
- **Tâches** : une par cause — **calepinage**. **Priorité** : P2 (P3 : S2-025, T1-006).

### CAP-D7-19 — Restes de style hors des listes de migration ACAL427-432
- **Constats** : T1-F1-009 (+ B1-008, B1-009, T1-010), T1-T1-011, T1-B1-017, T1-B1-018, T1-B1-021 (+ S2-009), T1-B1-011,
  T1-T1-013. Classe K-STYLE.
- **Causes** : `RT::ensureSetbackInputs` crée `rp9-setbacks`/`rp9-input`/`rp9-note` sans aucune règle dans
  `frontend/src/styles/roofbuilder.css` (lu) ; trois styles « choisi » (`.rp9-chip[aria-pressed]`, contour, coche — lu) ;
  `FC/production/PanneauProduction.jsx::TableauParPan` (probable) ; `FC/atelier/PanneauBatterie.jsx` (probable) ;
  `FC/reglages/ReglagesGabarits.jsx` (genres français en texte libre, `input type=file` natif — lu) ; `RP/panelTexture.ts`,
  `RP/scene3d.ts` (probable).
- **Test rouge** : `langageVisuel.test.mjs` (ACAL427/479) étendu à `roof-tool-pro11.ts`.
- **Tâches** : une par cause — **calepinage**. **Priorité** : P2-P3.

### CAP-D7-20 — Électrique lisible : tableau de dimensionnement, schéma complet, températures proposées
- **Constats** : T1-F1-011 (S2 → CAP-D3-21, reste ici le tableau statique), T1-F1-012 (S2), T1-B1-016 (S3), T1-S2-022 (S3).
- **Cause** : `FC/electrique/VerdictElectrique.jsx` ne publie que des motifs (probable : valeurs de chaîne déjà servies ?) ;
  `FC/SchemaUnifilairePanel.jsx` (champ → onduleur, nomenclature vide, sections « manquantes » seules — probable) ;
  `FC/electrique/SaisiesElectriques.jsx` (Tmin/Tmax sans repère — lu).
- **Après** : un tableau Voc(Tmin)/Vmp/Isc/DC-AC vert/rouge ; schéma jusqu'au compteur et au réseau (maquette
  `Schema.dc.html`), même grisé ; Tmin proposée depuis la météo du site, marquée « tirée de PVGIS ».
- **Tâches** : 1. tableau (`VerdictElectrique.jsx`) ; 2. schéma partiel + nomenclature (`SchemaUnifilairePanel.jsx`) ;
  3. Tmin/Tmax proposées (`SaisiesElectriques.jsx`) — **calepinage**. **Priorité** : P2.

### CAP-D7-21 — Bifacial seulement quand il s'applique
- **Constats** : T1-F1-008 (S3). Classe K-DEFAUT-CHOIX.
- **Cause** (lue) : `RP/optimizer.ts::paintCard` affiche le gain (`BIFACIAL_GAIN_FLAT/TILTED`) pour toute carte.
- **Après** : aucun gain en pose affleurante ni pour une fiche non bifaciale. **Test rouge** : vitest `paintCard` flush →
  pas de `rp9-reco-bifacial`. **Tâche** : `RP/optimizer.ts` — **calepinage**. **Priorité** : P2.

### CAP-D7-22 — Routés hors du module (aucune tâche calepinage)
- T1-B1-025 (`.gs-input` blanc en sombre, `frontend/src/styles/deploy/16-p67-composants.css`), T1-T1-026
  (`.header-menu-btn` #0f172a, `deploy/12-progression-mobile.css`), T1-T1-025 (barre du haut à 820 px, probable) →
  propriétaire **deploy** ; T1-S1-001, T1-S1-027 → **lead** via CAP-D6-06 t4 (`PLAN_AUDIT_LEAD.md`) ;
  T1-S1-017 (TRI sans facture, `apps/ventes/economie.py::_donnees_du_devis`) → **moteur** : « sans consommation connue,
  l'onglet Économie ne publie ni TRI ni retour » — P1, test rouge dans le module de test existant d'`economie.py`.

## D. Correspondance constat → fiche (ce fichier)
| Fiche | Constats retenus | P |
|---|---|---|
| D7-01 | S1-005, REJEU-NEW-2 | P0 |
| D7-02 | S1-018, B1-004 (+S2-005) | P0 |
| D7-03 | F1-030, F1-028, F1-029 | P0/P1 |
| D7-04 | F1-027, REJEU-NEW-1 | P0 |
| D7-05 | S1-007 (CAP-D6-04 t3 promue) | P0 |
| D7-06 | S1-023, S1-024, S1-025 | P0/P1 |
| D7-07 | REJEU-NEW-3 | P0 à confirmer |
| D7-08 | F1-023, REJEU-NEW-4 | P1 |
| D7-09 | F1-020, F1-031, F1-021 | P1 |
| D7-10 | S1-020, F1-013 | P1 |
| D7-11 | S2-001, S2-002, S2-023 | P1 |
| D7-12 | F1-016, F1-017 | P1 |
| D7-13 | S2-011, B1-024, F1-018, REJEU-NEW-5, F1-019, T1-015, S2-012, S2-015, S2-021 | P1/P2 |
| D7-14 | F1-001, F1-002, T1-008, T1-009 | P1 |
| D7-15 | F1-005 | P1 |
| D7-16 | S1-002, S1-014, F1-003, T1-023, T1-027 | P1/P2 |
| D7-17 | S2-018, S2-017, S2-019 | P1/P2 |
| D7-18 | B1-010, B1-013, S2-007, S1-003, B1-019, S2-025, T1-006, T1-022 | P2/P3 |
| D7-19 | F1-009, T1-011, B1-017, B1-018, B1-021, B1-011, T1-013 | P2/P3 |
| D7-20 | F1-011, F1-012, B1-016, S2-022 | P2 |
| D7-21 | F1-008 | P2 |
| D7-22 | B1-025, T1-025, T1-026, S1-017 (+ S1-001, S1-027 via CAP-D6-06) | — |
Retenus sans fiche D7 parce que couverts (voir `T1/consolidation.md` § d) ; restes non attribués à une fiche : S2-013
(variantes non comparées à la conception courante), S2-014 (menu Comparer), S2-016 (IAM société non hérité, probable),
S2-024 (replis silencieux non étiquetés — avec ACAL404/405), S1-012 (« Bâtiment sans id », second circuit
d'enregistrement des surfaces) → nouvelles, à rattacher à une fiche au tour 2 (cause dans le registre, non approfondie ici).

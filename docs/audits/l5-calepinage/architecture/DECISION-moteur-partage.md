# DÉCISION — un moteur de conception partagé, sans écran (« le module caché »)

Lane ARCHITECTE de la campagne L5 calepinage, 21/11/2026. Question de Reda (21/11, mot pour mot) : « dont forget that
in the CRM module i already have a lot of stuff that you can maybe change or move to calpinage .... but if you remove to
calpinage we still should be able to make quotes in the crm module without having to open calpinage... maybe a hiden
module used by both ? search the best and decide ».

Dépôt lu en LECTURE SEULE : `C:\dev\taqinor-os\.claude\worktrees\calpinage-module-enhance-04bba5`, HEAD `33c076d00`.
Aucun fichier du dépôt modifié, aucun test, aucun docker. Chaque fait « chez nous » cite `fichier::symbole` lu ou greppé
dans cette session ; ce qui ne l'est pas est dans § 9 « Non vérifié ». Chemins courts : `SV` =
`backend/django_core/apps/calepinage/services`, `VD` = `backend/django_core/apps/ventes/domain`, `QE` =
`backend/django_core/apps/ventes/quote_engine`, `RP` = `apps/web/src/scripts/roofPro11`, `WL` = `apps/web/src/lib`,
`FV` = `frontend/src/features/ventes`, `FC` = `frontend/src/features/calepinage`, `FCRM` = `frontend/src/features/crm`.

---

## 0. La décision en dix lignes (pour Reda)

1. On crée UN moteur de conception sans écran : il dessine le toit, compte les panneaux, vérifie l'électrique,
   calcule la production et l'économie. Il vit dans le socle commun (`core/conception`), à côté des trois moteurs
   qui y sont déjà (calepinage, électrique, pompage).
2. Le CRM ne calcule plus rien lui-même : il garde la fiche (factures, toit tracé, GPS, photos, visite) et ses boutons.
3. Depuis le lead, un bouton « Devis rapide » appelle ce moteur : adresse ou facture → devis prêt, sans ouvrir l'atelier.
4. Ce devis rapide crée la MÊME conception que l'atelier ouvrira plus tard (marquée « rapide — à vérifier sur place ») :
   il n'y a jamais deux dessins pour un même lead.
5. L'atelier calepinage devient un écran posé sur le même moteur : il déplace les panneaux, le moteur donne les chiffres.
6. Chaque chiffre (kWc, production, économie, verdict électrique) a UN seul calcul ; la carte de l'atelier, le
   document, le devis et le PDF montrent la même valeur, ou disent l'écart et pourquoi (étude technique ≠ chiffre client).
7. Le chiffre que voit le client reste celui du moteur de devis (votre décision D-ACAL-6) : il passe seulement à
   l'intérieur du moteur partagé et lit enfin la pose réelle (est-ouest, toit + sol).
8. Le simulateur du site public reste une estimation affichée comme telle ; il n'écrit jamais un chiffre dans un devis.
9. On y va par petites marches : d'abord des tests qui sonnent quand deux écrans se contredisent, puis on branche
   chaque chiffre un par un, l'ancien chemin gardé derrière un interrupteur jusqu'à la preuve.
10. Les devis déjà envoyés ne bougent pas ; seuls les nouveaux PDF changent, et seulement là où ils étaient faux.

---

## 1. Carte des doublons (quantité → implémentations → source de vérité aujourd'hui)

Légende « client » : **oui** = imprimé sur le PDF `/proposal` ou la page client ; **écran** = vu par la commerciale
seulement ; **public** = site taqinor.ma.

### 1.1 Géométrie du toit (contour, pente, face)
| Implémentation | Où ça se voit | Client |
|---|---|---|
| `backend/django_core/apps/crm/roof_detect.py::fetch_building_footprint` (OSM Overpass) via `crm/roof_views.py::lead_roof_footprint` | fiche lead, atelier (repère) | écran |
| `Lead.roof_outline` tracé par le visiteur, rendu par `FCRM/workspace/traceToit.js` | fiche lead | écran |
| `VD/geometrie.py::zone_toit_depuis_contour`, `aire_contour_m2`, `aire_du_pan` | devis automatique | oui (via le compte) |
| `VD/geometrie.py::orientation_du_pan` (pente/face lues pour le devis) | `etude_params.toiture.pans`, PDF | **oui** |
| `RP/zones.ts::panVierge` et `apps/web/src/scripts/roof-tool-pro11.ts` (22° / 180° de départ) | atelier | écran |
| `core/calepinage/geo.py` (projection unique, ACAL281) ; `SV/repere.py` | moteur serveur | — |
| `backend/django_core/apps/ventes/calepinage_options.py::anneau_enu`, `obstacles_enu` (repère local refait) | dessins par option, page client | oui |
**Source de vérité** : le document `Calepinage.roof_layout` (D-ACAL-1) dès qu'il existe ; avant, `Lead.roof_outline` +
la zone posée par `zone_toit_depuis_contour`. **Divergence prouvée** : pose est-ouest 15° décrite « 22° Sud » par
`orientation_du_pan` → PDF 111 420 kWh/an contre 98 574 dans le document (rejeu S1-005, `T1/rejeu.md`) ; rangées au sol
« 180 = sud » lues face 270° (REJEU-NEW-1).

### 1.2 Nombre de panneaux et disposition
| Implémentation | Où | Client |
|---|---|---|
| `RP/optimizer.ts` (`liveResolveFlat`/pentes), `RP/layoutEditor.ts` — le dessin de l'atelier | atelier ERP | via devis |
| `WL/estimatorBrainV3..V8.ts`, `WL/roofPro2.ts` (pavage, pas de rangée) | site public + atelier | public |
| `core/calepinage/*` (`optimum.py`, `moteur.py`) via `apps/calepinage/villa_service.py::calepiner_surface` | `SV/contenance.py` (assistant), compte A/B | écran |
| `VD/geometrie.py::compte_moteur_du_layout` / `arbitrer_compte_calepinage` (drapeau `USE_MOTEUR_CALEPINAGE`, défaut OFF, `erp_agentique/settings/base.py` l.1714) | devis | oui si levé |
| `VD/geometrie.py::plafond_physique_du_contour` (aire ÷ aire panneau) | devis automatique | oui |
| `backend/django_core/apps/ventes/calepinage_options.py::_Trame`, `capacite_du_layout`, `layout_derive` (prolonge/retire des rangées) | dessin de chaque option Éco/Recommandé/Max | **oui** |
| `VD/taille.py::_panneaux_dimensionnement_horaire` (compte depuis la facture) | devis automatique | **oui** |
| `VD/geometrie.py::pans_du_document` (lecture du compte) | composition du devis | **oui** |
**Source de vérité** : « le calepinage dessiné fait foi » (`SV/contenance.py::FIN_LIBELLE`) — le dessin du navigateur ;
le moteur serveur n'est qu'estimation ou arbitre éteint. **Divergence prouvée** : toit + champ au sol additionnés sans
question, 218 modules (F1-030) ; 400 = 224 + 176 pour un besoin de ~50 kWc.

### 1.3 Choix du module et de l'onduleur
| Implémentation | Où | Client |
|---|---|---|
| `WL/roofPro2.ts::PANEL2_WATT` = 720 (module par défaut de l'atelier, hors catalogue) | atelier | écran |
| `FV/solar.js::PANEL_W_DEFAUT` = 710 | générateur | via devis |
| `VD/composition.py` (premier 710 W du catalogue) ; `VD/geometrie.py::_panneau_pour_calepinage` | devis | **oui** |
| `SV/electrique.py` (`resoudre_materiel`) ; `backend/django_core/apps/ventes/solar_design.py::match_inverter` ; `moteur_ci/composition.py` | électrique atelier / devis / C&I | oui (lignes) |
**Source de vérité** : les lignes du devis (D-ACAL-10). **Divergence prouvée** : 72 kWc / 720 W à l'écran contre 71 kWc
« 100 × 710 W Canadian » au PDF, module jamais choisi (S1-018).

### 1.4 kWc
`RP` `geometry.kwc` (n × 720) · `FV/solar.js::kwcPourPanneaux` · `VD/pipeline.py` (`poser_puissance_kwc`, QJR63, sur les
lignes) · `SV/chaines.py::bloc_pose` (kWc du stock ou de `modules[].pmaxWc`) · `QE/builder.py::panneaux_et_watt_lu`.
**Source** : lignes du devis. **Divergence** : 72 vs 71 (S1-018) ; kWc du champ au sol `null` (`RP/zones.ts::renderAreasPanel
→ computeSiteStats` sans `moduleFor`, F1-029). Garde de nuit existante : `ventes/coherence/regles_calepinage.py`
règles `CAL_KWC_DEVIS_VS_CALEPINAGE`, `CAL_MODULES_DEVIS_VS_CALEPINAGE`.

### 1.5 Production annuelle — **6 calculs, 3 chiffres différents sur un même projet**
| Implémentation | Où | Client |
|---|---|---|
| `RP/optimizer.ts::renderLiveWinner` (écrête DC/AC) | carte « Recommandation » | écran |
| `RP/zones.ts::liveActiveResult` (n'écrête pas) → `layout.result.annualKwh` enregistré | Total, document | écran |
| table navigateur `WL/productionEngine.ts::fallbackPerKwc` — l'atelier ERP n'a AUCUN rendement serveur : `FC/atelier/useAtelierBoot.js` pose `rendementPvgis: null` (l.255, 392) et `productionAtelierErp = () => fallbackPerKwc()` | atelier ERP | écran |
| `WL/estimatorBrainV2.ts::specificYieldPvgis14`, `apps/web/src/pages/api/roof-yield.ts`, `roof-production.ts` (« × 0,72 kWc Canadian 720 W »), `roof-estimate.ts` | site public | public |
| `FV/solar.js::productibleForCity` + `GHI` (miroir de `QE/constants.py`, garde `test_dc9_ghi_parity.py`) | aperçu du générateur | écran |
| `QE/pricing.py::calculate_savings_roi` : `kWc × productible × PRODUCTION_DERATE` en repli, sinon `_lire_etude_horaire` ← `backend/django_core/apps/ventes/etude_horaire.py::calculer_etude_horaire` / `jours_types_annee` | **PDF /proposal** | **oui** |
| `backend/django_core/apps/ventes/etude.py::run_bankable_study` / `_zone_base_production` (PVGIS par zone) | étude bancable | oui (C&I) |
| `VD/etude_schema.py::cles_etude_du_layout` (l.496 : `production_annuelle = layout.result.annualKwh`) et `QE/builder.py` l.1429 | `etude_params` → page client | **oui** |
| `SV/simulation.py::simuler_calepinage` + `SV/chaine_pertes.py` (24 postes, par pan) | onglet Production (étude technique) | écran |
**Source de vérité** : pour le client, le moteur de devis (D-ACAL-6) ; mais `etude_params.production_annuelle` reçoit
le chiffre du NAVIGATEUR (`etude_schema.py` l.496) et le PDF le sien (`pricing.py`). **Divergence prouvée** : 93 504
(carte) / 98 574 (Total + document) / 111 420 (PDF) kWh/an (S1-005) ; même devis : 40 424 (zone seule) contre 154,78
kWc (zone + sol) (REJEU-NEW-2).

### 1.6 Ombrage
`RP/shadingUi.ts` + `WL/shadingEngine.ts` (navigateur) · `SV/chaine_pertes.py`, `SV/rapport_ombrage.py`,
`SV/ombrage_chaines.py` · `backend/django_core/apps/ventes/etude.py::_ombrage_du_calepinage` / `_zone_shading` (lit
`apps.calepinage.selectors.ombrage_servi`) · `calepinage_options.py::_ombrage_mesure`. **Source** : l'ombrage servi
par le calepinage, déjà branché sur le devis (lecture par sélecteur). Pas de divergence prouvée au tour 1.

### 1.7 Autoconsommation
`FV/calc/roi.js::AUTOCONSO_SANS` 0,60 / `AUTOCONSO_AVEC` 0,85 (forfaits) · `QE/pricing.py::autoconso_avec_ratio`
(forfait de repli) · `etude_horaire.py` (heure par heure) · `etude.py::_hourly_flows` · `VD/etude_ci.py` (C&I, D-CIQ-1) ·
`SV/autoconsommation.py`, `SV/batterie.py` · `RP/consumptionMarkup.ts`. **Source** : modèle horaire du devis.

### 1.8 Économie et retour sur investissement — **10 appelants navigateur contre 1 serveur**
`WL/estimatorBrainV2.ts::annualSavingsMad` (10 appelants : V2-V8, `billEstimate.ts`, `applianceConsumption.ts` —
`K-GRANDEUR-UNIQUE.md`) · `FV/calc/roi.js::computeROI` / `computeCashflowPayback` · `QE/pricing.py::calculate_savings_roi`
/ `compute_cashflow_payback` · `backend/django_core/apps/ventes/economie.py::economie_pour_devis` / `_donnees_du_devis`
(TRI) · `economie_ci.py`, `economie_pompage.py` · `backend/django_core/apps/ventes/dimensionnement.py::_payback`.
**Divergence prouvée** : 0 MAD sur la carte de l'atelier contre TRI 31,64 % / retour 4 ans (S1-017) ; facture 900 MAD →
0 MAD car `FC/atelier/contexteAtelier.js::contexteCalepinageVersPayload` ne passe que le nombre de panneaux (S1-023).

### 1.9 Verdict électrique — **un moteur, trois adaptateurs, trois verdicts**
Moteur unique `core/electrique` (pur, PV33). Adaptateurs : `backend/django_core/apps/ventes/electrical_service.py`
(conception électrique du devis, PV41) · `SV/electrique.py::_rapport_publication` (atelier, ne compte pas
`NON_VERIFIABLE` → « Publiable » à vide, F1-010/S1-020) · `SV/assistant.py::_bloc_electrique` · `FC/BoutonDevis.jsx`
(« indetermine »). Second calcul de chaînes : `backend/django_core/apps/ventes/solar_design.py::string_design` (FG246,
appelé par `SV/chaines.py`, `ventes/compatibilites.py`, `VD/catalogue.py`). Phases : `SV/raccordement.py` contre
`FC/electrique/SaisiesElectriques.jsx` (F1-013). Garde existante `apps/calepinage/tests/test_acal_verdict_unique.py`.

### 1.10 Facture → taille cible
`backend/django_core/apps/crm/devis_auto.py::champs_requis` (gating, propriétaire lead) · `FV/calc/tarifs.js::kwhFromBill`,
`consoAnnuelleDepuisFactures` · `QE/pricing.py::kwh_from_bill` · `apps/parametres/tariff.py::kwh_depuis_facture` (lu par
`SV/consommation.py::publier_kwh`) · `backend/django_core/apps/ventes/dimensionnement.py::recommander_taille` + balayage
adaptatif (`balayage_adaptatif.py`, décision du 23/10) · `VD/taille.py` · `WL/billEstimate.ts`, `estimatorBrainV2`
(`billToAnnualKwh`). **Source** : `recommander_taille` (serveur). **Divergence prouvée** : la facture du lead n'atteint
pas l'atelier (S1-023) ; « Effacer » ramène 60 panneaux au lieu de 4 (S1-024).

### 1.11 Pompage — déjà fait
`core/pompage` unique (AGR109), lu par `VD/pompage.py` et `SV/pompage.py` ; moteur JS retiré de `solar.js`
(`debitAtHmt` n'y existe plus que dans un commentaire de `frontend/src/features/stock/catalogue.js` l.198). **C'est le
précédent à suivre**, avec CIQ128 (« Supprimer le moteur C&I JS de `solar.js` (aucun second moteur) », `docs/PLAN.md`
l.1022, coché).

### 1.12 Documents
PDF client : `/proposal` seul (règle #4) — rend `etude_params` + `pricing.py`. Pièces techniques : `SV/planche.py`,
`SV/export_dxf.py`, `SV/plan_cablage` — dessinées d'une géométrie sans orientation de module (F1-020, F1-031). Deux
`design-context` : `backend/django_core/apps/calepinage/views/calepinages.py::design_context` (l.1051) et
`backend/django_core/apps/ventes/views/devis_calepinage.py::design_context` (l.343).

### 1.13 Couplages qui contraignent la réponse
- Hors tests, `apps/ventes` importe `apps.calepinage` dans **18 fichiers** et `apps/calepinage` importe `apps.ventes` dans
  **36** (aucun import de modèles, seulement sélecteurs/services) : les deux apps se tiennent déjà dans les deux sens.
- `.importlinter` : `calepinage-est-un-noyau-pur`, `electrique-est-un-noyau-pur` (interdit `core.calepinage`),
  `pompage-est-un-noyau-pur` (interdit `apps` et `core.calepinage`), `core-foundation-is-a-base-layer` (le socle
  n'importe aucune app). Leur commentaire donne la règle de placement : un moteur partagé par deux consommateurs qui
  ne doivent pas s'importer vit en fondation, et paie cela par sa PURETÉ (AOF33, PV33, AGR109).
- Propriétaires (`python scripts/check_ownership.py --owner-of`, lancé ici) : `core/calepinage/**`, `core/electrique/**`,
  `VD/geometrie.py`, `ventes/calepinage_options.py`, `ventes/electrical_service.py`, `RP/*`, `WL/roofPro2.ts`,
  `WL/productionEngine.ts`, `WL/estimatorBrainV8.ts` → **calepinage** ; `QE/pricing.py`, `QE/builder.py`,
  `etude_horaire.py`, `economie.py`, `offres_tailles.py`, `dimensionnement.py`, `solar_design.py`, `ventes/coherence/*` →
  **moteur** ; `VD/pipeline.py`, `VD/etude_schema.py`, `VD/creation_auto*.py`, `VD/taille.py`, `etude.py`, `core/pompage/**`
  → **devis** ; `crm/devis_auto.py`, `FCRM/workspace/*` → **lead** ; `FV/solar.js`, `FV/calc/*`, `DevisGenerator.jsx` →
  **generateur** ; `WL/estimatorBrainV2.ts`, `estimatorBrainCommun.ts` → **web** ; `.importlinter`, `settings/base.py` →
  **deploy**. **Un dossier neuf `core/conception/**` retombe aujourd'hui sur le résiduel `securite`** (vérifié) — il
  faut une ligne dans `docs/ownership.yml` AVANT tout code.

---

## 2. Ce que fait le marché (fait rapide depuis le lead, conception complète)

- **Reonic** : « Quick planning » est un mode de la MÊME fiche système du MÊME projet, « the shortcut alongside 2D and 3D
  planning » ; il saute l'éditeur 3D ET le calcul de rendement (aucune production, autoconsommation ni économie au devis
  rapide) ; la page suggère de passer en 3D une fois le client engagé « to lock the exact count » ; aucune conversion
  automatique décrite. https://docs.reonic.com/docs/en/offers-plan-pv-quick-planning (lu ici).
- **Aurora** : Sales Mode et Design Mode présentés comme UN modèle partagé, production « instantly updated with every design
  change » ; note d'août 2023 : réglages panneaux « applied consistently » entre Design/Sales Mode et AutoDesigner/manuel
  (affirmations de l'éditeur, non testées). https://aurorasolar.com/sales-mode ,
  https://help.aurorasolar.com/hc/en-us/articles/21424655782035-August-2023-Release-Notes
- **Scanifly SimpleDesign** : « a stripped down view of our design and engineering software », une interface sur
  PrelimDesign/DroneDesign, avec comparaison préliminaire ↔ drone « like an automatic true-up » ; la page ne dit pas
  comment l'écart est réglé, seulement « Communicate necessary changes with customers transparently ».
  https://scanifly.com/blog/introducing-simpledesign/ (lu ici).
- **OpenSolar** : Auto Design (Ada, « Max Offset » / « Max Fit ») crée des systèmes DANS le studio, modifiables ensuite
  « like normal », qui alimentent la proposition (https://www.opensolar.com/auto-design/). **Correction du banc B6-R35** :
  le « Quick Quote » de la 3.9 sert aux travaux NON solaires (« jobs that don't need a solar design ») — ce n'est pas
  une passerelle devis rapide → atelier (https://www.opensolar.com/product-updates/release-3-9/, lu ici).
- **Pylon / Eturnity** : proposition « en moins de 2 minutes » chez Pylon par conception 2D + modèle de proposition dans
  le MÊME fichier (revue tierce https://www.heavengreenenergy.com/blog/pylon-review) ; Eturnity : lead → projet → 3D →
  offre, liste de pièces reprise sans ressaisie (pages éditeur) — aucun ne documente deux moteurs.
- **Ce qui casse quand les deux chiffres divergent** : la proposition garde sa page financière pendant que le dessin
  change (« A new date on the proposal does not prove the annual energy was recalculated »,
  https://www.surgepv.com/blog/6-ways-the-proposal-can-drift-from-what-the-customer-saw-on-site) ; une confiance perdue
  ne revient parfois pas (https://www.financialcontent.com/article/sbtrendsetters-2026-9-9-the-true-cost-of-manual-solar-design-and-proposal-generation-errors) ;
  au forum, quatre devis pour le même toit à 7° se contredisent (B5-forums-anglais l.929) ; plan de chaînes et plan de
  câbles en désaccord après une retouche (B5-forums-anglais l.855, PV*SOL). Sources éditeur : à lire comme des points de vue.

**Conclusion du marché (5 lignes)** : personne de documenté ne fait tourner deux moteurs. Le schéma dominant est UN
modèle de projet + UN moteur, avec deux SURFACES (vendeur rapide / ingénieur complet). Le « rapide » honnête est soit
sans chiffre de production (Reonic), soit le même calcul sur une conception automatique (Aurora, OpenSolar, Scanifly).
Le passage rapide → complet se fait dans le MÊME projet, et l'écart est « communiqué », jamais caché. Le défaut cité
par les installateurs est exactement le nôtre : un chiffre de proposition qui n'a pas suivi le dessin.

---

## 3. Les options comparées

### (A) Statu quo + tests de réconciliation
- *Commerciale* : inchangé (« Devis automatique » du lead, `VD/creation_auto.py::build_devis_auto` ; ou générateur).
- *Calcul par grandeur* : 6 productions, 4 économies, 3 verdicts restent ; les tests ne font que SONNER.
- *Règles* : rien ne casse. *Coût* : faible. *Risque* : chaque nouvelle fonction doit être faite 2 à 4 fois (le défaut
  720/710 en est l'exemple ; CIQ128 et AGR132 ont dû retirer deux moteurs JS déjà construits).
- *Chiffres client* : aucun changement.
- **Perd** comme cible : 14 divergences sur 14 rejouées en un seul tour ; les tests sont nécessaires mais ce sont la
  marche 2 de (C), pas une architecture.

### (B) Tout passe dans l'app calepinage ; CRM et devis l'embarquent
- *Commerciale* : pour chiffrer il faut ouvrir l'atelier (carte MapLibre, clé MapTiler — `T1/B1.md` : l'atelier ne
  démarre pas sans elle) — exactement ce que Reda refuse.
- *Règles* : le cœur `ventes` dépendrait encore plus d'un satellite ; le moteur de devis (`QE`, propriétaire moteur,
  règle #4) ne peut pas déménager dans calepinage ; les 36 + 18 imports croisés grossissent.
- *Coût* : très élevé (déménager `etude_horaire`, `pricing`, `dimensionnement`). *Chiffres client* : tous rebasculent.
- **Perd** : contredit la demande (« without having to open calepinage ») et le placement par propriétaire.

### (C) Un moteur de conception sans écran, appelé par un chemin rapide (CRM / devis) et par l'atelier
- *Commerciale* : depuis le lead, « Devis rapide » → le moteur conçoit (adresse/OSM ou toit tracé → remplissage ;
  facture → taille) → devis ; rien à ouvrir.
- *Calcul par grandeur* : une fonction chacune, dans le moteur (§ 4).
- *Règles* : se range dans le patron déjà écrit dans `.importlinter` (moteur pur en fondation, deux consommateurs) ;
  règle #4 intacte (le moteur calcule, `/proposal` rend) ; D-ACAL-1 tenue (le rapide crée LE calepinage du lead) ;
  D-ACAL-6 tenue (la production client reste celle du moteur de devis — elle change d'adresse, pas de propriétaire).
- *Coût* : élevé mais découpable (strangler, § 6). *Risque* : déplacer des calculs propriétaires « moteur » qui
  impriment des chiffres client → chaque marche est byte-identique sur les goldens, sauf corrections nommées.
- *Chiffres client* : ne changent QUE là où ils sont faux aujourd'hui (E-O, toit + sol), sur les nouveaux rendus.

### (D) Variantes étudiées
- **D1 — le moteur TypeScript du navigateur devient l'unique moteur, le serveur le rejoue en Node.** Écartée : le PDF
  (règle #4) et le modèle horaire/tarifs sont en Python ; il faudrait un runtime Node sur le serveur (nouvelle
  dépendance d'infrastructure) et réécrire le modèle horaire en TS.
- **D2 — le moteur vit dans l'app ventes.** Écartée : l'atelier (calepinage) en dépendrait, alors que la géométrie et
  l'électrique sont déjà en fondation ; on remet du calcul dans une app au lieu du socle pur testable sans base.
- **D3 = (C) avec façade d'abord (retenue).** Le moteur pur `core/conception` est la cible ; on l'atteint par une
  FAÇADE unique côté app (`SV/conception.py::concevoir`) qui délègue d'abord aux fonctions d'aujourd'hui sans changer un
  chiffre, puis chaque grandeur est déplacée derrière elle. C'est (C) rendu livrable marche par marche.

---

## 4. L'architecture cible (une seule)

### 4.1 Le propriétaire unique de chaque grandeur
| Grandeur | Seul calcul (cible) | Propriétaire fichier | Remplace |
|---|---|---|---|
| Géométrie posée (pans, pente/face POSÉES, surfaces au sol) | `core/conception/geometrie.py::pans_poses(document)` | calepinage | `VD/geometrie.py::orientation_du_pan`, `pans_du_document`, `zone_toit_depuis_contour`, `aire_contour_m2`, `calepinage_options.anneau_enu` |
| Remplissage automatique (nombre, disposition) | `core.calepinage` (existant) appelé par `core/conception/pose.py::remplir` | calepinage | `RP/optimizer.ts` (remplissage), `WL/estimatorBrainV7/V8` côté ERP, `plafond_physique_du_contour`, `calepinage_options._Trame` |
| Compte d'un dessin | compter le document (`pans_poses`) — le dessin fait foi | calepinage | — |
| Module / onduleur de départ | entrée du moteur, résolue une fois du catalogue société (`modules-disponibles`), D-ACAL-10 | calepinage | `WL/roofPro2.ts::PANEL2_WATT` en ERP, `FV/solar.js::PANEL_W_DEFAUT` |
| kWc | `core/conception::kwc(pans, modules)` | calepinage | `geometry.kwc` 720, `kwcPourPanneaux`, `SV/chaines.py::bloc_pose` (lecture) |
| Électrique (chaînes, verdict 3 états, phases) | `core.electrique.concevoir` (existant) par UN adaptateur `SV/conception.py` | calepinage | `ventes/electrical_service.py`, `SV/electrique.py::_rapport_publication`, `SV/assistant.py::_bloc_electrique`, `ventes/solar_design.py::string_design` |
| Production CLIENT (« commerciale ») | `core/conception/production.py::production_commerciale` — le modèle horaire du devis, déplacé, nourri par les pans POSÉS | **moteur** | `pricing.py` (production), `etude_horaire.py` (production), `etude_schema.py` l.496 (copie du navigateur), `RP` cartes, `fallbackPerKwc` en ERP, `solar.js::productibleForCity` (aperçu) |
| Étude technique (P50/P90, 24 pertes) | `SV/simulation.py` + `chaine_pertes.py` (inchangés) — écart nommé au chiffre client (D-ACAL-6, `BandeauProvenanceProduction.jsx::EcartDevis`) | calepinage | — |
| Ombrage | document calepinage → `selectors.ombrage_servi` (existant), entrée du moteur | calepinage | `calepinage_options._ombrage_mesure` |
| Autoconsommation + économie + retour | `core/conception/economie.py` (barème, flux horaires, retour) — déplacé de `pricing.py` | **moteur** | `annualSavingsMad` en ERP, `FV/calc/roi.js::computeROI`, forfaits 0,60/0,85 (gardés seulement comme repli ÉTIQUETÉ) |
| TRI, prêt, amortissement | `ventes/economie.py` (inchangé) lit l'économie année 1 du moteur | moteur | — |
| Facture → taille cible | `ventes/dimensionnement.py::recommander_taille` (inchangé, appelé par le moteur) | moteur | `FV/calc/tarifs.js::kwhFromBill` (affichage seulement), `contexteCalepinageVersPayload` (nombre seul) |
| Pompage | `core.pompage` (déjà unique) | devis | — |
| Documents | `/proposal` rend `etude_params` écrit UNE fois par `VD/pipeline.py` depuis la conception ; planche/DXF depuis `pans_poses` | moteur / calepinage | — |

### 4.2 Ce qui reste au CRM, ce qui bouge, ce qui devient commun
- **Reste au CRM (propriétaire lead)** : la fiche et ses SAISIES (factures, profil énergie, `roof_outline`, GPS,
  photos de facture `crm/intake_photo.py`, visite), le gating « devis automatique prêt » (`crm/devis_auto.py`, source de
  vérité serveur unique déjà), les boutons, l'affichage des chiffres SERVIS. Le CRM ne calcule rien.
- **Reste dans `crm` mais change d'appelant** : `crm/roof_detect.py` (emprise OSM) devient une ENTRÉE lue par
  l'adaptateur du moteur (lecture par `crm.selectors`, jamais un import de vue).
- **Bouge** : le calcul (pas les écrans) — vers `core/conception` (§ 4.1). Les twins listés en colonne « Remplace » meurent
  après preuve de parité.
- **Devient commun** : `core/conception/` (paquet NEUF, pur, sans écran) — « le module caché ». Il peut vivre là parce
  que : (1) le socle est la place que `.importlinter` donne à un moteur partagé par deux consommateurs (AOF33/PV33/AGR109) ;
  (2) il n'importe que `core.calepinage`, `core.electrique`, `core.pompage` et la stdlib/numpy — les contrats existants
  interdisent ces imports DEPUIS les trois noyaux, pas VERS eux ; (3) il reste pur : la météo PVGIS, le catalogue, la
  facture, les barèmes lui sont PASSÉS par l'adaptateur. Nouveau contrat `conception-est-un-noyau-pur` (interdit Django,
  `apps`, `authentication`, les modules Django de `core`) + test AST, et les trois noyaux reçoivent `core.conception`
  dans leurs interdits (pas de cycle).
- **L'adaptateur (les entrées/sorties)** : `SV/conception.py` (propriétaire calepinage) construit l'entrée depuis un
  lead, un calepinage ou un devis (PVGIS via les clients et caches existants, `stock.selectors`, `crm.selectors`,
  `parametres`), appelle le moteur, et rend UN objet `Conception` au contrat `contract_samples/conception.json`. Le cœur
  `ventes` l'appelle comme il appelle déjà `apps.calepinage.services` (7 fichiers le font).

### 4.3 Les estimateurs du navigateur
- **Site public** (`WL/estimatorBrainV2..V8`, `roofPro2`, `productionEngine`, `pages/api/roof-*`) : restent des
  ESTIMATIONS (« JAMAIS un devis : une fourchette », en-tête de `roofPro2.ts`), étiquetées comme telles. Ce qu'ils
  envoient au lead est de la GÉOMÉTRIE (contour, panneaux posés), jamais un chiffre repris par un devis. Une garde
  compare leur production et leur économie au moteur sur les goldens, avec un écart maximal publié (pour que le site ne
  promette pas 20 % de plus que le devis).
- **Atelier ERP** (`RP` en mode calepinage) : le navigateur garde le DESSIN (glisser, retirer, tracer : instantané) ; les
  CHIFFRES viennent du serveur : à chaque geste posé (anti-rebond), `POST calepinages/<pk>/conception/chiffrer/` rend kWc,
  production commerciale, économie, verdict. Pendant l'attente la carte dit « calcul… », jamais un nombre de table. Hors
  ligne : le dernier chiffre servi, marqué « à recalculer ». `fallbackPerKwc` disparaît du mode ERP.
- **Générateur `/ventes/devis/nouveau`** : il montre déjà des valeurs signées « moteur » (`useSizingMoteur`,
  `useEtudeHorairePreview` dans `pages/ventes/generator/hooks/useApercuEtude.js`) à côté d'« aperçu » navigateur
  (`computeROI`, `productibleForCity`) ; l'aperçu résidentiel navigateur est retiré comme CIQ128 l'a fait pour le C&I.

### 4.4 Rapide et atelier restent UNE conception (D-ACAL-1, D-ACAL-12)
- « Devis rapide » depuis le lead → `SV/conception.py::concevoir_rapide_pour_lead(lead)` :
  1. adopte le calepinage OUVERT du lead s'il existe (`SV/creation.py::adopter_ou_creer_pour_devis`, D-ACAL-12), sinon en
     crée un, avec `etat_conception = 'rapide'` ;
  2. géométrie : contour tracé par le client, sinon emprise OSM, sinon aucune (devis « toit non tracé », compte par la
     seule facture — comportement d'aujourd'hui) ;
  3. remplissage : `core.calepinage` avec la politique de pas de l'atelier (`SV/traduction.py::politique_de_pose`, comme
     `SV/contenance.py`), borné par `recommander_taille` ;
  4. électrique, production, économie : le moteur ;
  5. le devis est produit par la porte unique existante `SV/devis.py::generer_devis` (ACAL108) — donc avec ses gardes
     (feu vert, garde électrique, et la garde de taille de D7-05).
- L'atelier ouvre CE document ; le premier enregistrement le fait passer à `complet` ; l'empreinte imprimée (D-ACAL-4)
  rend le devis « périmé » si le dessin change — le circuit existant, sans rien inventer.

### 4.5 Le schéma cible
```
            SAISIES (restent chez leur propriétaire)                         SURFACES (minces)
  ┌──────────────────────────────────────────────┐        ┌───────────────────────────────────────────┐
  │ CRM lead : factures, roof_outline, GPS, OSM, │        │ CRM fiche lead : « Devis rapide »,         │
  │ photos, visite (apps/crm, apps/visites)      │        │   chiffres servis (IdentityRail, DevisTab) │
  │ Catalogue (stock.selectors) · Barèmes        │        │ Générateur /ventes/devis/nouveau          │
  │ (parametres) · Météo PVGIS (caches existants)│        │ Atelier calepinage (dessin navigateur RP) │
  └───────────────────────┬──────────────────────┘        │ Assistant (contenance, copilote)          │
                          │ lectures selectors            └───────────────────┬───────────────────────┘
                          ▼                                                    │ appels services
  ┌───────────────────────────────────────────────────────────────────────────▼───────────────────────┐
  │ ADAPTATEUR  apps/calepinage/services/conception.py  (I/O, multi-société, contrat conception.json) │
  │   concevoir(calepinage) · concevoir_rapide_pour_lead(lead) · chiffrer(document)                   │
  └───────────────────────────────────────────────┬───────────────────────────────────────────────────┘
                                                  │ entrée canonique (données pures)
  ┌───────────────────────────────────────────────▼───────────────────────────────────────────────────┐
  │ MOTEUR PUR  core/conception  (« le module caché » — aucun écran, aucun Django, aucune I/O)        │
  │   geometrie.pans_poses → pose.remplir ─► core.calepinage                                          │
  │                        → electrique   ─► core.electrique      → pompage ─► core.pompage            │
  │                        → production.production_commerciale (moteur) → economie (moteur)           │
  │                        → controles (taille, verdict 3 états, écarts nommés)                       │
  └───────────────────────────────────────────────┬───────────────────────────────────────────────────┘
                                                  │ UN objet Conception
              ┌───────────────────────────────────┼────────────────────────────────┐
              ▼                                   ▼                                ▼
  Calepinage.roof_layout + resultat     VD/pipeline.py écrit etude_params    ventes/coherence (nuit)
  (le seul dessin, D-ACAL-1)            UNE fois → /proposal rend (règle #4)  gardes « une grandeur,
  étude technique SV/simulation.py      (devis envoyé : figé)                  une valeur »
  (écart nommé, D-ACAL-6)
  Site public apps/web : estimateurs = ESTIMATION étiquetée, ne nourrissent jamais un devis (garde d'écart).
```

---

## 5. Ce que la commerciale fait, dans chaque option, pour chiffrer un lead sans ouvrir l'atelier
| Option | Gestes | Le devis porte-t-il un dessin ? | Chiffres concordants ? |
|---|---|---|---|
| A | « Devis automatique » (aujourd'hui) | une zone tracée ou rien ; l'atelier la reprend ensuite | non (6 productions) |
| B | ouvrir l'atelier, tracer, générer | oui | oui, mais au prix de l'atelier |
| **C** | « Devis rapide » (1 clic, sur un lead « prêt ») | oui, le MÊME calepinage, état « rapide » | oui par construction ; écart technique nommé |

---

## 6. Ordre de migration (étrangleur — chaque marche livrable seule, l'ancien chemin gardé derrière un interrupteur)
1. **M0 — Contrat SEUL sur `main`** (PACT10) : `apps/calepinage/contract_samples/conception.json` (entrée + sortie, chaque
   grandeur `{valeur, unite, source, etat}`), ligne `core/conception/**` dans `docs/ownership.yml`, contrat import-linter
   `conception-est-un-noyau-pur` et paquet vide + test de pureté. Aucun chiffre ne bouge. (CAP-D8-01)
2. **M1 — Gardes « une grandeur, une valeur »** sur les goldens ACAL382/383 : un test par grandeur (carte, Total,
   document, `etude_params`, PDF) avec tolérance PUBLIÉE ; prouvées ROUGES sur `da49cb55b` (S1-005, S1-018, S1-017,
   S1-020), puis vertes au fil des marches ; trois règles de nuit dans `ventes/coherence/regles_calepinage.py`.
   (CAP-D8-02, CAP-D8-03)
3. **M2 — Façade** `SV/conception.py::concevoir` qui DÉLÈGUE aux fonctions d'aujourd'hui, byte-identique ; les appelants
   passent par elle un par un (design-context, simuler, pipeline, devis automatique, assistant). (CAP-D8-04)
4. **M3 — Chaque grandeur derrière le moteur**, dans l'ordre des chiffres faux que voit le client : matériel + kWc
   (D7-02) → géométrie posée (D7-01 t2, D7-03, D7-04) → production commerciale (D7-01 t1/t3) → économie (S1-017/023,
   D7-06 t1) → verdict (D7-10) → remplissage serveur (drapeau `USE_MOTEUR_CALEPINAGE` levé société par société après le
   dry-run `comparer_compte_moteur_calepinage`) → dessins par option. Interrupteur par grandeur dans les réglages
   (`MOTEUR_CONCEPTION_<GRANDEUR>`, défaut OFF) jusqu'à parité sur les goldens ET 7 nuits sans alerte du correcteur.
   (CAP-D8-05 à D8-10)
5. **M4 — Chemin rapide CRM** : « Devis rapide » → calepinage `rapide` + devis ; « Affiner dans l'atelier » ouvre le même
   document ; ACAL421 (« Conception automatique » dans l'atelier) appelle la même fonction. (CAP-D8-11)
6. **M5 — Estimateurs publics étiquetés + garde d'écart** (CAP-D8-12), puis **retrait des jumeaux morts**, chacun après sa
   garde verte (CAP-D8-13).
Gate de chaque marche : goldens ACAL382/383 + `QE` `test_quote_engine.py` + `test_solar_differential.py` +
`audit_coherence` de nuit. Une marche qui change un chiffre client le NOMME dans sa tâche et monte le niveau de règles
(`VD/regles_calcul.py`, dry-run `regles_calcul_ecarts_dryrun`) — les devis envoyés gardent leur rendu (mémoire « devis
envoyés : nouveaux rendus seulement », 08/10).

---

## 7. Risques
- **Déplacer des calculs « moteur » qui impriment des chiffres** (production, économie) : risque n° 1. Parade : marche
  byte-identique d'abord (déplacement pur, goldens), correction ensuite, séparément, sous un niveau de règles.
- **Latence de l'atelier** : un aller-retour serveur par geste. Le dimensionnement mesuré en prod coûte 0,05-0,10 s par
  taille (mémoire dimensionnement 23/10) ; le chiffrage d'UNE conception n'a pas été mesuré ici → la marche CAP-D8-07
  pose un budget (≤ 500 ms au 95e centile) et garde l'interrupteur tant qu'il n'est pas tenu.
- **Hors ligne / téléphone** : le dernier chiffre servi reste affiché « à recalculer » ; jamais un nombre de table.
- **Couplage ventes ↔ calepinage** déjà bidirectionnel (18/36 fichiers) : la façade ne doit RIEN ajouter dans ce sens ;
  garde : un compte d'imports croisés qui ne monte pas (cliquet).
- **Six propriétaires touchés** (calepinage, moteur, devis, lead, generateur, web, + deploy pour `.importlinter`) : chaque
  tâche reste chez le sien (cartes D8) ; le contrat d'abord évite deux contrats inventés (PACT10/PACT11).
- **Périmètre de la campagne L5** : `/proposal`, le moteur de devis et l'argent sont HORS périmètre (contrat L5 § 5,
  rappelé en tête de D7) → les tâches moteur/devis sont routées vers les plans de leurs propriétaires.
- **Remplissage serveur ≠ remplissage navigateur** sur certains toits : le drapeau reste OFF société par société tant que
  le dry-run montre des écarts hors tolérance PVG2 (±2 modules ou ±5 %, `VD/geometrie.py::TOLERANCE_ARBITRAGE_*`).

---

## 8. À confirmer par Reda (SEULEMENT ce qui change un chiffre que voit le client ; aucune dépendance payante)
Aucune dépendance payante : OSM Overpass et PVGIS sont gratuits et déjà appelés ; aucun runtime nouveau ; la clé
MapTiler n'est pas requise par le chemin rapide.
1. **Nouveaux PDF des toits est-ouest et des projets toit + sol** : la production imprimée deviendra celle de la pose
   réelle (cas rejoué : le PDF disait 111 420 kWh/an pour un dessin à 98 574 ; la valeur corrigée exacte n'est pas
   calculée ici). Devis déjà envoyés inchangés.
2. **Devis automatiques depuis le lead** : le nombre de panneaux sera borné par le toit réellement rempli (contour du
   client ou emprise OSM) au lieu de la seule surface brute (`plafond_physique_du_contour`) — un petit toit peut donc
   recevoir moins de panneaux que la facture ne le demande, avec la phrase qui le dit.
Tout le reste (structure, propriétaires, ordre, interrupteurs, seuils) est tranché ici par la règle « le plus simple qui
tient les décisions D-ACAL ».

---

## 9. Non vérifié (dit tel quel)
- Que `etude_horaire.py` et la partie production/économie de `pricing.py` s'extraient en code pur sans Django : NON lu en
  entier (seulement signatures et l.1560-1760 de `pricing.py`) ; la marche CAP-D8-07 t1 commence par ce constat.
- Les chiffres corrigés des cas rejoués (111 420 → ?) : non calculés.
- Latence d'un chiffrage complet : non mesurée.
- Marché : les affirmations Aurora/Pylon/Eturnity sont des pages d'éditeur ; Reonic ne documente pas de conversion rapide
  → 3D ; Scanifly ne dit pas comment l'écart est réglé.
- Le détail de `FC/BoutonDevis.jsx`, `SV/electrique.py::_rapport_publication`, `RP/zones.ts::liveActiveResult` est repris
  du rejeu et de la consolidation (`T1/rejeu.md`, `T1/consolidation.md`), pas relu ici.
- Le compte « 10 appelants navigateur » d'`annualSavingsMad` vient de `T1/classes/K-GRANDEUR-UNIQUE.md` (grep sur
  `da49cb55b`), pas recompté sur `33c076d00`.

Fiches de construction : `backlog/D8-moteur-partage.md`.

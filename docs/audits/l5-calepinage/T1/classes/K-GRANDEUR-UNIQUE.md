# Fiche d'invariant — classe `K-GRANDEUR-UNIQUE` (une grandeur, un seul calcul)

- **Invariant** : « Pour une conception, chaque grandeur montrée (kWc, Wc unitaire, production annuelle, économie, verdict
  électrique, phases) a UNE fonction source ; l'atelier, les onglets, le devis et le PDF /proposal affichent la même valeur
  ou nomment l'écart et sa raison. »
- **Née de** : T1-S1-005 (P0), T1-S1-018 (P0), T1-F1-004, T1-F1-024, T1-S1-017, T1-S1-020, T1-F1-013, T1-F1-029,
  T1-S2-016, T1-F1-026 (à reproduire) ; rejeu : REJEU-NEW-2 (production de la zone seule, kWc zone + champ). Classe 1 du rejeu.
- **Où il peut être violé** — greps sur `da49cb55b` (lancés dans cette session) :
  - `git grep -n -E "720 W\`" da49cb55b -- apps/web/src/scripts` → 2 littéraux d'affichage ;
  - `git grep -n -E "liveActiveResult|clipDcAcKwh\(" da49cb55b -- apps/web/src/scripts/roofPro11` → l'écrêtage n'est que dans la carte ;
  - `git grep -n -E "def orientation_du_pan|def pans_du_document|def ecrire_etude_params" da49cb55b -- backend/django_core/apps/ventes/domain` ;
  - `git grep -n -E "verdict_publiable\(|'publiable'|indetermine" da49cb55b -- <electrique.py, devis.py, BoutonDevis.jsx, VerdictElectrique.jsx>` ;
  - `git grep -n -E "annualSavingsMad\(|calculate_savings_roi\(" da49cb55b -- apps/web/src backend/django_core/apps/ventes` → 10 appelants navigateur (V2-V8, billEstimate, applianceConsumption) contre 1 serveur.
  | Endroit | Viole aujourd'hui ? | Couvert par la garde ? |
  |---|---|---|
  | `apps/web/src/scripts/roofPro11/optimizer.ts::paintCard` (« N × 720 W ») | oui (F1-004) | non |
  | `apps/web/src/scripts/roofPro11/zones.ts::renderAreasPanel` (« N × 720 W », Total) | oui (F1-024) | non |
  | `optimizer.ts::renderLiveWinner` ≠ `zones.ts::liveActiveResult` (écrêtage DC/AC) | oui (S1-005) | non (ACAL480 = navigateur ↔ serveur, pas carte ↔ total) |
  | `apps/ventes/domain/geometrie.py::orientation_du_pan` (E-O décrit en 22° Sud au devis) | oui (S1-005, /proposal 111 420) | non |
  | `apps/web/src/lib/roofPro2.ts::PANEL2_WATT` (720) vs composition catalogue 710 W | oui (S1-018, /proposal) | non |
  | `apps/ventes/domain/pipeline.py::ecrire_etude_params` (production racine = toit seul) | oui (REJEU-NEW-2) | non |
  | `apps/web/src/lib/estimatorBrainV2.ts::annualSavingsMad` vs `apps/ventes/economie.py::_donnees_du_devis` | oui (S1-017) | non |
  | `services/electrique.py::_rapport_publication` vs `BoutonDevis.jsx` (indetermine) vs `services/assistant.py::_bloc_electrique` | oui (S1-020) | `tests/test_acal_verdict_unique.py` existe, ne couvre pas NON_VERIFIABLE |
  | `services/raccordement.py` phases vs `electrique/SaisiesElectriques.jsx` phases | oui (F1-013) | `tests/test_acal_raccordement_unique.py` existe — à étendre |
  | `zones.ts::renderAreasPanel → computeSiteStats` sans `moduleFor` (kWc du champ au sol null) | oui (F1-029) | non |
  | `atelier/PanneauPertes.jsx` (IAM en %) vs `parametres_cles.py::modele_iam` (modèle + b0) | probable (S2-016) | non |
- **Matrice champ × condition** (round 2 — chaque case `tient` / `casse (id)` / `n/a`) :
  | Grandeur | 1 pan Sud | pan E-O | module catalogue ≠ défaut | toit + champ au sol | sans facture | après Effacer | devis généré → /proposal |
  |---|---|---|---|---|---|---|---|
  | Wc unitaire affiché | casse (F1-004) | casse | casse (F1-004) | ? | tient | ? | tient (710) |
  | kWc | tient | tient | casse (S1-018) | casse (F1-029, REJEU-NEW-2) | tient | ? | casse (S1-018) |
  | production annuelle | casse (52 341 PDF vs 51 713) | casse (S1-005) | ? | casse (REJEU-NEW-2) | ? | ? | casse |
  | économie | ? | ? | ? | ? | casse (S1-017) | ? | n/a (PDF n'imprime pas) |
  | verdict électrique | casse (S1-020) | — | — | — | — | — | n/a |
- **Garde** : UNE famille — étendre les goldens d'ACAL382/ACAL383 (même document `roof_layout`) par un test « une grandeur,
  une valeur » qui lit la carte, le Total, le résumé API, `etude_params` et le PDF d'un même golden, une assertion par case
  de la matrice ; côté verdict, étendre `apps/calepinage/tests/test_acal_verdict_unique.py` à un calepinage sans matériel.
  Écrite par le rédacteur des tests premiers. Rouge attendu sur `da49cb55b` (cas S1-005/S1-018 rejoués) — NON exécuté ici.
- **Cible du tour suivant** : oui.
- **Propriétaire** : calepinage (`apps/web/src/scripts/roofPro11`, `apps/ventes/domain/geometrie.py`) ; devis
  (`apps/ventes/domain/pipeline.py`) ; moteur (`apps/ventes/economie.py`) ; web (`apps/web/src/lib/estimatorBrainV2.ts`,
  `roofPro2.ts::PANEL2_WATT`, partagés avec le site public).
- **Ce qu'elle ne couvre pas** : la justesse ABSOLUE d'un productible (F1-026 → ACAL474) ; seulement l'unicité.
- **Question de sortie** : « le système l'attraperait-il tout seul ? » — non aujourd'hui → tâches D7-01, D7-02, D7-05, D7-06.

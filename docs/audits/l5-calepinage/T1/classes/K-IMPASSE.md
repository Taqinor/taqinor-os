# Fiche d'invariant — classe `K-IMPASSE` (un message ne demande que ce qu'un écran permet)

- **Invariant** : « Tout message qui demande une saisie ou un geste (norme électrique, lestage, mode météo, hauteur
  d'obstacle, « Calculer l'ombrage », module à désigner) nomme un écran où ce geste EXISTE, et son lien ouvre ce champ. »
- **Née de** : T1-S2-001, T1-S2-002, T1-S2-010 (doublon), T1-F1-016, T1-F1-017, T1-F1-032, T1-F1-005, T1-F1-025, T1-S1-009,
  T1-S1-001, T1-S1-027, T1-S1-012, T1-S2-013, T1-S2-017.
- **Où il peut être violé** — grep sur `da49cb55b` :
  `git grep -n -E "'/calepinage/reglages'|to=\"/calepinage/reglages|/calepinage/reglages\b" da49cb55b -- frontend/src/features/calepinage frontend/src/pages`
  → 6 liens sans ancre : `Bibliotheque.jsx` (cal-biblio-lien-reglages), `atelier/PanneauMasseLestage.jsx::CHEMIN_REGLAGES`,
  `production/BandeauProvenanceProduction.jsx` (acal52-lien-reglages), `production/PanneauProduction.jsx` (calx48-lien-reglages),
  `DossiersReglementaires.jsx` (gabarits) ; cible `reglages/ReglagesSimulation.jsx` (aucune clé norme, lestage, dégagements).
  | Endroit | Viole ? | Garde ? |
  |---|---|---|
  | `services/norme.py::norme_applicable` « sélectionnez la norme dans les réglages du module » — aucun écran (champ `norme_electrique` écrivable par PATCH seulement, `views/parametres.py`) | oui (S2-001) | non ; ACAL397 suppose ce réglage |
  | `atelier/PanneauMasseLestage.jsx::CHEMIN_REGLAGES` → page sans lestage | oui (S2-002) | non |
  | `commun/Provenance.jsx` (Sources des paramètres, lecture seule) | oui (S2-010) | non |
  | `services/simulation.py::controler_meteo` — « tmy » proposé, refusé sans fichier | oui (F1-016) | non (ACAL454-456 = fichier déposé) |
  | `services/chaine_pertes.py::decision_meteo` — une clé par refus, lien sans ancre | oui (F1-017) | non |
  | `atelier/BuilderDom.jsx` — pas de `#rp9-heatmap-toggle` (« Calculer l'ombrage ») | oui (F1-032) | ACAL436 |
  | `atelier/BuilderDom.jsx` — pas de `#rp9-obs-height` (lu par `obstaclesUi.ts::obsHeightEl`) | oui (F1-005) | non |
  | `BoutonDevis.jsx` « Ouvrir le devis » → `/ventes/devis/<id>/design` | oui (S1-009) | CAP-D6-04 t4 |
  | `crm/workspace/LeadWorkspace.jsx::ouvrirConceptionToiture` → devis auto 409 | oui (S1-027) | CAP-D6-06 t4 (lead) |
  | `Bibliotheque.jsx` favoris = ids produits tapés | oui (S2-017) | non |
- **Matrice** (round 2 : chaque message × « le lien existe » × « le champ est sur la page d'arrivée » × « enregistrer lève le message ») :
  | Message | lien | champ à l'arrivée | message levé après saisie |
  |---|---|---|---|
  | norme électrique | casse | casse (S2-001) | casse |
  | lestage | tient | casse (S2-002) | casse |
  | mode météo | tient | tient (sans ancre) | casse (refus suivant, F1-016/017) |
  | accès solaire | casse (F1-032) | casse | ? |
  | module à désigner (simulation) | casse (S2-005, 19e puce) | ? | ? |
  | hauteur d'obstacle | n/a | casse (F1-005) | n/a |
- **Garde** : un test de contrat (module `apps/calepinage/tests/test_cal223_contrats.py`) : chaque motif servi porte
  `cible_champ` (étape, panneau, clé) et un test frontend (module `production/PanneauProduction.test.jsx`) vérifie que chaque
  `cible_champ` existe dans le registre des champs montés. Rejoint ACAL386/ACAL397 (« ce qui manque » structuré) — la garde
  lit la même liste. Rouge attendu : `norme_electrique` sans champ monté — non exécuté.
- **Cible du tour suivant** : oui.
- **Propriétaire** : calepinage ; lead pour `LeadWorkspace.jsx`/`IdentityRail.jsx`.
- **Ce qu'elle ne couvre pas** : la valeur à proposer (profil de départ, ACAL403-405).
- **Question de sortie** : non → D7-12, D7-13, D7-14.

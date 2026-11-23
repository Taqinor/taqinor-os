# Complément du lot E aux classes du tour 1 (écrans v2, téléphone, tablette)

Quatre classes du tour 1 sont encore violées sur le lot E ; une classe neuve est née (`K-COUCHE-FIXE.md`). Les endroits
et les cases de matrice s'ajoutent aux fiches `T1/classes/K-*.md` ; aucune classe n'est dupliquée. Statut des causes :
lue / probable / à reproduire, comme dans `registre/evenements/T2-consolidation-E.jsonl`.

## K-STYLE (un seul langage visuel)
| Endroit | Viole ? | Tâche |
|---|---|---|
| `frontend/src/features/calepinage/atelier/coque/primitives.jsx::Tuile` + `::Segmente` + `frontend/src/styles/roofbuilder.css` (`.rp9-btn[aria-pressed]`) — trois styles « choisi » | oui, lue (T2-B2-007) | ACAL1802 |
| `frontend/src/styles/roofbuilder.css::.rp9-btn` / `.rp9-input` — 2 px de rayon à côté de 10 px | oui, probable (T2-B2-004) | ACAL1802 |
| `bg-black/30` dans 8 écrans (`atelier/PanneauReleve.jsx`, `PanneauAllees.jsx`, `atelier/PanneauPertes.jsx`, `atelier/PoseReelle.jsx`, `CourseSoleil.jsx`, `HorizonPanel.jsx`, `reglages/ReglagesAllees.jsx`, `SaisiePente.jsx`) | oui, lue (T2-B2-006, ACAL428, ACAL429) | ACAL1823 (+ ACAL1443 pour `PlanImporteCalage.jsx`) |
| la coque entière : or sur l'état actif, aucune ombre teintée, jetons de l'ERP seuls | oui, lue (B2 § 6) | ACAL1800-ACAL1804 |
Matrice : ligne « état choisi » × colonnes Guidé / Expert / feuille Avancé : casse / casse / casse (T2-B2-007) ; ligne
« champ actif » × thème clair : casse (T2-B2-006). Garde : `frontend/src/features/calepinage/langageVisuel.test.mjs`
étendue (un style choisi, rayons, `bg-black/` refusé) par ACAL1802 et ACAL1823.

## K-ACTION-ENFOUIE (l'action et le résultat se voient sans défiler)
| Endroit | Viole ? | Tâche |
|---|---|---|
| `frontend/src/features/calepinage/AtelierPanneaux.jsx::AtelierPanneaux` (« Relevé de visite », « Montrer au client » au fond d'« Avancé ») | oui, lue (T2-T2-009) | ACAL1809 |
| `frontend/src/styles/calepinage/56-coque-responsive.css` (carte visible 141 px au téléphone) | oui, lue (T2-T2-003) | ACAL1807 |
| `frontend/src/features/calepinage/CalepinageList.jsx` (première carte hors du premier écran au téléphone) | oui, lue (reste d'ACAL957) | ACAL1819 |
Matrice, colonne téléphone 390 : entrées de visite casse (T2-T2-009) ; toit pendant la pose casse (T2-T2-003) ; première
carte de la liste casse (ACAL957). Colonne tablette : contrôles visibles 25 contre 19 (reste d'ACAL1312) → ACAL1835.

## K-GESTE (chaque geste marche sur son appareil)
| Endroit | Viole ? | Tâche |
|---|---|---|
| `apps/web/src/scripts/roofPro11/etatVide.ts::texteEtatVide`, `formesToit.ts` (consignes « clic / double-clic » au doigt) | oui, lue (T2-T2-011) | ACAL1808 |
| `apps/web/src/scripts/roofPro11/gestesCarte.ts::optionsGestesCarte` / voile coopératif au chargement | oui, à reproduire (T2-T2-004) | ACAL1813 |
Matrice : « tracé en cours » × téléphone hors plein écran : casse (T2-T2-011) ; « chargement sans geste » × WebKit : casse (T2-T2-004).

## K-RETOUR-FAUX (un retour dit ce qui s'est vraiment passé)
| Endroit | Viole ? | Tâche |
|---|---|---|
| `frontend/src/features/calepinage/releve/ReleveVisite.jsx::terminer` (hors ligne : rien ne repart malgré le toast) | oui, lue (T2-T2-001) | ACAL1810 |
| `frontend/src/features/calepinage/releve/corpsReleve.js::corpsDuReleve` (orientation tapée enregistrée « boussole ») | oui, lue (T2-T2-006) | ACAL1814 |
| `frontend/src/features/calepinage/releve/ReleveVisite.jsx::ReleveVisite` (« Voir en 3D » ouvre l'atelier) | oui, lue (T2-T2-010) | ACAL1811 |
| `apps/web/src/scripts/roofPro11/shadingUi.ts::syncHeatmapNote` (« vert / rouge » pour une rampe bleu → or) | oui, lue (T2-B2-001, reste d'ACAL441) | ACAL1821 |
| `frontend/src/features/calepinage/HorizonPanel.jsx::HorizonPanel` (« Modifications non enregistrées » après l'enregistrement) | oui, à reproduire (T2-T2-007) | ACAL1816 |
Matrice : ligne « relevé terminé » × hors ligne : casse (T2-T2-001) ; ligne « orientation » × saisie à la main : casse (T2-T2-006).

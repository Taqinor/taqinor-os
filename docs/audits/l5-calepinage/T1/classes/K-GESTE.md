# Fiche d'invariant — classe `K-GESTE` (chaque geste de carte marche sur son appareil)

- **Invariant** : « Molette, clic, double-clic, glisser d'un doigt, pincer et les boutons de carte (zoom, plein écran)
  font ce qu'ils annoncent sans exception ni capture par un autre contrôle, à la souris comme au doigt ; cibles ≥ 44 px. »
- **Née de** : T1-F1-001 (+ S1-004), T1-F1-002 (+ B1-002, T1-003), T1-T1-009 (+ T1-014), T1-T1-004, T1-B1-020 ;
  hors périmètre : T1-T1-025 (barre du haut). Lié : T1-S1-025 (double-clic, classé K-SAISIE-PERDUE).
- **Où il peut être violé** — grep sur `da49cb55b` :
  `git grep -n -E "map.on\('(wheel|dblclick|touchmove|touchstart)'|cooperativeGestures" da49cb55b -- apps/web/src/scripts`
  → `roof-tool-pro11.ts` (wheel, touchstart, touchmove, dblclick), `roofPro11/captureBoot.ts` (dblclick),
  `roofPro11/layoutEditor.ts` (dblclick, touchstart, touchmove), `roofToolShared.ts` (dblclick, site public),
  `roofPro11/viewerFullBoot.ts` (seul `cooperativeGestures`, visionneuse).
  | Endroit | Viole ? | Garde ? |
  |---|---|---|
  | `roof-tool-pro11.ts::map.on('wheel')` lit `e.lngLat` absent | oui (F1-001) | non |
  | `atelier/BuilderDom.jsx` `rp9-plein-ecran-toggle` sur la pile `.maplibregl-ctrl-top-right` | oui (F1-002) | non |
  | `roof-tool-pro11.ts::map.on('touchmove')` — un doigt déplace la carte, pas le coin ni la page | oui (T1-009/014) | non |
  | `roof-tool-pro11.ts::map.on('dblclick')` / `roofToolShared.ts` / `captureBoot.ts` / `layoutEditor.ts` | oui (S1-025) / jumeaux à vérifier | non |
  | champs tolérance/pas 80×21 px, `.rp9-chip` | oui (T1-004, B1-020) | ACAL423, ACAL438 |
- **Matrice** : lignes = molette · clic coin · double-clic fermer · glisser coin · glisser page · pincer · + / − · plein écran ;
  colonnes = Chromium souris · WebKit iPhone 390 · WebKit iPad 820 · 3D inclinée · tracé en cours · toit fermé.
- **Garde** : étendre `frontend/e2e/calepinage_tactile.spec.js` (tablette existante) et la spec téléphone d'ACAL482 par la
  matrice (une ligne = un geste, oracle pageerror + position attendue). Rouge attendu (molette) — non exécuté.
- **Cible du tour suivant** : oui.
- **Propriétaire** : calepinage ; `roofToolShared.ts` = web.
- **Question de sortie** : non → D7-22, D7-23.

# Fiche d'invariant — classe `K-ACTION-ENFOUIE` (l'action et le résultat principaux se voient sans défiler)

- **Invariant** : « Le geste suivant, le bouton qui l'achève et le chiffre résultat sont visibles dans la première hauteur
  d'écran (1440×900, 390×844) à chaque étape ; les réglages de société et d'expert ne sont pas dans le chemin. »
- **Née de** : T1-S1-014 (+ T1-001), T1-S1-002, T1-B1-007, T1-T1-012, T1-F1-003, T1-S1-011, T1-S1-015, T1-S1-022
  (+ S2-006), T1-S2-014, T1-T1-021, T1-T1-023, T1-T1-027.
- **Où il peut être violé** (lu) : ordre de rendu de `frontend/src/pages/ventes/ToitureDesign.jsx::ToitureDesign`
  (BuilderDom → réglages → recommandation → total → `AtelierPanneaux` (Générer le devis) → bloc `cal-enregistrer-calepinage`),
  `atelier/BuilderDom.jsx` (`#rp9-finish` sous la carte `h-[56vh]`), `roof-tool-pro11.ts::go3DView` (pas de cadrage),
  `PanneauAllees.jsx` (réglage société dans l'atelier), `CalepinageList.jsx` (8 filtres), `reglages/ReglagesSimulation.jsx`
  (128 champs à plat), `roofPro11/layoutEditor.ts::renderLayoutPanel` (fenêtre cachée jusqu'au rechargement, probable).
  Mesures relevées : S1 « Générer le devis » à 6 622 px, « Enregistrer » à 6 746 px (7,4-7,5 écrans) ; T1 13,2 écrans au
  téléphone ; résultat à 6,4 écrans sous la carte (T1-012).
  | Endroit | Viole ? | Garde ? |
  |---|---|---|
  | barre d'enregistrement | oui | ACAL399 (+ ordre Générer/Enregistrer : non) |
  | résumé vivant | oui | ACAL401 |
  | disposition studio ≥ 1 280 px | oui | ACAL402 |
  | consigne sur la carte | oui | ACAL420 (sans « Terminer le tracé » : non) |
  | cadrage après fermeture | oui | ACAL435 partiel (bouton Dessus ; recadrage auto : non) |
  | réglages société hors atelier | oui | CAP-D6-06 t3 |
  | filtres repliés au téléphone | oui | non |
- **Matrice** : lignes = (consigne de tracé, Terminer, résultat kWc/production, Enregistrer, Générer le devis, rail
  d'étapes) ; colonnes = bureau 1440×900 · tablette 820×1180 · téléphone 390×844 · après fermeture du toit · après Générer.
- **Garde** : la spec de mesures ACAL385 + le budget ACAL478 (déjà planifiés) — y ajouter les 6 lignes de la matrice comme
  « visible sans défiler » ; écrite par la lane de test d'ACAL385. Rouge attendu partout aujourd'hui — non exécuté.
- **Cible du tour suivant** : oui.
- **Propriétaire** : calepinage.
- **Question de sortie** : oui une fois ACAL385/478 construits ; sinon D7-16.

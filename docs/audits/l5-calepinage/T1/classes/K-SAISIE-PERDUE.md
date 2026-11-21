# Fiche d'invariant — classe `K-SAISIE-PERDUE` (une saisie arrive jusqu'au calcul)

- **Invariant** : « Ce que l'utilisateur a saisi (facture du lead, dernier coin d'un tracé, cible de puissance, matériel du
  modèle) atteint le calcul et y reste après Effacer, double-clic, rechargement ou copie depuis un modèle. »
- **Née de** : T1-S1-023, T1-S1-024 (P0), T1-S1-025 (P0), T1-S2-018. Classe 4 du rejeu.
- **Où il peut être violé** — grep sur `da49cb55b` :
  `git grep -n -E "CHAMPS_COPIES\s*=|contexteToDevisPayload|contexteCalepinageVersPayload" da49cb55b -- backend/django_core/apps/calepinage frontend/src/features/calepinage frontend/src/pages`
  → `services/variantes.py::CHAMPS_COPIES` (roof_layout, layout_hash, pertes) ; `atelier/contexteAtelier.js::contexteToDevisPayload`
  et `::contexteCalepinageVersPayload` (appelé par `useAtelierBoot.js`) ; tests `ToitureDesignCibleAvec.test.mjs`,
  `ToitureDesign.golden.test.jsx`.
  | Endroit | Viole ? | Garde ? |
  |---|---|---|
  | `contexteCalepinageVersPayload` — facture / kWh du lead non transmis | oui (S1-023) | non |
  | `contexteToDevisPayload` (mode devis) | probable (jumeau, non rejoué) | non |
  | `roof-tool-pro11.ts::clearEditorState` (Effacer → neededPanels 0, neededAuto) | oui (S1-024) | non |
  | `roof-tool-pro11.ts::map.on('dblclick')` → `cancelPendingVertex` | oui (S1-025) | non |
  | `roofToolShared.ts` dblclick (simulateurs publics) | jumeau à vérifier | non |
  | `services/variantes.py::CHAMPS_COPIES` (matériel, températures non copiés) | oui (S2-018) — règle d'ACAL117, à trancher | non |
- **Matrice** : lignes = facture · cible panneaux · 4e coin · matériel · températures ; colonnes = ouverture depuis le lead ·
  mode devis · Effacer · double-clic · rechargement · « Partir d'un modèle ».
- **Garde** : étendre `frontend/src/pages/ventes/ToitureDesignCibleAvec.test.mjs` (payload) + le golden ACAL383 (document
  émis par une séance scriptée : facture, tracé fermé par double-clic, Effacer, retracé) ; rouge attendu S1-023/S1-024/S1-025 —
  non exécuté.
- **Cible du tour suivant** : oui.
- **Propriétaire** : calepinage ; `roofToolShared.ts` = web.
- **Question de sortie** : non → D7-05, D7-06, D7-25.

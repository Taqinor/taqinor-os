# Fiche d'invariant — classe `K-RETOUR-FAUX` (un retour dit ce qui s'est vraiment passé)

- **Invariant** : « Un état ou un message de retour (Publiable, Enregistré, Aucune conception, Hors ligne, erreur, 0 MAD)
  est vrai pour l'état serveur du moment ; aucun écran ne produit d'erreur sans geste de l'utilisateur. »
- **Née de** : T1-F1-010 (+ S2-003, B1-014), T1-S2-011 (+ T1-019), T1-B1-024, T1-F1-018 (+ S1-021, B1-023, T1-020, REJEU-NEW-5),
  T1-F1-019, T1-T1-015, T1-T1-008 (+ T1-024), T1-F1-006 (+ S1-006), T1-F1-007, T1-S1-013, T1-S2-012, T1-S2-015, T1-S2-021.
- **Où il peut être violé** — greps sur `da49cb55b` :
  - `git grep -n -E "MOTIF_SANS_CONCEPTION_DOCUMENT|SANS_CONCEPTION\b" da49cb55b -- backend/django_core/apps/calepinage` → 4 textes
    « Aucune conception enregistrée » : `services/documents/__init__.py`, `services/export_projet.py`, `views/sorties.py`,
    `services/variantes.py` (ce dernier juste) ;
  - `git grep -n -E "httpMessage\(" da49cb55b -- frontend/src` → `contexteAtelier.js::httpMessage` appelé 2 fois par
    `ToitureDesign.jsx` avec `code ?? 0` (« Création du devis impossible (erreur 0) » pour un enregistrement) ;
  - `git grep -n "REQUEST_TIMEOUT_MS" da49cb55b -- frontend/src/api` → `axios.js` 20 000 ms appliqué aux téléchargements ;
  - `production/TapisHoraire.jsx::charger` (export-csv au montage, lu).
  | Endroit | Viole ? | Garde ? |
  |---|---|---|
  | `services/electrique.py::_rapport_publication` → « Publiable » sans matériel | oui | CAP-D6-04 t2 (agrégat), onglet : non |
  | `services/documents/__init__.py::inventaire_des_documents` (motif unique quand seul `resultat` manque) | oui | non |
  | `views/sorties.py::SANS_CONCEPTION`, `services/export_projet.py::MOTIF_SANS_CONCEPTION` | à vérifier (jumeaux) | non |
  | `AtelierPanneaux.jsx` `detail` non relu après enregistrement (fiche « Non ») | oui | non |
  | `production/TapisHoraire.jsx::charger` (409 + toast à l'ouverture) | oui | non |
  | `api/axios.js::REQUEST_TIMEOUT_MS` sur `calepinageApi.js::telechargerDocument` (« serveur injoignable ») | oui | non |
  | `ToitureDesign.jsx::enregistrerCalepinage` hors ligne (erreur 0, pas d'outbox, badge qui promet) | oui | non |
  | `features/calepinage/pleinEcran.js` repli CSS jamais lu (iOS) | oui | non |
  | `roofPro11/optimizer.ts::paintCard` « 0 MAD » sans facture | oui | CAP-D6-05 t2 |
  | `production/BandeauProvenanceProduction.jsx::MENTION_RAPIDE` (PVGIS constant) | oui | CAP-D6-05 t4 |
  | `atelier/Approbation.jsx` (refus ×3, boutons offerts à l'auteur) | oui | non |
  | `reglages/ReglagesSimulation.jsx` (une erreur, bulle générique, bandeau en haut) | oui | non |
  | `selectors.py::_condition_recherche` (titre affiché introuvable) | oui | non |
- **Matrice** : lignes = les 13 retours ; colonnes = réseau OK · hors ligne · serveur lent (> 20 s) · rien simulé ·
  matériel non désigné · auteur = approbateur · après rechargement.
- **Garde** : une spec e2e existante du module (`frontend/e2e/calepinage-parcours.spec.js`) gagne l'oracle « aucune requête
  4xx/5xx ni console.error sans geste » à l'ouverture de chaque onglet (oracle qa-explorer n°1-2) ; côté serveur, un test
  `inventaire_des_documents` « conception enregistrée, non simulée » → motif « simulation manquante ». Rouge attendu
  (409 export-csv) — non exécuté.
- **Cible du tour suivant** : oui.
- **Propriétaire** : calepinage (`frontend/src/api/axios.js` : vérifier le propriétaire avant la tâche — non résolu ici).
- **Question de sortie** : non → D7-17 à D7-21.

# Fiche d'invariant — classe `K-JARGON` (une phrase de métier, une fois)

- **Invariant** : « Aucun texte montré à l'utilisateur ne contient une clé (`a.b.c`, `zones[]`), un chemin (`.py`, `::`),
  un code interne (`FICHE_INCOMPLETE`, `CAL197`), une valeur d'énumération brute (`martin_ruiz`, `tmy`) ; un même
  avertissement s'affiche une fois par écran. »
- **Née de** : T1-F1-014 (+ doublons S1-019, B1-003, B1-015, S2-004), T1-B1-010, T1-B1-013 (+ S2-008), T1-S2-007,
  T1-B1-019, T1-S1-003 (+ B1-022, T1-005), T1-S1-008, T1-S1-026, T1-S2-019, T1-S2-025, T1-T1-006, T1-T1-022, T1-S1-010
  (+ F1-022, T1-002 : intertitres répétés).
- **Où il peut être violé** — endroits LUS par les vérificateurs (grep de motif à refaire en round 2 :
  `git grep -n -E "zones\[\]|\.py\b|::|MODULES_PAR_CHAINE|degagements\.allees" da49cb55b -- backend/django_core/apps/calepinage/services apps/web/src/scripts/roofPro11 frontend/src/features/calepinage`) :
  | Endroit | Viole ? | Garde ? |
  |---|---|---|
  | `services/norme.py::norme_applicable` (phrase reprise par `cables.py`, `protections.py`, `terre.py` → ×3) | oui | CAP-D6-03 t4 |
  | `services/ombrage_chaines.py` (« zones[].geometry.solarAccess », « Le silence est explicite ») sur 4 onglets | oui | CAP-D6-03 t4 |
  | `services/electrique.py` (« core.calepinage.electrique, MODULES_PAR_CHAINE = 16 ») | oui | CAP-D6-03 t4 |
  | `electrique/VerdictElectrique.jsx` `<code>{motif.code}</code>` | oui | non |
  | `services/lestage.py::PARAMETRES` (noms de clés affichés) | oui | non |
  | `roofPro11/zones.ts::largeurAlleeDepuisReglages` + `services/degagements.py::largeur_allee_circulation` | oui | non |
  | `Bibliotheque.jsx::Section sousTitre` (CAL197…) + `services/profils_types.py` (chemin du dépôt) | oui | non |
  | `reglages/ReglagesSimulation.jsx::ChampValeur` (option = valeur brute ; « Table structurée (JSON) ») | oui | non |
  | `views/calepinages.py::_avertissements` + `ToitureDesign.jsx` (`libelleCibleEstimee`) — même refus deux fois | oui | non |
  | `BoutonDevis.jsx::generer` (14 lignes brutes, pas de « Devis créé ») | oui | CAP-D6-04 t4 |
  | `FicheCalepinage.jsx` (« Identifiant technique », « Code de statut ») | oui | ACAL432 (style), texte : non |
  | `atelier/onglets.js::groupesOnglets` (intertitres répétés) | oui | ACAL393 |
- **Matrice** : lignes = les 12 endroits ; colonnes = « clé brute » · « chemin / code » · « répété sur l'écran » ·
  « répété sur plusieurs onglets » · « langue (FR seul) » ; cases relevées en round 2.
- **Garde** : étendre la garde de CAP-D6-03 t4 (aucun `::`, `[]`, `.py` dans les textes des `contract_samples`) aux textes
  SERVIS en direct : un test dans le module existant des contrats (`apps/calepinage/tests/test_cal223_contrats.py`) qui
  rejoue les motifs des services listés et refuse ces motifs ; côté front, une assertion de dédoublonnage dans
  `production/PanneauProduction.test.jsx`. Rouge attendu (les 3 phrases norme) — non exécuté.
- **Cible du tour suivant** : oui.
- **Propriétaire** : calepinage.
- **Question de sortie** : non → D7-15 (et CAP-D6-03 t4 en tête).

# Fiche d'invariant — classe `K-DEFAUT-CHOIX` (un défaut n'est ni un choix ni un fait)

- **Invariant** : « Une valeur que personne n'a saisie (pente 22°, face Sud, module 720 Wc, allée 0,60 m, 16 modules par
  chaîne, inclinaison 35° ou 0° E-O, structures + socles, « on pose ce qui tient ») est marquée « par défaut — à confirmer »
  partout où elle s'affiche, et ne fixe jamais seule un chiffre client (devis, /proposal) sans une confirmation. »
- **Née de** : T1-S1-007 (P0), T1-F1-027 (P0), T1-F1-023, T1-F1-008, T1-B1-004, T1-S2-005, T1-S2-020, T1-S2-022,
  T1-S2-023, T1-S2-024 ; rejeu : REJEU-NEW-3 (structures acier × N + socles × 2N sur toit en pente affleurant, PDF p.2),
  REJEU-NEW-4 (« Est-Ouest 0° » recommandé). Classe 2 du rejeu.
- **Où il peut être violé** — greps sur `da49cb55b` :
  - `git grep -n -E "pitchDeg = 22" da49cb55b -- apps/web/src/scripts/roof-tool-pro11.ts` → `let pitchDeg = 22` (ACAL417 le traite à l'écran) ;
  - `git grep -n -E "PANEL2_WATT\s*=" da49cb55b -- apps/web/src` → `apps/web/src/lib/roofPro2.ts` (720) ;
  - `git grep -n -E "MODULES_PAR_CHAINE\s*=|allee_m.{0,15}0[.,]6" da49cb55b -- backend/django_core/core backend/django_core/apps/calepinage/services`
    → `core/calepinage/electrique.py::MODULES_PAR_CHAINE` (16), `core/calepinage/politique_pas.py::AlleeFixe.allee_m` (0,60),
    `core/calepinage/types.py` (0,60), `core/calepinage/serialisation.py` (0,60) ;
  - `apps/ventes/domain/composition.py::quantites_derivees_du_compte` (structure N, socle 2N sans condition — lu).
  | Endroit | Viole ? | Garde ? |
  |---|---|---|
  | `apps/calepinage/services/devis.py::generer_devis` — devis « toit rempli » sans facture ni taille | oui (S1-007, 168 800 / 513 800 MAD) | non |
  | `frontend/src/features/calepinage/ModeTerrain.helpers.js::demandeMoteur` → `politique_pas.py::AlleeFixe` 0,60 m | oui (F1-027, chiffré) | non |
  | `apps/ventes/domain/composition.py::quantites_derivees_du_compte` | oui (REJEU-NEW-3, chiffré) | non |
  | `apps/web/src/lib/estimatorBrainCommun.ts::departageBase` (max d'énergie posée, aucun critère de coût) | oui (F1-023) | non |
  | `apps/web/src/lib/estimatorBrainV7.ts::tiltCandidates` (grille [0,5,10…] pour E-O ; V6 = [10,12,15]) | oui (REJEU-NEW-4) | non |
  | `roofPro11/optimizer.ts::paintCard` gain bifacial sans test de pose ni de fiche bifaciale | oui (F1-008) | non |
  | `services/simulation.py::verifier_simulable` — le module par défaut de l'atelier n'est jamais écrit au document | oui (B1-004) | non |
  | `services/parametres_cles.py::registre` — décisions fondateur citées mais valeur vide ; replis silencieux ailleurs | oui (S2-020, S2-024) | non |
  | `services/lestage.py::PARAMETRES` — constantes physiques demandées comme réglages | oui (S2-023) | non |
  | `electrique/SaisiesElectriques.jsx` Tmin/Tmax sans repère | oui (S2-022) | non |
- **Matrice** :
  | Défaut | écran atelier | onglet | devis/composition | /proposal | après confirmation |
  |---|---|---|---|---|---|
  | pente 22° / Sud | casse (ACAL417) | casse | casse (S1-005 via orientation_du_pan) | casse | ? |
  | module 720 Wc | casse (S1-018) | casse (B1-004) | casse (substitué 710) | casse | ? |
  | allée 0,60 m champ au sol | casse (F1-027) | — | casse | casse | n/a (pas de choix possible) |
  | toit rempli sans cible | casse (S1-007) | — | casse | casse | n/a |
  | structures + socles | — | — | casse (REJEU-NEW-3) | casse | ? |
  | E-O 35° / 0° | casse (F1-023, NEW-4) | — | ? | ? | ? |
- **Garde** : étendre le golden ACAL383 (document émis) par une liste DONNÉES `defauts_annonces` : chaque clé posée sans
  saisie porte une provenance `defaut` ; un test de `apps/calepinage/tests` (module existant des devis générés) refuse un
  devis dont une grandeur chiffrée dérive d'une provenance `defaut` non confirmée sans avertissement. Rouge attendu sur les
  cas S1-007 / F1-027 / REJEU-NEW-3 — non exécuté.
- **Cible du tour suivant** : oui.
- **Propriétaire** : calepinage ; devis (`composition.py`) ; web (`estimatorBrainCommun.ts`).
- **Ce qu'elle ne couvre pas** : le choix du bon défaut (décision produit, § « choix tranchés »).
- **Question de sortie** : non → D7-03, D7-04, D7-07, D7-08.

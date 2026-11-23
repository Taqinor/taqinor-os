# Fiche d'invariant — classe `K-COUCHE-FIXE` (rien d'utile ne naît sous une pièce fixe ou flottante)

- **Invariant** : « Aucune pièce fixe ou flottante de l'atelier, du relevé ou de la vue client — barre du bas, barre
  d'outils, bandeau, panneau d'étape, tiroir, voile de geste, toast — ne recouvre une réponse à un geste, une consigne,
  une commande ou le toit cadré : la zone sous la pièce est réservée, la réponse est ramenée en vue (défilement + focus),
  et le cadrage de la carte se fait dans la zone libre entre les pièces. Mesure : `document.elementFromPoint` au centre
  de l'élément rend l'élément lui-même ou un descendant, à 1440 × 900, 1180 × 820 et 390 × 664. »
- **Née de** (tour 2, lot E) : T2-T2-002 (réponse de « Terminer le relevé » sous la barre fixe), T2-T2-001 (message
  honnête « Pas de réseau… » à y 688 sur 664), T2-T2-004 (voile « deux doigts » par-dessus le tiroir), T2-T2-005
  (explication de « Envoyer le lien » coupée sous le pied), T2-T2-007 (message qui écrase « Enregistrer le profil »,
  pastille « Caler le fond » sur la barre du bas), T2-B2-005 ; remarques des verdicts ACAL945 (message hors ligne qui
  recouvre « Générer le devis ») et ACAL951 (« Plein écran » recouvert par le tiroir agrandi).
  Voisine, pas identique, de `K-ACTION-ENFOUIE` (T1 : l'action est dans la première hauteur d'écran, mais peut y être
  CACHÉE par une pièce) et de `K-COLONNE-ETROITE` (lot B : la largeur d'une grille). Elle devient centrale avec la coque
  v2 (ACAL1801) : toutes les pièces flottent alors sur la carte.
- **Où il peut être violé** — greps lancés sur la tête de cette session (`b06468cc8`) :
  - `git grep -n -E "position: (fixed|sticky)|position: absolute" -- frontend/src/styles/calepinage frontend/src/styles/roofbuilder.css`
  - `git grep -n -E "role=\"status\"|role=\"alert\"" -- frontend/src/features/calepinage/releve frontend/src/features/calepinage/client frontend/src/features/calepinage/HorizonPanel.jsx`
  | Endroit | Viole aujourd'hui ? | Couvert par la garde ? |
  |---|---|---|
  | `frontend/src/features/calepinage/releve/ReleveVisite.jsx::ReleveVisite` (`releve-message` en fin de corps, sous `.cal-tel-pied`) | oui (T2-T2-002, T2-T2-001) | non — ACAL1812, garde ACAL1824 |
  | `frontend/src/features/calepinage/client/partiesClient.jsx::TuilesClient` (`client-lien-raison` sous `PiedClient`) | oui (T2-T2-005) | non — ACAL1837 |
  | `frontend/src/styles/roofbuilder.css` (voile `.maplibregl-cooperative-gesture-screen`, z-index 99999) | oui, à reproduire (T2-T2-004) | non — ACAL1813 |
  | `frontend/src/features/calepinage/HorizonPanel.jsx::HorizonPanel` (message sur la rangée du bouton) | oui (T2-T2-007) | non — ACAL1815 |
  | `apps/web/src/scripts/roofPro11/mapDraw.ts` (pastille « Caler le fond » sans règle téléphone) | oui (T2-T2-007) | non — ACAL1815 |
  | `frontend/src/styles/calepinage/56-coque-responsive.css` (tiroir de 300 px sur la carte au téléphone) | oui (T2-T2-003) | non — ACAL1807 |
  | `frontend/src/features/calepinage/atelier/coque/CoqueAtelier.jsx::usePlanALEntreeDEtape` (cadrage sans marges de pièces) | oui dès ACAL1801 | non — ACAL1801 |
  | message hors ligne de l'atelier sur « Générer le devis » (`BarreEnregistrement`, remarque d'ACAL945) | probable | non — garde ACAL1824 |
- **Matrice champ × condition** :
  | Élément | 1440 × 900 (coque v2) | 1180 × 820 tactile | 390 × 664 WebKit | hors ligne | thème sombre |
  |---|---|---|---|---|---|
  | réponse de « Terminer le relevé » | n/a — relevé au téléphone | casse (T2-T2-012, colonne) | casse (T2-T2-002) | casse (T2-T2-001) | ? |
  | explication « Envoyer le lien » | ? | ? | casse (T2-T2-005) | n/a | ? |
  | toit cadré à l'entrée d'étape | casse dès ACAL1801 | casse (feuille basse) | casse (T2-T2-003) | n/a | ? |
  | consigne de tracé | ? | ? | casse (T2-T2-004, T2-T2-011) | n/a | ? |
  | message « Profil d'horizon enregistré » | ? | ? | casse (T2-T2-007) | n/a | ? |
  | message d'enregistrement hors ligne de l'atelier | ? | ? | casse (ACAL945, remarque) | casse | ? |
- **Garde** (UNE, famille existante) : nouveau bloc « K-COUCHE-FIXE » de `frontend/e2e/calepinage-mesures-ecran.spec.js`
  (tâche ACAL1824) qui parcourt la matrice (une assertion `elementFromPoint` par case `casse` ou `tient`), aux trois
  tailles. Rouge sur la tête par T2-T2-002 (message à y 607 sous une barre dont le haut est à 578) ; mutant : retirer la
  zone réservée d'ACAL1812 ⇒ échec. Écrite par le rédacteur des tests premiers du tour, pas par la lane qui corrige.
- **Cible du tour suivant** : oui — à donner aux relecteurs (téléphone, tablette, et la coque v2 au bureau).
- **Propriétaire** : `docs/plans/PLAN_AUDIT_CALEPINAGE.md` (unité calepinage).
- **Ce qu'elle ne couvre pas** : le contraste d'un texte posé sur la photo aérienne (une vraie clé de carte est
  nécessaire) ; les pièces qui recouvrent volontairement la carte (bandeau, rail, panneau) tant que le toit cadré reste libre.
- **Question de sortie** : « le système l'attraperait-il tout seul la prochaine fois ? » — oui, par le bloc
  K-COUCHE-FIXE de la spec de mesures, une fois ACAL1824 construite.

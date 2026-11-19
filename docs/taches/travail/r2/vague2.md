# r2 — seconde vague de corrections (restes de la première, tenus au fil des plis)

Branche d'intégration : `dev-taches-r2` (worktree `taches-r2`). Plis faits : L1 `a083647e8`, L5 `e36003775`,
L3 `945c9ee63`. En cours à l'écriture de ce fichier : L2, L4, L6, L7, L8.

## Reportées volontairement (dépendances entre lanes)
- R2-009 — saisie en place au bureau (popover sous « Ajouter une tâche », sans voile). L1 a essayé puis retiré : il
  faut que `FeuilleACrans` (L4) ne dessine pas `.voile` pour `variante="popover"` et accepte un point d'ancrage, et
  que `.feuille.popover-bureau` soit placé sous `.saisie-bureau` (`saisie.css` L4 ou `base.css` L6) ; puis dans
  `FeuilleSaisie` : `variante={modeListe ? 'dialogue' : 'popover'}`.
- R2-021, R2-025, variante `panneau` du bilan du soir et d'Alléger (L2, après le pli de L4).
- R2-067 — maître-détail des Projets au bureau (L5, après le pli de L6 : prop `retour`).
- R2-128 — prop `retour` dans Réglages / Rythme / Recherche (L8, après le pli de L6).

## Demandes croisées remontées par les lanes
- (L1) `lib/gestes.js` : `annulerToast` annonce « Annulé » après TOUTE action de toast, y compris « Reprendre » :
  variante qui n'annonce pas, ou qui annonce le libellé du bouton.
- (L1) iPhone : le toast couvre la liste `#` des projets et le sélecteur de projet (position du toast : `base.css`).
- (L3) `pages/taches/Aujourdhui.jsx` : passer `bilanFait={Boolean(donnees.plan?.cloture_le)}` à `CarteDuMoment`
  (le constat « 57 % » s'affiche encore après le bilan) ; effacement en fondu de la ligne reportée (R2-017, fin).
- (L3) `base.css` : règle « méta sur la ligne du titre » pour `.ligne-corps.meta-courte` (méta `flex: 0 0 auto;
  white-space: nowrap`, titre `flex: 0 1 auto`, conteneur `flex-wrap: wrap`) ; les indices ont la classe `.indice`,
  texte caché `.sr`.
- (L3) serveur : ajouter `a_notes` (booléen) à l'ITEM de liste (`serializers/formes.py` + `contract_samples/item.json`,
  contrat d'abord) pour que l'indice « note » de la ligne s'affiche.
- (L3) `selectors/projets.py:478` : passer `courante=(lundi == lundi de la semaine en cours)` au gabarit de la Revue.
- (L3) `contract_samples/revue_projets.json` + `api.md` l.1956 gardent l'ancienne phrase « Du lun. 16… » (lue par
  `Revue.test.jsx`) : aligner sur « Cette semaine : N faites (M la précédente). ».
- (L3) R2-034 : phrase de santé « à ce rythme, pas prêt pour le 22 » (`moteur/sante.py`) non faite.
- (L5) libellé « Déplacer… » → « Changer de projet… » : il est dans `ui/LigneTache.jsx` (L3) et le titre de feuille
  « Déplacer vers… » dans `ActionsLigne` est asserté par `Aujourdhui.test.jsx` ; `Projet.test.jsx` référence encore
  « Déplacer… ». À faire d'un seul geste (libellé, titre de feuille, tests, specs e2e).
- (L5) au 400 d'un nom de projet refusé, le pont global de l'ERP ajoute un toast « Nom : … » en plus du message sous
  le champ (doublon).
- (L5) Chronologie : un point à la date de début d'axe dépasse le cadre de ~5 px ; vue iPhone non regardée.

## Vu sur la pile, à rejouer au tour 2
- 500 sur `POST /api/django/taches/tout-effacer/` : « canceling statement due to statement timeout … while deleting
  tuple in relation taches_planjour » (pile chargée par 8 lanes ; verrou ?). À reproduire au calme : un vrai défaut si
  « Tout effacer » peut échouer.
- Fenêtre « Bienvenue chez Taqinor » de l'ERP au premier chargement : bloque tout tant qu'on n'a pas touché « Plus
  tard » (hors module ; à juger au tour 2 : est-ce que Reda la verra en ouvrant Tâches ?).
- Le bouton + flottant capte le toucher d'une ligne placée sous lui.
- `LigneTache.test.jsx` « balisage figé » : dépendait de l'alias de classe de lucide (normalisé par L3).

## À rejouer sur l'écran après les plis (moitiés serveur non servies pendant la vague 1)
- L1 : « #Sal » tapé à la main ; coller `tests/donnees/liste30.txt` → 7 en-têtes ; les 7 phrases de F1 + « avant le 25 ».
- L5 : Planifier le projet › Plus › Étapes « Transport / Hébergement / Sur place » → « 3 étapes · 0 tâche ».
- L3 : carte « 3 tâches reportées 3 fois ou plus. Les revoir maintenant ? » (Oui / Pas maintenant) ; Revue « Cette
  semaine : … faites (… la précédente). ».

## Après le pli de L4 (`935f8a38e`)
Interface exposée par L4, à consommer telle quelle :
- `useOuvrirFiche()(id, { section, focus })` : `section: 'decouper'` ; `focus: 'titre' | 'heure'` (adresse
  `?tache=12&section=decouper` / `&focus=titre|heure`). R2-021 : `ouvrirFiche(item.id, { section: 'decouper' })` ;
  R2-025 : `{ focus: 'titre' }` et `{ focus: 'heure' }`.
- Bilan et Alléger en panneau : ajouter `variante: 'panneau'` dans l'objet `feuille` que `Aujourdhui.jsx` passe à la
  coquille (≥ 1024 px : panneau fixe à droite, `aria-modal="false"`, sans voile ; en dessous : inchangé).
- La fiche émet `taqinor:taches:ecrite` (`detail = { tache }`, constantes `EVENEMENT_ECRITE` / `signalerEcrite` de
  `lib/fiche.js`) ; `useApresCreation` écoute les deux événements.
Demandes de L4 :
- (→ L6 `CoquilleTaches.jsx`) `fermerFiche` sans marque d'historique ne retire que `tache` : retirer aussi `section`
  et `focus` ; la touche `n` est bloquée dès qu'un `[role="dialog"]` existe (donc avec le panneau non modal de la
  fiche) : filtrer sur `[aria-modal="true"]`.
- (→ L2) `taches-journee.spec.js` attend encore « Garder ces 0 » (texte changé par R2-026).
- Pas joué à l'écran par L4 : « Supprimer » et « Quand › Aujourd'hui » depuis la fiche (R2-040) ; notes tapées puis
  rechargement (R2-044) ; rappel (R2-046) ; specs `taches-bureau.spec.js` jamais lancées (CI).
- Animation de SORTIE des feuilles absente (la feuille disparaît d'un coup) : à juger au tour 2.
- Textes changés notés dans les messages de commit de L4 (référence `textes.md` non mise à jour) : à reporter.

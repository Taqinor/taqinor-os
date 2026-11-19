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

## Après le pli de L6 (`e9f532586`)
Interface exposée par L6 : prop de `CoquilleTaches` `retour={{ libelle, vers }}` (ex.
`<CoquilleTaches ecran="projet" titre={titre} retour={{ libelle: 'Projets', vers: '/taches/projets' }}>`) : « ‹ libellé »
au-dessus du titre ; iPhone : à la place de ☰ ; pas de loupe ni Copilote sur un écran qui la passe. L5 doit retirer
`BarreRetourProjets` de la page Projet en la passant (sinon deux retours). Rien de visible tant qu'aucune page ne la passe.
ATTENTION (leçon L6) : `.layout:has(.tch)` fuit sur toutes les apps (`TachesPresence` et le bouton ✓+ portent `.tch`
partout) ; le bon sélecteur est `.layout:has(> .layout-main > .layout-content > .route-fade > .tch)`.
Demandes de L6 :
- NOM DE CLASSE À ALIGNER : L3 pose `meta-courte` sur `.ligne-corps`, L6 a écrit la règle pour `meta-en-ligne`
  (`base.css`). Garder UN nom (celui du CSS ou celui du JSX) : sinon la méta ne monte jamais sur la ligne du titre.
- (→ L2) `Aujourdhui.jsx` garde son délai de squelette à 1 s ; aligner sur 300 ms (R2-089).
- (→ L5, R2-070) Projets hors ligne : il resterait la phrase rouge « Connexion perdue… » et « Aucun projet » (à
  revérifier après assemblage : L5 dit l'avoir réglé).
- R2-125 : libellé « Supprimées et derniers gestes » du menu ⋯ non fait.
- R2-088 : le réglage « sans délai » d'annulation est gardé sur l'appareil (localStorage) ; changé sur un AUTRE
  appareil, il ne vaut ici qu'après un passage dans Réglages.
- R2-092 : encore 6 à 7 tailles de texte sur Aujourd'hui (agenda, cartes, bandeaux), pas 4.
- Hors module : squelette générique de l'ERP au chargement à froid (Suspense du routeur, `module.config.jsx`).

## Après le pli de L7 (`43d3cc588`)
- (→ L2 `aujourdhui/ColonneBureau`) passer `creneauxLibres` à `GrilleAgenda` (aucun créneau sous un bloc) et adapter
  `ColonneBureau.test.jsx` (« Ajouter à 10:00 » tombe sous un bloc du jeu d'essai).
- `ui/LigneTache.test.jsx` : snapshot « Passe visuelle n° 46 » dépend de la DATE DU JOUR (« échéance jeu. 19 ») :
  horloge à figer dans le test.
- `e2e/acceptation/tch.spec.js` P139.7 clique « Placer à 10:00 » : ce créneau est absent s'il est sous un bloc.
- R2-103 : « venant de la Revue » → semaine suivante non géré à part (`Revue.jsx` ne passe aucun `jour`).
- R2-105 : toucher un bloc DÉJÀ posé ouvre la fiche ; « Déplacer » n'existe qu'après la pose.
- Références à reporter (`api.md` annexe A `agenda.json` + `rendez_vous_minutes`, `faites_nb` ; `textes.md` §2.8 ;
  `regles.md` : règle « faites » C-12, pause C-5).
- À rejouer sans interception après le pli : `rendez_vous_minutes`, `faites_nb` ; projet en pause + tâche à 16:00.
- Specs `e2e/taches-agenda.spec.js` jamais jouées (CI).

## Après le pli de L8 (`2bb1cf6fd`)
- R2-124 « Faites cette semaine » NON livré : la liste serveur ne dit pas quand une tâche a été faite. Il faut
  `fait_le` dans l'ITEM de liste (`serializers/formes.py` + `contract_samples/item.json` + tous les échantillons qui
  embarquent des items, tests clés-ET-ordre) ou `periode=faites_semaine` + date servie (`services/taches.py`,
  `views/taches.py`) ; puis le front de la Recherche (puce + groupes par jour).
- Libellé du menu ⋯ « Supprimées et derniers gestes » : vit dans `coquille/CoquilleTaches.jsx` (DESTINATIONS,
  « Supprimées récemment ») ; titre de page à aligner.
- `contract_samples/proposition_repondue.json` embarque un `rythme` sans `jours_travailles` : aligner.
- Toast global en doublon du message sous le champ : aussi au POST d'un agenda externe en erreur (« Url : Adresse
  injoignable… ») — même cause que le « Nom : … » des projets (pont d'erreurs de l'ERP).
- `RouteFocus` de l'ERP vole le curseur de la Recherche au chargement direct (repris par L8 dans les 1,5 s).
- Tests hors lane qui échouent en local selon l'horloge ou la charge : `LigneTache.test` (snapshot daté),
  `TachesPresence.test` (« 1 ouvertes »), `routes.test` (délai 5 s à froid).
- À rejouer après le pli (serveur servi) : `rythme/` de 10 entrées dont 5 `sans_donnees` ; tenir → libre → pousser
  rend le palier dit ; `gestes/` avec `titre` ; 3 messages d'agenda externe.

## Après le pli de L2 (`a10817e98`) — les 8 lanes de la vague 1 sont pliées (tête `cfdcd415d`)
Suite front du module sur l'assemblage (`npm run test:unit -- src/features/taches src/pages/taches`) : 889 verts,
11 rouges :
- `ui/CarteDuMoment.test.jsx` (2 : « sans essentiel : 1 sur 5 seul », « au toucher : objectif et source… ») :
  conséquence de R2-019/R2-035 (L2) : il faut aussi `d.essentiel = []` ; attendu « 1 faite sur 5 visées · 4 tâches gardées ».
- `pages/taches/Projet.test.jsx` (6 : TCH89 ×2, R2-071, R2-061 ×3) et `Projets.test.jsx` (1 : R2-070 autre compte) :
  couture L5 × (L1 saisie, L6 coquille) — V2-A travaille sur ces fichiers.
- `lib/gestes.test.js` (1 : « Messages sans délai — allumé ») : couture L6 (R2-088) — V2-B possède `lib/gestes.js`.
- `projets/PlanifierProjet.test.jsx` (1 : « Terminer envoie… ») : brouillon non vidé (`savedAt` encore présent) ;
  L5 le disait instable sous charge : à rejouer seul.
Demandes de L2 :
- `tests/test_flux_tuile.py` l.137 : poser `statut_depuis` à la veille pour « Projet-Z pause » (sous C-5 « Pause-Z »
  sortirait sinon dans le flux).
- Optionnel serveur : `reste_nb` ne compte pas les lignes de la suite (permettrait de réafficher le chiffre quand
  Proposé est replié).
- À rejouer : carte C7 « Oui » → déplie « À revoir » ; pause d'un projet + tâche à 16:00 aujourd'hui.
- Vu : au bureau le panneau (fiche, bilan, Alléger) RECOUVRE la colonne Agenda (une lettre du titre « Agenda » dépasse
  à gauche du panneau) ; le toast reste figé tant que la souris le survole.

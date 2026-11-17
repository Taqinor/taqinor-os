# Maquettes secondaires (L3 n°8)

33 HTML dans `maquettes/`, feuille `ecrans-secondaires.css` (préfixe `es-`), 132 captures. Trois tours vus par écran
(planches clair 1:1 + sombre ; bureau plein pour six écrans), puis contrôle mesuré : 0 cible sous 44 px, 1 contraste
sous 4,5 (fin), recouvrements du bouton flottant = boîtes de titre seulement, pas d'encre.

## Par écran
- **Recherche** (+ `-filtres`, `-vide`, `-palette`). T1 : puces sur deux lignes, bureau étiré. T2 : barre ‹ · champ ·
  réglages (pastille du nombre), une ligne de puces ; bureau à trois colonnes avec la fiche du résultat. T3 : respiration.
- **Supprimées récemment** (+ `-gestes`). T1 : cases inertes prises pour cochables. T2 : colonne vide, « Restaurer » en
  puce de tête comme « Garder », marge sous le toast. Tâche sans projet → « Restaurée dans À trier ».
- **Réglages** (accueil, notifications, vie privée + `-bas`, données + `-effacer`). Rubriques en texte seul (faute 4) ;
  bureau = rubriques au centre, rubrique à droite. T2 : intertitres dans la vie privée (mots inchangés), ce qui part en
  gras dans « Tout effacer ».
- **Archive, Modèles** (+ `-utiliser`, `-enregistrer`). T2 : calendrier au bureau seulement, aperçu des étapes visible
  sur iPhone, « Créer » près du titre. T3 : marge parasite du résumé.
- **Dialogues de projet** (décaler, décaler-avant, terminer, supprimer) sur l'écran du projet. T2 : aperçu avant → après
  empilé ; « Appliquer » indisponible en gris (l'or atténué virait au brun en sombre).
- **États** (hors ligne, pas à jour, conflit, erreur de champ, chargement, toast, astuce, question du rappel). T2 : toast
  À CÔTÉ du bouton flottant. T3 : « En attente d'envoi » écrit dans la méta ; échéance rouge relevée en sombre.
- **Rappel ouvert** : « Rappel · 10:00 » + Encore 10 min · Encore 1 h · Demain 9 h en tête de fiche.
- **Première utilisation** (lun. 2 nov.) : aperçu, Aujourd'hui (carte « 5 proposées », toast « 6 tâches créées »),
  après « Garder ces 5 » (carte Mon iPhone), Mon rythme. T2 : découpé pour respecter l'ordre des cartes.

## Écarts assumés
- « Prévue jeu. 26 » au lieu de « Reportée à jeu. 26 » (Reporter va au mer. 25).
- « Pas à jour · 09:02 » : heure ajoutée.
- Textes ajoutés hors `textes.md` : « Ouvertes / Faites », résumés des rubriques, « Nom du modèle », aide sur les dates
  d'un modèle, « Rappel · 10:00 ».
- Aperçu : « Nouveau projet · 3 tâches » sous le nom, comme les écrans cœur.
- Mon rythme jour 1 : « 0 jour sur 10 » ; modes aux phrases exactes de `textes.md`.
- Barre d'onglets gardée sur les écrans poussés.

## Ce qui déplaît encore
Bureau `.deux` : 340 px morts à droite ; Mes données et Modèles maigres sur iPhone ; cinq puces « Restaurer » azur
lourdes ; astuce figée. Non vérifié : vrai iPhone, daltonisme, texte à 130 %.

## À reporter dans les feuilles partagées
- `.meta .alerte` sur `.ligne.selectionnee`, sombre : 4,49:1.
- `.toast-place + .fab` soulève le bouton sur la colonne de fin ; adopter `.es-toast`.
- `.bouton[aria-disabled]` neutre, à verser dans `taches.css`.
- `rythme.html` : phrases des modes ≠ `textes.md` §2.11.
- Trancher la barre d'onglets sur les écrans poussés.

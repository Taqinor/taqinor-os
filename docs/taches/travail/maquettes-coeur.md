# Maquettes rendues — écrans cœur (L3 n°8)

16 pages `maquettes/ecran-*.html`, `ecrans-coeur.css` (jetons seuls, aucun littéral), 64 captures. Contrôle par
script (contraste sur fond composité, cibles avec `::after`, 1re tâche, action principale) : 64 vues sur 64 passent.
Données : `maquettes/SCENARIO.md` (mardi 24 novembre 2026, objectif 5).

## Tour 2 (critique 6-8/10) — ce qui a changé
- **Partagé (`taches.css`, lane propriétaire)** : segments partout, barre fine de projet, carte du moment, pastille
  « Toute la journée », barre latérale bureau + 3 colonnes fixes, titre compact, voile 32 % et z-index, bouton flottant
  caché au défilement, puce « Garder », puce icône 44 px, `.i.plein`, 88 px/h, bande de jours, `.maintenant-heure`,
  teintes chaudes en sombre, `--tch-surveiller`, interrupteur. Planches 3, 5, 7, 8 et sommaire mises à jour.
- **Matin** : carte « 3 tâches proposées pour atteindre 5 · Garder ces 3 » en haut ; « 0/2 » d'Essentiel retiré ;
  visite en pastille ; Proposé = 5 − 0 − 2 = 3 (fournisseur, rails, contrat).
- **15 h** : 3 sur 5, trois faites barrées, « Rédiger la fiche de poste → jeu. 26 », Proposé couvert (5 − 3 − 2 = 0).
- **Menu ⋯** : sans icône, groupes séparés par une bande. **Vide** : 2 lignes, bouton sans icône.
- **Retour** : « Garder ces 5 », « Garder » par ligne (le bouton flottant ne couvre plus rien).
- **Saisie / liste** (bureau) : en place dans la liste ; « Moyenne ▾ » par nouveau projet, en-tête neutre.
- **Fiche** : cran sans ruban, points 18 px, Plus = Répéter · Durée · Étiquettes · En attente de… · Lié à · Jalon ·
  Confidentielle (« Après… » retiré), titre dans la barre au défilement ; même liste au bureau.
- **À trier** : gestes 15 px 500 gris ; provenance sans icône ; compte au-dessus du titre ; au bureau une colonne.
- **Bilan** : 4 sur 5 en segments, « Faites », « Tout reporter à mer. 25 » dans l'en-tête du reste, constat et
  rythme du scénario, panneau droit au bureau.
- Script de contrôle : + intersection bouton flottant / cibles. 0 défaut sur toutes les vues rendues.

## Ce qui déplaît encore
- Le bouton flottant ne couvre plus de cible, mais il cache encore du texte de méta en bas de pli.
- À trier au bureau : 300 px vides à droite de la liste.
- La carte de retour reste haute (3 lignes de texte + 2 boutons empilés sur iPhone).
- Clavier en bloc gris ; titre compact sur fond à 94 % : un fantôme reste perceptible.

## Écarts assumés (la spec 7 devra s'aligner)
1. « Garder » en puce dans la méta des lignes proposées, au lieu d'un « + » en fin de ligne.
2. Menu ⋯ iPhone en feuille d'actions, actions de l'écran en bas.
3. Écran vide sans bouton flottant ; « !!! » au lieu de « !! » (spec 2 : `!!` = moyenne).
4. Bouton Fait vert ; saisie lundi 23 (le projet Salon y naît).
5. Phrases à valider : « Aucune n'est comptée en retard. », « Ton objectif est couvert par ce que tu as gardé. »,
   « Une liste par projet, une tâche par ligne. ».

Non vérifié : vrai iPhone (Safari, `text-wrap: balance` = 17.5, `:has()`), lecteur d'écran.

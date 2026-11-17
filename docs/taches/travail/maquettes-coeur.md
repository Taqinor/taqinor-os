# Maquettes rendues — écrans cœur (L3 n°8)

16 pages `maquettes/ecran-*.html`, `ecrans-coeur.css` (jetons seuls, aucun littéral), 64 captures. Contrôle par
script (contraste sur fond composité, cibles avec `::after`, 1re tâche, action principale) : 64 vues sur 64 passent.
Données : mardi 24 novembre 2026.

## Par écran (tours = rendu puis regard)
- **Aujourd'hui 8 h 30** (3) : anneau vide = fausse case → 5 segments ; Copilote au bord → loupe · Copilote · ⋯ ;
  explication de Proposé sur 3 lignes → sous-titre ; « : » insécables.
- **15 h** (4) : heure + ★ + échéance écrasaient le titre → heure retirée ; menu ⋯ en popover mettait « Alléger »
  en haut (y 133) → feuille d'actions au pouce (y 556).
- **Vide, retour** (3, 3) : « je » orphelin → équilibrage ; boutons de retour étirés au bureau → en ligne.
- **Saisie, liste collée** (3, 4) : jeton projet en contour cassé → fond teinté ; puces sur 3 rangées → 2 ;
  cases bleu plein → teinte douce ; nom de projet en titre.
- **Fiche, Plus** (4) : capitales → casse de phrase ; puces toutes neutres ; barre × ★ ⋯ alignée au bureau.
- **À trier** (4) : 20 pilules = formulaire → gestes en texte doux ; bureau : gestes à droite, colonne Projets.
- **Bilan, rythme** (3) : capitales retirées, « ⋯ » 40 → 44 px, flèche doublée.

## Ce qui déplaît encore
- Proposé ne se distingue des gardées que par le « + » et le titre.
- À trier reste un motif répété (4 gestes × 5 lignes).
- Segments sur Aujourd'hui, anneau au bilan : deux formes pour une idée.
- Clavier en bloc gris ; barre d'état opaque qui coupe le défilement ; menthe et ambre lourds en sombre.

## Écarts assumés (la spec 7 devra peut-être s'aligner)
1. Progression sans anneau (A14 oui, spec 8 §1 non) : un anneau vide imite une case.
2. « Prévu » titré (spec 7 rév. 3 ; spec 8 §2 le voulait sans titre).
3. Écran vide sans bouton flottant : deux boutons or se disputaient le regard.
4. Menu ⋯ iPhone = feuille d'actions, actions de l'écran en bas ; ordre de la spec gardé au bureau.
5. « !!! » au lieu de « !! » (spec 2 : `!!` = moyenne) ; puces Quand · Heure · Priorité · Projet.
6. Bilan : « Le reste → mer. 25 » (lot) au lieu de « Tout reporter » ; faites non barrées ; la proposition de
   rythme remplace le constat ce jour-là.
7. Bouton Fait vert : « fait » a une seule couleur.
8. **Chiffres du lot** : 4 gardées + « Garder ces 3 » = 7 pour un objectif de 5. La spec doit dire si Proposé
   remplit « jusqu'à l'objectif » en comptant les gardées. À 15 h, 3 ≥ 5/2 : pas de carte (spec 5a §3.9), Alléger
   passe par ⋯.
9. Phrases à valider : « Aucune n'est comptée en retard. », « Ton objectif est couvert par ce que tu as gardé. »,
   « Une liste par projet, une tâche par ligne. ».

## À reporter dans `taches.css`
- `.maintenant-heure` a le fond `--tch-surface` ; l'agenda bureau est sur `--background` → « 09:00 » transparaît.
- `.voile`, `.feuille` sans `z-index` : le trait « maintenant » (z 2) passe au-dessus du voile.
- `.puce::after` n'élargit pas : une puce icône reste sous 44 px.
- `.entete-actions { margin-right: -10px }` colle Copilote au bord s'il est dernier.

Non vérifié : vrai iPhone (Safari, `text-wrap: balance` = 17.5), lecteur d'écran.

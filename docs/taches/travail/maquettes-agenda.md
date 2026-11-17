# Maquettes de l'Agenda (L3 n°8) — tour 2

8 fichiers `maquettes/agenda-*.html` (régénérés d'une seule source de données), `maquettes/ecrans-agenda.css` (réécrit,
sans les rustines du tour 1), 32 captures re-rendues après la dernière version de `taches.css` (06:10). Mesure par
script, 8 fichiers × 4 rendus : 0 texte sous 4,5:1, 0 cible sous 44 px. Aucune couleur littérale.

## Scénario (SCENARIO.md)
Mardi 24, 09:41 (heure de la tuile, « 1 sur 5 »). Toute la journée : « Visite technique à Témara » + « Confirmer la
réservation du stand » ★. Blocs : rails 08:30 (fait), devis 09:00-11:00 ★, fournisseur 10:00, « Rappeler pour le devis »
10:30 (ERP). Les 5 gardées pèsent 4 h 15 : durées de « Confirmer… » (30 min) et « Relire… » (45 min) = estimations posées
par moi. À trier 5. Recrutement en vert.

## Corrections appliquées (critique tour 2)
- **P1** charge vraie : échelle de 6 h, repère à 4 h, fantôme non plafonné, ambre au-delà ; tournure unique « X pour 4 h »
  (Planifier, Semaine, Mois). Jeudi est le seul jour où la tâche tient (4 h pour 4 h).
- **P2/P3** Planifier iPhone : jours à plat, cibles sur `--tch-selection`, sans « + » ; seule la tâche choisie est
  cerclée ; week-end en une rangée de deux cibles. **P4** « Placée jeu. 26 · Annuler » dans le volet.
- **S1** jour courant sans fond ; **S2/M2/P5** non travaillé vide à 64 px (bureau) ; non travaillé = `--muted` 50 % partout.
- **J1** bande « Toute la journée » sur une rangée défilante, sans ligne de date. **J4/J5** blocs faits sans fond ;
  ouverture à l'heure − 30 min, calée sur l'heure pleine (09:00).
- **T4** le bouton Ajouter est au bout de la barre « À placer », dans les 4 vues : il ne recouvre plus rien.
- **V1** À venir bureau : liste à gauche, « À placer » à droite. **V2-V4** segments fixes, une espace, échéances masquées.
- **S3-S7, M1, M3, H1-H4** : « +3 » au bout de la 2ᵉ ligne, barre retirée de Semaine, pas de drapeau, Mes projets
  replié en Jour / déplié en Semaine, « +2 » en texte, aujourd'hui choisi en Mois, « + 11:00 – 11:30 », consigne dans le
  flux, défilement sur l'heure pleine, « Placée à 13:00 · Annuler » sur bureau.
- **T1** en-tête loupe · Copilote · ⋯ ; barre d'état et barre latérale de 240 px reprises de `taches.css`.

## Tours
Passe A (tout régénéré), B (libellé de bande, puces de la barre, cascade, fantômes), C (barre latérale, `--tch-heure-h`
partagé, week-end sombre, Planifier en mode sans barre latérale, week-end sur une rangée), puis re-rendu final. Clair et
sombre, iPhone et bureau regardés à chaque passe.

## Écarts assumés
1. 88 px/h (désormais le jeton partagé).
2. Case dans les blocs, sauf blocs étroits et colonnes de semaine.
3. Planifier plein écran ; sur bureau, c'est un mode : la barre latérale s'efface.
4. Semaine bureau : les chevauchements passent en **cascade** (le second bloc part à 28 %). Côte à côte, chaque bloc
   faisait 64 px. En Jour, ils restent côte à côte. Les deux restent visibles, aucun n'est masqué (spec 3).
5. Mois bureau : des titres. 6. Férié en Mois seulement.

## Ce qui déplaît encore
- La barre d'état coûte 47 pt : Jour iPhone montre environ 4,5 h, pas 5,6.
- Bureau à 3 colonnes : en Semaine, les titres sont coupés (« Appeler le f… »).
- Les titres passés du Mois bureau se répètent (le réservoir est petit).
- À venir iPhone : les jours repliés sont sous la ligne de flottaison.
- Non vérifié sur un vrai iPhone.

**« Toucher puis poser »** se lit sans la consigne : les jours s'éclairent, une seule tâche est cerclée, et chaque jour
dit sa charge. La consigne reste comme filet.

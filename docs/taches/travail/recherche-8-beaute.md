# Recherche L3 n°8 — Beauté

Sources lues : HIG Apple (JSON officiel : typography, dark-mode, color, motion, widgets, accessibility), MDN browser-compat-data, Linear, MacStories (Things 3), web.dev, Evil Martians (OKLCH), Radix Colors, WCAG 2.2, NN/g, jetons Material 3. Jetons ERP : `recherche-8-design-existant.md`.

## 1. Ce qui rend une app de tâches belle
**Constat.** Les Apple Design Awards 2025 n'ont couronné aucune app de tâches ; Apple ne donne de raisons que pour les gagnants (Taobao, CapWords, Feather, Play), pas pour les finalistes iA Writer et Mela (newsroom Apple). Things a reçu un prix en 2017 (source secondaire). Les raisons publiées de la beauté viennent donc des revues et des concepteurs : Things = espace blanc dominant, titres gras, couleur « en touches » sur surfaces neutres, la couleur d'un calendrier reste sa couleur, tâche touchée = elle se soulève en carte, appui long = elle sort de la liste, retours haptiques (MacStories). Linear = moins de bruit visuel, alignement « senti plus que vu », contraste relevé, élévation calculée en LCH (Linear). Tiimo (iPhone App of the Year 2025, App Store Awards) : « planificateur visuel », liste et calendrier d'un seul esprit (presse, secondaire). Structured : une colonne de temps ; critique : illisible quand beaucoup de tâches courtes s'empilent.
**Règles communes (8).** (1) Un seul premier plan par écran. (2) Hiérarchie par taille/graisse/couleur de texte, pas par boîtes. (3) Couleur rare et porteuse de sens. (4) Contraste haut, surfaces par élévation. (5) Alignement strict sur grille 4 px. (6) Mouvement bref, tied au geste, jamais bloquant. (7) Retour physique (soulèvement, haptique) plutôt que décor. (8) Liste et temps dans un même langage visuel.

## 2. Typographie
**Constat.** HIG : défaut iOS 17 pt, minimum 11 pt ; éviter les graisses légères ; peu de polices ; ajuster poids/taille/couleur pour la hiérarchie ; interligne serré admis dans une ligne de liste, jamais à partir de 3 lignes. Styles iOS (taille/interligne) : Large Title 34/41, Body 17/22, Subhead 15/20, Footnote 13/18, Caption 12/16. `tabular-nums` aligne les chiffres mais dépend de la police (MDN) ; `.tabular-nums` existe déjà (`tokens.css:718`).
**Règle.** Archivo (display) pour le seul titre de page ; Hanken pour tout le reste. Heures, durées, compteurs : toujours `.tabular-nums`. Poids : 400, 500, 600, 700 seulement. Un titre de tâche tient sur 2 lignes max (puis tronqué, détail dans la fiche).

## 3. Couleur
**Constat.** HIG : ne pas dépendre de la couleur seule ; contraste ≥ 4.5:1, viser 7:1 pour le petit texte ; fonds « base » sombres et « élevés » plus clairs ; ne pas imposer de réglage d'apparence propre à l'app (l'ERP en a un, mode `system` disponible). WCAG 1.4.11 : 3:1 pour les composants et pastilles porteurs de sens. Le sombre de l'ERP est déjà un navy sans noir pur (`tokens.css:415`) ; la page Apple n'interdit pas le noir pur. OKLCH : la clarté `L` reste prévisible d'une teinte à l'autre, à la différence de HSL ; garder L et C constants et ne varier que la teinte donne des couleurs d'égale présence ; `oklch()` supporté Safari 15.4 (MDN). Radix : échelle de 12 paliers aux rôles fixes (fonds 1-2, composants 3-5, bordures 6-8, plein 9-10, texte 11-12).
**Règle.** Neutres + un accent d'app ; la couleur de projet vit sur un point, une barre de 3 px ou un bloc d'agenda, jamais sur toute la ligne ; priorité = glyphe/poids, pas couleur seule. Rouge réservé à « en retard » et aux actions destructives.

## 4. Espace, densité, rythme
**Constat.** HIG Layout : grouper par espace négatif, conteneurs ou séparateurs ; espacements constants. Cible tactile 44×44 pt (HIG Accessibility). L'ERP a déjà `data-density` confortable/compacte.
**Règle.** Grille 4 px. Séparer par espace (8 px entre lignes, 24 px entre sections) et non par traits ; pas de trait entre lignes sauf liste dense. En-têtes de section collants, sans fond plein en dessous de 16 px de marge. Ligne confortable 52 px, compacte 44 px (jamais moins au tactile).

## 5. Mouvement
**Constat.** HIG : motion « purposeful », bref et précis, éviter sur les interactions fréquentes, annulable (ne jamais faire attendre), alternative non animée. web.dev : seuls `transform` et `opacity` évitent layout et paint ; ne pas promouvoir inutilement (`will-change`). Support (MDN BCD, vérifié par script) : `@starting-style` Safari 17.5 ; `transition-behavior: allow-discrete` 17.4 ; transition de `display` 18 ; `document.startViewTransition()` 18 ; `@view-transition` inter-documents 18.2 ; Safari iOS = mêmes versions (clé « mirror »). Material 3 publie des durées de 50 à 400 ms par pas de 50 ; standard `cubic-bezier(0.2,0,0,1)`, emphasized-decelerate `(0.05,0.7,0.1,1)`, emphasized-accelerate `(0.3,0,0.8,0.15)`. L'ERP a déjà `--motion-fast/base/slow` = 120/180/260 ms, annulés sous `prefers-reduced-motion` (`tokens.css:1047`).
**Règle.** Toute durée passe par `--motion-*` (donc 0 ms en mouvement réduit) ; seules deux courbes sont ajoutées. Tableau au §« Langage ».

## 6. Plaisir discret
**Constat.** Le socle déconseille points et confettis ; `celebrate.js` est réservé à « signé ». Todoist a un Karma à niveaux (pages Todoist) ; NN/g : un état vide dit l'état, apprend, ouvre un chemin d'action.
**Règle.** Réussite = case qui se remplit + haptique 10 ms (`hapticTap`, muet sur iOS Safari, donc jamais seul) + anneau du jour qui avance. « Journée faite » = pictogramme calme, une phrase factuelle, une action (« Voir demain »). Aucun son, aucune célébration par tâche.

## 7. Agenda lisible
**Constat.** Fantastical : bandeau de jours au-dessus d'une liste unifiée événements+tâches ; semaine médiocre avec chevauchements (presse). Notion Calendar : vue 3 jours jugée « voulue » (anecdote d'un utilisateur). Structured : bloc court = ruban illisible.
**Règle.** Téléphone : Jour (défaut) et 3 jours ; 7 jours défilables = AVANCÉ ; mois = points (3 max + « +n »). Bureau : semaine 7 jours. Grille : trait d'heure 1 px, pas de trait de demi-heure. Heure courante : trait 2 px accent + point de 8 px. Bloc de 30 min = 28 px de haut (heure 56 px), une ligne de titre 12 px semi-gras ; sous 28 px, le bloc devient pastille.

## 8. Tuile Scriptable
**Constat.** HIG Widgets : équilibrer la densité, un seul sujet, contenu qui change dans la journée, ne pas recopier l'icône, ne pas imiter le widget dans l'app, éviter les mises en page d'app, afficher l'heure de mise à jour si elle peut être périmée, textes lisibles (min 11 pt), rendu clair/sombre/teinté.
**Règle.** Moyenne : « Aujourd'hui » + 3 lignes (heure tabulaire, titre sur 1 ligne) + « n restantes ». Grande : bloc en cours + 6 lignes. Jamais de notes (socle §2.5). Vide : « Rien de prévu » + prochaine échéance. Pied : « mis à jour hh:mm ».

## 9. Cohérence avec l'ERP
**Constat.** Linear : une famille de police (Inter ; Inter Display pour les titres), standards Apple en repère. Rappels, Notion Calendar : non vérifié.
**Règle.** Mêmes jetons, mêmes primitives `@/ui` ; personnalité = accent de module (`--module-accent-azur`), Archivo sur les titres de page, mouvement plus soigné que le reste de l'ERP mais dans les mêmes durées. Le bouton primaire reste laiton.

## 10. Fautes de goût
Voir la liste finale ; elle s'appuie sur HIG, WCAG, NN/g, mais l'énumération est un jugement, non une étude.

---

# LE LANGAGE VISUEL PROPOSÉ

**Échelle (mobile / bureau).** Titre de page 1,75 rem/1,2, 700, `-0,02em` (jeton h2). Section 1 rem/1,3, 600 (1,0625 rem sous 768 px = Body iOS 17). Tâche 1 rem/1,35, 400 (1,0625 rem mobile). Méta 0,875 rem muted. Heures/compteurs 0,75 rem, 500, tabulaires. Aucun texte sous 12 px.
**Ligne de tâche.** 52 px (compacte 44), padding vertical 15 px, marge de page 16 px (24 bureau). Case ronde 22 px, zone tactile 44×44. Aucun trait, aucune ombre ; survol/pression = fond `--muted` à 60 %. Max 2 métas colorées par ligne (échéance en retard rouge, projet en point).
**Rayons.** Ligne 0 · bloc d'agenda 8 px · carte/feuille 16 px · pastille 999 px. Icônes lucide, `strokeWidth` 1,75 partout (2 dans la barre d'onglets), 20 px en ligne.
**Palette projet (OKLCH, vérifiée par calcul : dans le gamut sRGB ; contrastes WCAG calculés).** Teintes : terre 55 · ambre 85 · olive 115 · vert 150 · menthe 180 · ciel 215 · bleu 250 · indigo 285 · prune 320 · rose 355. Le rouge (25) est exclu.
| Rôle | Clair (sur blanc) | Sombre (sur `--card` 19,3 %) |
|---|---|---|
| Point/barre | `oklch(.64 .105 H)` ≥ 3,1:1 | `oklch(.72 .115 H)` ≥ 7:1 |
| Fond de bloc | `oklch(.955 .02 H)` | `oklch(.28 .045 H)` |
| Texte sur bloc | `oklch(.46 .08 H)` ≥ 6:1 | `oklch(.83 .085 H)` ≥ 8,4:1 |
Le nom du projet accompagne tout point.
**Mouvement (tout par `--motion-*`).**
| Geste | Durée | Courbe | Propriétés |
|---|---|---|---|
| Appui / survol | 120 | standard `(.2,0,0,1)` | opacity, fond |
| Cocher (remplissage + trait) | 180 | standard | transform, opacity |
| Barré puis attente | ligne reste 1,2 s avec « Annuler » | — | — |
| Sortie de ligne faite | 260 | accélérée `(.3,0,.8,.15)` | opacity + translateX ; refermeture par `grid-template-rows` (seule exception layout) |
| Ajout d'une ligne | 260 | décélérée `(.05,.7,.1,1)` | opacity + translateY 8 px, `@starting-style` |
| Feuille ouverte / fermée | 260 / 180 | décélérée / accélérée | transform |
| Réordonner : soulèvement | 120 | standard | transform scale 1,02 + `--shadow-md` |
| Jour → jour | 260 | standard | View Transition (Safari 18), sinon instantané |
Durées = propositions, à régler sur l'appareil. Mouvement réduit : 0 ms, état final seulement.
**Usage de la couleur.** Une couleur d'accent par écran (heure courante, sélection, focus). Priorité haute = glyphe « ! » + poids 600, pas de teinte. Rouge = retard et destructif. Surfaces sombres : `--background` navy, cartes +3,6 L, jamais de noir pur.
**États vides.** Pictogramme lucide 48 px, trait 1,5 px, deux tons (muted + accent), sans mascotte ni banque d'images ; 1 phrase factuelle ; 1 bouton. Journée faite : anneau plein + « Tout est fait pour aujourd'hui ».

# LES 12 FAUTES À NE PAS COMMETTRE
1. Un trait ou une carte autour de chaque tâche.
2. Plus de 2 badges colorés par ligne.
3. Ombres lourdes sur des lignes de liste.
4. Une icône devant chaque libellé.
5. Texte secondaire sous 4.5:1 (HIG).
6. Animation de plus de 300 ms ou qui retient la main.
7. Une modale pour une saisie simple : feuille basse ou saisie en place.
8. Rouge hors retard/destructif.
9. Points, séries, confettis par tâche.
10. Cible tactile sous 44 px.
11. Sens porté par la seule couleur (WCAG, HIG).
12. Chiffres proportionnels : une heure qui saute à chaque mise à jour.

# NON VÉRIFIÉ
- Raisons d'Apple pour Things/Tiimo/Structured : aucune page Apple lue ; Things 2017, Tiimo, Structured 2026 viennent de sources secondaires.
- Durée et courbe exactes de la case de Things : aucune source primaire trouvée.
- Notion Calendar, Amie, Todoist (design), Apple Rappels : rien de primaire lu.
- Hanken/Archivo contiennent-elles `tnum` : non testé.
- Version d'iOS du téléphone du fondateur (conditionne View Transitions, Safari 18) : inconnue.
- Chiffres de lisibilité (52 px, 28 px, 1,2 s, 8 px) : choix de conception, non issus d'une étude.
- Palette : contrastes calculés par moi, non revus à l'écran ni en daltonisme.
- Contraste dans le mode contraste augmenté d'iOS : non traité.

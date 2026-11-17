# Critique visuelle — Projets, Rythme, Copilote, tuile (L3 n°8, contradiction)

Jugé sur les PNG de `maquettes/captures/` : iPhone clair + sombre des 12 écrans ; bureau clair + sombre de
projets-liste, projet-liste, projet-tableau, projet-chronologie, rythme, revue-semaine, copilote. Références :
`ecran-aujourdhui-matin-iphone-clair`, `composants-1-iphone-clair`. Bureau de planifier, mon-iphone, tuile, cockpit :
non ouverts (non demandés).

## projets-liste — 6,5/10
**Préserver** : liste à plat ; priorité mot + barres (lisible sans légende) ; « À planifier » azur ; « Nouveau projet »
visible à mi-écran ; panneau bureau = vrai projet.
- **MAJEUR** `projets-liste-iphone-clair` : le camembert a la place et la taille d'une case ; « Site web » (0 %) est un
  rond vide identique à une case. Correction : point de couleur 10 px sur la 1re ligne + mini-barre 48 × 4 px après
  « 12 sur 18 ».
- **MAJEUR** même capture : deux « + » (pastille de « Nouveau projet », bouton flottant) pour deux actions.
  Correction : `folder-plus` 20 px sans pastille devant « Nouveau projet ».
- MINEUR : camembert et puce centrés sur 3 lignes (Chantier Benali) ; aligner sur la 1re ligne (spec 8 §2).
- MINEUR : « 12 sur 18   échéance 4 déc. » sans séparateur ; « 12 sur 18 · échéance ven. 4 déc. » (spec 7 §4).
- MINEUR : en-tête loupe · ⋯ · Copilote ; Aujourd'hui fait loupe · Copilote · ⋯. Prendre ce dernier.

## projet-liste — 6,5/10
**Préserver** : titre + point, puce Haute, barre fidèle (12/18 mesuré), jalon losange, « attend : … » en pointillé ;
santé juste (6 restantes à 8 par 20 jours = 15 jours ; 10 jours travaillés du 23/11 au 4/12).
- **MAJEUR** `projet-liste-iphone-clair` : la santé est un panneau de 3 lignes, le plus lourd sous le titre, et repousse
  Clôture et Faites sous le pli. Correction : une ligne sans fond, icône 14 px, « À ce rythme : 15 jours travaillés, il
  en reste 10 » (formule de la Chronologie), le détail au toucher.
- MINEUR : « …le PV de réce… » coupé en plein mot ; montrer « Fini quand… ⌄ » seul.
- MINEUR `projet-liste-bureau-clair` : le menu ⋯ répète « Vue : Liste / Tableau / Chronologie » à côté du segmenté
  (retirer) ; « Terminer le projet… » porte le drapeau de la priorité haute (`circle-check`).

## projet-tableau — 6/10
**Préserver** : puces d'étapes + bord de la colonne suivante ; « 2 faites » replié ; « Ajouter » par colonne.
- **MAJEUR** `projet-tableau-iphone-clair` : titres courts cassés (« Commander les rails de / fixation ») : colonne de
  306 px, texte décalé de 78 px. Correction : colonne = largeur − 48, marge de carte 12 px, titre 16 px.
- **MAJEUR** `projet-tableau-bureau-clair` : la colonne des projets passe de 470 px (Liste) à 345 px ; « Recrutement
  technicien » s'empile sur 4 lignes, les cartes cassent aussi. Correction : 360 px fixe, tableau défilant.
- MINEUR : puce active noire (clair) / blanche (sombre) ; la sélection est azur ailleurs.
- MINEUR : « Matériel » deux fois et trois indicateurs de position (puces, bord, points). Supprimer le titre de colonne
  sur iPhone (« 2 sur 5 » à droite des puces) et les points.

## projet-chronologie — 7/10
**Préserver (le meilleur du lot sur iPhone)** : frise verticale, aujourd'hui azur, étapes en barre de couleur, jalon
losange, échéance carrée, « Sans date » en bas. Pas un Gantt.
- **MAJEUR** `projet-chronologie-bureau-clair` : c'est un Gantt (escalier, colonne de libellés, nom écrit deux fois) ;
  « Études » semble commencer le 16 nov. au lieu du 2. Correction : sans colonne de gauche, « Matériel · 2 sur 5 » dans
  la barre, bord gauche ouvert « ← 2 nov. », sans « sem. 47 ».
- MINEUR : « 2 – 18 nov. » (tiret) contre « lun. 23 → jeu. 26 » (flèche) : flèche partout.
- MINEUR : bouton flottant sur le panneau « Sans date » : 88 px de marge basse.
- MINEUR `…-bureau-sombre` : fonds ambre au brun ; filet seul sur `--muted`.

## projet-planifier — pas 1 : 7,5/10 · pas 2 : 6,5/10
**Préserver** : trois questions sur un écran ; « Le 20 déc. est un dimanche : échéance au lundi 21 » ; tuiles de
priorité expliquées ; « Suivant » au pouce ; carte « Copilote · à valider » avec case et × par ligne. Deux minutes :
oui. Envie : oui, grâce au Copilote.
- **MAJEUR** `projet-planifier-2-iphone-clair` : « pas 2 sur 3 », 3 segments, mais le bouton dit « Terminer ».
  Correction : « pas 2 sur 2 », 2 segments.
- **MAJEUR** même capture : puce « Plus tard », terme interdit (§3, En réserve). Correction : « En réserve ».
- MINEUR pas 1 : deux styles de sélection (puce pleine « 1 mois », tuile en contour « Moyenne ») ; un seul.
- MINEUR : segment 2 gris plein, segment 3 en contour ; gris plein pour « à venir ».
- MINEUR `…-2-iphone-sombre` : carte plus sombre que la page (élévation inversée).

## rythme — 7/10
**Préserver** : anneau « 3 sur 5 », « passer à 6 ? » en tête avec sa source, objectif pointillé, aujourd'hui en
contour, week-end absent, modes expliqués (« Proposé, jamais imposé »). Ni points ni série : ne culpabilise pas. Au
bureau, « Ce que j'ai remarqué » + action (« Faire du vendredi un jour court ») = l'outil qui comprend et pousse.
- **MAJEUR** `rythme-iphone-clair` : « Les 14 derniers jours » sur 10 barres ; la proposition compte du 6 au 19 nov.,
  le graphique montre du 9 au 20 : « 5 jours sur 10 » ne se recompte pas (le 6 manque). Correction : « Les 10 derniers
  jours travaillés », du 6 au 19 + aujourd'hui.
- **MAJEUR** même capture : sur iPhone, les constats sont sous les trois modes, hors écran ; la preuve qu'il comprend
  ne se voit pas. Correction : graphique → « Ce que j'ai remarqué » (1 constat + action) → Mode.
- MINEUR : le « 4 » de m10 et m17 est barré par le pointillé (tour 2 dit corrigé). Fond `--card` sous les chiffres.
- MINEUR : deux phrases « N tâches N jours sur 10 » empilées. Source : « Objectif du jour : 5 · depuis le lun. 2 nov. » ;
  bouton « Passer à 6 » (le « Oui » de 58 px pèse moins que « Pas maintenant » en gras).
- MINEUR `rythme-bureau-clair` : « (34 et 31 lignes) » : jargon ; « Le matin, tu finis 82 % de ce que tu prévois ;
  après 16 h, 48 %. »

## revue-semaine — 5,5/10
**Préserver** : 4 faits sans jugement ; carte en pile ; Avancé / Attend / Prochaine action ; « Planifier ma semaine »
au pouce.
- **MAJEUR** `revue-semaine-iphone-clair` contre `rythme-iphone-clair` : le graphique donne 21 faites (7+4+5+2+3) et
  l'objectif atteint 2 jours ; la revue dit 26 et « 3 sur 5 » (la semaine précédente, 23, concorde). Correction : 21,
  2 sur 5.
- **MAJEUR** `revue-semaine-bureau-clair` : 5 cartes × 4 boutons = 20 boutons ; « Suivant » et « 1 sur 5 » n'ont pas de
  sens quand tout est visible. Correction : Garder · Pause · Terminer en segmenté, Garder présélectionné.
- MINEUR iPhone : quatre boutons de même poids ; même segmenté + « Suivant » seul.
- MINEUR : « Projet de la semaine » avec un rond de case ; étoile contour.
- MINEUR : intertitres en capitales espacées, absents ailleurs ; 14 px 600, casse normale.
- MINEUR bureau : « · » pendant en fin de ligne avant « à surveiller ».

## copilote — 7/10
**Préserver** : la carte reprend la ligne des écrans (case, titre 17, échéance rouge, point + projet) ; une raison
par ligne ; « Rien ne change tant que tu ne gardes pas » ; « Garder ces 5 » express (T2) ; 4 demandes (A12).
- **MAJEUR** `copilote-bureau-clair` : l'écran derrière est périmé et contredit la carte : « 4/6 », « plan 3/5 »
  (écartés par M2), objectif 6 contre 5, « Confirmer la réservation » déjà en Essentiel mais reproposée, visite à
  14:00 (N4). Correction : poser le panneau sur l'Aujourd'hui du matin.
- MINEUR `copilote-iphone-clair` : « échéance lun. 23 / mar. 24 » en gris ; la référence les met en `--foreground` 500.
- MINEUR : les 4 tuiles (une icône chacune, faute 4) restent et la bulle répète « Planifie ma journée » ; replier en une
  rangée de puces texte de 36 px.

## mon-iphone — 7/10
**Préserver** : « 2 sur 5 » + étapes numérotées ; preuves horodatées (« test reçu à 09:12 ») ; « Chacun se défait
ici ». Rassurant.
- **MAJEUR** `mon-iphone-iphone-clair` : Siri en jargon (« Obtenir le contenu de l'URL », « jeton », « en-tête »).
  Correction : bouton pleine largeur « Installer le raccourci » (A14 M5, il demande le jeton, N12) ; étapes repliées
  sous « Le faire à la main ».

## tuile — 6,5/10
**Préserver** : tailles et rayons de vrais widgets, « 2 sur 5 » en gros, segments d'Aujourd'hui, titres sur une
ligne, sombre soigné. Lisible en 2 secondes.
- **MAJEUR** `tuile-iphone-clair` : ronds de case sur un widget non interactif : on croit cocher, le toucher ouvre
  l'app. Correction : point de projet 8 px.
- **MAJEUR** même capture : « Visite technique à Témara 14:00 », Aujourd'hui dit « Toute la journée » (N4).
  Correction : « journée ».
- MINEUR moyenne : 4 éléments dans l'en-tête ; « maj 09:41 » au pied, et « + 3 » (6 à faire, 3 montrées).
- MINEUR : drapeau devant « Échéance » = glyphe de priorité haute ; `calendar-clock`, « échéance ven. 27 ».
- MINEUR grande : 100 px vides avant un pied tronqué (« Déposer le dossie… »).

## cockpit-carte — 7,5/10
**Préserver** : même ligne, « Ouvrir Aujourd'hui → », « + 1 autre ».
- MINEUR : anneau ici, segments sur Aujourd'hui et la tuile pour le même « 2 sur 5 ».
- MINEUR : 1re ligne : méta sur deux lignes ; marge intérieure 16 px au lieu de 32.
- MINEUR : « 4 à faire » ici, « 6 à faire » sur la tuile.

## Verdict sur les écarts assumés
1 Fini quand replié : oui, sans coupe en plein mot. 2 « attend : » : oui (§3). 3 « Suivant » par carte : oui sur
iPhone, NON au bureau. 4 Termes : oui. 5 Proposition en tête : oui, constat aussi avant Mode. 6 Tâche en tuile au
Tableau : oui, titres sur 1 ligne. 7 Santé en puce : oui, à étendre à la Liste. 8 Étape 5 : oui. 9 « 2 sur 5 · 4 à
faire » : oui, chiffres alignés sur la tuile. 10 Un fichier par pas : oui, indicateur à 2 pas.

## Défauts transversaux
- **Progression** : cinq formes pour « N sur M » (segments, anneau, camembert, barre). Journée = segments (anneau dans
  Mon rythme seul, A14) ; projet = barre.
- **Rond de case hors tâche** : camembert vide, « Projet de la semaine », tuile.
- **Drapeau** à trois sens : priorité haute, échéance, Terminer le projet.
- **Sélection** noire, blanche, azur pleine ou en contour selon l'écran ; azur (spec 8 §4).
- **Chiffres incohérents entre écrans** : 26/21, 3/2 jours, 6/4 à faire, 4/6 contre 5, visite à 14:00.
- **Capitales** (revue, carte Copilote, menu « VUE ») contre sections en casse normale.
- **Sombre** : ambre au brun ; carte plus sombre que la page.

## Les 10 corrections qui changeraient le plus le résultat
1. Projets : point + mini-barre au lieu du camembert-case ; `folder-plus` devant « Nouveau projet ».
2. Santé d'un projet : une ligne sans fond, « À ce rythme : 15 jours travaillés, il en reste 10 ».
3. Planifier : « pas 2 sur 2 », « En réserve » au lieu de « Plus tard ».
4. Mon rythme : graphique sur la fenêtre de la proposition, titre exact ; un constat avant Mode ; « Passer à 6 ».
5. Revue : Garder présélectionné en segmenté ; au bureau, sans Suivant ni compteur.
6. Chiffres cohérents d'un écran à l'autre (revue, tuile, cockpit, fond du Copilote, visite sans heure).
7. Tuile : point de projet au lieu de la case, « maj » au pied, « + 3 ».
8. Une forme par idée : segments pour la journée (cockpit compris), barre pour un projet.
9. Tableau : colonne des projets à 360 px au bureau, titres sur une ligne sur iPhone, sélection azur.
10. Chronologie bureau : sans colonne de libellés, Études ouverte à gauche, sans numéros de semaine.

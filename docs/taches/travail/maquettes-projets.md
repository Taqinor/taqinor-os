# Maquettes rendues — Projets, Rythme, Copilote, tuile (L3 n°8)

`docs/taches/maquettes/` : 12 écrans HTML + `ecrans-projets.css` (jetons existants seulement, réécrite au tour 4) ;
48 PNG dans `captures/`. Chiffres et formes : `SCENARIO.md` (mardi 24 novembre). Dernier rendu fait sur le
`taches.css` corrigé par sa lane. Mesure (couleurs calculées, partie visible, 48 vues) : 0 texte sous 4,5:1,
0 sous 12 px, 0 cible sous 44 px ; le fond voilé sous un dialogue n'est pas mesuré.

## Tour 4 (critique visuelle + scénario unique), écran par écran
- **projets-liste** — point de couleur sur la 1re ligne, barre fine `.barre-avance`, puce de priorité alignée ;
  `folder-plus` devant « Nouveau projet » (seul « + » : le bouton flottant). Bureau : `.page.trois` (barre latérale ·
  projets · projet ouvert), « Nouveau projet » vit dans la barre latérale.
- **projet-liste** — santé sur une ligne sans fond (« À ce rythme : 15 jours travaillés, il en reste 8 », 8 = jours
  travaillés du 25/11 au 4/12) ; « Fini quand… ⌄ » seul ; ⋯ sans le groupe Vue, Terminer = `circle-check`.
- **projet-tableau** — iPhone : colonne = largeur − 48, titres sur une ligne, plus de titre de colonne ni de points,
  puce d'étape azur. Bureau : barre latérale fixe, colonnes de 264 px, tableau défilant.
- **projet-chronologie** — bureau : une seule piste, étapes bout à bout avec leur nom dedans, détail dessous, Études
  ouverte « ← 2 nov. », jalon au-dessus, aucun numéro de semaine : plus un Gantt.
- **planifier** — « pas N sur 2 », 2 segments ; « En réserve » ; une seule sélection (azur plein, puces et tuiles) ;
  la carte du Copilote n'est plus plus sombre que la feuille.
- **rythme** — segments (plus d'anneau), « Les 10 derniers jours travaillés » du 9 au 23 (mer. 18 férié, sans
  barre), 6 jours sur 10, 48 faites ; « Passer à 6 » en bouton plein ; un constat avant le choix du mode.
- **revue-semaine** — 21 faites en 4 jours, 3 sur 4 ; Garder · Pause · Terminer en segmenté, Garder présélectionné ;
  « Suivant » et « 1 sur 5 » sur iPhone seulement ; étoile pour « Projet de la semaine » ; intertitres en casse normale.
- **copilote** — posé sur l'Aujourd'hui du matin ; 4 demandes en puces texte ; « Garder ces 3 » et la MÊME ligne
  proposée que l'écran (puce « Garder » en tête de méta).
- **mon-iphone** — « Installer le raccourci » pleine largeur, la manière manuelle repliée ; `.interrupteur` partagé.
- **tuile** — 1 sur 5 à 09:41, point de projet au lieu de la case, visite « journée », « + 3 autres », « maj 09:41 »
  au pied, échéance en `calendar-clock`.
- **cockpit-carte** — segments, « 3 sur 5 · 2 à faire », 2 à faire + 1 faite.

Tours de ce passage : 3 rendus regardés (tour 4, 4b, 4c), puis un rendu final après le nouveau `taches.css`.
Cassé par lui puis corrigé : double décalage de la barre d'état (déjà posé par `.barre-statut ~ .page`), classe
`.tuile` du sélecteur Quand qui écrasait mes segments de tuile.

## Tour 5 (second critique : 8 écrans prêts, 4 repris)
- **projets-liste** (M1) : « Nouveau projet » azur + dossier-plus dans la barre latérale, et la rangée de l'iPhone en
  fin de liste dans la colonne du milieu ; séparateur « · » dans la méta ; « Basse » au même fond.
- **tuile** (M2) : moyenne = une rangée d'en-tête (« Aujourd'hui » · « 1 sur 5 » · segments), 16 pt partout, pied
  « + 3 autres · maj 09:41 » décollé ; une icône (repère, téléphone) pour les lignes de l'ERP, plus d'anneau ; grande :
  « maj » en haut à droite, « Valider le plan de calepinage · échéance jeu. 26 » au pied, remplissage retiré.
- **revue-semaine** (M3) : état du ven. 20 au soir (Benali 10 sur 18, Salon 2 sur 11) ; Recrutement : faites « Définir
  le profil recherché » et « Publier l'annonce », en attente « Planifier les entretiens · attend : Trier les CV reçus »,
  prochaine « Trier les CV reçus » ; trois chiffres, le férié en note ; cartes non étirées au bureau.
- **projet-tableau** : colonnes en 1fr (Études 180 px), retrait du titre réduit : titres sur une ligne au bureau.
- Mineurs : méta du cockpit sur une ligne ; « 6 jours sur 10 » dit une seule fois (carte du rythme).
- « attend : … » rétabli partout (spec 7 §3, `textes.md` §1).
Trois tours rendus et regardés ; contrôle : 0 contraste faible, 0 texte sous 12 px, 0 cible sous 44 px (48 vues).

## Retiré de `ecrans-projets.css` (devenu partagé)
Barre d'état et indicateur maison, segments, mini-barre, point de projet, interrupteur, style de puce choisie,
mise en page bureau à deux colonnes, anneau et camembert, toutes les surcouches des tours 1 à 3.

## Ce qui me déplaît encore
- iPhone, projet en Liste : « Clôture » et « Faites » restent sous le pli.
- Chronologie iPhone : le point « Aujourd'hui » vient après Matériel (tri par début), alors qu'il tombe dedans.
- Tableau bureau : la dernière colonne est coupée (défilement voulu, mais sans indice).
- Non vérifié : vrai iPhone, Scriptable réel (SF au lieu de Hanken), daltonisme.

## Écarts assumés
1. « Fini quand… » replié (Détails, spec 7).
2. (levé) « attend : … » rétabli partout (spec 7 §3, `textes.md` §1) ; « Après… » interdit.
3. Revue : « Suivant » par carte sur iPhone seulement ; « Passer » quitte la revue.
4. « Proposé pour aujourd'hui », « objectif atteint » (termes interdits évités).
5. Rythme : proposition au-dessus du graphique.
6. Tableau : la tâche y est une tuile, titre sur une ligne.
7. Vues avancées : en-tête compact.
8. Mon iPhone, étape 5 « Ouvrir sur Aujourd'hui » (A13).
9. Site web « 0 sur 4 » et « À planifier » : le scénario prime, la spec 4 veut « À planifier » ⇔ 0 ouverte.
10. Un fichier par pas de Planifier.

## À reporter dans `taches.css`
- La classe `.tuile` (sélecteur Quand) est trop générique : elle a écrasé une autre classe. Préférer `.quand-tuile`.
- Ajouter une modification « pleine largeur » pour `.segments` (Mon rythme, tuile) au lieu de mon `.ep-plein`.

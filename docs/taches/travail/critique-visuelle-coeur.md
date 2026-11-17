# Critique visuelle contradictoire — écrans cœur (L3 n°8)

Méthode : `grille-visuelle.md`. Ouvertes : iPhone clair + sombre de chaque écran (+ `-bas`, `-menu`, `-rythme`) ;
bureau clair + sombre de matin, saisie, fiche, À trier, bilan ; `composants-1/2` iPhone. Non ouvertes, non jugées :
15 h / vide / retour au bureau, `saisie-liste` et planches au bureau. Recadrage agrandi : l'anneau du bilan vaut bien
≈ 60 % ; « 09:00 » est surimprimé par « 09:12 ».

## Aujourd'hui, 8 h 30 — 6/10
PRÉSERVER : sections sans boîtes (titres 650, tâches 400), rouge réservé à « échéance aujourd'hui », heures tabulaires
en fin de ligne, point + nom de projet, trait « maintenant » azur de l'agenda bureau.
- **MAJEUR** (`matin-iphone-*`) : pas de carte du moment ; « Garder ces N » est sous le pli (`matin-bas`), contre
  A17-M1. → État « rien gardé » : sous la progression, carte `--muted` rayon 16 « 5 proposées pour ton objectif » +
  bouton contour « Garder ces 5 ».
- **MAJEUR** (`matin-bas`) : « Garder ces 3 » faux : 4 ou 5 gardées ouvertes, N = objectif − gardées = 1 ou 0. → N
  calculé ; à 0, « Ton objectif est couvert » comme à 15 h.
- **MAJEUR** (`matin-bureau-*`) : 160 px vides à gauche, 184 px morts à droite, pas de colonne Projets (spec §4). →
  Colonne Projets de 240 px à gauche (celle d'À trier), agenda jusqu'à 24 px du bord.
- MINEUR : la visite est une ligne de Prévu ; N4 veut une bande « Toute la journée » avant Prévu.
- MINEUR : « essentiel 0/2 » deux fois. → Retirer le « 0/2 » de l'en-tête Essentiel.
- MINEUR : segments vides presque invisibles en clair. → `--muted-foreground` à 35 %.

## Aujourd'hui, 15 h — 7/10
PRÉSERVER : segments verts, ligne faite barrée en place, estampille « → jeu. 26 », « Ton objectif est couvert par ce
que tu as gardé. » + « Voir toutes les tâches de mes projets ».
- MINEUR (`15h-bas`) : « Faites » avant « À revoir » ; spec §4 (7) et le matin : À revoir, En attente, Faites.
- MINEUR : « échéance jeudi » en gris ; la planche 1 : « échéance lun. 23 » en `--foreground`. → « échéance jeu. 26 »,
  `--foreground` 500.
- MINEUR (`15h-iphone-clair`) : texte fantôme sous la barre d'onglets. → Transversal 1.

## Menu ⋯ — 7/10
PRÉSERVER : feuille d'actions au pouce, actions de l'écran en bas, « Fermer » détaché.
- MINEUR (`-clair`) : voile trop léger, la liste rivalise. → Transversal 6.
- MINEUR : une icône seule (plume d'« Alléger »). → La retirer ; le gras suffit.
- MINEUR (`-sombre`) : la séparation des deux groupes disparaît. → Bande de 8 px `--background`.

## Aujourd'hui vide — 8/10
PRÉSERVER : pastille 72 px, un seul bouton or, « Dicter » en texte, aucun bouton flottant concurrent.
- MINEUR : sous-texte en 3 lignes inégales. → 2 lignes, largeur max 30 ch.
- MINEUR : même pictogramme dans la pastille et le bouton. → Retirer celui du bouton.

## Retour de congé — 6/10
PRÉSERVER : une carte, une phrase, deux choix ; « Reprise ».
- **MAJEUR** (`retour-iphone-*`) : le bouton flottant couvre le « + » d'« Envoyer les badges exposants ». →
  Transversal 3.
- MINEUR : « Garder ces 3 » (fantôme en bas) alors que rien n'est gardé : N = 5.

## Saisie — 6/10
PRÉSERVER (iPhone) : jetons teintés dans le texte, puces « × », « Ajouter » or en bas à droite.
- **MAJEUR** (`saisie-bureau-*`) : modale centrée à cheval sur liste et agenda — faute 7. → Saisie en place : le champ
  « Ajouter une tâche » s'agrandit, puces dessous, liste poussée.
- MINEUR (`saisie-bureau-*`) : « 09:00 » sous « 09:12 ». → Masquer l'heure de grille à moins de 20 min du trait.
- MINEUR : contour pointillé du jeton « Nouveau projet » = code « En attente ». → Trait plein, fond teinté.
- MINEUR (`saisie-iphone-clair`) : voile trop faible. → Transversal 6.
- MINEUR : jeton « #Salon / Solaire Expo » coupé en deux lignes. → `white-space: nowrap` par jeton.

## Saisie, liste collée — 6/10
PRÉSERVER : « 6 tâches · 2 projets », cases d'aperçu carrées, « Coller encore » + « Créer 6 tâches » au pouce.
- **MAJEUR** : aucune puce de priorité par « Nouveau projet » (A17-M3, spec §8). → Puce « Moyenne ▾ » à la place du
  crayon (toucher le nom le renomme).
- MINEUR (`-sombre`) : en-têtes en bande pleine couleur projet (refusé, spec 8 §7), menthe lourde. → `--muted`,
  point 8 px + nom 650.

## Fiche — 8/10
PRÉSERVER : puces Quand · Échéance · Projet · Priorité, « Reporter à mer. 25 » + « Fait » au pouce ; au bureau,
panneau droit et ligne sélectionnée azur.
- MINEUR (`fiche-iphone-*`) : un ruban coupé du titre « Aujourd'hui » dépasse au-dessus de la feuille. → Cran à 100 %
  ou plus bas.
- MINEUR : points de check-list = case de tâche 22 px. → 18 px, trait 1,5.
- MINEUR (`fiche-bureau-*`) : Proposé a disparu (présent sur `matin-bureau`) et la liste glisse de 20 px. → Même liste,
  même x.

## Fiche, Plus — 7/10
PRÉSERVER : non renseigné en gris, renseigné en `--foreground`.
- **MAJEUR** : « Après… » est un mot interdit (spec §3 : « En attente de… » couvre une tâche) ; « Étiquettes » et
  « Jalon » manquent (spec §2). → Supprimer « Après… » ; En attente de… → Quelqu'un · Quelque chose · Une tâche ;
  ajouter « Étiquettes › » et « Jalon ».
- MINEUR : au défilement, la barre × ★ ⋯ perd le titre. → Titre 15 px 600 tronqué + filet.
- MINEUR (`-sombre`) : interrupteur éteint invisible. → Pouce `--foreground`.

## À trier — 6/10
PRÉSERVER (bureau) : gestes à droite, colonne Projets cible de glisser.
- **MAJEUR** (`a-trier-iphone-*`) : « Aujourd'hui · Demain · Projet… · ⋯ » en 17 px gras, 5 fois : plus lourds que
  les titres, l'œil lit les boutons avant les tâches. → 15 px, 500, `--muted-foreground`, marge haute 4 px.
- MINEUR : compte sous le titre (la date est au-dessus sur Aujourd'hui). → Au-dessus, 14 px 500.
- MINEUR : icône devant chaque provenance (micro, crayon, presse-papiers) — faute 4. → Texte seul.
- MINEUR (`a-trier-bureau-*`) : comptes de projets en azur ; « Convertir » à x 638, les autres à x 582. →
  `--muted-foreground` ; une colonne.

## Bilan du soir — 6/10
PRÉSERVER : « Valider » or pleine largeur ; « ✓ En réserve » qui remplace le bouton choisi ; un seul constat.
- **MAJEUR** (`bilan-iphone-*`) : « Tout reporter » devenu « Le reste → mer. 25 », lien hors de la 1re vue — le geste
  du parcours 8. → Bouton contour « Tout reporter à mer. 25 » dans l'en-tête « Restes », à la place du « 3 ».
- **MAJEUR** (`bilan-bureau-clair`) : anneau au bilan, segments juste derrière. → Transversal 4.
- MINEUR : « Fait » ici, « Faites » ailleurs. → « Faites ».
- MINEUR : « Reporter à mer. 25 » neutre ici, azur sur la fiche (spec 8 §4). → Azur.
- MINEUR : « (médianes) » est du jargon ; « Tu as tenu 5 tâches 5 jours sur 10 » se lit mal. → « Tu gardes souvent 6
  tâches et tu en finis 4. » ; « 5 jours sur 10, tu as fini tes 5 tâches : passer à 6 ? ».
- MINEUR (`-bas-sombre`, `-rythme-sombre`) : carte du constat fondue dans la feuille. → +4 % de L.
- MINEUR (`bilan-bureau-*`) : modale qui masque l'agenda. → Panneau droit, comme la fiche.

## Planches 1-2 — 8/10
PRÉSERVER : la ligne de référence — case sur la 1re ligne, ★ or, drapeau neutre, rouge seul pour « aujourd'hui »,
vert = fait, azur = sélection.
- MINEUR : pointillé à deux sens (« En attente » et jeton « Nouveau projet »). → Le réserver à « En attente ».

## Défauts transversaux
1. **Barre d'onglets translucide sans flou** (15 h, retour, menu) : texte fantôme dessous. → `--card` 92 % +
   `backdrop-filter: blur(20px)`, sinon opaque.
2. **Pas de titre compact au défilement** (`matin-bas`, `15h-bas`, `a-trier-bas`). → Barre 44 px, titre 17 px 600, filet.
3. **Bouton flottant sur des cibles** (retour ; Proposé, ★, heures partagent sa colonne). → `padding-bottom` 104 px,
   caché au défilement vers le bas, intersection bouton / cibles ajoutée au script de contrôle.
4. **Deux formes de progression.** → Segments partout ; au bilan, 5 segments de 24 × 8 px.
5. **Bureau** : bandes mortes, x de la liste qui change d'un écran à l'autre.
6. **Voile clair trop faible** (menu, saisie, fiche, bilan). → `--tch-voile` à 32 % de `--foreground`.
7. **N posés à la main** (matin, retour).
8. **Sombre** : surfaces confondues (constat, interrupteur, groupes du menu).
9. **Écarts à la planche** : échéance proche en gris ; « Reporter » neutre ou azur selon l'écran.
10. **Vocabulaire** : « Le reste → », « Après… », « Fait » / « Faites ».

## Les 10 corrections qui changeraient le plus le résultat
1. Matin : carte du moment en haut, « 5 proposées pour ton objectif · Garder ces 5 ».
2. N = objectif − gardées partout.
3. Bilan : « Tout reporter à mer. 25 » dans l'en-tête « Restes ».
4. Une seule forme de progression : les segments.
5. Saisie bureau en place, sans modale.
6. Bureau Aujourd'hui : colonne Projets à gauche, agenda jusqu'au bord, x fixe.
7. À trier : gestes en 15 px 500 `--muted-foreground`.
8. Bouton flottant : marge 104 px, caché au défilement, contrôle d'intersection.
9. Barre d'onglets floutée + titre compact au défilement.
10. Puce « Moyenne ▾ » par Nouveau projet collé ; Fiche Plus sans « Après… », avec Étiquettes et Jalon.

# Maquettes — unification (L3 n°8)

81 maquettes (70 écrans, 11 planches), une seule source pour les icônes, la coque et les données. 324 captures
re-rendues. Quatre lanes (agenda, projets, cœur, secondaires) ont aligné leurs écrans sur le scénario ; tout a été
re-vérifié et regardé ici.

## Ce qui est factorisé
- **Icônes** : `maquettes/icones.js`, sprite unique tiré des tracés de lucide-react par `outils/icones-generer.cjs`
  (68 icônes). Plus aucun `<symbol>` dans une page. `capturer.cjs` refuse un écran dont un `<use>` vise un symbole
  absent. (Régression d'origine : a99f38af3 a vidé le bloc `sprite` de 20 fichiers.)
- **Coque** : `maquettes/coque.js` pose barre d'état, barre latérale du bureau (256 px, « Nouveau projet » azur
  + dossier-plus, Mes projets comptés) et barre d'onglets. Les comptes viennent de l'heure (`SCENARIO.md` §7).
  Titre de page au bureau à y = 76 px partout (65 écrans ; revue = rituel, recherche = champ en tête).
- **Données** : `SCENARIO.md` réécrit — 18 tâches de Benali et 11 du Salon par étape, les 9, 10 et 4 des autres
  projets, la journée minute par minute (matin 08:30, 09:41, 15 h, bilan), la semaine du 23 au 29, les jours passés,
  la revue, les autres journées (2 et 3 nov., 7 déc.).
- **CSS** : `taches.css` reçoit les reports des lots (trait « maintenant » sous les blocs, bloc fait opaque,
  `.segments.plein`, `.quand-tuile`, toast à côté du bouton flottant, `.bouton[aria-disabled]`, échéance rouge
  sélectionnée en sombre, `.nav-item.nouveau`, panneau droit au jeton `--background`). Retirés : `.anneau`,
  `.camembert`, `.resume` et les doublons des quatre `ecrans-*.css`.

### Mode d'emploi (ajouter ou modifier une maquette)
1. `<head>` : `taches.css`, la feuille du lot, puis `<script src="icones.js" defer>` et `<script src="coque.js" defer>`.
2. `<body data-heure="15:00" data-onglet="aujourdhui">` (+ `data-pousse`, `data-projet`, `data-histoire` au besoin) et
   les trois emplacements `data-coque` ; jamais de barre écrite à la main.
3. Tout titre, heure, durée ou compte se lit dans `SCENARIO.md` à l'heure du body ; sinon, l'ajouter d'abord au scénario.
4. Nouvelle icône : `node outils/icones-generer.cjs`.
5. `node outils/verifier.cjs` (0 échec exigé), puis `node outils/capturer.cjs page.html` et regarder les PNG.

## Résultat de `verifier.cjs`
`81 maquettes × 4 vues : 0 échec(s).` Il contrôle : symbole absent ou icône vide, texte sous 4,5:1 (fond composité),
cible sous 44 px (`::after` compris), cible sous le bouton flottant ou sous les onglets hors du flux qui défile,
lexique interdit (`textes.md` §1 + « Passer à N »). Il a d'abord trouvé 181 échecs (« Passer à 6 », « en retard »,
« Clôture », échéance à 4,49:1, créneaux sous les onglets…), tous corrigés.

## Notes (grille visuelle)
| Écran | Fichier | Note |
|---|---|---|
| Aujourd'hui matin | ecran-aujourdhui-matin | 9 |
| Aujourd'hui 15 h | ecran-aujourdhui-15h (+ bas, menu) | 8,5 |
| Saisie (+ nouveau) | ecran-saisie, -nouveau | 9 |
| À trier | ecran-a-trier | 8,5 |
| Bilan (+ bas, rythme) | ecran-bilan… | 8,5 |
| Agenda Jour | agenda-jour | 8,5 |
| Agenda Semaine | agenda-semaine | 8,5 |
| Planifier (+ posée) | agenda-semaine-planifier… | 8,5 |
| Placer à une heure (+ durée) | agenda-placer-heure… | 8,5 |
| Mois · À venir | agenda-mois · agenda-a-venir | 8,5 · 8,5 |
| Projets | projets-liste | 8,5 |
| Un projet · Tableau · Chronologie | projet-liste · -tableau · -chronologie | 8,5 · 8,5 · 8 |
| Tuile | tuile | 9 |
| Revue | revue-semaine | 8,5 |
| Mon rythme | rythme | 8,5 |
| Copilote | copilote | 8,5 |
| Recherche · Réglages · Décaler | recherche · reglages · projet-decaler | 8,5 |
| Mon iPhone | mon-iphone | 8 |
| Premier usage, Mon rythme | premier-usage-4-rythme | 8 |

## Ce qui me déplaît encore
- Semaine : le trait « maintenant » passe sous le devis de 2 h ; il ne reste qu'un point et un bout de trait.
- Matin iPhone : le bouton flottant mord le drapeau de « Appeler le fournisseur » (pas une cible, le contrôle passe).
- Le « 09:00 » du devis fait passer sa méta sur deux lignes sur iPhone.
- Mon iPhone : « Installer le raccourci » en bouton plein or, alors que le seul bouton plein est le bouton flottant.
- Premier usage, Mon rythme au bureau : moitié droite vide. Chronologie iPhone : « Sans date » sous le pli.
- Projets, panneau : la phrase de santé tient sur deux lignes.
- Les données restent écrites dans chaque page : la coque est générée, pas les listes. Un générateur unique des
  listes depuis un JSON reste à faire (les lanes en ont écrit trois, jetables, hors dépôt).
- Rien n'a été vu hors Chromium.

## Textes à ajouter à `textes.md` (par son auteur)
- Rythme : boutons « Monter à {N1} » · « Descendre à {N_1} » (décision ; §4.2 dit « Oui, {N1} ») ; « Les 10 derniers
  jours travaillés » (§2.11 dit 14) ; « férié » comme jour hors règle ; « {f} sur {o} aujourd'hui » ; constat « Tu finis
  plus souvent ton essentiel quand il est placé avant midi. » (aucune forme C1-C8) + « Mettre l'essentiel le matin ? ».
- Agenda : groupes d'« À placer » « Aujourd'hui » · « À revoir » · « Mes projets » ; métas « prévue lun. 23 », « ce
  soir » ; toasts « Placée à {HH:MM} » et « Placée {jour} · Annuler » ; « Échéance du projet », « Jalon » ; dates
  au-dessus du titre (« 23 – 29 novembre 2026 », « Novembre 2026 », « 25 novembre – 4 décembre 2026 »).
- Surtitre d'un écran poussé : nom du parent (« Aujourd'hui », « Projets », « Réglages »).
- Santé courte : « À ce rythme : {besoin} jours travaillés, il en reste {reste} ».
- Chronologie : « Sans date » (§2.6 dit « Sans dates »), « {f} sur {t} faites », « Faite : {étape} · fini {jour} ».
- Aujourd'hui : « En tête : priorité haute. » ; puce « Garder » par ligne proposée.
- Copilote : « Tu as gardé 2 essentielles. Pour atteindre 5, voici 3 tâches de plus, dans cet ordre. Rien ne change
  tant que tu ne gardes pas. »
- Revue : « Le mer. 18 était férié : 4 jours travaillés. » ; compteur « {i}/{n} ».
- Planifier le projet : « Une phrase », « {projet} · pas {i} sur 2 ».
- Mon iPhone : « Cinq étapes, à faire une fois. Chacune se replie quand elle est faite. », « Le faire à la main »,
  « Le raccourci ne contient jamais ton jeton : il te le demande à l'installation. ».
- Réglages : résumés des rubriques ; « Rappel · {HH:MM} » ; Recherche « Ouvertes » / « Faites » ; Modèles « Nom du
  modèle », « Les dates deviennent des écarts… ».

## À vérifier sur un vrai iPhone (fondateur)
1. Safari : flou des barres (`backdrop-filter`), `:has()`, `text-wrap: balance`, `@starting-style`.
2. Barre d'onglets + indicateur d'accueil : rien de caché sous le pouce, bouton flottant à portée.
3. Balayage gauche/droite d'une ligne et retour haptique ; appui long.
4. Feuille de saisie sur le vrai clavier (hauteur, suggestions), dictée.
5. Agenda Jour : nombre d'heures visibles, défilement, « Toucher puis poser » en Planifier.
6. Mode sombre réel, contraste augmenté, texte à 130 %, daltonisme (couleurs de projet).
7. Tuile réelle (Scriptable, police SF) et rafraîchissement « maj ».

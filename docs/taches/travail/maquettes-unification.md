# Maquettes — unification (L3 n°8)

81 maquettes (70 écrans, 11 planches), 324 captures re-rendues. Quatre lanes ont aligné leurs écrans sur le
scénario ; tout a été re-vérifié et regardé ensuite.

## Ce qui est factorisé
- **Icônes** : `icones.js`, sprite unique tiré de lucide-react par `outils/icones-generer.cjs` (68 icônes), plus aucun
  `<symbol>` dans une page. `capturer.cjs` refuse un `<use>` sans symbole. (Origine : a99f38af3 a vidé 20 sprites.)
- **Coque** : `coque.js` pose barre d'état, barre latérale (256 px, « Nouveau projet » azur + dossier-plus) et
  onglets ; les comptes suivent l'heure (`SCENARIO.md` §7). Titre du bureau à y = 76 px sur 65 écrans.
- **Données** : `SCENARIO.md` donne toutes les tâches par projet et étape, la journée minute par minute, la semaine,
  les jours passés, la revue et les autres journées.
- **CSS** : reports des lots versés dans `taches.css` ; `.anneau`, `.camembert`, `.resume` et les doublons des lots retirés.

Mode d'emploi :
1. `<head>` : `taches.css`, feuille du lot, `icones.js` et `coque.js` en `defer`.
2. `<body data-heure data-onglet>` (+ `data-pousse`, `data-projet`, `data-histoire`) et les trois `data-coque`.
3. Tout titre, heure ou compte vient de `SCENARIO.md` ; sinon, l'y écrire d'abord.
4. Nouvelle icône : `node outils/icones-generer.cjs`.
5. `node outils/verifier.cjs` (0 échec), `node outils/capturer.cjs page.html`, regarder les PNG.

## `verifier.cjs`
`81 maquettes × 4 vues : 0 échec(s).` Contrôles : icône absente ou vide, texte sous 4,5:1, cible sous 44 px,
cible sous le bouton flottant ou les onglets, lexique interdit. Premier passage : 181 échecs, tous corrigés.

## Notes
| Écran | Fichier | Note |
|---|---|---|
| Matin | ecran-aujourdhui-matin | 9 |
| 15 h | ecran-aujourdhui-15h | 8,5 |
| Saisie | ecran-saisie(-nouveau) | 9 |
| À trier | ecran-a-trier | 8,5 |
| Bilan | ecran-bilan(…) | 8,5 |
| Jour · Semaine · Planifier | agenda-jour · -semaine · -semaine-planifier | 8,5 |
| Placer · Mois · À venir | agenda-placer-heure · -mois · -a-venir | 8,5 |
| Projets · Un projet · Tableau | projets-liste · projet-liste · projet-tableau | 8,5 |
| Chronologie | projet-chronologie | 8 |
| Tuile | tuile | 9 |
| Revue · Mon rythme · Copilote | revue-semaine · rythme · copilote | 8,5 |
| Recherche · Réglages · Décaler | recherche · reglages · projet-decaler | 8,5 |
| Mon iPhone | mon-iphone | 8 |
| Mon rythme, 1er jour | premier-usage-4-rythme | 8 |

## Passe après le tour 4
Recherche « devis » : 3 ouvertes (dont les 2 d'À trier) et 3 faites ; Chronologie du bureau : une rangée par étape, Matériel dès lun. 23, Pose sans date listée à part ; Agenda : titre à x 297, surtitre sur iPhone, À placer à 420 px ; vues du projet au même x (1162) ; Semaine : trait visible au-dessus du fond des blocs.
`verifier.cjs` contrôle aussi le TEXTE et les icônes porteuses de sens sous le bouton flottant (chevrons décoratifs exclus) : matin (espace avant Proposé), hors ligne (état dans la ligne du dessus, « échéance mer. 25 » rétablie), étapes du projet ; 81 × 4 vues, 0 échec.
Reste : à 15 h et hors ligne, le chevron des relances (même x partout) passe sous le bouton flottant au repos ; Semaine à 420 px coupe deux titres en cascade.

## Ce qui me déplaît encore
- Semaine : le trait « maintenant » passe sous le devis de 2 h, il n'en reste qu'un point.
- Matin iPhone : le bouton flottant mord le drapeau du fournisseur ; « 09:00 » met la méta du devis sur deux lignes.
- Mon iPhone : bouton plein or, alors que le seul bouton plein est le bouton flottant. Mon rythme du 1er jour :
  bureau à moitié vide. Chronologie iPhone : « Sans date » sous le pli.
- Les listes restent écrites à la main dans chaque page ; seule la coque est générée.
- Rien n'a été vu hors Chromium.

## Textes à ajouter à `textes.md`
- Rythme : « Monter à {N1} » / « Descendre à {N_1} » (§4.2 dit « Oui, {N1} ») ; « Les 10 derniers jours
  travaillés » (§2.11 : 14) ; jour hors règle « férié » ; « {f} sur {o} aujourd'hui ».
- Constat « Tu finis plus souvent ton essentiel quand il est placé avant midi. » + « Mettre l'essentiel le matin ? ».
- Agenda : groupes d'À placer « Aujourd'hui » · « À revoir » · « Mes projets » ; « prévue lun. 23 », « ce soir » ;
  toasts « Placée à {HH:MM} » et « Placée {jour} · Annuler » ; « Échéance du projet », « Jalon » ; dates en surtitre.
- Surtitre d'un écran poussé : nom du parent.
- Santé courte : « À ce rythme : {besoin} jours travaillés, il en reste {reste} ».
- Chronologie : « Sans date » (§2.6 : « Sans dates »), « {f} sur {t} faites ».
- « En tête : priorité haute. » ; puce « Garder » par ligne ; revue « {i}/{n} » et « Le mer. 18 était férié : 4 jours
  travaillés. ».
- Phrase du Copilote « Tu as gardé 2 essentielles… ».
- Planifier le projet : « Une phrase », « {projet} · pas {i} sur 2 ».
- Mon iPhone : « Le faire à la main », « Le raccourci ne contient jamais ton jeton… ».
- Résumés des Réglages, « Rappel · {HH:MM} », « Ouvertes » / « Faites », « Nom du modèle ».

## À vérifier sur un vrai iPhone
1. Safari : flou des barres, `:has()`, `text-wrap: balance`, `@starting-style`.
2. Pouce : onglets, indicateur d'accueil, bouton flottant.
3. Balayage d'une ligne, haptique, appui long.
4. Saisie sur le vrai clavier, dictée.
5. Agenda Jour : heures visibles, « Toucher puis poser ».
6. Sombre réel, contraste augmenté, texte à 130 %, daltonisme.
7. Tuile réelle (Scriptable, police SF).

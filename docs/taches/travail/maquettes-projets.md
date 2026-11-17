# Maquettes rendues — Projets, Rythme, Copilote, tuile (L3 n°8)

`docs/taches/maquettes/` : 12 écrans HTML + `ecrans-projets.css` (jetons existants seulement), 48 PNG dans `captures/`.
Mesure (couleurs calculées, partie visible, 48 vues) : 0 texte sous 4,5:1, 0 sous 12 px, 0 cible sous 44 px ; fond
voilé sous un dialogue exclu.

## Écrans (3 tours chacun : écrire → rendre → regarder → corriger)
- **projets-liste** — projet = ligne à plat : camembert couleur, « 12 sur 18 · échéance », puce de priorité (barres + mot,
  Basse en contour, jamais une teinte), « À planifier » en puce azur, « ⚠ à surveiller » en méta ; « Nouveau projet » en
  rangée de 56 px à mi-écran. T2 : alignements bureau ; T3 : panneau bureau = vrai projet.
- **projet-liste** — nom + point, priorité, échéance, barre couleur, prochain jalon, phrase de santé de la spec 4 ; ⋯
  ouvert au bureau. T2 : « Fini quand… » en aperçu replié, losange plein.
- **projet-tableau** — iPhone : puces d'étapes, une colonne + bord de la suivante. T2 : bureau élargi, méta qui
  débordait ; T3 : en-tête compact, « 2 faites » dans la colonne.
- **projet-chronologie** — iPhone : frise verticale (étapes, jalons, aujourd'hui, échéance) ; bureau : 3 semaines,
  deux traits, aucune dépendance. T2 : étiquettes superposées ; T3 : toute la frise tient sans défiler.
- **projet-planifier**, **-2** — pas 1 : fini quand…, échéance en puces, priorité en 3 tuiles ; pas 2 : première
  action, « Découper avec le Copilote », carte à valider (même ligne, ×), « Plus » replié. T2 : dialogue sous le voile,
  carte hors écran ; T3 : sélection unifiée.
- **rythme** — anneau « 3 sur 5 », source, proposition, 10 barres fines, week-end absent, objectif pointillé. T2 :
  chiffres sur le trait, bureau étroit ; T3 : phrase de source cohérente avec la règle +1.
- **revue-semaine** — 4 faits, carte projet en pile, 4 décisions, « Planifier ma semaine » au pouce. T2-T3 : textes trop
  longs, icône collée.
- **copilote** — 4 demandes, carte « Proposé pour aujourd'hui » avec la `.ligne` de l'écran, une raison par ligne.
  T2 : icône en ligne (libellés cassés) ; T3 : annulé.
- **mon-iphone** — « 2 sur 5 », étape en cours dépliée, interrupteurs. T2 : textes centrés ; T3 : boutons.
- **tuile** — moyenne : « 2 sur 5 » en 34 px, 3 lignes pleine largeur, échéance, « maj 09:41 » ; grande : 6 lignes.
  T2 : titres coupés → bandeau en tête ; T3 : 11 → 12 px.
- **cockpit-carte** — carte bordée parmi des squelettes ERP. T2 : ⋯ retiré ; T3 : vérifiée sans changement.

## Ce qui me déplaît encore
- Projet en Liste sur iPhone : la santé (3 lignes) repousse « Clôture » et « Faites » sous le pli.
- Tableau iPhone : « Matériel » répété (puce et tête de colonne).
- Ambre en sombre tire au brun ; vide sous « Priorité » au pas 1 ; deux « + » sur Projets.
- Non vérifié : vrai iPhone, Scriptable réel (SF, pas Hanken), daltonisme.

## Écarts assumés
1. « Fini quand… » en aperçu replié (spec 7 : Détails replié) ; jalon visible.
2. « Après… » écrit « attend : … » (§3 interdit « après »).
3. Revue : « Suivant » par carte (spec 7) ; « Passer » quitte la revue.
4. « Proposé pour aujourd'hui », « objectif atteint », « gardées faites » (termes interdits évités).
5. Rythme : proposition au-dessus du graphique (visible sans défiler).
6. Tableau : la tâche y est une tuile (`--card` sur `--muted`, sans trait) — seul endroit.
7. Vues avancées : en-tête compact, santé en puce.
8. Mon iPhone, étape 5 « Ouvrir sur Aujourd'hui » (A13).
9. Cockpit : « 2 sur 5 · 4 à faire » (format spec 7).
10. Un fichier par pas de Planifier.

## À reporter dans `taches.css`
- `svg.i { fill: none }` éteint tout remplissage à une classe : prévoir `.i.plein`.
- `--tch-surveiller` sur `--tch-panneau` = 4,46:1 en clair : avertissement seulement sur `--card`.
- `.puce[aria-checked="true"]` non stylé : l'aligner sur `.puce.active`.
- Planche 7 : « 0 sur 4 » + « À planifier » contredit la spec 4 (À planifier ⇔ 0 ouverte).
- `.ligne.projet` : `align-items: center` quand la méta passe à 2 lignes.

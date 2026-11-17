# Critique visuelle contradictoire — écrans cœur, tour 2 (L3 n°8)

Méthode : `grille-visuelle.md`. Ouvertes : les 4 vues de chaque écran du lot (17 états, `-bas`/`-menu`/`-rythme`
compris) ; planches 1, 3, 7 en iPhone clair + sombre. Mesures par script dans les PNG citées au fil du texte.

## 1. Suivi de la première critique

**Les 10 majeurs : tous corrigés.** Carte du moment (`matin-iphone-clair`) ; N = 5 − 0 − 2 = 3 ; matin bureau en
3 colonnes (`matin-bureau-clair`) ; retour sans recouvrement (`retour-iphone-clair`) ; saisie bureau en place
(`saisie-bureau-clair`) ; « Moyenne ▾ » (`saisie-liste-*`) ; Fiche Plus complète, sans « Après… » ; gestes d'À trier
15 px 500 gris ; « Tout reporter à mer. 25 » dans l'en-tête du reste ; segments au bilan.

**Corrections prioritaires.** 1-5, 7, 10 corrigées (mêmes preuves). 8 corrigée : bouton caché dans tous les `-bas`,
plus proche texte à ≈ 7 px de son bord, sans recouvrement. Restent :
- **6 partielle** : x gauche 280 partout, mais bord droit 996 / 956 / 1124 et À trier sans 3e colonne.
- **9 partielle** : barre d'onglets OK (fantôme mesuré 251/255, imperceptible) ; aucun titre compact dans la feuille
  du bilan (`bilan-bas-*`, `bilan-rythme-*`) ; `a-trier-bas-*` pose la barre sur un grand titre non défilé.
- **Transversal 8 partiel** : constat relevé (1,29:1), mais carte « passer à 6 » et puces de la fiche à 1,03:1 en
  sombre (`bilan-rythme-iphone-sombre`, `fiche-*-sombre`).
- **Transversal 9 non corrigé** sur À trier : « échéance ven. 27 » mesuré (90,100,136) = gris, (12,19,53) sur la fiche.

## 2. Nouveau regard, écran par écran

### Aujourd'hui, 8 h 30 — 8,5/10
PRÉSERVER : carte du moment en tête, pastille « Toute la journée » avant Prévu, rouge seul sur « échéance aujourd'hui »,
heures tabulaires, bureau en trois colonnes avec trait « maintenant » et heure de grille masquée près du trait.
- MINEUR (`matin-*`) : « Envoyer le devis révisé » n'affiche pas l'échéance que la fiche montre (« échéance mer. 25 »).
  → Méta « échéance mer. 25 » en `--foreground` 500 sur toutes les vues de ce jour.
- MINEUR (`matin-bureau-*`) : le champ « Ajouter une tâche » est SOUS la carte (y 212), au-dessus d'elle le jour du
  retour (y 138). → Toujours juste sous la progression ; la carte vient après.
- MINEUR (`matin-bureau-*`) : barre latérale qui tronque « Chantier Benali 9 k… », « Recrutement techni… ». → 256 px.
- MINEUR : étiquette d'agenda « journée » → « Toute la journée » (lexique), sur deux lignes.

### Aujourd'hui, 15 h — 7,5/10
PRÉSERVER : segments 3 sur 5, faites barrées en place, estampille « → jeu. 26 », phrase « objectif couvert ».
- **MAJEUR** (`15h-iphone-*`, `15h-bureau-*`) : l'activité ERP « Rappeler pour le devis 10:30 » a disparu de la liste
  alors que l'agenda du MÊME écran bureau la montre barrée. Les tâches faites restent barrées, l'activité faite
  s'évapore : deux règles. → Ajouter dans Prévu la ligne « Rappeler pour le devis » barrée, 10:30 en fin de ligne.
- **MAJEUR** (`15h-bureau-*`, aussi `bilan-bureau-*`) : comptes de « Mes projets » figés à 6 · 8 · 5 · 3 · 4. À 15 h,
  devis + rails faits → Chantier 18 − 14 = 4 ; fournisseur fait → Salon 11 − 4 = 7. Au bilan : Chantier 4, Salon 6.
  → Recalculer ; à défaut, retirer le compte.
- MINEUR : « Suivi des relances : 2 » ne se recompte pas dans SCENARIO. → L'y écrire.

### Menu ⋯ — 8,5/10
PRÉSERVER : feuille au pouce, groupes séparés, voile lisible.
- MINEUR (`15h-menu-bureau-*`) : popover non ancré (bord droit x 864 pour un ⋯ à x 968, il couvre « Copilote ») et
  voile plein écran pour un simple menu. → Bord droit aligné sur le ⋯, sans voile au bureau.

### Aujourd'hui vide — 9/10
Rien de nouveau.

### Retour de congé — 8,5/10
PRÉSERVER : une carte, « Reprise · objectif 5 », « Garder ces 5 » en bas de Proposé.
- MINEUR (`retour-bas-*`) : « Voir tout » ici, « Voir toutes les tâches de mes projets » le matin pour le même
  contrôle. → Un seul libellé (le long, A11).
- MINEUR : 10 jours, 18 tâches, relances 12, À trier 3, visite à Salé, comptes de projets : absents de SCENARIO.
  → Section « Retour, lun. 7 déc. » dans SCENARIO.

### Saisie — 7,5/10
PRÉSERVER : jetons teintés dans le texte, puces « × », « Ajouter » or au pouce, saisie en place au bureau.
- **MAJEUR** (`saisie-bureau-*`, `saisie-iphone-*`) : le 23, la saisie crée « Nouveau projet : Salon Solaire Expo »
  alors que (a) la barre latérale du même écran montre déjà « Salon Solaire Expo 8 », (b) `saisie-liste` le crée déjà
  le 2 novembre, (c) « demain 10h » donne Quand = mar. 24 : le 24 au matin cette tâche serait dans Prévu à 10:00 et
  dans l'agenda, pas dans Proposé (`matin-*` : « Garder · 10:00 »). → Saisie « relancer l'imprimeur jeudi #Salon
  Solaire Expo !!! » ; puces « jeu. 26 · Priorité haute · ● Salon Solaire Expo » (projet existant). Au matin, retirer
  « 10:00 » de la ligne proposée et dire « En tête : priorité haute. » ; l'heure 10:00 de 15 h vient de l'agenda.

### Saisie, liste collée — 9/10
PRÉSERVER : « 6 tâches · 2 projets », « Moyenne ▾ », en place au bureau. MINEUR : au bureau, « Créer 6 tâches » de
550 px. → Largeur au contenu, aligné à droite.

### Fiche — 8,5/10
PRÉSERVER : cran sans ruban, points 18 px, Reporter azur + Fait vert, panneau 460 px au bureau, liste au même x.
- MINEUR (`fiche-*-sombre`) : puces Quand · Échéance · Projet · Priorité à 1,03:1 de la feuille. → Fond de puce sombre
  = celui de la carte du constat (1,29:1).

### Fiche, Plus — 9/10
PRÉSERVER : sept lignes, titre dans la barre au défilement.

### À trier — 8/10
PRÉSERVER (iPhone) : compte au-dessus du titre, gestes discrets, provenance en texte, « Suggéré par l'ERP » en gras.
- **MAJEUR** (`a-trier-bureau-*`) : pas de troisième colonne : 316 px morts à droite, liste élargie jusqu'à x 1124,
  contre spec 8 §10. → Agenda du jour 420 px à droite (cible de glisser), liste 264-996 comme Aujourd'hui, gestes
  calés sur son bord droit.
- MINEUR (`a-trier-bas-*`) : la liste n'a pas défilé (lignes identiques à `a-trier` dès y 268) mais la barre compacte
  coupe le grand titre à mi-hauteur, « Copilote » en fantôme. → Barre compacte seulement quand le bas du grand titre
  est passé dessous ; refaire la capture avec une liste qui défile.
- MINEUR : « échéance ven. 27 » en gris (cf. §1). → `--foreground` 500.

### Bilan du soir — 7,5/10
PRÉSERVER : 4 sur 5 en segments, « 4 des 5 gardées · essentiel 2/2 », « Tout reporter à mer. 25 » dans l'en-tête,
un constat, panneau droit au bureau, « Valider » au pouce.
- **MAJEUR** (`bilan-bureau-*`) : derrière le panneau, la liste a perdu Prévu (fournisseur et rails faits, ligne
  « → jeu. 26 », relances) et le pied Proposé, alors qu'Essentiel garde ses faites barrées. Même journée que 15 h,
  autre règle. → Liste de 15 h + « Confirmer la réservation du stand » barrée.
- MINEUR (`bilan-bas-*`, `bilan-rythme-*`) : pas de titre compact, « Faites » tranché sous « Passer ». → Barre 44 px
  « Bilan du soir » + filet, comme `fiche-plus`.
- MINEUR (`bilan-rythme-iphone-sombre`) : carte « passer à 6 » à 1,03:1. → Même fond que le constat.
- MINEUR : Choisir un jour · En réserve · Abandonner cachés sous ⋯ ; spec 7 §4 les veut visibles. → Quatre puces sur
  deux lignes (la place existe).
- MINEUR : « Passer » (quitter) et « Passer à 6 » sur le même écran. → « Viser 6 » (SCENARIO à aligner).

### Planches 1, 3, 7 — 8,5/10
PRÉSERVER : ligne de référence, barre fine de projet, segments, carte du moment.
- MINEUR (`composants-1-*`) : « échéance lun. 23 » illustre l'échéance PROCHE alors qu'au 24 c'est hier. →
  « échéance jeu. 26 ».
- MINEUR (`composants-7-*`) : planche coupée au bas (« 4 sur 5 » tranché). → Capture pleine hauteur.

## 3. Écarts entre documents (à corriger hors maquettes)
- `SCENARIO.md` « plan tenu 4 sur 5 » : mot interdit (spec 7 §3) → « 4 des 5 gardées » (les maquettes ont raison).
- Spec 7 §4 « N = objectif − gardées ouvertes » donne 3 à 15 h ; SCENARIO « objectif − faites − gardées ouvertes »
  donne 0 → aligner la spec.

## 4. Verdict (« à construire tel quel » = ≥ 8,5 et aucun majeur)

**Prêts** : matin (8,5), menu (8,5), vide (9), retour (8,5), liste collée (9), fiche (8,5), fiche Plus (9),
planches (8,5).
**Non prêts** : 15 h (7,5) — activité ERP barrée dans Prévu, comptes recalculés ; saisie (7,5) — exemple qui ne
recrée pas Salon et sort de la journée du 24 ; À trier (8) — agenda en 3e colonne au bureau ; bilan (7,5) — liste de
fond = 15 h, comptes, titre compact de la feuille.

Les quatre majeurs sont des incohérences de données entre vues, pas de goût : le langage visuel tient.

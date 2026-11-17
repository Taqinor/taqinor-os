# Critique visuelle — tour 3 (L3 n°8)

Ouvertes : iPhone clair + sombre des 12 écrans et variantes ; bureau clair de chacun ; bureau sombre de 15 h, Semaine,
Placer-durée, bilan, À trier, Projets, revue, Tableau ; les 8 contrôles en iPhone clair + sombre + bureau clair.
Mesures par script dans les PNG ; sources lues par `grep` et `git show`.

## 1. Suivi du tour 2

**Cœur.** Corrigés : 15 h (ERP barrée à 10:30 dans Prévu ; comptes 4 · 7, `15h-bureau-clair`) ; saisie (« relancer
l'imprimeur jeudi #Salon Solaire Expo !!! » → jeu. 26, projet existant) ; matin sans « 10:00 » ; À trier en 3 colonnes,
liste jusqu'à x 996, échéance en encre ; bilan (fond = 15 h, comptes 4 · 6, barre compacte, 4 puces, carte lisible en
sombre) ; barre 256 px ; champ au-dessus de la carte. Non corrigés : « Suivi des relances : 2 » absent de SCENARIO ;
« journée » dans la colonne Agenda du bureau ; « Passer » et « Passer à 6 » ensemble.

**Agenda.** Corrigés : N1 (trait sous le bloc), N2 (« + 2 h » azur, ambre au-delà de 4 h), N3 (fond mesuré 46,46,49),
m1, m4 (246,248,252 / 8,12,25 partout), m5, J3, P6, S2 (2 titres coupés sur 17), marge de Planifier, bloc de 08:30.
Partiels : J1 (≈ 5,1 h visibles) ; m2 (« À placer · 10 » / « À placer 10 tâches ») ; P5 (« Recrutement techni… »).
Non corrigé : m3 — « Confirmer la réservation du stand » dans la bande « Toute la journée » (`agenda-jour-*`).

**Projets.** Corrigés : M1, M2 (texte à 44 px du haut, 35 du bas), M3 (10 sur 18, 2 sur 11, Recrutement juste),
pied de tuile, cartes de revue. **Tableau du bureau : non corrigé, aggravé** (§2). Mineurs restants : Salon sans
« à surveiller » ; Copilote « 0 + 2 gardées + 3 = 5 », « Chantier B… » ; « Passer à 6 » azur plein ; pas de
« Liste ⌄ » sur `projet-liste-iphone`.

## 2. Les 12 écrans

**Aujourd'hui 15 h — 8.** PRÉSERVER : faites barrées en place, ERP à son heure, « → jeu. 26 ».
- **MAJEUR (entre lots)** : à 09:41 l'Agenda place le devis 09:00–11:00 et les rails à 08:30 (`agenda-jour-*`,
  `agenda-mois-*`) ; à 15 h la liste les montre sans heure et la colonne Agenda (`15h-bureau-*`) ne garde que 10:00 et
  10:30. → 15 h et bilan : « 09:00 » sur le devis, rails en tête de Prévu « 08:30 », colonne : les deux blocs barrés.
- MINEUR : le bouton flottant masque le chevron des relances (iPhone, x 730 y 1408).

**Saisie (+ nouveau) — 9.** MINEUR : le nouveau projet prend le rose, voisin du rouge : en sombre, puce rose cerclée
de rose = air d'erreur → première teinte libre hors rose (menthe). MINEUR : « · moyenne » → « · Moyenne ».

**À trier — 8,5.** La règle « heure masquée à moins de 20 min » y marche (09:00 absent à 08:41).

**Bilan (+ bas, rythme) — 8,5.** MINEUR : « Passer » à x 48, titre à x 33 (bureau 1056 / 1048) → même colonne.

**Agenda Jour — 8,5.** MINEUR : « 10:00 » sous « 09:41 » (19 min ; au bureau, y 287 / 307, ils se touchent) → masquer.
MINEUR : barre latérale 6 · 8 à 09:41, rails faits à 08:30 → Chantier 5. MINEUR : m3.

**Agenda Semaine — 8.** PRÉSERVER : rail 64 px, colonnes de 165 px, surcharge ambre.
- **MAJEUR (données contre la revue)** : « Publier l'annonce » et « Classer les factures fournisseurs » prévues mer. 25
  sont FAITES dans la revue du 16-20 ; « Rédiger l'annonce » faite lun. 23, après la publication ; lundi = 1 tâche
  Benali, 1 Salon, 1 Recrutement, 1 Administratif, alors que SCENARIO fait passer Benali 10→12, Salon 2→3, les autres
  inchangés ; « Préparer l'entretien » jeu. 26 alors que les entretiens attendent « Trier les CV reçus ». Mêmes lignes
  dans Planifier, Mois, À venir. → Lundi : 2 Benali + 1 Salon + 1 sans projet ; mer. 25 et jeu. 26 : tâches absentes de
  la revue et non bloquées ; « Trier les CV reçus » partout ; titres écrits dans SCENARIO.
- MINEUR : le trait « maintenant » n'est plus que deux bouts de 6 px autour du devis (x 286, 454) → point au bord de la
  colonne du jour. MINEUR : « Toute la journée » collé au rail (x 64) → retrait 12 px.

**Planifier (+ posée) — 8.** PRÉSERVER : « + 2 h », week-end « non travaillé », « Placée jeu. 26 · Annuler ». Seul
défaut : le MAJEUR de données. MINEUR : « Terminer » azur sur iPhone, or au bureau.

**Placer à une heure (+ durée) — 8,5.** Mêmes mineurs que Jour.

**Projets — 8.**
- **MAJEUR** : horloge 15:02 mais 12 sur 18 · 3 sur 11 et barre 6 · 8, chiffres de 8 h 30 ; `15h-bureau-*` dit 4 · 7 à la
  même heure. Cause : SCENARIO l. 59 « valent le mardi 24 à 15 h » contre l. 67-68 « à 15 h Chantier 4 » (18 − 4 = 14).
  → SCENARIO « à 8 h 30 » et barre d'état 8:30 sur le lot Projets.
- MINEUR : « …il en reste » puis « 8 » seul en 2e ligne (panneau) → « 15 jours, il en reste 8 ».

**Tuile — 8.**
- **MAJEUR** : « 1 sur 5 » (les rails), mais la grande tuile liste les rails comme restants et omet « Appeler le
  fournisseur 10:00 », ouverte à 09:41. → Remplacer la ligne, avant « Rappeler pour le devis ».

**Revue — 8,5.** MINEUR : compteur de carte « 1 sur 5 », même forme que l'objectif du jour → « 1/5 ».

**Tableau — 7.**
- **MAJEUR (aggravé par la feuille commune)** : la page en trois colonnes laisse 420 px vides (x 1020-1440) et serre le
  tableau dans 684 px : colonnes de 158 px, « Valider le plan de… », « Faire signer le PV de… », méta sur 4 lignes.
  → Pas de 3e colonne en vue Tableau ; colonnes `1fr` (≈ 272 px).

## 3. Non-régression

Intacts : matin, fiche, liste collée, Mois, À venir (alignements, largeurs, titres compacts, sombre). Mois et À venir
portent les lignes fausses du 25.

**MAJEUR — icônes disparues** sur `projet-liste-*`, `rythme-*`, `copilote-*` : retour, ⋯, alerte, sablier, losange,
« + » du bouton flottant (disque or vide), onglets, étincelle et avatar du Copilote ; restent des retraits vides
(constat de Mon rythme à x 96). `projet-liste.html` avait un `<symbol>` à 873226e68, aucun à a99f38af3 ; 20 fichiers ont
le bloc `sprite` vide, dont les écrans cœur encore rendus avec icônes : la prochaine capture les cassera. → Sprite en
inclusion unique ; `capturer.cjs` échoue si un `<use href>` n'a pas de `<symbol>`.

MINEUR : le fond du Copilote (`copilote-bureau-clair`) est un ancien matin (champ sous la carte, « 10:00 » sur le
fournisseur) → recopier le matin actuel. Bouton Copilote de Mon rythme à 12 px du bord.

## 4. Cohérence d'ensemble

UN : en-tête iPhone, ligne de tâche, segments partout, barre fine, couleurs de rôle, jetons de surface, taille du titre
(capitale 18 px sur 7 écrans du bureau).

Écarts :
1. Barre latérale 240 px (Agenda) contre 256 (cœur, Projets).
2. « Nouveau projet » gris avec « + » (Agenda), azur avec `folder-plus` ailleurs.
3. Heure masquée près du trait : cœur oui, Agenda non.
4. Heures du devis et des rails (§2, MAJEUR).
5. Ligne de base du titre au bureau : y 68 (cœur), 56 (Projets), 48 (Agenda) : le titre saute à chaque section →
   ligne du dessus réservée partout.
6. Panneau droit teinté (cœur, Agenda), blanc (Projets), vide (Un projet, Tableau).
7. « Toute la journée » : visite seule (cœur), visite + tâche (Agenda), « journée » (colonne du bureau, tuile).
8. « Passer à 6 » : contour (bilan), azur plein (Mon rythme).
9. **MAJEUR — tâches de Benali** : le projet en compte 6 ouvertes (plan, panneaux, nacelle, structure, mise en service,
   PV), sans « Envoyer le devis révisé » ni les rails, essentielles du jour ; l'Agenda en montre 6 autres (onduleurs,
   câbles, raccordement, PV, photos, bureau de contrôle). → Les 18 tâches de Benali et les 11 du Salon, par étape, dans
   SCENARIO, reprises par tous les écrans.
10. « Trier les CV » / « Trier les CV reçus » ; « Fixer » / « Planifier les entretiens ».
11. Mon rythme sans barre latérale au bureau, sans être un rituel : on croit changer d'app.

## 5. Verdict

**Prêts (≥ 8,5, aucun majeur)** : Saisie et nouveau (9), À trier, Bilan et variantes, Agenda Jour, Placer à une heure
et durée, Revue (8,5) ; contrôles : matin, fiche, liste collée.

**Non prêts** : 15 h (heures du devis et des rails) ; Semaine, Planifier, Mois, À venir (données du 23 au 27) ; Projets
(heure ou chiffres) ; Tuile (une ligne) ; Tableau (3e colonne, 272 px) ; Un projet, Mon rythme, Copilote (icônes ;
Un projet aussi §4.9).

**Avis franc.** Le langage visuel tient : sur iPhone, Aujourd'hui, la saisie, la fiche, le bilan et Planifier ma semaine
soutiennent la comparaison avec Things et Rappels, et aucun défaut de goût majeur n'apparaît. Mais un fondateur qui
ouvre trois écrans de suite verra des chiffres qui ne se suivent pas et trois écrans sans icônes : pas encore « le
meilleur ». Ce qui ferait la différence :
1. **Un seul jeu de données** (JSON) d'où sortent les 30 écrans, comptes et heures calculés : les derniers tours ont
   surtout trouvé des chiffres recopiés à la main.
2. **Une capture qui refuse** un écran sans icône.
3. **Une seule coque de bureau** : barre 256 px, ligne de titre fixe, panneau droit au même jeton, Tableau sans 3e colonne.
4. **« Toute la journée » tranchée une fois** et appliquée partout.
5. **Une preuve sur un vrai iPhone** (Safari, flou, balayage, haptique) : rien n'a été vu hors Chromium.

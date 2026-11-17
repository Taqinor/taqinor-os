# Critique visuelle — tour 4 (L3 n°8, dernier tour)

Ouvertes : les 26 écrans en iPhone clair + sombre, et en bureau clair les 17 marqués (B). Mesures par script (Pillow) :
bord de la barre latérale, bas des capitales du titre, bords et fonds des panneaux, titre iPhone, écart titre/bouton,
emprise du bouton flottant. Sources lues : `SCENARIO.md`, `projet-chronologie.html` l. 48-54, `recherche.html`.

## 1. Suivi du tour 3

**Corrigés** : 15 h (devis 09:00, rails 08:30, colonne Agenda à 4 blocs barrés) ; données du 23 au 27 (Semaine,
Planifier, Mois, À venir conformes à §4) ; Projets (8:30, 12 sur 18 · 3 sur 11, barre 6 · 8) ; tuile (fournisseur
10:00 avant Rappeler) ; Tableau (4 colonnes de 272 px) ; icônes revenues (`projet-liste`, `rythme`, `copilote`) ;
tâches de Benali par étape. Mineurs : relances dans SCENARIO, « Toute la journée » partout, « Monter à 6 »,
« Passer » aligné (x 33 / 1048), 10:00 masqué à 09:41, stand hors « Toute la journée », À placer · 12, retrait de
12 px, « Terminer » or, santé sur une ligne, « Liste ⌄ », « 1/5 », fond du Copilote, barre latérale de Mon rythme,
« Nouveau projet » azur, nouveau projet menthe (source ; capture non ouverte).

**Partiels** : bouton flottant — le chevron des relances a été reculé à x 603 sur 15 h (x 731 le matin), et le bouton
(x 636-747, y 1372-1483) mord encore le drapeau (`matin-iphone`) et « → jeu. 26 » (`etat-hors-ligne-iphone`) ; trait
« maintenant » de la Semaine caché sous le devis ; panneaux droits (§2).

## 2. Une seule application ?

**Bureau, mesuré.** Barre 256 px sur 13 écrans (255 Agenda, arrondi) ; rail 64 px sur Semaine et Mois (voulu) ; rien
sur la revue (rituel). Bas du titre : y 68 sur les 12 écrans mesurés. Écarts : titre à x 297 (cœur, Projets) mais
x 281 sur Agenda Jour et À venir ; panneau droit 420 px partout sauf Agenda (**340 px**) ; sélecteur Liste · Tableau ·
Chronologie à x 838-1062 en Liste, x 1162-1385 ailleurs (saut de 324 px). Fonds : teinté (compagnon), blanc bordé
(fiche, bilan, recherche) — défendable.

**iPhone.** Onglets, badge, icônes identiques partout. Écart : bas du titre à y 191 (Aujourd'hui, À trier, Projets),
y 155 sur les 4 vues d'Agenda (pas de surtitre) : 18 pt de saut entre onglets voisins.

## 3. Les données — 14 recomptes

Justes : matin 0 sur 5 · 0/2, barre 6 · 8 · 5 · 3 · 4 ; 15 h 3 sur 5 · 1/2, Benali 4 · Salon 7 ; bilan 4 sur 5,
4 des 5 gardées, Salon 6 ; Agenda 09:41 Benali 5, À placer 12 (2 + 2 + 8) ; Semaine mar. 4 h 15 (30+120+30+30+45),
mer. 2 h 30, jeu. 2 h, ven. 2 h, lun. 4 faites ; Planifier « + 2 h » ambre mar. (6 h 15) et mer. (4 h 30), azur
jeu., ven. (4 h) ; Projets 12/18, 3/11, 4/9, 7/10, 0/4, barres 160 · 66 · 106 · 168 px sur 240 ; panneau Benali
7/8 · 3/3 · 2/5 · 0/2, Faites 12, « 10 jours, il en reste 8 » ; Mon rythme 48, 6 sur 10, « vendredi 4 » = (3+5)/2 et
« 5 les autres » = 40/8 ; revue 21 = 5+4+7+5 ; Mois (9 → 5, 12 → 6, 19 → 7, 24 → 3 + 4) ; tuile 1 sur 5, + 3 autres.

**Écarts** :
- Recherche « devis » : 1 ouverte, il y en a 3 (MAJEUR 1).
- Chronologie du bureau : Matériel dès mer. 25 au lieu de lun. 23 ; Pose dessinée ven. 27 → jeu. 3 déc. mais
  « sans date » (MAJEUR 2).
- Hors ligne (15:20, même état que 15 h) ôte « échéance mer. 25 » au devis, que 15 h affiche (mineur).

## 4. Nouveau regard

**Notes** : Matin 9 · 15 h 9 · Saisie 9 · Liste collée 9 · Fiche 9 · À trier 8,5 · Bilan 8,5 · Jour 8,5 · Semaine
8,5 · Planifier 8,5 · Mois 9 · À venir 9 · Placer 8,5 · Projets 9 · Un projet 8,5 · Tableau 8,5 · **Chronologie 7,5**
· Planifier le projet 8,5 · Mon rythme 8,5 · Revue 8,5 · Copilote 9 · Mon iPhone 8,5 · Tuile 9 · **Recherche 7,5** ·
Vie privée 8,5 · Hors ligne 8,5.

**MAJEUR 1 — la recherche oublie des tâches** (`recherche-*`). « Préparer le chantier du devis accepté » et « Demander
le devis d'assurance décennale » (À trier, §1) manquent. → Ouvertes 3 : ces deux lignes (« À trier · Suggéré par
l'ERP », « À trier · noté lun. 23 »), puis Comparer.

**MAJEUR 2 — la Chronologie du bureau contredit ses légendes** (`projet-chronologie-bureau-clair`, html l. 51). Axe
juste (13 jours, repères à midi), mais barres posées bout à bout. → Une rangée par étape : Matériel
`left:0;width:30.77%` ; Pose sans barre, « Pose · 0 sur 2 · sans date », le losange seul à jeu. 3 déc.

**Mineurs nouveaux** :
1. Agenda iPhone : surtitre « Mardi 24 novembre », titre à y 191.
2. Agenda bureau : titre à x 297.
3. Panneau À placer : 420 px (un seul jeton de panneau).
4. Sélecteur de vue : même place en Liste qu'en Tableau.
5. `agenda-semaine-planifier-iphone` : titre fini à x 559, « Terminer » dès x 570 (5,5 pt) et chevauchant en hauteur
   → « Terminer » sur la ligne du surtitre.
6. « essentiel 2/2 » et « 2 sur 2 » côte à côte (`ecran-bilan-bureau-clair`), tuile « 0 sur 2 » → « sur » partout, le
   « / » réservé à « 1/5 ».
7. Bureau Projets : titre du panneau à la taille du titre de page → 22 px, comme la fiche.
8. Vie privée : émoji 👎 → icône lucide 16 px.
9. Revue : Benali montre 3 faites sur 6 sans le dire → « Faites cette semaine · 6 ».
10. Chevron des relances à x 731 partout ; marge basse 104 px pour qu'au repos rien ne passe sous le bouton.

**Ce que l'unification a cassé** : rien de majeur. Effets de bord : le chevron déplacé pour passer le contrôle « cible
sous le bouton flottant » ; la Chronologie réécrite sur l'axe sans mise en rangées.

**À préserver** : segments (journée), barre fine (projet), faites barrées en place, « + 2 h » azur/ambre, sombre sans
brun, le Mois, la tuile, le Tableau à 272 px.

## 5. Verdict

**Pas encore** : deux majeurs de données, de quelques lignes chacun (Recherche, Chronologie du bureau). Tous les autres
écrans regardés sont ≥ 8,5 ; le langage visuel tient. Faire les mineurs 1-4 (coque) dans la même passe, puis vérifier
ces deux écrans et la coque : un 5e tour complet n'apporterait rien.

**Les 8 points de la construction** (ce qui se perd entre maquette et produit) :
1. **Une coque, un composant** : barre 256 px, ligne de surtitre réservée, panneau d'une largeur ; aucune page ne
   redéfinit ces cotes.
2. **Jetons seulement** (`--tch-*` versés dans `tokens.css`, clair ET sombre, sous `check_hex.mjs`) : un hex posé à
   la main, et le sombre vire au brun.
3. **Polices exactes** : Archivo 700 / −0,02 em pour le seul titre, Hanken tabulaire pour les heures, préchargées avec
   métriques de repli.
4. **Sans boîtes** : ni bordure, ni ombre, ni séparateur par tâche ; case 22 px sur la 1re ligne ; titre sur 2 lignes
   puis coupé — la première chose qu'on « améliore » en codant.
5. **Chiffres calculés** : progression, comptes, À placer, charges, santé sortent d'un même sélecteur ; la recherche
   couvre tout, À trier compris.
6. **Icônes lucide-react seules** (20/1,75 · 14/2 · 24/2), aucun émoji.
7. **Pouce et mouvement** : marge basse 104 px + `safe-area`, rien d'actionnable sous le bouton ni les onglets ;
   ≤ 260 ms, 0 en mouvement réduit ; une faite reste barrée en place.
8. **La preuve sur le produit** : `verifier.cjs` (contraste, 44 px, recouvrement) et captures Playwright du produit
   chargé du jeu SCENARIO, comparées aux maquettes, en CI ; puis un vrai iPhone (Safari, flou, `:has()`, clavier,
   haptique) — rien n'a été vu hors Chromium.

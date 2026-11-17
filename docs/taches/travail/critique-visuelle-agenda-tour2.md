# Critique visuelle de l'Agenda — tour 2 (L3 n°8, contradiction)

32 captures `agenda-*` et 2 références `ecran-aujourdhui-matin-*-clair` ouvertes. Mesures par script dans les PNG
(iPhone ×2 : 176 px par heure).

## 1. Suivi

**Charge projetée (P1) : JUSTE.** Barre de 143 px = 6 h, repère à 4 h (x 690-693). Choisie (tâche de 2 h) : mar. plein
jusqu'au repère + 4 px (4 h 15), fantôme ambre jusqu'au bout (6 h 15 coupé à 6 h, le texte le dit) ; mer. et ven.
59 px (2 h 30) + 34 px azur + 10 px ambre (= 2 h) ; jeu. 47 + 46 px, arrêt au repère. Posée : jeu. plein, les autres
reviennent. Recompte : 4 h 15 = rails 30 + devis 120 + fournisseur 30 + Confirmer 30 + Relire 45 min (deux durées
estimées, dit par l'auteur) ; jeu. = 2 blocs d'1 h. Mer. et ven. reposent sur des tâches sans heure dont la durée
n'est montrée nulle part : rien de faux, rien de vérifiable.

- **Corrigés** : J2, J4, J5, S1, S3-S7, P1, P2, P3, P4, M1-M3, V1-V4, H1-H4, T1, T2, T4.
- **J1 partiel** : 437 pt de grille, 4,9 h visibles (4,7 avant, 5,6 visé) — `agenda-jour-iphone-*`.
- **J3 non** : l'étiquette « Toute la journée » est à x = 3 px du bord sur iPhone (heures à 26) ; bureau 249 contre 261.
- **S2 partiel** : 64 px et cascade faits, mais 11 titres sur 19 coupés — `agenda-semaine-bureau-*`.
- **P5 partiel** : « Recrutement techni… » — `…-planifier-bureau-*`.
- **P6 partiel** : en état « choisie », le week-end prend le fond des cibles (231, 236, 249), comme les jours
  travaillés — `…-planifier-iphone-clair`.
- **T3 partiel** (m1, m2, m3) ; **T5 partiel** : plus brun, désormais mauve (N3).
- Corrections prioritaires : 1, 2, 3, 4, 7, 8, 9 faites ; 5, 6, 10 partielles.

## 2. Défauts nouveaux (transversaux)

- **MAJEUR N1 — le trait « maintenant » barre l'heure de l'essentiel.** `agenda-jour-iphone-*`,
  `agenda-placer-heure-iphone-*` : trait azur aux lignes 652-655, au milieu de « 09:00 – 11:00 » (644-661). Barré
  veut dire fait : la seule ★ ouverte a l'air faite, à côté du bloc fait des rails. Bureau : le trait colle à la
  ligne de base (292 contre 291) ; en Semaine, il souligne « devis révisé ». L'ouverture à 09:00 (J5) l'a rendu
  visible. **Correction** : dans l'emprise d'un bloc, le trait passe SOUS le bloc opaque ; le point et « 09:41 »
  restent dans la gouttière.
- **MAJEUR N2 — Planifier : actuel et projeté mêlés sans le dire.** `…-planifier-iphone-*` : « jeu. 26 · 2 tâches ·
  4 h pour 4 h ». Les tâches sont comptées sans la tâche choisie, les heures avec (2 h + 2 h). On lit « jeudi est
  plein », le contraire de la réponse. Mardi : « 5 tâches · 6 h 15 ». Même chose sur la colonne survolée du bureau.
  **Correction** : chiffres actuels + projection en azur, couleur du fantôme : « 2 tâches · 2 h pour 4 h · **+ 2 h** » ;
  au-delà de 4 h, « + 2 h » en `--tch-surveiller`.
- **MAJEUR N3 — sombre : le bloc ambre devient mauve.** `taches.css:149` mélange `--muted` et le point `in oklch` : fond
  du devis (50, 44, 68), plus violet que le bloc du Salon (39, 38, 62). Chantier et Salon ont le même fond, seul le
  filet les sépare ; c'est le mélange OKLCH déjà refusé par la spec 8 §7. `agenda-jour-*-sombre`,
  `agenda-semaine-bureau-sombre`, `agenda-placer-heure*-sombre`. **Correction** : `color-mix(in srgb, …)` → environ
  (57, 56, 56), gris neutre.
- **MINEUR m1** : deux formes de cible. Placer à une heure : pastilles « + 11:00 – 11:30 » ; Planifier : fond
  `--tch-selection` sans + (P2 : + = Ajouter). **Correction** : créneaux sur `--tch-selection`, sans +.
- **MINEUR m2** : « À placer · 2 » (Jour) contre « À placer 10 » (Semaine, Mois, À venir), même liste, même jour. Mardi :
  Semaine « +3 », Mois 3 points + 4 ; Semaine omet le fait de 08:30, qu'elle montre le lundi. **Correction** :
  « À placer 10 » partout ; « +4 » comme le Mois.
- **MINEUR m3** : la bande « Toute la journée » contient des tâches (« Confirmer la réservation du stand »…) ; la spec 7
  §3 la réserve aux visites et poses, et la colonne d'Aujourd'hui n'y met que la visite. **Correction** : une seule
  règle — celle de l'Agenda, inscrite au §3.
- **MINEUR m4** : barre latérale du bureau blanche (255) dans l'Agenda, teintée (246, 248, 252) dans Aujourd'hui ; en
  sombre, confondue avec le fond (15, 20, 33) au lieu de (8, 12, 25). Panneau droit : (238, 241, 248) contre
  (246, 248, 252). **Correction** : les jetons d'Aujourd'hui.
- **MINEUR m5** : la surcharge n'a que la barre. « 4 h 15 pour 4 h » reste neutre en Semaine et Mois ; l'ambre du
  fantôme est boueux, (167, 129, 110) en clair. **Correction** : phrase en `--tch-surveiller` 600 au-delà du temps
  disponible ; fantôme opaque.

## 3. Écran par écran

**Jour — 7/10 (iPhone 6,5, bureau 8).** PRÉSERVER : bande sur une rangée, + au bout d'« À placer », bloc fait sans
fond, ERP gris + icône, côte à côte. Défauts : N1, N3, J3. MINEUR : le bloc fait de 08:30 dépasse de 6 pt sous
09:00, sans titre → rogner net, ou ouvrir à 08:30 quand un bloc commence dans la demi-heure.

**Semaine — 7,5/10 (iPhone 8,5, bureau 6,5).** PRÉSERVER : la liste iPhone, lundi barré, week-end en une ligne,
« Planifier ma semaine » dans la barre, colonne du jour blanche, cascade. **MAJEUR (reste de S2)** : colonnes de
129 px ; « Rappele… » (activité ERP illisible), « Appeler le f… ». **Correction** : en Semaine et Mois, barre latérale
réduite à un rail d'icônes de 64 px (Planifier la retire déjà) → colonnes d'environ 164 px ; puces « Toute la
journée » sur 2 lignes. Plus m2, m5.

**Planifier ma semaine — 7,5/10 (iPhone 7, bureau 8,5).** PRÉSERVER : seule la tâche choisie cerclée, cibles teintées
sans +, « Placée jeu. 26 · Annuler » dans le volet, aide clavier, « Terminer » en or. Défauts : N2 ; P6 (week-end en
`--muted`, mais touchable). MINEUR : 53 pt vides sous dim. 29, alors que l'indicateur d'accueil barre « Réserver
l'hôtel du salon » (`…-pose-iphone-*`) → volet ancré sous les jours, marge basse de 34 pt.

**Mois — 8,5/10.** PRÉSERVER : points et « +n » gris, Férié, aujourd'hui choisi avec charge, passé atténué, week-end en
64 px. MINEUR : sur bureau, ni « À placer » (présent sur iPhone, exigé par la spec 7 §4) ni liste du jour ; titres
répétés (« Commander les kakémonos » les 5 et 20) → panneau de 340 px, réservoir sans doublon.

**À venir — 8,5/10.** PRÉSERVER : « Demain · mer. 25 », ligne de référence, week-end en une ligne, liste + panneau.
Aucun défaut nouveau notable.

**Placer à une heure — 7,5/10 (iPhone 7, bureau 8,5).** PRÉSERVER : puce cerclée, consigne dans le flux, « Placée à
13:00 · Annuler » + 30 min / 1 h / 2 h, bulles « 13:00 – 13:30 » et « 14:00 · 1 h ». Défauts : N1, N3, m1. MINEUR
(`…-duree-iphone-*`) : défilé à 10:00, le devis n'est plus qu'un rectangle sans titre → titre collé en haut de la
partie visible.

**En-tête** : identique sur iPhone (loupe · Copilote · ⋯, segments fixes, mesurés) ; sur bureau, même ordre, mais la
barre latérale diffère (m4). **Fautes** : 11, légère (N3) ; 1, tolérable (cartes dans des colonnes, Planifier bureau).

## 4. « Toucher puis poser » sans la consigne

Pas encore. Il y a une seule tâche cerclée, les jours s'éclairent et chaque barre porte un fantôme. Mais ce fantôme
fait 24 × 3 pt, et le chiffre omet ce qui est projeté (N2) : sans la phrase, on voit des jours « pleins » qui ne le
sont pas. Avec « + 2 h » en azur sur chaque ligne, le jour dit ce qu'il recevra, et le geste se lit. Garder la
consigne en filet. Non vérifié sur un vrai iPhone.

## 5. Verdict (≥ 8,5 et aucun majeur)

- **Prêts** : Mois (8,5), À venir (8,5), avec leurs mineurs.
- **Pas prêts** : Jour (7 : N1, N3, J3) ; Semaine (7,5 : titres du bureau, m2, m5) ; Planifier (7,5 : N2, P6, marge
  basse) ; Placer à une heure (7,5 : N1, N3, m1, titre collé).

N1, N2 et N3 se corrigent chacune par une règle (trait sous les blocs, « + 2 h » azur, mélange sRGB) : un tour de plus
devrait suffire.

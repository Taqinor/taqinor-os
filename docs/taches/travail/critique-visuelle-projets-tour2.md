# Critique visuelle — Projets, Rythme, Copilote, tuile — second tour (L3 n°8)

Ouvertes : iPhone clair + sombre des 12 écrans ; bureau clair + sombre des 7 écrans à vraie version bureau ;
les deux références Aujourd'hui du matin. Mesuré par script : barres du rythme, couleur de « Nouveau projet »,
marges de la tuile et du bouton Copilote.

## 1. Suivi de la première critique

**16 majeurs.** Corrigés (14) : 1 camembert-case et 2 deux « + » (`projets-liste-iphone-clair`, barre 12/18 = 0,667 mesurée) ;
3 santé en panneau (`projet-liste-iphone-clair`) ; 4 titres du Tableau iPhone ; 6 Gantt (`projet-chronologie-bureau-clair`,
une piste) ; 7 « pas 2 sur 2 » et 8 « En réserve » (`projet-planifier-2-iphone-clair`) ; 9 fenêtre du rythme (barres
mesurées 5,5,4,6,3,5,4,7,5,4 = 48, 6 jours ≥ 5) ; 10 constat avant Mode ; 11 revue 21 · 3 sur 4 ; 12 revue bureau en
segmenté sans Suivant ; 13 fond du Copilote = Aujourd'hui de 8 h 30 ; 14 Siri sans jargon ; 16 visite « journée ».
**Partiels (2)** : 5 Tableau bureau — barre latérale fixe, mais 3 titres sur 2 lignes (`projet-tableau-bureau-clair`) ;
15 cases de la tuile — points pleins pour les tâches, anneau creux pour Visite et Rappeler (`tuile-iphone-clair`).

**10 corrections prioritaires** : 2, 3, 4, 5, 7, 8, 10 corrigées. **6 partielle** (voir M3 ci-dessous).
**9 partielle** (titres du Tableau bureau). **1** : corrigée sur iPhone, pas au bureau (M1).

**Mineurs du tour 1 non corrigés** : séparateur « 12 sur 18 · échéance ven. 4 déc. » (`projets-liste-*`,
`revue-semaine-*`) ; méta de la 1re ligne du cockpit sur deux lignes (`cockpit-carte-iphone-clair`) ; deux
« 6 jours sur 10 » (carte + légende du rythme).

## 2. Nouveau regard, écran par écran

### projets-liste — 8/10
**Préserver** : point + barre fine ; puce de priorité ; « À planifier » azur. iPhone : « Nouveau projet » se voit.
- **MAJEUR M1** `projets-liste-bureau-clair` : « Nouveau projet » n'existe que dans la barre latérale, en
  `--foreground` (pixel mesuré 12,19,53) avec un « + » gris, alors que la même entrée est AZUR sur
  `ecran-aujourdhui-matin-bureau-clair` (35,66,181). L'action propre à l'écran Projets y est plus faible que
  partout ailleurs. Correction : azur + `folder-plus` dans la barre latérale (comme Aujourd'hui), et la ligne
  « Nouveau projet » de l'iPhone en fin de liste dans la colonne du milieu.
- MINEUR : « Basse » en contour, les autres puces pleines : même fond, barres plus pâles.
- MINEUR : Salon Solaire Expo, 8 restantes en 3 jours travaillés, n'est pas « à surveiller » quand Benali
  (6 en 8 jours) l'est. Ajouter le signal ou fixer son rythme dans `SCENARIO.md`.

### projet-liste — 8,5/10
**Préserver** : santé en une ligne, recomptable (8 jours travaillés du 25/11 au 4/12) ; « attend : … » en
pointillé ; jalon losange ; ⋯ sans groupe Vue.
- MINEUR `projet-liste-iphone-clair` : le bouton flottant couvre le « 0 sur 1 » de Clôture.
- MINEUR : pas de pastille « Liste ⌄ » alors que Tableau et Chronologie en ont une (`projet-tableau-iphone-clair`).
- MINEUR bureau : le menu s'ouvre à 50 px à droite de son ⋯ ; l'ancrer dessous.

### projet-tableau — 8/10
**Préserver** : titres sur une ligne sur iPhone, puce d'étape azur, bord de la colonne suivante, « 2 faites ».
- MINEUR `projet-tableau-bureau-clair` : « Valider le plan de / calepinage », « Réceptionner les 16 / panneaux »,
  « Faire signer le PV de / réception » sur deux lignes avec 1 120 px disponibles : colonnes en `1fr`
  (≈ 272 px), retrait du titre 40 px au lieu de 55.

### projet-chronologie — 8,5/10
**Préserver** : frise iPhone ; piste unique au bureau, positions justes au jour près.
- MINEUR bureau : « dim. 6 déc. » aligné à droite de son repère, les autres à gauche : il tombe au-dessus de
  l'échéance du ven. 4. Repère « lun. 7 déc. » aligné à gauche, ou rien.
- MINEUR iPhone : « Aujourd'hui » après Matériel au lieu de dedans ; Études finit le mer. 18, férié.

### projet-planifier — pas 1 : 8,5/10 · pas 2 : 8,5/10
**Préserver** : un seul style de sélection azur ; date expliquée ; carte Copilote à cases et ×.
- MINEUR pas 2 : Site web compte 4 tâches (`projets-liste`), « Premières actions » n'en montre qu'une.

### rythme — 8,5/10
Compris sans juger : oui (pas de rouge, pas de série, mode « Proposé, jamais imposé »). Proposition
recomptable : oui, et le 2e constat bureau aussi (vendredis 3 et 5 → 4 ; autres jours 40/8 → 5).
- MINEUR : le mer. 18 n'ouvre aucun espace (17→19 : 58 px, comme deux jours contigus ; week-end : 80 px).
  Même écart que le week-end, ou repère « férié ».
- MINEUR `rythme-iphone-clair` : bouton Copilote à 13 px du bord droit (gouttière 32 px ailleurs).
- MINEUR : « Passer à 6 » en azur plein, seul bouton d'action plein qui n'est pas or (spec 8 §4).

### revue-semaine — 7,5/10
Légère sur iPhone : oui (4 chiffres, une carte, un segmenté).
- **MAJEUR M3** (chiffres et contenu non recomptables) : la revue est celle du ven. 20, mais Benali « 12 sur
  18 » et Salon « 3 sur 11 » sont les chiffres du mar. 24 à 15 h. Or deux tâches Benali (devis révisé, rails)
  et une Salon (fournisseur) n'ont été faites que le 24 (`SCENARIO.md` §15 h). Il faut 10 sur 18 et 2 sur 11.
  Au bureau, Recrutement donne « Rédiger la fiche de poste » faite cette semaine, alors que le 24 elle est
  encore ouverte, estampillée « → jeu. 26 ». Et « Prochaine action : Publier l'annonce » contredit « attend :
  Trier les CV reçus ». Correction : 10 sur 18 · 2 sur 11. Recrutement : Avancé « Publier l'annonce »,
  Prochaine action « Trier les CV reçus ». Dater l'avancement des projets dans `SCENARIO.md`.
- MINEUR : 4e chiffre « mer. 18 férié » occupe une case de fait sans rien dire ; 3 chiffres, le férié en
  légende.
- MINEUR bureau : cartes étirées (Salon : 200 px vides) ; `align-items: start`.

### copilote — 8,5/10
**Préserver** : fond juste ; puces de demande ; ligne identique à l'écran ; « Garder ces 3 » au pouce.
- MINEUR : « 0 + 2 gardées + 3 = 5 » : le 0 n'a pas de nom ; « 2 gardées + 3 = 5 ».
- MINEUR : « Chantier B… » coupé (iPhone et bureau) ; la raison « projet prioritaire » passe sous le titre.

### mon-iphone — 8,5/10
**Préserver** : « Installer le raccourci » pleine largeur ; « code » au lieu de « jeton ».
- MINEUR : « Dis « Dis Siri, ajoute… » » : « Dis : « Dis Siri, ajoute une tâche », puis parle ».

### tuile — 7,5/10
Envie : oui ; lisible en 2 s : oui (« 1 sur 5 », les deux étoiles, « maj 09:41 »). Chiffres justes
(1 sur 5, essentiel 0 sur 2, 6 restants → 3 montrés + 3).
- **MAJEUR M2** `tuile-iphone-clair`, moyenne : le pied « + 3 autres · maj 09:41 » est à 10 px (5 pt) du bord
  bas, contre 37 px en haut (mesuré). L'en-tête prend deux hauteurs : « 1 » géant, « Aujourd'hui » flottant à
  sa droite, deux points focaux. C'est là qu'on voit que ce n'est pas un vrai widget iOS. Correction : en-tête
  sur une rangée (« Aujourd'hui » à gauche, « 1 sur 5 » + segments à droite), marges 16 pt partout.
- MINEUR : anneau creux devant Visite et Rappeler = petite case ; point plein gris.
- MINEUR grande : « essentiel 0 sur 2 » flotte entre titre et chiffre : sur la ligne de base de « sur 5 ».
- MINEUR grande : « échéance jeu. 26  Valider… » sans séparateur : « Valider le plan de calepinage ·
  échéance jeu. 26 » ; « toucher pour ouvrir Aujourd'hui » est du remplissage, à retirer.

### cockpit-carte — 8,5/10
**Préserver** : segments, « 3 sur 5 · 2 à faire », faite barrée verte. Seul reste : la méta de la 1re ligne
sur deux lignes.

## Ce que les corrections ont cassé
- « Passer à 6 » est devenu un bouton plein azur (hors rôle des couleurs).
- La barre latérale des écrans Projets a perdu l'azur de « Nouveau projet » qu'a Aujourd'hui (M1).
- Le scénario unique a fixé l'avancement des projets sans heure. La revue du 20 reprend donc les chiffres du 24
  (M3).
- Sombre : rien de cassé (plus de brun, élévations justes).

## 3. Verdict (≥ 8,5 et aucun majeur)
**Prêts à construire tels quels** (mineurs à polir pendant la construction) : projet-liste,
projet-chronologie, projet-planifier (pas 1 et 2), rythme, copilote, mon-iphone, cockpit-carte.

**Non prêts** :
- **projets-liste** (8) : M1, « Nouveau projet » azur dans la colonne et la barre latérale au bureau.
- **revue-semaine** (7,5) : M3, avancements datés du ven. 20, contenu Recrutement cohérent.
- **tuile** (7,5) : M2, en-tête sur une rangée, marges 16 pt.
- **projet-tableau** (8) : titres du bureau sur une ligne (colonnes `1fr`, retrait 40 px).

# Relecteur F2-TOIT-a — tour 2 (technicien qui relève et trace le toit)

Compte `rev_toit`, pile `l5cal` (http://127.0.0.1:5241, code `origin/main@bfb859c90`), bureau 1440 × 900 clair, jumeau sombre.
Données créées : leads/calepinages « F2-TOIT Villa Agadir » (1931), « F2-TOIT Halle Casablanca » (1932), « F2-TOIT Maison
Rabat pente » (1943) et la visite technique n° 48 (validée, 30°). Scripts et captures :
`C:/Users/kasri/AppData/Local/Temp/claude/0f9063243c725bde/b36b49db-06cb-474e-a24f-5b0f5d71f674/scratchpad/T2/F2-TOIT-a/`
(`cap/` pour les captures). L'instrument a été saturé vers 01 h 00-01 h 40 ; tout ce qui avait été vu pendant la panne
a été rejoué ensuite (le constat 004 l'a été à 01 h 28 sur pile saine), rien n'est fondé sur une lenteur.

## 1. Verdict

L'étape Toit a désormais les bonnes pièces (tuiles de forme, carte pente, obstacles avec hauteur, trame, gabarits,
ombre mesurée, objets d'environnement, horizon, relief) : 11 corrections sur 21 tiennent à l'écran.
Mais plusieurs saisies du technicien ne reviennent pas à la réouverture (date de photo, hauteur du bâtiment, objets
d'environnement) et des chiffres d'ombrage affichés restent faux après effacement : la confiance d'un ingénieur ne tient pas.
Le mode Guidé cache encore des gestes indispensables (adresse, aide clavier, Annuler de la barre toujours grisé).

## 2. Comptes

Contre-vérification (21 tâches) : **ok 11** (ACAL493, 1288, 1292, 496, 497, 498, 499, 494, 449, 458, 466) ·
**partiel 10** (ACAL1032, 492, 504, 500, 501, 502, 1290, 495, 527, 506) · non-fait 0 · faux 0 · régression 0 ·
déjà-présent 0 · non essayé 0 (des sous-cas non joués sont dits dans « reste » : hors ligne d'ACAL466, cas à un pan
d'ACAL527, recul effectif des modules d'ACAL499).

Cases de matrice cassées :
- K-SAISIE-PERDUE : rechargement × (date de photo, hauteur bâtiment) → 008 ; rechargement × objets d'environnement → 010 ;
  hauteur saisie → calcul de la course du soleil → 017 ; virgule décimale → 009.
- K-DEFAUT-CHOIX : « toit rempli » par défaut (11 panneaux pour une cible de 5, Panneaux marquée « fait ») → 001 ; même
  chose sur la halle C&I (268 panneaux, 192,96 kWc, sans cible) — vu, même constat.
- K-GESTE : bouton Annuler/Rétablir de la barre (souris) → 004 ; touche ? en Guidé → 005 ; champ d'adresse absent en
  Guidé → 007. Tenu : double-clic pour finir une haie, Ctrl + Z, Ctrl + D, glisser un obstacle.

## 3. Constats neufs (registre `registre/constats/T2-F2-TOIT-a.jsonl`)

- **001 S2** — sans choix de l'utilisateur, « Créer le toit » pose le maximum (11 panneaux) et marque Panneaux « fait » alors que « Couvrir la facture — Recommandé » dit 5.
- **002 S2** — « Ensoleillement de chaque panneau » activé : les panneaux restent des aplats noirs, aucune couleur.
- 003 S3 — après « Créer le toit », le toit reste minuscule, la vue passe en 3D, « 12.4 × 8.6 m » avec des points.
- **004 S2** — Annuler et Rétablir de la barre flottante restent grisés (disabled) après toute modification ; seul Ctrl + Z annule.
- 005 S3 — en Guidé la touche ? ouvre une aide de 0 × 0 px (invisible).
- 006 S3 — carte « Obstacle sélectionné » : − et + de 27 px, titre après les menus, phrase de dégagement sur 4 lignes, pas de liste d'obstacles.
- **007 S2** — en Guidé la consigne dit « tapez l'adresse » mais aucun champ d'adresse n'existe.
- **008 S2** — date de la photo, source, hauteur du bâtiment et provenance enregistrées mais vides à la réouverture (« non renseignée »).
- 009 S3 — « Heure solaire de l'image » refuse « 10,5 », accepte « 10.5 ».
- **010 S2** — poteau, arbre, haie enregistrés mais liste vide à la réouverture, et l'ombrage ne les compte plus.
- **011 S2** — la note d'ombrage reste à « −72 % » après « Effacer les ombres », quels que soient les objets posés.
- 012 S3 — panneau Expert : étiquette sur la valeur, boutons d'un mot par ligne, contenu hors du panneau.
- 013 S3 — gabarit de zone jugé comme gabarit d'obstacle avec « longueur_m et largeur_m » à l'écran ; toast à clé interne.
- **014 S2** — Avancé : « Le devis annonce 13 491 kWh/an » et « ≈ 3 462 kWh/an (estimation) » pour la même conception (−74 % d'une ombre effacée).
- **015 S2** — Reprise de la visite : « Aucun écart mesurable » alors que visite 30° / dessin 22° (deux pans non rapprochés, jamais dit).
- 016 S3 — diagramme de course du soleil : libellés rendus à 5-6 px, aucune graduation.
- 017 S3 — course du soleil : « hauteur supposée à 6 m, non mesurée » alors que 6 m mesurée au télémètre est saisie.
- 018 S3 — étape Toit face à Main / ToitSombre : PROCHE, pas FIDÈLE (bulle d'aide, cotes d'arêtes, boussole, widget Soleil, liste d'obstacles, pastille « À confirmer » absents).

## 4. Ce qui est bien (à ne pas casser)

- Tuiles de forme 3 × 2 propres, sélection dorée relue au rechargement ; « 1 pan » réservé à l'Expert.
- Carte pente : « Je ne la connais pas » n'écrit rien et le dit ; « Confirmer » pose la source et le « À confirmer » disparaît.
- Hauteur d'obstacle réellement prise par l'ombrage (98,4 % → 96,5 % d'accès quand 1,2 m → 3 m) ; bandeau « Compte NON engageable » juste.
- Poser en série : « 6 obstacles posés en trame (3 × 2, pas 3,0 m) », refus clair d'un pas nul ; Ctrl + D parle sans sélection.
- Dégagement par type sourcé : « 1,8 m (réglage de votre société — … DS 1-15) » vs « 0,3 m (recul de base, aucun dégagement société pour ce type) ».
- Mesure de hauteur par l'ombre : refus sans date/heure, calcul exact (11,7 m × tan 68,8° = 30,1 m), « à confirmer ».
- Import d'horizon : convention jamais présélectionnée (Importer grisé), 8 points relus après rechargement.
- Relief Copernicus : pente, azimut, source et attribution, « Utiliser cette pente » remplit le champ.
- Gabarits de société : refus sous le champ Source, gabarit posé à ses cotes depuis l'atelier.

## 5. Non essayé, et pourquoi

- Lisibilité sur photo aérienne, détection IA : pile sans imagerie ni clé (fiche de l'instrument).
- Lecture du relief hors ligne : impossible de couper Internet au serveur depuis le poste.
- Tablette, téléphone, WebKit, molette, pincer : non joués faute de temps (priorité aux 21 contre-vérifications).
- Effet du recul de 1,8 m sur les modules (lanterneau posé sur un pan sans modules).
- À vérifier (vu une fois, pas rejoué) : un clic sur le pan nord ne change pas la carte pente (toujours « 22° · face sud »
  alors que ce pan regarde au nord : azimut 0 au document) ; dans la course du soleil une obstruction est libellée
  « Bâtiment » alors qu'aucun bâtiment voisin n'est posé ; rafale de 401 en console quand le jeton expire puis
  rechargement réussi ; la pastille a une fois perdu « Besoin d'après la facture » ; l'enregistrement vide l'historique
  d'annulation ; l'onglet « Reprise de la visite » n'est atteignable que par `?onglet=` (introuvable dans les menus).
- Le 409 automatique de `POST …/simuler/` à chaque ouverture (console) est vu sur tous les calepinages : laissé au
  relecteur Résultats, non inscrit ici.

## 6. Trois propositions pour rejoindre les meilleurs

1. **Un toit qui se relit comme il a été saisi** (fonction) — tout ce que le technicien entre au relevé (date de
   l'image, hauteur et provenance du bâtiment, objets d'environnement, écarts avec la visite) revient à l'identique à la
   réouverture et nourrit les mêmes chiffres ; référence : Aurora (le modèle de site et ses obstructions sont le même
   objet à chaque ouverture, la feuille d'écarts avec la visite se lit avant le permis).
2. **Les gestes du technicien en Guidé** (simplicité) — adresse/coordonnées, Annuler/Rétablir actifs, aide ?, et un
   panneau « Obstacles · n » listant chaque obstacle avec cotes et hauteur, cliquable pour le sélectionner ; référence :
   OpenSolar (recherche d'adresse et liste d'obstructions toujours visibles, undo/redo de barre) et la maquette Main.
3. **Une ombre visible et cohérente** (beauté + exactitude) — carte d'accès solaire réellement colorée sur les
   panneaux, une seule perte d'ombrage affichée partout, diagramme de masques lisible et gradué ; référence : PVsyst
   (diagramme d'ombrage proche gradué en hauteur/azimut) et Aurora (heatmap d'irradiance par module).

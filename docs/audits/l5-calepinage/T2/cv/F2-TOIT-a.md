# Contre-vérification — F2-TOIT-a — Site, toit, relevé (étape Toit)

21 corrections livrées (première moitié de la liste, S1-S2 d'abord) sans preuve en direct, S1-S2 d'abord. Pour chacune : rejoue la « preuve », regarde l'écran, écris UN verdict (ok / partiel / non-fait / faux / regression / deja-present).
Le texte complet d'une tâche (constat d'origine, Given/When/Then) : `grep -n "<id> —" docs/plans/PLAN_AUDIT_CALEPINAGE.md` dans le worktree en lecture.

- **ACAL493** (S2) — Monter dans la carte « Obstacle sélectionné » la saisie de HAUTEUR et le bandeau « Compte NON engageable » que le constructeur pilote déjà ; fini quand une cheminée sélectionnée prend une hauteur tapée de 1,2 m, porte une ombre da
  - Preuve : PA2.3 — cheminée posée, hauteur 1,2 m : carte d'accès solaire avant et après, bandeau « Compte NON engageable ».
- **ACAL494** (S2) — Ajouter à Réglages › Calepinage la section « Gabarits d'obstacle » (voir, créer, modifier, supprimer ; rectangle ou cercle) ; fini quand un gabarit créé là, avec sa source, apparaît dans « Gabarit de votre société » de l'atelier a
  - Preuve : PA2.3 — gabarit créé dans Réglages, atelier rouvert, gabarit posé sur le toit.
- **ACAL495** (S2) — Ajouter à la même section les « gabarits de ZONE » de la société (bande coupe-feu, servitude) ; fini quand une bande créée là, avec sa largeur et sa source, se pose depuis « Gabarit réglementaire » de l'atelier au rechargement
  - Preuve : PA2.3 — bande créée dans Réglages, posée sur le toit depuis l'atelier.
- **ACAL496** (S2) — Remplacer le soleil de prise de vue SUPPOSÉ (jour 80, 10 h 30) par une date et une heure solaire SAISIES ; fini quand tracer une ombre sans l'une ou l'autre est refusé en le disant, et qu'avec elles la hauteur proposée vaut ombre 
  - Preuve : PA2.3 — atelier ERP (ACAL497) : sans date le message, avec date et heure la hauteur proposée.
- **ACAL497** (S2) — Monter dans l'atelier ERP l'outil « Mesurer une hauteur par son ombre » (bouton, heure solaire de l'image, note, liste des ombres, effacement) ; fini quand, date et heure déclarées, pied puis bout d'une ombre de 10 m ajoutent une 
  - Preuve : PA2.3 — image avec un arbre et son ombre : date et heure déclarées, ombre tracée, capture de la ligne et de la perte annuelle.
- **ACAL499** (S2) — Faire lire le dégagement d'un NOUVEAU type d'obstacle dans les réglages de la société, et dire « recul de base, aucun dégagement société pour ce type » quand elle n'en a pas saisi ; fini quand un lanterneau d'une société qui a sai
  - Preuve : PA2.3 — société avec 1,8 m saisi par l'API : lanterneau posé, ligne « réglage de votre société » et modules reculés de 1,8 m.
- **ACAL504** (S2) — Monter la saisie de HAUTEUR du bâtiment et sa note pour que le panneau « Bâtiment » (étages, hauteur d'étage, provenance, acrotère, hauteur OSM proposée) apparaisse dans l'atelier ERP ; fini quand « 6 m » + « mesurée au télémètre 
  - Preuve : PA2.3 — hauteur 6 m tapée, panneau « Bâtiment » visible, refus sans provenance.
- **ACAL527** (S2) — Afficher dans l'onglet « Reprise de la visite » un bandeau « n écarts avec la visite » qui ouvre le tableau Visite / Dessin / Écart ; fini quand l'écart de pente se lit sans ouvrir la visite
  - Preuve : atelier ERP : un lead avec visite validée à 22° et un pan à 15° ; le bandeau et le tableau se lisent ; capture jointe.
- **ACAL1032** (S2) — Monter « Dupliquer » et « Poser en série » dans la carte « Obstacle sélectionné » de l'atelier ERP ; fini quand, sur un obstacle sélectionné, « Dupliquer » ajoute une copie et « Poser en série » (pas, colonnes et lignes saisis : 3
  - Preuve : PA2.3 — halle avec un lanterneau : trame 3 × 2, un seul Annuler, captures avant et après.
- **ACAL1288** (S2) — Présenter les formes de toit en six tuiles illustrées 3 × 2 (Plat, 2 pans, 4 pans, En L, En T, Tracé libre) au lieu de petits boutons texte ; fini quand les six tuiles ont un pictogramme `currentColor`, « En L » et « En T » rempla
  - Preuve : PA2.3 — capture à 1440 × 900 sur un calepinage dans le même état (calepinage 1 de la pile de recette, mode guidé, thème clair), posée à côté de `docs/audits/l5-calepinage/maquettes/Main.dc.html` rendue en `file://` à la même taille : fait 1 de l'étape Toit : six tuiles 3 × 2 — Plat, 2 pans (sélectionnée : bord doré, fond pâle), 4 pans, En L, En T, Tracé libre (pointillé) ; verdict FIDÈLE d'un relecteur neuf (CLAUDE.md 3-bis : la lane écrit le code et le test, l'orchestrateur prend la capture sur la pile reconstruit
- **ACAL1290** (S2) — Présenter la pente et l'orientation en une carte (« 22° · face sud », « À confirmer », « Confirmer », « Je ne la connais pas ») ; fini quand la carte montre la valeur servie, « À confirmer » tant qu'aucune source n'est enregistrée
  - Preuve : PA2.3 — capture à 1440 × 900 sur un calepinage dans le même état (calepinage 1 de la pile de recette, mode guidé, thème clair), posée à côté de `docs/audits/l5-calepinage/maquettes/Main.dc.html` rendue en `file://` à la même taille : fait 3 : carte à cadre doré pâle « 22° · face sud » (20 px), « À confirmer », « Confirmer » bleu nuit, « Je ne la connais pas » en contour ; verdict FIDÈLE d'un relecteur neuf (CLAUDE.md 3-bis : la lane écrit le code et le test, l'orchestrateur prend la capture sur la pile reconstruite
- **ACAL1292** (S2) — Poser sur la carte de l'étape Toit la pastille de chiffres, la pile de zoom et la barre d'outils flottante (sélection/tracé, obstacle, mesure, annuler/rétablir, Plan/3D) ; fini quand ces trois surcouches existent sur la carte et q
  - Preuve : PA2.3 — capture à 1440 × 900 sur un calepinage dans le même état (calepinage 1 de la pile de recette, mode guidé, thème clair), posée à côté de `docs/audits/l5-calepinage/maquettes/Main.dc.html` rendue en `file://` à la même taille : faits 5, 6 et 7 : pastille blanche « Surface du toit | Pans | Besoin d'après la facture » en haut à gauche, pile de zoom en haut à droite, barre flottante centrée en bas (4 outils | annuler/rétablir | Plan/3D), plus de rangée d'angles droits sous la carte ; verdict FIDÈLE d'un relecteu
- **ACAL449** (S3) — Le diagramme de la course du soleil montre les zones d'ombrage (table de facteurs azimut × hauteur du soleil rangée au document) par-dessus la course, l'horizon et les obstructions, sur le même graphique ; fini quand les cellules 
  - Preuve : PA2.5 — calepinage avec un obstacle proche : onglet Course du soleil, zones teintées.
- **ACAL458** (S3) — Importer un profil d'horizon depuis un fichier texte (deux colonnes azimut ; hauteur, ou le format une-hauteur-par-ligne de PVGIS) dans l'onglet Horizon, convention d'azimut CHOISIE par l'utilisateur ; fini quand un fichier de hui
  - Preuve : pile locale — onglet Horizon d'un calepinage, importer un fichier de 8 lignes, enregistrer, recharger la page, relire les points.
- **ACAL466** (S3) — Lire la pente et l'orientation du relief d'un champ au sol sur Copernicus GLO-30 (gratuit, sans compte) et les proposer dans l'écran Terrain ; fini quand `GET calepinages/<pk>/pente-terrain/?surface=<id>` rend pente, azimut de pen
  - Preuve : PA2.5 — champ au sol à Casablanca, « Lire la pente du relief » : pente et source affichées, « Utiliser » remplit le champ ; hors ligne : motif.
- **ACAL492** (S3) — Dire dans l'aide des raccourcis ce que fait Ctrl + D (« Dupliquer l'obstacle sélectionné ») et le faire parler quand rien n'est sélectionné ; fini quand la ligne de l'aide se lit « Dupliquer l'obstacle sélectionné » et que Ctrl + 
  - Preuve : PA2.3 — atelier sans sélection, Ctrl + D : le message ; avec un obstacle : la copie.
- **ACAL498** (S3) — Étendre le menu « Type d'obstacle » de six types (lanterneau, exutoire de fumée, climatiseur, citerne, garde-corps, joint de dilatation), chacun traduit vers son type moteur exact ; fini quand un climatiseur posé à l'atelier arriv
  - Preuve : PA2.3 — climatiseur et citerne posés, document enregistré et rouvert, type conservé.
- **ACAL500** (S3) — Ajouter le genre « poteau » aux objets d'environnement (pose au clic, hauteur et diamètre saisis) ; fini quand un poteau de 8 m de haut et 0,3 m de diamètre, posé au clic, survit à l'enregistrement et fait de l'ombre dans le calcu
  - Preuve : PA2.3 — poteau posé, hauteur et diamètre tapés, atelier rouvert, perte d'ombrage visible.
- **ACAL501** (S3) — Ajouter le genre « ligne » (haie, mur) tracée en polyligne avec hauteur et épaisseur saisies ; fini quand une haie de 20 m, 3 m de haut et 0,5 m d'épaisseur se trace, se relit après enregistrement et fait de l'ombre
  - Preuve : PA2.3 — haie tracée au bord d'un toit, ombrage avant et après.
- **ACAL502** (S3) — Ranger pour chaque arbre une hauteur future saisie (« dans N ans : H m ») et une case « Supposer coupé » ; fini quand les trois survivent à l'enregistrement et qu'un arbre supposé coupé ne fait plus d'ombre
  - Preuve : PA2.3 — arbre au sud, « Supposer coupé » : ombrage avant et après.
- **ACAL506** (S3) — Reconnaître des coordonnées ou un lien de carte collés dans le champ d'adresse et centrer la carte dessus sans appeler le géocodeur ; fini quand « 33.5731, -7.5898 » propose une ligne « Coordonnées collées » qui centre la carte à 
  - Preuve : atelier ERP : coller `33.5731, -7.5898` dans le champ, la carte se centre sur Casablanca sans appel MapTiler (onglet Réseau vide) ; capture jointe.

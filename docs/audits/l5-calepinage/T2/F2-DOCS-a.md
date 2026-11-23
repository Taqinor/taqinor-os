# F2-DOCS-a — tour 2 — Documents : planche, plan de pose, câblage, DXF, rapport d'étude

Relecteur : F2-DOCS-a (compte `rev_docs`), bureau 1440 × 900, thème clair (jumeau sombre regardé), pile `l5cal`
(`origin/main@bfb859c90`). Scripts et captures : `C:/Users/kasri/AppData/Local/Temp/claude/0f9063243c725bde/b36b49db-06cb-474e-a24f-5b0f5d71f674/scratchpad/T2/F2-DOCS-a/`
(`cap/` captures d'écran, `dl/` documents téléchargés et leurs rendus PNG). Les PDF ont été mesurés avec PyMuPDF ;
les DXF avec un petit lecteur écrit pour l'occasion (`lire_dxf.py`, ezdxf absent du poste).

Calepinages créés pour mes preuves : 1945 (toit plat 9,02 × 5,89, deux obstacles en débord, 5 modules),
1946 (plat 18 × 16, 78 modules portrait), 1947 (plat 8 × 6), 1948 (deux pans 12 × 9, 9 modules portrait),
1952 (plat 10 × 6, 16 modules paysage, onduleur, simulation), 1956 (devis automatique DEV-202611-0008, conception
rapide), 1958 (plat 8 × 1,20, pan sans module) ; devis DEV-202611-0009 généré depuis 1945. Ouverts en lecture
seulement : 1899, 1934, 1936 (plans de câblage, chaînes déjà calculées).

## 1. Verdict

La géométrie des documents est maintenant juste : modules dans leur vrai sens, sans recouvrement, échelle imprimée =
échelle dessinée, cotes du toit seul, DXF propre — c'était le cœur S1 de la liste et il tient sur tous mes cas.
Ce qui ne va pas est ailleurs : le **chiffre de production** change selon le document remis (atelier 5 571, devis
6 047, rapport d'étude « P50 » 8 198 kWh pour la même conception), les **cotes aux rives** du plan de pose sont
fausses dès que le champ touche une rive, et l'étape Documents reste PROCHE de sa maquette, pas FIDÈLE.

## 2. Comptes

Contre-vérification (17 tâches) : **ok 8** (ACAL601, 602, 603, 604, 605, 550, 1008, 1065) · **partiel 5**
(ACAL942, 591, 590, 1306, 1307) · non-fait 0 · faux 0 · régression 0 · déjà-présent 0 · **non essayé 4**
(ACAL575, 578, 580, 588 — voir § 5). Arrêt : après tous les S1-S2 et 5 des 8 tâches sans gravité.

Cases de matrice :
- `K-DOC-GEOMETRIE` — planche, DXF et plan de câblage : portrait, paysage, pan d'azimut 90° (1934, en lecture),
  obstacle hors pan : **tiennent**. Cassent sur le même périmètre : numérotation des modules du plan de pose
  (T2-F2-DOCS-a-002), cotes aux rives du plan de pose (ACAL591 partiel), flèche de chaîne invisible (ACAL590 partiel).
  Non jouées : toit + champ au sol, rangées « 180 = sud » saisies.
- `K-GRANDEUR-UNIQUE` — production annuelle : **casse** sur « 1 pan Sud » (atelier 5 571 / Résultats 8 198 « au
  plus » / rapport « P50 » 8 198, T2-F2-DOCS-a-005) et sur « devis généré → /proposal » (6 047 kWh/an,
  T2-F2-DOCS-a-008) ; rapport d'étude vide de production alors que l'écran en montre une (T2-F2-DOCS-a-006).
  kWc et Wc unitaire : tiennent sur 1945 (3,55 kWc, 5 × 710 W partout).

## 3. Constats neufs (registre `registre/constats/T2-F2-DOCS-a.jsonl`)

- **T2-F2-DOCS-a-005 — S1** — le rapport d'étude publie un plafond sous l'étiquette « Production annuelle P50 »
  (8 198,3 kWh) et un productible de 2 309 kWh/kWc sans réserve, contre 5 571 kWh dans l'atelier.
- **T2-F2-DOCS-a-008 — S1** — le client reçoit deux productions pour une conception : proposition 6 047 kWh/an,
  rapport d'étude P50 8 198 kWh ; aucun document ne nomme l'autre.
- **T2-F2-DOCS-a-001 — S2** — « Régler » de « Obstacles dans leur pan » (et de « Matériel électrique désigné »)
  dans Documents ouvre le bloc « PLAN IMPORTÉ » de l'étape Toit (jumeau de T2-S2-PARCOURS-012).
- **T2-F2-DOCS-a-006 — S2** — après une simulation affichée (22 290 kWh), la carte « Rapport d'étude » est offerte
  comme prête et le PDF de 15 pages dit « Production non simulée » ; la note de calcul se dit « périmée » sans
  modification enregistrée.
- T2-F2-DOCS-a-002 — S3 — plan de pose numéroté 6…83, 13…21 : la numérotation ne repart jamais de 1.
- T2-F2-DOCS-a-003 — S3 — le titre du cartouche (planche, plan de pose, câblage) coupe le nom du projet et sort de
  la feuille.
- T2-F2-DOCS-a-004 — S3 — la carte DXF promet « chaque panneau numéroté, avec son pan et sa chaîne » ; le DXF n'a
  ni numéro, ni pan, ni chaîne.
- T2-F2-DOCS-a-007 — S3 — clés techniques (« ohmique_dc », « production.total.p50_kwh ») et « onglet Production »
  dans le rapport remis au client.
- T2-F2-DOCS-a-009 — S3 — en mode Expert, le rail « Documents » s'allume mais l'écran reste celui du Toit.

## 4. Ce qui est bien (à ne pas casser)

- Planche A3 : modules à leur vraie emprise (1,302 × 2,384 m à plat, 2,210 m sous 22°, 2,065 m sous 30°), 0
  recouvrement sur 78 modules, cotes du toit seul (9,02 × 5,89 avec deux obstacles en débord), échelle juste au
  dixième (1/33, 1/38, 1/59, 1/32) et barre cohérente.
- DXF : une polyligne par module à la bonne taille, un seul anneau TOITURE quand le pan est le contour.
- Plan de câblage et calque CHAINES : modules teintés à leur vraie emprise, tournés avec le pan (azimut 90°).
- Plan de pose : phrase de cause au centre d'un pan vide (« le retrait de rive (0,50 m de chaque côté) ne laisse que
  0,20 m sur 1,20 m de large ») ; repère de chantier imprimé avec symbole, texte, légende et cercle de 2,0 m exact ;
  cotes aux rives justes quand le champ est en retrait (0,50 / 3,33 / 1,93 / 0,50 m, vérifiées au calcul).
- Conception rapide : planche refusée avec « conception rapide non vérifiée », acceptée après « J'ai vérifié le
  toit ».
- Étape Documents : deux colonnes, cinq cartes à vignette, « Faits à partir de la version enregistrée à HH:MM »,
  motifs qui disent quoi faire, aide « ? » qui s'ouvre, pas de texte sous 12 px, cibles ≥ 44 px (sauf la bascule
  Guidé/Expert, 30 px), thème sombre propre.

## 5. Non essayé, et pourquoi

- ACAL588 — la preuve passe par `python manage.py shell` : interdit ici (aucune commande docker).
- ACAL575 (pan « existant »), ACAL578 (champ au sol en tables), ACAL580 (poteaux d'ombrière) — non joués faute de
  temps (préparation d'un document importé à pan existant, d'un champ au sol et d'une ombrière) ; je me suis arrêté là.
- ACAL605 : aucune chaîne obtenue sur MES calepinages (« Raccorder automatiquement » ne calcule rien tant que le
  module n'est pas désigné, et le « Régler » du matériel mène au mauvais écran) ; la preuve est faite sur 1899, 1934 et
  1936, ouverts en lecture.
- ACAL1008 : l'omission de l'annexe « paramètres du site » et le rendement de pose au devis ne sont pas départagés
  (le /proposal est identique avant et après vérification, le devis n'a pas été resynchronisé).
- Impressions A4/A3 réelles et lecture « à 1 m » : pas d'imprimante ; toutes les mesures sont faites dans les PDF.
- Fond de carte (tuiles en 403) et clés d'IA : absents de la pile, comme annoncé par la fiche.

À vérifier (vu mais pas prouvé de bout en bout, hors de mes données) :
- 1934 (F2-GESTES) : le plan de câblage liste les chaînes 5 à 9 et « Affectés sans position posée : 50 modules » sans
  les dessiner ; chaînes 3 et 4 à « Voc 1 073 V » ; la mention d'échelle est couverte par les modules.
- « Le plus de panneaux » pose le champ contre les rives (0 m) alors que les retraits réglés valent 0,5 m — peut-être
  voulu (« Pleine rive ») ; les documents le reproduisent fidèlement.
- Cartouche du schéma : « Auteur » = responsable du lead attribué d'office (« Relecteur BEAUTE »), pas la personne
  qui a conçu.
- Panneau « Heure du soleil » en Expert : date « 20/12/2028 ».

## 6. Trois propositions pour rejoindre les meilleures références

1. **Un seul chiffre de production dans tout le dossier, avec son statut** (PVsyst : le rapport ne publie une P50 que
   sur une simulation complète, sinon il n'imprime rien de « P50 »). Le rapport d'étude, la proposition et l'atelier
   lisent la même production servie ; tant que des pertes manquent, tous trois disent « plafond, X pertes non
   comptées » et aucun n'écrit « P50 » ni un productible spécifique.
2. **Une colonne d'aperçu dans l'étape Documents** (maquette v2 `Documents.dc.html` ; HelioScope et PV*SOL montrent
   la planche dans l'application) : la première page du plan de pose affichée dans l'écran, avec Aperçu/Télécharger,
   au lieu d'un nouvel onglet ; une pastille « Prêt · PDF » ou « Il manque … » par carte ; le bandeau bleu visible sans
   défiler.
3. **Un plan de pose de chantier digne d'un bureau d'études** (PV*SOL, plans de cotes ; PVcase, numérotation) :
   numéros 1…N par pan, flèche de chaîne contrastée et repères + / −, quatre cotes aux rives toujours justes et
   placées chacune sur son bord, nom du projet entier dans le cartouche, et un DXF qui porte réellement numéros, pan et
   chaîne comme sa carte le promet.

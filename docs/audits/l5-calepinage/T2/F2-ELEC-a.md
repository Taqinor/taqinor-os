# F2-ELEC-a — tour 2 — l'électricien qui valide le raccordement (fonction, bureau 1440 × 900, clair)

Compte `rev_elec`, pile `l5cal` (http://127.0.0.1:5241). Mes calepinages : 1969 (Casablanca, toit plat 10 × 7, 20 × Canadien 710 W),
1975 (Rabat, 8 modules), 1977 (Fès, 8 modules), 1982 et 1987 (essais de forme : un seul pan), 1985 (Tanger, « 4 pans »).
Scripts et captures : `C:/Users/kasri/AppData/Local/Temp/claude/0f9063243c725bde/b36b49db-06cb-474e-a24f-5b0f5d71f674/scratchpad/T2/F2-ELEC-a/`.

## 1. Verdict

L'étape Électrique a pris la forme de la maquette (pastille, barre d'actions, carte onduleur, « Comparer », « Prêt à envoyer ? »,
écran Schéma avec légende et cartouche) et ses calculs de chaîne sont justes, mais un électricien ne peut pas la mener au bout :
les « Régler » ne mènent nulle part où régler, le PDF « du schéma » n'est pas le schéma, et l'écran donne trois comptes et quatre
verdicts différents pour une même chose. Plus proche de la maquette que fidèle.

## 2. Contre-vérification (19 tâches)

| ok | partiel | non-fait | faux | régression | déjà-présent | non essayé |
|---|---|---|---|---|---|---|
| 6 | 7 | 0 | 0 | 0 | 0 | 6 |

- ok : ACAL934, ACAL612, ACAL613, ACAL617, ACAL630, ACAL631.
- partiel : ACAL1300 (PROCHE, pas FIDÈLE), ACAL1301 (PDF/DXF = plan de câblage), ACAL935 (le résumé d'affectation dit « Prêt »
  quand le dossier est « À compléter : 10 points »), ACAL1299 (chaînes non colorées sur la carte), ACAL619 (tableau illisible),
  ACAL627 (température chaude exigée en plus), ACAL628 (idem + bloc rouge dit deux fois).
- Détail et captures : `registre/evenements/T2-F2-ELEC-a-cv.jsonl`.

Cases de matrice cassées sur mon périmètre :
- **K-GRANDEUR-UNIQUE**, ligne « verdict électrique » : rail 4 / pastille 3 / dossier 10 sur le même écran (006) ; rapport DC/AC
  avec quatre verdicts (005) ; résumé d'affectation « Prêt » contre dossier « À compléter » (ACAL935).
- **K-RETOUR-FAUX**, colonne « matériel non désigné » : « Raccorder automatiquement » ne fait rien et ne dit rien (007) ;
  « Compatible sous réserve » sur un écrêtage permanent (004) ; pose à 0 panneau sans message (003) ; PDF annoncé comme schéma
  (001) ; refus CSV sans sa ligne (011).
- **K-JARGON** : clé brute (`electrical.cheminements`, `core.electrique.onduleurs`), même avertissement ×3, langue (« Choose
  File No file chosen »), accords (« 1 chaînes ») — 008, 009, 013 ; nombres au point anglais dans le tableau du verdict (ACAL619).

## 3. Constats neufs (`registre/constats/T2-F2-ELEC-a.jsonl`)

- 001 S2 — « Télécharger (PDF) » et « DXF » de l'écran Schéma livrent le plan de câblage (modules teintés), pas le schéma unifilaire ; la carte Documents promet « des panneaux au compteur, avec la section de chaque câble ».
- 002 S2 — les « Régler » de Dossier électrique, Chutes de tension et Terre & protections ouvrent tous l'écran Schéma ; « Proposer le tracé » réclame une position d'onduleur qu'aucun geste ne pose (K-IMPASSE).
- 003 S2 — toit « 4 pans » : « Le plus de panneaux » et « Couvrir la facture » posent 0 panneau, sans message ; l'enregistrement fait un 409 sur simuler + erreur de console.
- 004 S3 — surintensité d'entrée (17,6 A pour 13,5 A, « écrêtage permanent ») affichée « Compatible sous réserve », avec un conseil faux.
- 005 S3 — rapport DC/AC : quatre verdicts sur la même étape.
- 006 S3 — trois comptes de points à régler sur le même écran.
- 007 S3 — « Raccorder automatiquement » silencieux quand le module n'est pas désigné.
- 008 S3 — jargon et triplon d'avertissements dans « Modifier une chaîne », « Cheminement & câbles », « Contrôle rapide ».
- 009 S3 — champ fichier en anglais dans « Importer un plan de chaînes (CSV) ».
- 010 S3 — après « Générer le devis », la carte « Prêt à envoyer ? » s'écrase (seul « Électrique » reste visible).
- 011 S3 — import CSV : le module inconnu n'est pas rattaché à sa ligne et renvoie « à l'onglet Affectation » où l'on est déjà.
- 012 S3 — auto-raccordement 1 × 20 sur une seule entrée d'un onduleur à 2 entrées (1 016 V pour 1 100 V).
- 013 S4 — accords « 1 chaînes », « 1 modules », « 1 onduleur(s) ».
- 014 S4 — nom d'onduleur doublé et coupé dans la carte.

## 4. Ce qui est bien (à ne pas casser)

- Les quatre lecteurs de l'état électrique servent les mêmes mots et le même nombre (« À compléter : 19 points ») ; badge ambre au Verdict.
- « Comparer avec N autres onduleurs » : cartes claires (ratio, entrées, pastille, alertes) et « Appliquer » qui enregistre et relit tout.
- Ligne « Tension des chaînes par grand froid — 508,1 V sous 800,0 V à 4,2 °C » : juste, sourcée, à la bonne température du lieu (−2,8 °C à Fès).
- Contrôle rapide d'une chaîne : « Trop haut : 1 142 V — 1 100 V » et « de 4 à 21 modules par chaîne », sans rien dessiner.
- Écran Schéma : mise en page proche de la maquette (blocs, légende servie, cartouche, note bleue) ; côté réseau marqué « à calculer » plutôt qu'inventé.
- Import CSV : refus ligne par ligne et rien d'écrit avant « Enregistrer ».

## 5. Non essayé, et pourquoi

- ACAL1188 : le catalogue de démonstration n'a aucun micro-onduleur ; le 6e contrôle répond « le champ ne compte pas que des micro-onduleurs ». Vu seulement : le champ « Dispositif qui limite l'injection » existe, après « Justification du plafond », dans « Limites imposées par le distributeur » (replié).
- ACAL632, ACAL633, ACAL634 : il faut un champ à trois pans ; le toit « 4 pans » pose 0 panneau (constat 003), « Plat » et « En L » donnent un seul pan (`onduleurs_suggeres` = null, motif « aucun nombre d'onduleurs jusqu'à 1 ne lève… »).
- ACAL635, ACAL636 : exigent la norme électrique et deux réglages de la SOCIÉTÉ (température de service, facteur de regroupement) ; la société de démonstration est partagée par les autres relecteurs, je ne l'ai pas modifiée ; sans norme les tronçons sont « OMIS ».
- Cas « fiche incomplète » d'ACAL627 : le seul produit incomplet est CALX109, exclu.
- Photo aérienne (fond gris), panneaux en aplats noirs : vus en Chromium ET WebKit, je ne juge pas le rendu des panneaux lui-même.
- Simulation complète puis côté réseau du schéma (« Lancez la simulation pour dimensionner le côté réseau ») : non rejoué.

À vérifier (vu une fois, non reproduit ou non capturé) : juste après le premier « Appliquer », la carte disait encore « 10 kW » sous « Deye 15 kW » (correct au second essai) ; le cartouche du schéma met « Auteur : Relecteur BEAUTE » (responsable) sur un calepinage créé par Relecteur ELEC ; carte « Densité maximale — 20 panneaux · 14,40 kWc » (720 W) à côté de « 14,20 kWc · 20 × 710 W » dans le panneau expert (texte lu, pas capturé) ; arrivée par `?onglet=verdict-electrique&mode=expert` : l'onglet est hors champ, colonne à faire défiler.

## 6. Trois propositions

1. **Un vrai schéma unifilaire à télécharger** (fonction) — SolarEdge Designer et OpenSolar sortent le schéma unifilaire en PDF depuis l'écran du câblage : brancher « Télécharger (PDF) » sur le dessin affiché, et mettre le choix de la norme électrique et les longueurs de câble DANS l'étape, là où « Régler » mène.
2. **Chaînage automatique à la manière d'OpenSolar** (fonction + simplicité) — une chaîne par entrée, équilibrée, tension de chaque chaîne écrite sur la carte, chaînes colorées comme la légende (maquette `Electrique.dc.html`) ; et si le module dépasse le courant d'entrée, le dire en tête : « ce panneau ne convient pas à cet onduleur ».
3. **Un seul compte, un seul verdict** (simplicité + beauté) — façon Reonic « Check before you send » : un nombre de points identique au rail, à la pastille et au dossier ; une ligne par contrôle, une seule ligne dorée à régler à la fois, et le module de l'étape Panneaux reconnu d'office par l'électrique.

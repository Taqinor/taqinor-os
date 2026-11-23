# F2-DOCS-b — tour 2 — contre-vérification, seconde moitié de la liste Documents

Relecteur : F2-DOCS-b (compte `rev_b4`), bureau 1440 × 900, thème clair, pile `l5cal` (`origin/main@bfb859c90`).
Scripts, captures et documents téléchargés :
`C:/Users/kasri/AppData/Local/Temp/claude/0f9063243c725bde/b36b49db-06cb-474e-a24f-5b0f5d71f674/scratchpad/T2/F2-DOCS-b/` (`cap/`, `dl/`).
Mes données (préfixe « F2-DOCS-b ») : calepinages 1974 (4 modules, simulé), 1976 (13 modules, chaîne de 9, simulé),
1979 (2 pans + champ au sol + ombrière, système de fixation F2DOCSB-1 créé par moi), 1980 (module de cotes 2278 × 1134) ;
clones faits par `export-layout` / `import-layout` depuis 1899, 1934 et 1936 (lus seulement). Une consigne DC d'essai a
été posée dans les réglages de la société de démonstration (voir § 5).

## 1. Verdict

Les chiffres tiennent : quantités de fixation par pan et au total, tensions par chaîne, attributs du DXF, rapport d'étude
(consommation, pompage) — recomptés à la main, ils sont justes. Ce qui ne va pas est la **mise en page** : plusieurs
lignes neuves (bandeau du schéma, consigne sur le plan de pose, source des pieds, repères de poteaux) sortent de la
feuille ou sont illisibles, et la flèche de chaîne est invisible. Et le comparatif de modules ne s'ouvre pas depuis le
mode Expert qui offre son bouton.

## 2. Comptes (19 tâches : 16 de la liste + ACAL575, 578, 580)

ok **11** (ACAL594, 595, 598, 672, 673, 674, 831, 832, 834, 575, 578) · partiel **6** (ACAL592, 600, 643, 686, 889, 580) ·
non-fait 0 · faux 0 · régression 0 · déjà-présent 0 · non essayé **2** (ACAL596, ACAL833). Le fichier de verdicts porte
17 lignes pour 17 ids : ACAL889 y figure deux fois (même verdict, doublon posé par erreur de ma part).

## 3. Verdicts qui ne sont pas `ok`

- **ACAL592 partiel** — l'encart « Fixation de ce pan » dit « illisible sur le document » pour les composants d'échafaudage
  (ACAL598) que `bom-fixation/` calcule (82,76 et 20,68). Le reste est juste : rail 15,88 + 240,4 = 256,28 m = le projet,
  pinces 8 + 80 = 88, recompté à la main sur le pan de 6 modules.
- **ACAL600 partiel** — en Expert, « Créer les variantes et comparer » crée les variantes (201) puis l'URL devient
  `?onglet=variantes` mais l'écran reste l'atelier 3D. Le comparatif (ligne « Module », « À re-poser dans l'atelier : les
  cotes du module diffèrent ») n'apparaît qu'en rechargeant la page en mode Guidé.
- **ACAL643 partiel** — la flèche de sens de numérotation est tracée dans la couleur de la chaîne par-dessus des modules
  de la même couleur : invisible (seul un tronçon sort dans l'interstice) ; la légende est en très petit.
- **ACAL686 partiel** — la phrase « Côté alternatif non dessiné (disjoncteur AC, compteur de production, TGBT, compteur du
  réseau) » est servie mais le SVG la dessine sur une ligne de 1 568 px dans une planche de 1 122 px : elle est coupée à
  « Côté alternatif non de ». Cas « avec une norme : bandeau vide » non joué.
- **ACAL889 partiel** — la ligne de tension par chaîne est là ; la consigne de la société est imprimée sur une seule
  ligne qui sort de la feuille (« …sous tension dès c ») ; le plan de câblage la replie, pas le plan de pose.
- **ACAL580 partiel** — repères P1…P12 en 7 pt posés sur le trait du contour, sans symbole ; « Pieds de châssis : 68 (portée
  saisie 2,4 m — <source> » coupé au bord de la feuille.
- **ACAL643 (ajout)** — sur 1934 (9 chaînes) les « flèches » sont des traits diagonaux sans pointe traversant les modules ;
  les chaînes 1 et 2 (3 modules chacune) n'en portent aucune visible.

## 4. Constats neufs (`registre/constats/T2-F2-DOCS-b.jsonl`)

- **T2-F2-DOCS-b-001 — S2** — schéma unifilaire : bandeau coupé (voir ACAL686) et nomenclature des équipements vide
  (en-têtes sans lignes), cartouche « Client » vide.
- **T2-F2-DOCS-b-002 — S3** — la carte « Schéma électrique — Des panneaux au compteur, avec la section de chaque câble »
  livre le plan de câblage (modules teintés, aucun câble ni section).
- **T2-F2-DOCS-b-003 — S2** — tension « à froid » des chaînes calculée à +4,6 °C (1934 : +1,9 °C), « TMY + NOCT fiche » :
  la tâche parle de −5 °C ; la tension maxi imprimée sur les plans de chantier est sous-estimée de 6 à 8 % (à confirmer
  par l'ingénieur).
- **T2-F2-DOCS-b-004 — S2** — un composant de fixation dont le libellé contient « marge » (l'exemple même d'ACAL598 :
  « Marge d'échafaudage en hauteur ») fait refuser TOUT le plan de pose en 409 (« une pièce de chantier ne porte aucun
  montant. Trouvé — marge. ») sans dire quel composant.
- **T2-F2-DOCS-b-005 — S3** — encart « Fixation de ce pan » : échafaudage « illisible » (voir ACAL592).
- **T2-F2-DOCS-b-006 — S2** — comparatif de modules non ouvert depuis Expert (voir ACAL600).
- **T2-F2-DOCS-b-007 — S3** — panneau droit de l'atelier Expert : « Factures du lead » et « Brouillon » se chevauchent.

À vérifier (vu, non prouvé de bout en bout) : le rapport d'étude de 1976 imprime 121 977 kWh/an de consommation alors que la
courbe saisie sur 1936 vaut 12 191 kWh/an (écart ×10 non élucidé, domaine F2-CONSO) ; en guidé, « Raccorder » ne passe pas le
module à l'électrique (j'ai dû le désigner par `entree-electrique`) — jumeau du constat de F2-DOCS-a sur le « Régler » du
matériel ; zones[].result.annualKwh de A est recopié dans les variantes par module (le comparatif, lui, n'affiche aucune
production).

## 5. Ce qui est bien (à ne pas casser)

- `variantes-par-module` : noms par module, « — à re-poser » quand les cotes diffèrent, refus d'un produit inconnu en
  nommant le champ, kWc et Wc recalculés, production du résultat retirée.
- Plan de pose : pan existant teinté gris pointillé et légendé « mis en service en 2019 », exclu de la nomenclature ;
  pinces, rails, pieux, poteaux et pieds recomptés à la main et justes.
- DXF du plan de câblage : bloc `MODULE` + un INSERT par module affecté avec CHAINE/MPPT/ONDULEUR/N (1936 : 9 ; 1934 : 48 =
  56 posés − 8 non affectés) ; polylignes et textes conservés.
- Rapport d'étude : section « Consommation et hypothèses » absente (même de l'annexe) sans consommation ; « Pompage »
  absente sans dimensionnement ; refus d'enregistrement du pompage motivé (« calcul incomplet : hmt_saisie »).

## 6. Non essayé, et pourquoi

- **ACAL833** — j'ai déclaré 1976 hors réseau (`entree-electrique` `hors_reseau.actif`, 2 jours d'autonomie) et lancé la
  simulation (job 98) : elle est restée à « running 5 % » plus de dix minutes (les simulations raccordées ont pris 2 min), je
  l'ai laissée tourner sans rien relancer. Seul le côté « raccordé » est prouvé : les rapports de 1976 et 1974 n'impriment
  aucune section « Hors réseau ». À rejouer quand le worker est libre ; la lenteur de la simulation hors réseau est
  peut-être à confier à F2-SIMU. 1976 est aujourd'hui déclaré hors réseau (état de ma donnée de démonstration).

- **ACAL596** — preuve par `manage.py shell` (interdit : aucune commande docker) ; son apparition dans la check-list est
  ACAL597, hors liste.
- Cas « avec une norme choisie » d'ACAL686 : la norme est un réglage de société partagé, le changer aurait modifié les calculs
  des autres relecteurs.
- ACAL831 : « devis lié figé » (verrou) et « lecteur sans `calepinage_gerer` » (un seul compte administrateur).
- ACAL834 : pompe, variateur, volumes et composantes de HMT (aucune pompe de démonstration n'a de prix : aucune n'est retenue).
- ACAL598 : saisie de l'arête d'égout et de la hauteur par l'écran (posées par `import-layout`).
- ACAL595 : cas « mixte ». ACAL578 : « entraxe non saisi ». ACAL580 : « poteaux non décrits ».
- Fond de carte (tuiles 403) et clés d'IA : absents de la pile, comme annoncé.
- Consigne DC : aucun écran de Réglages ne la propose (grep : seul le libellé du profil de départ la cite) ; je l'ai posée par
  `PUT /calepinage/parametres/` (`electrique_societe.consigne_dc_plan_cablage`). Elle reste dans les réglages de la société
  de démonstration (texte « F2-DOCS-b essai … ») : à vider si besoin.

## 7. Trois propositions

1. **Un bandeau qui se replie** (PVsyst, PV*SOL : les notes de planche passent à la ligne dans leur cadre) : une seule
   fonction de mise en forme du texte long, utilisée par le schéma unifilaire, le bandeau du plan de pose (consigne, source
   des pieds) et le plan de câblage — plus aucune phrase servie qui sorte de la feuille.
2. **Une flèche de chaîne qu'on voit** (PVcase, OpenSolar : flèche contrastée et repères + / −) : flèche sombre à pointe
   pleine au-dessus de la teinte, numéro du premier et du dernier module imprimés.
3. **Le comparatif de modules à un geste** (PVcase GM, Pylon) : après « Créer les variantes et comparer », ouvrir le
   comparatif quel que soit le mode, sans exiger de passer en Guidé.

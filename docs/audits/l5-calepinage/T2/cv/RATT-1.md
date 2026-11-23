# Contre-vérification — RATT-1 — Parcours et suivi (preuves perdues pendant la panne de la pile, puis restes du parcours)

15 corrections livrées restées SANS verdict au tour 2 (preuve non jouée par le premier relecteur). Pour chacune : rejoue la « preuve », regarde l'écran, écris UN verdict (ok / partiel / non-fait / faux / regression / deja-present).
Le texte complet d'une tâche (constat d'origine, Given/When/Then) : `grep -n "<id> —" docs/plans/PLAN_AUDIT_CALEPINAGE.md` dans le worktree en lecture.

- **ACAL874** (S3) — Brancher le « ? » sur les grandeurs ÉLECTRIQUES affichées : élévation de tension, marge à la limite, puissance injectée, déséquilibre entre phases, chutes DC et AC cumulées, sections et longueurs des tronçons, alertes non bloquantes ; fini quand chacune porte un « ? » dont la phrase cite la valeur servie
  - Preuve : PA2.5 — étape Électrique, section Raccordement : le « ? » de l'élévation de tension donne la valeur servie.
- **ACAL875** (S3) — Brancher le « ? » sur la famille ÉNERGIE : capacité utile, énergie stockée et restituée, les six flux, hors-réseau (défaillance, pire mois, jours d'autonomie), taux d'autoconsommation et de couverture, horizon retenu et flux annuel ; fini quand les 22 grandeurs sans explication de la batterie et de l'économie en ont une
  - Preuve : PA2.5 — onglet Batterie : le « ? » de la capacité utile et des jours d'autonomie.
- **ACAL877** (S3) — Brancher le « ? » sur la famille POMPAGE : débit à la HMT, pompe retenue, variateur, autonomie du réservoir, m³ mensuels, couverture ; fini quand les 7 grandeurs sans explication de `PompagePanel` en ont une
  - Preuve : PA2.5 — onglet Pompage : le « ? » du débit à la HMT.
- **ACAL878** (S3) — Brancher le « ? » sur la famille COMPARATIF et DOCUMENTS : modules, kWc, P50 et écarts du comparatif des variantes, pages par pièce, statut et avancement du dossier ; fini quand les 4 + 5 grandeurs sans explication de ces écrans en ont une
  - Preuve : PA2.5 — comparatif de deux variantes : le « ? » de l'écart.
- **ACAL879** (S3) — Dire en mots du métier les motifs serveur qui montrent un chemin de code, et un seul vocabulaire pour le statut « omis » ; fini quand une garde ne trouve plus `::`, `[]` ni `.py` dans les textes affichés de `electrique.py` et que les deux écrans disent la même chose
  - Preuve : PA2.5 — onglet Verdict électrique et Raccordement : aucun chemin de code, même mot pour « omis ».
- **ACAL880** (S3) — Ajouter sous le chiffre de production le bouton « Pourquoi ce chiffre ? » (maquette `Resultats.dc.html`) : les trois plus gros postes de pertes de la cascade et un geste chacun ; fini quand l'exemple du contrat rend trois lignes
  - Preuve : PA2.5 — calepinage simulé : « Pourquoi ce chiffre ? » liste trois postes et leur geste.
- **ACAL883** (S3) — Faire dire au comparatif des variantes « mêmes hypothèses de pertes et de météo » ou NOMMER ce qui diffère ; fini quand deux variantes à réglages différents rendent la liste des différences servie
  - Preuve : PA2.5 — deux variantes dont une avec une autre poussière : la réponse nomme la différence.
- **ACAL884** (S3) — Afficher sous le tableau des variantes la ligne « mêmes hypothèses de pertes et de météo » ou la liste de ce qui diffère ; fini quand deux variantes à réglages différents le disent
  - Preuve : PA2.5 — comparatif de deux variantes aux réglages différents : la différence est nommée sous le tableau.
- **ACAL885** (S3) — Ajouter à l'export tableur une feuille « Vérification » qui écrit EN TEXTE les formules de la Voc à froid et du ratio DC/AC avec les valeurs de la fiche ; fini quand un ingénieur retrouve la Voc à froid de l'écran à 0,1 V
  - Preuve : PA2.5 — exporter le tableur d'un calepinage chaîné, refaire le calcul à la main et retrouver la Voc à froid de l'écran.
- **ACAL888** (S3) — Ajouter le panneau « Livré et prévu » (douze valeurs mesurées collées, écart au P50) à l'étape Résultats, en mode expert ; fini quand l'exemple du contrat rend douze écarts lisibles
  - Preuve : PA2.5 — coller les 12 valeurs d'un compteur : l'écart annuel s'affiche.
- **ACAL891** (S3) — Refuser en le disant un pavage au-delà de la limite mesurée de modules : « Au-delà de N modules l'atelier n'est plus fluide » ; fini quand un remplissage qui dépasserait la limite affiche le message et ne pose rien
  - Preuve : PA2.5 — avec une limite basse injectée, « Remplir » affiche le refus.
- **ACAL894** (S3) — Ne nommer PVGIS dans la mention « Estimation rapide » que si PVGIS a répondu, et n'écrire que la perte réellement employée ; fini quand la carte ne dit plus « PVGIS » à côté de « table committée — PVGIS indisponible »
  - Preuve : PA2.5 — toit en pente, PVGIS coupé : une seule provenance.
- **ACAL897** (S3) — Offrir, sur la page « Photos du site », « Image pour le client » : la même projection des modules sur la photo calée, avec un titre et une légende client, sans aucun prix ni chiffre ; fini quand le PNG client porte le titre « Vos panneaux sur la photo de votre toit » et la légende de projection indicative, sans marque de calage
  - Preuve : atelier ERP, page Photos du site : caler une photo, cliquer « Image pour le client », ouvrir le PNG (capture jointe) ; devis déjà envoyés : inchangés, rien ne passe par `/proposal`.
- **ACAL959** (S2) — Faire porter le matériel au modèle : « Partir d'un modèle » recopie le module, l'onduleur et les décisions de matériel, jamais les températures ni les saisies de site ; fini quand un calepinage créé depuis un modèle a déjà son module et son onduleur, températures vides
  - Preuve : rejouer T1-S2-018 : modèle Jinko 710 W + Huawei 100 kW + températures, « Partir d'un modèle » sur le lead d'Agadir : matériel désigné, températures vides.
- **ACAL856** (S2) — Poser le contrat `calepinage_pret_a_envoyer.json` (les contrôles avant l'envoi du devis : code, état ok / info / à régler / bloquant, cause, geste, champ à ouvrir, source du seuil) SEUL sur `main` ; fini quand l'échantillon porte un vert, un info, un orange et un rouge, sépare codes produits et codes réservés, et est déclaré dan
  - Preuve : n/a — échantillon sans route ; la preuve en direct est celle d'ACAL860.

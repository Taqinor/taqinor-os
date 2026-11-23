# Contre-vérification — F2-POSE-b — Pose des panneaux, structure, lestage (étape Panneaux)

17 corrections livrées (seconde moitié de la liste) sans preuve en direct, S1-S2 d'abord. Pour chacune : rejoue la « preuve », regarde l'écran, écris UN verdict (ok / partiel / non-fait / faux / regression / deja-present).
Le texte complet d'une tâche (constat d'origine, Given/When/Then) : `grep -n "<id> —" docs/plans/PLAN_AUDIT_CALEPINAGE.md` dans le worktree en lecture.

- **ACAL546** (S3) — Monter dans l'atelier ERP le tableau comparatif des poses du toit plat (configuration, panneaux, kWc, kWh/an, % du besoin) et l'objectif du classement, sans aucune colonne en MAD ; fini quand un toit plat tracé dans `/calepinage/:
  - Preuve : PA2.5 — calepinage de démo à toit plat : ouvrir « Comparer les poses », trier par kWh/an, cliquer une ligne : la pose change et aucune cellule ne dit MAD.
- **ACAL547** (S3) — Ajouter aux cartes de variantes de l'atelier la carte « Couvre le besoin » (le plus petit nombre de panneaux qui atteint le besoin, avec sa couverture, étiquetée « estimation ») ; fini quand un toit plat dont une pose couvre le be
  - Preuve : PA2.5 — toit plat de démo : la première carte dit « N panneaux suffisent » et un clic pose N.
- **ACAL548** (S3) — Ajouter dans l'atelier ERP le champ « Accès solaire minimal (%) » qui écrit `optimisation.seuilAccesSolaire`, le réglage de la société (ACAL714) servant de valeur de départ ; fini quand saisir 80 sur un pan ombré retire du pavage 
  - Preuve : PA2.5 — pan avec cheminée, saisir 80 : des emplacements disparaissent et la phrase donne leur nombre ; enregistrer, rouvrir : le champ affiche 80.
- **ACAL549** (S3) — Nommer, sous le champ « Panneaux nécessaires », la cause mesurée d'un pan où aucun module ne tient, et la ranger au document ; fini quand un pan de 3 × 1,5 m avec un retrait de rive de 0,80 m affiche la cause avec ses chiffres, et
  - Preuve : PA2.5 — tracer un pan étroit, régler le retrait : la phrase donne les chiffres ; enregistrer, rouvrir : même phrase.
- **ACAL552** (S3) — Afficher, sous les puces Portrait / Paysage d'un toit plat ombré, les deux poses chiffrées (panneaux posés, accès solaire moyen mesuré) ; fini quand un pan avec une cheminée affiche deux lignes cliquables chiffrées et qu'un pan sa
  - Preuve : PA2.5 — toit plat avec cheminée : deux lignes chiffrées, un clic change la pose ; sans cheminée : rien.
- **ACAL553** (S3) — Copier la sélection libre (Ctrl+C) et la coller au curseur (Ctrl+V) dans le pan actif, y compris un autre pan, tout ou rien avec refus nommé ; fini quand une rangée copiée du pan A se colle dans le pan B et qu'un collage qui sorti
  - Preuve : PA2.5 — deux pans, placement libre : copier une rangée du pan A, activer B, Ctrl+V ; coller près d'une rive : refus nommé.
- **ACAL554** (S3) — Ajouter « Appliquer ces réglages à… » sur la ligne d'un pan : le module, le type de toit, la pente et la face du pan source passent aux pans cochés, qui sont re-pavés, après avoir listé ceux déjà réglés à la main ; fini quand appl
  - Preuve : PA2.5 — trois pans, A en 550 Wc : appliquer à B et C, vérifier le module et le compte, annuler.
- **ACAL561** (S3) — Ajouter à la section `degagements` la table « retrait supplémentaire par type d'arête » (faîtage, égout, rive, noue, arêtier), chaque valeur avec sa source, vide par défaut, et son écran ; fini quand l'écran enregistre « égout 0,4
  - Preuve : PA2.5 — saisir « égout 0,40 m, notice X », recharger la page : la ligne demeure.
- **ACAL562** (S3) — Poser d'office, à la fermeture d'un pan, le retrait de la table société sur chaque arête typée sans retrait saisi, marqué « réglage société » ; fini quand un pan à 4 arêtes (2 rives, 1 faîtage, 1 égout) reçoit 3 retraits distincts
  - Preuve : PA2.5 — saisir la table (ACAL561), tracer un pan : l'arête d'égout porte 0,40 m et la pose des panneaux s'en écarte.
- **ACAL565** (S3) — Dessiner la feuille « Plan de lestage » (modules teintés centre, rive, coin, lest inscrit par module, mention de source) et la servir en `plan-lestage.pdf` ; fini quand le PDF sort pour un toit plat lesté dont les quatre paramètre
  - Preuve : PA2.5 — saisir les quatre paramètres (ACAL572) et un système lesté, ouvrir Documents : la carte « Plan de lestage » ouvre un PDF aux trois zones.
- **ACAL566** (S3) — Déclarer sur chaque système de fixation les couvertures qu'il sert (vocabulaire du lead) et proposer le système compatible avec le `type_toiture` du lead ; fini quand un lead « tuiles » reçoit le système « tuiles » et qu'en cas de
  - Preuve : PA2.5 — deux systèmes (tuiles, bac acier), un lead « tuiles » : l'onglet Fixation applique le premier sans geste.
- **ACAL568** (S3) — Contrôler, sur les valeurs de pose déclarées par le système, la distance rail-bord contre la zone de serrage du module et le porte-à-faux du rail, et publier des alertes nommées dans la nomenclature de fixation ; fini quand une di
  - Preuve : PA2.5 — saisir un système avec une distance de 300 mm et une fiche module à 345-415 mm : l'alerte s'affiche dans l'onglet Fixation.
- **ACAL569** (S3) — Ajouter aux règles de quantité de fixation les bases « rangées en portrait », « rangées en paysage », « modules en portrait », « modules en paysage » ; fini quand une règle « 4 rails par rangée » posée sur la base « rangées en pay
  - Preuve : PA2.5 — un pan en paysage et une règle « rails croisés » : la quantité double dans l'onglet Fixation.
- **ACAL593** (S3) — Ajouter à l'atelier une couche « Repères de chantier » (ancre antichute, accès, passage de câble : type, texte, rayon SAISI) posée sur le plan, listée, enregistrée dans `reperesChantier` et relue ; fini quand une ancre posée avec 
  - Preuve : atelier local : poser une ancre de 2 m sur un pan, enregistrer, recharger la page (le repère revient avec son cercle), recentrer sur le lead : le repère suit ; l'impression est la preuve d'ACAL1065.
- **ACAL939** (S3) — Retirer la pesanteur et la masse volumique de l'air des paramètres de lestage à saisir : constantes fixes documentées avec leur source, une saisie existante restant prioritaire ; fini quand la feuille de lestage se calcule sans ce
  - Preuve : Masse et lestage d'un calepinage dont vent, terrain, pressions et frottement sont saisis : plus de ligne « Accélération de la pesanteur : non saisie ».
- **ACAL1296** (S3) — Présenter le conseil d'ombrage en alerte (« N panneaux à l'ombre de … », « Retirer ces N panneaux », « Garder ») ; fini quand l'alerte n'apparaît que si le script rapporte des panneaux sous le seuil, nomme l'obstacle servi et que 
  - Preuve : PA2.3 — capture à 1440 × 900 sur un calepinage dans le même état (calepinage 1 de la pile de recette, mode guidé, thème clair), posée à côté de `docs/audits/l5-calepinage/maquettes/Panneaux.dc.html` rendue en `file://` à la même taille : fait 5 : alerte « N panneaux à l'ombre… » avec « Retirer ces N panneaux » et « Garder », visible seulement parce que le calepinage de recette a des panneaux sous le seuil ; verdict FIDÈLE d'un relecteur neuf (CLAUDE.md 3-bis : la lane écrit le code et le test, l'orchestrateur prend
- **ACAL551** (S4) — Peindre à la position visée la silhouette du panneau (ou du lot) glissé, rouge quand une contrainte dure l'interdit, ambre quand seule une marge réglable est franchie ; fini quand glisser un panneau libre sur un obstacle montre un
  - Preuve : PA2.5 — placement libre, glisser un panneau sur la cheminée : silhouette rouge puis rien au relâchement ; glisser près de la rive : ambre.

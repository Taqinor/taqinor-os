# Contre-vérification — F2-ELEC-b — Électrique et schéma (étape Électrique)

19 corrections livrées (seconde moitié de la liste) sans preuve en direct, S1-S2 d'abord. Pour chacune : rejoue la « preuve », regarde l'écran, écris UN verdict (ok / partiel / non-fait / faux / regression / deja-present).
Le texte complet d'une tâche (constat d'origine, Given/When/Then) : `grep -n "<id> —" docs/plans/PLAN_AUDIT_CALEPINAGE.md` dans le worktree en lecture.

- **ACAL641** (S3) — Saisir, pour chaque pan, le motif de parcours du câble et le point de collecte (aujourd'hui aucun écran ne les écrit) ; fini quand choisir « aller-retour » sur un pan change la longueur publiée de la course DC de ce pan
  - Preuve : pile locale — calepinage à deux pans posés : choisir « aller-retour » + un point de collecte, enregistrer, lire la course DC publiée changer.
- **ACAL642** (S3) — Ordonner l'affectation des modules aux chaînes selon un motif par pan (« le long de la rangée » ou « aller-retour en U ») au lieu du seul ordre du document ; fini quand, sur un pan 2 × 10, le motif en U met les modules 1 à 10 puis
  - Preuve : pile locale — pan de deux rangées, motif « aller-retour en U », ouvrir « Affectation des chaînes » : les modules d'une chaîne se suivent le long du U.
- **ACAL647** (S3) — Proposer les modules ombrés pour un optimiseur dans l'affectation des chaînes (liste calculée par le serveur d'après un seuil saisi par la société) ; fini quand, seuil vide, aucune proposition n'apparaît et, seuil saisi, « 6 modul
  - Preuve : pile locale — saisir un seuil dans les réglages, ouvrir « Affectation des chaînes » d'un calepinage ombré, cliquer « Les équiper ».
- **ACAL664** (S3) — Publier la puissance AC disponible de l'onduleur à la température d'AIR maximale du site d'après la réduction publiée sur sa fiche ; fini quand une fiche « −2 %/°C au-delà de 45 °C » et un site dont l'air monte à 50 °C rendent 90 
  - Preuve : pile locale — onglet Verdict électrique d'un calepinage dont l'onduleur porte la réduction : la ligne s'affiche.
- **ACAL671** (S3) — Publier une ligne « plutôt onduleur de chaîne, micro-onduleurs ou optimiseurs » d'après le nombre d'orientations et le plus grand écart d'accès solaire à l'intérieur d'une chaîne, avec des seuils saisis par la société ; fini quand
  - Preuve : pile locale — onglet Verdict électrique d'un calepinage à trois orientations, seuils saisis puis vides.
- **ACAL675** (S3) — Poser dans la check-list des protections la question « coupure d'urgence DC / arrêt rapide exigé ? » (oui, non, non renseigné) et ajouter l'organe au schéma et à la nomenclature quand la réponse est oui ; fini quand « oui » fait a
  - Preuve : pile locale — décisions de protections avec l'exigence « oui » : l'organe figure au schéma unifilaire et à la nomenclature.
- **ACAL678** (S3) — Avertir, sans bloquer, quand la boucle d'une chaîne dépasse une surface maximale SAISIE par la société (valeur + source, vide par défaut) ; fini quand, la limite saisie à 3 m² avec sa source, la chaîne de 4,5 m² d'ACAL677 ajoute u
  - Preuve : pile locale — saisir la limite dans les réglages du module, ouvrir l'onglet « Affectation des chaînes » (étape Panneaux) : l'alerte figure dans sa liste d'alertes (`frontend/src/features/calepinage/plan/AffectationChaines.jsx:498`, qui affiche `alertes[]` ; `VerdictElectrique.jsx` ne lit pas cette liste) ; texte seulement, aucune interface neuve.
- **ACAL685** (S3) — Afficher dans le verdict électrique (niveau expert) la surface de boucle de chaque chaîne, sa limite société et l'alerte du serveur ; fini quand la ligne « Chaîne 1 : boucle de 4,5 m², limite de 3 m² » s'affiche avec les nombres s
  - Preuve : à rejouer par l'orchestrateur sur la pile locale : calepinage à un pan posé, point de collecte saisi, limite saisie dans les réglages : lire la ligne et l'alerte dans le verdict.
- **ACAL687** (S3) — Faire lire par le verdict de raccordement les phases saisies dans « Saisies électriques » quand le raccordement ne les porte pas, en le disant ; fini quand 1 phase saisie à un seul endroit n'est plus redemandée par le verdict
  - Preuve : pile locale — saisir 1 phase dans « Saisies électriques » seulement : le verdict ne demande plus la saisie.
- **ACAL782** (S3) — Publier le régime loi 82-21 du site dans le bloc raccordement ; fini quand un calepinage de 12 kWc triphasé publie `regime` = « Accord de raccordement » avec sa base légale, sa puissance retenue et « base à confirmer avec le distr
  - Preuve : PA2.5 — ouvrir Raccordement d'un calepinage de 12 kWc : le régime est publié avec sa source.
- **ACAL783** (S3) — Comparer la part injectée simulée au plafond légal de 20 % de la production annuelle (loi 82-21 art. 12) et la publier, avec un avertissement non bloquant quand elle le dépasse ; fini quand une simulation à 35 % d'injection publie
  - Preuve : PA2.5 — simuler un site sans consommation de jour : l'avertissement apparaît.
- **ACAL784** (S3) — Afficher le régime 82-21 et la part injectée face au plafond en deux lignes de l'onglet Raccordement ; fini quand les deux lignes se lisent sur l'exemple du contrat, toujours visibles, avec un voyant orange au-delà du plafond
  - Preuve : PA2.5 — ouvrir Raccordement d'un calepinage de 12 kWc simulé : les deux lignes.
- **ACAL822** (S3) — Faire porter au gabarit de dossier réglementaire une date « vérifié le » et des limites saisies `{code, valeur, unité, source}`, pour le dossier marocain générique (D-ACAL-43) ; fini quand un gabarit « Dossier marocain générique »
  - Preuve : PA2.5 — API seulement : créer le gabarit d'essai, le relire, puis envoyer une limite sans source.
- **ACAL824** (S3) — Dire sur chaque dossier « vérifié le … » et avertir « vérifié il y a plus de N jours » quand la société a réglé N ; fini quand un gabarit vérifié il y a 400 jours avec N = 365 affiche l'avertissement, et qu'aucun avertissement ne 
  - Preuve : PA2.5 — Réglages › Électrique société : saisir N avec sa source, puis onglet Documents : la ligne et le bandeau.
- **ACAL827** (S3) — Saisir le plafond d'injection en ampères et publier sa conversion en kW ; fini quand 16 A en triphasé à 400 V avec un cos φ imposé de 1 publient `calcul.plafond_injection_kw_converti` = 11,085 kW avec sa formule
  - Preuve : PA2.5 — API : POST du cas, puis relancer la simulation : l'écrêtage cite 11,085 kW.
- **ACAL830** (S3) — Ajouter au bloc « Raccordement » (étape Électrique, niveau expert, replié) le plafond en ampères, trois plages horaires et le plafond de soutirage ; fini quand ces champs survivent au rechargement et que le kW converti s'affiche s
  - Preuve : PA2.5 — étape Électrique, niveau expert : saisir 16 A et une plage, enregistrer, recharger.
- **ACAL887** (S3) — Enregistrer douze valeurs mensuelles de production MESURÉE par calepinage et servir leur écart au P50 mensuel (`GET/PUT calepinages/<pk>/production-mesuree/`) ; fini quand douze mesures collées rendent douze écarts en pourcentage
  - Preuve : PA2.5 — coller 12 mesures sur un calepinage simulé : douze écarts en pourcentage.
- **ACAL895** (S3) — Semer, de façon IDEMPOTENTE, trois MODÈLES de bibliothèque marqués « Exemple » (villa à toit incliné, toit plat C&I est-ouest, champ au sol), sans lead, client ni devis, jamais comptés dans les chiffres ; fini quand `semer_exemple
  - Preuve : pile locale : dry-run puis `--apply`, ouvrir la bibliothèque (badge « Exemple »), créer un projet depuis un exemple pour un lead d'essai ; la production ne reçoit ces lignes que sur un geste de Reda (commande `--apply`, jamais au déploiement).
- **ACAL974** (S3) — Proposer la température minimale et maximale du site tirées de la météo, marquées « proposée — à confirmer » ; fini quand les champs vides de Saisies électriques montrent la proposition servie (ou rien) avec un bouton « Utiliser c
  - Preuve : PA2.5 — calepinage avec épingle et module à fiche complète : Saisies électriques propose les températures, champs modifiables (rejoué par l'orchestrateur, PVGIS joignable).

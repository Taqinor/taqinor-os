# Squelette — complément ACAL « L5 » du 2026-11-20 (orchestrateur)

Constat = `C-ACAL-L5-<numéro de la tâche>` (ex. ACAL404 ↔ C-ACAL-L5-404). Les titres ci-dessous sont des INTENTIONS :
le rédacteur vérifie la prémisse dans le code, borne la fin (« fini quand … »), et choisit les vrais fichiers.
Références mesurées (R1) : rail de 36 onglets ; ≈ 100 contrôles sur la page atelier ; 37 clés de réglage sans valeur de
départ ; simulation non lancée seule ; pas d'enregistrement automatique serveur ; deux dialectes visuels (39 fichiers en
classes du site public) ; atelier = îlot sombre codé en dur ; `HelpTip` jamais utilisé dans le module.

## LOT W1 — M0 « Figer et contrats » (ACAL382-391), M3 « gardes » (ACAL478-484), GATED (ACAL485-489), acceptation (ACAL490)
Sections de sortie : `### ACAL — M0 contrats (seuls sur main d'abord)`, `### ACAL — M3 nettoyage et gardes`,
`### ACAL — GATED (ne PAS auto-construire)`, et la tâche `(@acceptation)` (gabarit D de r1/a4, format v3).

- ACAL382 — Figer les chiffres servis par la simulation : golden de caractérisation sur 3 projets de référence (toit
  incliné résidentiel, toit plat C&I à châssis, champ au sol), enregistré sur le commit intact, verrouillé (un écart =
  échec nommé ; mise à jour seulement par une tâche qui nomme le changement voulu). Réutiliser les goldens existants
  s'ils couvrent déjà cela (alors la tâche = compléter les cas manquants).
- ACAL383 — Figer les gestes du constructeur : document `roof_layout` émis par une séquence scriptée (tracé, pente,
  remplissage, obstacle, enregistrement) dans le test de parcours existant `apps/web/tests/userJourneyPro11.test.ts`.
- ACAL384 — Base visuelle : captures Playwright des écrans centraux du module (liste, atelier — étape toit, production,
  documents) ajoutées à la spec visuelle existante du dépôt (le module n'y a aucune entrée).
- ACAL385 — Mesures d'écran rejouables (base des critères simplicité/beauté) : spec qui compte, sur l'atelier ouvert,
  les contrôles visibles au premier écran, les tailles de texte distinctes, les cibles < 44 px, le nombre de gestes
  « lead → résultat de production », et écrit un JSON de base commité.
- ACAL386 — Contrat `parcours_guide.json` : étapes (toit, panneaux, electrique, resultats, documents), état de chaque
  étape (a_faire / en_cours / fait / bloque), liste « ce qui manque » structurée {code, message, etape, cible, gravite}
  dédupliquée. Contrat seul (échantillon + test de forme).
- ACAL387 — Contrat `profil_depart.json` : valeurs de départ sourcées {cle, valeur, unite, source, reference, url,
  date_lecture} pour les clés du registre `parametres_cles.py`. Contrat seul. [dépend de la décision D-ACAL-L5-1]
- ACAL388 — Contrat `balayage.json` : demande (axes : inclinaison, azimut, pas inter-rangées, ratio DC/AC ; bornes ;
  pas) et résultat (grille, optimum, état de la tâche asynchrone).
- ACAL389 — Contrat `table_ombrage.json` / clé du schéma `roof_layout_v2` : table des facteurs d'ombrage par azimut ×
  hauteur du soleil + facteur de vue du ciel par zone (pour ACAL459-461).
- ACAL390 — Liste des promesses du complément en DONNÉES (`apps/calepinage/parcours/` : une entrée par promesse, son
  oracle = test ou spec, statut) + garde : une promesse « à venir » ne peut que disparaître (liste qui rétrécit).
- ACAL391 — (libre)

- ACAL478 — Garde « budget de simplicité » : la spec de mesures (ACAL385) échoue si le mode guidé dépasse des seuils
  fixés (≤ 5 étapes, ≤ N contrôles au premier écran, 0 saisie technique obligatoire avant un premier résultat). Seuils
  = valeurs mesurées après ACAL392-400, jamais un chiffre inventé ici : la tâche lit la base et la verrouille.
- ACAL479 — Garde « un seul langage visuel » : test qui refuse une classe héritée du site public (`cine-`, `lune-`,
  `nuit-`, `tech-label`) dans `frontend/src/features/calepinage/**` (liste d'exceptions qui rétrécit).
- ACAL480 — Garde « parité atelier / serveur » : sur les projets de référence d'ACAL382, la production affichée par le
  constructeur (navigateur) et celle de la simulation serveur s'écartent de moins d'un seuil publié ; l'écart est
  affiché en interne (D-ACAL-6). Vérifier ce qu'ACAL356/381 comparent déjà.
- ACAL481 — Garde « raccourcis » : une seule table de raccourcis fait foi (après ACAL414) ; test qui échoue si une
  touche nue déclenche une action destructive ou si deux tables divergent.
- ACAL482 — Parcours téléphone sous WebKit : spec `frontend/e2e/calepinage-telephone.spec.js` (relevé + consultation à
  390 × 844). Vérifier qui possède `frontend/playwright.config.js` : si autre propriétaire, la tâche n'inclut PAS ce
  fichier et dit comment la spec est lancée par le projet existant ; sinon « à router ».
- ACAL483, ACAL484 — (libres)

- ACAL485 [GATED D-CALX-PAYANT] — Détection assistée du toit par vision IA sur l'image satellite (coût d'appels API).
- ACAL486 [GATED : attend un rapport PVsyst réel fourni par Reda] — Comparer le moteur à un rapport PVsyst sur le même
  projet et publier l'écart dans la note de validation.
- ACAL487 [GATED : autre propriétaire (web/ventes)] — Vue 3D interactive (soleil animé) sur la page publique du devis,
  chiffres = ceux du devis. Vérifier d'abord ce que la page publique montre déjà (`viewerFullBoot.ts`,
  `ventes/ToitClientOverlay.jsx`) et le dire.
- ACAL488, ACAL489 — (libres, GATED)

- ACAL490 (@acceptation) — Acceptation en direct du complément : l'orchestrateur rejoue sur la pile locale le parcours
  guidé « lead → toit → panneaux → électrique → résultat complet → devis → documents » (bureau 1440 × 900 clair et
  sombre, tablette 820 × 1180, téléphone 390 × 844), 3 passages tous verts pour les parcours critiques, les chiffres
  d'ACAL382 inchangés sauf changements nommés, mesures d'ACAL385 avant/après, et liste les gestes de Reda (deploy,
  30 min sur son appareil, 5 jours d'usage réel, 3 questions de débrief).

## LOT W2 — M1 « Simplicité : parcours et coquille ERP » (ACAL392-409) → `### ACAL — M1 bloquant-fondateur`
- ACAL392 — Servir l'état du parcours guidé (endpoint `calepinages/<pk>/parcours/`) calculé depuis le document, le
  résultat et les réglages : état des 5 étapes + « ce qui manque » dédupliqué (aujourd'hui l'onglet Production répète
  3 fois le même avertissement de norme électrique — capture `docs/audits/acceptation/ACAL/traces/2026-11-01/ACAL351-onglet-production.jpg`).
- ACAL393 — Rail guidé à 5 étapes dans l'atelier (Toit → Panneaux → Électrique → Résultats → Documents) affiché par
  défaut à la place du rail de 36 onglets ; chaque étape ne montre que ses panneaux essentiels (table de
  correspondance onglet → étape + niveau essentiel/expert dans un fichier neuf, `onglets.js` restant en ajout seul).
- ACAL394 — Mode expert : un interrupteur « Mode expert », mémorisé par utilisateur, qui rend tous les onglets, rangés
  sous les 5 étapes ; guidé par défaut pour tous (choix pris seul, réversible — D-ACAL-L5-2 si Reda répond autrement).
- ACAL395 — Étape « Électrique » en un écran : une synthèse (« conforme » / « n points à régler ») et des sections
  repliables au lieu de 7 onglets (Équipements, Cheminement & câbles, Raccordement, Verdict, Matériel, Saisies,
  Décisions) en mode guidé.
- ACAL396 — Fusionner « Pertes » et « Postes de pertes » : le diagramme et l'édition d'un poste sur le même panneau.
- ACAL397 — « Ce qui manque » en liste d'actions : chaque ligne ouvre le champ exact (étape + panneau + champ), les
  doublons sont regroupés avec leur nombre, triée par gravité.
- ACAL398 — Simulation automatique : après un enregistrement qui périme la simulation, elle est relancée seule et le
  résultat se rafraîchit ; le bouton reste (« Recalculer »). Vérifier ce que fait déjà le serveur à l'enregistrement.
- ACAL399 — Barre d'enregistrement toujours visible + indicateur « Enregistré à HH:MM » / « Modifications non
  enregistrées » (le bouton vert est aujourd'hui en bas d'une très longue page).
- ACAL400 — Brouillon enregistré côté serveur (reprise sur un autre poste) sans créer de version : aujourd'hui le
  brouillon n'est que local (`features/calepinage/brouillon.js`). Respecter les deux empreintes (D-ACAL-4/21).
- ACAL401 — Barre de résumé vivante : nombre de panneaux, kWc, production (marquée « estimation » tant que la
  simulation serveur n'a pas tourné), mise à jour pendant l'édition.
- ACAL402 — Atelier en disposition « studio » pleine hauteur : carte/3D au centre, étapes à gauche, inspecteur à
  droite, plus de page à défilement long (`ToitureDesign.jsx` mono-écrivain).
- ACAL403 — Appliquer le profil de départ (serveur) : un geste d'administrateur remplit les SEULES clés vides du
  registre depuis `profil_depart.json` (valeur + source + référence), journalisé, jamais d'écrasement, retirable.
  [D-ACAL-L5-1]
- ACAL404 — Compiler le profil de départ (données) : chaque valeur vient d'une source publiée vérifiable (norme, notice
  constructeur, documentation PVsyst/PVGIS/NREL) avec URL et date de lecture ; une clé sans source vérifiable reste
  ABSENTE du fichier. Tâche de données, `@model: opus`. [D-ACAL-L5-1]
- ACAL405 — Écran « Démarrage rapide » dans Réglages simulation : tableau des valeurs proposées avec leur source, un
  bouton « Appliquer aux réglages vides » ; dans les résultats, mention « valeur publiée, non mesurée » sur les étapes
  qui en dépendent. [D-ACAL-L5-1]
- ACAL406 — Fiche calepinage : remplacer l'affichage brut (`JSON.stringify` des données personnalisées, « Source de la
  cible » = chaîne serveur) par des libellés lisibles.
- ACAL407 — Une seule adresse par panneau : `?onglet=` et la route profonde donnent la même URL canonique ; les deux
  liens texte hors rail (« Comparer les variantes », « Photos du site ») rejoignent leur étape.
- ACAL408 — Guide utilisateur à jour (`docs/GUIDE_UTILISATEUR_ERP.md`, section Calepinage) : menu réel, parcours en 5
  étapes, simulation automatique. `@after` les tâches qu'il décrit. (Fichier sous `docs/` : sans propriétaire — vérifie
  que le validateur l'accepte ; sinon « à router ».)
- ACAL409 — (libre)

## LOT W3 — M1 « Simplicité : gestes du constructeur » (ACAL410-426) → `### ACAL — M2` (sous-titre atelier)
- ACAL410 — Boutons de formes de toit prêtes (2 pans, 4 pans, L, T) : le moteur existe sans bouton
  (`scene3d.ts::generateRoofShapePans`, `zones.ts::buildAreasFromShape`).
- ACAL411 — Barre « Pivoter / Aligner / Répartir » sur une sélection de panneaux : le moteur existe sans bouton
  (`layoutEditor.ts::freeRotateSelection`, `freeAlignSelection`, `freeDistributeSelection`).
- ACAL412 — Annuler / Rétablir partout (tracé, obstacles, disposition) avec deux boutons visibles et Ctrl+Z / Ctrl+Y.
- ACAL413 — « Effacer » et « Tout effacer » réversibles : bandeau « Annuler » après le geste (aucune confirmation
  n'existe aujourd'hui — à vérifier) ; le geste caché Alt+clic (supprimer un panneau) reçoit un bouton visible.
- ACAL414 — Une seule table de raccourcis (aujourd'hui 3 : `clavier.ts`, `RaccourcisAtelier.helpers.js`,
  `layoutEditor.ts`) + panneau d'aide unique.
- ACAL415 — Palette de commandes de l'atelier : tous les outils et étapes cherchables en mots simples (vérifier si la
  palette globale ⌘K de l'ERP expose un registre où s'inscrire ; sinon palette locale).
- ACAL416 — Une seule saisie de pente (aujourd'hui 3 entrées dans des écrans différents) avec l'aide « je ne connais
  pas la pente » (cotes ou photo).
- ACAL417 — Pente et orientation par défaut jamais présentées comme confirmées : tant que l'utilisateur n'a pas
  confirmé (ou qu'une source ne les donne pas), elles portent « à confirmer » et la génération du devis le signale
  (aujourd'hui 22° / Sud apparaissent sélectionnés et la production semble plausible sans saisie — à vérifier).
- ACAL418 — Barre d'outils contextuelle sur la sélection (panneau, pan, obstacle) à la place de la fenêtre repliée
  « Personnaliser la disposition ».
- ACAL419 — Libellés en langage clair + info-bulle `HelpTip` sur chaque terme technique du rail et des panneaux
  (glossaire unique ; `HelpTip` n'est importé nulle part dans le module).
- ACAL420 — Première ouverture guidée : états vides qui disent le prochain geste (« Localisez le toit », « Tracez le
  contour ou choisissez une forme ») sur la carte et dans chaque étape.
- ACAL421 — « Conception automatique » en un geste : depuis l'adresse, emprise du bâtiment (détection OSM déjà servie
  — vérifier la route qu'utilise le constructeur) → forme → remplissage optimal → chaînes → simulation, puis
  correction à la main. Rester dans les fichiers du calepinage.
- ACAL422 — Toit par cotes : saisir longueur × largeur (et une forme prête) crée le contour sans tracer sur la carte
  (imagerie satellite inégale au Maroc).
- ACAL423 — Atelier lisible au téléphone (390 × 844) pour consulter et relever : pas de défilement horizontal, rail
  d'étapes en barre basse, cibles tactiles ≥ 44 px.
- ACAL424 — Orthophoto de drone géoréférencée (image + fichier de calage) posée comme fond sans calage manuel (le
  fond importé existe avec calage 2 points : `underlay.ts`).
- ACAL425 — Aides d'alignement intelligentes pendant le déplacement (repères d'alignement sur les rangées et les rives).
- ACAL426 — Copier / coller une sélection de panneaux ou d'obstacles (dupliquer et miroir existent ; coller absent).

## LOT W4 — M2 « Beauté : système visuel et 3D » (ACAL427-442) → `### ACAL — M2` (sous-titre beauté)
- ACAL427 — Migrer les panneaux de `features/calepinage/atelier/**` des classes héritées du site public vers les jetons
  ERP (`design/tokens.css`, composants `ui/*`).
- ACAL428 — Idem pour `production/`, `electrique/`, `economie/`, `documents/`.
- ACAL429 — Idem pour les pages liste, fiche, bibliothèque, réglages, comparaisons.
- ACAL430 — L'atelier suit le thème clair/sombre de l'ERP (fin de l'îlot sombre codé en dur `.rp9-host`, palette en
  variables). Vérifier le propriétaire de `frontend/src/styles/roofbuilder.css`.
- ACAL431 — Ciel et atmosphère dans la scène 3D (dégradé suivant la position du soleil) — fichier neuf sous
  `roofPro11/`, `scene3d.ts` (3 115 l.) ne grossit pas.
- ACAL432 — Matériaux de toit (tuile, étanchéité/béton, bac acier) selon le type de toit choisi.
- ACAL433 — Apparence du module posé = celle du produit choisi au stock (couleur des cellules, cadre, dimensions) au
  lieu d'une texture fixe « Canadian Solar 720 W » (à vérifier dans le code).
- ACAL434 — Frise du soleil : une barre de temps (heure + mois) avec lecture/pause et dates repères, ombres en direct
  (le curseur et la lecture existent — vérifier ce qui manque : frise, dates repères).
- ACAL435 — Vues de caméra prêtes (dessus, sud, 3/4, « vue client ») avec transitions douces.
- ACAL436 — Note d'ensoleillement par panneau (pastille en %) + légende de la carte de chaleur à l'écran.
- ACAL437 — Squelettes de chargement à la place du simple indicateur tournant sur les panneaux du rail.
- ACAL438 — Échelle typographique et tactile : ramener l'atelier aux tailles de texte de l'ERP (nombre mesuré par
  ACAL385) et aux cibles ≥ 44 px.
- ACAL439 — Accessibilité : spec automatique (axe, version de la CI) sur les écrans centraux, contraste AA, focus
  visible, rail utilisable au clavier — 0 violation.
- ACAL440 — Fluidité mesurée : spec de performance (délai d'interaction pendant un glisser de panneaux, 500 modules)
  avec un budget lu sur la base (web.dev : INP ≤ 200 ms = « bon »), sur un vrai rendu WebGL.
- ACAL441 — Export d'image HD « vue client » (ciel, matériaux) pour la planche interne — vérifier l'export HD existant
  (`scene3d.ts`, jusqu'à 8 192 px) et ne garder que le manque.
- ACAL442 — (libre)

## LOT W5 — M2 « Beauté : résultats et graphiques » (ACAL443-453) → `### ACAL — M2` (sous-titre résultats)
- ACAL443 — Écran Résultats à un chiffre héros : production annuelle en grand, 3 chiffres secondaires, détails
  (P75/P90/P95, variabilité) repliés ; quand le résultat est incomplet, UN état « Résultat incomplet — n réglages à
  faire » avec progression, à la place de 9 tuiles « non calculée ».
- ACAL444 — Diagramme de pertes « du soleil au réseau » interactif : chaque étape de la chaîne (ordre serveur
  `chaine_pertes.py::ORDRE_ETAPES`) avec valeur, source, et étapes omises grisées « à renseigner » (référence : le
  diagramme de pertes de PVsyst). `DiagrammePertes.jsx` existe en barres — ne garder que le manque.
- ACAL445 — Graphique mensuel production / consommation / autoconsommation (aujourd'hui un tableau).
- ACAL446 — Journée type : courbes production / consommation / batterie (par saison).
- ACAL447 — État de charge de la batterie sur une semaine type (données du pilotage batterie déjà calculé).
- ACAL448 — Graphique des flux de trésorerie (AFFICHAGE de `PanneauEconomie.jsx::TableauFlux`, données de ventes
  inchangées).
- ACAL449 — Diagramme d'ombrage : course du soleil + masque d'horizon + lignes d'iso-ombrage sur un seul graphique
  (`SunDiagram.jsx`, `CourseSoleil.jsx`, `HorizonPanel.jsx` existent séparés) — `@after` ACAL459.
- ACAL450 — Carte « Conseils » : afficher les propositions du moteur (`core/calepinage/recommandations.py::proposer`,
  `sensibilites.py::batterie`) si elles n'ont aucun écran (à prouver), en phrases simples avec « Appliquer ».
- ACAL451 — Rapport d'étude : page « Bilans et résultats principaux » (tableau mensuel irradiation horizontale,
  irradiation dans le plan, énergie champ, énergie réseau, indice de performance) — vérifier les 13 sections existantes.
- ACAL452 — Rapport d'étude : page « Diagramme de pertes » complète (même chaîne qu'ACAL444) si absente.
- ACAL453 — (libre)

## LOT W6a — M3fn « Fonctions de classe PVsyst : météo, irradiation, ombrage » (ACAL454-464) → `### ACAL — M2` (sous-titre physique)
- ACAL454 — Import météo EPW et CSV horaire horizontal (GHI/DHI/DNI) : aujourd'hui seul un CSV horaire dans le plan
  des modules est accepté et un fichier horizontal est refusé (`meteo_fichier.py::MOTIF_HORIZONTAL_SEUL`).
- ACAL455 — Transposition horizontal → plan des modules avec pvlib (modèle nommé dans le résultat) pour ces fichiers
  (pvlib épinglé, utilisé seulement dans un test aujourd'hui).
- ACAL456 — Décomposition du global en direct + diffus quand le fichier ne donne que le global (modèle pvlib nommé).
- ACAL457 — Probabilités de dépassement étendues : P99 et un Pxx au choix (aujourd'hui P50/75/90/95 :
  `services/incertitude.py::_quantiles`), sous la règle D-ACAL-7 (cachées si pertes incomplètes).
- ACAL458 — Import d'un masque d'horizon (fichier azimut ; hauteur, dont le format `.HOR`) en plus de PVGIS et de la
  saisie manuelle.
- ACAL459 — Table des facteurs d'ombrage (azimut × hauteur du soleil) calculée par le moteur d'ombrage du navigateur
  et rangée au document (`shadingEngine.ts`), `@after` ACAL389.
- ACAL460 — Facteur de vue du ciel par zone calculé par le constructeur et rangé au document, `@after` ACAL389.
- ACAL461 — Étape serveur « ombrage du diffus » : applique le facteur de vue du ciel à la part diffuse (aujourd'hui
  seul le direct est dératé), omise et nommée si le facteur manque.
- ACAL462 — Ombrage électrique : publier les deux bornes (linéaire / selon les chaînes) et la valeur retenue avec sa
  règle (aujourd'hui `etapes/mismatch_ombrage.py`, niveau chaîne seulement).
- ACAL463 — Étape « neige » : le créneau de saisie mensuelle existe sans étape de calcul (à prouver) — brancher.
- ACAL464 — Perte de faible éclairement par modèle à une diode ajusté sur la fiche du module (pvlib), omise et nommée
  si la fiche est incomplète.

## LOT W6b — M3fn « Fonctions de classe PVsyst : système, optimisation, validation » (ACAL465-477) → `### ACAL — M2` (sous-titre système)
- ACAL465 — Gain bifacial par facteurs de vue (pvlib `infinite_sheds`) pour les rangées (toit plat, sol) à la place du
  gain simplifié (`bifacial.py`).
- ACAL466 — Champ au sol sur terrain en pente : pente lue sur un modèle de terrain gratuit (Copernicus GLO-30) —
  vérifier `surfaces/sol.py` et la décision « IGN = pente de terrain » ; si une dépendance neuve est nécessaire, le
  dire (catégorie ARCH).
- ACAL467 — Ombrière en géométrie réelle (structure, hauteur libre, inclinaison, nombre de modules calculé) au lieu
  d'une capacité déclarée.
- ACAL468 — Balayage paramétrique serveur asynchrone (inclinaison, azimut, pas inter-rangées, ratio DC/AC) → grille +
  optimum, `@after` ACAL388.
- ACAL469 — Écran « Optimiser » : lancer un balayage, voir la carte des résultats, appliquer l'optimum en un geste.
- ACAL470 — Cible de remplissage « autoconsommation ≥ X % » ou « production ≥ X kWh/an » (aujourd'hui : kWc max et
  cible tirée de la facture — vérifier `optimizer.ts`).
- ACAL471 — Limitation d'injection (dont zéro injection) comme étape distincte de la chaîne de pertes, hors batterie
  (vérifier `plafond_injection` et `ORDRE_ETAPES`).
- ACAL472 — Cheminement automatique des câbles (plus court chemin le long des rangées et rives) proposé, corrigeable
  (aujourd'hui longueurs depuis des chemins dessinés : `troncons.py`).
- ACAL473 — Courbe de charge horaire importée (CSV) et bibliothèque de profils types — vérifier ce qui existe côté
  consommation avant d'écrire.
- ACAL474 — Banc de validation : le moteur comparé à PVGIS PVcalc et à pvlib `ModelChain` sur des sites marocains de
  référence (fixtures = vrais appels enregistrés), écart publié, test qui échoue au-delà de la tolérance choisie par
  la tâche d'après les écarts MESURÉS (jamais un seuil inventé).
- ACAL475 — « Note de validation » générée (méthode, sites, écarts) jointe au rapport d'étude.
- ACAL476 — Export DXF du toit et « publier-devis » : deux segments de route sans appelant trouvé (r1/a1 « B ») —
  prouver, puis brancher un bouton ou classer « sans écran par design ».
- ACAL477 — (libre)

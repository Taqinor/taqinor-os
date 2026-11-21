# B2 — Aurora Solar et OpenSolar : côté atelier de conception, confrontés à notre module Calepinage

Date de la lecture : 21/11/2026. Dépôt lu en lecture seule (worktree `calpinage-module-enhance-04bba5`, HEAD `5a75a182b`).
Méthode : uniquement des pages que les éditeurs servent normalement à un lecteur (pages produit, blogs, notes de version, communiqués, listes d'applications, avis écrits). Chaque ligne cite une page RÉELLEMENT lue dans cette session (identifiant de source `S..`, tableau en fin de fichier). Les centres d'aide `help.aurorasolar.com` et `support.opensolar.com` n'ont jamais été ouverts (voir « Bloqué »).

Légende verdict (colonne « Chez nous ») : PRÉSENT (`fichier::symbole`) · PARTIEL (cas manquant) · ABSENT · PLANIFIÉ (id de tâche trouvé dans `docs/plans` / `docs/PLAN2.md`) · HORS DÉCISION (données ou logiciel payant, suiveurs, argent calculé dans le module de conception, tout ce qui change le PDF client du devis).
Automatisme : 1clic = un clic ; assist = assistant / réglage puis calcul ; manuel = l'utilisateur fait chaque geste ; auto = sans action.
Type de source : produit = page produit/fonction ; blog ; notes = note de version ; presse ; avis = avis écrit (opinion) ; vidéo = titre/description de page vidéo publique.

---

## PARTIE 1 + 2 — Aurora Solar (atelier de conception)

| # | Zone | Ce que l'utilisateur peut faire, concrètement | Auto | Sortie | Source (type) | Chez nous |
|---|---|---|---|---|---|---|
| A01 | Démarrage | Partir d'une adresse + UNE facture mensuelle pour obtenir un modèle 3D et un design prêt pour la proposition (« Aurora AI », « sous 10 secondes », plus de 3 millions de lancements annoncés) | auto | modèle de toit 3D + design | S-A2 (produit) | PLANIFIÉ — ACAL421 (« Conception automatique » : contour OSM + optimiseur), ACAL485/488/489 (IA toit) ; aujourd'hui seule la page publique `apps/web/src/pages/devis/mon-toit.astro` fait adresse → recommandation |
| A02 | Démarrage | Choisir l'imagerie HD incluse (Google HD, Vexcel) | assist | fond d'imagerie | S-A9 (produit) | PRÉSENT — `apps/web/src/lib/roofConfig.ts` (fournisseurs maptiler/mapbox/ign_bd_ortho) + `apps/calepinage/services/site.py` |
| A03 | Démarrage | Imagerie Nearmap en option payante | assist | fond d'imagerie | S-A9 (produit) | HORS DÉCISION (imagerie payante) |
| A04 | Démarrage | Commander un modèle de toit « Expert Design Services » (équipe Aurora, livraison ~3 h, QA individuelle, données client anonymisées) | manuel | modèle de toit prêt à concevoir | S-A8 (produit), S-A9 (tarifs, ~3 h) | ABSENT (service humain ; équivalent interne = file de demandes, voir N12) |
| A05 | Imagerie | Téléverser des images/vidéos de drone → carte à l'échelle + surface LIDAR + maillage 3D, sans surcoût | assist | carte, surface LIDAR, maillage 3D | S-A5 (produit) | PARTIEL — fond d'image calé seul : ACAL424 (fichier « monde » .jgw/.pgw/.wld) planifiée ; photogrammétrie ABSENTE |
| A06 | Imagerie | « Drone true-up » : fusionner le modèle drone avec le design vendu pour détecter les écarts avant permis | assist | écarts design/réel | S-A1 (produit), S-A5 (produit) | ABSENT (le module « pose réelle » `frontend/src/features/calepinage/atelier/PoseReelle.jsx` compare plan et pose, pas un levé drone) |
| A07 | Démarrage | Outil de capture de leads à poser sur le site de l'installateur (« Embedded Leads » / Lead Capture AI) | auto | lead + estimation | S-PV (presse) ; légende d'image S-A10 (produit) | PRÉSENT — `apps/web/src/pages/devis/mon-toit.astro` (+ `apps/calepinage/services/reprise_public.py`, contrat `lead_layout_public.json`) |
| A08 | Toit | « Aurora AI » détecte la structure du toit avant de poser les panneaux (réservé Enterprise) ; détection d'obstacles assistée par IA (même offre) | auto | pans + obstacles | S-A1 (produit), S-A9 (tarifs) | PLANIFIÉ pour contour et pans — ACAL485/488/489 ; obstacles par IA ABSENTS (non couverts) |
| A09 | Toit | Modèle 3D du bâtiment depuis LIDAR, imagerie ou drone, à distance | assist | hauteurs, pentes, arbres | S-A1 (produit), S-A6 (blog LIDAR) | PARTIEL — `apps/calepinage/services/lidar_ign.py` (France seule, suggestion jamais appliquée sans validation) ; Maroc : tout se relève |
| A10 | Toit | Arbres dans le modèle 3D (hauteurs LIDAR) qui ombrent le toit | auto | ombres d'arbres | S-A1, S-A9 (produit) | PARTIEL — arbres saisis à la main (hauteur, diamètre) : `apps/web/src/scripts/roofPro11/environment.ts` ; détection auto ABSENTE |
| A11 | Toit | Retraits (setbacks) depuis les rives et obstacles, appliqués automatiquement à tout nouveau design | assist | surface posable | S-B-FIRE (blog) | PRÉSENT — `apps/web/src/lib/roofSetbackEdge.ts`, `backend/django_core/apps/calepinage/services/degagements.py` |
| A12 | Toit | « Auto Place Fire Pathways » : un bouton pose le minimum de passages réglementaires pour l'autorité et l'année de code, avec ou sans sprinklers ; panneaux gênants en jaune ; passages hors périmètre autorisés | 1clic | passages pompiers dans le design et le DXF | S-B-FIRE (blog), S-A3 (produit), S-DOCS (docs API) | PARTIEL — zones d'exclusion à gabarit + allées saisies par la société (`PanneauAllees.jsx`, `degagements.py`) ; pas de règle réglementaire marocaine à appliquer automatiquement |
| A13 | Toit | Dessiner soi-même les passages ; panneaux qui chevauchent → jaune, chevauchement entre panneaux/obstacles → rouge | manuel | design validé | S-B-FIRE (blog) | PRÉSENT — `apps/web/src/scripts/roofPro11/obstaclesUi.ts` (zones d'exclusion), `layoutEditor.ts::checkPanelAt` (refus tout-ou-rien) |
| A14 | Toit | Base de 25 000+ autorités (AHJ) avec règles locales de code | auto | règles de code par site | S-A9 (produit) | ABSENT, sans objet (données américaines) ; équivalent marocain = gabarits de dossiers (`apps/calepinage/services/gabarits.py`) |
| A15 | Ombrage | Horizon lointain automatique (profil à 360° de plus d'un million de points d'altitude) ; perte d'horizon dans le diagramme de pertes | auto | profil d'horizon, ligne de pertes | S-B-HOR (blog) | PRÉSENT — `apps/calepinage/services/horizon.py::ClientHorizon` (PVGIS), `ET/horizon.py` |
| A16 | Ombrage | Analyse d'ombrage par LIDAR : trajet de l'ombre des arbres et voisins, carte d'irradiance ; écart annoncé à ±3 points de SunEye | auto | heat map d'irradiance | S-A1 (produit), S-A6 (blog) | PARTIEL — moteur d'ombrage dans le navigateur (`apps/web/src/lib/shadingEngine.ts`) alimenté par obstacles SAISIS ; pas de LIDAR hors France |
| A17 | Ombrage | Irradiance visible SUR chaque panneau (pas seulement sur le toit), y compris carports et sols ; ombrage inter-rangées en bord de panneau | auto | heat map par module | S-B-IRR (blog) | PRÉSENT — `shadingEngine.ts::cellsSolarAccess` + `shadingUi.ts::refreshHeatmap` ; ombrage inter-rangées horaire `core/calepinage/ombre_rangees.py::fraction_ombree` |
| A18 | Ombrage | Comparer l'irradiance reçue à différentes inclinaisons/orientations, panneaux non affleurants | assist | comparaison | S-B-IRR (blog) | PRÉSENT — `apps/web/src/lib/estimatorBrainV6.ts::fineGridMatrixV6` + `roofPro11/matrix.ts` (matrice triable) |
| A19 | Ombrage | Rapports d'ombrage « bancables » (offre Premium) pour incitations | 1clic | rapport d'ombrage | S-A9 (produit) | HORS DÉCISION (« pas de bancable », `docs/moteur-calepinage.md` §7) — le rapport d'ombrage non bancable existe : `apps/calepinage/services/rapport_ombrage.py` |
| A20 | Ombrage | Simulation de la course du soleil un jour donné, énergie par heure | assist | courbes/animation | S-R-MUST (produit), S-A3 | PRÉSENT — `roofPro11/soleilPlay.ts::createSoleilPlayer`, onglet `course-soleil` |
| A21 | Production | Simulation de production avec dégradation, salissure, neige, composants choisis | auto | production annuelle/mensuelle | S-A3 (produit) | PRÉSENT — `apps/calepinage/services/chaine_pertes.py::ORDRE_ETAPES` ; neige : PLANIFIÉ ACAL463 |
| A22 | Production | Diagramme du système de pertes | auto | diagramme | S-B-HOR (blog, légende) | PRÉSENT — `services/diagramme_pertes.py`, `production/DiagrammePertes.jsx` |
| A23 | Production | Production en P50 seulement (« ne sort pas de P90 en natif ») | — | — | S-SURGE-A (avis, concurrent) | nous dépassons : P50/P75/P90/P95 — `services/incertitude.py::bloc_incertitude` ; P99 refusé (D-ACAL-34) |
| A24 | Production | Résultats qui se rafraîchissent en direct quand le système change (stockage, prix) | auto | simulation vivante | S-A4 (produit) | PLANIFIÉ — ACAL398 (relance auto après enregistrement), ACAL401 (barre de résumé vivante) |
| A25 | Conso | Courbe de consommation prédite depuis UNE facture, lacunes comblées | assist | profil de charge | S-R-MUST (produit) | PRÉSENT — `services/consommation.py`, `services/courbe_charge.py`, modèle `ProfilTypeConsommation` |
| A26 | Conso | Auto-consommation et économies avec batterie (tarifs de pointe) | assist | % couverture, kWh | S-R-MUST (produit) | PRÉSENT pour les kWh — `services/autoconsommation.py`, `services/batterie.py::simuler_batterie` (6 stratégies) ; les économies en argent restent dans `ventes` (HORS DÉCISION côté montants) |
| A27 | Stockage | Placer batteries, modules d'extension et onduleurs de stockage dans le design à côté des panneaux ; empilements multiples ; rénovation avec batterie | manuel | batterie dans le plan | S-A4 (produit) | PARTIEL — dimensionnement et dispatch (`batterie.py`, champs `ond_bat_*`) + marqueurs d'équipement 3D (`roofPro11/electrique3d.ts`) ; pas d'objet batterie posé au mur dans l'atelier |
| A28 | Stockage | Indicateurs « autosuffisance 83 % / économies 67 % / heures de secours par charge » mis à jour quand la batterie change | auto | panneau d'indicateurs | S-A4 (produit, légende d'image) | PARTIEL — couverture et stratégie `backup` présentes ; « heures de secours par charge » ABSENT |
| A29 | Stockage | Onduleur hybride compté une seule fois dans la nomenclature ; unités d'extension comme composants distincts | auto | nomenclature | S-A4 (produit, légendes) | PARTIEL — nomenclature `core/electrique/nomenclature.py` (comptage unique de l'hybride non vérifié) |
| A30 | Électrification | Ajouter VE, pompe à chaleur, pack efficacité à la même proposition | manuel | scénario d'électrification | S-A3 (produit), S-PV (presse) | PARTIEL — charges VE/PAC dans la simulation (`services/charges.py::courbe_vehicule/courbe_pac`) ; la proposition client = HORS DÉCISION |
| A31 | Panneaux | AutoDesigner : pose automatique des panneaux, révisable | 1clic | disposition | S-A3 (produit), S-A9 (produit) | PRÉSENT — `roofPro11/optimizer.ts::liveResolveFlat/liveResolvePitched`, `layoutVariability.ts::fillAll`, serveur `core/calepinage/optimum.py` |
| A32 | Panneaux | Pose manuelle + flux hybride (partir d'un auto-layout puis corriger) ; réglages par défaut d'équipe | manuel/assist | disposition | S-A3 (produit) | PRÉSENT — `layoutEditor.ts` ; défauts : `services/presets.py`, `services/modeles.py` |
| A33 | Panneaux | Sols, carports et ombrières dans le même outil | assist | pans de pose | S-A9 (produit), S-B-IRR (blog) | PARTIEL — `roofPro11/poseSurfaces.ts` (sol/ombrière/façade), `core/calepinage/surfaces/sol.py::SurfaceSol` : terrain plat seulement, ombrière = capacité déclarée |
| A34 | Panneaux | Placement dynamique en réunion avec le client (Sales Mode, « live design ») | manuel | design modifié en direct | S-A9 (produit), S-A4' (produit) | ABSENT (l'atelier est interne) ; le client voit une visionneuse lecture seule `roofPro11/viewerFullBoot.ts` |
| A35 | Électrique | AutoStringer : choisit onduleurs et optimiseurs par programmation linéaire en nombres entiers (coût, panneaux non câblés), construit les chaînes (parcours du voyageur de commerce + « serpent »), moins de 2 s en moyenne | 1clic | liste onduleurs/chaînes dessinée | S-B-STR (blog) | PARTIEL — câblage auto des chaînes par pan : `services/chaines.py::concevoir_par_pan` ; le CHOIX auto du nombre/type d'onduleurs ABSENT |
| A36 | Électrique | Vérifie que panneau, optimiseur et onduleur sont compatibles (tensions, courants, entrées), signale l'incompatible | auto | alertes | S-B-STR (blog) | PRÉSENT — `core/electrique/chaines.py` (Voc à froid, fenêtre Vmpp, Imax), `services/electrique.py` |
| A37 | Électrique | Regrouper les panneaux d'une chaîne par même azimut | auto | chaînes homogènes | S-B-STR (blog) | PRÉSENT — `services/polystring.py` (une orientation par chaîne) |
| A38 | Électrique | Optimiseurs et micro-onduleurs multi-entrées (MI-MLPE) via AutoDesigner/AutoStringer | assist | design | S-B-MLPE (blog) | PARTIEL — optimiseurs `opt_*`, micro-onduleurs `services/micro_onduleurs.py` ; multi-entrées non vérifié |
| A39 | Électrique | Racking compatible avec nomenclature qui part vers la commande fournisseur | auto | BOM + commande | S-A3 (produit) | PARTIEL — nomenclature fixation `services/fixation.py` ; commande fournisseur HORS DÉCISION |
| A40 | Électrique | Rapports de validation NEC | 1clic | rapport | S-SURGE-A (avis) | PRÉSENT sous la norme du site — `services/norme.py` (NF C 15-100/IEC), `services/electrique.py` (verdict) |
| A41 | Documents | « Instant Plan Sets » : plans de permis générés depuis le design (États-Unis) | auto | jeu de plans | S-A3 (produit), S-A9 | PRÉSENT sous forme marocaine — `services/documents/`, `views/sorties.py` (`plan-pose`, `plan-toiture`, `plan-masse`, `note-calcul`), `services/pack_technique.py` |
| A42 | Documents | Plan Sets Service (24-48 h, cachet d'ingénieur, 95 % d'approbation annoncée) | manuel | plans estampillés | S-A-PLAN (produit) | HORS DÉCISION (service humain tiers) |
| A43 | Exports | Export DXF contenant les passages pompiers, pour plans CAD | 1clic | DXF | S-B-FIRE (blog) | PRÉSENT — `services/export_dxf.py` |
| A44 | Documents | Proposition web interactive + PDF, modèles de marque, suivi d'ouverture, signature | assist | lien + PDF | S-A9 (produit), S-A4' (produit) | HORS DÉCISION (le seul chemin de PDF client = `/proposal`, règle 4) |
| A45 | Documents | Un seul design pour vente, permis et installation | auto | design unique | S-A3 (produit) | PRÉSENT — D-ACAL-1 (calepinage = unique conception du devis) |
| A46 | Mobile | Sales Mode adapté tablette, interactions « glisser » | assist | vue tablette | S-A9 (produit) | PLANIFIÉ — ACAL423 (atelier téléphone 390 px), ACAL482 (parcours téléphone) ; tactile déjà géré `frontend/e2e/calepinage_tactile.spec.js` |
| A47 | Collab | Règles de conception sur mesure, base de composants | manuel | défauts d'équipe | S-A9 (produit) | PRÉSENT — `apps/stock/models_fiche_technique.py::FicheTechnique`, `services/presets.py` |
| A48 | Collab | Modèles de proposition, règles de prix, frais additionnels, remises | manuel | tarification | S-A9, S-A4' (produit) | HORS DÉCISION (argent) |
| A49 | Collab | Équipes, rôles à droits fins, gestion des partenaires/revendeurs, visibilité par équipe | manuel | droits | S-A9 (produit), S-A11 (produit) | PARTIEL — `apps/roles` + droit `calepinage_approuver` ; partenaires/revendeurs ABSENTS |
| A50 | Collab | API de synchro, API de conception (déclenche une simulation), webhooks, SSO | auto | JSON | S-A12 (produit), S-DOCS | PARTIEL — événement `calepinage.simule` vers `apps/publicapi` (`services/simulation.py`) ; pas d'API de conception publique |
| A51 | IA | Pipeline « modèle de toit → AutoDesigner → passages → AutoStringer » sans clic, relecture conseillée, aussi par API | auto | design complet | S-A1 (produit) | PLANIFIÉ en partie — ACAL421 ; absent aujourd'hui dans l'atelier |
| A52 | IA | Modèle drone « Expert Model » posé sur les données drone | manuel | modèle | S-A5 (produit) | ABSENT |
| A53 | Vidéos | Titres publics : « Aurora AutoDesigner », « SmartRoof Tutorial: How to Design a 3D Rooftop for Solar in Minutes », « Storage Modeling in Aurora », « Aurora AI in Action: Pro Tips from a Top User » (descriptions non servies) | — | — | S-YT (vidéo, titres seuls) | sans objet |
| A54 | HelioScope | Poser des champs (toit, carport, sol) + stockage dans UN projet, mise en page auto, rangées posées avant de modéliser le bâtiment, profils réutilisables, simulation sous la minute | assist | projet C&I | S-HS (produit) | PARTIEL — surfaces sol/ombrière ; profils : `ParametresCalepinage` ; pas de mode « champ sans bâtiment » nommé |
| A55 | HelioScope | Choix du modèle de transposition (Perez/Hay), salissure par mois, mismatch, rétro-tracking | manuel | hypothèses | S-B-HSPV (blog, vendeur) | PLANIFIÉ — ACAL455 (transposition pvlib) ; suiveurs HORS DÉCISION |

Lignes Aurora : 55 (53 de capacité ; A23 et A53 sont des lignes de contexte).

---

## PARTIE 1 + 2 — OpenSolar (atelier « Design Studio »)

| # | Zone | Ce que l'utilisateur peut faire, concrètement | Auto | Sortie | Source (type) | Chez nous |
|---|---|---|---|---|---|---|
| O01 | Démarrage | Imagerie HD mondiale en 3D, 2D ou site personnalisé | assist | fond d'imagerie | S-O3 (produit) | PRÉSENT (2D) — `roofConfig.ts` ; 3D photogrammétrique : HORS DÉCISION (Google Solar, absent au Maroc) |
| O02 | Démarrage | Démarrer un projet depuis des coordonnées (latitude, longitude) collées, formats virgule ou espace reconnus | assist | projet centré | S-RN38 (notes) | ABSENT — `roofPro11/mapDraw.ts::geocode` n'envoie que du texte d'adresse au géocodeur ; non planifié |
| O03 | Imagerie | Place de marché d'imagerie payante (MetroMap, Nearmap, 3D Plus), portefeuille pré-payé, achat par projet | assist | imagerie premium | S-O6 (produit) | HORS DÉCISION |
| O04 | Toit | Croquis du toit sur image 2D quand il n'y a pas de 3D | manuel | plan de toit | S-O3 (produit) | PRÉSENT — `roofPro11/mapDraw.ts::addVertex`, `redrawTrace` |
| O05 | Toit | Mode « plans de toit et obstructions » manuel avec outil de mesure intégré | manuel | pans + obstacles | S-O3 (produit) | PRÉSENT — `roofPro11/zones.ts`, `obstaclesUi.ts`, `mesureUi.ts` |
| O06 | Toit | Modèle de surface numérique (DSM) par photogrammétrie : pente, azimut, ombrage sans saisie | auto | toit 3D | S-O3, S-O4 (produit) | HORS DÉCISION (DSM d'imagerie 3D payante/Google) |
| O07 | Toit | Les lignes du toit s'aimantent à 90°/180°, aimantation des nœuds, guides en GIF pour poser les nœuds | assist | contour propre | S-RN30 (notes) | PRÉSENT — `roofPro11/snap.ts::contraindreAngle`, `aimanterAuxZones` |
| O08 | Toit | Mettre à l'échelle une image personnalisée téléversée avec l'outil de mesure | manuel | fond calé | S-RN30 (notes) | PRÉSENT — `roofPro11/underlay.ts`, `calageFondUi.ts`, `PlanImporteCalage.jsx` |
| O09 | Toit | Bibliothèque d'objets de toit : évents, cheminée, antenne, lanterneaux, citerne, climatiseur, chauffe-eau, échelle, passerelle, garde-corps ; l'ombre portée s'ajoute seule | manuel | obstacles 3D + ombre | S-RN310 (notes), S-O-ELEV (produit) | PARTIEL — 6 types seulement : `apps/web/src/lib/obstacles.ts::ObstacleType` (cheminee, ventilation, chien_assis, edicule, antenne, autre) ; pas de lanterneau, citerne, climatiseur, passerelle, garde-corps |
| O10 | Toit | Annotations de dessin et de proposition (détails de toit, notes pour le client) | manuel | repères sur le plan | S-RN38 (notes) | ABSENT (seule la cote `mesureUi.ts`) ; non planifié |
| O11 | Toit | Point d'ancrage anti-chute avec rayon de travail sûr, « cartes de site – zones de sécurité » dans le dossier de pose ; carte de remise sans les zones de sécurité | manuel | plan de chantier | S-RN310, S-RN312 (notes) | ABSENT ; non planifié |
| O12 | Panneaux | « Auto Design » par l'assistant Ada : plusieurs systèmes en secondes, « Max Offset » (couvrir la conso) et « Max Fit » (remplir) à partir de préférences et de modèles | 1clic | 2 propositions de système | S-O-AUTO, S-OS30 (produit, notes) | PARTIEL — « Remplir » = Max Fit (`fillAll`) ; cible conso : `estimatorBrainV7/V8` et PLANIFIÉ ACAL470 (cible kWh), ACAL421 ; la présentation à deux cartes n'existe nulle part |
| O13 | Panneaux | Enregistrer un projet comme modèle de design automatique ; frais additionnels dans le modèle | assist | modèle réutilisable | S-RN33 (notes) | PRÉSENT — `services/modeles.py` (D-ACAL-15), `services/kits.py` |
| O14 | Panneaux | Plusieurs modèles de panneaux dans un système, un par groupe | manuel | design multi-module | S-O3 (produit), S-RN30 | PRÉSENT — `roofPro11/moduleSelect.ts` (module par pan) |
| O15 | Panneaux | Écartement préréglé entre modules | manuel | jeu entre panneaux | S-RN30 (notes) | PRÉSENT — `rp9-free-gap` (`layoutEditor.ts`) |
| O16 | Panneaux | Réglages par groupe : fixation (affleurant…), azimut, pente ; accès solaire annuel du groupe | manuel | inspecteur de groupe | S-O3 (produit, légende) | PRÉSENT — inspecteur de pan + production par pan |
| O17 | Panneaux | Double inclinaison (Est-Ouest) | manuel | rangées | S-O-MOUNT (produit) | PRÉSENT — `data-family="eastwest"`, `core/calepinage/ombre_rangees.py::fraction_ombree_est_ouest` |
| O18 | Panneaux | Structures surélevées sur dalle béton plate (RCC) : pieds, pannes, chevrons créés seuls ; hauteur et inclinaison réglables, hauteur arrière recalculée ; règles de portée (1,8 m max, porte-à-faux 20-30 %, plus dense en zone côtière) ; panneau rouge si conflit avec obstacle ; lest optionnel | assist | structure 3D, visuel de proposition (pas de plan d'exécution) | S-O-ELEV (produit), S-RN38 (notes) | PARTIEL — châssis de toit plat dessinés en 3D (`scene3d.ts`), nomenclature `services/fixation.py`, lest `services/lestage.py` ; pas de pieds/pannes ni de règle de portée ; non planifié |
| O19 | Panneaux | Mounting Designer : quantité de rails, ancres, vis, colliers au collier près ; compatibilité kit/toit/pente ; évaluation structurelle et vent ; BOM en CSV ; fournisseurs intégrés par pays | assist | BOM de fixation | S-O-MOUNT (produit), S-RN313 (notes) | PARTIEL — `services/fixation.py`, `services/catalogue_fixation.py`, route `bom-fixation` ; vent/neige = HORS (non-objectif documenté `docs/moteur-calepinage.md` §7) |
| O20 | Panneaux | Calcul de portée de rail avec les données neige/vent du projet (Fast-Rack, Canada) ; portée d'ancre pour un seul type d'ancre | auto | liste de pièces | S-RN310, S-RN313 (notes) | PARTIEL — paramètres saisis par la société (`lestage`) ; pas de calcul de portée (D-CALX 7 : aucun chiffre inventé) |
| O21 | Électrique | Auto-câblage des chaînes (de 20 s à 3-5 s) ; bascule d'auto-câblage avant d'ajouter l'onduleur ; avertissement de taille au lieu d'un échec (onduleur 12 kW sur 4 kW de panneaux) | 1clic | chaînes | S-RN30, S-RN312 (notes) | PRÉSENT — `services/chaines.py::concevoir_par_pan` ; alerte DC/AC `core/electrique/onduleurs.py::ratios` |
| O22 | Électrique | Mode câblage amélioré : onduleurs câblés seuls, configuration manuelle, annulation facile | assist | chaînes | S-RN313 (notes) | PARTIEL — `plan/AffectationChaines.jsx` (glisser-déposer) ; annulation dédiée absente |
| O23 | Électrique | Schéma unifilaire automatique depuis le design et le câblage, gabarits AU/US/UK/DE/IT/ES, équipements préremplis, resynchro avec le design, éditeur de formes/étiquettes/liaisons, export, intégration au modèle de proposition | 1clic | SLD éditable | S-O-SLD (produit) | PRÉSENT — `services/sld.py::edition_sld`, `sld_export.py` (SVG + DXF), `views/schema.py` ; norme du site `services/norme.py` |
| O24 | Électrique | SLD indien depuis modèle (étiquettes DCDB/ACDB, compteurs, mises à la terre, parafoudres), export PDF et DXF | manuel | SLD | S-RN312 (notes) | PRÉSENT — `services/terre.py`, `services/coffrets.py`, `sld_export.py` |
| O25 | Électrique | Câble DC choisi et ajouté chez le fournisseur préféré par repli d'automatisation | auto | ligne de câble | S-RN313 (notes) | PRÉSENT — `services/cables.py` (section et chute) |
| O26 | Ombrage | Pas de saisie : pente, azimut et ombrage calculés ; traçage solaire dynamique jour/mois/année | auto | valeurs d'ombrage | S-O3, S-O4 (produit) | PRÉSENT — `shadingEngine.ts::hourlyShadeFactors`, matrice 12×24 `ET/ombrage_proche.py` |
| O27 | Ombrage | Ombrage au niveau sous-chaîne (sous-panneau) pour choisir l'équipement | auto | indications | S-O3 (produit) | PARTIEL — `ET/mismatch_ombrage.py` (au niveau chaîne) ; étape `diodes` omise « non modélisé en v1 » |
| O28 | Ombrage | Cartes de chaleur, rapports d'ombrage, accès solaire annuel par groupe, simulation sans saisie | 1clic | heat map + rapport | S-O3 (produit) | PRÉSENT — `rp9-heatmap-toggle`, `services/rapport_ombrage.py` (`rapport-ombrage.pdf`) |
| O29 | Production | Moteur de calcul basé sur le System Advisor Model | auto | production | S-O3 (produit) | PRÉSENT sous un autre moteur — `services/chaine_pertes.py` + PVGIS (`pvgis_serie.py`) ; pvlib prévu (ACAL454-456, 465) |
| O30 | Production | Recalcul d'ombrage depuis « Outils avancés » ; calculs SAM en parallèle | assist | résultat à jour | S-OS30 (notes) | PARTIEL — « Recalculer » dans l'onglet Production ; relance auto : ACAL398 planifiée |
| O31 | Stockage | Profil de consommation généré depuis l'adresse, graphique annuel modifiable (onglet Énergie) | auto | profil | S-OS30 (notes) | PRÉSENT — `models.py::ProfilTypeConsommation`, `services/consommation.py` |
| O32 | Stockage | Pétrole/diesel → VE : saisie de la consommation, économies calculées ; gaz → pompe à chaleur avec profil 8760 h | assist | scénario | S-OS30 (notes) | PARTIEL — charges VE/PAC `services/charges.py` ; économies en argent HORS DÉCISION |
| O33 | Stockage | Rénovation avec batterie sur un système existant ou importé | assist | modèle | S-OS30 (notes) | PARTIEL — `services/batterie.py` simule une batterie sur le PV du design ; pas de système « existant » importé |
| O34 | Stockage | Indicateur « cycles moyens par jour » dans le panneau batterie ; logique Powerwall 3 | auto | métrique | S-RN33 (notes) | PARTIEL — cycles annuels calculés (`batterie.py`), affichage dans l'onglet Batterie non prouvé |
| O35 | Comparaison | Jusqu'à six designs par projet ; options de système et de paiement côte à côte (Swipe/Scroll/Bespoke) | assist | comparaison | S-O-SMP (produit) | PRÉSENT pour les designs — `models.py::CalepinageVariante`, `services/variantes.py`, `VariantesCompare.jsx`, `comparaison_projets.py` (1 à 5 projets) ; paiements = HORS DÉCISION |
| O36 | Documents | Proposition interactive : 3D que le client fait tourner sans compte, soleil et ombre sur l'année, comparaison de systèmes, lien unique avec suivi des sections lues | assist | lien web | S-O-SMP (produit), S-RN312 (notes) | HORS DÉCISION pour la proposition ; visionneuse 3D lecture seule PRÉSENTE (`viewerFullBoot.ts`) et soleil animé PLANIFIÉ (ACAL487, GATED autre propriétaire) |
| O37 | Documents | Partage en un clic par WhatsApp, message commercial personnalisé relu avant envoi | 1clic | message WhatsApp | S-O-SMP (produit) | PARTIEL — page `/proposition/[token]` a déjà boutons rappel/WhatsApp (`apps/web/src/pages/api/proposition-contact.ts`) ; envoi WhatsApp reste manuel (règle fondateur) |
| O38 | Documents | BOM automatique depuis le design, mise à jour quand on ajoute/retire un composant, avertissement « BOM différent du design », « Sync from Design » | auto | nomenclature | S-O-BOM (produit), S-RN312 (notes) | PRÉSENT — `export_tableur.py`, `core/electrique/nomenclature.py`, `services/devis.py` (`sync-devis`) |
| O39 | Documents | BOM → boutique (prix et stock en direct, commande) | 1clic | commande | S-O-BOM (produit), S-RN311 (notes) | HORS DÉCISION pour prix/commande ; la disponibilité en stock seule est ABSENTE |
| O40 | Documents | Permis : demande à des partenaires (jeu de plans, cachets, interconnexion), États-Unis | manuel | demande | S-O-PERM (produit) | HORS DÉCISION |
| O41 | Documents | Étiquettes/QR dans les documents de projet | auto | QR | S-RN311 (notes) | PARTIEL — `services/etiquettes.py` |
| O42 | Mobile | Concevoir, vendre et gérer depuis téléphone ou tablette, au bureau ou sur le terrain ; gérer un projet, envoyer des factures, partager (iOS, Android) | manuel | projet à jour | S-O-MOB (produit), S-RN312 (notes) | PLANIFIÉ — ACAL423, ACAL482 ; module visites existant `apps/visites` |
| O43 | Mobile | Design opportuniste sur le terrain puis affectation à un collègue | manuel | design affecté | S-O-MOB (produit) | PARTIEL — responsable du lead côté CRM ; pas d'affectation d'un calepinage |
| O44 | Collab | Rôles personnalisés (voir/créer/modifier/supprimer par champ), équipes internes et externes, file de demandes de design (concepteurs ↔ commerciaux), étiquetage de partenaires, partage multi-organisations | manuel | droits + file | S-O-ROLES (produit) | PARTIEL — `apps/roles` ; file de demandes de conception ABSENTE ; non planifiée |
| O45 | Collab | Bibliothèque de modèles de proposition, bascule sans changer les données | manuel | modèles | S-O-SMP (produit) | HORS DÉCISION (proposition) |
| O46 | IA | Assistant Ada par chat : créer projet, modèle, design depuis la conversation ; retour sur un design (pouce) | assist | design | S-RN33, S-OS30 (notes) | PARTIEL — assistant copilote `features/ia/cartes/modules/CartesCalepinage.jsx` (drapeaux `ASSISTANT_*` éteints par défaut) |
| O47 | IA | Commande vocale : créer un projet, lancer un auto-design | assist | projet | S-RN30 (notes) | ABSENT dans l'atelier ; agent d'actions séparé (`apps/agent`) |
| O48 | IA | Widget « AI Lead Gen » à intégrer au site : le client donne adresse, conso, type de toit, voit solaire, coûts, économies ; routage vers le CRM | auto | lead | S-RN30 (notes) | PRÉSENT — `apps/web/src/pages/devis/mon-toit.astro`, `reprise_public.py` |
| O49 | Exports | BOM CSV, SLD PDF/DXF, documents de projet | 1clic | fichiers | S-O-MOUNT, S-RN312 (notes) | PRÉSENT — `export_csv.py`, `export_tableur.py`, `sld_export.py`, `export_dxf.py` |
| O50 | Exports | Accès API et connecteurs payants (CRM, comptabilité, incitations) | auto | JSON | S-O1 (produit) | PARTIEL — `apps/publicapi` ; connecteurs tiers HORS DÉCISION |
| O51 | Avis | Dimensionnement : le centre d'aide recommande des designs 3D sous 500 kW, au-delà lenteurs, délais et erreurs d'enregistrement ; Auto Design « en bêta » (avis d'un concurrent, à lire comme opinion) | — | — | S-SURGE-O (avis) | notre plafond : `plafonner_selection` et test de performance CAL106 (2 000 modules, coût pur) |
| O52 | Vidéos | Titres publics : « OpenSolar 3D Design Tutorial », « Begineer's guide to a solar design with Open Solar » (descriptions non servies) | — | — | S-YT (vidéo, titres seuls) | sans objet |

Lignes OpenSolar : 52 (50 de capacité ; O51 et O52 sont des lignes de contexte).

---

## Lignes bonus (autres outils lus pour la Partie 3, classées de la même façon)

| # | Outil | Fonction | Source (type) | Chez nous |
|---|---|---|---|---|
| X01 | Reonic | « Optimize Layout » d'un clic puis ajustement ; groupes de panneaux avec jeu, orientation, inclinaison | S-RE-PLAN (produit) | PRÉSENT — `fillAll`, `layoutEditor.ts` |
| X02 | Reonic | Note par panneau de 0 à 10 sur une carte de chaleur (rouge < 4 … vert ≥ 6) ; perte d'ombrage annuelle/mensuelle | S-RE-PLAN, S-RE-DOC (produit/docs) | PARTIEL — accès solaire % par module ; légende de couleurs PLANIFIÉE ACAL441 |
| X03 | Reonic | Simulation d'ombre en direct sur une journée type, mise en pause ; comparer saisons | S-RE-SHADE (produit) | PRÉSENT — `soleilPlay.ts` ; côté client : ACAL487 |
| X04 | Reonic | Génération automatique de chaînes (même orientation, longueur maxi) + avertissement de courant dépassé + optimiseurs par panneau | S-RE-DOCS2 (docs) | PRÉSENT — `chaines.py`, `polystring.py`, `mismatch_ombrage.py` |
| X05 | Reonic | « AI Circuit Plan » : décrire en mots les modifs du schéma de câblage | S-RE-PLAN (produit) | ABSENT ; non planifié |
| X06 | Reonic | Jusqu'à cinq vues 3D personnalisées dans le PDF client ; instantanés | S-RE-PLAN (produit) | PARTIEL — vues planifiées ACAL435 ; l'ajout au PDF client = HORS DÉCISION |
| X07 | Reonic | Toit depuis plan d'architecte mis à l'échelle par un trait de référence | S-RE-PLAN (produit) | PRÉSENT — `underlay.ts` |
| X08 | Reonic | Toit : pente par arête (Smart Roof), lucarnes avec largeur/saillie/pentes, retrait par arête, calques de fond (orthophoto, Google 3D, OSM, drone, image perso) | S-RE-DOCS1 (docs) | PARTIEL — pente par PAN ; lucarne comme obstacle `batiment.ts::construireLucarnes` ; formes : ACAL410 |
| X09 | Reonic | Simulation au pas de 15 minutes sur 20 ans, tarifs dynamiques | S-RE-PLAN (produit) | PRÉSENT pour le pas horaire/25 ans — `vieillissement.py` ; tarifs = HORS DÉCISION |
| X10 | Pylon | Tampon de bord + retrait de gouttière ; imagerie à 7,5 cm | S-PY (produit) | PRÉSENT (retraits) ; imagerie HD HORS DÉCISION |
| X11 | Pylon | SLD automatique, manuel du propriétaire, rapport de chute de tension avec tracé de câble au glisser | S-PY (produit) | PRÉSENT — `sld.py`, `documents/manuel_proprietaire.py`, `troncons.py`, route `troncons` |
| X12 | Pylon | « Conseiller batterie » : recommandé / non recommandé selon jours d'autonomie | S-PY (produit) | PARTIEL — `services/hors_reseau.py::dimensionner_hors_reseau` ; pas de verdict en trois mots |
| X13 | Solargraf | Max-fit par face, concepteur intelligent selon cible de conso, curseur d'autoconsommation → stockage optimal, vue partagée | S-SG (produit) | PARTIEL/PLANIFIÉ — voir O12 ; vue partagée : ACAL402 (disposition « studio ») |
| X14 | Scanifly | App mobile gratuite de relevé avec listes de contrôle et photos annotées ; ombrage en temps réel sur site (« viewsheds ») | S-SC (produit) | PARTIEL — `ReleveTerrain`, `PhotoSite`, `apps/visites` ; ombrage mesuré sur site ABSENT |
| X15 | SolarEdge Designer | Détection de toit par IA d'un glissé ; détection auto d'obstacles semblables ; ombrage d'arbres par dimensions ; import/export DXF | S-SE (notes) | PLANIFIÉ (toit) ; obstacles AUTO ABSENT ; arbres PRÉSENT ; DXF PRÉSENT (`import_plan.py`, `export_dxf.py`) |
| X16 | SolarEdge Designer | Sélection multiple, copier-coller, alignement sur les arêtes ; dupliquer des blocs câblés pour agrandir | S-SE2 (presse) | PARTIEL — « Dupliquer » ; pas de « coller » ; guides : ACAL425 ; blocs câblés ABSENT |
| X17 | PV*SOL premium | Importer des modèles 3D, extruder des bâtiments, rayonnement perdu par module dans la vue 3D | S-PVSOL (produit) | PARTIEL — bâtiment extrudé `batiment.ts` ; import de modèle 3D ABSENT |
| X18 | PV*SOL | Schéma de circuit avec pertes de câble pour les autorités ; rapports en 22 langues | S-PVSOL (produit) | PRÉSENT/PARTIEL — `sld.py` ; langues FR/EN (CALX296) |
| X19 | PVsyst | Diagramme iso-ombrage (table de facteurs de masque), 3 modes d'ombrage (linéaire/chaînes/détaillé) | S-PVSYST (docs/PDF officiel) | PLANIFIÉ en partie — ACAL389, 449, 459, 467 ; mode « détaillé » ABSENT |
| X20 | HelioScope | Profils d'ombrage en bitmap géolocalisé ; mise en page auto | S-HS (produit) | PARTIEL — heat map par module |

---

## Décompte des verdicts (comptés par script sur la première mot de la dernière colonne ; lignes de contexte A23, A53, O51, O52 exclues)

| Verdict | Aurora (53 lignes) | OpenSolar (50) | Bonus autres outils (20) | Total (123) |
|---|---|---|---|---|
| PRÉSENT | 21 | 22 | 8 | 51 |
| PARTIEL | 16 | 17 | 8 (+1 mixte PARTIEL/PLANIFIÉ, X13) | 42 |
| ABSENT | 5 | 4 | 1 | 10 |
| PLANIFIÉ | 6 | 1 | 2 | 9 |
| HORS DÉCISION | 5 | 6 | 0 | 11 |

Plusieurs lignes PRÉSENT/PARTIEL portent un volet HORS DÉCISION dans le texte (proposition client, argent, imagerie payante) : le verdict affiché est celui de la partie conception.

---

## Nouvelles capacités PROPOSÉES (absentes ou partielles, non planifiées, permises), par ordre de rang

Rang = valeur pour un installateur marocain non ingénieur ÷ petit effort, sans donnée payante.

| Rang | En clair | Qui le fait et comment (URL) | Ce que nous avons (preuve) | Plus petite version crédible, sans donnée payante | Comment ça reste simple |
|---|---|---|---|---|---|
| 1 | « Le toit lu sur la photo du drone » : importer le relief (MNS) du drone pour lire pente, azimut et hauteurs | Aurora, drone → carte + surface LIDAR + maillage (https://aurorasolar.com/drone-mapping/) ; Reonic, 3D depuis photos de drone (https://reonic.com/en-gb/product/360h/planning/) | `services/lidar_ign.py` suggère pente/azimut pour la France ; l'inventaire dit « hors France aucune aide pour mesurer pente/hauteur » ; ACAL424 ne cale que l'image | Charger un GeoTIFF de hauteurs produit par l'outil de drone de l'installateur ; ajuster un plan sur chaque pan tracé ; PROPOSER pente et azimut (« à confirmer »), même patron que `lidar_ign.py` | Un seul bouton « Lire la pente sur le relief » dans l'onglet Pente ; le résultat remplit les champs existants, que l'utilisateur confirme |
| 2 | Deux propositions en un clic : « le plus de panneaux » et « couvrir ma facture » | OpenSolar Ada « Max Offset / Max Fit » (https://www.opensolar.com/?p=14292) ; Solargraf « Max-fit » et concepteur intelligent (https://www.solargraf.com/in/design-tool-in/) | `fillAll` (max), `neededPanelsForTarget` (cible facture) existent séparément ; ACAL421, 470 planifiées | Après « Conception automatique » (ACAL421), afficher deux cartes (nombre, kWc, production, couverture) ; choisir applique la disposition | Deux cartes, un seul geste, pas de réglage ; tout vient d'optimiseurs déjà présents |
| 3 | Plus d'objets de toit : lanterneau, citerne, climatiseur, chauffe-eau, passerelle, garde-corps | OpenSolar 3.10 (https://www.opensolar.com/product-updates/release-3-10/) | `ObstacleType` = 6 types ; dégagements saisis par la société par type (`degagements.py`) | Ajouter 5-6 types à `OBSTACLE_TYPES`, chacun avec son dégagement saisi (aucune valeur par défaut inventée) | Palette d'icônes dans la barre « obstacle » existante |
| 4 | Repères sur le plan : point d'ancrage, passage de câble, onduleur, tableau, note libre, avec rayon de sécurité | OpenSolar 3.8/3.10/3.12 (https://www.opensolar.com/product-updates/release-3-12/) ; Scanifly annotations de photos (https://www.scanifly.com) | seule l'outil de mesure (`roofPro11/mesureUi.ts`) ; plans PDF `plan-pose.pdf` déjà générés | Une couche « Repères » (type + texte + rayon optionnel) rangée dans le document, imprimée sur le plan de pose avec une légende | Un outil « Repère » à côté de « Mesure » ; rien à calculer |
| 5 | Démarrer en collant des coordonnées GPS | OpenSolar 3.8 (https://www.opensolar.com/product-updates/release-3-8/) | `mapDraw.ts::geocode` envoie la saisie telle quelle à `geocodeSearchUrl` (MapTiler, borné au pays) sans reconnaître « lat, lng » ; ce que le géocodeur ferait d'une paire de nombres n'a pas été testé ; les leads portent déjà un GPS | Reconnaître « lat, lng » (virgule ou espace) dans la barre d'adresse et recentrer | Aucune nouvelle zone ; même champ |
| 6 | Dalle béton plate : pieds et longrines qui se posent seuls | OpenSolar structures surélevées (https://www.opensolar.com/elevated-structures/) | châssis 3D `scene3d.ts`, `fixation.py`, `lestage.py` ; vent/neige non-objectif | Pieds espacés selon une PORTÉE MAXIMALE SAISIE par la société (source obligatoire), panneau rouge si conflit, lignes de pièces en nomenclature ; sans calcul de vent | Une case « Structure surélevée » sur le pan plat ; le visuel sort seul |
| 7 | Détecter aussi les obstacles et les arbres, pas seulement le toit | Aurora IA d'obstacles (https://aurorasolar.com/pricing/) ; SolarEdge (https://marketing.solaredge.com/solaredge-designer-0-20) ; Reonic Building AI (https://docs.reonic.com/docs/en/offers-plan-pv-plan-modules) | ACAL485 renvoie contour et pans seuls ; porte IA `vision_toit` (ACAL489) | Étendre la même demande à des obstacles typés et des arbres PROPOSÉS, confirmés un par un | Une liste cochable sous le contour proposé |
| 8 | « Combien d'heures tient la maison sur batterie » par charge, et verdict batterie en trois mots | Aurora panneau d'autosuffisance (https://aurorasolar.com/sell-battery-storage/) ; Pylon conseiller batterie (https://www.getpylon.com) | stratégie `backup` dans `batterie.py`, `hors_reseau.py` | Liste de charges critiques saisie + autonomie en heures ; verdict « adaptée / trop petite / trop grande » | Trois cartes de texte, aucune courbe |
| 9 | Poser des rangées sur un terrain, sans devoir dessiner un bâtiment d'abord | HelioScope « rangées avant le bâtiment » (https://helioscope.aurorasolar.com/design-solutions/) | `SurfaceSol` (terrain plat), `roofPro11/poseSurfaces.ts`, écrans `ModeTerrain.jsx` | Un mode « Champ » qui ouvre directement un pan de sol à partir d'un rectangle ou de la parcelle (`parcelle.ts`), sans bâtiment | Un seul choix au départ : « Toit » ou « Champ » |
| 10 | File de demandes « calepinage à faire » entre commercial et technicien | OpenSolar Design Request queue (https://www.opensolar.com/rolesandpermissions/) | `apps/roles`, tâches CRM, `calepinage_approuver` | Bouton sur la fiche lead qui crée une tâche assignée à un rôle avec lien vers le calepinage | Un bouton, une tâche, un lien |
| 11 | Nomenclature avec la disponibilité en stock (« en stock / à commander »), sans prix ni commande | OpenSolar Shop et BOM (https://www.opensolar.com/auto-bom/) | nomenclature `nomenclature.py`, `apps.stock.selectors` (lecture croisée via sélecteurs) | Colonne « stock » dans l'onglet Fixation/Matériel via sélecteur de stock ; lecture seule | Une colonne |
| 12 | Copier-coller de panneaux entre pans et guides d'alignement | SolarEdge Designer (https://www.pv-tech.org/solaredge-bolsters-design-tool-to-streamline-ci-rooftop-planning-process) | « Dupliquer » ; ACAL425 (guides) planifiée | seulement « coller » sur un autre pan avec refus nommé si ça ne rentre pas | Ctrl+V habituel |
| 13 | Toit complexe : pente par arête et lucarnes réglées (largeur, saillie, pentes) | Reonic Smart Roof et lucarnes (https://docs.reonic.com/docs/en/offers-plan-pv-plan-building) | pente par PAN ; lucarne = obstacle (`batiment.ts::construireLucarnes`, `percerPanLucarnes`) ; ACAL410 ne traite que les formes | Champ « pente » par arête dans l'inspecteur d'un pan et fiche de lucarne à 4 champs | Les champs n'apparaissent que si on choisit « Lucarne » ou « Modifier une arête » |
| 14 | Choix automatique du nombre d'onduleurs : le plus petit nombre qui câble tous les panneaux | Aurora AutoStringer (https://aurorasolar.com/?p=13829) | câblage auto, ratios DC/AC ; choix manuel | proposer le plus petit nombre d'onduleurs de la fiche société dont les entrées câblent tout (sans coût en MAD) | Une suggestion à accepter |
| 15 | Import de modèle 3D du bâtiment (glTF/OBJ) pour grands sites | PV*SOL (https://valentin-software.com/en/products/pvsol-premium) | bâtiment extrudé | lecture d'un glTF simple comme volume ombrant | Hors parcours standard : « Importer un volume » en mode expert |
| 16 | Dupliquer un bloc câblé pour agrandir l'installation | SolarEdge Designer (même article) | affectation de chaînes | copier un groupe et ses chaînes | Un bouton « Dupliquer le bloc » |
| 17 | Pouce haut/bas sur le remplissage auto avec motif | OpenSolar 3.3 (https://www.opensolar.com/product-updates/release-3-3-0/) | `services/journal.py` | une ligne de journal avec motif libre | Deux boutons |
| 18 | Verdict de pose « ombrage mesuré sur place » avec le téléphone | Scanifly (https://www.scanifly.com) | releve terrain, photos calées | photo ciel + boussole → horizon saisi | Un geste sur le chantier |
| 19 | Commande vocale « calepinage depuis la fiche lead » | OpenSolar Ada voix (https://www.opensolar.com/product-updates/release-3-0/) | assistant copilote (éteint par défaut) | via l'agent d'actions existant, jamais pour confirmer | hors atelier |
| 20 | Fiche des différences « design vs relevé drone » avant commande de matériel | Aurora drone true-up (https://aurorasolar.com/design-mode/) | `PoseReelle.jsx`, `asbuilt.py` | comparer deux contours (planifié vs levé) | Une liste d'écarts |

Remarque de tri : les rangs 1 à 8 sont ceux qui comblent un manque propre au Maroc (relevé sans LIDAR) ou un vrai gain de simplicité. Le rang 12 (coller) touche à ACAL425 (guides) mais seul le collage n'est pas planifié. Déjà au plan, donc NON proposés : soleil animé dans la visionneuse du client (ACAL487, GATED autre propriétaire), formes de toit (ACAL410), légende de la carte d'accès solaire (ACAL441), conception automatique d'un clic (ACAL421), cible de production (ACAL470), téléphone (ACAL423/482).

---

## Ce qui a été bloqué ou non lu

- `help.aurorasolar.com` et `support.opensolar.com` : jamais ouverts (règle). Des extraits de ces pages apparaissaient dans les résultats de recherche (sur « 3 ways to model a roof », « Obstructions », « Heatmaps on OpenSolar », « Generating a Shade Report », AI SmartRoof/Trees) : AUCUN n'a été utilisé comme ligne.
- 403 : `capterra.com` (Aurora et OpenSolar), `solaredge.com/.../designer`, `businesswire.com` (communiqué HelioScope stockage). 404 : `opensolar.com/design/`, `aurorasolar.com/lead-capture-ai/`, `pvsyst.com/pvsyst/`, `pvsyst.com/features/`, `arka360.com/ros/solar-design-software/`. `pylon.solar` : erreur de certificat (le site réel est `getpylon.com`, lu). Hôte `www.nrel.gov` introuvable. `updates.aurorasolar.com` (journal des versions Aurora) : rendu côté navigateur, page vide à la lecture ; la page d'accueil `arka360.com` ne décrit aucun écran.
- Vidéos : les pages YouTube ne servent que le titre (pas de description ni chapitres), donc seulement des titres (lignes A53, O52).
- Aucun test n'a été lancé ; les verdicts « chez nous » viennent des inventaires `r1/a1-a3` recoupés par `git grep` ciblés (symboles vérifiés : `simuler_batterie`, `concevoir_par_pan`, `lire_serie_meteo`, `bloc_incertitude`, `SurfaceSol`, `fraction_ombree`, `ClientHorizon`, `createSoleilPlayer`, `proposeShadedRemoval`, `setAffectationChaines`, `liveResolveFlat`, `courbe_vehicule`, `dimensionner_hors_reseau`, `fillAll`, `cellsSolarAccess`, `ajouterPanDepuisContour`, `ObstacleType`).
- Les clauses « Constat » des lots `plan/lot-W*.md` n'ont servi qu'à confirmer l'existence des tâches ACAL382-490 (déjà dans `docs/plans/PLAN_AUDIT_CALEPINAGE.md`).

---

## Table des sources (toutes lues, date de lecture 21/11/2026)

| Id | URL | Type |
|---|---|---|
| S-A1 | https://aurorasolar.com/design-mode/ | produit |
| S-A2 | https://aurorasolar.com/aurora-ai/ | produit |
| S-A3 | https://aurorasolar.com/product/ | produit |
| S-A4 | https://aurorasolar.com/sell-battery-storage/ | produit |
| S-A4' | https://aurorasolar.com/sales-mode/ | produit |
| S-A5 | https://aurorasolar.com/drone-mapping/ | produit |
| S-A-PLAN | https://aurorasolar.com/plan-sets/ | produit |
| S-A6 | https://aurorasolar.com/blog/lidar-what-it-is-how-it-works-and-a-huge-update/ | blog |
| S-A8 | https://aurorasolar.com/expert-design-services/ | produit |
| S-A9 | https://aurorasolar.com/pricing/ | produit |
| S-A10 | https://aurorasolar.com/api/ (légende d'image) | produit |
| S-A11 | https://aurorasolar.com/aurora-for-channel-managers/ | produit |
| S-A12 | https://aurorasolar.com/api/ | produit |
| S-B-FIRE | https://aurorasolar.com/blog/whats-the-deal-with-fire-setbacks-auroras-fire-pathways-solution-explained/ | blog |
| S-B-IRR | https://www.aurorasolar.com/smarter-solar-design-with-irradiance-on-modules | blog |
| S-B-STR | https://aurorasolar.com/?p=13829 (AutoStringer) | blog |
| S-B-MLPE | https://aurorasolar.com/blog/now-you-can-design-solar-installations-using-multi-input-module-level-power-electronics-mi-mlpe-in-aurora/ | blog |
| S-B-HOR | https://aurorasolar.com/blog/top-10-things-you-didnt-know-aurora-can-do-9-horizon-shading/ | blog |
| S-B-HSPV | https://aurorasolar.com/blog/2024/07/12/optimizing-commercial-solar-project-designs-a-comprehensive-comparison-of-helioscope-and-pvsyst/ | blog (vendeur) |
| S-R-MUST | https://resources.aurorasolar.com/solar-software-must-haves-for-design-pros/design-special-features | produit |
| S-DOCS | https://docs.aurorasolar.com/reference/fire-pathway-placement | docs API (page servie normalement) |
| S-HS | https://helioscope.aurorasolar.com et /design-solutions/ | produit |
| S-PV | https://pv-magazine-usa.com/2026/09/22/aurora-solar-updates-platform-to-include-home-electrification-and-new-financing-tools/ | presse |
| S-SURGE-A | https://www.surgepv.com/reviews/aurora-solar | avis (concurrent, opinion) |
| S-O1 | https://www.opensolar.com/features/ | produit |
| S-O3 | https://www.opensolar.com/auto-design/ | produit |
| S-O4 | https://www.opensolar.com/3ddesign/ | produit |
| S-O6 | https://www.opensolar.com/premium-imagery/ | produit |
| S-O-AUTO | https://www.opensolar.com/auto-design/ | produit |
| S-O-SLD | https://www.opensolar.com/single-line-diagrams/ | produit |
| S-O-MOUNT | https://www.opensolar.com/mounting-designer/ | produit |
| S-O-ELEV | https://www.opensolar.com/elevated-structures/ | produit |
| S-O-SMP | https://www.opensolar.com/sales-machine-proposal/ (+ /proposals/) | produit |
| S-O-BOM | https://www.opensolar.com/auto-bom/ | produit |
| S-O-ROLES | https://www.opensolar.com/rolesandpermissions/ | produit |
| S-O-PERM | https://www.opensolar.com/permitting/ | produit |
| S-O-MOB | https://www.opensolar.com/salesmode/ | produit |
| S-OS30 | https://www.opensolar.com/?p=14292 (blog OS 3.0) | blog |
| S-RN30 | https://www.opensolar.com/?p=14518 (notes OS 3.0) | notes |
| S-RN33 | https://www.opensolar.com/product-updates/release-3-3-0/ | notes |
| S-RN38 | https://www.opensolar.com/product-updates/release-3-8/ | notes |
| S-RN310 | https://www.opensolar.com/product-updates/release-3-10/ | notes |
| S-RN311 | https://www.opensolar.com/product-updates/ (liste) | notes |
| S-RN312 | https://www.opensolar.com/product-updates/release-3-12/ | notes |
| S-RN313 | https://www.opensolar.com/product-updates/release-3-13/ | notes |
| S-SURGE-O | https://www.surgepv.com/reviews/opensolar | avis (concurrent, opinion) |
| S-YT | https://www.youtube.com/watch?v=ncDyHdc6IAg ; ?v=ldc4AYNqbYE ; ?v=QVq4dK6VZGk ; ?v=e0ujZ4j3DTQ | vidéo (titre) |
| S-RE-PLAN | https://reonic.com/en-gb/product/360h/planning/ | produit |
| S-RE-SHADE | https://reonic.com/en-gb/page/shading-analysis/ | produit |
| S-RE-DOCS1 | https://docs.reonic.com/docs/en/offers-plan-pv-plan-building | docs |
| S-RE-DOCS2 | https://docs.reonic.com/docs/en/offers-plan-pv-plan-modules | docs |
| S-PY | https://www.getpylon.com | produit |
| S-SG | https://www.solargraf.com/in/design-tool-in/ | produit |
| S-SC | https://www.scanifly.com | produit |
| S-SE | https://marketing.solaredge.com/solaredge-designer-0-20 | notes |
| S-SE2 | https://www.pv-tech.org/solaredge-bolsters-design-tool-to-streamline-ci-rooftop-planning-process | presse |
| S-PVSOL | https://valentin-software.com/en/products/pvsol-premium | produit |
| S-PVSYST | https://www.pvsyst.com/pdf/pdf-tutorials/pvsyst-8/pvsyst-tutorial-v8-grid-connected-en.pdf et https://www.pvsyst.com/en/products/pvsyst/ | docs officiel |



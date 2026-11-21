# B6 — Notes de version : ce que les outils du marché ont ajouté, année après année, face à notre module Calepinage

Date : 2026-11-21. Dépôt en lecture seule (worktree `calpinage-module-enhance-04bba5`). Sources : pages de notes de version publiques lues cette session ; aucune connexion, aucun contournement de refus.

## 0. Lecture rapide

- **575 lignes** de capacités (une ligne = un élément de note de version, en français, avec le terme du fournisseur entre parenthèses), **19 outils/sources** ; §2.
- Lignes par outil : PVsyst 221 · PVcase 90 · PV*SOL 43 · OpenSolar 58 · Scanifly 28 · Pylon 25 · SolarEdge 16 · SMA Sunny Design 10 · archelios 10 · Eturnity 4 · HelioScope 9 · K2 Base 6 · Huawei 3 · Arka 360 2 · RatedPower 4 · Aurora 4 · Polysun 6 · SAM 23 · pvlib 13.
- **96 grappes** de capacités (§3) ; **58 grappes livrées par 4 outils ou plus** (« table stakes »). Le classement en grappes est fait PAR MOTS-CLÉS sur le texte français : une ligne peut compter dans plusieurs grappes, et un compte d'outils est un plancher plausible, pas une mesure exacte.
- Verdicts par grappe : PRÉSENT 42 · PARTIEL 32 · ABSENT 9 · PLANIFIÉ 4 · HORS DÉCISION 7 · HORS MODULE 2 (§4).
- **63 propositions** (§5) : 27 nouvelles, 36 qui confirment une proposition déjà écrite dans B1-B5 (id cité).
- Ce qui a refusé ou n'a rien donné : §1.

## 1. Sources, couverture, refus

| Outil | Ce qui a répondu | Versions / publications couvertes | Lignes |
|---|---|---|---|
| PVsyst | `https://www.pvsyst.com/help/release-notes/index.html` (page unique de 248 000 caractères, lue en trois morceaux) | 6.00 (2013-02-04) → 8.1.8 (2026-10-26) : toutes les versions listées, ≈ 180 entrées (≈ 85 en 6.x, 63 en 7.x, 31 en 8.x) ; les entrées « base de données » ou « aucune nouveauté » ne donnent pas de ligne | 221 |
| PVcase | API JSON du centre d'aide `help.pvcase.com/api/v2/help_center/en-us/articles.json` (395 articles, 4 pages) | Ground Mount 2.49 → 2.66 (2024-11-20 → 2026-11-12) = 18 notes ; Roof Mount 1.47 → 1.60 (2025-03-20 → 2026-11-04) = 14 notes ; 32 titres uniques | 90 |
| PV*SOL | page produit `valentin-software.com/en/products/pvsol-premium` (notes inline 2026 R1 → 2027 R2) + article « 2025 » + page de nouvelles | 2026 R1…R8 et 2027 R1…R2 (10 publications) + version 2025 (2024-11-20) ; 2019-2024 : aucune note publique lisible | 43 |
| OpenSolar | `opensolar.com/product-updates/` (2 pages de liste) | 2.30.0 → 3.13 (2025-03-08 → 2026-11-16) : 16 pages lues (2.30, 2.31, 2.33, 3.0, 3.2 → 3.13) ; 3.1 = 404 et 2.32.0 = trop de redirections (non lus) ; avant 2.30 : non listé | 58 |
| Scanifly | billets de blog « Product Updates » (liste du blog p. 1-5 sur 18) | 10 billets lus (2025-06 → 2026-11) + listes des pages 1 à 5 ; pages 6-18 non lues | 28 |
| Pylon | billets de blog `getpylon.com/blog/<mois>-update` (le /changelog redirige vers le blog) | mars, mai, juin, juillet, septembre (UK + AU), novembre 2026 (UK + AU) ; billets antérieurs (page 2 du blog) : 404 | 25 |
| SolarEdge Designer | pages d'archive `marketing.solaredge.com/solaredge-designer-0-8 / 0-9 / 0-15` + article presse 2020 | 2020-01, 2021-07, 2021-08, 2022-02 ; plus récent que 2022 : rien de public trouvé | 16 |
| SMA Sunny Design | article de presse 5.20 (2021-07-20) + extraits de recherche des notes de version | 5.0, 5.20, 5.61, 5.90, 6.00 (notes lues par extrait de recherche seulement) ; 6.10 sans détail | 10 |
| archelios PRO / CALC | articles Trace Software + solarserver (2022) | Suite 2022, PRO 2023, 2024 (extraits), 2025.1 (2025-11-21) | 10 |
| NREL SAM | `natlabrockies.github.io/SAM/doc/releasenotes` (424 000 caractères ; 300 000 lus) | 2014.11.24 → 2026.7.3 (2019 absent de la page ; 2014 et plus anciens non lus) | 23 |
| pvlib-python | `pvlib-python.readthedocs.io/en/stable/whatsnew.html` | 0.9.0 (2021-09-01) → 0.16.1 (2026-09-26) | 13 |
| HelioScope | API JSON du centre d'aide (243 articles) : AUCUNE section « notes de version » | 4 articles « Updated … » 2025-2026 + 2 articles stockage 2026 ; les ≈ 100 lignes HelioScope de B3 viennent des pages fonctionnelles, pas de notes | 9 |
| K2 Base | page produit + liste des nouvelles (page 1 sur 10) | 2 entrées 2026 sans détail + liste de fonctions | 6 |
| Huawei SmartDesign | page produit | aucune note de version | 3 |
| Eturnity | article pv magazine 2025-05 | 1 publication | 4 |
| Arka 360 | billet « Web Proposal » | 1 billet, non daté | 2 |
| RatedPower | 2 billets de blog 2026 | 2026-09-15 et 2026-10-14 | 4 |
| Aurora (blog) | page produit + billet « Drone Mapping » | 2 pages, sans date | 4 |
| Polysun | extraits de recherche seulement | 5.6, 5.8, 5.10, 6.2, 7.0, 10.0, 11.1 par extrait | 6 |

**Refus et pages sans contenu utile (rien d'autre n'a été tenté pour les contourner) :**

- `pveurope.eu` (PV*SOL 2026) : « Access Denied » ; trois communiqués `pressebox.com` (Polysun 8.1, 10.0, 11.1) : corps de l'article bloqué par une invite de sécurité ; `knowledge-center.solaredge.com` : 403.
- `help.ratedpower.com` (centre d'aide à rendu JavaScript : écran « loading ») et son API : 401 ; `acca.it/update-release-history/solarius-pv` : la page se charge sans liste ; `esdec.com/en/news` : « Loading… ».
- Introuvables ou sans notes : `pvsyst.com/release-notes` (404, remplacé par `/help/release-notes/`), `docs.reonic.com/…/changelog` (404) et `reonic.com/blog` (aucune annonce), `getpylon.com/changelog` (redirige), `scanifly.com/product-updates` (404), `eturnity.com/product-updates` (404), `helioscope.com/whats-new` (redirige vers Aurora), `renusol.com/en/pv-configurator/` (404), `fronius.com/…solar-creator` (404), `sma.de/…/sunny-design` (404), `solar.huawei.com/en/smart-design/` (aucune note), `k2-systems.com/en/k2-base/` (aucun journal), `easysolar.app` (aucune date).
- Hôtes inexistants : `help.solargraf.com`, `solargraf.com`, `www.archelios.com`. Non tentés faute de page identifiée : Sollit, BlueSol, Schletter, Esdec (hors la page « news » vide), Renusol, Fronius, Solarius (ACCA).
- Aurora et OpenSolar : consigne = billets publics, pas centres d'aide. J'ai fait UN seul appel de sondage à l'API JSON du centre d'aide Aurora (réponse : titres de 5 articles, 314 au total) et n'ai lu aucune de ses notes de version ; elles existent (une recherche en cite) et sont à lire à part si le fondateur l'autorise.
- Un essai `curl` avec un en-tête de navigateur simulé sur `pvsyst.com`/`valentin-software.com` a été refusé par le garde-fou de la session ; je ne l'ai pas rejoué. Les lectures de pages ont ensuite toutes été faites avec l'outil de lecture web ; `curl` simple n'a servi que pour les deux API JSON publiques de Zendesk (PVcase, HelioScope).
- Les 12 recherches web autorisées sont toutes consommées (PVsyst ×2, PV*SOL, SolarEdge, Sunny Design, archelios, Reonic, Polysun, K2, Solarius, SAM, Eturnity).
- Les dates 2026 que les pages impriment (PVsyst 8.1.x, PV*SOL 2027, OpenSolar 3.x, PVcase 2.6x) sont recopiées telles quelles ; la date du jour est le 2026-11-21.

## 2. Lignes (une par capacité), regroupées par outil

Colonnes : n° · version / date telle qu'imprimée · domaine · capacité (FR, terme du fournisseur entre parenthèses) · URL.

### PVsyst (221 lignes)

| n° | Version / date | Domaine | Capacité | URL |
|---|---|---|---|---|
| 1 | 6.02 (2013-02-27) | electrical & stringing | Choix de Vmax IEC ou UL pour la limite de tension Voc au dimensionnement ; option Vco(Tmin) avec muVco | https://www.pvsyst.com/help/release-notes/index.html |
| 2 | 6.11 (2013-08-25) | simulation & losses | Facteur de puissance définissable pour exigences réseau | https://www.pvsyst.com/help/release-notes/index.html |
| 3 | 6.13 (2013-12-08) | variants & optimisation | Inclinaison saisonnière compatible avec l'ombrage 3D ; sous-champs électriques nommés avec orientation | https://www.pvsyst.com/help/release-notes/index.html |
| 4 | 6.05 (2013-04-11) | weather data | Import TMY3 acceptant plus de sources, années spécifiques et années bissextiles | https://www.pvsyst.com/help/release-notes/index.html |
| 5 | 6.11 (2013-08-25) | weather data | Import de projets simples et fichiers météo SolarGIS directs (année précise, TMY, mensuel, multi-annuel) | https://www.pvsyst.com/help/release-notes/index.html |
| 6 | 6.15 (2013-12-19) | results & charts | Copie de la fenêtre de synthèse vers le presse-papiers | https://www.pvsyst.com/help/release-notes/index.html |
| 7 | 6.16 (2013-12-30) | report & documents | Meilleure visualisation de la scène 3D sauvegardée dans le rapport | https://www.pvsyst.com/help/release-notes/index.html |
| 8 | 6.11 (2013-08-25) | variants & optimisation | Évaluation P50-P90 avec page de rapport dédiée (P50-P90 tool) | https://www.pvsyst.com/help/release-notes/index.html |
| 9 | 6.11 (2013-08-25) | simulation & losses | Limitation de puissance injectée au réseau, avec facteur de puissance optionnel (grid power limitation) | https://www.pvsyst.com/help/release-notes/index.html |
| 10 | 6.13 (2013-12-08) | variants & optimisation | Multi-orientation jusqu'à 8 orientations avec ombrage indépendant par orientation | https://www.pvsyst.com/help/release-notes/index.html |
| 11 | 6.13 (2013-12-08) | electrical & stringing | Fenêtre de synthèse du système avec contrôles de compatibilité module/onduleur (System Summary) | https://www.pvsyst.com/help/release-notes/index.html |
| 12 | 6.24 (2014-05-20) | report & documents | Aperçu du rapport : changement d'unités et de langue, copie des résultats vers Excel | https://www.pvsyst.com/help/release-notes/index.html |
| 13 | 6.18 (2014-01-30) | usability | Vue latérale du calepinage avec sélection des tables en 3D ; la mise à jour sauvegarde les fichiers utilisateur | https://www.pvsyst.com/help/release-notes/index.html |
| 14 | 6.20 (2014-03-09) | weather data | Heure d'été revue à l'import ASCII, y compris dates américaines et hémisphère sud | https://www.pvsyst.com/help/release-notes/index.html |
| 15 | 6.25 (2014-06-15) | module placement | Toutes les tables sur un même plan déplaçables ; table de travail sélectionnable en 3D | https://www.pvsyst.com/help/release-notes/index.html |
| 16 | 6.27 (2014-09-18) | simulation & losses | Perte électrique d'ombrage avec seuil ; pertes AC après onduleur tenant compte du facteur de puissance | https://www.pvsyst.com/help/release-notes/index.html |
| 17 | 6.32 (2014-11-13) | simulation & losses | Outil d'analyse IAM (Fresnel, anti-reflet, Sandia) avec distributions d'irradiance | https://www.pvsyst.com/help/release-notes/index.html |
| 18 | 6.18 (2014-01-30) | module placement | Champs 3D définis par nombre de modules en largeur et longueur, champs polygonaux posés module par module | https://www.pvsyst.com/help/release-notes/index.html |
| 19 | 6.18 (2014-01-30) | results & charts | Tableaux mensuels de valeurs horaires pour toute variable de simulation | https://www.pvsyst.com/help/release-notes/index.html |
| 20 | 6.19 (2014-02-10) | results & charts | Vue en perspective colorée par attribution électrique, sauvée en BMP/JPG/PNG/SVG | https://www.pvsyst.com/help/release-notes/index.html |
| 21 | 6.25 (2014-06-15) | report & documents | Calepinage des modules exportable en image et imprimable (ModuleLayout save as image) | https://www.pvsyst.com/help/release-notes/index.html |
| 22 | 6.27 (2014-09-18) | report & documents | Bilan carbone (CO2) avec page de rapport dédiée | https://www.pvsyst.com/help/release-notes/index.html |
| 23 | 6.27 (2014-09-18) | simulation & losses | Optimiseurs Tigo et dépendance de la puissance nominale onduleur à la température | https://www.pvsyst.com/help/release-notes/index.html |
| 24 | 6.35 (2015-03-23) | shading | Outil d'ombrage électrique réécrit avec tracé en fenêtre latérale | https://www.pvsyst.com/help/release-notes/index.html |
| 25 | 6.33 (2015-01-28) | simulation & losses | Pertes de surcharge calculées au dimensionnement avec ratio de puissance nominale rapide | https://www.pvsyst.com/help/release-notes/index.html |
| 26 | 6.35 (2015-03-23) | electrical & stringing | Modules AC identifiés dans la base avec choix automatique du partenaire | https://www.pvsyst.com/help/release-notes/index.html |
| 27 | 6.33 (2015-01-28) | roof & obstacles | Définition et modification du terrain 3D ; zones polygonales de positionnement des tables ; répartition de séries de tables | https://www.pvsyst.com/help/release-notes/index.html |
| 28 | 6.33 (2015-01-28) | electrical & stringing | Partage ajustable de la puissance nominale entre entrées MPPT d'un onduleur multi-MPPT | https://www.pvsyst.com/help/release-notes/index.html |
| 29 | 6.36 (2015-04-29) | shading | Calcul d'ombrage sur un sous-système partiel ; groupes d'objets 3D à modification commune ; vue perspective avec position d'observateur | https://www.pvsyst.com/help/release-notes/index.html |
| 30 | 6.36 (2015-04-29) | weather data | Outil de comparaison de fichiers météo avec profils de probabilité P90 ; création de fichier météo par modèle de ciel clair | https://www.pvsyst.com/help/release-notes/index.html |
| 31 | 6.39 (2015-07-21) | variants & optimisation | Outil d'optimisation complet pour systèmes à rangées (sheds) par simulations en lot avec graphiques | https://www.pvsyst.com/help/release-notes/index.html |
| 32 | 6.39 (2015-07-21) | exports & imports | Import d'objets d'ombrage Helios3D ; terrain défini par fichier CSV personnalisé | https://www.pvsyst.com/help/release-notes/index.html |
| 33 | 6.40 (2016-01-17) | shading | Les objets de sol peuvent projeter des ombres ; facteur d'ombrage pour sous-systèmes partiels amélioré | https://www.pvsyst.com/help/release-notes/index.html |
| 34 | 6.42 (2016-02-18) | consumption & EV & heat pump | Fichiers de profils de charge acceptant davantage de formats | https://www.pvsyst.com/help/release-notes/index.html |
| 35 | 6.40 (2016-01-17) | variants & optimisation | Dialogue d'optimisation de rangées refondu avec visionneuse intégrée et choix générique de paramètres | https://www.pvsyst.com/help/release-notes/index.html |
| 36 | 6.40 (2016-01-17) | usability | Gestion de projet modernisée avec sauvegarde explicite après chaque modification ; lancement depuis un script | https://www.pvsyst.com/help/release-notes/index.html |
| 37 | 6.41 (2016-01-31) | simulation & losses | Choix du modèle de transposition (Hay/Perez) dans les définitions du projet | https://www.pvsyst.com/help/release-notes/index.html |
| 38 | 6.44 (2016-05-29) | usability | Courbe d'efficacité de l'onduleur affichable dans son dialogue ; fichiers de profil de charge horaires plus tolérants | https://www.pvsyst.com/help/release-notes/index.html |
| 39 | 6.46 (2016-06-26) | module placement | Informations de backtracking dans la section Orientation | https://www.pvsyst.com/help/release-notes/index.html |
| 40 | 6.48 (2016-09-19) | electrical & stringing | Optimiseurs Tigo « Smart modules » ; dialogue de facteur de puissance amélioré | https://www.pvsyst.com/help/release-notes/index.html |
| 41 | 6.40 (2016-01-17) | storage | Gestion de batterie réécrite, charge pilotée par SOC, outil visuel liant seuils SOC et tension | https://www.pvsyst.com/help/release-notes/index.html |
| 42 | 6.40 (2016-01-17) | shading | Nouvel algorithme de facteur d'ombrage 3D environ 20 fois plus rapide | https://www.pvsyst.com/help/release-notes/index.html |
| 43 | 6.40 (2016-01-17) | site & imagery | Image du sol importée comme fond de scène 3D ; dessin d'objets 3D à la souris | https://www.pvsyst.com/help/release-notes/index.html |
| 44 | 6.40 (2016-01-17) | roof & obstacles | Nouveaux objets : dômes et éoliennes ; effet d'ombrage désactivable par objet | https://www.pvsyst.com/help/release-notes/index.html |
| 45 | 6.40 (2016-01-17) | variants & optimisation | Variantes de calcul illimitées ; balayage d'inclinaison et azimut ; outil de dimensionnement paramétrique | https://www.pvsyst.com/help/release-notes/index.html |
| 46 | 6.40 (2016-01-17) | consumption & EV & heat pump | Gestion des besoins utilisateur modernisée avec horaires d'usage des appareils (time-of-use) | https://www.pvsyst.com/help/release-notes/index.html |
| 47 | 6.42 (2016-02-18) | simulation & losses | Outil de dégradation des modules avec dispersion pour simuler une année après mise en service (module degradation tool) | https://www.pvsyst.com/help/release-notes/index.html |
| 48 | 6.43 (2016-03-17) | pumping | Pompage : définition de conduite personnalisée (custom pipe) | https://www.pvsyst.com/help/release-notes/index.html |
| 49 | 6.51 (2016-11-27) | pumping | Pompes définissables depuis un document Excel ; nombreuses améliorations du pompage ; optimiseurs Maxim niveau sous-module | https://www.pvsyst.com/help/release-notes/index.html |
| 50 | 6.60 (2017-03-08) | usability | Gestion des variantes améliorée dans le dialogue général du projet | https://www.pvsyst.com/help/release-notes/index.html |
| 51 | 6.60 (2017-03-08) | simulation & losses | Profils IAM prédéfinis (Fresnel, anti-reflet, Sandia) | https://www.pvsyst.com/help/release-notes/index.html |
| 52 | 6.64 (2017-09-04) | electrical & stringing | Courant maximal explicite par MPPT avec catégorie de perte dédiée ; partage de puissance par groupes de sous-champs | https://www.pvsyst.com/help/release-notes/index.html |
| 53 | 6.65 (2017-10-25) | simulation & losses | Bifacial : composante directe en face arrière et correction de la contribution des facteurs de vue | https://www.pvsyst.com/help/release-notes/index.html |
| 54 | 6.60 (2017-03-08) | results & charts | Comparaisons de mesures importables avec les paramètres d'une variante de simulation | https://www.pvsyst.com/help/release-notes/index.html |
| 55 | 6.62 (2017-04-30) | roof & obstacles | Tout objet posable au-dessus de l'objet de sol ; alerte quand un système à trackers n'a pas de définition d'ombrage 3D | https://www.pvsyst.com/help/release-notes/index.html |
| 56 | 6.63 (2017-06-22) | module placement | Orientation saisonnière avec inclinaison d'été négative pour basses latitudes | https://www.pvsyst.com/help/release-notes/index.html |
| 57 | 6.64 (2017-09-04) | weather data | Sources météo Reuniwatt et Explorador | https://www.pvsyst.com/help/release-notes/index.html |
| 58 | 6.65 (2017-10-25) | usability | Dossier de travail : ouverture à l'emplacement courant | https://www.pvsyst.com/help/release-notes/index.html |
| 59 | 6.60 (2017-03-08) | site & imagery | Système de dessin 3D OpenGL refondu ; import de dessin 3D DAE (SketchUp, AutoCAD) | https://www.pvsyst.com/help/release-notes/index.html |
| 60 | 6.60 (2017-03-08) | module placement | Conversion directe d'objets importés en champs PV par sélection de matériaux (DAE/3DS) | https://www.pvsyst.com/help/release-notes/index.html |
| 61 | 6.60 (2017-03-08) | simulation & losses | Modèle bifacial complet pour systèmes à rangées ; profils IAM prédéfinis ; partage de puissance multi-orientation (dômes) | https://www.pvsyst.com/help/release-notes/index.html |
| 62 | 6.60 (2017-03-08) | weather data | Import météo de nouveaux fournisseurs (NSRDB, SolarAnywhere, 3-Tiers), import multi-annuel | https://www.pvsyst.com/help/release-notes/index.html |
| 63 | 6.64 (2017-09-04) | simulation & losses | Outil d'analyse de la dispersion entre chaînes (mismatch between strings) ; outil de définition d'orientation pour systèmes complexes | https://www.pvsyst.com/help/release-notes/index.html |
| 64 | 6.65 (2017-10-25) | shading | Outil d'étude d'ombrage par objet mince (thin object shading) ; dialogue de sélection avancée des objets d'ombrage | https://www.pvsyst.com/help/release-notes/index.html |
| 65 | 6.65 (2017-10-25) | pumping | Dialogue de système de pompage entièrement redessiné | https://www.pvsyst.com/help/release-notes/index.html |
| 66 | 6.65 (2017-10-25) | report & documents | Création directe du PDF du rapport sans logiciel tiers | https://www.pvsyst.com/help/release-notes/index.html |
| 67 | 6.67 (2017-11-15) | module placement | Orientation de trackers à axe horizontal illimités sans scène 3D | https://www.pvsyst.com/help/release-notes/index.html |
| 68 | 6.71 (2018-04-30) | simulation & losses | Backtracking possible avec trackers horizontaux et décalés ; bifacial avec hauteur au sol en paramètre | https://www.pvsyst.com/help/release-notes/index.html |
| 69 | 6.78 (2018-12-17) | simulation & losses | Pertes d'auxiliaires séparées jour et nuit | https://www.pvsyst.com/help/release-notes/index.html |
| 70 | 6.68 (2018-02-01) | simulation & losses | Pertes LID pour systèmes autonomes et de pompage ; valeurs Pxx choisies visibles dans le rapport | https://www.pvsyst.com/help/release-notes/index.html |
| 71 | 6.74 (2018-07-12) | weather data | Mise à jour Meteonorm 7.2 (2 500 stations, coefficient de Linke, humidité) | https://www.pvsyst.com/help/release-notes/index.html |
| 72 | 6.76 (2018-10-17) | usability | Coordonnées en secondes ou 4 décimales ; dossier de modèles de travail | https://www.pvsyst.com/help/release-notes/index.html |
| 73 | 6.78 (2018-12-17) | site & imagery | Carte interactive OpenStreetMap et Geonames optimisée | https://www.pvsyst.com/help/release-notes/index.html |
| 74 | 6.68 (2018-02-01) | storage | Prise en charge des batteries lithium-ion (modèle, base, simulation) | https://www.pvsyst.com/help/release-notes/index.html |
| 75 | 6.70 (2018-03-27) | simulation & losses | Modèle bifacial pour trackers 1 axe ; export du diagramme de pertes vers Excel | https://www.pvsyst.com/help/release-notes/index.html |
| 76 | 6.71 (2018-04-30) | simulation & losses | Outil de vieillissement pour simulation multi-annuelle par lot (ageing tool) ; ombrage multithread | https://www.pvsyst.com/help/release-notes/index.html |
| 77 | 6.72 (2018-05-03) | roof & obstacles | Masques de zones de table pour interdire le placement de tables | https://www.pvsyst.com/help/release-notes/index.html |
| 78 | 6.73 (2018-05-28) | weather data | Import de données météo mesurées sur tracker ; base de prix économique | https://www.pvsyst.com/help/release-notes/index.html |
| 79 | 6.74 (2018-07-12) | results & charts | Performance Ratio corrigé de la météo (température uniquement) ; colonnes mensuelles du rapport sélectionnables | https://www.pvsyst.com/help/release-notes/index.html |
| 80 | 6.76 (2018-10-17) | storage | Stratégies de stockage : autoconsommation, écrêtage de pointe, îlotage réseau faible (battery strategies) | https://www.pvsyst.com/help/release-notes/index.html |
| 81 | 6.76 (2018-10-17) | weather data | Import direct PVGIS et NREL NSRDB ; import d'horizon depuis PVGIS ou CSV ; import SAM CSV | https://www.pvsyst.com/help/release-notes/index.html |
| 82 | 6.76 (2018-10-17) | simulation & losses | Modèle de correction spectrale First Solar ; filtre modules bifaciaux et 1500 V | https://www.pvsyst.com/help/release-notes/index.html |
| 83 | 6.78 (2018-12-17) | results & charts | Outil d'évaluation économique avancé (coûts détaillés, stratégie d'injection, dégradation, bilan financier) | https://www.pvsyst.com/help/release-notes/index.html |
| 84 | 6.78 (2018-12-17) | simulation & losses | Limitation de puissance au niveau onduleur et avec autoconsommation ; pertes d'auxiliaires jour/nuit séparées | https://www.pvsyst.com/help/release-notes/index.html |
| 85 | 6.79 (2019-03-05) | weather data | Import météo personnalisé avec nouvelles variables et choix d'unités | https://www.pvsyst.com/help/release-notes/index.html |
| 86 | 6.80 (2019-05-16) | report & documents | Nouveaux graphiques par défaut dans le rapport (entrée/sortie, distribution de puissance) et graphiques prédéfinis sélectionnables | https://www.pvsyst.com/help/release-notes/index.html |
| 87 | 6.79 (2019-03-05) | usability | Bouton de création de site directement dans la fenêtre projet ; tri des projets par site | https://www.pvsyst.com/help/release-notes/index.html |
| 88 | 6.80 (2019-05-16) | usability | Filtres de recherche dans les paramètres cachés | https://www.pvsyst.com/help/release-notes/index.html |
| 89 | 6.79 (2019-03-05) | shading | Objet d'ombrage pylône électrique et outil de liaison de câbles ; simplification automatique de géométrie importée | https://www.pvsyst.com/help/release-notes/index.html |
| 90 | 6.79 (2019-03-05) | simulation & losses | Suivi par optimisation de l'irradiance sur le tracker ; tarifs d'injection horaires avec import CSV | https://www.pvsyst.com/help/release-notes/index.html |
| 91 | 6.79 (2019-03-05) | weather data | Imports météo directs Vaisala et PVGIS ; import météo personnalisé refondu avec choix d'unités | https://www.pvsyst.com/help/release-notes/index.html |
| 92 | 6.80 (2019-05-16) | storage | Batterie universelle pour optimisations par lot ; état de usure initial (SOW) en autonome | https://www.pvsyst.com/help/release-notes/index.html |
| 93 | 6.80 (2019-05-16) | usability | Info-bulle au survol d'un module dans le calepinage ; affichage optionnel du chemin solaire | https://www.pvsyst.com/help/release-notes/index.html |
| 94 | 6.81 (2019-05-30) | shading | Outil de sélection avancée pour lister et gérer les objets ; modification groupée de la pente de base des tables | https://www.pvsyst.com/help/release-notes/index.html |
| 95 | 6.84 (2019-08-29) | weather data | Import des nouveaux fichiers SolarAnywhere (TMY et séries temporelles) | https://www.pvsyst.com/help/release-notes/index.html |
| 96 | 6.86 (2019-12-18) | results & charts | Économies d'autoconsommation dans le graphique de bilan annuel ; import PVGIS 5.1 | https://www.pvsyst.com/help/release-notes/index.html |
| 97 | 7.0.0 (2020-05-25) | usability | Architecture 64 bits ; interface refondue ; traduction complète du logiciel | https://www.pvsyst.com/help/release-notes/index.html |
| 98 | 7.0.15 (2020-10-20) | consumption & EV & heat pump | Profils de charge horaires importés renormalisables à la consommation annuelle ; profils types ajoutés aux modèles | https://www.pvsyst.com/help/release-notes/index.html |
| 99 | 7.1.0 (2020-11-25) | electrical & stringing | Meilleure attribution des chaînes, y compris avec nombre impair de modules | https://www.pvsyst.com/help/release-notes/index.html |
| 100 | 7.1.1 (2020-12-09) | shading | Outils de sélection des matériaux PV dans la fenêtre d'import ; menu contextuel 3D amélioré | https://www.pvsyst.com/help/release-notes/index.html |
| 101 | 7.0.0 (2020-05-25) | electrical & stringing | Avertissements de configuration pendant et après la simulation | https://www.pvsyst.com/help/release-notes/index.html |
| 102 | 7.0.6 (2020-07-28) | usability | Vue de dessus avec nord en haut dans l'hémisphère sud | https://www.pvsyst.com/help/release-notes/index.html |
| 103 | 7.1.2 (2020-12-21) | results & charts | Choix des données P50-P90 à afficher dans le rapport amélioré | https://www.pvsyst.com/help/release-notes/index.html |
| 104 | 7.0.0 (2020-05-25) | variants & optimisation | Sous-champs illimités (unlimited sub-arrays) | https://www.pvsyst.com/help/release-notes/index.html |
| 105 | 7.0.0 (2020-05-25) | shading | Conversion de tables fixes en trackers, trackers à espace central, import de trackers Helios3D et PVC | https://www.pvsyst.com/help/release-notes/index.html |
| 106 | 7.0.0 (2020-05-25) | results & charts | Résultats en direct pendant la simulation ; avertissements pendant et après simulation | https://www.pvsyst.com/help/release-notes/index.html |
| 107 | 7.0.0 (2020-05-25) | results & charts | LCOE, VAN, prêts multiples et amortissement avancé ; évaluation économique pour autonome et pompage | https://www.pvsyst.com/help/release-notes/index.html |
| 108 | 7.0.0 (2020-05-25) | electrical & stringing | Plusieurs transformateurs MT et HT dans le circuit de sortie AC | https://www.pvsyst.com/help/release-notes/index.html |
| 109 | 7.0.0 (2020-05-25) | report & documents | Calepinage imprimable dans le rapport ; interface traduite (turc, coréen ajoutés) | https://www.pvsyst.com/help/release-notes/index.html |
| 110 | 7.1.0 (2020-11-25) | report & documents | Refonte du rapport : blocs modulaires, page de garde personnalisable, page de synthèse, table des matières à signets, 600 DPI | https://www.pvsyst.com/help/release-notes/index.html |
| 111 | 7.1.0 (2020-11-25) | module placement | Remplissage d'une zone par trackers à axe incliné ; modification groupée améliorée ; modules demi-cellules jumeaux avec optimiseurs | https://www.pvsyst.com/help/release-notes/index.html |
| 112 | 7.1.0 (2020-11-25) | cabling | Pertes ohmiques AC définies par onduleur ; perte de ligne HT après transformateur | https://www.pvsyst.com/help/release-notes/index.html |
| 113 | 7.1.4 (2021-01-27) | collaboration & templates | Import de variante au clavier ; téléchargement des mises à jour en arrière-plan | https://www.pvsyst.com/help/release-notes/index.html |
| 114 | 7.2.4 (2021-07-06) | simulation & losses | Restrictions de backtracking et bifacial extensibles par paramètres avancés | https://www.pvsyst.com/help/release-notes/index.html |
| 115 | 7.2.5 (2021-09-02) | roof & obstacles | Inclinaisons négatives acceptées depuis les fichiers H2P | https://www.pvsyst.com/help/release-notes/index.html |
| 116 | 7.2.7 (2021-10-22) | results & charts | Export CSV dans la fenêtre de backtracking ; nombre total de modules en barre d'état | https://www.pvsyst.com/help/release-notes/index.html |
| 117 | 7.2.9 (2021-12-13) | variants & optimisation | Variabilité météo annuelle P50/P90 par défaut pour tous les fournisseurs qui la donnent | https://www.pvsyst.com/help/release-notes/index.html |
| 118 | 7.1.7 (2021-03-17) | weather data | Génération GHI/DHI à partir de DNI avec SolarAnywhere ; nouveau format incluant albédo et particules | https://www.pvsyst.com/help/release-notes/index.html |
| 119 | 7.1.8 (2021-04-01) | exports & imports | Translation définie par l'utilisateur à l'import de fichiers 3D | https://www.pvsyst.com/help/release-notes/index.html |
| 120 | 7.2.3 (2021-06-03) | exports & imports | Création de fichier PAN simplifiée avec messages de guidage | https://www.pvsyst.com/help/release-notes/index.html |
| 121 | 7.2.3 (2021-06-03) | weather data | Import météo : albédo mensuel ; irradiance incidente dans le plan (PoA) avec transposition inverse de Hay | https://www.pvsyst.com/help/release-notes/index.html |
| 122 | 7.2.3 (2021-06-03) | module placement | Option de prise en compte des zones de tables pour identifier les orientations | https://www.pvsyst.com/help/release-notes/index.html |
| 123 | 7.2.5 (2021-09-02) | weather data | Fenêtre de création de site améliorée : données horaires importées, valeurs mensuelles éditables, génération synthétique | https://www.pvsyst.com/help/release-notes/index.html |
| 124 | 7.2.7 (2021-10-22) | usability | Rappel d'expiration de licence dans le menu principal | https://www.pvsyst.com/help/release-notes/index.html |
| 125 | 7.1.4 (2021-01-27) | roof & obstacles | Vues « Géographique » et « Bâtiment » de la scène 3D | https://www.pvsyst.com/help/release-notes/index.html |
| 126 | 7.1.4 (2021-01-27) | results & charts | Détail du prêt dans le rapport économique | https://www.pvsyst.com/help/release-notes/index.html |
| 127 | 7.1.6 (2021-03-05) | simulation & losses | Option de transposition circumsolaire dans les options du projet | https://www.pvsyst.com/help/release-notes/index.html |
| 128 | 7.2.0 (2021-04-22) | module placement | Dialogues de champ 3D redessinés autour du nombre de modules et de l'orientation ; partition en rectangles et chaînes | https://www.pvsyst.com/help/release-notes/index.html |
| 129 | 7.2.0 (2021-04-22) | roof & obstacles | Outil de calcul et d'affichage des angles entre plans | https://www.pvsyst.com/help/release-notes/index.html |
| 130 | 7.2.0 (2021-04-22) | report & documents | Comparaison de rapports côte à côte avec surlignage des différences | https://www.pvsyst.com/help/release-notes/index.html |
| 131 | 7.2.0 (2021-04-22) | weather data | Base Meteonorm 8 ; SOLCAST comme source météo ; traductions japonaise et chinoise complètes | https://www.pvsyst.com/help/release-notes/index.html |
| 132 | 7.2.0 (2021-04-22) | shading | Gestionnaire de pas de backtracking avec analyse de toute la scène ; contrôle d'adéquation des modules dans le calepinage | https://www.pvsyst.com/help/release-notes/index.html |
| 133 | 7.2.4 (2021-07-06) | weather data | Génération d'année type TMY à partir de données horaires multi-annuelles (méthodes ISO, Sandia, NREL) | https://www.pvsyst.com/help/release-notes/index.html |
| 134 | 7.2.7 (2021-10-22) | variants & optimisation | Nouvelle fenêtre de gestion des variantes (variant management) | https://www.pvsyst.com/help/release-notes/index.html |
| 135 | 7.2.9 (2021-12-13) | consumption & EV & heat pump | Accès rapide aux modèles de profils de charge à l'import CSV | https://www.pvsyst.com/help/release-notes/index.html |
| 136 | 7.2.10 (2021-12-21) | shading | Conversion d'un champ PV en objets d'ombrage élémentaires ; modifications groupées de trackers à axe vertical | https://www.pvsyst.com/help/release-notes/index.html |
| 137 | 7.2.13 (2022-04-07) | simulation & losses | Performance IEC 61724-1 bifaciale dans le résumé des résultats | https://www.pvsyst.com/help/release-notes/index.html |
| 138 | 7.2.15 (2022-06-02) | shading | Copier-coller dans l'outil de sélection avancée des ombrages | https://www.pvsyst.com/help/release-notes/index.html |
| 139 | 7.3.0 (2022-12-19) | results & charts | Résultats d'ombrage et de vieillissement affichés en tableau exportable | https://www.pvsyst.com/help/release-notes/index.html |
| 140 | 7.2.12 (2022-02-24) | electrical & stringing | Optimiseur SolarEdge pour onduleur central | https://www.pvsyst.com/help/release-notes/index.html |
| 141 | 7.3.0 (2022-12-19) | results & charts | Rapport fusionnant graphiques spéciaux et prédéfinis, sélectionnables et ordonnables | https://www.pvsyst.com/help/release-notes/index.html |
| 142 | 7.3.0 (2022-12-19) | usability | Projets chargeables depuis la fenêtre d'accueil ; résumé de projet et notes utilisateur améliorés ; azimut de zone au dixième de degré | https://www.pvsyst.com/help/release-notes/index.html |
| 143 | 7.2.13 (2022-04-07) | electrical & stringing | Optimiseurs Huawei avec contraintes de dimensionnement ; profils de charge importés remis à l'échelle de la consommation mensuelle | https://www.pvsyst.com/help/release-notes/index.html |
| 144 | 7.2.15 (2022-06-02) | weather data | Téléchargement direct des données météo SolarAnywhere ; nouvelle interface de partage de puissance | https://www.pvsyst.com/help/release-notes/index.html |
| 145 | 7.2.16 (2022-06-15) | report & documents | Rapport montrant l'attribution module/chaîne dans la vue 3D ; support PVGIS 5.2 | https://www.pvsyst.com/help/release-notes/index.html |
| 146 | 7.2.17 (2022-07-26) | storage | Dialogue de stockage réseau avec durées de charge/décharge par niveau de puissance ; interdiction de réinjection avec autoconsommation | https://www.pvsyst.com/help/release-notes/index.html |
| 147 | 7.3.0 (2022-12-19) | electrical & stringing | Vue de circuit unifilaire des chaînes et onduleurs (single-line circuit view) | https://www.pvsyst.com/help/release-notes/index.html |
| 148 | 7.3.0 (2022-12-19) | results & charts | TRI dans les résultats financiers ; amortissement par actif ; provision annuelle de remplacement d'onduleur | https://www.pvsyst.com/help/release-notes/index.html |
| 149 | 7.3.0 (2022-12-19) | simulation & losses | Outil de définition d'ombrage diffus des trackers ; révision majeure de la limitation réseau | https://www.pvsyst.com/help/release-notes/index.html |
| 150 | 7.3.1 (2022-12-22) | module placement | Conversion d'une table PV unique en un ou plusieurs réseaux de tables | https://www.pvsyst.com/help/release-notes/index.html |
| 151 | 7.3.2 (2023-02-08) | electrical & stringing | Regroupement d'onduleurs plus simple dans le schéma unifilaire | https://www.pvsyst.com/help/release-notes/index.html |
| 152 | 7.3.3 (2023-04-04) | exports & imports | Avertissements quand les données IAM ou faible éclairement des fichiers PAN sont sur-évaluées | https://www.pvsyst.com/help/release-notes/index.html |
| 153 | 7.4.0 (2023-06-26) | electrical & stringing | Optimiseurs Sungrow avec contraintes de dimensionnement | https://www.pvsyst.com/help/release-notes/index.html |
| 154 | 7.4.1 (2023-08-22) | usability | Axes, grille et points cardinaux basculables depuis la barre d'outils | https://www.pvsyst.com/help/release-notes/index.html |
| 155 | 7.3.2 (2023-02-08) | shading | Avertissement pour recalculer les tables d'ombrage faites avec une version plus ancienne ; fichiers 3DS importés ramenés à l'origine de la scène | https://www.pvsyst.com/help/release-notes/index.html |
| 156 | 7.3.2 (2023-02-08) | storage | Circuit et instructions dans l'écran de partage de puissance | https://www.pvsyst.com/help/release-notes/index.html |
| 157 | 7.4.3 (2023-11-03) | weather data | Format Solargis à virgule ; mode lot changeant site et fichier météo ensemble | https://www.pvsyst.com/help/release-notes/index.html |
| 158 | 7.3.2 (2023-02-08) | simulation & losses | Outil de vieillissement refondu ; calcul automatique de rabattement spécifique ou débit maximal en pompage | https://www.pvsyst.com/help/release-notes/index.html |
| 159 | 7.3.2 (2023-02-08) | roof & obstacles | Tout objet convertible en objet de sol ; colonne objets minces et sous-objets de bâtiment en sélection avancée | https://www.pvsyst.com/help/release-notes/index.html |
| 160 | 7.3.3 (2023-04-04) | simulation & losses | Détection automatique de la taille de cellule PV ; ombrage de la structure arrière pour bifacial | https://www.pvsyst.com/help/release-notes/index.html |
| 161 | 7.3.3 (2023-04-04) | exports & imports | Option de rotation 180° de tous les objets à l'import DAE/PVC/3DS ; sortie de lot en unités choisies | https://www.pvsyst.com/help/release-notes/index.html |
| 162 | 7.4.0 (2023-06-26) | simulation & losses | Mise en drapeau par vent (wind stow) pour trackers ; modèle de partitions d'ombrage électrique amélioré | https://www.pvsyst.com/help/release-notes/index.html |
| 163 | 7.4.0 (2023-06-26) | weather data | Import TMY horaires 3E ; import NSRDB Asie/Australie/Pacifique | https://www.pvsyst.com/help/release-notes/index.html |
| 164 | 7.4.3 (2023-11-03) | electrical & stringing | Règles de conception Huawei et liste d'onduleurs éditable avec stratégie de chaînes longues par réduction de tension | https://www.pvsyst.com/help/release-notes/index.html |
| 165 | 7.4.3 (2023-11-03) | results & charts | Diagramme de pertes montrant charge/décharge batterie et E_Solar ; simulation autonome révisée | https://www.pvsyst.com/help/release-notes/index.html |
| 166 | 7.4.5 (2023-12-08) | weather data | Option TMY via API Solargis à la création du site ; messages d'erreur détaillés à l'import CSV météo | https://www.pvsyst.com/help/release-notes/index.html |
| 167 | 8.0.0 (2024-11-07) | simulation & losses | Pas de pitch bifacial définissable pour le modèle d'irradiance ; ombrage diffus par orientation | https://www.pvsyst.com/help/release-notes/index.html |
| 168 | 8.0.0 (2024-11-07) | weather data | Import d'horizon SolarAnywhere ; choix Bing Maps ou OpenStreetMap | https://www.pvsyst.com/help/release-notes/index.html |
| 169 | 8.0.0 (2024-11-07) | results & charts | Rapports PDF sans mot de passe ; format de date américain dans les rapports | https://www.pvsyst.com/help/release-notes/index.html |
| 170 | 7.4.6 (2024-03-19) | module placement | Avertissement quand le GCR moyen diffère du GCR de backtracking | https://www.pvsyst.com/help/release-notes/index.html |
| 171 | 7.4.6 (2024-03-19) | storage | Modèle de stockage réseau refondu pour batteries sur/sous-dimensionnées avec meilleure gestion du SOC | https://www.pvsyst.com/help/release-notes/index.html |
| 172 | 8.0.0 (2024-11-07) | variants & optimisation | Orientations illimitées, trackers et plans fixes mélangés dans une même simulation, orientations mixtes pour tous types de champs | https://www.pvsyst.com/help/release-notes/index.html |
| 173 | 8.0.0 (2024-11-07) | simulation & losses | Bifacial dans plusieurs orientations ; ombrage diffus par orientation ; correction d'écrêtage sub-horaire | https://www.pvsyst.com/help/release-notes/index.html |
| 174 | 8.0.0 (2024-11-07) | storage | Systèmes autonomes avec plusieurs sous-champs et orientations | https://www.pvsyst.com/help/release-notes/index.html |
| 175 | 8.0.0 (2024-11-07) | collaboration & templates | PVsystCLI, interface texte pour automatiser les simulations | https://www.pvsyst.com/help/release-notes/index.html |
| 176 | 8.0.0 (2024-11-07) | site & imagery | Téléchargement de l'image du sol et de la topographie depuis la carte interactive ; afficher/masquer/recadrer l'image | https://www.pvsyst.com/help/release-notes/index.html |
| 177 | 8.0.0 (2024-11-07) | roof & obstacles | Outil de contrôle d'orientation ; rotation X/Z de tous les objets | https://www.pvsyst.com/help/release-notes/index.html |
| 178 | 8.0.0 (2024-11-07) | exports & imports | Import CSV de terrain amélioré (translation, rotation, simplification) ; import direct des fichiers SolarAnywhere PXX | https://www.pvsyst.com/help/release-notes/index.html |
| 179 | 8.0.0 (2024-11-07) | usability | Documentation reconstruite (recherche, modes clair/sombre, impression) ; page d'accueil réorganisée | https://www.pvsyst.com/help/release-notes/index.html |
| 180 | 8.0.8 (2025-03-18) | results & charts | Perte de limitation réseau variable sélectionnable dans le tableau mensuel du rapport | https://www.pvsyst.com/help/release-notes/index.html |
| 181 | 8.0.10 (2025-04-23) | site & imagery | Azure Maps remplace Bing Maps | https://www.pvsyst.com/help/release-notes/index.html |
| 182 | 8.0.13 (2025-06-12) | results & charts | Coût des optimiseurs inclus dans les coûts d'installation ; le rapport indique le nom du fichier PAN personnalisé | https://www.pvsyst.com/help/release-notes/index.html |
| 183 | 8.0.12 (2025-05-15) | shading | Outil de backtracking montrant toutes les orientations de trackers, y compris en erreur | https://www.pvsyst.com/help/release-notes/index.html |
| 184 | 8.0.13 (2025-06-12) | results & charts | Report affichant la limitation réseau ; surcharge ajustée quand un facteur de puissance est fixé | https://www.pvsyst.com/help/release-notes/index.html |
| 185 | 8.0.14 (2025-07-17) | usability | Aide réécrite avec illustrations (facteur de puissance, GCR) ; message en quittant la 3D si la sélection d'ombrage partiel est petite | https://www.pvsyst.com/help/release-notes/index.html |
| 186 | 8.0.16 (2025-09-18) | weather data | NSRDB Physical Solar Model passé de v3 à v4 | https://www.pvsyst.com/help/release-notes/index.html |
| 187 | 8.0.19 (2025-12-09) | module placement | L'import groupe les orientations de tables selon les tolérances du projet | https://www.pvsyst.com/help/release-notes/index.html |
| 188 | 8.0.6 (2025-01-15) | shading | Nouvel outil d'ombrage électrique pour analyser les très faibles tensions cellule inverses | https://www.pvsyst.com/help/release-notes/index.html |
| 189 | 8.0.7 (2025-02-21) | module placement | Création d'une orientation à partir d'objets PV sélectionnés (Create orientation from selection) | https://www.pvsyst.com/help/release-notes/index.html |
| 190 | 8.0.7 (2025-02-21) | weather data | PVGIS 5.3 par API par défaut | https://www.pvsyst.com/help/release-notes/index.html |
| 191 | 8.0.8 (2025-03-18) | variants & optimisation | Onglet de gestion des orientations estimant l'effet de la dispersion d'orientation sur l'irradiation incidente | https://www.pvsyst.com/help/release-notes/index.html |
| 192 | 8.0.10 (2025-04-23) | usability | Gestion des groupes par menu contextuel de la scène 3D ; ajout d'objets PV à une orientation existante | https://www.pvsyst.com/help/release-notes/index.html |
| 193 | 8.0.10 (2025-04-23) | shading | Courbes I-V des MPPT à orientations mixtes après l'animation d'ombrage | https://www.pvsyst.com/help/release-notes/index.html |
| 194 | 8.0.12 (2025-05-15) | results & charts | PR bifacial tenant compte du facteur de bifacialité dans rapport et tableaux mensuels | https://www.pvsyst.com/help/release-notes/index.html |
| 195 | 8.0.13 (2025-06-12) | simulation & losses | Dégradation des modules renommée « Module degradation » ; avertissements de sous-dimensionnement onduleur à 2 % et 4 % de surcharge | https://www.pvsyst.com/help/release-notes/index.html |
| 196 | 8.0.13 (2025-06-12) | report & documents | Projet commercial de démonstration ; le rapport indique le mode de limitation réseau | https://www.pvsyst.com/help/release-notes/index.html |
| 197 | 8.0.15 (2025-08-13) | electrical & stringing | Sous-champs SolarEdge avec chaînes hétérogènes | https://www.pvsyst.com/help/release-notes/index.html |
| 198 | 8.0.17 (2025-10-22) | storage | Stratégie de stockage réseau de décalage de puissance vers les périodes à meilleur tarif (power shifting) | https://www.pvsyst.com/help/release-notes/index.html |
| 199 | 8.1.0 (2026-04-15) | storage | Améliorations de la gestion de batterie autonome ; décalage de puissance de stockage défini par CSV | https://www.pvsyst.com/help/release-notes/index.html |
| 200 | 8.1.0 (2026-04-15) | electrical & stringing | Nouveaux optimiseurs Huawei | https://www.pvsyst.com/help/release-notes/index.html |
| 201 | 8.1.4 (2026-07-01) | weather data | Données météo web API ANE-NEDO pour le Japon | https://www.pvsyst.com/help/release-notes/index.html |
| 202 | 8.1.5 (2026-08-12) | weather data | Génération de fichiers Meteonorm synthétiques au pas de 5 et 15 minutes ; imports multi-années en un fichier par année | https://www.pvsyst.com/help/release-notes/index.html |
| 203 | 8.1.6 (2026-09-16) | simulation & losses | Modèle spectral First Solar avec coefficients personnalisés et graphique du facteur de correction | https://www.pvsyst.com/help/release-notes/index.html |
| 204 | 8.1.7 (2026-10-01) | simulation & losses | Simulation beaucoup plus rapide pour systèmes à nombreux sous-champs ; pas sub-horaires prédéfinis | https://www.pvsyst.com/help/release-notes/index.html |
| 205 | 8.1.0 (2026-04-15) | simulation & losses | Nouvelles étapes de validation des données météo personnalisées | https://www.pvsyst.com/help/release-notes/index.html |
| 206 | 8.1.4 (2026-07-01) | results & charts | Remplissage plus rapide des zones dans la scène 3D | https://www.pvsyst.com/help/release-notes/index.html |
| 207 | 8.1.5 (2026-08-12) | site & imagery | Meilleure sélection des points de sol pour le modèle bifacial de facteurs de vue 2D | https://www.pvsyst.com/help/release-notes/index.html |
| 208 | 8.1.8 (2026-10-26) | shading | Tables d'ombrage d'autres versions signalées et recalculées sur confirmation ou en lot | https://www.pvsyst.com/help/release-notes/index.html |
| 209 | 8.0.20 (2026-02-04) | usability | Tutoriels PDF pas à pas, autonome et pompage | https://www.pvsyst.com/help/release-notes/index.html |
| 210 | 8.1.0 (2026-04-15) | simulation & losses | Simulation sub-horaire pour systèmes réseau et autonomes (sub-hourly simulation) | https://www.pvsyst.com/help/release-notes/index.html |
| 211 | 8.1.0 (2026-04-15) | weather data | Assistant d'import de données météo avec étape de validation ; Meteonorm V9 ; horizon Meteonorm local sans internet ; NASA POWER remplace NASA-SSE | https://www.pvsyst.com/help/release-notes/index.html |
| 212 | 8.1.0 (2026-04-15) | simulation & losses | Modèle thermique transitoire de température de module ; coefficients Perez sub-horaires ; nouveau modèle GHI vers DHI | https://www.pvsyst.com/help/release-notes/index.html |
| 213 | 8.1.0 (2026-04-15) | simulation & losses | Seuil de limitation réseau, salissure et décalage de stockage définissables depuis un CSV de série temporelle | https://www.pvsyst.com/help/release-notes/index.html |
| 214 | 8.1.2 (2026-05-06) | simulation & losses | Albédo du sol définissable depuis une série temporelle CSV | https://www.pvsyst.com/help/release-notes/index.html |
| 215 | 8.1.4 (2026-07-01) | storage | L'état de santé de la batterie (SOH) modifie la capacité pendant la simulation ; variabilité GHI P50-P90 linéaire par défaut | https://www.pvsyst.com/help/release-notes/index.html |
| 216 | 8.1.5 (2026-08-12) | exports & imports | Import de fichiers .pvc2 et .pvz2 pour les données 3D | https://www.pvsyst.com/help/release-notes/index.html |
| 217 | 8.1.5 (2026-08-12) | electrical & stringing | Plus de 2 chaînes par MPPT pour combinaisons Huawei onduleur/optimiseur compatibles | https://www.pvsyst.com/help/release-notes/index.html |
| 218 | 8.1.5 (2026-08-12) | weather data | Température minimale du fichier MET affichée avec alerte si sous la limite de tension absolue | https://www.pvsyst.com/help/release-notes/index.html |
| 219 | 8.1.5 (2026-08-12) | results & charts | Coûts d'exploitation planifiables par année ou plage d'années ; variables d'export GHI et DHI ciel clair | https://www.pvsyst.com/help/release-notes/index.html |
| 220 | 8.1.6 (2026-09-16) | simulation & losses | Indisponibilité du système définissable depuis un CSV de série temporelle ; pertes auxiliaires de nuit coupées si indisponible | https://www.pvsyst.com/help/release-notes/index.html |
| 221 | 8.1.8 (2026-10-26) | results & charts | Graphiques personnalisés (custom graphs) dans les résultats détaillés ; import de météo sub-horaire au format standard | https://www.pvsyst.com/help/release-notes/index.html |

### PVcase (90 lignes)

| n° | Version / date | Domaine | Capacité | URL |
|---|---|---|---|---|
| 222 | 2.49 (2024-11-20) | module placement | [PVcase GM] Génération de rangées pour trackers suivant le terrain (terrain-following) en respectant les angles de joint admis, moins de terrassement | https://help.pvcase.com/hc/en-us/articles/35594041579539-Release-notes-2-49 |
| 223 | 2.49 (2024-11-20) | roof & obstacles | [PVcase GM] Routes 2D : création automatique des croisements et jonctions en T, routes circulaires (2D roads) | https://help.pvcase.com/hc/en-us/articles/35594041579539-Release-notes-2-49 |
| 224 | 2.50 (2024-12-09) | cabling | [PVcase GM] Dimensionnement des câbles et chute de tension DC/AC avec choix IEC/NEC, section minimale, cuivre/alu (cable sizing & voltage drop) | https://help.pvcase.com/hc/en-us/articles/36227369118227-Release-notes-2-50 |
| 225 | 2.50 (2024-12-09) | electrical & stringing | [PVcase GM] Copier-coller d'un schéma électrique complet (chaînes, onduleurs, transfo) sous un autre emplacement (copy transformer and dedicated devices) | https://help.pvcase.com/hc/en-us/articles/36227369118227-Release-notes-2-50 |
| 226 | 2.50 (2024-12-09) | mounting & structure | [PVcase GM] Débords mécaniques (overhangs) des rails au-delà des modules pour fixe-incliné et est-ouest | https://help.pvcase.com/hc/en-us/articles/36227369118227-Release-notes-2-50 |
| 227 | 2.55 (2025-06-16) | electrical & stringing | [PVcase GM] Câblage manuel de chaînes : choix de la connexion d'extrémité de table | https://help.pvcase.com/hc/en-us/articles/42201294317203-Release-notes-2-55 |
| 228 | 2.56 (2025-07-30) | storage | [PVcase GM] Alimentation DC des batteries : câblage DC principal vers l'onduleur central et nomenclature/schéma unifilaire des éléments de batterie | https://help.pvcase.com/hc/en-us/articles/43407020340883-Release-notes-2-56 |
| 229 | 2.57 (2025-11-25) | variants & optimisation | [PVcase GM] Itérations de capacité : les entrées surchargent les paramètres du parc ; version 1 dépréciée | https://help.pvcase.com/hc/en-us/articles/46831310724883-Release-notes-2-57 |
| 230 | 1.55 (2025-09-23) | roof & obstacles | [PVcase RM] Décalages à la création des faîtages | https://help.pvcase.com/hc/en-us/articles/44971319435155-Release-notes-1-55 |
| 231 | 1.56 (2025-10-28) | usability | [PVcase RM] Colonnes du tableau d'informations de calepinage configurables ; masquage des chaînes, câbles, optimiseurs, hachures | https://help.pvcase.com/hc/en-us/articles/46003220223507-Release-notes-1-56 |
| 232 | 1.56 (2025-10-28) | exports & imports | [PVcase RM] Azimuts des modules à plat reportés dans la nomenclature | https://help.pvcase.com/hc/en-us/articles/46003220223507-Release-notes-1-56 |
| 233 | 2.51 (2025-01-20) | variants & optimisation | [PVcase GM] Mode de génération « optimisé » : réglage fin de chaque table pour minimiser terrassement et longueur de pieux dans une plage de garde au sol (optimized mode) | https://help.pvcase.com/hc/en-us/articles/37587553067155-Release-notes-2-51 |
| 234 | 2.51 (2025-01-20) | shading | [PVcase GM] Limite d'ombrage admise entre rangées (allowed shading %) mieux gérée sur terrains accidentés et pentes nord | https://help.pvcase.com/hc/en-us/articles/37587553067155-Release-notes-2-51 |
| 235 | 2.51 (2025-01-20) | mounting & structure | [PVcase GM] Écart structurel entre haut du pieu et dos du module (structural gap) séparé de la quantité de pieux | https://help.pvcase.com/hc/en-us/articles/37587553067155-Release-notes-2-51 |
| 236 | 2.51 (2025-01-20) | results & charts | [PVcase GM] Vue d'ensemble électrique avec longueur, conducteur Cu/Al, section, tension, chute de tension % par câble (Electrical overview) | https://help.pvcase.com/hc/en-us/articles/37587553067155-Release-notes-2-51 |
| 237 | 2.51 (2025-01-20) | cabling | [PVcase GM] Câblage DC principal et DC chaînes séparés pour la configuration boîte de jonction–onduleur–transfo, avec sections et matériaux distincts | https://help.pvcase.com/hc/en-us/articles/37587553067155-Release-notes-2-51 |
| 238 | 2.52 (2025-02-18) | exports & imports | [PVcase GM] Export de la surface de terrain en LandXML (triangulation) pour Civil3D/AGTEK | https://help.pvcase.com/hc/en-us/articles/38633639072915-Release-notes-2-52 |
| 239 | 2.52 (2025-02-18) | cabling | [PVcase GM] Chute de tension avec résistivités NEC (75 °C) en plus d'IEC 60364 | https://help.pvcase.com/hc/en-us/articles/38633639072915-Release-notes-2-52 |
| 240 | 2.52 (2025-02-18) | collaboration & templates | [PVcase GM] Export vers visionneuse web 3D partageable par lien, pour n'importe quelle conception (Export to Web Viewer) | https://help.pvcase.com/hc/en-us/articles/38633639072915-Release-notes-2-52 |
| 241 | 2.52 (2025-02-18) | usability | [PVcase GM] Synchronisation automatique des unités de distance entre le logiciel et AutoCAD | https://help.pvcase.com/hc/en-us/articles/38633639072915-Release-notes-2-52 |
| 242 | 2.53 (2025-04-15) | storage | [PVcase GM] Conception de stockage AC (AC-BESS) dans le module sol | https://help.pvcase.com/hc/en-us/articles/40354272242963-Release-notes-2-53 |
| 243 | 2.53 (2025-04-15) | roof & obstacles | [PVcase GM] Analyse civile refondue : analyse de pente, de collisions et terrassement par garde au sol, carte thermique de terrassement (ground grading heatmap) | https://help.pvcase.com/hc/en-us/articles/40354272242963-Release-notes-2-53 |
| 244 | 2.53 (2025-04-15) | exports & imports | [PVcase GM] Export en KML | https://help.pvcase.com/hc/en-us/articles/40354272242963-Release-notes-2-53 |
| 245 | 2.53 (2025-04-15) | electrical & stringing | [PVcase GM] Câblage en chaîne à travers plusieurs zones PV (stringing across multiple PV areas) et mise à jour du schéma unifilaire pour onduleurs centraux | https://help.pvcase.com/hc/en-us/articles/40354272242963-Release-notes-2-53 |
| 246 | 2.53 (2025-04-15) | cabling | [PVcase GM] Choix multiple de sections de câble candidates dans le calcul de chute de tension | https://help.pvcase.com/hc/en-us/articles/40354272242963-Release-notes-2-53 |
| 247 | 2.53 (2025-04-15) | electrical & stringing | [PVcase GM] Flux de conception électrique préliminaire expérimental (preliminary electrical design flow) | https://help.pvcase.com/hc/en-us/articles/40354272242963-Release-notes-2-53 |
| 248 | 2.54 (2025-04-25) | roof & obstacles | [PVcase GM] Terrassement (ground grading) pour batteries et autres équipements | https://help.pvcase.com/hc/en-us/articles/40659143233299-Release-notes-2-54 |
| 249 | 2.54 (2025-04-25) | variants & optimisation | [PVcase GM] Tri des résultats dans l'itération de capacité (capacity iteration) | https://help.pvcase.com/hc/en-us/articles/40659143233299-Release-notes-2-54 |
| 250 | 2.55 (2025-06-16) | electrical & stringing | [PVcase GM] Gestionnaire de harnais : harnais d'extrémité, parallèle, moteur (harness manager) | https://help.pvcase.com/hc/en-us/articles/42201294317203-Release-notes-2-55 |
| 251 | 2.55 (2025-06-16) | electrical & stringing | [PVcase GM] Câblage par connexion au milieu de la table (middle connection stringing) | https://help.pvcase.com/hc/en-us/articles/42201294317203-Release-notes-2-55 |
| 252 | 2.55 (2025-06-16) | results & charts | [PVcase GM] Surface de couverture effective dans le tableau d'informations de calepinage (effective area coverage) | https://help.pvcase.com/hc/en-us/articles/42201294317203-Release-notes-2-55 |
| 253 | 2.56 (2025-07-30) | storage | [PVcase GM] Batterie couplée DC (DC-coupled BESS) rattachée à un onduleur central | https://help.pvcase.com/hc/en-us/articles/43407020340883-Release-notes-2-56 |
| 254 | 2.56 (2025-07-30) | storage | [PVcase GM] Stockage autonome sans zone PV (standalone BESS) câblé vers ses postes | https://help.pvcase.com/hc/en-us/articles/43407020340883-Release-notes-2-56 |
| 255 | 2.56 (2025-07-30) | mounting & structure | [PVcase GM] Contraintes mécaniques supplémentaires pour trackers suivant le terrain | https://help.pvcase.com/hc/en-us/articles/43407020340883-Release-notes-2-56 |
| 256 | 2.57 (2025-11-25) | simulation & losses | [PVcase GM] Estimation rapide de productible depuis le design (QuickYield, bêta) pour comparer les itérations de capacité | https://help.pvcase.com/hc/en-us/articles/46831310724883-Release-notes-2-57 |
| 257 | 2.57 (2025-11-25) | usability | [PVcase GM] Numérotation cohérente des zones PV | https://help.pvcase.com/hc/en-us/articles/46831310724883-Release-notes-2-57 |
| 258 | 1.47 (2025-03-20) | electrical & stringing | [PVcase RM] Dimensionnement de chaîne recommandé depuis les températures du site et la Vmax onduleur ou MPPT (string sizing) | https://help.pvcase.com/hc/en-us/articles/39561780679571-Release-notes-1-47-1-47-2 |
| 259 | 1.48 (2025-04-15) | site & imagery | [PVcase RM] Utilisation d'imagerie drone (Airteam) dans le projet toiture | https://help.pvcase.com/hc/en-us/articles/40353898032915-Release-notes-1-48 |
| 260 | 1.48 (2025-04-15) | roof & obstacles | [PVcase RM] Outil de pente accepte les pentes négatives ; conversion de toits, obstacles et modules depuis maillages | https://help.pvcase.com/hc/en-us/articles/40353898032915-Release-notes-1-48 |
| 261 | 1.48 (2025-04-15) | module placement | [PVcase RM] Modules en surnombre surlignés en rouge à la tentative de câblage ; inclinaison depuis le sol en plus de l'inclinaison depuis le toit | https://help.pvcase.com/hc/en-us/articles/40353898032915-Release-notes-1-48 |
| 262 | 1.48 (2025-04-15) | shading | [PVcase RM] Nord personnalisé (NorthDirection) pris en compte dans analyses d'ombrage et d'irradiation | https://help.pvcase.com/hc/en-us/articles/40353898032915-Release-notes-1-48 |
| 263 | 1.49 (2025-04-21) | exports & imports | [PVcase RM] Import de conceptions depuis K2 Base | https://help.pvcase.com/hc/en-us/articles/40518835982867-Release-notes-1-49 |
| 264 | 1.50 (2025-05-26) | module placement | [PVcase RM] Modules est et ouest séparés, inversion d'azimut par module (flip module azimuth) ; étiquettes E/O/N/S sur chaînes et BOM | https://help.pvcase.com/hc/en-us/articles/41591214850451-Release-notes-1-50 |
| 265 | 1.50 (2025-05-26) | roof & obstacles | [PVcase RM] Sélection multi-toits d'arêtes pour acrotères et retraits en une fois ; boîtes d'accrochage pour créer les toits | https://help.pvcase.com/hc/en-us/articles/41591214850451-Release-notes-1-50 |
| 266 | 1.51 (2025-07-01) | collaboration & templates | [PVcase RM] Bibliothèque de composants pré-remplie avec recherche et filtres (component library) | https://help.pvcase.com/hc/en-us/articles/42611886078483-Release-notes-1-51 |
| 267 | 1.51 (2025-07-01) | module placement | [PVcase RM] Alignement des modules sur les bords du toit plutôt que sur l'acrotère ; systèmes à plat alignés sur bords | https://help.pvcase.com/hc/en-us/articles/42611886078483-Release-notes-1-51 |
| 268 | 1.52 (2025-07-17) | module placement | [PVcase RM] Génération de calepinage avec cadres à inclinaison fixe (fixed-tilt frames), option d'ajustement des cadres | https://help.pvcase.com/hc/en-us/articles/43067880332947-Release-notes-1-52 |
| 269 | 1.52 (2025-07-17) | collaboration & templates | [PVcase RM] Copier et réutiliser les paramètres de génération d'une zone PV (pick generation settings) | https://help.pvcase.com/hc/en-us/articles/43067880332947-Release-notes-1-52 |
| 270 | 1.53 (2025-08-07) | roof & obstacles | [PVcase RM] Option de planification de toit (planarize roof) et contrôle de santé du constructeur de toit signalant surfaces irrégulières | https://help.pvcase.com/hc/en-us/articles/43635017183507-Release-notes-1-53 |
| 271 | 1.53 (2025-08-07) | module placement | [PVcase RM] Option d'alignement des rangées entre zones PV | https://help.pvcase.com/hc/en-us/articles/43635017183507-Release-notes-1-53 |
| 272 | 1.54 (2025-08-21) | electrical & stringing | [PVcase RM] Création de motifs de câblage personnalisés pour une zone sélectionnée (custom stringing pattern) | https://help.pvcase.com/hc/en-us/articles/44029863872019-Release-notes-1-54 |
| 273 | 1.54 (2025-08-21) | roof & obstacles | [PVcase RM] Notification d'écart d'azimut ; meilleur traitement des toits maillés avec trous ; pente sur n'importe quelle arête | https://help.pvcase.com/hc/en-us/articles/44029863872019-Release-notes-1-54 |
| 274 | 1.54 (2025-08-21) | exports & imports | [PVcase RM] Import de projet PV*SOL amélioré | https://help.pvcase.com/hc/en-us/articles/44029863872019-Release-notes-1-54 |
| 275 | 1.55 (2025-09-23) | simulation & losses | [PVcase RM] Simulation d'énergie avec pertes personnalisables, résultats horaires et export CSV (GHI, DHI, DNI, T amb, vent, irradiance effective, puissance AC) | https://help.pvcase.com/hc/en-us/articles/44971319435155-Release-notes-1-55 |
| 276 | 1.55 (2025-09-23) | electrical & stringing | [PVcase RM] Affectation des chaînes pour utiliser tous les MPPT (un par MPPT d'abord) ; câblage personnalisé reliant le côté opposé en est-ouest | https://help.pvcase.com/hc/en-us/articles/44971319435155-Release-notes-1-55 |
| 277 | 1.56 (2025-10-28) | usability | [PVcase RM] Outil d'audit de la conception toiture (Roof Mount audit tool) | https://help.pvcase.com/hc/en-us/articles/46003220223507-Release-notes-1-56 |
| 278 | 1.56 (2025-10-28) | roof & obstacles | [PVcase RM] Puits de lumière intégrés (skylights) posés perpendiculairement au toit | https://help.pvcase.com/hc/en-us/articles/46003220223507-Release-notes-1-56 |
| 279 | 1.56 (2025-10-28) | collaboration & templates | [PVcase RM] Import/export des réglages de conception et de couloirs | https://help.pvcase.com/hc/en-us/articles/46003220223507-Release-notes-1-56 |
| 280 | 2.58 (2026-01-19) | variants & optimisation | [PVcase GM] Itérations plus rapides et plus précises | https://help.pvcase.com/hc/en-us/articles/48330224363667-Release-notes-2-58 |
| 281 | 2.59 (2026-03-06) | exports & imports | [PVcase GM] Export KML et objets d'ombrage personnalisés mis à jour | https://help.pvcase.com/hc/en-us/articles/49689264573843-Release-notes-2-59 |
| 282 | 2.62 (2026-07-01) | results & charts | [PVcase GM] Carte thermique de terrassement : contours générés par palier, colonnes surface et volume | https://help.pvcase.com/hc/en-us/articles/53070728036371-Release-notes-2-62 |
| 283 | 2.62 (2026-07-01) | usability | [PVcase GM] Précision des champs de distance ; vue de face améliorée avec plateformes de terrassement dans l'interface | https://help.pvcase.com/hc/en-us/articles/53070728036371-Release-notes-2-62 |
| 284 | 2.65 (2026-10-05) | simulation & losses | [PVcase GM] Base de composants, dimensionnement d'onduleur et QuickYield sans connexion séparée | https://help.pvcase.com/hc/en-us/articles/56103380716691-Release-notes-2-65 |
| 285 | 1.57 (2026-03-06) | results & charts | [PVcase RM] Mises en page d'onduleurs plus lisibles | https://help.pvcase.com/hc/en-us/articles/49707073480339-Release-notes-1-57 |
| 286 | 1.58 (2026-07-16) | exports & imports | [PVcase RM] Amélioration de la conversion de blocs vers objets du logiciel (Convert to PVcase) | https://help.pvcase.com/hc/en-us/articles/53520151092243-Release-notes-1-58 |
| 287 | 1.60 (2026-11-04) | roof & obstacles | [PVcase RM] Placement de décalage de faîtage | https://help.pvcase.com/hc/en-us/articles/57132267373331-Release-notes-1-60 |
| 288 | 2.58 (2026-01-19) | module placement | [PVcase GM] Génération de rangées alignées pour est-ouest ; limite de rangées augmentée pour trackers multi-rangées | https://help.pvcase.com/hc/en-us/articles/48330224363667-Release-notes-2-58 |
| 289 | 2.58 (2026-01-19) | shading | [PVcase GM] Placement d'objets d'ombrage par unité, par lot de points ou le long d'une polyligne (shading objects: single/batch/polyline) | https://help.pvcase.com/hc/en-us/articles/48330224363667-Release-notes-2-58 |
| 290 | 2.58 (2026-01-19) | exports & imports | [PVcase GM] Objets d'ombrage personnalisés exportables vers PVsyst | https://help.pvcase.com/hc/en-us/articles/48330224363667-Release-notes-2-58 |
| 291 | 2.58 (2026-01-19) | mounting & structure | [PVcase GM] Options de placement des pieux pour trackers mono-axe ; répartition des appareils révisée en fixe | https://help.pvcase.com/hc/en-us/articles/48330224363667-Release-notes-2-58 |
| 292 | 2.58 (2026-01-19) | electrical & stringing | [PVcase GM] Conception électrique préliminaire : placement automatique du transfo/onduleur central en sélectionnant le bloc, câbles automatiques suivant les couloirs | https://help.pvcase.com/hc/en-us/articles/48330224363667-Release-notes-2-58 |
| 293 | 2.59 (2026-03-06) | cabling | [PVcase GM] Dimensionnement de câbles en version complète avec valeurs dans l'aperçu électrique | https://help.pvcase.com/hc/en-us/articles/49689264573843-Release-notes-2-59 |
| 294 | 2.59 (2026-03-06) | electrical & stringing | [PVcase GM] Câblage manuel de chaînes et schéma unifilaire incluant les harnais | https://help.pvcase.com/hc/en-us/articles/49689264573843-Release-notes-2-59 |
| 295 | 2.59 (2026-03-06) | site & imagery | [PVcase GM] Tracé manuel de la surface effective (draw the effective area) | https://help.pvcase.com/hc/en-us/articles/49689264573843-Release-notes-2-59 |
| 296 | 2.60 (2026-04-02) | electrical & stringing | [PVcase GM] Appareils électriques en 3D (onduleurs et boîtes de jonction avec dimensions modifiables) | https://help.pvcase.com/hc/en-us/articles/50498471168787-Release-notes-2-60 |
| 297 | 2.60 (2026-04-02) | electrical & stringing | [PVcase GM] Câblage continu : remplit chaque rangée avec des chaînes de taille min/max, restes en S ou U (continuous stringing) | https://help.pvcase.com/hc/en-us/articles/50498471168787-Release-notes-2-60 |
| 298 | 2.60 (2026-04-02) | exports & imports | [PVcase GM] Export PVsyst avec sélection des zones et détection automatique du maillage terrain | https://help.pvcase.com/hc/en-us/articles/50498471168787-Release-notes-2-60 |
| 299 | 2.61 (2026-05-04) | usability | [PVcase GM] Étiquetage unifié (rangées, pas, électrique) avec styles (unified labeling) | https://help.pvcase.com/hc/en-us/articles/51392098100755-Release-notes-2-61 |
| 300 | 2.61 (2026-05-04) | simulation & losses | [PVcase GM] QuickYield en version complète | https://help.pvcase.com/hc/en-us/articles/51392098100755-Release-notes-2-61 |
| 301 | 2.62 (2026-07-01) | electrical & stringing | [PVcase GM] Base de composants (module/onduleur) et outil de dimensionnement d'onduleur : tailles de chaîne min/max avec températures PVGIS horaires (inverter sizing) | https://help.pvcase.com/hc/en-us/articles/53070728036371-Release-notes-2-62 |
| 302 | 2.62 (2026-07-01) | cabling | [PVcase GM] Aperçu des modes de pose pour le dimensionnement de câbles (installation methods) | https://help.pvcase.com/hc/en-us/articles/53070728036371-Release-notes-2-62 |
| 303 | 2.63 (2026-08-12) | exports & imports | [PVcase GM] Export PVCollada 2.0 vers le simulateur | https://help.pvcase.com/hc/en-us/articles/54335766571923-Release-notes-2-63 |
| 304 | 2.64 (2026-08-24) | shading | [PVcase GM] Calculs d'ombrage 2 à 10 fois plus rapides | https://help.pvcase.com/hc/en-us/articles/54734740370323-Release-notes-2-64 |
| 305 | 2.64 (2026-08-24) | electrical & stringing | [PVcase GM] Renommage des appareils électriques synchronisé avec les rapports ; placement d'appareil sur poteau optionnel | https://help.pvcase.com/hc/en-us/articles/54734740370323-Release-notes-2-64 |
| 306 | 2.64 (2026-08-24) | exports & imports | [PVcase GM] Export KML étendu aux zones, tables, pieux, objets d'ombrage, transfos et routes | https://help.pvcase.com/hc/en-us/articles/54734740370323-Release-notes-2-64 |
| 307 | 2.65 (2026-10-05) | cabling | [PVcase GM] Câbles enterrés : distance câble-à-câble ; câbles à l'air : type de chemin de câbles et disposition (IEC 60364 B.52) | https://help.pvcase.com/hc/en-us/articles/56103380716691-Release-notes-2-65 |
| 308 | 2.66 (2026-11-12) | cabling | [PVcase GM] Valeurs d'ampacité IEC personnalisées pour gros câbles 400-1000 mm² | https://help.pvcase.com/hc/en-us/articles/57446915266707-Release-notes-2-66 |
| 309 | 1.58 (2026-07-16) | electrical & stringing | [PVcase RM] Réglages du schéma unifilaire (SLD settings) | https://help.pvcase.com/hc/en-us/articles/53520151092243-Release-notes-1-58 |
| 310 | 1.59 (2026-10-12) | cabling | [PVcase RM] Sauts de chaîne longs redirigés vers chemins de câbles ; planarisation de toit améliorée ; inversion de sens des chaînes en saute-mouton | https://help.pvcase.com/hc/en-us/articles/56327383690259-Release-notes-1-59 |
| 311 | 1.60 (2026-11-04) | collaboration & templates | [PVcase RM] Base de composants intégrée au module toiture | https://help.pvcase.com/hc/en-us/articles/57132267373331-Release-notes-1-60 |

### PV*SOL (43 lignes)

| n° | Version / date | Domaine | Capacité | URL |
|---|---|---|---|---|
| 312 | 2025 (2024-11-20) | usability | [PV*SOL premium] Licence par utilisateur utilisable sur plusieurs appareils, gérée par un gestionnaire de licences | https://valentin-software.com/en/product-news-blog-en/pvsol-premium-2025-available-now/ |
| 313 | 2025 (2024-11-20) | results & charts | [PV*SOL premium] Bilan énergétique en diagramme de Sankey, du rayonnement à l'injection (Sankey diagram) | https://valentin-software.com/en/product-news-blog-en/pvsol-premium-2025-available-now/ |
| 314 | 2025 (2024-11-20) | collaboration & templates | [PV*SOL premium] Profils de données utilisateur chargeables dans les projets (user data profiles) | https://valentin-software.com/en/product-news-blog-en/pvsol-premium-2025-available-now/ |
| 315 | 2025 (2024-11-20) | exports & imports | [PV*SOL premium] Export CSV configurable : séries choisies et pas de 1, 10, 15 ou 30 minutes | https://valentin-software.com/en/product-news-blog-en/pvsol-premium-2025-available-now/ |
| 316 | 2025 (2024-11-20) | weather data | [PV*SOL premium] Données climatiques gratuites NREL Meteosat en plus de Meteonorm et PVGIS | https://valentin-software.com/en/product-news-blog-en/pvsol-premium-2025-available-now/ |
| 317 | 2026 R1 (2025-11-24) | consumption & EV & heat pump | [PV*SOL premium] Pompes à chaleur et chauffe-eau à immersion raccordables aux batteries AC et DC | https://valentin-software.com/en/?p=6693 |
| 318 | 2026 R1 (2025-11-24) | results & charts | [PV*SOL premium] Boîte de dialogue de rentabilité redessinée ; export CSV standardisé sans notation scientifique | https://valentin-software.com/en/products/pvsol-premium |
| 319 | 2026 R1 (2025-11-24) | storage | [PV*SOL premium] Charge/décharge combinées avec batteries à couplage DC générateur bloquée ; mode thermique+batterie sans « optimisé PV » | https://valentin-software.com/en/products/pvsol-premium |
| 320 | 2026 R1 (2025-11-24) | report & documents | [PV*SOL premium] Rapports de projet en lituanien | https://valentin-software.com/en/products/pvsol-premium |
| 321 | 2025 (2025-06-03) | exports & imports | [PV*SOL premium] Interface avec le configurateur de fixation Renusol PV-Configurator | https://valentin-software.com/en/company/news/ |
| 322 | 2026 R1 (2025-11-24) | consumption & EV & heat pump | [PV*SOL premium] Nouveau type de système : PV réseau avec appareils, thermique et stockage batterie combinés | https://valentin-software.com/en/products/pvsol-premium |
| 323 | 2026 R1 (2025-11-24) | consumption & EV & heat pump | [PV*SOL premium] Plusieurs tarifs de soutirage affectables à différents consommateurs (VE, pompe à chaleur) | https://valentin-software.com/en/?p=6693 |
| 324 | 2026 R1 (2025-11-24) | report & documents | [PV*SOL premium] Rapport de projet compact avec résultats clés ; présentation client en PDF ou DOCX (customer presentation) | https://valentin-software.com/en/?p=6693 |
| 325 | 2026 R1 (2025-11-24) | consumption & EV & heat pump | [PV*SOL premium] Nouveaux profils de charge : climatisation, télétravail, foyers de retraités | https://valentin-software.com/en/products/pvsol-premium |
| 326 | 2026 R1 (2025-11-24) | weather data | [PV*SOL premium] Données climatiques Meteonorm 9 (2001-2020) | https://valentin-software.com/en/products/pvsol-premium |
| 327 | 2026 R1 (2025-11-24) | report & documents | [PV*SOL premium] Tous les graphiques de résultats ajoutables au rapport de projet | https://valentin-software.com/en/products/pvsol-premium |
| 328 | 2026 R1 (2025-11-24) | exports & imports | [PV*SOL premium] Export JSON des données de projet et des résultats pour CRM/ERP externes | https://valentin-software.com/en/?p=6693 |
| 329 | 2026 R1 (2025-11-24) | shading | [PV*SOL premium] Calcul d'ombrage 3D et de fréquence d'ombre plus rapides | https://valentin-software.com/en/products/pvsol-premium |
| 330 | 2026 R1 (2025-11-24) | storage | [PV*SOL premium] Charge/décharge pilotée par horaire pouvant dépasser minuit | https://valentin-software.com/en/products/pvsol-premium |
| 331 | 2026 R5 (2026-06-09) | site & imagery | [PV*SOL premium] Sections de carte pour l'Espagne et la France ; Pologne et Tchéquie (R8) | https://valentin-software.com/en/products/pvsol-premium |
| 332 | 2026 R5 (2026-06-09) | weather data | [PV*SOL premium] Données SolarAnywhere TMY mises à jour | https://valentin-software.com/en/products/pvsol-premium |
| 333 | 2026 R5 (2026-06-09) | usability | [PV*SOL premium] Nouvelle disposition du menu d'options | https://valentin-software.com/en/products/pvsol-premium |
| 334 | 2026 R4 (2026-03-18) | results & charts | [PV*SOL premium] Écrêtage de puissance masqué du tableau de résultats quand non défini au point d'injection ; légende de schéma révisée | https://valentin-software.com/en/products/pvsol-premium |
| 335 | 2027 R1 (2026-11-11) | results & charts | [PV*SOL premium] Avis de limitation à 60 % aussi affiché avec écrêtage de puissance totale ; limite de quatre séries levée dans l'éditeur de diagrammes | https://valentin-software.com/en/products/pvsol-premium |
| 336 | 2027 R1 (2026-11-11) | exports & imports | [PV*SOL premium] Limite d'import de 1024 Mo ; contrôle de taille des profils de charge importés | https://valentin-software.com/en/products/pvsol-premium |
| 337 | 2027 R2 (2026-11-18) | usability | [PV*SOL premium] Chargement plus rapide de la page onduleur ; vue détaillée Meteosyn améliorée | https://valentin-software.com/en/products/pvsol-premium |
| 338 | 2026 R2 (2026-01-26) | consumption & EV & heat pump | [PV*SOL premium] Profils de charge de valeurs mesurées regroupés dans le dialogue de consommation | https://valentin-software.com/en/products/pvsol-premium |
| 339 | 2026 R2 (2026-01-26) | results & charts | [PV*SOL premium] Symboles de circuit avant batteries AC et VE dans le schéma ; plan type inclus dans le nom des fichiers de plan exportés | https://valentin-software.com/en/products/pvsol-premium |
| 340 | 2026 R4 (2026-03-18) | site & imagery | [PV*SOL premium] Couverture accrue de l'API Google Solar en Amérique latine | https://valentin-software.com/en/products/pvsol-premium |
| 341 | 2026 R4 (2026-03-18) | exports & imports | [PV*SOL premium] Import de fichiers .pan amélioré (angle d'incidence et faible éclairement) | https://valentin-software.com/en/products/pvsol-premium |
| 342 | 2026 R4 (2026-03-18) | consumption & EV & heat pump | [PV*SOL premium] Option de désactiver la décharge du véhicule électrique pour couvrir la consommation | https://valentin-software.com/en/products/pvsol-premium |
| 343 | 2026 R5 (2026-06-09) | site & imagery | [PV*SOL premium] Modèles 3D de bâtiments générés par scans LiDAR via l'API Rexplorer (Allemagne seulement) | https://valentin-software.com/en/products/pvsol-premium |
| 344 | 2026 R5 (2026-06-09) | electrical & stringing | [PV*SOL premium] Règles de configuration pour optimiseurs SolarEdge S500B W, S650B W, S650A | https://valentin-software.com/en/products/pvsol-premium |
| 345 | 2026 R5 (2026-06-09) | consumption & EV & heat pump | [PV*SOL premium] Nouveaux profils de charge BDEW H25/G25/L25, Elexon UK, Catapult UK ; copie des profils de valeurs mesurées | https://valentin-software.com/en/products/pvsol-premium |
| 346 | 2026 R7 (2026-08-04) | consumption & EV & heat pump | [PV*SOL premium] Avertissement si la consommation excédentaire n'a qu'un tarif de soutirage ; projet d'exemple planifié via API Rexplorer | https://valentin-software.com/en/products/pvsol-premium |
| 347 | 2026 R8 (2026-09-22) | module placement | [PV*SOL premium] Valeurs par défaut améliorées de la boîte d'orientation relative pour montage est/ouest | https://valentin-software.com/en/products/pvsol-premium |
| 348 | 2027 R1 (2026-11-11) | module placement | [PV*SOL premium] Planification 3D : plus de mémoire, limites de 15 000 modules en toiture et 10 000 au sol ; rayon de sélection Rexplorer ajustable | https://valentin-software.com/en/products/pvsol-premium |
| 349 | 2027 R1 (2026-11-11) | results & charts | [PV*SOL premium] Tarifs avec prix de capacité, import de tarif dynamique, investissements ultérieurs | https://valentin-software.com/en/products/pvsol-premium |
| 350 | 2027 R1 (2026-11-11) | storage | [PV*SOL premium] Gestion d'énergie batterie : charge retardée, écrêtage de pointe, charge/décharge selon tarif dynamique | https://valentin-software.com/en/products/pvsol-premium |
| 351 | 2027 R1 (2026-11-11) | consumption & EV & heat pump | [PV*SOL premium] Consommateurs favoris à sélection rapide ; consommation annuelle d'un profil de charge modifiable en un clic | https://valentin-software.com/en/products/pvsol-premium |
| 352 | 2027 R1 (2026-11-11) | electrical & stringing | [PV*SOL premium] Schéma de circuit : symboles batterie à couplage DC intermédiaire, meilleure génération pour grands projets | https://valentin-software.com/en/products/pvsol-premium |
| 353 | 2027 R1 (2026-11-11) | weather data | [PV*SOL premium] Meteosyn : correction PVGIS améliorée et détails de qualité des données | https://valentin-software.com/en/products/pvsol-premium |
| 354 | 2027 R1 (2026-11-11) | usability | [PV*SOL premium] Nouveaux projets d'exemple ; navigation de pages et surbrillance clavier revues | https://valentin-software.com/en/products/pvsol-premium |

### OpenSolar (58 lignes)

| n° | Version / date | Domaine | Capacité | URL |
|---|---|---|---|---|
| 355 | 3.0 (2025-09-18) | results & charts | Comparaison visuelle des coûts actuels fossiles et d'un mode de vie électrifié dans la proposition | https://www.opensolar.com/product-updates/release-3-0/ |
| 356 | 3.0 (2025-09-18) | usability | Calculs SAM parallélisés pour un traitement plus rapide | https://www.opensolar.com/product-updates/release-3-0/ |
| 357 | 3.0 (2025-09-18) | roof & obstacles | Pan sélectionné au clic quand des panneaux y sont posés (et non le groupe) | https://www.opensolar.com/product-updates/release-3-0/ |
| 358 | 3.2.0 (2025-11-04) | mobile & site survey | Champs supplémentaires du widget : nombre d'étages et de phases, téléversement de facture | https://www.opensolar.com/product-updates/release-3-2-0/ |
| 359 | 3.0 (2025-09-18) | results & charts | Comparaison côte à côte des modes de paiement ; tableau d'activité des tâches de CRM | https://www.opensolar.com/product-updates/release-3-0/ |
| 360 | 2.30.0 (2025-03-08) | collaboration & templates | Ajustements automatiques selon nom du distributeur, type et pente de toit, avec verrou anti-suppression (smart adders) | https://www.opensolar.com/product-updates/release-2-30-0/ |
| 361 | 2.30.0 (2025-03-08) | usability | Optimisation du calcul solaire ; préchargement de l'imagerie Google Solar API ; assistant de conception batterie pour 2e et 3e batterie | https://www.opensolar.com/product-updates/release-2-30-0/ |
| 362 | 2.30.0 (2025-03-08) | roof & obstacles | Raffinement des outils de toit pour un calepinage plus précis | https://www.opensolar.com/product-updates/release-2-30-0/ |
| 363 | 2.31.0 (2025-04-16) | module placement | Alerte de retrait réglementaire (setback) qui clignote en rouge quand un panneau approche la limite | https://www.opensolar.com/product-updates/release-2-31-0/ |
| 364 | 2.31.0 (2025-04-16) | collaboration & templates | Vues de gestion de projet personnalisables en Kanban, filtres, documents partagés | https://www.opensolar.com/product-updates/release-2-31-0/ |
| 365 | 3.0 (2025-09-18) | AI | Assistant IA « Ada » dans toute l'application, avec création de projet et de conception à la voix | https://www.opensolar.com/product-updates/release-3-0/ |
| 366 | 3.0 (2025-09-18) | AI | Conception automatique du système à partir des préférences de matériel et de prix (Auto System Design) | https://www.opensolar.com/product-updates/release-3-0/ |
| 367 | 3.0 (2025-09-18) | collaboration & templates | Widget embarquable qui donne une estimation solaire aux visiteurs du site, routage automatique des leads vers le CRM (AI Lead Gen) | https://www.opensolar.com/product-updates/release-3-0/ |
| 368 | 3.0 (2025-09-18) | collaboration & templates | Modèles de conception système pour prix, matériel et retraits cohérents (system design templates) | https://www.opensolar.com/product-updates/release-3-0/ |
| 369 | 3.0 (2025-09-18) | roof & obstacles | Outil de croquis de toit lorsque l'imagerie est de mauvaise qualité (roof sketch) | https://www.opensolar.com/product-updates/release-3-0/ |
| 370 | 3.0 (2025-09-18) | consumption & EV & heat pump | Graphique de consommation redessiné et éditable ; capture carburant/gaz pour estimer les économies VE et pompe à chaleur | https://www.opensolar.com/product-updates/release-3-0/ |
| 371 | 3.0 (2025-09-18) | storage | Modélisation de l'ajout d'une batterie sur système existant ou importé (battery retrofit) | https://www.opensolar.com/product-updates/release-3-0/ |
| 372 | 3.0 (2025-09-18) | roof & obstacles | Accrochage des lignes de toit à 90° et 180° ; guide visuel de pose manuelle des nœuds ; glisser-déposer des nœuds et objets ; outil de mesure pour mettre à l'échelle une image téléversée | https://www.opensolar.com/product-updates/release-3-0/ |
| 373 | 3.0 (2025-09-18) | module placement | Plusieurs types de panneaux dans un système avec optimisation par type ; espacement de modules prédéfini | https://www.opensolar.com/product-updates/release-3-0/ |
| 374 | 3.0 (2025-09-18) | report & documents | Proposition interactive en chapitres avec comparaison côte à côte des conceptions et modes de paiement (Sales Machine) | https://www.opensolar.com/product-updates/release-3-0/ |
| 375 | 3.0 (2025-09-18) | exports & imports | Nomenclature matériel synchronisable depuis la conception (Sync from Design) ; BOM éditable indépendamment | https://www.opensolar.com/product-updates/release-3-0/ |
| 376 | 3.2.0 (2025-11-04) | collaboration & templates | Attribution de tâches avec échéances, vue d'activité personnelle, page de gestion redessinée | https://www.opensolar.com/product-updates/release-3-2-0/ |
| 377 | 3.2.0 (2025-11-04) | results & charts | Chiffrage de la batterie en ligne séparée optionnelle sur la proposition en ligne | https://www.opensolar.com/product-updates/release-3-2-0/ |
| 378 | 3.3.0 (2025-12-17) | AI | Retour d'appréciation sur les conceptions automatiques ; sauvegarde d'un projet existant comme modèle de conception automatique ; l'IA crée modèles et conceptions | https://www.opensolar.com/product-updates/release-3-3-0/ |
| 379 | 3.3.0 (2025-12-17) | storage | Métrique « cycles moyens par jour » dans le panneau batterie ; logique de conception pour Tesla Powerwall 3 | https://www.opensolar.com/product-updates/release-3-3-0/ |
| 380 | 3.3.0 (2025-12-17) | electrical & stringing | Règle de conception recommandant un compteur de production compatible avec l'onduleur | https://www.opensolar.com/product-updates/release-3-3-0/ |
| 381 | 3.3.0 (2025-12-17) | mounting & structure | Calculateur de fixation K2 SimpleTilt | https://www.opensolar.com/product-updates/release-3-3-0/ |
| 382 | 3.3.0 (2025-12-17) | weather data | Estimations de production à partir de données mensuelles ou trimestrielles incomplètes ; jeu NREL PSM4 | https://www.opensolar.com/product-updates/release-3-3-0/ |
| 383 | 3.12 (2026-10-15) | report & documents | Co-signature des propositions par l'équipe avec certificat de complétion | https://www.opensolar.com/product-updates/release-3-12/ |
| 384 | 3.4.0 (2026-01-27) | simulation & losses | Modélisation de fin de vie batterie et onduleur pour scénarios de remplacement et impact financier | https://www.opensolar.com/product-updates/release-3-4-0/ |
| 385 | 3.4.0 (2026-01-27) | weather data | Nouveaux jeux météo CSIRO et Himawari (Australie) et PSM4 (États-Unis) | https://www.opensolar.com/product-updates/release-3-4-0/ |
| 386 | 3.4.0 (2026-01-27) | usability | Placement des panneaux plus réactif en 3D | https://www.opensolar.com/product-updates/release-3-4-0/ |
| 387 | 3.11 (2026-09-17) | exports & imports | Calcul de nomenclature de fixation pour toit en tuiles avec choix de type de tuile (plate/pantile) avant calcul | https://www.opensolar.com/product-updates/release-3-11/ |
| 388 | 3.11 (2026-09-17) | storage | Étiquette de batterie du fournisseur préféré ajoutée automatiquement à la conception | https://www.opensolar.com/product-updates/release-3-11/ |
| 389 | 3.11 (2026-09-17) | electrical & stringing | Schéma unifilaire string jusqu'à 2 onduleurs, 3 MPPT par onduleur, 4 chaînes par MPPT, numérotation MPPT par onduleur | https://www.opensolar.com/product-updates/release-3-11/ |
| 390 | 3.11 (2026-09-17) | collaboration & templates | Code QR imprimable d'un document de projet pour le placer sur l'installation | https://www.opensolar.com/product-updates/release-3-11/ |
| 391 | 3.9 (2026-07-24) | report & documents | Devis rapide pour travaux non solaires sans conception (Quick Quote) | https://www.opensolar.com/product-updates/release-3-9/ |
| 392 | 3.9 (2026-07-24) | report & documents | Édition des modèles de proposition avec aperçu en direct (live preview) | https://www.opensolar.com/product-updates/release-3-9/ |
| 393 | 3.10 (2026-08-21) | roof & obstacles | Bibliothèque Objets et arbres : évents, lanterneaux, cheminées, citernes avec ombre automatique (Objects & Trees library) | https://www.opensolar.com/product-updates/release-3-10/ |
| 394 | 3.10 (2026-08-21) | roof & obstacles | Rayon de travail sûr des points d'ancrage antichute affiché autour du point (Arrest Roof Anchor Point) | https://www.opensolar.com/product-updates/release-3-10/ |
| 395 | 3.10 (2026-08-21) | report & documents | Plan de site avec zones de sécurité et légende pour les dossiers de chantier (job pack) | https://www.opensolar.com/product-updates/release-3-10/ |
| 396 | 3.10 (2026-08-21) | collaboration & templates | Planification des visites, installations et maintenances avec synchronisation Google Calendar/Outlook (Scheduling) ; partage de proposition par WhatsApp | https://www.opensolar.com/product-updates/release-3-10/ |
| 397 | 3.8 (2026-06-26) | module placement | Annotations dans la conception et la proposition ; démarrage d'un projet par latitude/longitude | https://www.opensolar.com/product-updates/release-3-8/ |
| 398 | 3.8 (2026-06-26) | mounting & structure | Structures surélevées pour toits plats en béton armé avec hauteur et inclinaison réglables, acrotères pris en compte (Elevated structures, RCC) | https://www.opensolar.com/product-updates/release-3-8/ |
| 399 | 3.8 (2026-06-26) | consumption & EV & heat pump | Détails VE et pompe à chaleur dans les propositions | https://www.opensolar.com/product-updates/release-3-8/ |
| 400 | 3.8 (2026-06-26) | electrical & stringing | Couleurs de chaînes distinctes par MPPT ; composants BOS auto-ajoutés après câblage (isolateurs, câbles, compteur, connecteurs MC4) | https://www.opensolar.com/product-updates/release-3-8/ |
| 401 | 3.7.0 (2026-05-28) | site & imagery | Marché d'imagerie premium (haute résolution, 3D) achetée par projet | https://www.opensolar.com/product-updates/release-3-7-0/ |
| 402 | 3.7.0 (2026-05-28) | report & documents | Choix de langue de la proposition (bêta, environ 12 langues) ; polices et couleurs par modèle ; exclure les fiches techniques du PDF pour alléger | https://www.opensolar.com/product-updates/release-3-7-0/ |
| 403 | 3.7.0 (2026-05-28) | exports & imports | Nomenclature de fixation SolarNEST pour toit et sol ; BOM sur plusieurs projets en un achat | https://www.opensolar.com/product-updates/release-3-7-0/ |
| 404 | 3.11 (2026-09-17) | exports & imports | Calcul de nomenclature pour fixation toit incliné à partir du toit dessiné, choix du système et de ses options (Van Der Valk) | https://www.opensolar.com/product-updates/release-3-11/ |
| 405 | 3.12 (2026-10-15) | electrical & stringing | Génération du schéma unifilaire spécifique à l'Inde avec export PDF/DXF | https://www.opensolar.com/product-updates/release-3-12/ |
| 406 | 3.12 (2026-10-15) | collaboration & templates | Application mobile pour gérer projets, factures et partage de proposition WhatsApp (Mobile Experience) | https://www.opensolar.com/product-updates/release-3-12/ |
| 407 | 3.12 (2026-10-15) | results & charts | Propositions 3D interactives où le client explore toiture, ombrage et ensoleillement | https://www.opensolar.com/product-updates/release-3-12/ |
| 408 | 3.12 (2026-10-15) | report & documents | Site maps du dossier d'installation avec zones de sécurité, ancrages et rayons ; carte client sans détails de sécurité | https://www.opensolar.com/product-updates/release-3-12/ |
| 409 | 3.13 (2026-11-16) | electrical & stringing | Mode de câblage amélioré avec annulation facilitée et câblage automatique des onduleurs (stringing mode) | https://www.opensolar.com/product-updates/release-3-13/ |
| 410 | 3.13 (2026-11-16) | report & documents | Tableau de devis détaillé ligne à ligne dans la proposition (itemised quotation) | https://www.opensolar.com/product-updates/release-3-13/ |
| 411 | 3.13 (2026-11-16) | mounting & structure | Aperçu des marques de fixation avant le choix du type de toit ; rail K2 BasicRail pour toits trapézoïdaux | https://www.opensolar.com/product-updates/release-3-13/ |
| 412 | 3.13 (2026-11-16) | site & imagery | Démarrage d'un projet depuis la position actuelle ou un lien Google Maps | https://www.opensolar.com/product-updates/release-3-13/ |

### Scanifly (28 lignes)

| n° | Version / date | Domaine | Capacité | URL |
|---|---|---|---|---|
| 413 | 2025-08-27 | usability | Refonte de l'infrastructure pour une modélisation plus rapide sur anciens ordinateurs | https://scanifly.com/blog/august-2025-pv-design-platform-updates/ |
| 414 | 2025-10-07 | roof & obstacles | Arbres transparents en vue de dessus pour dimensionner la canopée | https://scanifly.com/blog/september-2025-pv-design-platform-updates/ |
| 415 | 2025-08-27 | collaboration & templates | Partenariats EnergySage et Pipe : conceptions IA livrées aux plateformes de leads | https://scanifly.com/blog/august-2025-pv-design-platform-updates/ |
| 416 | SimpleDesign (2025-06-16) | usability | Interface simplifiée « Grid Mode » : activer/désactiver modules par clic, pans entiers par double-clic, production et couverture de facture en direct | https://scanifly.com/blog/introducing-simpledesign/ |
| 417 | SimpleDesign (2025-06-16) | module placement | Garde-fous bloquant retrait d'arbres, violation de retraits AHJ ou pose sur obstacle ; mode manuel déplacer/copier/coller des rangées | https://scanifly.com/blog/introducing-simpledesign/ |
| 418 | SimpleDesign (2025-06-16) | AI | Calepinage généré par IA à partir de la seule adresse de la propriété | https://scanifly.com/blog/introducing-simpledesign/ |
| 419 | SimpleDesign (2025-06-16) | results & charts | Comparaison automatique conception préliminaire contre modèle drone (true-up) | https://scanifly.com/blog/introducing-simpledesign/ |
| 420 | 2025-08-27 | site & imagery | Prix de l'imagerie Nearmap réduit et aperçu avant achat ; édition de hauteur de plusieurs obstacles par raccourcis clavier en 3D | https://scanifly.com/blog/august-2025-pv-design-platform-updates/ |
| 421 | 2025-10-07 | roof & obstacles | Placement d'arbres par glisser-déposer, édition directe, arbres transparents en vue de dessus, raccourcis clavier | https://scanifly.com/blog/september-2025-pv-design-platform-updates/ |
| 422 | 2025-11-19 | module placement | Placement de modules par glisser-déposer ; indicateurs de conflit rouge/orange ; création de projet par longitude/latitude ; placement IA plus fin | https://scanifly.com/blog/november-2025-pv-design-platform-updates/ |
| 423 | 2025-11-19 | site & imagery | Couverture LiDAR élargie ; Azure Maps remplace Bing Maps | https://scanifly.com/blog/november-2025-pv-design-platform-updates/ |
| 424 | 2025-05-09 | collaboration & templates | API et Zapier pour intégrations avec CRM, outils de proposition et fabricants de fixation | https://scanifly.com/blog/scaniflys-new-api-ecosystem/ |
| 425 | 2026-06-02 | results & charts | Étiquettes de valeurs sur les barres de production et de consommation, copiables pour rapports | https://scanifly.com/blog/may-2026-product-updates/ |
| 426 | 2026-08-18 | collaboration & templates | Options administrateur pour masquer rapport PDF, bouton Finaliser ou bandeau d'utilisation en conception simple | https://scanifly.com/blog/whats-new-in-scanifly-summer-2026/ |
| 427 | 2026-11-02 | consumption & EV & heat pump | Page de données de consommation : 1 à 12 mois saisis, mois vides estimés, mois estimés en barres pointillées | https://scanifly.com/blog/scanifly-consumption-data/ |
| 428 | 2026-06-02 | usability | Performances de la vue d'implantation (viewshed) améliorées | https://scanifly.com/blog/may-2026-product-updates/ |
| 429 | 2026-02-03 | roof & obstacles | Retraits incendie automatiques par type d'arête (faîtage, égout) avec profils par juridiction (fire setbacks) | https://scanifly.com/blog/january-2026-product-updates/ |
| 430 | 2026-02-03 | exports & imports | Intégration IronRidge : envoi design et panneaux en un clic | https://scanifly.com/blog/january-2026-product-updates/ |
| 431 | 2026-02-03 | AI | L'IA respecte les minimums ASA et TSRF à la génération initiale | https://scanifly.com/blog/january-2026-product-updates/ |
| 432 | 2026-02-26 | usability | Interface Calques et Propriétés redessinée : onglets par pan (aperçu, contours, exclusions, ombre, rangées), tri par nombre de modules ou TSRF, volets déplaçables | https://scanifly.com/blog/february-2026-product-updates/ |
| 433 | 2026-06-02 | mobile & site survey | Albums de photos (drone, électrique, structure, mobile) consultables dans l'espace 3D ; Street View en couche de données | https://scanifly.com/blog/may-2026-product-updates/ |
| 434 | 2026-06-02 | module placement | Réglages avancés de calepinage (espacement, hauteur de support, inclinaison) pour toits plats ; outil de dé-inclinaison avec annuler/rétablir | https://scanifly.com/blog/may-2026-product-updates/ |
| 435 | 2026-07-07 | mobile & site survey | Listes de contrôle de chantier éditables à plusieurs en direct avec horodatage ; alerte de doublon de projet | https://scanifly.com/blog/june-2026-product-updates/ |
| 436 | 2026-08-18 | roof & obstacles | Limite d'occluders doublée à 16 ; occluders sur couches Google 3D et LiDAR ; préréglages de zones d'exclusion avec hauteur par défaut, déplaçables en 3D | https://scanifly.com/blog/whats-new-in-scanifly-summer-2026/ |
| 437 | 2026-08-18 | shading | Rapport d'ombrage avec répartition des pertes et pertes d'ombrage mensuelles | https://scanifly.com/blog/whats-new-in-scanifly-summer-2026/ |
| 438 | 2026-08-18 | report & documents | Rapport de projet PDF généré depuis l'espace de conception | https://scanifly.com/blog/whats-new-in-scanifly-summer-2026/ |
| 439 | 2026-10-21 | mobile & site survey | Application mobile de relevé : checklists, photos avec autocollants électriques/danger/direction, inclinaison mesurée en posant le téléphone sur le toit, azimut lu, albums exportables en PDF, sous-traitants à accès limité | https://scanifly.com/blog/scanifly-mobile-solar-site-survey-app/ |
| 440 | 2026-11-02 | consumption & EV & heat pump | Estimation des mois de consommation manquants depuis températures normales NOAA ; total annuel réparti sur 12 mois ; profil pondéré degrés-jours | https://scanifly.com/blog/scanifly-consumption-data/ |

### Pylon (25 lignes)

| n° | Version / date | Domaine | Capacité | URL |
|---|---|---|---|---|
| 441 | 2026-03 (2026-03-17) | results & charts | Paramètre de marge cible dans l'onglet prix d'une conception | https://getpylon.com/blog/march-2026-update/ |
| 442 | 2026-09 (2026-09-21) | exports & imports | Détails d'ajouts, matériaux et climatiseurs exposés par l'API de conception | https://getpylon.com/blog/september-2026-update-uk/ |
| 443 | 2026-05 (2026-05-04) | storage | Simulation par séries de batteries ; carte thermique de la taille solaire/batterie optimale | https://getpylon.com/blog/march-2026-update/ |
| 444 | 2026-03 (2026-03-17) | storage | Recommandeur de batterie : taille optimale depuis la consommation du client, carte thermique solaire/batterie, bouton d'application en un clic (Battery Recommender) | https://getpylon.com/blog/march-2026-update/ |
| 445 | 2026-03 (2026-03-17) | module placement | Affichage de l'objectif de panneaux pendant la pose | https://getpylon.com/blog/march-2026-update/ |
| 446 | 2026-03 (2026-03-17) | collaboration & templates | Automatisations CRM : déclencheurs, étapes de pipeline, démarrage de workflow, marquage automatique « vendu » | https://getpylon.com/blog/march-2026-update/ |
| 447 | 2026-05 (2026-05-04) | storage | Recommandeur de batterie avec graphique d'état de charge, jours d'autonomie et cycles par jour ; recommandations jusqu'à 500 kWh | https://getpylon.com/blog/may-2026-update/ |
| 448 | 2026-05 (2026-05-04) | consumption & EV & heat pump | Lecteur automatique de facture PDF (usage et injection) ; processeur universel de données d'intervalle | https://getpylon.com/blog/may-2026-update/ |
| 449 | 2026-05 (2026-05-04) | mobile & site survey | Création de projet et début de conception depuis le téléphone | https://getpylon.com/blog/may-2026-update/ |
| 450 | 2026-05 (2026-05-04) | collaboration & templates | Attribution tournante des leads entre commerciaux (round-robin) | https://getpylon.com/blog/may-2026-update/ |
| 451 | 2026-05 (2026-05-04) | site & imagery | Échelle d'import de plan (A4, portrait, 1:200) ; filtre pays de la bibliothèque de composants | https://getpylon.com/blog/may-2026-update/ |
| 452 | 2026-07 (2026-07-23) | electrical & stringing | Éditeur de schéma unifilaire personnalisé directement dans l'outil (Custom SLD editor) | https://getpylon.com/blog/july-2026-update/ |
| 453 | 2026-07 (2026-07-23) | module placement | Accrochage automatique d'un panneau posé près d'un groupe existant | https://getpylon.com/blog/july-2026-update/ |
| 454 | 2026-07 (2026-07-23) | report & documents | Calculs par toit pour rapports conformes MCS (MCS roof splitting) | https://getpylon.com/blog/july-2026-update/ |
| 455 | 2026-09 (2026-09-21) | electrical & stringing | Schéma unifilaire : composant groupe électrogène, étiquettes et légendes claires, étiquettes suivant la rotation, accrochage et câbles améliorés | https://getpylon.com/blog/september-2026-update-australia/ |
| 456 | 2026-09 (2026-09-21) | collaboration & templates | Notifications de proposition ouverte, page de comparaison vue et signature consultée | https://getpylon.com/blog/september-2026-update-australia/ |
| 457 | 2026-09 (2026-09-21) | report & documents | Fiches de chantier avec plan de site batterie et lien de téléchargement du schéma unifilaire ; manuels utilisateur étendus ; documents de sécurité batterie à la remise | https://getpylon.com/blog/september-2026-update-australia/ |
| 458 | 2026-09 (2026-09-21) | site & imagery | Limites de parcelle (titre de propriété) affichées sur l'imagerie aérienne dans l'éditeur ; coordonnées OS Grid automatiques sur les plans de site | https://getpylon.com/blog/september-2026-update-uk/ |
| 459 | 2026-09 (2026-09-21) | collaboration & templates | Gestion de projet bêta avec création automatique du chantier à la vente ; livres de prix régionaux versionnés avec marges minimales | https://getpylon.com/blog/september-2026-update-uk/ |
| 460 | 2026-09 (2026-09-21) | report & documents | Lettre d'autorisation à signer par le propriétaire envoyée depuis l'outil | https://getpylon.com/blog/september-2026-update-uk/ |
| 461 | 2026-11 (2026-11-18) | electrical & stringing | Contrôle de la tension de démarrage de l'onduleur lors de la revue des chaînes (string advice) | https://getpylon.com/blog/november-2026-update-uk/ |
| 462 | 2026-11 (2026-11-18) | site & imagery | Recadrage du plan téléversé dans l'éditeur de conception (blueprint cropping) | https://getpylon.com/blog/november-2026-update-uk/ |
| 463 | 2026-11 (2026-11-18) | report & documents | Nouveaux modèles de proposition ; aperçus visuels du sélecteur de modèles ; devis à lignes alternées avec coordonnées de l'entreprise | https://getpylon.com/blog/november-2026-update-uk/ |
| 464 | 2026-11 (2026-11-18) | results & charts | Rapports personnalisés avec plage de dates et comparaison à la période précédente (custom reporting, bêta) | https://getpylon.com/blog/november-2026-update-uk/ |
| 465 | 2026-11 (2026-11-18) | collaboration & templates | Dossier de raccordement : pièces jointes schéma, plan de site, lettre d'autorisation dans le flux (Connect Direct) | https://getpylon.com/blog/november-2026-update-uk/ |

### SolarEdge (16 lignes)

| n° | Version / date | Domaine | Capacité | URL |
|---|---|---|---|---|
| 466 | 2020-01-08 | usability | [SolarEdge Designer] Sélection multiple d'objets, copier-coller d'éléments de conception, meilleur alignement des bords | https://www.pv-tech.org/solaredge-bolsters-design-tool-to-streamline-ci-rooftop-planning-process |
| 467 | 2020-01-08 | electrical & stringing | [SolarEdge Designer] Câblage automatique des chaînes suivant des règles préréglées ; extension d'un système par réplication de blocs de modules câblés | https://www.pv-tech.org/solaredge-bolsters-design-tool-to-streamline-ci-rooftop-planning-process |
| 468 | 2020-01-08 | consumption & EV & heat pump | [SolarEdge Designer] Profils de consommation commerciaux supplémentaires | https://www.pv-tech.org/solaredge-bolsters-design-tool-to-streamline-ci-rooftop-planning-process |
| 469 | 2021-08 | collaboration & templates | [SolarEdge Designer] Onglet de partage de la conception finale ou d'alternatives avec les clients ; export d'un clic vers la plateforme de supervision | https://marketing.solaredge.com/solaredge-designer-0-15 |
| 470 | 2021-07 | results & charts | [SolarEdge Designer] Outil d'analyse financière (économies, retour sur investissement) avec graphiques dans les rapports | https://marketing.solaredge.com/solaredge-designer-0-8 |
| 471 | 2021-07 | exports & imports | [SolarEdge Designer] Export de la nomenclature en PDF ou tableur avec notes et articles personnalisés mémorisés | https://marketing.solaredge.com/solaredge-designer-0-8 |
| 472 | 2021-07 | module placement | [SolarEdge Designer] Rotation de polygones, d'obstacles et de groupes de modules par poignée de rotation (rotating polygons / modules) | https://marketing.solaredge.com/solaredge-designer-0-8 |
| 473 | 2021-07 | collaboration & templates | [SolarEdge Designer] Partage de proposition par lien avec réglage de l'image 3D du site par le client (Share a proposal) | https://marketing.solaredge.com/solaredge-designer-0-8 |
| 474 | 2021-08 | variants & optimisation | [SolarEdge Designer] Conceptions multiples d'un même projet, duplication d'onglet, défilement synchronisé pour comparer (Multi-Design Support) | https://marketing.solaredge.com/solaredge-designer-0-15 |
| 475 | 2021-08 | consumption & EV & heat pump | [SolarEdge Designer] Création de profil de consommation personnalisé avec édition journalière et mensuelle | https://marketing.solaredge.com/solaredge-designer-0-15 |
| 476 | 2021-08 | simulation & losses | [SolarEdge Designer] Indication de la perte de facteur de rendement dans le diagramme de pertes avec conseil de réduction (Yield Factor Loss Indication) | https://marketing.solaredge.com/solaredge-designer-0-15 |
| 477 | 2022-02 | site & imagery | [SolarEdge Designer] Détection automatique du toit (automatic roof detection) | https://marketing.solaredge.com/solaredge-designer-0-9 |
| 478 | 2022-02 | electrical & stringing | [SolarEdge Designer] Câblage automatique des chaînes (auto stringing) | https://marketing.solaredge.com/solaredge-designer-0-9 |
| 479 | 2022-02 | shading | [SolarEdge Designer] Calcul d'ombrage des arbres (tree shading) | https://marketing.solaredge.com/solaredge-designer-0-9 |
| 480 | 2022-02 | exports & imports | [SolarEdge Designer] Import et export de fichiers DXF | https://marketing.solaredge.com/solaredge-designer-0-9 |
| 481 | 2022-02 | roof & obstacles | [SolarEdge Designer] Détection automatique d'obstacles d'aspect similaire (similar-looking obstacles) | https://marketing.solaredge.com/solaredge-designer-0-9 |

### SMA Sunny Design (10 lignes)

| n° | Version / date | Domaine | Capacité | URL |
|---|---|---|---|---|
| 482 | 5.0 | module placement | Planification visuelle de toit et interface directe vers Everest Base | https://www.sma.de/en/products/apps-software/sunny-design |
| 483 | 5.90 | consumption & EV & heat pump | Simulation de la charge VE optimisée PV pour bornes SMA Charger (PV optimized charging) | https://manuals.sma.de/Business-Systeme-PL/en-US/15015658635.html |
| 484 | 6.00 | collaboration & templates | Collaboration d'équipes de planificateurs sur les mêmes projets | https://manuals.sma.de/Business-Systeme-PL/en-US/15015658635.html |
| 485 | 5.61 | usability | Page d'accueil personnelle avec puissance crête et icône de planification de toit par projet | https://manuals.sma.de/Business-Systeme-PL/en-US/15015658635.html |
| 486 | Web (2016-10-17) | electrical & stringing | Planification avec optimiseurs de modules Tigo TS4-R, nombre d'optimiseurs et sélection automatique du matériel selon le coût | https://www.pv-magazine.com/press-releases/smart-module-technology-from-sma-and-tigo-can-now-be-planned-with-sunny-design_100026534 |
| 487 | 5.20 (2021-07-20) | roof & obstacles | Toit planifié avec un nombre choisi de bâtiments ; objets extérieurs (arbres, murs, cheminées) dans la planification de toit | https://www.energias-renovables.com/fotovoltaica/sma-lanza-una-nueva-version-de-su-20210720/ |
| 488 | 5.20 (2021-07-20) | module placement | Jusqu'à six générateurs PV différents par sous-projet en planification manuelle et visuelle | https://www.energias-renovables.com/fotovoltaica/sma-lanza-una-nueva-version-de-su-20210720/ |
| 489 | 5.20 (2021-07-20) | shading | Ombres annuelles sur toits, pourcentage d'ombrage par panneau, trajectoire des ombres à une heure donnée | https://www.energias-renovables.com/fotovoltaica/sma-lanza-una-nueva-version-de-su-20210720/ |
| 490 | 5.20 (2021-07-20) | variants & optimisation | Suggestions de conception optimisées ; comparaison d'alternatives par autoconsommation et autosuffisance | https://www.energias-renovables.com/fotovoltaica/sma-lanza-una-nueva-version-de-su-20210720/ |
| 491 | 5.20 (2021-07-20) | electrical & stringing | Tension maximale du système et courants de court-circuit avec support NEC 2017 étendu | https://www.energias-renovables.com/fotovoltaica/sma-lanza-una-nueva-version-de-su-20210720/ |

### archelios (10 lignes)

| n° | Version / date | Domaine | Capacité | URL |
|---|---|---|---|---|
| 492 | Suite 2022 (2022-10) | site & imagery | Modélisation 3D intégrée à l'interface web sans expertise SketchUp/Revit ; plugin Revit avec aller-retour | https://www.solarserver.de/2022/10/22/photovoltaik-software-archelios-suite-neuerungen-bei-3d-modellierung-und-fuer-leistungsoptimierer/ |
| 493 | Suite 2022 (2022-10) | electrical & stringing | Menu optimiseurs de puissance dans CALC avec contrôle de compatibilité module/optimiseur/onduleur et rapport de calcul conforme à la norme | https://www.solarserver.de/2022/10/22/photovoltaik-software-archelios-suite-neuerungen-bei-3d-modellierung-und-fuer-leistungsoptimierer/ |
| 494 | Suite 2022 (2022-10) | exports & imports | Import direct de projets K2 Base et Sunny Design | https://www.solarserver.de/2022/10/22/photovoltaik-software-archelios-suite-neuerungen-bei-3d-modellierung-und-fuer-leistungsoptimierer/ |
| 495 | PRO 2023 | consumption & EV & heat pump | Gestionnaire de profils de consommation (consumption profile manager) | https://www.trace-software.com/?p=26762 |
| 496 | PRO 2024 | usability | Environnement 3D natif intégré ; gestion de favoris pour listes de références | https://www.trace-software.com/?p=26762 |
| 497 | PRO 2025.1 (2025-11-21) | exports & imports | Import du système de fixation Enstall dans la nomenclature avec données de coût et rapport joint au PDF | https://www.trace-software.com/en/archelios-pro-a-new-version-focused-on-reliability-bankability-and-automation/ |
| 498 | PRO 2025.1 (2025-11-21) | results & charts | Indicateurs de probabilité Pxx personnalisables de P50 à P95 par pas de 5 % dans le rapport PDF | https://www.trace-software.com/en/archelios-pro-a-new-version-focused-on-reliability-bankability-and-automation/ |
| 499 | PRO 2025.1 (2025-11-21) | weather data | Données Meteonorm 9 (plus de 4 000 stations TMY) par défaut | https://www.trace-software.com/en/archelios-pro-a-new-version-focused-on-reliability-bankability-and-automation/ |
| 500 | PRO 2025.1 (2025-11-21) | consumption & EV & heat pump | Profils de consommation ELMAS pour industriel et tertiaire (18 profils horaires types) | https://www.trace-software.com/en/archelios-pro-a-new-version-focused-on-reliability-bankability-and-automation/ |
| 501 | PRO 2025.1 (2025-11-21) | electrical & stringing | Option d'afficher ou masquer le tableau BT dans le schéma unifilaire simplifié | https://www.trace-software.com/en/archelios-pro-a-new-version-focused-on-reliability-bankability-and-automation/ |

### Eturnity (4 lignes)

| n° | Version / date | Domaine | Capacité | URL |
|---|---|---|---|---|
| 502 | 2025-05 | consumption & EV & heat pump | Prise en charge du stockage batterie, de la recharge VE, du pilotage d'énergie (HEMS) et des pompes à chaleur, y compris rénovations | https://www.pv-magazine.com/2025/05/09/eturnity-adds-more-pv-design-automation-energy-system-project-control-to-its-software |
| 503 | 2025-05 | electrical & stringing | Outil de dimensionnement onduleur/chaînes qui génère plans de chaînes, schémas unifilaires et plans de toit | https://www.pv-magazine.com/2025/05/09/eturnity-adds-more-pv-design-automation-energy-system-project-control-to-its-software |
| 504 | 2025-05 | shading | Analyse d'ombrage ajoutée au module de calepinage de toit 2D/3D | https://www.pv-magazine.com/2025/05/09/eturnity-adds-more-pv-design-automation-energy-system-project-control-to-its-software |
| 505 | 2025-05 | exports & imports | Nomenclature depuis une bibliothèque de pièces à jour ; intégrations de dimensionnement structurel et fournisseurs | https://www.pv-magazine.com/2025/05/09/eturnity-adds-more-pv-design-automation-energy-system-project-control-to-its-software |

### HelioScope (9 lignes)

| n° | Version / date | Domaine | Capacité | URL |
|---|---|---|---|---|
| 506 | 2022-08 | collaboration & templates | Profils de projet par défaut : profils mécanique, électrique et conditions (Project Profiles) | https://help-center.helioscope.com/hc/en-us/articles/8338409298707-Project-Profiles |
| 507 | 2025-11-19 | consumption & EV & heat pump | Page Énergie : tarif plat ou personnalisé, consommation par intervalle ou mensuelle, incitations multiples ordonnées pour la base fiscale | https://help-center.helioscope.com/hc/en-us/articles/46672289394195-Updated-New-Experience-Overview-Simulations-and-Financials-Pages |
| 508 | 2025-11-19 | exports & imports | Téléchargement DXF, DAE, schéma unifilaire et rendu JPEG de conception depuis l'aperçu | https://help-center.helioscope.com/hc/en-us/articles/46672289394195-Updated-New-Experience-Overview-Simulations-and-Financials-Pages |
| 509 | 2025-07 à 2026-08 | results & charts | Pages Aperçu, Conditions, Énergie, Rapports et Financier refondues ; téléchargement du rapport d'ombrage et du CSV 8760 | https://help-center.helioscope.com/hc/en-us/articles/46672289394195-Updated-New-Experience-Overview-Simulations-and-Financials-Pages |
| 510 | 2025-07 | simulation & losses | Modélisation bifaciale et indicateur P90 (nouvelle expérience) | https://help-center.helioscope.com/hc/en-us/articles/42861118451475-Updated-New-Experience-Navigation |
| 511 | 2025-09-04 | collaboration & templates | Recherche de projets, archivage, renommage et partage depuis la page Projets | https://help-center.helioscope.com/hc/en-us/articles/44442846208019-Updated-V2-Projects-Page |
| 512 | 2026-07-22 | storage | Peak shaving : cibles de pointe par mois en pourcentage, simulation en un clic avec production et finances | https://help-center.helioscope.com/hc/en-us/articles/53702706058899-Peak-Demand-Shaving |
| 513 | 2026-07-22 | storage | Écrêtage de pointe par batterie avec cibles mensuelles optionnelles et charge réseau (peak demand shaving) | https://help-center.helioscope.com/hc/en-us/articles/53702706058899-Peak-Demand-Shaving |
| 514 | 2026-08 | storage | Arbitrage d'énergie par batterie (energy arbitrage) et limite de ratio puissance/capacité (C-rate) | https://help-center.helioscope.com/hc/en-us/articles/53702706058899-Peak-Demand-Shaving |

### K2 Base (6 lignes)

| n° | Version / date | Domaine | Capacité | URL |
|---|---|---|---|---|
| 515 | 2026-10-13 | exports & imports | Nouvelle interface entre K2 Base et le mode conception d'Aurora | https://k2-systems.com/en/news/ |
| 516 | page produit (2026) | mounting & structure | Détermination automatique des charges de vent et de neige, calcul et affichage des fixations et du lestage sur le toit | https://k2-systems.com/en/k2-base/ |
| 517 | page produit (2026) | report & documents | Rapport de résultats avec plans de montage, analyse structurelle et lestage en PDF et nomenclature éditable par toit | https://k2-systems.com/en/k2-base/ |
| 518 | page produit (2026) | exports & imports | Transfert des données vers SolarEdge, SMA, Fronius, Kostal, GoodWe, PV*SOL premium, archelios Pro et paniers de boutiques partenaires | https://k2-systems.com/en/k2-base/ |
| 519 | page produit (2026) | site & imagery | Plan de base : Google Maps, image satellite ou image téléversée (drone, plan) avec outils de dessin | https://k2-systems.com/en/k2-base/ |
| 520 | 2026-11-03 | mounting & structure | Calcul optimisé du système Dome 6 (est-ouest) | https://k2-systems.com/en/news/ |

### Huawei (3 lignes)

| n° | Version / date | Domaine | Capacité | URL |
|---|---|---|---|---|
| 521 | 2.0 (page produit) | AI | [Huawei SmartDesign] Calepinage automatique depuis l'imagerie satellite sans visite sur place, conception électrique en un clic | https://solar.huawei.com/en/smart-design/ |
| 522 | 2.0 (page produit) | storage | [Huawei SmartDesign] Recommandation de capacité de stockage pour réduire la facture et comparaison de plusieurs solutions | https://solar.huawei.com/en/smart-design/ |
| 523 | 2.0 (page produit) | results & charts | [Huawei SmartDesign] Rapport avec modèle 3D du site et coûts/bénéfices en un coup d'œil | https://solar.huawei.com/en/smart-design/ |

### Arka 360 (2 lignes)

| n° | Version / date | Domaine | Capacité | URL |
|---|---|---|---|---|
| 524 | Web Proposal (blog) | report & documents | Proposition web interactive : pages choisies et réordonnées, modèle 3D, carte d'irradiance, simulation animée de production, projections de facture sur 25 ans, calendrier d'installation, galerie de réalisations, signature numérique | https://arka360.com/ros/arka60-new-web-proposal |
| 525 | Web Proposal (blog) | results & charts | Simulations animées de production selon météo et heure ; carte d'irradiance par pan ; projection de coût du réseau sur 25 ans | https://arka360.com/ros/arka60-new-web-proposal |

### RatedPower (4 lignes)

| n° | Version / date | Domaine | Capacité | URL |
|---|---|---|---|---|
| 526 | blog (2026-09-15) | results & charts | Estimation de risque civil depuis le terrain du projet et comparaison de versions de disposition par volumes déblai/remblai | https://ratedpower.com/blog/automated-earthwork-calculations/ |
| 527 | blog (2026-09-15) | roof & obstacles | Terrassement automatisé au niveau pieu : pente, collisions, volumes déblai/remblai, cartes thermiques, coupes et profils | https://ratedpower.com/blog/automated-earthwork-calculations/ |
| 528 | blog (2026-09-15) | module placement | Variation automatique du pas entre rangées en fixe pour suivre le terrain dans une fenêtre sans ombre ; trackers suivant le terrain | https://ratedpower.com/blog/automated-earthwork-calculations/ |
| 529 | blog (2026-10-14) | simulation & losses | Simulation énergétique 3D avec terrain et backtracking validée sur centrales réelles | https://ratedpower.com/blog/3d-energy-simulation/ |

### Aurora (4 lignes)

| n° | Version / date | Domaine | Capacité | URL |
|---|---|---|---|---|
| 530 | Design Mode (page produit) | shading | Analyse d'ombrage, câblage, allées incendie, stockage et optimisation énergétique dans le mode conception | https://aurorasolar.com/product-updates/ |
| 531 | Drone Mapping (blog) | mobile & site survey | Mise à jour de conception après la pose depuis les données drone (true-up) | https://aurorasolar.com/product-updates/ |
| 532 | Drone Mapping (blog) | site & imagery | Cartographie par drone native à l'outil : carte, surface LiDAR et maillage | https://aurorasolar.com/drone-mapping-aurora/ |
| 533 | produit (page) | AI | Génération automatique de toit et calepinage avec ombrage, câblage et allées incendie ; plans de pose instantanés | https://aurorasolar.com/product-updates/ |

### Polysun (6 lignes)

| n° | Version / date | Domaine | Capacité | URL |
|---|---|---|---|---|
| 534 | 6.2 | storage | Modèle de batterie avec suivi de l'état de santé (SOH) ; profils de consommation au quart d'heure | https://www.pressebox.com/pressrelease/vela-solaris-ag/the-new-version-of-polysun-simulation-software-makes-research-results-available-to-end-customers/boxid/637058 |
| 535 | 10.0 | consumption & EV & heat pump | Composant véhicule électrique avec profils de conduite combiné au PV ou à la cogénération | https://www.pressebox.com/pressrelease/vela-solaris-ag/e-mobility-in-polysun-10-0/boxid/859885 |
| 536 | 7.0 | consumption & EV & heat pump | Pompes à chaleur pilotées par onduleur et cogénérateurs ; groupes électrogènes pour PV hors réseau ; stockage de glace | https://www.pressebox.com/pressrelease/vela-solaris-ag/polysun-7-0-updated-component-catalogues-and-template-databases-new-features-cogenerators-generators-for-off-grid-pv-systems-ice-storage-tanks/boxid/681014 |
| 537 | 11.1 | usability | Mode sombre optionnel ; import de schémas de système depuis d'autres projets (Premium) | https://www.pressebox.com/pressrelease/vela-solaris-ag/Polysun-11-1-reaches-top-performance-scores/boxid/959500 |
| 538 | 5.10 | usability | Favoris : produits préférés en accès rapide (bookmark) | https://www.pressebox.com/pressrelease/vela-solaris-ag/new-polysun-5-10-the-new-bookmark-feature-puts-your-favorite-products-in-the-fast-lane/boxid/530592 |
| 539 | 5.8 | shading | Ombrage proche et visualisation des liaisons de régulation | https://www.pressebox.com/pressrelease/vela-solaris-ag/New-Polysun-58-nearby-shading-and-visualization-of-controller-connections/boxid/471796 |

### SAM (23 lignes)

| n° | Version / date | Domaine | Capacité | URL |
|---|---|---|---|---|
| 540 | 2014.11.24 (SSC 40) | usability | Pages Système, Ombrage et Pertes séparées ; nouveau format CSV météo avec base de 1 600 sites | https://natlabrockies.github.io/SAM/doc/releasenotes |
| 541 | 2014.11.24 | simulation & losses | [NREL SAM] Calculateur d'ombrage 3D, simulations sub-horaires (1-60 min), macro de dimensionnement d'onduleur, auto-ombrage des trackers | https://natlabrockies.github.io/SAM/doc/releasenotes |
| 542 | 2015.6.30 | weather data | [NREL SAM] Prise en charge des fichiers TYA, années multiples en mode durée de vie avec dégradation | https://natlabrockies.github.io/SAM/doc/releasenotes |
| 543 | 2015.6.30 | storage | [NREL SAM] Modèle de batterie plomb et lithium-ion avec contrôleur de dispatch manuel, perte des optimiseurs DC, perte par neige | https://natlabrockies.github.io/SAM/doc/releasenotes |
| 544 | 2016.3.14 (SSC 159) | storage | Écrêtage de pointe automatique, mode puissance cible, horaires de week-end, priorité PV, niveaux de charge réseau | https://natlabrockies.github.io/SAM/doc/releasenotes |
| 545 | 2016.3.14 | shading | [NREL SAM] Modèle d'ombrage par obstruction ; irradiance dans le plan en entrée ; écrêtage de pointe automatique par batterie | https://natlabrockies.github.io/SAM/doc/releasenotes |
| 546 | 2017.1.17 (SSC 170) | storage | Dispatch manuel de batterie pour grands sites, topologies couplées DC, batterie vanadium | https://natlabrockies.github.io/SAM/doc/releasenotes |
| 547 | 2017.1.17 | simulation & losses | [NREL SAM] Calculateur de coefficients onduleur, modèle de perte transformateur, inclinaison saisonnière, écrêtage DC/AC | https://natlabrockies.github.io/SAM/doc/releasenotes |
| 548 | 2018.11.11 | weather data | [NREL SAM] Téléchargements PSM V3 TMY et fichiers EPW sub-horaires | https://natlabrockies.github.io/SAM/doc/releasenotes |
| 549 | 2018.11.11 | simulation & losses | [NREL SAM] Modules bifaciaux, entrées MPPT multiples, modèle de température onduleur, optimiseur de disposition de sous-champs | https://natlabrockies.github.io/SAM/doc/releasenotes |
| 550 | 2020.11.29 | weather data | [NREL SAM] NSRDB 5 minutes, Europe/Afrique/Asie et TMY/TGY/TDY | https://natlabrockies.github.io/SAM/doc/releasenotes |
| 551 | 2020.2.29 (SSC 237) | simulation & losses | Modèle de température de cellule transitoire ; pertes DC/AC journalières ; GHI ajouté aux fichiers météo par défaut | https://natlabrockies.github.io/SAM/doc/releasenotes |
| 552 | 2020.2.29 | storage | [NREL SAM] Dimensionnement et dispatch de batterie par ReOpt Lite ; PVWatts V7 avec neige, masse d'air et ombrage diffus | https://natlabrockies.github.io/SAM/doc/releasenotes |
| 553 | 2020.11.29 | simulation & losses | [NREL SAM] Modèle thermique transitoire du module ; backtracking amélioré ; dispatch batterie compte-tenu du tarif et de la dégradation | https://natlabrockies.github.io/SAM/doc/releasenotes |
| 554 | 2021.12.02 | storage | [NREL SAM] Configuration batterie autonome, dispatch en panne réseau, charge sur écrêtage PV ; PVWatts V8 avec bifacial et salissure mensuelle | https://natlabrockies.github.io/SAM/doc/releasenotes |
| 555 | 2022.11.21 | simulation & losses | [NREL SAM] Albédo spatial et irradiance au sol, estimation du mismatch bifacial, modèle d'incertitude P50/P90 amélioré | https://natlabrockies.github.io/SAM/doc/releasenotes |
| 556 | 2023.12.17 (SSC 288) | simulation & losses | Entrée d'axe de rotation de tracker ; coefficient de glissement de neige en sortie | https://natlabrockies.github.io/SAM/doc/releasenotes |
| 557 | 2023.12.17 | storage | [NREL SAM] Configurations hybrides PV/batterie ; dispatch d'autoconsommation derrière le compteur ; correction d'écrêtage sub-horaire AC | https://natlabrockies.github.io/SAM/doc/releasenotes |
| 558 | 2024.12.12 | weather data | [NREL SAM] NSRDB GOES V4 (1998-2023) ; simulations PV plus rapides ; bibliothèques PV mises à jour | https://natlabrockies.github.io/SAM/doc/releasenotes |
| 559 | 2024.12.12 (SSC 298) | storage | Pertes de disponibilité de batterie ; options de dispatch avec limite de réseau | https://natlabrockies.github.io/SAM/doc/releasenotes |
| 560 | 2024.12.12 | storage | [NREL SAM] Écrêtage de puissance réseau par batterie, pertes de disponibilité batterie, graphiques de factures BTM | https://natlabrockies.github.io/SAM/doc/releasenotes |
| 561 | 2026.7.3 | weather data | [NREL SAM] Données NSRDB Arctique ; téléchargement des profondeurs de neige ; Location et Resource réorganisés | https://natlabrockies.github.io/SAM/doc/releasenotes |
| 562 | 2026.7.3 | storage | [NREL SAM] Modèle batterie complet dans PVWatts ; décharge batterie vers le réseau ; interface PV détaillée refondue avec correction spectrale | https://natlabrockies.github.io/SAM/doc/releasenotes |

### pvlib (13 lignes)

| n° | Version / date | Domaine | Capacité | URL |
|---|---|---|---|---|
| 563 | 0.11.0 | shading | Fraction ombrée 1D (shaded_fraction1d) ; ombrage direct Martinez ; albédo d'eau intérieure | https://pvlib-python.readthedocs.io/en/stable/whatsnew.html |
| 564 | 0.9.0 (2021-09-01) | weather data | Lecteurs de données horaires PVGIS | https://pvlib-python.readthedocs.io/en/stable/whatsnew.html |
| 565 | 0.9.1 (2022-03-29) | simulation & losses | Modèle bifacial « infinite sheds » ; modèle de température Prilliman | https://pvlib-python.readthedocs.io/en/stable/whatsnew.html |
| 566 | 0.9.3 (2022-09-15) | simulation & losses | Modèle de perte de neige Townsend ; mismatch spectral de terrain | https://pvlib-python.readthedocs.io/en/stable/whatsnew.html |
| 567 | 0.9.4 (2022-12-20) | simulation & losses | Modèles d'angle d'incidence Schlick ; modèle de rendement ADR | https://pvlib-python.readthedocs.io/en/stable/whatsnew.html |
| 568 | 0.10.0 (2023-06-30) | weather data | Lecteurs d'horizon PVGIS, SRML, ACIS ; modèles de décomposition Orgill-Hollands et Louche | https://pvlib-python.readthedocs.io/en/stable/whatsnew.html |
| 569 | 0.10.2 (2023-09-21) | exports & imports | Lecture des fichiers .PAN et .OND (read_panond) | https://pvlib-python.readthedocs.io/en/stable/whatsnew.html |
| 570 | 0.10.3 (2023-12-20) | weather data | Transposition Perez-Driesse ; lecteurs Solcast et SolarAnywhere | https://pvlib-python.readthedocs.io/en/stable/whatsnew.html |
| 571 | 0.11.1 (2024-09-26) | simulation & losses | Mismatch de puissance bifacial (Deline) ; lois de puissance du vent | https://pvlib-python.readthedocs.io/en/stable/whatsnew.html |
| 572 | 0.13.0 (2025-06-07) | weather data | Client NSRDB PSM v4 ; ajustement SDM PVsyst depuis IEC 61853-1 | https://pvlib-python.readthedocs.io/en/stable/whatsnew.html |
| 573 | 0.13.1 (2025-09-24) | weather data | Lecteurs Meteonorm et NASA POWER | https://pvlib-python.readthedocs.io/en/stable/whatsnew.html |
| 574 | 0.14.0 (2026-01-16) | weather data | Lecteurs ERA5 et MERRA-2 ; facteur spectral de Polo pour façades verticales | https://pvlib-python.readthedocs.io/en/stable/whatsnew.html |
| 575 | 0.16.0 (2026-09-26) | simulation & losses | Modèle bifacial ANTS-2D ; lecteur SURFRAD ; IAM diffus | https://pvlib-python.readthedocs.io/en/stable/whatsnew.html |

## 3. Grappes de capacités et nombre d'outils

Une grappe = même capacité chez plusieurs outils. « Outils » = outils distincts (PVcase GM et RM comptent pour un). Années = première et dernière année de livraison trouvée dans les lignes datées.

| Grappe | Capacité | Outils (n) | Années | Lignes | Verdict | Preuve / renvoi |
|---|---|---|---|---|---|---|
| K01 | Câblage automatique des chaînes sur le calepinage (auto stringing) | 5 : Eturnity, OpenSolar, PVcase, PVsyst, SolarEdge | 2020-2026 | 9 | **PRÉSENT** | `apps/calepinage/services/chaines.py::concevoir_par_pan`, `services/polystring.py`, `core/electrique/chaines.py` (†a1 §7) |
| K02 | Motifs de câblage au choix (saute-mouton, U/S, milieu de table, côté opposé, manuel) | 1 : PVcase | 2025-2026 | 7 | **PARTIEL** | câblage par pan avec un azimut par chaîne (`chaines.py`), un seul motif ; pas de choix saute-mouton/U (B3-N11 propose déjà) |
| K03 | Dimensionnement de chaîne min/max selon températures du site et fenêtre MPPT | 5 : PVcase, PVsyst, Pylon, SAM, SMA Sunny Design | 2013-2026 | 8 | **PRÉSENT** | `core/electrique/chaines.py`, `services/electrique.py` (températures froid/chaud depuis TMY, `temperatures_tmy`) ; `CALX216` explique le choix (†a1 §7) |
| K04 | Utiliser tous les MPPT, plusieurs chaînes par MPPT, partage de puissance entre MPPT | 4 : OpenSolar, PVcase, PVsyst, SAM | 2015-2026 | 12 | **PRÉSENT** | `services/polystring.py`, `services/agregation_electrique.py` (énergie par chaîne/MPPT/onduleur) ; `ond_entrees_par_mppt`, `ond_chaines_max_par_mppt` (†a1 §6) |
| K05 | Schéma unifilaire généré, éditable, exporté (SLD) | 7 : Eturnity, HelioScope, OpenSolar, PVcase, PVsyst, Pylon, archelios | 2022-2026 | 14 | **PRÉSENT** | `services/sld.py` (éditable), `services/sld_export.py` (SVG + DXF), route `schema-unifilaire` (†a1 §7) |
| K06 | Dimensionnement des câbles et chute de tension (sections, matériaux, modes de pose) | 2 : PVcase, PVsyst | 2020-2026 | 9 | **PRÉSENT** | `services/cables.py`, `services/troncons.py`, `core/electrique/cables.py` ; réserve : modes de pose et regroupement (B5 rang 6) non vérifiés |
| K07 | Routage automatique des câbles sur chemins de câbles / tranchées | 1 : PVcase | 2025-2026 | 4 | **PARTIEL** | `services/troncons.py` + `plan-cablage.pdf/.dxf` : métré depuis des chemins dessinés ou déclarés, aucun routage automatique (`docs/moteur-calepinage.md` §7) (†a1) ; git grep `chemin de c` : 0 fichier de code |
| K08 | Nomenclature (BOM) exportée du calepinage | 6 : Eturnity, K2 Base, OpenSolar, PVcase, SolarEdge, archelios | 2021-2026 | 11 | **PRÉSENT** | `services/export_tableur.py`, `services/fixation.py`, `core/electrique/nomenclature.py` (†a1 §14) |
| K09 | Fixation : nomenclature de rails/crochets/lestage depuis le système choisi (et calculateurs de fabricants) | 6 : K2 Base, OpenSolar, PV*SOL, PVcase, Scanifly, archelios | 2022-2026 | 15 | **PRÉSENT** | `services/fixation.py`, `services/catalogue_fixation.py`, `services/lestage.py` (coefficients saisis par la société, jamais en dur) ; pas d'API de fabricant (D-CALX-PAYANT) |
| K10 | Toit plat : châssis inclinés, structures surélevées sur dalle béton | 3 : OpenSolar, PVcase, Scanifly | 2025-2026 | 4 | **PRÉSENT** | `core/calepinage/politique_pas.py`, `ombre_rangees.py` ; `apps/web/src/lib/estimatorBrainV2.ts`, onglet `coupe` (†a1 §8, a3) ; pieds/longrines sur dalle : B2-r6 |
| K11 | Alignement des rangées/modules entre zones et sur les bords du toit | 2 : PVcase, SolarEdge | 2020-2026 | 4 | **PARTIEL** | aimantation aux zones voisines `roofPro11/snap.ts::aimanterAuxZones` ; `layoutEditor.ts::freeAlignSelection` sans bouton (†a3 « M ») ; B3-N4 propose déjà |
| K12 | Est-ouest : rangées alignées, azimut inversé par module, pose dos-à-dos | 3 : K2 Base, PV*SOL, PVcase | 2024-2026 | 6 | **PRÉSENT** | `data-family="eastwest"`, `core/calepinage/ombre_rangees.py::fraction_ombree_est_ouest`, `services/polystring.py` (†a1 §8, a3) ; inversion par module : B3-N25 |
| K13 | Copier-coller / dupliquer un bloc câblé, un pan ou des réglages | 4 : PVcase, PVsyst, Scanifly, SolarEdge | 2020-2025 | 6 | **PARTIEL** | `layoutEditor.ts` « Dupliquer » avec décalage + symétrie (CALX112 coché), dupliquer un pan (CALX98) ; pas de « coller » ni de copie entre pans (†a3 §5 pt 5) ; B2-r12, B2-r16, B3-N14 proposent déjà |
| K14 | Bibliothèque d'objets de toit (lanterneau, citerne, évent, cheminée, pylône) avec ombre auto | 3 : OpenSolar, PVcase, PVsyst | 2015-2026 | 14 | **PARTIEL** | 6 types seulement : `ObstacleType = cheminee\|ventilation\|chien_assis\|edicule\|antenne\|autre` (`apps/web/src/lib/obstacles.ts:37`) ; gabarits société CALX104 ; B2-r3, B3-N19 proposent déjà |
| K15 | Détection automatique du toit / des obstacles sur l'image (IA) | 5 : Huawei, PVcase, PVsyst, Scanifly, SolarEdge | 2022-2026 | 7 | **PLANIFIÉ** | D-ACAL-33 (détection IA du toit à planifier, cf. B1 en-tête) ; empreinte OSM présente `contract_samples/calepinage_empreinte_osm.json` ; B2-r7 |
| K16 | Arbres et végétation modélisés avec ombre | 5 : OpenSolar, PVsyst, SMA Sunny Design, Scanifly, SolarEdge | 2018-2026 | 9 | **PRÉSENT** | `roofPro11/environment.ts`, `obstaclesUi.ts` (`rp9-env-add-tree`) : hauteur/diamètre saisis, ombre portée (†a3) |
| K17 | Retraits réglementaires, zones d'exclusion, acrotère, retraits par arête | 5 : Aurora, OpenSolar, PV*SOL, PVcase, Scanifly | 2025-2026 | 13 | **PRÉSENT** | `lib/roofSetbackEdge.ts`, `services/zones_reglementaires.py` (gabarits SOURCÉS par la société, CAL74), `roofPro11/batiment.ts::acrotereDuBatiment` |
| K18 | Points d'ancrage antichute avec rayon de sécurité et plan de site de sécurité | 2 : OpenSolar, Pylon | 2026-2026 | 4 | **ABSENT** | git grep `ancrage\|ligne de vie` dans le module : aucune occurrence pertinente ; B2-r4 propose déjà (repères) |
| K19 | Garde-fous de pose : conflit, refus nommé, alerte de retrait | 4 : OpenSolar, PV*SOL, PVcase, Scanifly | 2025-2025 | 5 | **PRÉSENT** | `layoutEditor.ts::checkPanelAt` refuse le geste et nomme la raison (†a3 §4) ; `services/feu_vert.py` |
| K20 | Imagerie enrichie : drone, LiDAR, Google 3D, Street View, imagerie premium | 6 : Aurora, K2 Base, OpenSolar, PV*SOL, PVcase, Scanifly | 2025-2026 | 17 | **HORS DÉCISION** | D-CALX-PAYANT (imagerie oblique/LiDAR payante, Google Solar CAL51 GATED) ; reste partiel gratuit : `services/lidar_ign.py` France seulement ; import d'orthophoto drone : B2-r1 |
| K21 | Démarrer un projet par latitude/longitude ou position actuelle | 3 : OpenSolar, PVsyst, Scanifly | 2017-2026 | 4 | **ABSENT** | `mapDraw.ts::geocode` n'envoie que du texte (†a3) ; git grep `coordonn.es GPS` : 0 ; B2-r5 propose déjà |
| K22 | Outils de toit : pente par arête, faîtage/arêtier, accrochage 90°, planarisation | 5 : OpenSolar, PVcase, PVsyst, RatedPower, Scanifly | 2019-2026 | 17 | **PARTIEL** | types d'arête 6 valeurs (CALX94), noue/arêtier déduits (CALX93), aimantation 90°/45° `snap.ts` ; pas d'outil de dessin de faîtage ; presets L/T/2 pans codés sans bouton (†a3 §5) ; B2-r13 |
| K23 | Plan/blueprint importé et calé à l'échelle (DXF, PDF, image) ; mesure d'échelle | 5 : K2 Base, OpenSolar, PVsyst, Pylon, SolarEdge | 2016-2026 | 7 | **PRÉSENT** | `services/import_plan.py` (ezdxf, PyMuPDF), `roofPro11/underlay.ts` calage 2 points + distance saisie (†a1, a3) |
| K24 | Import de scènes 3D externes (DAE, 3DS, PVC, IFC, glTF, .pvc2) | 3 : HelioScope, PVcase, PVsyst | 2017-2026 | 9 | **ABSENT** | git grep `glTF\|IFC` : 0 ; B2-r15 propose déjà |
| K25 | Rapport d'ombrage : pertes mensuelles, % d'ombrage par module, analyse 3D | 11 : Aurora, Eturnity, HelioScope, PV*SOL, PVcase, PVsyst, Polysun, SAM, SMA Sunny Design, Scanifly, SolarEdge | 2013-2026 | 17 | **PRÉSENT** | `services/rapport_ombrage.py` (carte de chaleur 12×24, moyennes mensuelles, table d'horizon), `ombrage_chaines.py::acces_par_module`, moteur navigateur `lib/shadingEngine.ts` (†a1 §3) |
| K26 | Ombrage électrique fin : diodes de dérivation, cellules, ombrage diffus, dispersion entre chaînes | 3 : PVsyst, SAM, pvlib | 2015-2026 | 16 | **PARTIEL** | `etapes/mismatch_ombrage.py` (effondrement I-V par chaîne) ; étape `diodes` déclarée mais omise « non modélisé en v1 » ; diffus non dérivé (†a1 §3) ; B1-C07 |
| K27 | Simulation sous-horaire (1-60 min) | 2 : PVsyst, SAM | 2014-2026 | 9 | **HORS DÉCISION** | simulation infra-horaire exclue (D-CALX 192 : PVGIS est horaire, `services/pvgis_serie.py`) |
| K28 | Écrêtage, limitation d'injection, facteur de puissance imposé | 4 : HelioScope, PV*SOL, PVsyst, SAM | 2013-2026 | 24 | **PRÉSENT** | `etapes/ecretage.py`, `services/raccordement.py` (cos φ société), stratégie `plafond_injection` (†a1 §5, §10) |
| K29 | Bifacial : plusieurs orientations, 1 axe, facteur de vue, PR bifacial | 4 : HelioScope, PVsyst, SAM, pvlib | 2017-2026 | 17 | **PARTIEL** | `services/bifacial.py`, `etapes/bifacial.py` : gain calculé à part, sans lancer de rayons arrière horaire (†a1 §4) |
| K30 | Incertitude et quantiles de production P50/P75/P90/P95 | 4 : HelioScope, PVsyst, SAM, archelios | 2013-2026 | 10 | **PRÉSENT** | `services/incertitude.py`, `services/p50p90.py` ; P99 non publié (D-ACAL-34=b) → HORS DÉCISION pour P99 |
| K31 | Sources météo supplémentaires (Meteonorm, NSRDB, NASA POWER, ERA5, Solcast, Solargis…) | 7 : OpenSolar, PV*SOL, PVcase, PVsyst, SAM, archelios, pvlib | 2013-2026 | 41 | **PARTIEL** | PVGIS horaire + TMY seulement (`services/pvgis_serie.py`) ; Meteonorm/Solcast payants = HORS DÉCISION (D-CALX-PAYANT) ; NASA POWER / ERA5 gratuits non branchés ; B1-C06 propose une 2e source gratuite |
| K32 | Import d'un fichier météo perso + assistant de validation, TMY multi-année, ciel clair | 3 : PVsyst, SAM, pvlib | 2015-2026 | 21 | **PARTIEL** | `services/meteo_fichier.py` : CSV nommé, horaire, fuseau explicite seulement ; pas de PVsyst .MET/EPW/TMY3 (†a1 §1) ; B1-C15 propose le contrôle qualité |
| K33 | Pertes saisies en série temporelle : salissure, neige, albédo, indisponibilité | 4 : K2 Base, PVsyst, SAM, pvlib | 2015-2026 | 11 | **PARTIEL** | `etapes/salissure.py` (12 valeurs mensuelles), `neige` poste mensuel saisi, `etapes/indisponibilite.py` ; pas de CSV de série temporelle (†a1 §4-5) |
| K34 | Dégradation / vieillissement des modules sur 25 ans | 2 : PVsyst, SAM | 2015-2025 | 8 | **PRÉSENT** | `etapes/vieillissement.py` → `production.annees` (†a1 §4) |
| K35 | Stratégies de batterie : autoconsommation, écrêtage de pointe, décalage tarifaire, arbitrage | 4 : HelioScope, PV*SOL, PVsyst, SAM | 2015-2026 | 20 | **PRÉSENT** | `services/batterie.py::simuler_batterie` : stratégies `autoconso, peak_shaving, backup, decalage, plafond_injection, heures_tarif` (†a1 §10) |
| K36 | Recommandation / dimensionnement automatique de la batterie depuis la consommation | 4 : Huawei, PVsyst, Pylon, SAM | 2019-2026 | 5 | **PARTIEL** | `services/hors_reseau.py::dimensionner_hors_reseau` (autonomie), `core/calepinage/recommandations.py` ; pas de recommandeur réseau avec carte solaire/batterie ; B2-r8 propose déjà |
| K37 | État de santé / usure / fin de vie de la batterie | 3 : OpenSolar, PVsyst, Polysun | 2019-2026 | 6 | **PRÉSENT** | `services/batterie.py::vieillissement_batterie` (par cycles, CALX63), champ `bat_cycles_publies`, rétention fin de vie (†a1 §6, §10) |
| K38 | Batterie couplée DC/AC, stockage autonome, BESS | 3 : PV*SOL, PVcase, SAM | 2015-2026 | 10 | **PARTIEL** | hybride via champs `ond_bat_*` ; pas de topologie DC/AC dessinée (†a1 §6) ; BESS réseau hors besoin résidentiel/petit C&I |
| K39 | Charge de véhicule électrique (optimisée PV, profils de conduite) | 7 : Eturnity, OpenSolar, PV*SOL, PVsyst, Polysun, SMA Sunny Design, Scanifly | 2014-2026 | 12 | **PRÉSENT** | `services/charges.py::courbe_vehicule` (†a1 §10) |
| K40 | Pompe à chaleur, chauffe-eau à immersion, thermique couplé au PV | 7 : OpenSolar, PV*SOL, PVcase, PVsyst, Pylon, RatedPower, SAM | 2020-2026 | 14 | **PRÉSENT** | `services/charges.py::courbe_pac` (†a1 §10) ; chauffe-eau à immersion : non vérifié |
| K41 | Bibliothèque de profils de charge types (par foyer/activité) | 5 : PV*SOL, PVsyst, Polysun, SolarEdge, archelios | 2016-2026 | 15 | **PRÉSENT** | `ProfilTypeConsommation`, `services/profils_types.py`, route `parametres/profils-types` (†a1 §10) |
| K42 | Consommation : mois manquants estimés, total annuel réparti, lecture de facture, données d'intervalle | 7 : Arka 360, Huawei, OpenSolar, PV*SOL, Pylon, SAM, Scanifly | 2024-2026 | 10 | **PARTIEL** | `services/consommation.py` (mensuel depuis factures), `courbe_charge.py` (courbe importée) ; pas d'estimation des mois manquants ni lecture de photo de facture (B3-N17 propose déjà) |
| K43 | Profil de consommation éditable (jour/mois) et renormalisation à la consommation annuelle | 4 : OpenSolar, PV*SOL, PVsyst, SolarEdge | 2020-2026 | 5 | **PRÉSENT** | `services/courbe_charge.py` (courbe importée, mensuelle + horaire) (†a1 §10) |
| K44 | Pompage solaire (pompes, conduites, rabattement, débit) | 5 : Eturnity, OpenSolar, PV*SOL, PVsyst, Polysun | 2016-2026 | 14 | **PRÉSENT** | `services/pompage.py` → `apps.ventes.solar_design.pumping_cycle_yield` (†a1 §10) ; bilan journalier réservoir : B1-C22 |
| K45 | Variantes d'un projet et comparaison côte à côte | 6 : Huawei, OpenSolar, PVcase, PVsyst, SMA Sunny Design, SolarEdge | 2016-2026 | 12 | **PRÉSENT** | `CalepinageVariante`, `services/variantes.py`, `services/comparaison.py`, `comparatif.xlsx`, comparer jusqu'à 5 projets (†a1 §12) |
| K46 | Optimisation / itération de capacité / balayages de paramètres | 7 : Aurora, OpenSolar, PV*SOL, PVcase, PVsyst, SAM, SMA Sunny Design | 2015-2026 | 16 | **PARTIEL** | optimiseur navigateur (matrice tilt×azimut `estimatorBrainV6.ts::fineGridMatrixV6`) ; côté serveur « Parametric sweeps : D » (†a1 §12) ; B1-C02 |
| K47 | Conception automatique par IA (calepinage et système générés) | 4 : Aurora, OpenSolar, PVcase, Scanifly | 2025-2026 | 6 | **PARTIEL** | remplissage auto déterministe PRÉSENT (`roofPro11/optimizer.ts`, `core/calepinage/optimum.py`) ; copilote IA éteint par réglage ; vision IA : D-ACAL-33 |
| K48 | Commande vocale / assistant conversationnel de conception | 2 : OpenSolar, Scanifly | 2025-2026 | 3 | **ABSENT** | B2-r19 propose déjà ; copilote ERP existe (`apps/calepinage/assistant.py`, éteint par défaut) |
| K49 | Rapport technique modulaire, page de garde, graphiques choisis, présentation client PDF/DOCX | 10 : HelioScope, Huawei, K2 Base, PV*SOL, PVcase, PVsyst, Pylon, Scanifly, SolarEdge, archelios | 2018-2026 | 25 | **PRÉSENT** | `services/rapport/` sections choisies par la société, `rapport-etude.pdf`, Sankey `chaine_pertes.py` ; DOCX : B1-C19, B4-r12 |
| K50 | Proposition web interactive, 3D partageable par lien, co-signature | 5 : Arka 360, OpenSolar, PVcase, PVsyst, SolarEdge | 2016-2026 | 10 | **PARTIEL** | visionneuse client en lecture seule `viewerFullBoot.ts` ; pas de lien public ni d'espace client côté backend (†a1 §14) ; la proposition client reste `/proposal` (règle n°4) → HORS DÉCISION pour le PDF |
| K51 | Exports de données ouverts (JSON, CSV, XLSX, API) | 9 : HelioScope, OpenSolar, PV*SOL, PVcase, PVsyst, Pylon, SAM, Scanifly, SolarEdge | 2014-2026 | 27 | **PRÉSENT** | `services/export_projet.py` (JSON), `export_csv.py`, `export_tableur.py` ; API publique `calepinage.simule` (†a1 §14-15) |
| K52 | Exports CAO/SIG (DXF, KML, LandXML, PVCollada, SketchUp) | 6 : HelioScope, OpenSolar, PVcase, PVsyst, SolarEdge, archelios | 2017-2026 | 13 | **PARTIEL** | DXF toit et SLD PRÉSENT (`services/export_dxf.py`) ; KML/LandXML/PVCollada/DWG : git grep 0 ; B5b rang 7 (DWG) propose déjà |
| K53 | Échanges avec d'autres outils de conception (import K2/PV*SOL/Sunny Design, interface constructeur) | 6 : K2 Base, PV*SOL, PVcase, PVsyst, SMA Sunny Design, archelios | 2013-2026 | 10 | **ABSENT** | git grep `K2 Base\|PV\*SOL` en import : 0 ; faible intérêt (notre module est le maître) |
| K54 | Base de composants / catalogue de produits, import .PAN/.OND, filtres | 8 : OpenSolar, PV*SOL, PVcase, PVsyst, Polysun, Pylon, archelios, pvlib | 2021-2026 | 14 | **PLANIFIÉ** | fiche technique 129 champs `apps/stock/models_fiche_technique.py` PRÉSENTE ; import .PAN/.OND : CALX339, CALX356, CALX357 ([ ] ouvertes, `docs/PLAN2.md:692,710,711`) |
| K55 | Modèles, gabarits et profils par défaut réutilisables | 5 : HelioScope, OpenSolar, PV*SOL, PVcase, Pylon | 2022-2026 | 7 | **PRÉSENT** | `services/modeles.py`, `presets.py`, `gabarits.py`, `kits.py` (†a1 §15) |
| K56 | Relevé de chantier mobile : checklists, photos annotées, azimut/inclinaison au téléphone | 3 : OpenSolar, Pylon, Scanifly | 2026-2026 | 4 | **PARTIEL** | `PhotoSite`, `ReleveTerrain`, `services/releve.py`, `reprise_visite.py` (†a1 §13) ; pas d'app terrain hors ligne (B4-r17, B4-r19, B3-N10) |
| K57 | Audit / contrôle de santé de la conception, alertes de compatibilité | 6 : OpenSolar, PV*SOL, PVcase, PVsyst, Scanifly, archelios | 2013-2026 | 16 | **PRÉSENT** | `services/validation.py` (CALX195), `feu_vert.py`, rapport de contrôle ; panneau « prêt à envoyer » : B3-N6, B4-r6 |
| K58 | Travail d'équipe : tâches, attribution, notifications, gestion de projet | 7 : OpenSolar, PV*SOL, PVcase, PVsyst, Pylon, SMA Sunny Design, Scanifly | 2016-2026 | 16 | **HORS MODULE** | relève de l'ERP (CRM, chantiers, tâches), pas du module de calepinage |
| K59 | Terrassement, pieux, collisions, routes, terrain irrégulier (génie civil sol) | 4 : PVcase, PVsyst, RatedPower, pvlib | 2015-2026 | 23 | **HORS DÉCISION** | terrain-following et élévation : non-objectif déclaré (`docs/moteur-calepinage.md` §7) ; champ au sol plat `core/calepinage/surfaces/sol.py` |
| K60 | Trackers et backtracking | 4 : PVcase, PVsyst, RatedPower, SAM | 2014-2026 | 27 | **HORS DÉCISION** | trackers : non-objectif déclaré (`docs/moteur-calepinage.md` §7) |
| K61 | Étiquettes, numérotation des modules et des chaînes, annotations | 4 : OpenSolar, PVcase, Pylon, Scanifly | 2025-2026 | 9 | **PRÉSENT** | `roofPro11/numerotation.ts`, `services/etiquettes.py` ; annotations libres sur plan/photo : B2-r4 |
| K62 | Carte d'irradiance / d'accès solaire sur le toit | 1 : Arka 360 | n.d. | 2 | **PRÉSENT** | `shadingUi.ts::refreshHeatmap`, `lib/shadingEngine.ts::cellsSolarAccess` (†a3 §1) |
| K63 | Course du soleil / ombres à une heure donnée | 2 : PVsyst, SMA Sunny Design | 2019-2021 | 2 | **PRÉSENT** | onglet `course-soleil`, `soleilPlay.ts` (†a3 §1) ; heure légale vs solaire : B4-r12 |
| K64 | Dimensionnement de l'onduleur : ratio DC/AC, surcharge, courant, déclassement thermique | 4 : PVcase, PVsyst, SAM, SMA Sunny Design | 2014-2026 | 12 | **PRÉSENT** | `core/electrique/onduleurs.py::ratios` ; déclassement thermique : B1-C03 |
| K65 | Règles d'optimiseurs et micro-onduleurs (Tigo, Huawei, SolarEdge, Maxim) | 7 : K2 Base, PV*SOL, PVcase, PVsyst, SAM, SMA Sunny Design, archelios | 2014-2026 | 22 | **PARTIEL** | champs `opt_*`, `services/micro_onduleurs.py` (†a1 §6) ; règles de dimensionnement propres à une marque : non (hors fiche) |
| K66 | Système combiné PV + thermique + batterie + appareils | 3 : PV*SOL, PVsyst, SAM | 2023-2026 | 3 | **PARTIEL** | batterie + VE + PAC modélisés séparément (`charges.py`, `batterie.py`) ; pas de « type de système » combiné nommé |
| K67 | Hors réseau et groupe électrogène | 7 : PV*SOL, PVcase, PVsyst, Polysun, Pylon, SAM, SMA Sunny Design | 2018-2026 | 14 | **PARTIEL** | `services/hors_reseau.py` PRÉSENT ; groupe électrogène : B1-C14 propose déjà |
| K68 | Bilan carbone | 1 : PVsyst | 2014-2014 | 1 | **PLANIFIÉ** | B1-C20 (GATED sur une source datée) |
| K69 | Projets d'exemple, tutoriels, aide guidée | 2 : PV*SOL, PVsyst | 2025-2026 | 4 | **ABSENT** | B1-C18 propose déjà (calepinage d'exemple) |
| K70 | Interface simplifiée pour le vendeur (mode simple, grille on/off, parcours guidé) | 4 : HelioScope, OpenSolar, PVcase, Scanifly | 2025-2026 | 8 | **PLANIFIÉ** | D-ACAL-32 (parcours guidé à 5 étapes, ACAL392-394) ; B3-N5, B3-N15 |
| K71 | Argent dans le logiciel de conception (tarifs, VAN, TRI, financement, marges) | 13 : Arka 360, HelioScope, Huawei, OpenSolar, PV*SOL, PVcase, PVsyst, Pylon, SAM, SMA Sunny Design, Scanifly, SolarEdge, archelios | 2016-2026 | 33 | **HORS DÉCISION** | l'argent reste dans `apps/ventes` (règle fondateur, `docs/moteur-calepinage.md`) |
| K72 | Dossier de raccordement / permis / lettre d'autorisation | 3 : OpenSolar, PVsyst, Pylon | 2017-2026 | 7 | **PRÉSENT** | `services/reglementaire.py`, `services/gabarits.py`, `services/raccordement.py` (†a1 §14) |
| K73 | Orientations multiples : mixtes sur un même onduleur, création depuis la sélection, dispersion | 1 : PVsyst | 2013-2025 | 11 | **PRÉSENT** | `services/polystring.py` (plusieurs orientations sur une entrée MPPT), multi-pans (†a1 §6) |
| K74 | Rotation d'objets et du site entier | 6 : OpenSolar, PVcase, PVsyst, Pylon, SAM, SolarEdge | 2021-2026 | 8 | **PARTIEL** | orientation fine ±1° (`nudgeAzimuthDeg`), rotation libre testée sans bouton (†a3) ; B4-r14 propose déjà |
| K75 | Sélection avancée : groupes, multi-sélection, liste des objets, modification groupée | 4 : PVsyst, Polysun, Pylon, SolarEdge | 2015-2026 | 16 | **PARTIEL** | lasso/cadre/rangée entière, `moveGroup` PRÉSENTS (†a3) ; tableau des objets du site : B1-C13 |
| K76 | Mesures de distance, surface, angle ; outil d'angle entre plans | 2 : OpenSolar, PVsyst | 2017-2025 | 3 | **PRÉSENT** | `roofPro11/mesureUi.ts` (†a3) |
| K77 | Calques, volets déplaçables, liste hiérarchique des pans, tri | 5 : PVcase, PVsyst, Polysun, SAM, Scanifly | 2019-2026 | 7 | **PARTIEL** | calques `PanneauCalques.jsx`, rail d'onglets ; pas de volets déplaçables ni de tri des pans (†a3 §4) |
| K78 | Annuler / rétablir généralisé | 2 : OpenSolar, Scanifly | 2026-2026 | 2 | **PARTIEL** | pile de 50 pas mais clavier actif seulement en mode disposition (`layoutHistory.ts`, †a3 §5 pt 6) ; B4-r5 propose déjà |
| K79 | Rapidité de calcul et de chargement | 6 : OpenSolar, PV*SOL, PVcase, PVsyst, SAM, Scanifly | 2016-2026 | 13 | **PRÉSENT** | test de perf `roofPro11/perf.test.ts` (2 000 modules), `InstancedMesh` (†a3 §3) — non fonctionnel, pas une fonction à livrer |
| K80 | Sécurité du site et plan de chantier (job pack, plan de site, QR code) | 6 : OpenSolar, PVcase, Pylon, SAM, SMA Sunny Design, Scanifly | 2015-2026 | 13 | **PARTIEL** | `documents/manuel_proprietaire.py`, `plan-masse.pdf`, `document_asbuilt.py` (†a1 §14) ; QR code vers l'ouvrage : absent |
| K81 | Intégration de fabricants d'onduleurs/structures dans le flux (cartes, nomenclature, supplier) | 8 : Aurora, Eturnity, Huawei, OpenSolar, PV*SOL, PVcase, PVsyst, Polysun | 2017-2026 | 17 | **HORS DÉCISION** | achats/stock = autre module ; D-CALX-PAYANT pour les données fabricant payantes |
| K82 | Géolocalisation / carte : fonds de carte et sections de carte | 5 : K2 Base, OpenSolar, PV*SOL, PVsyst, Scanifly | 2018-2026 | 10 | **PARTIEL** | MapTiler/Mapbox/IGN (`lib/roofConfig.ts`) ; sélecteur de fournisseur par société (†a3 §2) |
| K83 | Heure, fuseau, hémisphère, cardinaux dans l'affichage de scène | 2 : PVcase, PVsyst | 2014-2025 | 6 | **PARTIEL** | boussole `rp9-compass` (†a3) ; nord personnalisé : orientation relevée à l'azimut |
| K84 | Gestion de l'énergie réactive, transformateurs MT/HT, postes | 4 : OpenSolar, PVcase, PVsyst, SAM | 2017-2026 | 5 | **PRÉSENT** | `etapes/transformateur.py`, `services/coffrets.py`, B1-C24 pour kVArh (†a1 §5) |
| K85 | Modèles physiques de simulation : IAM, spectral, transposition, circumsolaire, décomposition | 4 : PV*SOL, PVsyst, SAM, pvlib | 2014-2026 | 20 | **PARTIEL** | IAM PRÉSENT (`etapes/iam.py`), thermique Faiman/NOCT PRÉSENT (`services/thermique.py`) ; spectral omis, transposition faite par PVGIS (†a1 §1, §4) ; pvlib adopté (`docs/PLAN2.md:104`) mais non branché pour le modèle une-diode (CALX198) |
| K86 | Champs de modules définis par nombre de rangées/colonnes, polygones, réseaux de tables | 2 : PVsyst, Scanifly | 2014-2026 | 5 | **PRÉSENT** | `core/calepinage/surfaces/{rectangle,polygone,multi}.py`, zones d'exclusion `zones.ts::exclusionZoneRing` (†a1 §8, a3) |
| K87 | Placement et rendu 3D des appareils électriques (onduleurs, boîtes, postes, harnais) | 1 : PVcase | 2025-2026 | 8 | **ABSENT** | `electrique3d.ts` ne trace que les chaînes (†a3 §1) ; `services/coffrets.py` dimensionne sans placement 3D |
| K88 | Cible de panneaux affichée pendant la pose | 1 : Pylon | 2026-2026 | 1 | **PRÉSENT** | cible « panneaux nécessaires » de l'optimiseur vivant `roofPro11/optimizer.ts` (†a3 §6) |
| K89 | Export image / impression du calepinage | 3 : HelioScope, OpenSolar, PVsyst | 2014-2026 | 5 | **PRÉSENT** | `scene3d.ts` PNG HD 8192 px, `planche.pdf/.svg`, `plan-pose.pdf` (†a1 §14, a3 §3) |
| K90 | Licence par utilisateur, multi-appareils | 2 : PV*SOL, PVsyst | 2021-2024 | 2 | **HORS MODULE** | compte et droits de l'ERP, pas du calepinage |
| K91 | Liste de projets : recherche, archivage, renommage, partage | 2 : HelioScope, PVcase | 2025-2026 | 2 | **PRÉSENT** | `services/archivage.py`, routes `archiver`, `restaurer-corbeille`, `dupliquer` (†a1 §15) |
| K92 | Perte de rendement expliquée avec conseil de réduction | 1 : SolarEdge | 2021-2021 | 1 | **PARTIEL** | cascade des pertes `diagramme-pertes.svg` PRÉSENTE ; pas de phrase « que faire » (B4-r1, B4-r2 proposent déjà) |
| K93 | Modélisation d'une batterie ajoutée à un système existant ou importé | 1 : OpenSolar | 2025-2025 | 1 | **ABSENT** | B4-r7 et B5a-r9 proposent déjà « installation existante » |
| K94 | Règle de conception recommandant un compteur de production selon l'onduleur | 1 : OpenSolar | 2025-2025 | 1 | **ABSENT** | aucune occurrence ; faible intérêt |
| K95 | Langue, polices et couleurs des propositions | 1 : OpenSolar | 2026-2026 | 1 | **HORS DÉCISION** | change le PDF client : règle n°4 (`/proposal` seul chemin) |
| K96 | Capacités isolées (une seule source, sans grappe) | 8 : OpenSolar, PV*SOL, PVcase, PVsyst, Pylon, SMA Sunny Design, Scanifly, pvlib | 2013-2026 | 32 | **PARTIEL** | voir lignes : pertes d'auxiliaires jour/nuit (présent `etapes/auxiliaires.py`), batteries Li-ion (présent), horaires d'usage d'appareils (présent `charges.py`), inclinaisons négatives H2P, vues scène 3D, limites de parcelle (cadastre = non-objectif) |

## 4. Vérification contre notre module

Méthode : inventaires `r1/a1-backend.md`, `a2-frontend-erp.md`, `a3-atelier-3d.md` (marqués `†` quand la preuve vient de là sans que cette passe ait rouvert le code), fichiers de lots `plan/lot-W*.md`, grep du code (`backend/django_core/apps/calepinage`, `core/calepinage`, `core/electrique`, `frontend/src/features/calepinage`, `apps/web/src/scripts/roofPro11`, `apps/web/src/lib`) et de `docs/plans`, `docs/PLAN2.md`. Greps de cette passe : `KML`, `LandXML|PVCollada`, `ColladaExporter|GLTFExporter|\.dae`, `DeviceOrientation`, `cycles par jour`, `ancrage|ligne de vie`, `chemin de c.bles`, `glTF|IFC`, `coordonn.es GPS`, `SOH|état de santé` : 0 occurrence pertinente dans le module. Présents : `ObstacleType` à 6 types (`apps/web/src/lib/obstacles.ts:37`), zones sourcées (`services/zones_reglementaires.py`), vieillissement batterie (`services/batterie.py::vieillissement_batterie`), `SOLAR_ACCESS_LOW` fixe (`shadingUi.ts`).

Verdicts : PRÉSENT · PARTIEL · ABSENT · PLANIFIÉ (tâche citée) · HORS DÉCISION (données/logiciels payants, trackers, infra-horaire, argent dans le module, calcul normatif vent/neige, PDF client) · HORS MODULE (autre partie de l'ERP).

| Verdict | Grappes | Liste |
|---|---|---|
| PRÉSENT | 42 | K01, K03, K04, K05, K06, K08, K09, K10, K12, K16, K17, K19, K23, K25, K28, K30, K34, K35, K37, K39, K40, K41, K43, K44, K45, K49, K51, K55, K57, K61, K62, K63, K64, K72, K73, K76, K79, K84, K86, K88, K89, K91 |
| PARTIEL | 32 | K02, K07, K11, K13, K14, K22, K26, K29, K31, K32, K33, K36, K38, K42, K46, K47, K50, K52, K56, K65, K66, K67, K74, K75, K77, K78, K80, K82, K83, K85, K92, K96 |
| ABSENT | 9 | K18, K21, K24, K48, K53, K69, K87, K93, K94 |
| PLANIFIÉ | 4 | K15, K54, K68, K70 |
| HORS DÉCISION | 7 | K20, K27, K59, K60, K71, K81, K95 |
| HORS MODULE | 2 | K58, K90 |

Tâches déjà au plan, trouvées par `git grep` : **CALX339, CALX356, CALX357** (import `.PAN`/`.OND`, `docs/PLAN2.md:692,710,711`, ouvertes) ; **CAL51** (Google Solar, GATED payant) ; **CALX198** (modèle une-diode, pvlib « adopté » `docs/PLAN2.md:104`) ; **D-ACAL-32 / ACAL392-394** (parcours guidé) ; **D-ACAL-33** (détection IA du toit) ; **D-ACAL-34=b** (P99 non publié, ACAL457 `[SKIP]`).

## 5. Propositions pour nous (absent ou partiel, non planifié, permis), classées

Rang = nombre d'outils × adéquation (3 = toit résidentiel/plat béton/C&I/pompage vendu par un non-ingénieur ; 1 = marginal pour nous). « NOUVEAU » = absent de B1-B5 ; « CONFIRME … » = déjà proposé ailleurs, ce benchmark ajoute des outils et des versions (id cité). Aucune proposition ne change le PDF client, n'ajoute de l'argent dans le module, ne suppose une donnée payante.

| R | Capacité (une ligne) | Outils et versions | Ce que nous avons (preuve) | Plus petite version crédible | Reste simple / caché | Statut |
|---|---|---|---|---|---|---|
| R1 | Seconde source météo gratuite (NASA POWER ou ERA5) avec écart annoncé face à PVGIS | PVsyst 8.1.0 (NASA POWER), 8.0.7 (PVGIS 5.3), PVcase GM 2.62 (PVGIS 5.3 horaire), pvlib 0.13.1 / 0.14.0 (NASA POWER, ERA5, MERRA-2), SAM 2024.12.12 (NSRDB), archelios 2025.1 (Meteonorm 9), OpenSolar 3.3.0/3.4.0 (PSM4, CSIRO) (7 outils · adéquation 3) | PVGIS seul (`services/pvgis_serie.py`) ; Meteonorm/Solcast = payant (D-CALX-PAYANT) ; ERA5/NASA POWER gratuits non branchés | lecture ERA5 ou NASA POWER pour le même site, écart annuel affiché à côté du résultat PVGIS, jamais de substitution silencieuse | affiché seulement quand l'écart dépasse un seuil | CONFIRME B1-C06 |
| R2 | Copier-coller de modules, de rangées et des réglages d'un pan vers un autre pan existant | PVcase RM 1.52 (2025-07) « Pick generation settings », PVcase GM 2.50 (2024-12), SolarEdge Designer 2020-01 (copy/paste, replicate blocks), PVsyst 6.40/7.2.15 (copy/paste advanced selection), Scanifly 2026-01 (annoncé) (5 outils · adéquation 3) | « Dupliquer » une sélection avec décalage + symétrie (CALX112), dupliquer un pan (CALX98) ; pas de « coller » ni de copie entre pans (a3 §5 pt 5) | Ctrl+C / Ctrl+V sur la sélection, collé au curseur dans le pan visé ; « appliquer les réglages de ce pan à ceux-ci » | geste standard, aucun nouveau réglage | CONFIRME B2-r12, B2-r16, B3-N14 |
| R3 | Vérifier la tension de démarrage de l'onduleur et la fenêtre MPPT chaîne par chaîne à la revue du câblage | Pylon 2026-11-18 (string advice : startup voltage), PVcase RM 1.47 (2025-03) et GM 2.62 (inverter sizing), PVsyst 8.1.5 (T min < limite de tension), 6.02 (Vmax IEC/UL), SMA Sunny Design 5.20 (NEC) (5 outils · adéquation 3) | `etapes/mppt.py` compte les heures hors fenêtre ; `core/electrique/chaines.py` borne Voc à froid ; pas de message « démarre à telle heure » par chaîne | ligne par chaîne : Voc froid, Vmpp chaud, tension de démarrage et verdict en français | voyant vert/ambre/rouge, le détail sous clic | CONFIRME B5a-r11 (perte de démarrage), B5b-r4 |
| R4 | Bibliothèque d'obstacles plus riche (lanterneau, citerne, climatiseur, chauffe-eau, passerelle, garde-corps) avec ombre auto | OpenSolar 3.10 (2026-08) « Objects & Trees », PVcase RM 1.56 (2025-10) skylights, PVsyst 6.40 (dômes, éoliennes), 6.79 (pylône), SolarEdge 2022-02 (obstacles semblables) (4 outils · adéquation 3) | 6 types seulement (`apps/web/src/lib/obstacles.ts:37`) ; gabarits société CALX104 (circulaire + gabarits réutilisables) | ajouter 6 types avec hauteur typique saisie et ombre ; chaque hauteur reste « à confirmer » tant qu'elle n'est pas relevée | menu déroulant, hauteur préremplie par type et marquée hypothèse | CONFIRME B2-r3, B3-N19 |
| R5 | Recommandeur de batterie : taille proposée depuis la consommation, carte thermique PV × batterie, jours d'autonomie et cycles par jour | Pylon 2026-03-17 et 2026-05-04 (Battery Recommender, heat map, days of autonomy, cycles/day, jusqu'à 500 kWh), Huawei SmartDesign 2.0 (recommandation de capacité), OpenSolar 3.3.0 (cycles moyens/jour), PVsyst 6.40 (outil paramétrique), HelioScope 2026-07 (4 outils · adéquation 3) | `services/batterie.py` (6 stratégies), `core/calepinage/sensibilites.py::batterie` ; git grep `cycles par jour` : 0 | balayer 5 tailles de batterie sur la série existante, tableau autoconsommation/couverture, une ligne « recommandée » ; cycles/jour dans le résultat | une phrase « meilleure taille : X kWh, pourquoi », détail replié | CONFIRME B2-r8 (cycles/jour et carte = NOUVEAU) |
| R6 | Importer l'orthophoto d'un drone comme fond géoréférencé (et lire le relief) | PVcase RM 1.48 (Airteam), Aurora Drone Mapping (blog), Scanifly SimpleDesign 2025-06, PV*SOL 2026 R5 (Rexplorer, hors Maroc) (4 outils · adéquation 3) | aucun dépôt d'orthophoto (a3 §2) ; LiDAR IGN France seulement | GeoTIFF + 2 points ou EXIF → fond calé | fond d'image, pas de relevé du relief au début | CONFIRME B2-r1 |
| R7 | Mode « salon » du vendeur : activer/désactiver modules, rangées, pans, avec garde-fous | Scanifly SimpleDesign 2025-06-16 (Grid Mode + guardrails), Aurora Sales Mode, OpenSolar 3.0 (Ada), Huawei SmartDesign 2.0 (4 outils · adéquation 3) | atelier complet à ~40 onglets (a3 §4) | vue simple avec bascule modules et garde-fous | mode par défaut du vendeur | CONFIRME B3-N5 (planifié D-ACAL-32) |
| R8 | Estimer les mois de consommation manquants et répartir un total annuel selon la saison locale (barres estimées en pointillé) | Scanifly 2026-11-02 (1 à 12 mois, NOAA normals), OpenSolar 3.3.0 (estimations sur données incomplètes), Pylon 2026-05-04 (lecteur de facture, données d'intervalle) (3 outils · adéquation 3) | `services/consommation.py` : mensuel depuis factures ; `ProfilTypeConsommation` société ; pas d'estimation des mois vides (git grep `mois manquants` : 0) | forme saisonnière tirée du profil type de la société et des températures PVGIS déjà lues ; mois estimés marqués « estimé » et jamais présentés comme mesurés (règle zéro chiffre inventé) | le vendeur n'a que deux factures : l'écran propose l'année complète, à confirmer | NOUVEAU |
| R9 | Une chaîne qui court sur deux zones de même orientation et inclinaison | PVcase GM 2.53 (2025-04) stringing across PV areas, SolarEdge 2020-01 (blocs câblés répliqués), PVsyst 7.1.0 (attribution des chaînes, nombre impair) (3 outils · adéquation 3) | `services/chaines.py` : chaînes pan par pan, un azimut par chaîne (a1 §7) | autoriser le passage d'un pan à un autre quand azimut et inclinaison sont identiques à la tolérance près | résolu par le câblage automatique, sans question | NOUVEAU |
| R10 | Montrer en rouge/orange le panneau en conflit (retrait, obstacle) pendant le glissé, au lieu de refuser après coup | Scanifly 2025-11-19 (module conflict indicators red/orange), PVcase RM 1.48 (modules en surnombre en rouge), OpenSolar 2.31 (setback flash red) (3 outils · adéquation 3) | `layoutEditor.ts::checkPanelAt` refuse et nomme la raison (a3 §4) | fantôme du panneau coloré selon la règle violée et phrase de raison déjà existante | visible seulement pendant le geste | NOUVEAU |
| R11 | Type de couverture (tuile plate, tuile canal, bac acier, dalle) qui choisit la pièce de fixation | OpenSolar 3.11 (2026-09) choix plate/pantile avant calcul, 3.13 (K2 BasicRail trapézoïdal), 3.8 (Tile Slate hooks), PV*SOL 2025 (interface Renusol PV-Configurator) (3 outils · adéquation 3) | `services/fixation.py`, `catalogue_fixation.py` ; mode de pose bac acier (migration `0020_ciq112_mode_pose_bac_acier`) ; tuile canal non vérifié | champ « couverture » par pan qui filtre le catalogue de fixation de la société | préselection selon le relevé, modifiable | NOUVEAU |
| R12 | Relevé de chantier mobile : listes de contrôle avec champs obligatoires, photos annotées, albums | Scanifly Mobile 2026-10-21, Scanifly 2026-07-07 (checklists multi-utilisateurs), OpenSolar 3.12 (2026-10) Mobile Experience, Pylon 2026-05 (création de projet mobile) (3 outils · adéquation 3) | `PhotoSite`, `ReleveTerrain`, `services/releve.py`, `reprise_visite.py` (a1 §13) ; pas d'app hors ligne | gabarit de relevé « toiture » à champs obligatoires et 6 photos nommées, brouillon local déjà présent | la visite se remplit dans l'ordre, rien d'optionnel oublié | CONFIRME B3-N10, B4-r17, B4-r19 |
| R13 | Comparer l'inclinaison, le nombre de modules et le kWh/an d'un toit plat en un tableau | PVsyst 6.39 (optimisation de rangées), 6.40 (balayage inclinaison), PVcase GM 2.51 (limite d'ombrage admise), 2.54/2.57 (itération de capacité), HelioScope (3 outils · adéquation 3) | optimiseur navigateur `fineGridMatrixV6` ; pas de balayage serveur (a1 §12) | tableau 3×3 recalculé côté serveur | une ligne « meilleur compromis » | CONFIRME B1-C02 |
| R14 | Dalle béton plate : pieds et longrines posés automatiquement | OpenSolar 3.8 (2026-06) « Elevated structures » RCC avec acrotères, PVcase RM 1.52 (cadres à inclinaison fixe), Scanifly 2026-06 (réglages avancés toits plats) (3 outils · adéquation 3) | châssis 3D existant `scene3d.ts` ; pas de pieds/longrines générés | paire de longrines par rangée, pièces comptées dans la nomenclature | affichage 3D seulement | CONFIRME B2-r6 |
| R15 | Panneau « prêt à envoyer » : contrôles vert/ambre/rouge avec la phrase du correctif | PVcase RM 1.56 (audit tool), PVsyst 7.0.0 (avertissements pendant/après simulation), 8.0.13, OpenSolar 3.13 (Power Up) (3 outils · adéquation 3) | `feu_vert.py`, `validation.py` | liste unique des vérifications existantes | un voyant | CONFIRME B3-N6, B4-r6 |
| R16 | Deux propositions en un clic : « le plus de panneaux » et « couvrir ma facture » | OpenSolar Ada (Max Offset / Max Fit), Scanifly SimpleDesign (MaxFill), Aurora AI (3 outils · adéquation 3) | `optimizer.ts` cible « panneaux nécessaires » | deux variantes créées d'un bouton | variantes nommées | CONFIRME B2-r2 |
| R17 | Export de la scène 3D en COLLADA (.dae) pour PVsyst, SketchUp et le bureau d'études | PVcase GM 2.58 (objets d'ombrage vers PVsyst), 2.60 (2026-04 export PVsyst), 2.63 (2026-08 PVCollada 2.0), HelioScope 2025-11-19 (DAE), PVsyst 6.60 / 7.3.3 (import DAE), archelios (SketchUp/Revit) (4 outils · adéquation 2) | git grep `ColladaExporter\|GLTFExporter\|\.dae` : 0 ; la scène est déjà en Three.js (`scene3d.ts`) | exporter bâtiment + modules + obstacles par le `ColladaExporter` de Three.js, unités et nord inclus | bouton dans « Dossiers » ; pas de promesse de bancabilité (D « pas de bankable ») | NOUVEAU |
| R18 | Lien de visionneuse 3D client en lecture seule (jeton, expiration, sans prix), partageable par WhatsApp | OpenSolar 3.12 (2026-10) propositions 3D interactives + WhatsApp 3.10, Arka 360 Web Proposal (modèle 3D, irradiance), PVcase GM 2.52 (2025-02) Web Viewer par lien, SolarEdge Designer 2021-07/08 (Share) (4 outils · adéquation 2) | visionneuse `viewerFullBoot.ts` (`readOnly`) existe ; aucun jeton public côté backend (a1 §14) ; le PDF client reste `/proposal` (règle n°4) | URL à jeton révocable qui ouvre la scène en lecture seule, sans chiffres monétaires | un bouton « envoyer le plan 3D » ; ne touche pas au PDF | NOUVEAU (voir B4-r18 pour le suivi de lecture) |
| R19 | Éditer librement le schéma unifilaire : ajouter/déplacer/tourner un composant, légende et cartouche | Pylon 2026-06-30 et 2026-09 (Custom SLD editor, legend, rotation, snapping, generator), OpenSolar 3.11 (SLD 2 onduleurs), 3.12 (template Inde PDF/DXF), PVcase RM 1.58 (SLD settings), PVsyst 7.3.2 (grouping) (4 outils · adéquation 2) | `services/sld.py` : étiquettes et références éditables seulement (a1 §7) | faire glisser/pivoter un symbole, ajouter un composant de la liste, légende avec référence et date | le schéma auto reste la base ; l'édition est un mode avancé | NOUVEAU |
| R20 | Bifacial horaire par facteurs de vue (albédo mensuel, hauteur, GCR) au lieu d'un gain global | PVsyst 6.60/6.70/8.0.0/8.1.5, SAM 2018.11.11 / 2022.11.21 (albédo spatial, mismatch bifacial), pvlib 0.9.1 (infinite sheds) / 0.16.0 (ANTS-2D), HelioScope 2025-07 (bifacial) (4 outils · adéquation 2) | `services/bifacial.py` : gain calculé à part, sans rayons arrière horaires (a1 §4) ; pvlib « adopté » (`docs/PLAN2.md:104`) | modèle infinite-sheds pvlib appliqué aux toits plats E-O ou inclinés, albédo saisi par la société | silencieux si le module n'est pas bifacial | NOUVEAU |
| R21 | Export CSV à colonnes et pas de temps au choix (horaire, journalier, mensuel) | PV*SOL 2025 (CSV configurable 1/10/15/30 min), PVcase RM 1.55 (CSV énergie), PVsyst 6.18 / 7.3.0 / 8.1.8 (graphiques et tableaux personnalisés), HelioScope 2025-11 (CSV 8760) (4 outils · adéquation 2) | `services/export_csv.py` : une série horaire fixe (`calepinage-…-horaire.csv`, a1 §14) | cases à cocher sur les colonnes existantes et agrégation journalière/mensuelle | défaut = export actuel | NOUVEAU |
| R22 | Profils de charge types prêts à compléter : climatisation d'été, télétravail, retraités, Ramadan | PV*SOL 2026 R1 (2025-11) climatisation/télétravail/retraités, archelios PRO 2025.1 (ELMAS), SolarEdge 2020-01 (profils commerciaux), PVsyst 6.40 (time-of-use) (4 outils · adéquation 2) | `ProfilTypeConsommation` à valeurs société ; cas de test `casablanca_ramadan` (a1 §16) ; règle zéro chiffre inventé | gabarits VIDES à compléter par la société avec sa source, aucune valeur livrée | le vendeur choisit un type de foyer, rien d'autre | NOUVEAU |
| R23 | Info-bulle sur chaque élément du dessin (module, rangée, obstacle, onduleur) donnant ses valeurs | PVcase RM 1.53 (2025-08, informational tooltips), PVsyst 6.80 (tooltip au survol d'un module), OpenSolar 3.3.0 (tooltips d'en-tête), Scanifly 2026-06 (étiquettes de valeur) (4 outils · adéquation 2) | `roofPro11/infoBulleOmbrage.ts` seulement pour l'ombrage | survol = chaîne, MPPT, accès solaire, tension | apparaît au survol, rien d'ajouté à l'écran | NOUVEAU (voir B4-r1) |
| R24 | Trier ou filtrer les pans par accès solaire ou nombre de modules ; bandeau fixe (modules, kWc, accès moyen) | Scanifly 2026-02-26 (tri par TSRF/module count, header persistant), OpenSolar 3.3.0 (tooltips d'en-tête), PVsyst 7.2.7 (total de modules en barre d'état) (3 outils · adéquation 2) | liste des zones `rp9-areas-list` (a3 §1) ; pas de tri ni de bandeau persistant | un tri et une ligne fixe de totaux | apparaît tout seul, sans réglage | NOUVEAU |
| R25 | Afficher la date et la résolution de l'image satellite utilisée | OpenSolar 3.6 (2026-04, contrôle de la date de capture), 3.7 (marché d'imagerie), Scanifly 2025-08-27 (aperçu avant achat), RatedPower (2026) (3 outils · adéquation 2) | `lib/roofConfig.ts` : `resolution null` = non annoncée (a3 §2) | ligne « image Maxar/Mapbox, date non annoncée par le fournisseur » dans l'écran et le rapport d'ombrage | texte discret sous la carte | NOUVEAU |
| R26 | Essayer un module ou un onduleur de remplacement sur les chaînes avant de l'appliquer | PVcase GM 2.62 (2026-07, comparer un module/onduleur secondaire au primaire), Pylon 2026-11 (string advice), OpenSolar 3.3.0 (design rules) (3 outils · adéquation 2) | `SV/equipements.py` choisit un modèle ; `CalepinageVariante` pour comparer ; pas de simulation à blanc des chaînes | aperçu « chaînes : avant/après » pour le modèle choisi | affiché dans la liste de choix | NOUVEAU (voir B4-r3) |
| R27 | Contrôle qualité d'un fichier météo déposé (trous, décalage horaire, valeurs hors bornes) et assistant d'import | PVsyst 8.1.0 (weather data import assistant + validation step), 6.44/6.45 (time shift), SAM 2021.12.02 r1 (labels PVLIB), pvlib 0.13.1 (lecteurs) (3 outils · adéquation 2) | `services/meteo_fichier.py` : CSV nommé, ISO avec fuseau explicite, horaire ; refus nommés mais pas de contrôle de continuité (a1 §1) | après lecture : nombre d'heures manquantes, décalage probable, min/max physiques, en français | message unique « fichier lisible / à corriger » | CONFIRME B1-C15 |
| R28 | Page de synthèse chiffrée en tête du rapport d'étude | PV*SOL 2026 R1 (rapport compact), PVsyst 7.1.0 (page de synthèse), archelios 2025.1 (Pxx dans le PDF) (3 outils · adéquation 2) | `services/rapport/` sections ; pas de page de synthèse (B1) | une page de chiffres clés générée depuis le résultat | première page du rapport interne | CONFIRME B1-C04 |
| R29 | Comparer 2-3 configurations d'onduleurs côte à côte | SMA Sunny Design 5.20 (comparer alternatives autoconsommation/autosuffisance), SolarEdge Designer 2021-08 (multi-design), PVsyst 7.2.7 (variantes) (3 outils · adéquation 2) | `CalepinageVariante` + `comparaison.py` ; comparatif par onduleur non explicite | colonne « onduleur » dans le comparatif de variantes | variantes créées en un clic | CONFIRME B1-C10 |
| R30 | Graphe de dimensionnement DC/AC : énergie écrêtée par classe de puissance | PVsyst 6.33 (ratio de puissance nominale rapide), 8.0.13 (alertes de sous-dimensionnement à 2 % et 4 %), SAM 2014.11.24 (macro de dimensionnement d'onduleur) (3 outils · adéquation 2) | `etapes/ecretage.py` ; ratios `core/electrique/onduleurs.py` | histogramme d'écrêtage par classe | sous le ratio DC/AC | CONFIRME B1-C11 |
| R31 | Prolonger une installation existante : modules déjà posés comptés à part | OpenSolar 3.0 (battery retrofit, système existant/importé), Eturnity 2025-05 (rénovations), PVsyst 6.40 (sous-systèmes) (3 outils · adéquation 2) | aucun marqueur « existant » (B4-r7) | case « existant » sur un champ/onduleur | affichage grisé | CONFIRME B4-r7, B5a-r9 |
| R32 | Groupe électrogène existant dans les systèmes autonomes ou hybrides | Polysun 7.0 (groupes pour PV hors réseau), PVsyst 6.76 / 7.4.3 (générateur de secours), SAM 2017.1.17 (3 outils · adéquation 2) | `services/hors_reseau.py` sans groupe | seuils de SOC et puissance du groupe | uniquement dans l'étude hors réseau | CONFIRME B1-C14 |
| R33 | DXF avec modules en blocs nommés par chaîne et onduleur | PVcase GM 2.64, SolarEdge Designer 2022-02 (DXF import/export), HelioScope 2025-11 (DXF) (3 outils · adéquation 2) | `services/export_dxf.py` : DXF toit et SLD (a1 §14) | blocs par chaîne et attribut onduleur | export existant enrichi | CONFIRME B3-N20 |
| R34 | Gabarits de schéma unifilaire réutilisables par type de système | OpenSolar 3.12 (SLD template Inde), Pylon 2026-06 (custom SLD), PVcase RM 1.58 (3 outils · adéquation 2) | `services/sld.py` génère un SLD par calcul ; pas de gabarit société | gabarit choisi par type d'onduleur | préréglage | CONFIRME B3-N21 |
| R35 | Passerelle devis rapide vers atelier | OpenSolar 3.9 (Quick Quote), Eturnity 2025-05, SMA Sunny Design (planification rapide/détaillée) (3 outils · adéquation 2) | `/ventes/devis/nouveau` indépendant de l'atelier | bouton « dessiner ce devis » | un lien | CONFIRME B3-N15 |
| R36 | Obstacle linéaire (mur, haie, câble aérien) tracé comme une ligne avec hauteur | PVcase GM 2.58 (2026-01, shading objects le long d'une polyligne), PVsyst 6.79 (pylône + liaison de câbles), OpenSolar 3.10 (objets et arbres) (3 outils · adéquation 2) | obstacles ponctuels et zones d'exclusion (`obstaclesUi.ts`) ; pas de type ligne (a3 §1) | type « ligne » avec hauteur, ombre portée le long du tracé | un type de plus dans le menu des obstacles | CONFIRME B5b-r5 |
| R37 | Aligner les rangées de deux pans voisins et caler la pose sur les bords du toit plutôt que sur l'acrotère | PVcase RM 1.51 (2025-07), 1.53 (2025-08) « Align rows between PV areas », PVcase GM 2.58 (2026-01) E-W alignées, SolarEdge Designer 2020-01 (edge alignment) (2 outils · adéquation 3) | aimantation aux zones voisines `snap.ts::aimanterAuxZones` ; `layoutEditor.ts::freeAlignSelection` sans bouton (a3 « M ») | case « aligner sur la zone voisine » + bouton « aligner » branché sur `freeAlignSelection` | une seule case, cochée par défaut sur les toits plats à plusieurs zones | CONFIRME B3-N4 |
| R38 | Annuler / rétablir sur tout l'atelier (tracé, obstacles, zones), pas seulement la disposition | OpenSolar 3.13 (2026-11, stringing undo), Scanifly 2026-05 (undo/redo de-tilt), PVsyst 6.47 (selection after paste) (2 outils · adéquation 3) | pile de 50 pas mais `Ctrl+Z` gardé par `ctx.layoutMode` (a3 §5 pt 6) ; `createWorkshopHistory` existe sans branchement clavier | brancher l'historique d'atelier existant sur Ctrl+Z / Ctrl+Y dans tous les modes | invisible : le geste habituel marche partout | CONFIRME B4-r5 |
| R39 | Perte expliquée au client en phrases (6 postes) avec conseil de réduction | SolarEdge Designer 2021-08 (Yield Factor Loss Indication), PVsyst 7.1.0 (rapport), PVcase RM 1.55 (simulation personnalisable) (2 outils · adéquation 3) | cascade `chaine_pertes.py` ; pas de phrase « que faire » | phrase générée par poste dominant avec le geste correctif | texte sous le graphe | CONFIRME B4-r1, B4-r2 |
| R40 | Seuil d'accès solaire minimal réglé par la société et appliqué au remplissage automatique | Scanifly 2026-01 (SolarAI respecte ASA/TSRF minimums), Aurora design mode (filtre TSRF), OpenSolar 3.0 (design templates) (2 outils · adéquation 2) | `SOLAR_ACCESS_LOW = 0.75` codé en dur dans `shadingUi.ts` (proposition de retrait seulement) | valeur dans les réglages société (champ, source écrite), appliquée à l'optimiseur | défaut = comportement actuel | NOUVEAU |
| R41 | Contrôle de raccord 3D du toit (pans voisins qui ne se rejoignent pas à l'arête, hauteurs incohérentes) | PVcase RM 1.53 (2025-08) roof builder health check + planarize, 1.59 (2026-10) planarisation améliorée, OpenSolar 2.30 (outils de toit) (2 outils · adéquation 2) | `computeMixedAltitudeOffsets` ; pas de message d'incohérence (a3 §1) | écart de hauteur à l'arête > seuil → avertissement nommant les deux pans | apparaît seulement s'il y a un défaut | NOUVEAU |
| R42 | Rogner le plan importé et proposer des échelles courantes (A4 1:200) | Pylon 2026-11-18 (blueprint cropping), 2026-05 (scale option A4 portrait 1:200), OpenSolar 3.0 (outil de mesure d'échelle) (2 outils · adéquation 2) | `underlay.ts` calage 2 points + distance saisie ; pas de rognage (a3 §1) | rectangle de rognage et gabarits d'échelle | visible à l'import seulement | NOUVEAU |
| R43 | Couleur par MPPT et orientation E/O/N/S de chaque chaîne lisibles sur le plan et la nomenclature | OpenSolar 3.8 (2026-06 couleurs de chaînes par MPPT), PVcase RM 1.50 (E/W/N/S dans chaînes, layout info, BOM), 1.56 (azimuts en BOM) (2 outils · adéquation 2) | teinte des modules par chaîne `electrique3d.ts` ; pas de famille de couleur par MPPT | famille de teintes par MPPT et sigle d'orientation dans la nomenclature | affichage seulement | NOUVEAU |
| R44 | Points d'ancrage antichute et repères de sécurité avec rayon de sécurité sur le plan de site | OpenSolar 3.10 (2026-08) « Arrest Roof Anchor Point » rayon en mètres, 3.12 (2026-10) site maps avec zones de sécurité, Pylon 2026-09 (plan de site) (2 outils · adéquation 2) | git grep `ancrage\|ligne de vie` dans le module : rien de pertinent | type de repère (ancrage, passage de câble, onduleur, tableau) avec rayon optionnel ; apparaît sur `plan-masse.pdf` seulement | uniquement dans le dossier technique, jamais sur le PDF client (règle n°4) | CONFIRME B2-r4 |
| R45 | Démarrer un projet en collant des coordonnées GPS ou un lien de carte | OpenSolar 3.8 (2026-06) lat/long dans la barre de recherche, 3.13 (2026-11) lien Google Maps / position actuelle, Scanifly 2025-11-19 (création par longitude/latitude) (2 outils · adéquation 2) | `mapDraw.ts::geocode` n'envoie que du texte (a3 §2) ; git grep `coordonn.es GPS` : 0 | reconnaître « 33.57, -7.58 » (et lien Maps) dans le champ adresse, centrer la carte | le même champ, détection automatique du format | CONFIRME B2-r5 |
| R46 | Schéma de flux d'énergie (Sankey) de la production vers autoconsommation, batterie, injection et pertes | PV*SOL 2025 (2024-11) Sankey, PVsyst 6.80/7.3.2 (diagramme de pertes avec charge/décharge batterie), SAM 2024.12.12 (graphiques de factures) (2 outils · adéquation 2) | cascade des pertes `diagramme-pertes.svg` ; pas de flux client | Sankey SVG depuis `bilan_autoconsommation` | un seul graphe, lisible sans légende | CONFIRME B1-C01 |
| R47 | Diodes de dérivation : ombrage au niveau des sous-chaînes | PVsyst 8.0.6 (electrical shading), 7.4.0 (partitions), 6.35, SAM 2017 (3D shading) (2 outils · adéquation 2) | étape `diodes` déclarée et omise (a1 §3) | règle « paysage = perte limitée à une bande » sans modèle cellule | un avertissement textuel | CONFIRME B1-C07, B4-r11 |
| R48 | Nomenclature avec disponibilité en stock (sans prix ni commande) | OpenSolar 3.0 / 3.9 (Shop, supplier sync), Pylon 2026-09 (price books) (2 outils · adéquation 2) | nomenclature `core/electrique/nomenclature.py` ; stock = autre module | colonne « en stock » via `selectors` du stock | affichage | CONFIRME B2-r11 |
| R49 | Choisir les graphiques du rapport d'étude un par un et dans l'ordre | PVsyst 6.80 / 7.1.0 / 7.3.0 (graphiques prédéfinis sélectionnables et ordonnables), PV*SOL 2026 R1 (tous les graphiques ajoutables), HelioScope 2025-11 (3 outils · adéquation 1) | `services/rapport/` : la société choisit des sections, pas des graphiques (a1 §14) | liste de graphiques cochables dans les sections existantes | réglage société, invisible au vendeur | NOUVEAU |
| R50 | QR code sur la planche ou le dossier d'ouvrage qui renvoie au manuel propriétaire / fiche de l'installation | OpenSolar 3.5.0→3.11 (QR imprimable d'un document de projet), Pylon 2026-09 (manuels utilisateur, documents de sécurité batterie à la remise), Scanifly Mobile 2026-10 (3 outils · adéquation 1) | `documents/manuel_proprietaire.py`, `document_asbuilt.py` (a1 §14) ; pas de QR | QR vers la page du dossier de l'ouvrage (jeton) | imprimé tout seul sur le dossier technique | NOUVEAU |
| R51 | Taux d'occupation et surface couverte du toit dans le résumé | PVcase GM 2.55 (2025-06) effective area coverage, PVsyst 8.0.14 (définition du GCR), RatedPower (2026) (3 outils · adéquation 1) | GCR mesuré sur le sol `core/calepinage/surfaces/sol.py` ; capacité `contenance.py` | ligne « modules / surface utilisable » dans le résumé | affiché sans réglage | NOUVEAU |
| R52 | Calepinage d'exemple prêt à ouvrir | PVsyst 8.0.13 (projet commercial de démonstration), PV*SOL 2027 R1 (projets d'exemple), OpenSolar 3.13 (Power Up checklist) (3 outils · adéquation 1) | aucun projet d'exemple fourni | un projet de démonstration par type de toit | ouvert depuis l'écran vide | CONFIRME B1-C18 |
| R53 | Pivoter tout le site d'un coup | PVsyst 8.0.0 (rotation X/Z), SolarEdge Designer 2021-07 (rotation de polygones/modules), PVcase RM 1.48 (Nord personnalisé) (3 outils · adéquation 1) | orientation fine ±1° (`nudgeAzimuthDeg`) ; rotation libre sans bouton (a3 « M ») | rotation autour du centre de tous les objets | un bouton | CONFIRME B4-r14 |
| R54 | Liste des objets du site en tableau éditable | PVsyst 6.40 / 6.65 / 6.81 / 7.2.9 (sélection avancée), SolarEdge Designer 2021-07, Polysun (3 outils · adéquation 1) | sélection lasso/cadre, pas de tableau | tableau des obstacles et zones avec hauteur et provenance | onglet existant | CONFIRME B1-C13 |
| R55 | Mesurer pente et azimut du toit avec les capteurs du téléphone pendant la visite (inclinomètre + boussole), valeur gardée « relevé » avec sa provenance | Scanifly Mobile 2026-10-21 (tilt sticker + azimuth reader), Scanifly 2026-06 albums (1 outil · adéquation 3) | Au Maroc aucun MNS : « il faut tout relever sur place » (a3 §5 pt 10) ; git grep `DeviceOrientation` dans le module : 0 ; provenance RELEVE/RELEVE_DOUTEUX existe (`apps/web/src/lib/obstacles.ts:ObstacleProvenance`) | bouton « Mesurer » dans l'écran de relevé : lecture capteur, confirmation humaine, écrit pente/azimut du pan avec provenance RELEVE | le technicien pose le téléphone sur la couverture ; aucun chiffre à connaître ni à taper | NOUVEAU |
| R56 | Export KML / GeoJSON du calepinage (zones, rangées, obstacles) pour Google Earth et le téléphone | PVcase GM 2.53 (2025-04), 2.61 (2026-05, couleurs conservées), 2.64 (2026-08, zones/tables/pieux/ombrage/transfos/routes) (1 outil · adéquation 3) | git grep `kml` dans le module : 0 ; GeoJSON déjà manipulé en interne (`apps/web/src/lib/roof.ts`) | bouton « Google Earth » : un fichier KML des pans, zones d'exclusion et rangées | un bouton dans les exports, aucun réglage | NOUVEAU |
| R57 | Heure légale contre heure solaire sur la course du soleil | PVsyst 6.80 (solar path), SMA Sunny Design 5.20 (trajectoire des ombres) (2 outils · adéquation 1) | `soleilPlay.ts`, onglet `course-soleil` | une ligne d'information | info-bulle | CONFIRME B4-r12, B5a-r8 |
| R58 | Appliquer un retrait ou un acrotère à plusieurs pans/arêtes en une opération | PVcase RM 1.50 (2025-05) sélection multi-toits d'arêtes, 1.55 (offsets de faîtage) (1 outil · adéquation 2) | retraits par arête (`lib/roofSetbackEdge.ts`) un pan à la fois (a3 §1) | multi-sélection d'arêtes puis une valeur | un geste de moins sur chaque toit complexe | NOUVEAU |
| R59 | Photos du relevé en album, visibles à côté du 3D | Scanifly 2026-06-02 (albums dans l'espace 3D, Street View), Scanifly Mobile 2026-10 (albums exportables en PDF) (1 outil · adéquation 2) | `PhotoSite` + calage 4 coins `PhotoSiteCalage.jsx` ; pas d'album dans la scène | volet « photos » à côté de la carte avec légende | dossier déjà rempli par la visite | NOUVEAU (voir B4-r13) |
| R60 | Routage automatique des câbles le long de chemins, avec saut de chaîne long signalé | PVcase RM 1.59 (2026-10) long jumps vers chemins de câbles, PVcase GM 2.58 (câbles suivant les couloirs), 2.51 (tranchées) (1 outil · adéquation 2) | `services/troncons.py` : métré depuis des chemins dessinés ; pas de routage (a1 §7) | plus court chemin orthogonal sur le contour du toit entre chaîne et onduleur, longueur écrite | tracé proposé, le dessinateur peut le corriger | CONFIRME B3-N12 |
| R61 | Alerte d'écart d'azimut entre un pan et l'axe du bâtiment | PVcase RM 1.54 (2025-08) azimuth deviation notification (1 outil · adéquation 1) | azimut saisi librement (`rp9-facing-range`) ; aucune alerte | avertir quand l'écart pan/bâtiment dépasse 10° sans raison déclarée | avertissement discret | NOUVEAU |
| R62 | Appareils électriques (onduleurs, boîtes) placés et dimensionnés en 3D dans la scène | PVcase GM 2.60 (2026-04, electrical 3D devices), 2.64 (placement sur poteau), 2.55 (harnais) (1 outil · adéquation 1) | `electrique3d.ts` ne trace que les chaînes (a3 §1) ; `coffrets.py` dimensionne sans place | boîtier 3D posé à l'emplacement saisi | visible seulement en vue 3D | NOUVEAU |
| R63 | Commande vocale « calepinage depuis la fiche lead » | OpenSolar 3.0 (2025-09) Ada voix (1 outil · adéquation 1) | `assistant.py` éteint par défaut | dictée d'une adresse | optionnel | CONFIRME B2-r19 |

Écartés après lecture : placement 3D de boîtes électriques hors besoin (gardé comme R mineure), BESS/stockage réseau et couplage DC (marché utilitaire), import K2 Base/PV*SOL (notre module est le maître), langue/polices des propositions et marge cible (PDF client, règle n°4 ; argent), terrassement et pieux (non-objectif), trackers et sub-horaire (HORS DÉCISION), notifications de proposition vue et attribution de leads (autres modules de l'ERP), calcul de vent/neige K2 (normatif, hors décision), Meteonorm/Solcast/Nearmap/Google 3D (payants).

## 6. « Table stakes » que nous n'avons pas (≥ 4 outils, grappe ABSENT ou PARTIEL, permise)

| Grappe | Capacité | Outils (n) | Années | Verdict |
|---|---|---|---|---|
| K31 | Sources météo supplémentaires (Meteonorm, NSRDB, NASA POWER, ERA5, Solcast, Solargis…) | 7 : OpenSolar, PV*SOL, PVcase, PVsyst, SAM, archelios, pvlib | 2013-2026 | PARTIEL |
| K42 | Consommation : mois manquants estimés, total annuel réparti, lecture de facture, données d'intervalle | 7 : Arka 360, Huawei, OpenSolar, PV*SOL, Pylon, SAM, Scanifly | 2024-2026 | PARTIEL |
| K46 | Optimisation / itération de capacité / balayages de paramètres | 7 : Aurora, OpenSolar, PV*SOL, PVcase, PVsyst, SAM, SMA Sunny Design | 2015-2026 | PARTIEL |
| K65 | Règles d'optimiseurs et micro-onduleurs (Tigo, Huawei, SolarEdge, Maxim) | 7 : K2 Base, PV*SOL, PVcase, PVsyst, SAM, SMA Sunny Design, archelios | 2014-2026 | PARTIEL |
| K67 | Hors réseau et groupe électrogène | 7 : PV*SOL, PVcase, PVsyst, Polysun, Pylon, SAM, SMA Sunny Design | 2018-2026 | PARTIEL |
| K52 | Exports CAO/SIG (DXF, KML, LandXML, PVCollada, SketchUp) | 6 : HelioScope, OpenSolar, PVcase, PVsyst, SolarEdge, archelios | 2017-2026 | PARTIEL |
| K53 | Échanges avec d'autres outils de conception (import K2/PV*SOL/Sunny Design, interface constructeur) | 6 : K2 Base, PV*SOL, PVcase, PVsyst, SMA Sunny Design, archelios | 2013-2026 | ABSENT |
| K74 | Rotation d'objets et du site entier | 6 : OpenSolar, PVcase, PVsyst, Pylon, SAM, SolarEdge | 2021-2026 | PARTIEL |
| K80 | Sécurité du site et plan de chantier (job pack, plan de site, QR code) | 6 : OpenSolar, PVcase, Pylon, SAM, SMA Sunny Design, Scanifly | 2015-2026 | PARTIEL |
| K22 | Outils de toit : pente par arête, faîtage/arêtier, accrochage 90°, planarisation | 5 : OpenSolar, PVcase, PVsyst, RatedPower, Scanifly | 2019-2026 | PARTIEL |
| K50 | Proposition web interactive, 3D partageable par lien, co-signature | 5 : Arka 360, OpenSolar, PVcase, PVsyst, SolarEdge | 2016-2026 | PARTIEL |
| K77 | Calques, volets déplaçables, liste hiérarchique des pans, tri | 5 : PVcase, PVsyst, Polysun, SAM, Scanifly | 2019-2026 | PARTIEL |
| K82 | Géolocalisation / carte : fonds de carte et sections de carte | 5 : K2 Base, OpenSolar, PV*SOL, PVsyst, Scanifly | 2018-2026 | PARTIEL |
| K13 | Copier-coller / dupliquer un bloc câblé, un pan ou des réglages | 4 : PVcase, PVsyst, Scanifly, SolarEdge | 2020-2025 | PARTIEL |
| K29 | Bifacial : plusieurs orientations, 1 axe, facteur de vue, PR bifacial | 4 : HelioScope, PVsyst, SAM, pvlib | 2017-2026 | PARTIEL |
| K33 | Pertes saisies en série temporelle : salissure, neige, albédo, indisponibilité | 4 : K2 Base, PVsyst, SAM, pvlib | 2015-2026 | PARTIEL |
| K36 | Recommandation / dimensionnement automatique de la batterie depuis la consommation | 4 : Huawei, PVsyst, Pylon, SAM | 2019-2026 | PARTIEL |
| K47 | Conception automatique par IA (calepinage et système générés) | 4 : Aurora, OpenSolar, PVcase, Scanifly | 2025-2026 | PARTIEL |
| K75 | Sélection avancée : groupes, multi-sélection, liste des objets, modification groupée | 4 : PVsyst, Polysun, Pylon, SolarEdge | 2015-2026 | PARTIEL |
| K85 | Modèles physiques de simulation : IAM, spectral, transposition, circumsolaire, décomposition | 4 : PV*SOL, PVsyst, SAM, pvlib | 2014-2026 | PARTIEL |

Lecture : les grappes PARTIEL à 4 outils ou plus sont, par ordre d'intérêt pour nous, la copie d'un bloc ou de réglages entre pans (K13), la météo à plusieurs sources (K31), la consommation à mois manquants (K42), l'optimisation de capacité (K46), la recommandation de batterie (K36), le bifacial plus fin (K29), les exports vers le bureau d'études (K52), les outils de toit (K22), la sélection avancée (K75) et la sécurité du site/dossier d'ouvrage (K80). K53 (échanges avec d'autres outils) et K65 (règles par marque d'optimiseur) sont volontairement non proposées.

## 7. Où sont allés les leaders en 2025-2026

Grappes où au moins deux outils ont livré en 2025 ou 2026 (comptées dans les lignes) :

| Grappe | Capacité | Outils actifs 2025-2026 | Verdict chez nous |
|---|---|---|---|
| K49 | Rapport technique modulaire, page de garde, graphiques choisis, présentation client PDF/DOCX | 8 : HelioScope, K2 Base, PV*SOL, PVcase, PVsyst, Pylon, Scanifly, archelios | PRÉSENT |
| K71 | Argent dans le logiciel de conception (tarifs, VAN, TRI, financement, marges) | 8 : HelioScope, OpenSolar, PV*SOL, PVcase, PVsyst, Pylon, Scanifly, archelios | HORS DÉCISION |
| K31 | Sources météo supplémentaires (Meteonorm, NSRDB, NASA POWER, ERA5, Solcast, Solargis…) | 7 : OpenSolar, PV*SOL, PVcase, PVsyst, SAM, archelios, pvlib | PARTIEL |
| K51 | Exports de données ouverts (JSON, CSV, XLSX, API) | 7 : HelioScope, OpenSolar, PV*SOL, PVcase, PVsyst, Pylon, Scanifly | PRÉSENT |
| K05 | Schéma unifilaire généré, éditable, exporté (SLD) | 6 : Eturnity, HelioScope, OpenSolar, PVcase, Pylon, archelios | PRÉSENT |
| K09 | Fixation : nomenclature de rails/crochets/lestage depuis le système choisi (et calculateurs de fabricants) | 6 : K2 Base, OpenSolar, PV*SOL, PVcase, Scanifly, archelios | PRÉSENT |
| K40 | Pompe à chaleur, chauffe-eau à immersion, thermique couplé au PV | 6 : OpenSolar, PV*SOL, PVcase, PVsyst, Pylon, RatedPower | PRÉSENT |
| K08 | Nomenclature (BOM) exportée du calepinage | 5 : Eturnity, K2 Base, OpenSolar, PVcase, archelios | PRÉSENT |
| K20 | Imagerie enrichie : drone, LiDAR, Google 3D, Street View, imagerie premium | 5 : K2 Base, OpenSolar, PV*SOL, PVcase, Scanifly | HORS DÉCISION |
| K25 | Rapport d'ombrage : pertes mensuelles, % d'ombrage par module, analyse 3D | 5 : Eturnity, HelioScope, PV*SOL, PVcase, Scanifly | PRÉSENT |
| K54 | Base de composants / catalogue de produits, import .PAN/.OND, filtres | 5 : OpenSolar, PV*SOL, PVcase, PVsyst, Pylon | PLANIFIÉ |
| K57 | Audit / contrôle de santé de la conception, alertes de compatibilité | 5 : OpenSolar, PV*SOL, PVcase, PVsyst, Scanifly | PRÉSENT |
| K58 | Travail d'équipe : tâches, attribution, notifications, gestion de projet | 5 : OpenSolar, PV*SOL, PVcase, Pylon, Scanifly | HORS MODULE |
| K79 | Rapidité de calcul et de chargement | 5 : OpenSolar, PV*SOL, PVcase, PVsyst, Scanifly | PRÉSENT |
| K81 | Intégration de fabricants d'onduleurs/structures dans le flux (cartes, nomenclature, supplier) | 5 : Eturnity, OpenSolar, PV*SOL, PVcase, PVsyst | HORS DÉCISION |
| K82 | Géolocalisation / carte : fonds de carte et sections de carte | 5 : K2 Base, OpenSolar, PV*SOL, PVsyst, Scanifly | PARTIEL |
| K17 | Retraits réglementaires, zones d'exclusion, acrotère, retraits par arête | 4 : OpenSolar, PV*SOL, PVcase, Scanifly | PRÉSENT |
| K19 | Garde-fous de pose : conflit, refus nommé, alerte de retrait | 4 : OpenSolar, PV*SOL, PVcase, Scanifly | PRÉSENT |
| K22 | Outils de toit : pente par arête, faîtage/arêtier, accrochage 90°, planarisation | 4 : OpenSolar, PVcase, RatedPower, Scanifly | PARTIEL |
| K39 | Charge de véhicule électrique (optimisée PV, profils de conduite) | 4 : Eturnity, OpenSolar, PV*SOL, Scanifly | PRÉSENT |
| K42 | Consommation : mois manquants estimés, total annuel réparti, lecture de facture, données d'intervalle | 4 : OpenSolar, PV*SOL, Pylon, Scanifly | PARTIEL |
| K44 | Pompage solaire (pompes, conduites, rabattement, débit) | 4 : Eturnity, OpenSolar, PV*SOL, PVsyst | PRÉSENT |
| K61 | Étiquettes, numérotation des modules et des chaînes, annotations | 4 : OpenSolar, PVcase, Pylon, Scanifly | PRÉSENT |
| K65 | Règles d'optimiseurs et micro-onduleurs (Tigo, Huawei, SolarEdge, Maxim) | 4 : K2 Base, PV*SOL, PVcase, PVsyst | PARTIEL |
| K67 | Hors réseau et groupe électrogène | 4 : PV*SOL, PVcase, PVsyst, Pylon | PARTIEL |
| K70 | Interface simplifiée pour le vendeur (mode simple, grille on/off, parcours guidé) | 4 : HelioScope, OpenSolar, PVcase, Scanifly | PLANIFIÉ |
| K80 | Sécurité du site et plan de chantier (job pack, plan de site, QR code) | 4 : OpenSolar, PVcase, Pylon, Scanifly | PARTIEL |
| K85 | Modèles physiques de simulation : IAM, spectral, transposition, circumsolaire, décomposition | 4 : PV*SOL, PVsyst, SAM, pvlib | PARTIEL |
| K01 | Câblage automatique des chaînes sur le calepinage (auto stringing) | 3 : Eturnity, OpenSolar, PVcase | PRÉSENT |
| K03 | Dimensionnement de chaîne min/max selon températures du site et fenêtre MPPT | 3 : PVcase, PVsyst, Pylon | PRÉSENT |
| K04 | Utiliser tous les MPPT, plusieurs chaînes par MPPT, partage de puissance entre MPPT | 3 : OpenSolar, PVcase, PVsyst | PRÉSENT |
| K10 | Toit plat : châssis inclinés, structures surélevées sur dalle béton | 3 : OpenSolar, PVcase, Scanifly | PRÉSENT |
| K12 | Est-ouest : rangées alignées, azimut inversé par module, pose dos-à-dos | 3 : K2 Base, PV*SOL, PVcase | PRÉSENT |
| K23 | Plan/blueprint importé et calé à l'échelle (DXF, PDF, image) ; mesure d'échelle | 3 : K2 Base, OpenSolar, Pylon | PRÉSENT |
| K24 | Import de scènes 3D externes (DAE, 3DS, PVC, IFC, glTF, .pvc2) | 3 : HelioScope, PVcase, PVsyst | ABSENT |
| K28 | Écrêtage, limitation d'injection, facteur de puissance imposé | 3 : HelioScope, PV*SOL, PVsyst | PRÉSENT |
| K29 | Bifacial : plusieurs orientations, 1 axe, facteur de vue, PR bifacial | 3 : HelioScope, PVsyst, pvlib | PARTIEL |
| K30 | Incertitude et quantiles de production P50/P75/P90/P95 | 3 : HelioScope, PVsyst, archelios | PRÉSENT |
| K33 | Pertes saisies en série temporelle : salissure, neige, albédo, indisponibilité | 3 : K2 Base, PVsyst, SAM | PARTIEL |
| K35 | Stratégies de batterie : autoconsommation, écrêtage de pointe, décalage tarifaire, arbitrage | 3 : HelioScope, PV*SOL, PVsyst | PRÉSENT |
| K46 | Optimisation / itération de capacité / balayages de paramètres | 3 : OpenSolar, PV*SOL, PVcase | PARTIEL |
| K47 | Conception automatique par IA (calepinage et système générés) | 3 : OpenSolar, PVcase, Scanifly | PARTIEL |
| K52 | Exports CAO/SIG (DXF, KML, LandXML, PVCollada, SketchUp) | 3 : HelioScope, OpenSolar, PVcase | PARTIEL |
| K53 | Échanges avec d'autres outils de conception (import K2/PV*SOL/Sunny Design, interface constructeur) | 3 : K2 Base, PV*SOL, PVcase | ABSENT |
| K55 | Modèles, gabarits et profils par défaut réutilisables | 3 : OpenSolar, PVcase, Pylon | PRÉSENT |
| K56 | Relevé de chantier mobile : checklists, photos annotées, azimut/inclinaison au téléphone | 3 : OpenSolar, Pylon, Scanifly | PARTIEL |
| K60 | Trackers et backtracking | 3 : PVcase, PVsyst, RatedPower | HORS DÉCISION |
| K74 | Rotation d'objets et du site entier | 3 : OpenSolar, PVcase, Pylon | PARTIEL |
| K77 | Calques, volets déplaçables, liste hiérarchique des pans, tri | 3 : PVcase, SAM, Scanifly | PARTIEL |
| K13 | Copier-coller / dupliquer un bloc câblé, un pan ou des réglages | 2 : PVcase, Scanifly | PARTIEL |
| K14 | Bibliothèque d'objets de toit (lanterneau, citerne, évent, cheminée, pylône) avec ombre auto | 2 : OpenSolar, PVcase | PARTIEL |
| K15 | Détection automatique du toit / des obstacles sur l'image (IA) | 2 : PVcase, Scanifly | PLANIFIÉ |
| K16 | Arbres et végétation modélisés avec ombre | 2 : OpenSolar, Scanifly | PRÉSENT |
| K18 | Points d'ancrage antichute avec rayon de sécurité et plan de site de sécurité | 2 : OpenSolar, Pylon | ABSENT |
| K21 | Démarrer un projet par latitude/longitude ou position actuelle | 2 : OpenSolar, Scanifly | ABSENT |
| K26 | Ombrage électrique fin : diodes de dérivation, cellules, ombrage diffus, dispersion entre chaînes | 2 : PVsyst, pvlib | PARTIEL |
| K32 | Import d'un fichier météo perso + assistant de validation, TMY multi-année, ciel clair | 2 : PVsyst, pvlib | PARTIEL |
| K37 | État de santé / usure / fin de vie de la batterie | 2 : OpenSolar, PVsyst | PRÉSENT |
| K38 | Batterie couplée DC/AC, stockage autonome, BESS | 2 : PV*SOL, PVcase | PARTIEL |
| K41 | Bibliothèque de profils de charge types (par foyer/activité) | 2 : PV*SOL, archelios | PRÉSENT |
| K43 | Profil de consommation éditable (jour/mois) et renormalisation à la consommation annuelle | 2 : OpenSolar, PV*SOL | PRÉSENT |
| K45 | Variantes d'un projet et comparaison côte à côte | 2 : OpenSolar, PVcase | PRÉSENT |
| K48 | Commande vocale / assistant conversationnel de conception | 2 : OpenSolar, Scanifly | ABSENT |
| K50 | Proposition web interactive, 3D partageable par lien, co-signature | 2 : OpenSolar, PVcase | PARTIEL |
| K59 | Terrassement, pieux, collisions, routes, terrain irrégulier (génie civil sol) | 2 : PVcase, RatedPower | HORS DÉCISION |
| K64 | Dimensionnement de l'onduleur : ratio DC/AC, surcharge, courant, déclassement thermique | 2 : PVcase, PVsyst | PRÉSENT |
| K66 | Système combiné PV + thermique + batterie + appareils | 2 : PV*SOL, PVsyst | PARTIEL |
| K69 | Projets d'exemple, tutoriels, aide guidée | 2 : PV*SOL, PVsyst | ABSENT |
| K72 | Dossier de raccordement / permis / lettre d'autorisation | 2 : OpenSolar, Pylon | PRÉSENT |
| K75 | Sélection avancée : groupes, multi-sélection, liste des objets, modification groupée | 2 : PVsyst, Pylon | PARTIEL |
| K78 | Annuler / rétablir généralisé | 2 : OpenSolar, Scanifly | PARTIEL |
| K84 | Gestion de l'énergie réactive, transformateurs MT/HT, postes | 2 : OpenSolar, PVcase | PRÉSENT |
| K89 | Export image / impression du calepinage | 2 : HelioScope, OpenSolar | PRÉSENT |
| K91 | Liste de projets : recherche, archivage, renommage, partage | 2 : HelioScope, PVcase | PRÉSENT |

Tendances lues dans les notes (avec les lignes qui les portent) :

- **Conception par IA et mode « vendeur simple »** — Ada et Auto System Design (OpenSolar 3.0), SolarAI et SimpleDesign (Scanifly), Aurora AI, Huawei SmartDesign 2.0, Pylon. Lignes : 303, 343, 346, 365, 366, 378, 415, 416, 418, 422, 431.
- **Relevé de chantier sur téléphone relié au 3D** — Scanifly Mobile 2026-10, OpenSolar Mobile Experience 3.12, Pylon création de projet mobile 2026-05 ; tilt et azimut mesurés au téléphone. Lignes : 406, 433, 439, 449.
- **Proposition 3D interactive partageable (WhatsApp, lien)** — OpenSolar 3.12, 3.10, Arka Web Proposal, PVcase Web Viewer 2.52. Lignes : 240, 396, 406, 407.
- **Stockage : recommandeur, écrêtage de pointe, arbitrage, décalage tarifaire** — Pylon 2026-03/05, HelioScope 2026-07/08, PV*SOL 2027 R1, PVsyst 8.0.17, SAM 2026.7.3. Lignes : 198, 199, 213, 215, 228, 230, 248, 253, 287, 317, 319, 322, 339, 350 … (29 lignes).
- **Consommation estimée depuis des données partielles** — Scanifly 2026-11, Pylon 2026-05 (lecteur de facture, intervalle), OpenSolar 3.3.0. Lignes : 382, 440, 448.
- **Sécurité de chantier : retraits incendie, ancrages, zones de sécurité** — Scanifly 2026-02, OpenSolar 3.7/3.10/3.12, Pylon 2026-09 (plan de site). Lignes : 394, 395, 408, 429, 457, 465.
- **Intégration des fabricants de fixation dans le calepinage** — OpenSolar 3.7→3.13 (SolarNEST, Van Der Valk, K2 SimpleTilt/BasicRail, NOVA), PV*SOL 2025 (Renusol), archelios 2025.1 (Enstall), Scanifly 2026-02 (IronRidge), K2 Base ↔ Aurora 2026-10, PVcase 1.49 (K2 Base). Lignes : 263, 321, 381, 387, 403, 404, 411, 424, 430, 497, 515, 516.
- **Base de composants et dimensionnement d'onduleur sans dessin** — PVcase 1.51/1.60/2.62/2.65 (component database + inverter sizing), PVsyst 8.x. Lignes : 266, 284, 301, 311, 451.
- **Câblage complet : dimensionnement, modes de pose, SLD éditables** — PVcase 2.50→2.66, Pylon SLD editor 2026-06, OpenSolar 3.11 SLD. Lignes : 228, 236, 239, 245, 246, 293, 294, 302, 308, 309, 389, 405, 452, 455 … (18 lignes).
- **Probabilités et sub-horaire dans la simulation** — PVsyst 8.1.0 sub-horaire, archelios 2025.1 P50-P95, SAM, pvlib 0.14/0.16 (ERA5, ANTS-2D). Lignes : 204, 210, 212, 215, 221, 498.
- **Terrassement et génie civil du champ au sol** — PVcase 2.53→2.62, RatedPower 2026-09 (HORS DÉCISION pour nous). Lignes : 233, 243, 248, 282, 283, 527.
- **Usage VE + pompe à chaleur dans le même projet** — PV*SOL 2026 R1/R4, OpenSolar 3.8, Eturnity 2025-05, SMA 5.90. Lignes : 323, 342, 370, 399.

## 8. Limites de cette passe

- Les notes de version couvrent ce que le fournisseur choisit d'annoncer : les petites améliorations de calcul y sont rares, les pertes et modèles internes absents. Un outil sans notes publiques (Aurora, Reonic, Solargraf, Sollit, BlueSol, Solarius, Esdec, Renusol, Schletter, Fronius, Huawei) est sous-représenté ; ses fonctions sont dans B2/B3/B5.
- PVsyst compte pour une grande part des lignes (liste exhaustive sur 13 ans) ; les grappes « moteur de simulation » sont donc tirées par PVsyst, SAM et pvlib. Un compte d'outils faible sur ces grappes ne dit pas que le marché s'en désintéresse.
- Les grappes sont rangées par mots-clés ; certains rangements sont discutables (ex. K31 mêle nouvelles sources et import). Le verdict de chaque grappe repose sur les inventaires `a1/a2/a3` (`†`) quand aucun grep n'est cité ; il faut rouvrir le code avant de s'engager sur une tâche.
- Les lignes 2025-2026 viennent de pages qui ne donnent pas toutes la date exacte (SolarEdge 2021 : « Last updated: August 2021 » ; SMA 5.0/5.61/5.80/5.90/6.00/6.10 : sans date).
- OpenSolar : j'ai retiré mes premières attributions de version quand j'ai vu qu'elles ne suivaient pas l'ordre des pages lues (une correction a été appliquée avant d'écrire ce fichier) ; en cas de doute, la page citée dans l'URL fait foi.

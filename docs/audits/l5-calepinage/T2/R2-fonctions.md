# R2 — Fonctions des meilleurs outils (novembre 2026) face au module calepinage

Date du rapport : 22/11/2026. Lane R2, axe FONCTIONS.

## Comment lire ce rapport (méthode et limites)

- Inventaire local : j'ai lu `id`, `etat`, `titre` des 961 tâches (503 cochées, 388 livrées non prouvées, 51 ouvertes, 19 gated) par recherche de mots dans les titres. Les titres sont tronqués à ma lecture : « déjà là » = un titre le dit clairement. Une fonction que je dis « ABSENT du plan » veut dire : aucun titre ne la mentionne. Un corps de tâche que je n'ai pas lu pourrait la couvrir ; à confirmer par grep sur les corps avant de créer une tâche.
- Sources web : primaires lues en entier (pages fetchées) = notes de version PVsyst (partie lue : 8.0.0 à 8.1.8, 100 000 premiers caractères sur 248 000), PV*SOL 2026 (page éditeur), PV*SOL 2027 (communiqué relayé par pv magazine DE), OpenSolar (page des mises à jour + notes OS 3.0 + page schéma unifilaire), Solargraf (récap T1 2026 + version de juin 2026), Scanifly (janvier 2026), RatedPower (webinaire T2 2026), K2 Base (page produit), Lorentz (aide du dimensionneur S), Eturnity (pv magazine, 9 mai 2025), pv magazine USA (Aurora, 22 sept. 2026), page Aurora AI v2 et page Aurora Lyra (non datées). Le reste vient de résultats de recherche (marqué « recherche seule » dans la section D).
- Aucun nom de société, client ou projet n'a été envoyé ; les requêtes ne contenaient que des noms de produits publics.
- Règle du dépôt à respecter : D-CALX-PAYANT interdit tout logiciel payant (vu dans ACAL486). Toutes les pistes « sans service payant » ci-dessous en tiennent compte.

---

## A. Tableau des écarts

Légende « chez nous » : déjà là = tâche cochée (coche) ; livré = code livré, preuve due ; prévu = ouvert/gated ; ABSENT = aucun titre ne la mentionne.
Valeur pour un installateur marocain : H / M / B. Coût : petit / moyen / gros. Payant : oui / non.

### A1. Études et simulation

| Fonction | Qui la livre (version, date, URL) | Ce que l'utilisateur voit | Chez nous | Valeur (Maroc) | Coût | Payant |
|---|---|---|---|---|---|---|
| Pas de temps sous-horaire (1, 5, 15 min) et correction d'écrêtage sous-horaire | PVsyst 8.1.0 (15/04/2026), 8.1.5 (12/08/2026), 8.1.7 (01/10/2026) — https://www.pvsyst.com/help/release-notes/index.html | Un écrêtage onduleur moins sous-estimé quand le ratio DC/AC est élevé | ABSENT (nous avons écrêtage horaire : ACAL141 coche, ACAL477 coche, ACAL740 livré) | B (utile surtout au C&I à fort ratio DC/AC) | moyen | non (mais il faut des données sous-horaires : PVGIS n'en donne pas ; Meteonorm synthétique = payant) |
| Modèle thermique transitoire du module | PVsyst 8.1.0 (15/04/2026) | Température de module plus juste quand le ciel varie | ABSENT (déclassement thermique onduleur ACAL740 livré ; pas de modèle transitoire module) | B | moyen | non |
| Importer une météo mesurée sur site (CSV) via un assistant, plusieurs années | PVsyst 8.1.0, 8.1.5 (multi-années CSV) | On remplace le TMY par des mesures du client | ABSENT (nous lisons PVGIS ; ACAL455 lit un fichier d'horizon, pas une météo) | B | moyen | non |
| Salissure (soiling) et indisponibilité lues d'une série CSV | PVsyst 8.1.0 (soiling), 8.1.6 (indisponibilité, 16/09/2026) | Calendrier réel de nettoyage ou de pannes dans la simulation | Partiel : salissure mensuelle saisie (ACAL135 coche) ; pas de série ni de calendrier de nettoyage | H (poussière, sirocco, nettoyage = gros sujet au Maroc) | petit | non |
| Albédo en série CSV (bifacial) | PVsyst 8.1.2 (06/05/2026) | Albédo variable dans l'année | Déjà là en partie : table d'albédo par surface ACAL747 (coche), ACAL748 (livré), bifacial infinite sheds ACAL465 (coche) | B | petit | non |
| Dégradation d'état de santé batterie (capacité utile diminue) dans la simulation | PVsyst 8.1.4 (01/07/2026) | Productible batterie réaliste sur 10-15 ans | ABSENT du module (côté devis : règle des cycles D-BATCYC, hors module) | M | moyen | non |
| Indicateurs de probabilité P50 à P95 | archelios Pro 2025.1 (21/11/2025, recherche seule) ; PVsyst | Fourchette de production bancable | Déjà là : ACAL443, ACAL313 (coche), ACAL8, ACAL49-52 (coche) ; P99 gated ACAL457 | — | — | — |
| Correction spectrale personnalisée (First Solar) | PVsyst 8.1.6 | Précision pour modules couche mince | ABSENT | B (peu de couche mince au Maroc) | petit | non |
| Comparaison de notre simulation à un rapport PVsyst réel | (pratique d'étude sérieuse) | Preuve de justesse devant un financeur | Prévu : ACAL486 (gated, attend un rapport réel de Reda) ; golden ACAL382 coche | M | petit | non |
| Météo Meteonorm 9 par défaut | PV*SOL 2026 (24/11/2025), archelios 2025.1 (21/11/2025), PVsyst 8.1.0 | Base météo « de référence » du marché | Non applicable : Meteonorm est payant ; nous avons PVGIS + horizon (ACAL124, ACAL458) | — | — | oui (ne pas copier) |

### A2. Site, toit, détection

| Fonction | Qui la livre | Ce que l'utilisateur voit | Chez nous | Valeur | Coût | Payant |
|---|---|---|---|---|---|---|
| Modèle 3D du toit en ~10 s par IA, détection d'obstacles améliorée (+25 %) | Aurora AI v2 (non daté, page copyright 2026) — https://aurorasolar.com/?p=15795 | On saisit l'adresse, le toit est tracé | Déjà là : détection du toit par IA ACAL391, ACAL485, ACAL488, ACAL530, ACAL1049 (coche), ACAL531 (livré) | — | — | — |
| Conception automatique en un clic à partir de n'importe quelle source de prospect | OpenSolar OS 3.0 (2025) — https://www.opensolar.com/?p=14518 | Un projet naît déjà dessiné | Déjà là : ACAL421 (coche) ; balayage orientation ACAL468 (coche) | — | — | — |
| Pose automatique qui respecte un accès solaire minimal (TSRF/ASA) | Scanifly janvier 2026 — https://scanifly.com/?p=8816 | Aucun module posé sous un seuil d'ensoleillement | Livré : seuil d'accès solaire ACAL548 ; accès solaire par module ACAL137, ACAL138 (coche) | — | — | — |
| Retraits (setbacks) par type d'arête (faîte, égout, autre), classification par IA | Scanifly janvier 2026 | Retraits différents au faîte et à l'égout, profils enregistrés | Partiel : réglages société de dégagement par type ACAL256 (coche), types d'arêtes ACAL78 (coche) ; classification auto par IA ABSENT | B (retraits marocains peu normés ; IA coûteuse) | moyen | non |
| Carte de chaleur d'ensoleillement par module, rapport d'ombrage | Scanifly (mai 2026, photos dans la scène 3D) ; Arka 360 (recherche seule) ; Solargraf visualiseur T1 2026 | On voit le module le plus ombré | Déjà là : ACAL436, ACAL441 (livré), ACAL224-225 (coche), ACAL449 (livré), ACAL434 (livré, ombre 3D par heure et saison) | — | — | — |
| Photos de drone / d'étage et rue dans la scène 3D | Scanifly mai 2026 ; Aurora « drone mapping » amélioré (annoncé 22/09/2026, « bientôt », sans date) | Photos de terrain rattachées au toit | Partiel : orthophoto de drone calée ACAL424 (coche), relief de drone GeoTIFF ACAL534 (coche), ACAL535 (livré), photos du site ACAL13 / ACAL892 (livré) ; photogrammétrie (créer le modèle depuis les photos) ABSENT | M | gros | non (OpenDroneMap est libre mais lourd) |
| Import d'un modèle 3D de bâtiment par LiDAR (100 m autour) | PV*SOL 2026 (interface Rexplorer, Intersolar 05/2026, Allemagne seulement) ; Solargraf juin 2026 (choix lidar/DSM) | Bâtiment importé automatiquement | Non transposable : pas de LiDAR national au Maroc ; empreinte OSM + hauteur OSM ACAL421, ACAL504 (livré) ; relief Copernicus GLO-30 ACAL466 (livré) | B (indisponible) | — | oui (ne pas copier) |
| Terrain en pente : posage suivant le relief (suiveurs, terrassement) | RatedPower T2 2026 (terrain-following, earthworks) ; PVcase 2.62 (recherche seule) | Rangs qui suivent le terrain | Partiel : pente lue (ACAL466, ACAL66) mais ACAL75 dit que la pente du terrain n'entre PAS dans le calcul | M (champs au sol et agri en pente) | moyen | non |
| Objets proches d'ombrage (poteaux, arbres) | RatedPower T2 2026 ; Scanifly (septembre 2025, arbres) | Ombre des arbres/poteaux modélisée | Déjà là : poteaux ACAL500 (livré), obstacles et mesure par ombre ACAL497 (livré) | — | — | — |

### A3. Électrique

| Fonction | Qui la livre | Ce que l'utilisateur voit | Chez nous | Valeur | Coût | Payant |
|---|---|---|---|---|---|---|
| Schéma unifilaire généré automatiquement, éditable, par pays | OpenSolar SLD (AU, US, UK, DE, IT, ES) — https://www.opensolar.com/single-line-diagrams/ ; Eturnity (09/05/2025) ; Aurora (éditeur SLD Europe) ; PVsyst 8.1.0 (circuit AC vue unifilaire) | Schéma prêt à joindre | Déjà là : ACAL55, ACAL160, ACAL161, ACAL163, ACAL168 (batterie), ACAL162 (micro-onduleurs) (coche) | — | — | — |
| Schéma TRIFILAIRE (3 lignes) et pages de calcul détaillées, export DWG | Solargraf (outil « TLD », date non vue) ; Solargraf juin 2026 (auto-stringing triphasé) | Pièce exigée par certains gestionnaires pour les systèmes complexes | ABSENT (unifilaire seulement) | M (C&I MT/triphasé) | moyen | non |
| Plan de câblage, cheminement de câbles, chute de tension | Eturnity (plans de chaînes) ; PVcase 2.60/2.62 (3D électrique, câblage continu) | Longueurs et sections par tronçon | Déjà là : ACAL472 (cheminement, coche), ACAL635 (livré), ACAL260, ACAL269 (plan de câblage, coche), ACAL150, ACAL154 (coche) | — | — | — |
| Plus de deux chaînes par MPPT, optimiseurs, micro-onduleurs | PVsyst 8.1.5 (12/08/2026), 8.0.0 (optimiseurs) | Combinaisons onduleur/optimiseur réelles | Déjà là : ACAL56, ACAL149, ACAL615, ACAL162 (coche) ; vérifier le cas « plus de 2 chaînes/MPPT » (non trouvé dans les titres) | B | petit | non |
| Base de composants (modules/onduleurs) et dimensionnement onduleur | PVcase 2.62 (Intersolar 06/2026, recherche seule) ; PVsyst 8.0.0 (.PAN/.OND) | Fiches techniques toutes prêtes | Partiel : fiche technique et courbe dans `stock` (SPL110, SPL111, coche) ; import de fichiers .PAN/.OND ABSENT | M | petit | non |
| Dimensionneur par constructeur (SolarEdge, Huawei, Sungrow) avec design auto en un clic | Huawei SmartDesign 2.0 (2022, pv-tech) ; Sungrow iSolarDesign (11/2025) ; SolarEdge Designer | Électrique et nomenclature automatiques | Équivalent générique déjà là (voir ci-dessus) ; liaison constructeur ABSENT | B (verrouille sur une marque) | gros | non |
| Recette de mise en service (IEC 62446), courbes I-V | (pratique) | Dossier de fin de chantier | Hors module ou déjà là : ADRG16 (coche) | — | — | — |

### A4. Structure, lestage, fixation

| Fonction | Qui la livre | Ce que l'utilisateur voit | Chez nous | Valeur | Coût | Payant |
|---|---|---|---|---|---|---|
| Vent et neige calculés automatiquement, ballast et fixations dimensionnés, rapport PDF avec taux d'utilisation | K2 Base (page produit, non datée ; mise à jour 06/2025 : limite de pression sur l'isolant) — https://k2-systems.com/en/digital-services/k2-base/ ; Esdec (calculateur certifié Peutz, recherche seule) ; IronRidge BX (recherche seule) | Plan de lestage + justificatif de charge | Partiel : plan de lestage par zones centre/rive/coin ACAL563, ACAL564 (coche), ACAL565, ACAL572 (livré) ; vérification de charge totale vs portance, vent/neige calculés ABSENT | H (toits plats C&I : la question « le toit tient-il ? ») | moyen à gros | non |
| Nomenclature de fixation et BOM de montage par fournisseur | OpenSolar 3.8-3.11 (Fast-Rack Canada, calculateur AU) ; Scanifly + IronRidge (01/2026) | BOM exportée | Déjà là : ACAL81 (coche), ACAL598 (échafaudage, livré) | — | — | — |
| Suiveurs (trackers) | RatedPower, PVsyst 8.0.0 | Rangs mobiles | ABSENT | B | gros | non |

### A5. Consommation, stockage, tarifs

| Fonction | Qui la livre | Ce que l'utilisateur voit | Chez nous | Valeur | Coût | Payant |
|---|---|---|---|---|---|---|
| Tarifs dynamiques (série horaire/quart d'heure sur un an), suppléments (réseau, livraison) | PV*SOL 2027 (12/11/2026) — https://www.pv-magazine.de/unternehmensmeldungen/pvsol-premium-2027-veroeffentlicht-jetzt-mit-dynamischen-stromtarifen-neuen-optionen-im-energiemanagement-von-batteriespeichern-und-einer-noch-leistungsfaehigeren-3d-planung/ ; Solargraf T1 2026 (24/04/2026, upload de tarifs horaires) | Économies calculées heure par heure au vrai tarif | ABSENT du module (aucun titre ne parle de tarif ; le moteur de devis les calcule peut-être ailleurs : à vérifier hors module) | H | moyen | non (tarifs ONEE/régies à saisir ; pas de service) |
| Tarifs à puissance souscrite / prix de la puissance, effet écrêtage de pointe | PV*SOL 2027 (12/11/2026) ; PVsyst 8.0.17 (22/10/2025, décalage de puissance vers une période plus chère) ; HelioScope stockage intégré (16/06/2026, recherche seule) | On voit combien PV + batterie réduit la pointe | ABSENT (ACAL157/158/175 gèrent la puissance souscrite pour le raccordement, pas l'économie de pointe) | H (C&I) | moyen | non |
| Options de gestion de batterie : charge différée, soutien réseau, écrêtage de pointe, réserve de secours, tarif dynamique | PV*SOL 2027 (12/11/2026) ; PVsyst 8.0.17 | Choix de la stratégie | Partiel : stratégies ACAL166, ACAL167 (coche), ACAL788, ACAL792 (livré), secours ACAL798, ACAL799 (livré), hors réseau ACAL790-791 ; écrêtage de pointe/tarif ABSENT | M | moyen | non |
| Profils de charge types (climatisation, télétravail, seniors), favoris | PV*SOL 2026 (24/11/2025) | Bibliothèque de profils | Partiel : profil du lead, appareils, charges à venir (voiture, PAC, clim.) ACAL21, ACAL310, ACAL780 (livré) ; bibliothèque de profils types ABSENT | M | petit | non |
| Tarif distinct par consommateur (maison, voiture, PAC) avec compteurs au schéma | PV*SOL 2026 | Chaque charge a son tarif | ABSENT | B | moyen | non |
| Voiture électrique par jour de semaine | Solargraf T1 2026 | Recharge réaliste | ABSENT (ACAL780 ajoute une charge, sans jour de semaine ; à confirmer) | B | petit | non |
| Chauffe-eau / PAC branchés sur la batterie | PV*SOL 2026 ; Aurora 22/09/2026 (CVC + VE + batterie dans une même proposition) | Surplus utilisé par un ballon | Partiel : charges ACAL780 ; pas de ballon dimensionné comme tel | M (chauffe-eau solaire électrique répandu) | moyen | non |
| Plafond d'injection / injection limitée | PVsyst 8.1.0 (seuil depuis CSV) | Surplus écrêté | Déjà là : ACAL155, ACAL156, ACAL1187 (coche), ACAL783 (livré) | — | — | — |
| Bilan carbone évité | (courant) | Chiffre CO2 | Prévu : ACAL765 (gated : attend un facteur d'émission marocain daté) | B | petit | non |

### A6. Pompage solaire

| Fonction | Qui la livre | Ce que l'utilisateur voit | Chez nous | Valeur | Coût | Payant |
|---|---|---|---|---|---|---|
| Choix de la pompe par besoin d'eau, avec champ PV et schéma de modules ; coût le plus bas par m³ signalé ; sortie mensuelle et horaire | Lorentz (dimensionneur S, aide en ligne, non datée) — https://lorentz.de/s/help/1720/how-to-size-your-pumping-system | Une étoile sur l'option la moins chère au m³ | Déjà là : débit à la HMT, pompe, variateur, m³ mensuels ACAL806-811, ACAL834, ACAL877, ACAL1114 ; coût au m³ ABSENT | M | petit | non |
| Dimensionner de trois façons : par besoin, par nombre de panneaux, par pompe déjà en stock ; hors ligne puis synchronisation | Grundfos GO Solar (recherche seule ; page non lue) | Appli de terrain | Partiel : pompe existante décidée côté devis (D-AGR) ; « par nombre de panneaux » ABSENT ; hors ligne ACAL945, ACAL892 (livré, générique) | M | petit | non |
| Remplissage de réservoir jour par jour, niveau d'eau qui varie | (pratique) | Autonomie en eau | Déjà là : ACAL807 (livré), ACAL806 (coche) ; ouvert ACAL1267 | — | — | — |

### A7. Documents, vente, permis, collaboration

| Fonction | Qui la livre | Ce que l'utilisateur voit | Chez nous | Valeur | Coût | Payant |
|---|---|---|---|---|---|---|
| Présentation client PDF/DOCX après l'étude | PV*SOL 2026 (24/11/2025) | Résumé prêt | Déjà là en PDF : présentation compacte ACAL50, planche A3, rapport d'étude ACAL757 (livré) ; DOCX ABSENT | B | petit | non |
| Export JSON des résultats vers CRM/ERP | PV*SOL 2026 (24/11/2025) ; Solargraf API roof summary | Intégration facile | Déjà là : export/import de projet ACAL17 (coche) | — | — | — |
| Export DXF, KML, glTF, XLSX | PVcase (AutoCAD) ; (pratique) | Fichiers pour bureau d'étude | Déjà là : ACAL536 KML, ACAL537 glTF (livré), ACAL604 DXF (livré) | — | — | — |
| Import de fichiers PVsyst (.PAN/.OND, scène 3D .pvc2/.pvz2) | PVsyst 8.0.0, 8.1.5 (12/08/2026) | Données constructeur sans ressaisie | ABSENT | M | petit pour .PAN/.OND (fichiers texte) ; gros pour la scène 3D | non |
| Paquet de permis (plans, schéma, BOM) en minutes | Aurora Instant Plan Sets (non daté, sur invitation) — https://aurorasolar.com/lyra/ ; Solargraf (tampons, Canada 06/2026) | Dossier complet | Déjà là : dossier technique/réglementaire ACAL163, ACAL214, ACAL236 (coche), loi 82-21 ACAL782 (livré) | — | — | — |
| Vue client 3D en lecture seule, lien partagé | (courant) | Le client voit sa maison | Livré : ACAL1314 (téléphone), ACAL1353 (ouvert) ; page hôte publique gated ACAL487 | M | petit | non |
| Proposition interactive, comparaison comptant/prêt/leasing, signature électronique, paiements | Aurora Sales Mode ; OpenSolar Sales Machine + CashFlow ; Enact (recherche seule) | Le client signe en ligne | Hors module (devis/ventes de l'ERP) : ne pas juger ici | M | — | — |
| Widget d'estimation sur le site (adresse → devis indicatif) | OpenSolar AI Lead Gen (OS 3.0) ; Aurora (22/09/2026) | Un visiteur obtient une estimation | ABSENT du plan du module ; formulaire public PARKÉ (règle du dépôt) | M | moyen | non (PVGIS + OSM) |
| Assistant IA / commandes naturelles / voix | OpenSolar « Ada » (OS 3.0) ; Solargraf chatbot (T1 2026) | On parle au logiciel | Hors module : copilote ERP (mémoire du dépôt) | B | — | — |
| Commentaires, historique, restauration, verrou | (courant) | Collaboration | Déjà là : versions et restauration ACAL45 (coche), verrou ACAL43, commentaire ACAL293 (coche) | — | — | — |

### A8. Suivi après pose

| Fonction | Qui la livre | Ce que l'utilisateur voit | Chez nous | Valeur | Coût | Payant |
|---|---|---|---|---|---|---|
| Comparaison production réelle / simulée, import d'un site existant, projets d'extension/batterie seule | Solargraf (Enlighten import, 06/2026) ; OpenSolar OS 3.0 (rétrofit batterie sur système existant) ; Aurora (détection panneaux existants, annoncée sans date) | Écart mensuel et alerte | Partiel : 12 valeurs mensuelles mesurées vs P50 ACAL887 (livré) ; connexion automatique aux portails d'onduleurs ABSENT ; modules déjà en place ACAL510 (livré) | H | moyen | non (si l'API du constructeur est ouverte au partenaire : non vérifié) |

---

## B. Les 15 fonctions ABSENTES (ou presque) du plan les plus utiles, classées

Critère de rang : gain pour un installateur marocain (résidentiel, C&I, pompage), peu de risque, livrable sans abonnement.

1. **Tarifs réels par période + économies heure par heure (BT et MT)** — H, moyen. Simple : une table de tarifs saisie par la société (périodes, prix du kWh, suppléments), appliquée à la série horaire que la simulation sort déjà (ACAL142 la persiste). Aucune donnée payante. À vérifier d'abord : le moteur de devis le fait-il déjà hors module ? (PV*SOL 2027 et Solargraf T1 2026 en font un argument fort.)
2. **Écrêtage de pointe et optimisation de la puissance souscrite (C&I)** — H, moyen. Simple : à partir de la courbe de charge horaire déjà lue (ACAL446, ACAL757) calculer la pointe mensuelle avant/après PV + batterie, montrer la puissance souscrite possible et l'économie. Algorithme glouton « décharge quand la charge dépasse un seuil » sur les 8 760 heures, en Python pur ; le principe existe dans SAM (envoi par seuil, notes SAM 2025.4.16 du 24/07/2025, recherche seule) mais on n'a pas besoin de SAM.
3. **Calendrier de nettoyage / salissure par saison et par ville** — H, petit. Simple : le modèle de salissure de pvlib (Kimber ou Hsu) pilote une courbe de perte ; données de pluie : ERA5 (Copernicus) ou séries gratuites. Aujourd'hui nous prenons douze pertes mensuelles saisies (ACAL135). Sortie : « un nettoyage tous les N jours gagne X kWh/an » — chiffre parlant pour le client.
4. **Vérification de charge sur toit plat (kg/m² totaux vs portance saisie) et justificatif de lestage** — H, moyen. Simple : somme module + châssis + lest par m² comparée à la portance déclarée par le bureau/visite, feu vert/orange/rouge, avec mention « pré-étude, non engage la structure ». Ne PAS calculer vent/neige par norme sans fichier officiel ; les pressions de vent viennent d'une table que l'installateur saisit (comme les paramètres de zones de ACAL563).
5. **Suivi après pose : lecture automatique de la production réelle et alerte de sous-performance** — H, moyen. Simple : à partir de ACAL887 (12 valeurs mensuelles), ajouter une relance mensuelle et un import CSV d'export du portail onduleur ; l'API constructeur vient après (non vérifiée ici).
6. **Import de fichiers .PAN / .OND** — M, petit. Fichiers texte clé=valeur ; remplissent la fiche technique de `stock` (courbes, coefficients). Évite la ressaisie. (PVsyst 8.0.0 ; il faut vérifier que la licence du fichier fabricant permet la réutilisation.)
7. **Export du site vers PVsyst (horizon, coordonnées, orientations) pour une contre-étude demandée par un financeur** — M, petit. Simple : fichier d'horizon et feuille de paramètres ; lien avec ACAL486 (comparaison à un rapport PVsyst réel, gated).
8. **Schéma trifilaire (MT/triphasé) et pages de calcul détaillées** — M, moyen. Simple : étendre le générateur d'unifilaire (ACAL55) avec une vue développée par phase ; export DXF déjà là.
9. **Hauteur des bâtiments depuis Open Buildings 2.5D Temporal** (Afrique, 4 m, erreur moyenne 1,5 m, CC-BY/ODbL, 2016-2023) — M, moyen. Source : https://research.google/blog/open-buildings-25d-temporal-dataset-tracks-building-changes-across-the-global-south/ . Utile quand la hauteur OSM (ACAL504) manque. Attention : prendre le fichier depuis le stockage public, pas Earth Engine (licence commerciale possible, non vérifié).
10. **Terrain en pente pour champs au sol et ombrières** — M, moyen. Simple : la pente et l'orientation du terrain sont déjà lues sur Copernicus GLO-30 (ACAL466) ; les utiliser pour corriger le pas entre rangées et l'ombrage mutuel au lieu de dire « la pente n'entre pas dans le calcul » (ACAL75). Pas de terrassement.
11. **Coût au m³ d'eau et dimensionnement « par nombre de panneaux »** (Lorentz, Grundfos) — M, petit. Simple : coût annualisé du système / m³ annuels déjà calculés (ACAL877).
12. **Bibliothèque de profils de charge types marocains** (climatisation d'été, commerce, atelier, pompe de ferme) — M, petit. Courbes types publiées dans les études d'adoption ; aucune donnée payante. (PV*SOL 2026 ajoute clim., télétravail, seniors.)
13. **Chauffe-eau électrique / ballon comme consommateur piloté par le surplus** — M, moyen. Simple : une charge dont le seuil de déclenchement est le surplus PV ; extension de ACAL780.
14. **Widget d'estimation instantanée pour le site public** — M, moyen. Simple : adresse → empreinte OSM → conception auto (ACAL421) → production PVGIS → fourchette de prix. Attention : le formulaire de contact est PARKÉ (règle du dépôt) ; à ne lancer que si le fondateur rouvre le canal.
15. **Pas de temps sous-horaire pour l'écrêtage onduleur** — B, moyen. Reporter tant que nous n'avons pas de données sous-horaires gratuites ; PVsyst 8.1.0 en fait un titre, mais pour un petit installateur l'écart est faible.

Fonctions du plan à ne pas oublier de VÉRIFIER (non trouvées dans les titres, peut-être ailleurs) : dégradation de l'état de santé de la batterie dans la simulation (PVsyst 8.1.4), tarif par consommateur, jour de semaine pour la voiture.

---

## C. Ce que les leaders font et qu'il ne faut PAS copier pour un petit installateur

- Imagerie payante et places de marché d'images (OpenSolar Imagery Marketplace, AU/NZ, 28/05/2026 ; Nearmap, EagleView) : abonnement et couverture non garantie au Maroc.
- Météo Meteonorm, Solargis, NSRDB et horizons SolarAnywhere : payants ou hors zone ; PVGIS + Copernicus suffisent.
- Échelle de centrale (RatedPower, PVcase Ground Mount) : terrassement, suiveurs, 15 000 modules, plan de terrassement, 3D électrique de centrale. Hors cible.
- Paiements, factures, rapprochement comptable, boutique fournisseurs avec stock en direct, prêts partenaires (OpenSolar CashFlow/Shop 3.4-3.11, Solargraf loans, Enact) : l'ERP a déjà ses factures ; les prêteurs sont américains.
- Codes électriques étrangers (NEC, CEC 2025, tampons d'ingénieur au Canada) : hors sujet.
- Monte-Carlo pluriannuel, modèle de salissure complet à l'échelle utilitaire, optimisation de rendement par 20 paramètres : la fourchette P50-P95 actuelle suffit.
- Intégration constructeur obligatoire (Huawei SmartDesign, Sungrow iSolarDesign, SolarEdge Designer) : enferme dans une marque ; notre conception générique est plus utile pour un installateur multi-marques.
- Assistant vocal/IA de conception et chatbots de connaissance en plus du copilote ERP : le copilote existe déjà.
- Classification d'arêtes par IA pour les retraits (Scanifly) : retraits marocains peu codifiés, nos réglages société suffisent.
- Édition temps réel multi-utilisateurs : le verrou + versions (ACAL43, ACAL45) suffisent.
- Calcul de vent et neige « conforme norme » sans table officielle ni ingénieur signataire : risque de responsabilité ; rester sur une pré-vérification de charge.

---

## D. Non vérifié / pages inaccessibles

- Notes de version PVsyst : je n'ai lu que les 100 000 premiers caractères sur 248 000 ; versions 8.0.0 à 8.1.8 couvertes, la suite (autres sections) non lue. Pas de version 8.2 trouvée.
- Aurora : pages d'aide `help.aurorasolar.com` (notes de version 2025) renvoient 403 ; aucune note de 2026 indexée. Faits 2026 d'Aurora (home electrification, drone mapping, stockage HelioScope) viennent de la presse (pv magazine USA du 22/09/2026 lu en entier ; businesswire du 16/06/2026 en résultat de recherche seulement). Aurora AI v2 et Lyra : pages non datées.
- PV*SOL 2026 : la page pveurope est bloquée (anti-robot) ; j'ai pris la page éditeur et le communiqué de 2027.
- PVcase (notes 2.62 et 2.64) : 403 ; contenu issu de résultats de recherche seulement. Roof Mount 2026 non lu.
- RatedPower : liste des fonctions du T2 2026 lue, mais pas leur date exacte (avril ou mai 2026) ni les détails.
- Grundfos GO Solar : page produit en 403 ; description issue de la recherche (pas de lecture directe). Lorentz COMPASS : la page lue décrit l'outil « LORENTZ S » ; je suppose la même famille, non confirmé. Pas de notes de version COMPASS trouvées.
- archelios Pro 2025.1 (21/11/2025), HelioScope (stockage), Nearmap/EagleView (2026), SAM (release notes 2025.4.16), Reonic, Eturnity 2026, Pylon, Enact, Arka 360, Sunbase/Solo, SolarEdge Designer, Huawei SmartDesign, Sungrow iSolarDesign, Esdec, IronRidge : résultats de recherche seulement, souvent marketing ou comparatifs de concurrents. Aucune version 2026 trouvée pour Eturnity, Pylon, Reonic, Enact, Arka, SolarEdge Designer, Huawei SmartDesign (dernier élément : 2025).
- « Solo / Sunbase » : rien trouvé sur un produit « Solo ». pvlib : versions 0.13 lues, la page « What's new » mentionne 0.15.2 (16/06/2026) mais je ne l'ai pas lue. 
- OpenSolar : les notes 3.3 et 3.4 n'étaient pas sur la page ; 3.12 et 3.13 ne détaillent que des « correctifs » et du « stringing plus facile » ; rien sur l'ombrage ou l'IA de design dans 3.5-3.13 d'après la page.
- Côté plan : titres tronqués, pas de lecture des corps de tâche ; statuts ACAL livrés non prouvés (« livré ») ne sont pas des preuves.
- Non vérifié en ligne : tarifs marocains (BT/MT, périodes), existence d'API ouvertes de portails d'onduleurs, droits de réutilisation des fichiers .PAN/.OND, licence Earth Engine pour Open Buildings.

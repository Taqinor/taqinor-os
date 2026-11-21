# Synthèse visuelle : ce que les meilleurs outils de conception solaire disent ou montrent

Lecture du 21/11/2026. Je n'ai pas regardé les images : tout vient de textes de pages, de légendes et d'alt (numéros de l'index `index.md` entre crochets, notes de version et pages produit par leur adresse). Les phrases marquées OPINION sont des jugements de rédacteurs ou d'avis, jamais des faits mesurés.

## 1. Traits que les meilleurs outils revendiquent ou montrent

### 1.1 L'écran est d'abord un plan, les outils s'y adossent
- Reonic organise l'éditeur en trois phases dans l'ordre : Bâtiment, Modules, Chaînes ; une barre en bas porte Sélectionner/Tourner, Déplacer, Mesurer ; un panneau « Calques » change le fond (orthophoto, Google 3D, bâtiments OSM, modèle de drone, image perso) ; la caméra a un bouton orthographique/perspective, une boussole et « Ajouter une vue » (jusqu'à quatre instantanés plus un par défaut). Source : https://docs.reonic.com/docs/en/offers-plan-pv-plan-modules [26-30].
- Aurora place « Fire Pathways » dans la section « System » de la barre d'outils (clic sur un bouton, fenêtre qui vérifie l'autorité et l'année de code, puis résultat) ; le même écran montre panneaux, passages et chaînes en couches. Sources : https://aurorasolar.com/blog/whats-the-deal-with-fire-setbacks-auroras-fire-pathways-solution-explained/ [9, 10], https://aurorasolar.com/design-mode/ [3].
- OpenSolar met un assistant (Ada) en panneau à gauche et le site à droite ; un second écran montre une fenêtre de synthèse « 41 Panels System » à droite et les réglages d'un « Panel Group » à gauche. Sources : alt des images, https://www.opensolar.com/auto-design/ [16, 17].
- PVsyst : la fenêtre de scène 3D a, à droite, deux onglets « Scene Objects » et « Tools » (manuel v8, p. 75) [42].
- Une seule note de nuance : Pylon se présente, d'après un résumé de recherche de fiches d'agrégateurs (page non relue ici), comme un canevas 2D plat opposé aux outils à rotation 3D. À prendre comme dire de l'éditeur, non vérifié.

### 1.2 Les résultats sont présentés en quelques chiffres + une carte de couleur
- Aurora : un panneau d'autosuffisance à trois lectures (83 % d'autosuffisance, 67 % d'économie, heures de secours par charge) ; les chiffres, le prix et l'impact sur la facture se mettent à jour quand la batterie change. Source : https://aurorasolar.com/sell-battery-storage/ [13].
- Reonic : un panneau de simulation interactif (production, autarcie, investissement, retour sur investissement) qui se relance seul ; un clic d'optimisation ; une carte « note 0-10 par panneau ». Source : https://docs.reonic.com/docs/en/offers-plan-pv-plan-modules.
- OpenSolar : un en-tête de synthèse par système avec info-bulles sur chaque indicateur (version 3.3.0) et un indicateur « cycles moyens par jour » sur la batterie. Source : https://www.opensolar.com/product-updates/release-3-3-0/.
- PVsyst : un rapport imprimable ; tables mensuelles, graphes à quatre variables au plus, diagramme de pertes parmi les graphes prédéfinis. Source : https://www.pvsyst.com/help/project-design/results/index.html [43].

### 1.3 La couleur dit un état, et reste sobre
- Irradiance : Aurora affiche l'irradiance en carte de chaleur sur le toit puis SUR chaque panneau, la bordure du panneau montrant l'ombrage entre rangées [5, 7, 8]. Reonic note chaque panneau de 0 à 10 : rouge sous 4, jaune sous 5, citron vert sous 6, vert à partir de 6 [30 ; docs Reonic].
- Conflits : Aurora met en jaune les panneaux qui gênent un passage pompiers et en rouge ceux qui chevauchent un autre panneau ou un obstacle [10] ; OpenSolar met en rouge un panneau en conflit avec un obstacle sur une structure surélevée (https://www.opensolar.com/elevated-structures/).
- Chaînes : Reonic les teinte et les renomme dans « String Info » ; un module non câblé reste distinct ; des avertissements nomment la chaîne dont le courant dépasse la limite (docs Reonic).
- Mode clair ou sombre : AUCUNE des pages lues ne le dit. Je ne peux donc rien affirmer sur ce point.

### 1.4 Combien d'étapes
- Aurora AI : adresse + une facture suffisent, modèle 3D « en moins de 10 secondes » (https://aurorasolar.com/aurora-ai/). AutoStringer : moins de 2 s en moyenne (https://aurorasolar.com/?p=13829).
- Reonic : « Cover roof side » remplit un pan ; le résultat serait, d'après les docs, de 80 à 90 % de la disposition finale ; puis on ajuste (docs Reonic).
- OpenSolar : Ada fait plusieurs systèmes « en secondes » ; les propositions « Max Offset » puis « Max Fit » arrivent à la suite dans le chat (https://www.opensolar.com/?p=14292 [18]). Le câblage auto est passé de ~20 s à 3-5 s (notes 3.0).
- SolarEdge : un glissé autour du toit suffit à détecter le contour (https://marketing.solaredge.com/solaredge-designer-0-20 [34]).

### 1.5 Le client voit la même conception, en lecture
- Aurora : une seule conception pour la vente, la conception et le plan de permis [15] ; la vue « Sales Mode » est conçue pour tablette (https://aurorasolar.com/sales-mode/ [14]).
- OpenSolar : 3D que le client fait tourner sans compte, avec soleil et ombre sur l'année (https://www.opensolar.com/sales-machine-proposal/ [24]) ; partage par un lien ou par WhatsApp (même page).
- Reonic : simulation d'ombre en direct sur un jour type, avec pause (https://reonic.com/en-gb/page/shading-analysis/ [29]).
- Côté nous : la visionneuse 3D lecture seule existe (`apps/web/src/scripts/roofPro11/viewerFullBoot.ts`) ; le soleil animé y est planifié (ACAL487).

### 1.6 Le terrain et le téléphone
- Scanifly : application mobile gratuite avec listes de contrôle et photos annotées ; ombrage en temps réel sur site [37, 38].
- OpenSolar : gestion de projet au téléphone, factures d'électricité, partage WhatsApp, iOS et Android (notes 3.12) [25].

## 2. Faiblesses que les relecteurs rapportent (OPINION sauf mention)

Sources lues : https://www.surgepv.com/reviews/opensolar et https://www.surgepv.com/reviews/aurora-solar (rédacteur CONCURRENT, il le dit lui-même : à lire comme opinion).

- OpenSolar (OPINION d'un concurrent) : Auto Design « en bêta » ; l'aide recommande de garder les designs 3D sous 500 kW, au-delà lenteurs, délais dépassés et erreurs d'enregistrement ; certains modules payants (API, connecteurs, support) ; les permis seulement aux États-Unis.
- Aurora (OPINION d'un concurrent) : production donnée en P50 seulement ; l'éditeur de schéma unifilaire seulement en Europe ; IA de toit, drone, API et gestion de contrats réservés à l'offre Enterprise sans prix publié ; rapport d'ombrage absent de l'offre de base ; incohérence « moins de 15 secondes » / « moins de 10 secondes » pour le modèle IA.
- Faits vérifiables sur la page d'Aurora : offre de base à 159 dollars par utilisateur et par mois (135 par an), 50 projets par mois pour un utilisateur ; sans batterie en offre de base (https://aurorasolar.com/pricing/).

Indices NON relus dans cette session (repris du dossier `r1/c2-sales-design-ux.md` §6, qui les tenait de résumés de recherche, les pages d'avis étant fermées aux robots) : OpenSolar jugé « fonctionnel mais daté », courbe d'apprentissage ; Aurora : fonctions manquantes et prise en main (note G2 4,7 sur 121 avis) ; Solargraf : courbe d'apprentissage. À prendre comme OPINION non vérifiée.

Limites de ma propre lecture : je n'ai pas pu confronter ces avis à l'usage réel ; aucune page lue ne mesure la lisibilité des écrans.

## 3. Ce que nos écrans pourraient reprendre sans dépendre d'une donnée payante

(Chacun est une inférence de ma part à partir des sources ci-dessus ; les tâches ACAL du complément du 20/11 couvrent déjà plusieurs de ces traits.)
- Un plan d'abord, outils adossés, inspecteur d'un pan à droite : ACAL402 (disposition « studio » à 1 280 px).
- Un héros de trois chiffres lisibles par un non-ingénieur : ACAL443 (Production), à rapprocher du panneau d'autosuffisance d'Aurora [13].
- Une couleur par état avec légende nommée : ACAL441 (légende de la carte d'accès solaire) ; rouge/jaune pour les conflits de panneaux existe déjà dans notre atelier (`checkPanelAt`).
- Un geste de départ en un clic puis correction : ACAL421 ; proposition de toit par IA : ACAL485/488 ; à ajouter : deux propositions côte à côte (voir B2, rang 2).
- Mode clair et sombre : aucune page lue ne le dit ; ACAL430 le prévoit chez nous.

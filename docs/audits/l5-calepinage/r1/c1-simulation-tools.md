# C1 - Outils de simulation PV "engineering-grade" : checklist sourcee (2026-11-20)

Budget : 18 WebSearch utilises sur 22 + ~40 WebFetch. Tout ce qui n'est pas source est marque "non verifie".
Les dates de versions viennent des pages de release notes vendeur ; elles sont reprises telles quelles.

## 0. Limites de la recherche (honnetete)
- Pages PVsyst "loss diagram" et "report" : le texte officiel ne liste PAS les etapes une par une (page `results/loss-diagram.html` : generalites seulement). Les NOMS DE VARIABLES officiels sont verifies (section E) ; les LIBELLES exacts du diagramme du rapport sont donnes de memoire et marques "non verifie (libelle)".
- SAM : sam.nrel.gov ne resout plus ; le site est maintenant sam.nlr.gov / natlabrockies.github.io (verifie).
- Aurora help center (HelioScope) : HTTP 403 -> uniquement presse + pages publiques.
- Archelios : pas de doc technique profonde lisible ; seulement pages produit/presse.
- RatedPower / PVcase : non traites (optionnel).
- Google Solar API : couverture Maroc = **non verifie**.

---
## E. PVsyst 8.x - chaine de pertes ORDONNEE (priorite)

### E1. Source officielle verifiee : ordre des pertes "Array and system losses"
Source : https://www.pvsyst.com/help/project-design/array-and-system-losses/index.html (ordre de la page)
1. Incidence angle (IAM) 2. Soiling 3. Irradiance level (low-light) 4. Thermal 5. LID (cristallin) 6. Light soaking (CIS/CIGS) 7. Module quality 8. Mismatch 9. Module degradation (ageing) 10. Optimizers 11. Array ohmic wiring 12. AC ohmic wiring 13. External transformer 14. Auxiliaries 15. System unavailability.

### E2. Variables officielles (verifie) - https://www.pvsyst.com/help/project-design/results/simulation-variables-grid-system.html
- Pertes champ : GIncLoss (niveau d'irradiance), TempLoss, SpctCor (correction spectrale), LigSoak, ShdElec (mismatch electrique d'ombrage), ModQual, LIDLoss, MisLoss, OP_Oper/OP_Pmin/OP_Pmax/OP_Vmin/OP_Vmax (optimiseurs), OhmLoss (cablage DC).
- Energies : PNomArray ; EArrRef (GlobInc x PNom, base PR) ; EArrNom (nominal STC, GlobEff) ; EArrMPP (apres toutes pertes champ) ; EArray (apres decalage point de fonctionnement onduleur) ; EOutInv (energie disponible en sortie onduleur) ; E_Grid (injectee au reseau) ; E_Avail ; E_Solar / E_User / SolFrac (si charge).
- Pertes onduleur : IL_Oper (courbe de rendement), IL_Pmin (seuil de puissance), IL_Pmax (surcharge = ecretage), IL_Vmin, IL_Vmax (fenetre de tension MPP), IL_Night (conso nocturne).
- Pertes sortie : Aux_Lss, EacOhmL (ohmique AC jusqu'au point d'injection), ETrfLss (transformateur externe), UnavLss (indisponibilite), EGrdLim (limitation reseau, perte separee optionnelle), EUnused (diagramme quand limite reseau evaluee separement - https://www.pvsyst.com/help/project-design/grid-connected-system-definition/grid-power-limitation.html).
- PR = E_Grid / (GlobInc x PNomArray) ; Yr, Ya, Yf, Lc, Ls selon IEC 61724 (meme page).
- Chaque perte est "un pourcentage de la quantite d'energie precedente" donc non additive : https://www.pvsyst.com/help/project-design/results/loss-diagram.html

### E3. Chaine du diagramme du rapport, de GHI a E_Grid (ordre usuel ; LIBELLES = NON VERIFIE contre un rapport officiel)
Partiellement confirme par un rapport exemple (GlobHor -> near shadings -> IAM -> irradiation effective -> energie nominale STC -> energie virtuelle au MPP) : resultat de recherche citant un rapport Solis sur Scribd https://www.scribd.com/document/582386299/Solis (source secondaire).
1. Global horizontal irradiation (GlobHor)
2. Global incident in coll. plane (facteur de transposition +/- %)
3. Near shadings : irradiance loss (ShdLoss) [+ ground reflection/bifacial si applicable]
4. IAM factor on global
5. Soiling loss factor
6. Effective irradiation on collectors (GlobEff)
7. PV conversion -> Array nominal energy (at STC effic.) (EArrNom)
8. PV loss due to irradiance level
9. PV loss due to temperature
10. Spectral correction (si activee)
11. Shadings : electrical loss (ShdElec)
12. Module quality loss
13. LID - Light induced degradation
14. Mismatch loss, modules and strings
15. Ohmic wiring loss (DC)
16. (Module degradation / optimiseurs si definis)
17. Array virtual energy at MPP (EArrMPP)
18. Inverter Loss during operation (efficiency, Pnom/Vnom/Vmin/Vmax/threshold, night consumption, over nominal inv. power = clipping)
19. Available Energy at Inverter Output (EOutInv)
20. Auxiliaries (fans etc.), AC ohmic loss, external transformer loss, unavailability (si definis ; limitation reseau EGrdLim/EUnused si separee)
21. Energy injected into grid (E_Grid)
=> A benchmarker : 1 poste par variable ci-dessus ; ne jamais additionner les %.

### E4. Degradation / vieillissement (verifie)
https://www.pvsyst.com/help/project-design/array-and-system-losses/ageing-pv-modules-degradation/index.html : annee N appliquee a mi-annee (annee 10 = 9,5 ans) ; taux moyen reseau (ne pas utiliser la pente garantie constructeur) ; dispersion RMS gaussienne des taux par module, mismatch estime par Monte-Carlo (limite 2 sigma).

---
## PVsyst 8.x - tableaux A a J

### A. Meteo & site
| Capacite | Detail | Source |
|---|---|---|
| Import connu `.csv -> .MET` (fournisseurs supportes) ; import fichier custom via `.MEF` (mapping), obligatoires GlobHor, DiffHor, T_Amb | assistant d'import (nouveau 8.1.0) | https://www.pvsyst.com/help/meteo-database/index.html |
| Sub-horaire (custom, Meteonorm option minute, generation synthetique minute) | | idem |
| Multi-annees : TMY a partir de >=10 `.MET` ; serie annuelle ou plus courte | | idem |
| Meteonorm V9 (8.1.0) ; NASA POWER remplace NASA-SSE (8.1.0, resume forum) | | https://www.pvsyst.com/help/release-notes/index.html ; https://forum.pvsyst.com/topic/4830-pvsyst-810-main-changes/ |
| Horizon : trace graphique (sun path), mesures terrain, fichiers importes (`.HOR` propre, non ASCII, non exportable), API SolarAnywhere ; formats d'import exacts non listes sur la page | | https://www.pvsyst.com/help/project-design/shadings/far-shadings-horizon/index.html |
| Albedo projet (transposition) separe de l'albedo bifacial (sol sous l'installation), valeurs saisonnieres | | https://www.pvsyst.com/help/project-design/bifacial-systems/index.html |
| P50/P90 : rendement annuel suppose normal ; variabilite interannuelle (% de la moyenne, sauvegardee dans le TMY genere, defaut sinon, ~3-5 % sur le forum) ; non significatif pour sub-annuel | | https://www.pvsyst.com/help/project-design/p50-p90-evaluations.html ; https://www.pvsyst.com/help/meteo-database/compare-meteo-data/annual-variability.html (via recherche) |

### B. Scene 3D & ombrages proches
| Capacite | Source |
|---|---|
| Ombrage lointain = horizon ; proche = description 3D detaillee ; facteur d'ombrage = surface ombragee / surface sensible ; calcule a chaque pas, separement beam/diffus/albedo | https://www.pvsyst.com/help/project-design/shadings/index.html |
| Import 3D : 3DS, DAE (Collada, SketchUp), PVC (PV Collada, stocke aussi modules/tables) ; 8.1.5 : import `.pvc2/.pvz2` | https://www.pvsyst.com/help/project-design/shadings/near-shadings-import/sketchup-and-other-cad-software.html ; release notes |
| Table de facteurs d'ombrage par direction solaire + diagramme iso-shading ; "linear (irradiance)" = borne basse ; "module strings" = borne haute ; curseur "fraction pour effet electrique" 0-100 % | https://www.pvsyst.com/help/project-design/shadings/near-shadings-main-dialog/index.html |
| Effet electrique : "selon strings" (estimation) ou "Module Layout" detaille (position 3D de chaque module + affectation string/MPPT, courbes I/V, cristallin uniquement, warning >1 MWc, erreur >5 MWc par defaut) ; diffus/albedo = facteur constant | https://www.pvsyst.com/help/project-design/shadings/electrical-shadings-module-layout/index.html |
| Partitions "module-strings" recommandees pour ombres fines (poteaux) | idem |
| Calcul sur sous-ensemble de la scene ; backtracking ; construction 3D ; image sol (8.0.0) | page shadings (liens) ; release notes |
| Animation d'ombrage, valeurs par module : non confirme sur les pages lues -> non verifie |  |

### C. Composants & bases
| Capacite | Source |
|---|---|
| Base : modules, onduleurs reseau, batteries, regulateurs autonomes, generateurs, pompes, regulateurs de pompage, fabricants/revendeurs, prix perso | https://www.pvsyst.com/help/component-database/index.html |
| Multi-MPPT, optimiseurs, master-slave, schema unifilaire (pages du chapitre) ; optimiseurs SolarEdge strings heterogenes (8.0.15), Huawei multi-strings (8.1.5) | https://www.pvsyst.com/help/project-design/grid-connected-system-definition/index.html ; release notes |
| Bifacial : sheds illimites et trackers horizontaux 2D, facteurs de vue, mismatch face arriere defaut 10 % | page bifacial |
| Orientations 8.x flexibles : fixe multi-orientation, sheds/trackers "illimites" coexistant avec la scene 3D, 1 ou 2 orientations par sous-champ | https://www.pvsyst.com/help/project-design/orientations-in-v8/index.html |
| Import .PAN/.OND : non confirme sur ces pages -> non verifie |  |

### D. Assistants de dimensionnement
| Capacite | Source |
|---|---|
| Assistant : ratio PNom defaut 1,25 ; propose nb modules/strings tenant dans la fenetre MPPT a 60 degC et 20 degC, limite absolue onduleur, tension systeme module a Voc (-10 degC Europe) ; alertes rouge (bloque) / orange | https://www.pvsyst.com/help/project-design/grid-connected-system-definition/index.html |
| Dimensionnement onduleur par pertes de surcharge previsionnelles (DC:AC souvent plus bas que constructeurs) | idem |
| Limitation de puissance reseau : kW ou kVA, cos phi annuel/mensuel, constante ou serie temporelle, au niveau onduleur ou point d'injection ; depuis 7.3 calcul par MPPT a chaque pas | https://www.pvsyst.com/help/project-design/grid-connected-system-definition/grid-power-limitation.html |
| Facteur de puissance, transformateur : transfo = perte ETrfLss (variables) ; pas de page transfo dans la page de definition | variables page |

### F. Stockage / autoconsommation / pompage
| Capacite | Source |
|---|---|
| Charge utilisateur horaire (autoconso, net metering) ; systemes autonomes ; DC-grid | https://www.pvsyst.com/help/project-design/grid-connected-system-definition/index.html |
| Strategies batterie reseau (autoconsommation, limitation injection) ; 8.0.17 : strategie "power shifting" stockage reseau | tutoriel officiel https://www.pvsyst.com/pdf/pdf-tutorials/pvsyst-8/pvsyst-tutorial-v8-grid-connected-en.pdf ; release notes |
| Pompage : systemes isoles au fil du soleil SANS batterie, reservoir = stockage ; circuit (puits profond, lac, pressurisation), charge hydraulique f(debit), besoins en eau ; pas de pompage reseau modelise | https://www.pvsyst.com/help/project-design/pumping-systems/index.html |
| VE : non verifie |  |

### G. Economie
LCOE, ROI, payback, NPV ; couts initiaux + annuels, tarifs injection ou autoconso : https://www.pvsyst.com/help/project-design/economic-evaluation/index.html

### H. Sorties
- Rapport imprimable : parametres generaux, parametres detailles (horizon, ombrages proches), page resultats principaux, diagramme de pertes, tout graphe, fiche economique ; comparaison de rapports ; https://www.pvsyst.com/help/project-design/results/index.html
- Structure type observee (V7.x, sources secondaires, varie selon version) : Project and results summary ; General parameters ; PV array characteristics ; System losses ; Main results ; Loss diagram ; Predefined/Special graphs ; Single-line diagram (selon projet). Source : exemples Scribd remontes par la recherche (non officiel), p.ex. https://www.scribd.com/document/654188698/Report-41
- Variables de sortie : voir E2 ; resultats mensuels (tables predefinies, tables perso 8 variables, graphes 4 variables) ; donnees pas de temps horaire/sub-horaire/journalier ; histogrammes, distributions de puissance (page results).
- PVsystCLI (batch/automatisation) introduit 8.0.0 : https://www.pvsyst.com/help-cli/release-notes.html ; page https://www.pvsyst.com/help/pvsyst-cli.html (lien). Export CSV/DXF/liens de partage : non verifie.

### I. Nouveautes 2025-2026 (verifie : https://www.pvsyst.com/help/release-notes/index.html)
- 8.0.0 (07/11/2024) : orientations flexibles, PVsystCLI, image du sol dans la scene 3D, documentation refondue.
- 8.0.7 creer orientation depuis selection ; 8.0.8 onglet dispersion d'orientation ; 8.0.10 (23/04/2025) Azure Maps remplace Bing, courbes I-V MPPT a orientations mixtes ; 8.0.15 (13/08/2025) strings heterogenes SolarEdge ; 8.0.17 (22/10/2025) strategie power shifting stockage reseau.
- 8.1.0 (15/04/2026) : assistant d'import meteo, simulation SUB-HORAIRE, Meteonorm V9, modele thermique transitoire, transposition Perez sub-horaire, modele diffus fichier custom ; resume forum : refit des coefficients Perez, NASA POWER remplace NASA-SSE (https://forum.pvsyst.com/topic/4830-pvsyst-810-main-changes/).
- 8.1.4 (01/07/2026) API meteo ANE-NEDO (Japon) ; 8.1.5 (12/08/2026) import .pvc2/.pvz2, Huawei multi-strings ; dernier vu : 8.1.8 (26/10/2026).
- Fonction IA : aucune trouvee -> non verifie.

### J. Plaintes d'usage (opinions, a marquer comme telles)
- G2 (opinion, echantillons minuscules) : PVsyst cons = cout, limites version gratuite, materiel, resultats d'ombrage electrique differents selon le type de partition ; https://www.g2.com/compare/helioscope-vs-pvsyst ; facilite : HelioScope 8,8 vs PVsyst 6,5 sur ~13 avis (page DE https://www.g2.com/de/compare/helioscope-vs-pvsyst, contenu auto-genere : prudence).
- Source vendeur (Aurora, biaisee) : PVsyst demande de l'experience pour choisir le facteur de desensibilisation d'ombrage ; https://aurorasolar.com/blog/pvsyst-vs-helioscope-frequently-asked-questions/ (cite par la recherche, non lu).
- "Courbe d'apprentissage raide" : aucune source dediee trouvee -> non verifie.

---
## PV*SOL premium (2026, puis 2027)
Sources : https://valentin-software.com/en/products/pvsol-premium/ ; https://valentin-software.com/en/product-news-blog-en/pvsol-premium-2026-available-now/ ; https://www.pv-magazine.de/unternehmensmeldungen/pvsol-premium-2027-veroeffentlicht-jetzt-mit-dynamischen-stromtarifen-neuen-optionen-im-energiemanagement-von-batteriespeichern-und-einer-noch-leistungsfaehigeren-3d-planung/
| Groupe | Capacite |
|---|---|
| A | Climat Meteonorm 9 (2026) ; Meteonorm 2001-2020 ; import climat mesure DWD/Meteonorm/WBV ; Google Solar API et Rexplorer utilisables |
| B | Ombrage 3D, batiments extrudes depuis plans/cadastre/captures, import modeles 3D ; jusqu'a 7 500 modules montes / 10 000 paralleles au toit (2026) ; 2027 : 15 000 / 10 000 sol |
| C | >30 000 modules, ~8 500-9 000 onduleurs ; import .pan ; courbes U-I et U-P par pas ; choix modeles diffus/inclines |
| D | Schemas automatiques avec pertes cables et protections ; layout 3D avec interfaces K2 et Renusol |
| F | Autoconsommation, injection totale/surplus, batterie (AC ou DC couplee 2026), VE (kilometrage/temps), pompes a chaleur ; gestion : charge differee, ecretage de pointe, tarifs dynamiques ; profils charge (clim, home office, seniors) |
| G | Analyse financiere 20 ans, payback ; tarifs par consommateur (2026), tarifs dynamiques horaire/30/15 min, tarifs a prix de puissance C&I (2027) |
| H | Rapports 24 langues Word/PDF, presentation client, rapport compact, export JSON (2026) et CSV |
| I (nouveau) | 2026 : presentation client, tarifs individuels, Meteonorm 9, JSON, nouveaux profils, batteries AC/DC avec chauffage ; R5 : interface Rexplorer (batiments 3D dans 100 m) - https://www.pveurope.eu/ (non lu, 403) ; 2027 (12/11/2026) : tarifs dynamiques, demand charges, gestion batterie etendue, 3D plus grande |
| E | Liste exacte des pertes PV*SOL : non verifie |
| J | G2 : PV*SOL juge cher pour petites entreprises (opinion, https://www.g2.com/compare/helioscope-vs-pv-sol) |
Sections du rapport PV*SOL : non verifie (seule la structure fonctionnelle ci-dessus).

## Archelios Pro / Calc (Trace Software)
- Pro 2025.1 (21/11/2025) : Enstall mounting, indicateurs Pxx P50-P95, Meteonorm 9 par defaut (>4 000 stations TMY), plugin Revit 2026, SketchUp 2026, profils ELMAS (France) : https://www.trace-software.com/archelios-pro/
- 3D integre, analyse d'ombrage module par module, sortie horaire par MPPT ; export Calc (onduleurs, trackers, longueurs de cables), export DXF, CSV ; paliers Free 9 kWc / Silver 100 kWc / Gold / Platinum : https://www.pv-magazine.com/press-releases/the-pv-software-archelios-pro-silver-manage-projects-up-to-100-kwp/ et https://www.pv-magazine.com/press-releases/trace-software-takes-an-additional-step-in-photovoltaic-design-with-the-new-version-of-pv-software-archelios-pro (via recherche)
- Calc : notes de calcul PDF 4 langues, schema unifilaire normatif ; import .ond (2020) : https://www.pv-magazine.com/press-releases/the-newest-versions-of-archelios-pro-and-archelios-calc-photovoltaic-software-solutions/
- Pertes detaillees, moteur de simulation, usability : non verifie.

## HelioScope (Aurora)
- 2026 : modelisation stockage integree (BESS, dimensionnement en direct, peak shaving) annoncee 16-23/06/2026 : https://pv-magazine-usa.com/2026/06/23/aurora-adds-integrated-storage-modeling-to-helioscope-commercial-solar-design-software/ ; peak-shaving sept. 2026 : https://www.solarpowerworldonline.com/2026/09/aurora-solar-updates-services-expands-to-uk/ (via recherche).
- Ombrage : profil d'ombrage geolocalise bitmaps, cablage calcule par conducteur/heure ; PAS d'ajustement LID specifique ; NREL 2019 : soiling defaut 2 % : https://www.nrel.gov/docs/fy19osti/72155.pdf (resume de recherche) et pages Aurora (non lues, 403).
- Nouveautes ombrage/bifacial 2026 : non verifie. G2 : facilite 8,8 vs PVsyst 6,5 (opinion).

## NREL SAM (maintenant "National Laboratory of the Rockies' SAM")
- Derniere version vue : SAM 2026.7.3 (SSC 308) du 03/07/2026 ; PV detaille + PVWatts, batterie, financier, correction spectrale (air mass / precipitable water / clearsky index), neige, batterie PVWatts complete, degradation lineaire, Single Owner revenus hors energie (agrivoltaisme) : https://natlabrockies.github.io/SAM/doc/releasenotes
- Technologies : PV, batterie, CSP, eolien, etc. ; modeles financiers residentiel/commercial/PPA : https://sam.nlr.gov/ ; PySAM 7.1.1 : https://pypi.org/project/nrel-pysam
- Parametrique, optimisation, P50/P90 : non verifie sur ces pages.

## pvlib (reference open-source)
- v0.16.0/0.16.1 (26/09/2026) : ANTS-2D bifacial, IAM diffus, Schlick IAM, infinite_sheds plus rapide : https://pvlib-python.readthedocs.io/en/stable/whatsnew.html
- Reference : Location/PVSystem/Array/ModelChain, clear-sky (Ineichen, Solis...), transposition, bifacial (pvfactors, infinite sheds, ANTS-2D, Deline), pertes (neige, salissure, ombrage, spectre), tracking, transformateur : https://pvlib-python.readthedocs.io/en/stable/reference/index.html
- iotools : PVGIS (tmy, hourly, horizon), NASA POWER, ERA5, MERRA-2, CAMS, NSRDB, Meteonorm, Solcast, Solargis, SolarAnywhere, EPW/TMY, read_panond : https://pvlib-python.readthedocs.io/en/stable/reference/iotools.html

---
## K. Pratiques de validation publiees
- PVsyst : comparaisons au mesure ; 1996 sept installations suisses ~+/-5 % annuel ; Geneve +/-5 % ; 2008 MBE 1-2 % sur 10 kWp amorphe ; "pas de validation independante publiee connue" (dit par l'auteur) ; parametres saisis = 1re source d'incertitude ; meteo connue a 5-10 %, variabilite annuelle ~+/-5 % : https://www.pvsyst.com/help/validations/index.html
- NREL multi-outils (PVsyst 6.1.1 inclus) sur 9 systemes : erreurs annuelles ~+/-8 % hors aberrants : https://www.nrel.gov/docs/fy14osti/61497.pdf (via recherche, resume partiel)
- Cross-validation PVsyst vs PV*SOL, 83 sites europeens : nRMSE < 3,2 % (annuel/mensuel) (source citee par la recherche, URL non isolee : non verifie precisement)
- ICF : l'ecart reel provient surtout des pannes (jusqu'a 30 %/mois) plus que du biais modele : https://icf.com/insights/energy/model-measure-solar-project-performance
- PVGIS 5.3 : rapport JRC139355 (2024) vs BSRN : https://joint-research-centre.ec.europa.eu/photovoltaic-geographical-information-system-pvgis/pvgis-releases/pvgis-53_en
- Sandia : comparaison croisee PVsyst/SAM/PlantPredict/pvlib, la reponse depend des hypotheses (soiling) : https://pvpmc.sandia.gov/download/4654 (via recherche)

## L. Donnees gratuites pour le Maroc
| Source | Fait verifie | URL |
|---|---|---|
| PVGIS 5.3 | Production depuis sept. 2024 ; SARAH-3 (2005-2023, ~5 km) defaut Europe/Asie centrale/Afrique ; ERA5 2005-2023 ; ERA5-Land pour temperature/vent ; terrain SRTM 90 m, horizon GRASS r.horizon ; PVGIS 5.3 a rapporte un bug pression corrige 29/03/2025 ; "PVGIS 6" cite avec periodes contradictoires (2014-2024 vs 2014-2025) | https://joint-research-centre.ec.europa.eu/photovoltaic-geographical-information-system-pvgis/pvgis-releases/pvgis-53_en ; recherche JRC |
| PVGIS (methodes) | METEOSAT couvre l'Afrique, ~4 km ; horizon : donnees ne voient pas les ombres proches ; fichier horizon utilisateur possible | https://joint-research-centre.ec.europa.eu/photovoltaic-geographical-information-system-pvgis/getting-started-pvgis/pvgis-data-sources-calculation-methods_en |
| TMY PVGIS / API horizon | TMY et horizon via API (pvlib get_pvgis_tmy/get_pvgis_horizon) ; annees TMY exactes : non verifie | https://pvlib-python.readthedocs.io/en/stable/reference/iotools.html |
| NASA POWER | Rayonnement grille 1 deg x 1 deg ; meteo 0,5 x 0,625 deg (MERRA-2) ; Release 10 ; licence non indiquee sur la page ; horaire pour certains parametres | https://power.larc.nasa.gov/docs/methodology/ |
| Open-Meteo | Historique : GHI/DHI/DNI/GTI horaires ; ERA5 0,25 deg depuis 1940, ERA5-Land 0,1 deg, IFS 9 km depuis 2017 ; usage commercial = cle API payante ; non-commercial gratuit | https://open-meteo.com/en/docs/historical-weather-api |
| Copernicus DEM | GLO-30 (30 m) et GLO-90 (90 m), c'est un DSM (batiments/vegetation inclus), erreur absolue < 4 m a 90 %, licence gratuite mondiale | https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM |
| Hauteur de batiments | GlobalBuildingAtlas (TUM, ESSD 2025) : 2,68 Mrd batiments, RMSE hauteur 1,5-8,9 m selon continent ; LoD1 ; CC BY-NC 4.0 (non commercial !) ; Afrique/Maroc : precision locale non verifiee | https://essd.copernicus.org/articles/17/6647/2025/ ; https://huggingface.co/datasets/vitrobot/GBA.LoD1/blob/main/README.md |
| Google Solar API | Couverture Maroc : **non verifie** (page de couverture = carte/GeoJSON, aucun pays nomme) ; 472 M batiments, >40 pays (blog jan. 2024) ; mode experimental EXPANDED_COVERAGE (BASE) existe | https://developers.google.com/maps/documentation/solar/coverage ; https://cloud.google.com/blog/products/maps-platform/our-solar-api-now-covers-more-rooftops-worldwide |

## Synthese "classe PVsyst" - 25 capacites (a benchmarker)
Voir le resume de reponse ; chaque ligne est tiree des tableaux ci-dessus.

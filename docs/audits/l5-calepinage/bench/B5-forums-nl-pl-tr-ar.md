# B5 — Forums NL / PL / TR / AR (et CS) : ce que disent les installateurs — 21/11/2026

Lane lecture seule. Aucune connexion, aucun compte. Budget de recherche web : 15 recherches utilisées (plafond atteint) ; le reste en WebFetch direct.

## 0. HONNÊTETÉ SUR CE QUE CETTE LANE A PU LIRE (à lire avant tout le reste)

La mission demandait 200+ lignes issues de fils de forum néerlandais, polonais, turcs, arabes. **Ce n'est pas ce qui a été livré, et le chiffre ne doit pas être pris pour une mesure de la communauté.** Les grands forums cibles ont refusé ou n'ont pas répondu :

| Site | Résultat | Détail mesuré |
|---|---|---|
| gathering.tweakers.net / tweakers.net (NL) | REFUSÉ | WebFetch : « unable to fetch » ; WebSearch : domaine « not accessible to our user agent » |
| livios.be (BE) | REFUSÉ | WebSearch : domaine « not accessible » (jamais ouvert) |
| zonstraal.be (BE) : accueil + 2 fils `viewtopic` | REFUSÉ | HTTP 403 ×3 |
| ecobouwers.be/forum (BE) | REFUSÉ | HTTP 403 |
| elektroda.pl (PL) : 1 liste, 8 fils, la recherche interne, les miroirs .com et .de | NE RÉPOND PAS | 12 tentatives, 12 « timeout of 60000ms exceeded » → **0 fil lu en entier** |
| forum.murator.pl (PL) | REFUSÉ | HTTP 403 ×2 (après redirection depuis muratordom.pl) |
| reddit.com | REFUSÉ | « unable to fetch » |
| quora (ar) | REFUSÉ | HTTP 403 |
| capterra.com, getapp.co.uk (avis 2Solar/Sollit) | REFUSÉ | HTTP 403 ×2 |
| arab-eng.org | HORS SERVICE | HTTP 522 ×2 |
| solarhome.ru (RU) | REFUSÉ | HTTP 403 |
| forum.fotowoltaika.info | CERTIFICAT INVALIDE | « self signed certificate » (non contourné) |
| tzb-info.cz /forum | 404 | |
| forum.zonnepanelen.net, forum.bouwinfo.be | N'EXISTENT PAS | ENOTFOUND |
| enerjiportali.com | REDIRIGE vers un domaine sans rapport | non suivi |
| emo.org.tr (document « Çatı GES Tasarım Kriterleri ») | 404 ×2 | (avec et sans paramètres) |
| hybsun.com, turkmenenerji.com | 410 | |

**Pages réellement ouvertes et lues** (c'est tout le corpus « L ») : donanimhaber.com (index solaire + 5 fils, TR) ; solarmagazine.nl (1) ; zelfopwekken.nl (1) ; duurzaamthuislab.nl (1) ; fritts.nl (1, articles + commentaires) ; sollit.com et solarmonkey.io (2, vendeur) ; heavengreenenergy.com et opusflow.io (2, concurrents des outils décrits) ; gramwzielone.pl (4 articles dont 3 sponsorisés, 0 commentaire sur chacun) ; oze.tzb-info.cz (1, communiqué) ; myenerjisolar.com (1, vendeur EPC) ; elkomelektrik.com.tr (1) ; voltiat.com, solarpect-sa.com, acropol-eg.com (3 pages arabes, vendeurs) ; oze.tzb-info.cz.

**Lignes « R »** = extraits de résumés de recherche (le moteur a lu la page, moi non). Ils m'ont donné les TITRES de ~21 fils elektroda/murator et des paraphrases de leur contenu ; je les marque `R` et ils comptent pour « fil identifié », jamais pour « fil lu ». Un titre de fil seul prouve qu'une question existe, pas qu'elle est répandue.

**Constat d'ensemble.** Les forums néerlandophones, polonais et arabes où se trouvent les vraies voix sont fermés aux lecteurs automatiques ; ce qui est lisible est du contenu de vendeurs ou d'EPC (à pondérer). Le forum turc lisible (donanimhaber, rubrique solaire : 40 sujets en page 1) est un forum grand public : sur 5 fils ouverts, **0 parle de conception PV** (3 chauffe-eau solaires/chaudière, 1 film de vitrage, 1 chaudière ; fils : 156077653, 157114442, 160091939, 164104830, 155864110) ; je n'en tire donc aucune ligne de besoin sauf une (R63). Aucune source marocaine, algérienne, tunisienne ou égyptienne de type forum n'a été lisible.

Conséquence : ~85 lignes (pas 200+), dont une minorité de vraies voix d'utilisateurs. Les « volumes de fils » par cluster ci-dessous sont des comptes de **pages/fils distincts mentionnant le besoin**, majoritairement de vendeurs et de résumés de recherche.

Légende `src` : L = page ouverte et lue · R = résumé de recherche seulement · V = vendeur · C = concurrent de l'outil décrit · P = article sponsorisé (annoncé comme tel sur la page).
Clés d'URL : `EL` = https://www.elektroda.pl/rtvforum/topic · `GW` = https://www.gramwzielone.pl/energia-sloneczna/ · `DT` = https://duurzaamthuislab.nl/posts/zonnepanelen-plat-dak-optimaal-opstellen/ · `HG` = https://www.heavengreenenergy.com/blog/ · `ME` = https://www.myenerjisolar.com/ges-projesi-nasil-cizilir-muhendislik-yerlesim-plani-ve-onay-sureci/ · `VO` = https://www.voltiat.com/steps-to-calculate-solar-pumping-systems/

## 1. LIGNES (besoin en une phrase, terme d'origine entre crochets)

| # | type | langue | outil | besoin (FR) | chiffre | src | URL | date |
|---|---|---|---|---|---|---|---|---|
| R01 | À LA MAIN | nl | sans outil | Comparer 2-3 dispositions réalistes (sud incliné vs est-ouest bas) avec les MÊMES pertes avant de choisir [legplan, oost-west] | sud 15° ≈ 957 kWh/kWp, E-O 10° ≈ 858 (De Bilt, PVGIS) | L | DT | 2026 |
| R02 | À LA MAIN | nl | PVGIS à la main | Comparer en euros : kWh autoconsommé valorisé 0,26 €, export 0,004 € ; E-O pose plus de panneaux sur le même toit | pertes système 14 % ; 6,5 kWc S ≈ 464 €/an = E-O ; 9,7 kWc E-O ≈ 502 € | L | DT | 2026 |
| R03 | QUESTION | nl | sans outil | La surface brute n'est pas la surface posable : retraits de rive, velux, cheminées, évacuations, passages d'entretien, voies d'évacuation, place de câbles/onduleur [vrije zones] | — | L | DT | 2026 |
| R04 | IRRITANT | nl | croquis de vente | Des plans sans cotes ni passages libres, dessinés « à l'œil » | — | L | DT | 2026 |
| R05 | À LA MAIN | nl | sans outil | Positions de lest/ancrages, charge max, compatibilité avec la membrane, vent selon hauteur/zone/bord, à justifier par projet [ballast] | « 100 kg/m² » dit insuffisant | L | DT | 2026 |
| R06 | IRRITANT | nl | blogs | Copier des distances de bord/lest génériques trouvées en ligne | — | L | DT | 2026 |
| R07 | QUESTION | nl | règle de pouce | « hauteur × 2,5 » pour l'espacement des rangées n'est qu'un croquis géométrique | ×2,5 | L | DT | 2026 |
| R08 | SOUHAIT | nl | sans outil | Juger l'ombre par heure du jour ET par chaîne (diodes de contournement, MPPT), pas par un % global | — | L | DT | 2026 |
| R09 | À LA MAIN | nl | sans outil | À 10° d'inclinaison, E ou O ≈ 90 % du max, nord ≈ 80 % | 90 % / 80 % ; un commentaire corrige à ~85 % | L | https://fritts.nl/zonnepanelen-oost-west-plat-dak/ | — |
| R10 | À LA MAIN | nl | sans outil | Distance de bord ≈ 20 cm par mètre de hauteur du bâtiment ; le permis local peut exiger plus (jusqu'à la hauteur du système) [randafstand] | 20 cm/m | L | https://fritts.nl/zonnepanelen-oost-west-plat-dak/ | — |
| R11 | À LA MAIN | nl | sans outil | Rangées à ~50 cm d'écart à 15°, avec pertes hivernales d'ombre mutuelle [rijafstand] | 50 cm / 15° | L | https://fritts.nl/zonnepanelen-oost-west-plat-dak/ | — |
| R12 | IRRITANT | nl | sans outil | Mélanger orientations/inclinaisons sur une même chaîne fait perdre du rendement ; il faut une chaîne par orientation donc 2 MPPT [string, MPP-tracker] | — | L | https://fritts.nl/zonnepanelen-oost-west-plat-dak/ | — |
| R13 | QUESTION | nl | sans outil | Vérification de structure (lucarnes, neige) avant pose, calcul statique demandé [constructieve berekening] | — | L | https://fritts.nl/zonnepanelen-oost-west-plat-dak/ | — |
| R14 | À LA MAIN | nl | sans outil | À faible pente le nettoyage compte plus : contrôle et lavage au moins une fois par an | 1×/an | L | https://fritts.nl/zonnepanelen-oost-west-plat-dak/ | — |
| R15 | À LA MAIN | nl | sans outil | Est et ouest sur des entrées MPPT séparées ; tout sur une chaîne unique « catastrophique » car l'ombre d'un panneau tire les autres | — | R | https://www.zonstraal.be/forum/viewtopic.php?t=20222 | ≤2017 |
| R16 | IRRITANT | nl | onduleurs « 2 strings » | Les deux entrées sont parfois reliées en parallèle à l'intérieur : à vérifier dans la fiche technique avant de croire à deux MPPT | — | R | https://www.zonstraal.be/forum/viewtopic.php?t=20222 | ≤2017 |
| R17 | À LA MAIN | nl | PVcalc | Sud donne +16,75 % qu'E-O, mais le choix d'onduleur change à peine | 16,75 % | R | https://www.zonstraal.be/forum/viewtopic.php?t=20222 | ≤2017 |
| R18 | À LA MAIN | nl | sans outil | En dos-à-dos la première rangée est à l'ombre de la seconde matin et soir : d'où ~10° d'inclinaison | ~10° | R | https://www.zonstraal.be/forum/viewtopic.php?t=20222 | ≤2017 |
| R19 | QUESTION | nl | sans outil | Nombre minimal de panneaux par chaîne pour démarrer tôt le matin [opstarten] (réponses datées) | — | R | https://www.zonstraal.be/forum/viewtopic.php?t=21607 | ≤2017 |
| R20 | QUESTION | nl | sans outil | Quand micro-onduleurs plutôt que string : ≥3 pans, ombre forte, ou <6 panneaux ; sinon string (~90 % des cas) | 3 pans ; <6 panneaux ; 90 % | L,V | https://zelfopwekken.nl/kennisbank/omvormers/omvormers-meerdere-dakvlakken | 09/06/2023 |
| R21 | À LA MAIN | nl | sans outil | Mini 4 panneaux par chaîne (~100 V pour que l'onduleur démarre), maxi 20-25 par chaîne | 4 ; ~100 V ; 20-25 | L,V | https://zelfopwekken.nl/kennisbank/omvormers/omvormers-meerdere-dakvlakken | 09/06/2023 |
| R22 | AIMÉ | nl | 2Solar / Sollit | Dessiner des plans de pose toit plat et toit incliné, facile à apprendre (avis d'utilisateurs néerlandais) | — | R | https://www.capterra.co.uk/software/219176/2solar | 2026 |
| R23 | IRRITANT | nl | Sollit | Manque de symboles et d'outils de dessin | — | R | https://www.capterra.co.uk/software/219176/2solar | 2026 |
| R24 | IRRITANT | nl | Sollit | Prix par utilisateur jugé compliqué et cher | — | R | https://www.capterra.com/p/219176/2Solar/ | 2026 |
| R25 | AIMÉ | nl | 2solar (calculateur d'ombre) | Animation d'ombre jointe au devis par un lien, pour comparer marques et variantes de disposition ; présentée comme argument d'expert | dev. > 6 mois | L,V | https://solarmagazine.nl/nieuws-zonne-energie/i13201/2solar-voegt-schaduwcalculator-toe-aan-software | 23/02/2017 |
| R26 | IRRITANT | nl | sans outil | Le calcul d'ombre est souvent évité : trop de variables, trop long [schaduwberekening] | — | L,V | https://solarmagazine.nl/nieuws-zonne-energie/i13201/2solar-voegt-schaduwcalculator-toe-aan-software | 23/02/2017 |
| R27 | AIMÉ | nl | Solar Monkey | Devis en ~90 s depuis une adresse (toit détecté sur vue aérienne, ombre, rendement calibré mer du Nord), onboarding ~1 h | 90 s ; 525 €/mois/50 projets ; dès 85 €+12 €/projet | L,V,C | https://www.heavengreenenergy.com/blog/solar-monkey-review ; https://solarmonkey.io/ | 2026 |
| R28 | IRRITANT | nl | Solar Monkey | Ni schéma unifilaire, ni rapport P50/P75/P90, ni levé drone/LiDAR propre ; toiture résidentielle seulement | note 36/50 (concurrent) | L,C | https://www.heavengreenenergy.com/blog/solar-monkey-review | 2026 |
| R29 | IRRITANT | nl | Solar Monkey | Coût par devis élevé sous ~30 devis/mois | ≈10,50 € à 50 devis ; 52,50 € à 10 | L,C | https://www.heavengreenenergy.com/blog/solar-monkey-review | 2026 |
| R30 | IRRITANT | nl | Solar Monkey | Ne couvre ni planning, ni stock, ni facturation, ni suivi chantier (vendeur concurrent, non vérifié) | — | L,C | https://opusflow.io/blog/solar/solar-monkey-alternatives/ | 2026 |
| R31 | AIMÉ | nl | Sollit | Fonds aériens (Cyclomedia, Google, PDOK) sous le tracé ; calcul auto de sous-structure et suggestion d'onduleur selon la gamme de l'installateur (revendications vendeur) | config. de base « 1 à 2 min » | L,V | https://sollit.com/software/design/ | 2026 |
| R32 | À LA MAIN | pl | sans outil | Voc à froid : plus de 800 V sous ~−15 °C ; après ajout de panneaux, Voc >500 V empêche le démarrage [napięcie biegu jałowego] | 800 V à −15 °C ; 500 V | R | EL3784644 = https://www.elektroda.pl/rtvforum/topic3784644.html | — |
| R33 | QUESTION | pl | sans outil | Tension du string sous la plage MPP ? À 70 °C la tension de travail baisse d'environ 5 V [Vdc, zakres MPPT] | ~5 V à 70 °C | R | https://www.elektroda.pl/rtvforum/topic3865605.html ; https://www.elektroda.pl/rtvforum/topic3973572.html | — |
| R34 | QUESTION | pl | sans outil | 1 ou 2 strings ? viser la tension nominale de l'onduleur ? | — | R | https://www.elektroda.pl/rtvforum/topic3880280.html | — |
| R35 | QUESTION | pl | sans outil | Deux strings gauche/droite sur un même toit ; faut-il les séparer sur 2 MPPT | — | R | https://www.elektroda.pl/rtvforum/topic4009312.html ; https://forum.murator.pl/topic/275045-po%C5%82%C4%85czenie-paneli-fotowoltaicznych-dwa-stringo-prawalewa/ | — |
| R36 | À LA MAIN | pl | sans outil | Contrôler à la main Voc au minimum de température, Vmpp au maximum, Isc contre la limite MPPT, tension de démarrage ; un auteur a trouvé courants de chaîne trop hauts ET tension trop basse sur deux onduleurs | — | R | https://www.elektroda.pl/rtvforum/topic3851320.html ; https://www.elektroda.pl/rtvforum/topic2925056.html | — |
| R37 | À LA MAIN | pl | sans outil | Rapport P_AC/P_DC visé ≈ 90 % sur toit sud 30-35° ; l'écart grandit avec l'écart d'orientation (exemple 3 kW → ~3,3 kWc) | 90 % | L,P | GW13939/na-co-zwrocic-uwage-przy-doborze-falownika-dla-instalacji-fotowoltaicznej | 19/12/2014 |
| R38 | SOUHAIT | pl | (SMA, sponsorisé) | Large plage MPP, tension de démarrage > minimale (sinon cyclage), plusieurs MPPT pour multi-orientation/ombre, courant d'entrée élevé pour mixer des modules | — | L,P | GW13939/na-co-zwrocic-uwage-przy-doborze-falownika-dla-instalacji-fotowoltaicznej | 19/12/2014 |
| R39 | À LA MAIN | pl | PV*SOL | Un utilisateur obtient 2-3 % d'ombrage pour un toit à 30° avec obstacle de 2,7 m | 2-3 % ; 30° ; 2,7 m | R | https://www.elektroda.pl/rtvforum/topic3867017.html (fil non confirmé : le résumé ne cite pas le numéro) | — |
| R40 | QUESTION | pl | PV*SOL | Un « 5 % d'ombrage » affiché est-il par module ou la somme ? | 5 % | R | https://www.elektroda.pl/rtvforum/topic3685683.html | — |
| R41 | À LA MAIN | pl | sans outil | Lucarnes/cheminées : déplacer des panneaux sur un autre pan ou une autre chaîne ; le courant est limité par le plus faible du string | — | R | https://www.elektroda.pl/rtvforum/topic3867017.html | — |
| R42 | QUESTION | pl | optimiseurs | Optimiseurs de puissance à 5 % d'ombrage : à partir de quand sont-ils justifiés [optymalizatory mocy] | 5 % | R (titre) | https://www.elektroda.pl/rtvforum/topic3685683.html | — |
| R43 | QUESTION | pl | sans outil | L'ombre d'un câble électrique aérien pèse-t-elle sur le rendement | — | R (titre) | https://www.elektroda.pl/rtvforum/topic4062535.html | — |
| R44 | QUESTION | pl | PV*SOL / PVsyst | PV*SOL plus simple mais limité (~500 kWc), PVsyst plus précis mais plus long [opinions de fil] | ~500 kWc | R | https://poszukaj.elektroda.pl/szukaj,projekt-instalacji-fotowoltaicznej.html | — |
| R45 | À LA MAIN | pl | Sunny Design + BlueSol | Un utilisateur a projeté l'installation dans les deux outils et voulait recouper avec un troisième | — | R | https://poszukaj.elektroda.pl/szukaj,projekt-instalacji-fotowoltaicznej.html | — |
| R46 | AIMÉ | pl | BlueSol Design | Version polonaise : import plan DXF/DWG/image, export DWG/DXF, schéma unifilaire auto modifiable, modèles de documents, tables de câbles CEI-UNEL, chute de tension, essai 30 j, mises à jour gratuites (revendications vendeur) | ~20 000 modules (PHOTON), ~1 600 onduleurs | L,V | https://www.gramwzielone.pl/?p=15764 ; GW30355/bluesol-design-to-profesjonalne-oprogramowanie-do-projektowania-systemow-fotowoltaicznych-na-rynek-polski | 29/05/2015 ; 09/03/2018 |
| R47 | IRRITANT | pl | BlueSol | Systèmes listés jusqu'à Windows 8 ; position sur carte exige internet (vendeur, 2018) | — | L,V | GW30355/bluesol-design-to-profesjonalne-oprogramowanie-do-projektowania-systemow-fotowoltaicznych-na-rynek-polski | 09/03/2018 |
| R48 | À LA MAIN | pl | sans outil | Joindre à la déclaration de micro-installation un schéma unifilaire avec protections AC/DC et le compteur de l'opérateur [schemat jednokreskowy] | — | R | https://www.elektroda.pl/rtvforum/topic3617415.html | — |
| R49 | QUESTION | pl | sans outil | Parafoudre non exigé d'office par l'opérateur : type selon la protection foudre ; sectionneur DC inutile si l'onduleur en a un | — | R | https://www.elektroda.pl/rtvforum/topic3683616.html | — |
| R50 | SOUHAIT | pl | sans outil | Faire relire/valider un schéma unifilaire déjà dessiné [ocena poprawności] | — | R (titre) | https://www.elektroda.pl/rtvforum/topic4118071.html | — |
| R51 | À LA MAIN | pl | (sponsorisé) | Parafoudre DC au plus près des modules, un par entrée MPPT, jeu supplémentaire si câble >10 m ; fusibles dès 3 chaînes parallèles ; sectionneur DC toujours ; RCD type A/B ; interrupteur-pompier si volume du compartiment >1 000 m³ | 10 m ; 3 chaînes ; 1 000 m³ | L,P | GW103977/ochrona-instalacji-fotowoltaicznej-na-szostke | 05/10/2020 |
| R52 | QUESTION | pl | sans outil | Consultation d'un expert incendie pour une installation PV (changement de droit de la construction) | — | L,P | GW103977/ochrona-instalacji-fotowoltaicznej-na-szostke | 05/10/2020 |
| R53 | QUESTION | pl | sans outil | Qui doit signer le projet : concepteur habilité ou installateur (le résumé ne tranche pas) | — | R | https://www.elektroda.pl/rtvforum/topic3837577.html | — |
| R54 | QUESTION | pl | sans outil | PV sur le toit d'un immeuble de 50 logements [dach bloku] | 50 logements | R (titre) | https://www.elektroda.pl/rtvforum/topic4166994.html | — |
| R55 | QUESTION | pl | sans outil | Schéma d'une installation hors réseau domestique | — | R (titre) | https://www.elektroda.pl/rtvforum/topic4120355.html | — |
| R56 | QUESTION | pl | sans outil | Vérifier la compatibilité d'une liste d'équipements (Deye 12 kW + Jinko 570 Wc + stockage) avant achat | 12 kW ; 570 Wc | R (titre) | https://www.elektroda.pl/rtvforum/topic4112334.html | — |
| R57 | AIMÉ | cs | PV*SOL premium | Schéma de raccordement généré automatiquement, import de profil de charge à la minute, ombrage 3D, 6 langues (communiqué du vendeur) | pas de 1 min | L,V | https://oze.tzb-info.cz/114617-novy-software-pro-precizni-navrh-fotovoltaickych-elektraren | 23/05/2014 |
| R58 | À LA MAIN | tr | sans outil | Le layout ne se réduit pas au nombre max de panneaux : pente, orientation, ombre, distances de maintenance, accès incendie, positions d'onduleurs, chemins de câbles, SCADA [yerleşim planı] | — | L,V | ME | 2026 |
| R59 | À LA MAIN | tr | sans outil | Dimensionner sur 12 mois de consommation et un profil 15 min/horaire, pas sur un total annuel [yük profili] | 12 mois ; 15 min | L,V | ME | 2026 |
| R60 | QUESTION | tr | sans outil | Erreurs fréquentes : pas de profil de charge, ombrage sauté, structure/sol/drainage oubliés, capacité réseau vérifiée trop tard, chaînes/onduleur incompatibles, simulation prise pour une garantie | — | L,V | ME | 2026 |
| R61 | À LA MAIN | tr | sans outil | Dossier d'approbation : plan d'implantation, schéma unifilaire [tek hat şeması], calculs techniques ; rien ne démarre sans approbation du distributeur | — | L | https://elkomelektrik.com.tr/cati-tipi-ges-basvuru-rehberi/ | 09/09/2024 |
| R62 | À LA MAIN | tr | sans outil | Pièces attendues : plan de chaînes, plan de terre, cheminements de câbles, fiches techniques, métré, PV de réception, as-built ; accès O&M (nettoyage, supervision) conçu dès le départ | — | L,V | ME | 2026 |
| R63 | QUESTION | tr | sans outil | Clients à tarif par paliers : facture qui bondit avec la clim quasi 24 h et façade ouest ensoleillée (forum grand public, sans chiffres) | — | L | https://forum.donanimhaber.com/elektrik-faturasi-cozumu--164104830 | 21/09/2026 |
| R64 | À LA MAIN | tr | PVsyst | Calculer à part l'effet de l'ombre des structures voisines avec PVsyst ou HelioScope (résumé de recherche d'un site d'EPC) | — | R,V | https://turkmenenerji.com/cati-ges-kurulumu/ | — |
| R65 | AIMÉ | tr/en | HelioScope + PVsyst | Dessiner le toit dans HelioScope, relancer PVsyst pour le financement ; écart <1 % si hypothèses alignées (sites d'outils concurrents, non indépendants) | <1 % | R,C | https://www.heavengreenenergy.com/blog/helioscope-vs-pvsyst | 2026 |
| R66 | QUESTION | ar | sans outil | Débit = besoin d'eau par jour ÷ heures de soleil pic, puis ÷ 60 pour des litres/minute [التصريف] | — | L,V | VO | — |
| R67 | À LA MAIN | ar | sans outil | Puissance de pompe = Q(l/min) × HMT × 0,0001635 ÷ (η pompe × η onduleur) ; ou 0,002725 avec Q en m³/h | 0,0001635 ; 0,002725 | L,V | VO | — |
| R68 | QUESTION | ar | sans outil | Facteurs de surdimensionnement du champ contradictoires : ×1,6 (voltiat) contre ×1,3 à ×1,5 (autres vendeurs, résumés) ; onduleur ×1,3 | 1,6 ; 1,3-1,5 ; 1,3 | L,V + R | VO ; https://www.rafsun.com/ar/how-many-solar-panels-for-a-solar-water-pump/ (page 404 à l'ouverture, extrait seul) | — |
| R69 | À LA MAIN | ar | sans outil | Réservoir à 3 jours d'autonomie ; onduleur seulement pour moteur AC ; gamme 1-300 kW pour jusqu'à 450 m³/h | 3 jours ; 450 m³/h | L,V | VO | — |
| R70 | QUESTION | ar | sans outil | HMT et TDH sont deux noms pour la hauteur : prendre la valeur donnée par le catalogue de la pompe | — | L,V | VO | — |
| R71 | À LA MAIN | ar | sans outil | Choisir la pompe sur les courbes du constructeur au point débit/hauteur du système [منحنى المضخة] | — | L,V | VO ; https://acropol-eg.com/%D9%83%D9%8A%D9%81%D9%8A%D8%A9-%D8%AD%D8%B3%D8%A7%D8%A8-%D9%82%D8%AF%D8%B1%D8%A9-%D8%A7%D9%84%D9%85%D8%B6%D8%AE%D8%A9/ | — |
| R72 | IRRITANT | ar | sans outil | Le calcul à la main produit des erreurs : formule de batterie Wh÷V incohérente, panneau 580 W × ~4,3 h compté 2 500 Wh sans aucune perte ; chaleur et poussière « significatives » sans pourcentage | 7 500 Wh ; 580 W ; 2 500 Wh | L,V | https://solarpect-sa.com/blog/dalil-mozareen-hisab-kafaa-taqa-shamsiya/a-1826349470 | — |
| R73 | QUESTION | ar | sans outil | Pomper la nuit avec batteries (3-4 × 200 Ah pour ~7 h) : affirmation vendeur sans donnée | 200 Ah ; 7 h | L,V | https://solarpect-sa.com/blog/dalil-mozareen-hisab-kafaa-taqa-shamsiya/a-1826349470 | — |
| R74 | À LA MAIN | ar | sans outil | MPPT et non PWM ; courant de démarrage de l'onduleur ; section du câble selon la distance ; marge de sécurité ; ensoleillement local | — | L,V | https://solarpect-sa.com/blog/dalil-mozareen-hisab-kafaa-taqa-shamsiya/a-1826349470 | — |
| R75 | QUESTION | ar | sans outil | Puissance du moteur ou du système ? la valeur nominale prête à confusion ; pompe sur-dimensionnée = énergie et coût, sous-dimensionnée = débit faible | 60 m³/j ÷ 6 h = 10 m³/h | L,V | https://acropol-eg.com/%D9%83%D9%8A%D9%81%D9%8A%D8%A9-%D8%AD%D8%B3%D8%A7%D8%A8-%D9%82%D8%AF%D8%B1%D8%A9-%D8%A7%D9%84%D9%85%D8%B6%D8%AE%D8%A9/ | — |
| R76 | À LA MAIN | ar | sans outil | Exemple universitaire syrien : nombre de panneaux = puissance totale ÷ 195 W ; les chiffres de l'exemple se contredisent entre eux | 195 W | R | https://hama-univ.edu.sy/newsites/agricultural/wp-content/uploads/2022/06/%D8%A7%D9%84%D9%85%D8%B6%D8%AE%D8%A7%D8%AA-%D8%A7%D9%84%D8%B4%D9%85%D8%B3%D9%8A%D8%A9.pdf | 2022 |
| R77 | À LA MAIN | ar | PVsyst | Étude académique libyenne : ombrières de parking 78 kW raccordées au réseau simulées sous PVsyst (sud 30°) ; pas une voix d'installateur | 78 kW ; 128 964 kWh/an | R | https://journals.zu.edu.ly/index.php/UZJEST/article/view/1458/985 | — |
| R78 | SOUHAIT | ar | outils de design | Une page arabe d'outil de design « تحليل الظلال » existe (titre vu seulement) : la demande d'interface arabe est réelle côté éditeurs, non mesurée côté installateurs | — | R,V | https://www.surgepv.com/ar/shadow-analysis | — |
| R79 | AIMÉ | en | HelioScope | Wiki : à hypothèses égales l'écart PVsyst/HelioScope est ~1 % (affirmation du fournisseur) | 1 % | R,V | https://help-center.helioscope.com/hc/en-us/articles/4465905757843-HelioScope-vs-PVsyst | — |

Aucune citation >15 mots ; tout paraphrasé. Les prix des outils (Solar Monkey) viennent d'un concurrent et du vendeur, ne les prendre que comme ordre de grandeur.

**Décompte** : voir section 2 (calculé par commande).

## 2. COMPTES (calculés sur le tableau ci-dessus)

Total **79 lignes** ; par type : À LA MAIN 30, QUESTION 25, IRRITANT 12, AIMÉ 8, SOUHAIT 4 ; par langue : nl 31, pl 25, ar 13, tr 7, cs 1, tr/en 1, en 1 ; par statut de source : lu(L) 46, résumé(R) 33 (lu en page ouverte, y compris vendeurs/concurrents : une ligne « L » n'est PAS pour autant une voix d'utilisateur).

## 3. CLUSTERS CLASSÉS (par nombre de pages/fils distincts ; toutes sources confondues, vendeurs inclus)

Le nombre de clusters est ~30, pas 50 : le corpus ne permet pas plus sans les inventer. Colonnes : cluster · besoin (FR) · outils qui y répondent / échouent · fils (n, dont lus L) · URLs.

| rang | cluster | besoin en une ligne | outils | fils (n / L) | lignes |
|---|---|---|---|---|---|
| 1 | Une chaîne par orientation / MPPT séparés | Ne jamais mélanger deux pans sur une entrée MPPT ; savoir si les « 2 strings » sont vraiment indépendants | tous les onduleurs multi-MPPT ; échec : plans à la main | 7 / 3 | R12 R15 R16 R20 R35 R38 R60 |
| 2 | Fenêtre de tension (Voc froid, Vmp chaud, Isc, démarrage, nb min/max de modules) | Savoir qu'un string est faisable sans calcul manuel | PV*SOL (config check, cf. B4), Sunny Design ; échec : calcul à la main | 7 / 2 | R19 R21 R32 R33 R34 R36 R38 |
| 3 | Schéma unifilaire + dossier de dépôt (opérateur) | Sortir le schéma, le plan de chaînes, le plan d'implantation et les calculs attendus par le distributeur | BlueSol (auto) ; PV*SOL premium (auto) ; Solar Monkey ABSENT | 8 / 3 | R28 R46 R48 R50 R57 R61 R62 |
| 4 | Surface posable : retraits, obstacles, passages, voies de secours | Ne poser que sur la surface réellement utilisable, passages d'entretien et incendie compris | outils pro ; échec : croquis sans cotes | 6 / 4 | R03 R04 R10 R52 R58 R62 |
| 5 | Ombrage par heure et par chaîne (pas un % global) | Savoir ce que vaut l'ombre sur chaque chaîne et à quelle heure | PV*SOL (3D, par module) ; 2solar (animation) | 6 / 3 | R08 R25 R26 R39 R40 R64 |
| 6 | Comparer des dispositions à pertes identiques | Sud incliné contre est-ouest bas, en kWh/kWc et en kWh posés | PV*SOL (6 versions, cf. B4) ; PVcalc à la main | 4 / 3 | R01 R02 R09 R17 |
| 7 | Espacement des rangées / inclinaison toit plat | Distance entre rangées, ombre mutuelle matin/soir, inclinaison basse | règles de pouce partout | 4 / 3 | R07 R11 R18 R09 |
| 8 | Micro-onduleur / optimiseur ou string selon pans, ombre, nombre | Une recommandation qui dit quel matériel selon la toiture | aucun outil lu ne le fait seul | 3 / 1 | R20 R40 R42 |
| 9 | Lestage, vent, structure, charge admissible | Justifier le lest et vérifier la structure, sans règle de pouce | Sollit (revendique), à la main | 3 / 3 | R05 R06 R13 |
| 10 | Protections : parafoudre (1 par MPPT, >10 m), fusibles dès 3 chaînes, sectionneur DC, pompier, RCD | Le bon appareillage pour la bonne raison | à la main | 3 / 1 | R49 R51 R52 |
| 11 | Dimensionnement de pompe (débit, HMT, courbe, onduleur, champ, réservoir) | Calculer champ PV + variateur + réservoir sans formule maison ni facteur au pif | formules à la main ; facteurs contradictoires 1,3 / 1,5 / 1,6 | 5 / 4 | R66-R71 R75 R76 |
| 12 | Erreurs du calcul à la main (pompage) | Ne pas se tromper d'unités, ne pas oublier les pertes chaleur/poussière | — | 3 / 2 | R72 R73 R74 |
| 13 | Rapport DC/AC | Surdimensionner le champ vs l'onduleur de façon réfléchie (~90 % AC/DC cité) | sizing tools | 2 / 1 | R37 R38 |
| 14 | Profil de charge fin | 15 min / horaire plutôt que total annuel | PV*SOL premium | 3 / 3 | R57 R59 R60 |
| 15 | Fond de plan aérien/DXF sous le tracé | Tracer sur image aérienne ou plan déposé | Sollit, Solar Monkey, BlueSol | 4 / 3 | R27 R31 R46 R47 |
| 16 | Catalogue à jour (modules/onduleurs) | Bibliothèque large sans saisie | BlueSol 20 000 / 1 600 | 1 / 1 | R46 |
| 17 | Animation d'ombre partageable avec le client | Montrer l'ombre au client | 2solar, PV*SOL | 2 / 1 | R25 |
| 18 | Vérifier une liste d'équipements / un schéma déjà dessiné | « Mon installation est-elle correcte ? » | aucun | 3 / 0 | R36 R50 R56 |
| 19 | Pertes chaleur / poussière / nettoyage | Pertes saisonnières, nettoyage plus important à faible pente | PVsyst (soiling) | 4 / 3 | R14 R72 R74 R12 |
| 20 | Rendement P50/P90 | Résultat bancable | PVsyst ; Solar Monkey ABSENT | 2 / 1 | R28 R65 |
| 21 | Qui signe / exigences légales locales | Faire valider par habilité, incendie, opérateur | — | 3 / 2 | R52 R53 R61 |
| 22 | Hors réseau | Schéma et dimensionnement hors réseau | BlueSol (revendique) | 2 / 0 | R46 R55 |
| 23 | Toit partagé d'immeuble | PV sur copropriété | — | 1 / 0 | R54 |
| 24 | Ombre d'un câble / obstacle fin | Ombre d'un fil aérien | — | 1 / 0 | R43 |
| 25 | Coût par devis / prix par utilisateur | Outil rentable à petit volume | Solar Monkey, Sollit | 3 / 2 | R24 R29 R27 |
| 26 | Périmètre : un outil de vente ne fait pas le chantier | Planning, stock, facturation | Solar Monkey | 1 / 1 | R30 |
| 27 | Interface dans la langue du marché | Outil traduit (pl, ar) | BlueSol, PV*SOL (6 langues), SurgePV (ar) | 3 / 2 | R46 R57 R78 |
| 28 | Tarif par paliers / facture | Estimer l'effet d'un seuil tarifaire | — | 1 / 1 | R63 |
| 29 | Outil obsolète | Systèmes d'exploitation anciens | BlueSol | 1 / 1 | R47 |
| 30 | Pompage : nuit et batterie | Pomper la nuit | — | 1 / 1 | R73 |

## 4. CLIMATS CHAUDS / TOITS TERRASSES / POMPAGE / RÉSEAU FAIBLE

Ce que les sources arabes et turques disent réellement (peu, et de vendeurs) :

- **Pompage (ar, 5 pages : voltiat, solarpect, acropol, Hama [extrait], rafsun [extrait]).** La méthode enseignée est manuelle : débit ÷ heures de soleil pic, puissance par constante 0,0001635 ou 0,002725 ÷ rendements, champ = pompe × un coefficient, onduleur ×1,3, réservoir 3 jours. Les coefficients du champ **ne concordent pas** d'une page à l'autre (×1,6 / ×1,3-1,5). Un guide saoudien se trompe d'unités et compte un panneau sans aucune perte. Aucune page ne mentionne de courbe de pompe PVGIS horaire : le besoin « calcul fiable, sans formule maison » est visible, mais exprimé par des vendeurs, pas par des installateurs.
- **Chaleur et poussière (ar).** Citées comme causes de perte (guide saoudien) sans aucun pourcentage ; la dérive thermique n'est donnée que par mon propre complément, pas par la source. Pas de ligne d'installateur.
- **Toits terrasses (nl).** Seule région où j'ai lu du détail : retraits de rive, ballast, rangées, E-O vs S. Ces pages décrivent un toit terrasse béton comme chez notre utilisateur, mais avec vent/neige/pluie nordiques.
- **Réseau faible.** **Aucune source lue** n'en parle (ni chute de tension à la prise, ni groupe électrogène, ni délestage). Cette absence est un vide de ma lecture, pas une preuve que le besoin n'existe pas. Je ne propose donc rien là-dessus sur la base de cette lane.
- **Turquie.** Le forum lisible est grand public ; les seuls faits de conception viennent d'un EPC (myenerjisolar) et d'un distributeur (Elkom) : dossier d'approbation = implantation + unifilaire + calculs ; profil de charge 15 min ; accès O&M. Le document de l'ordre des ingénieurs (EMO) n'a pas pu être ouvert (404).
- **Maroc, Algérie, Tunisie, Égypte, Jordanie, EAU.** Aucune page de forum lisible ; seul acropol-eg.com (Le Caire) est une page d'entreprise sans consigne climatique.

## 5. CE QUE LES OUTILS LOCAUX FONT QUE LES GRANDS NE FONT PAS (revendications de vendeurs ou de concurrents, non vérifiées)

| outil local | fait | source |
|---|---|---|
| Solar Monkey (NL/BE) | adresse → toit détecté, ombre et rendement calibré sur le climat local, devis en ~90 s, tarifs du pays et options pompe à chaleur/borne/clim dans le même devis ; manque : unifilaire, P50/P90 | solarmonkey.io ; heavengreenenergy.com/blog/solar-monkey-review (concurrent) |
| Sollit (ex-2Solar, NL) | fonds aériens néerlandais (Cyclomedia, PDOK), plans de pose toit plat/incliné, calcul de sous-structure, suggestion d'onduleur selon la gamme de l'installateur ; avis utilisateurs : facile à apprendre, peu de symboles | sollit.com/software/design/ (vendeur) ; avis capterra via résumé |
| 2solar (2017) | calcul d'ombre en animation qui se joint au devis | solarmagazine.nl |
| BlueSol (PL, IT) | interface polonaise, DXF/DWG entrée et sortie, unifilaire auto, tableaux de câbles italiens CEI-UNEL, documents modèles, hors réseau et micro-onduleurs | gramwzielone.pl (sponsorisé) |
| PV*SOL premium (CS/PL) | schéma de raccordement généré, rapport pour gestionnaire de réseau, 6 langues dont polonais | oze.tzb-info.cz (communiqué) |

Absent partout (lu): un outil qui conçoit dans la langue ET avec les règles locales de dépôt du distributeur pour des toits terrasses chauds et poussiéreux + pompage ; je n'ai lu aucune page marocaine qui le dit.

## 6. CLUSTERS CONTRE NOTRE MODULE (vérifié par grep dans le dépôt)

Légende : PRÉSENT (`fichier::symbole`) · PARTIEL · ABSENT · DÉJÀ PLANIFIÉ (id). Chemins : `BE`=backend/django_core, `AC`=BE/apps/calepinage, `CE`=BE/core/electrique, `RP`=apps/web/src/scripts/roofPro11.

| cluster | verdict | preuve |
|---|---|---|
| 1 Une chaîne par orientation | PRÉSENT | `CE/chaines.py` (règle 1 en docstring l.20 « un groupe par PAN, jamais mélangé sur une entrée MPPT ») ; `CE/chaines.py::_allouer_mppt` (l.566) ; message l.693 |
| 1b « 2 strings » en réalité parallèles | ABSENT | `git grep independantes` dans `CE` : 0 hit ; pas de champ « entrées indépendantes » trouvé |
| 2 Fenêtre de tension | PRÉSENT | `AC/services/electrique.py` : `voc_froid_v` l.2219, verdicts `vmp_cold_under_mppt_max` / `vmp_hot_over_mppt_min` l.3769-3770 ; `v_demarrage_v` dans `AC/services/chaines.py` l.431 et `etapes/mppt.py` |
| 3 Unifilaire + dossier | PRÉSENT | `CE/schema.py::blocs_du_schema` ; route `schema-unifilaire/` (CALX234) ; `AC/services/documents/plan_cablage.py` ; `AC/models.py::GabaritDossierReglementaire` ; export `export.dxf` (CALX22, `services/export_dxf.py`) |
| 3b Relecture d'un schéma déjà dessiné | ABSENT | rien de tel trouvé ; les verdicts électriques s'appliquent à un calepinage complet |
| 4 Surface posable, retraits, passages | PRÉSENT | `apps/web/src/lib/roofSetbackEdge.ts` ; `RP/zones.ts` (gabarits ; commentaire l.1201 « fire pathways » parité Aurora) ; `RP/obstaclesUi.ts` ; `RP/batiment.ts::acrotereDuBatiment` |
| 5 Ombrage par heure/chaîne | PRÉSENT | `AC/services/etapes/ombrage_proche.py::appliquer` (matrice 12×24) ; `ombrage_chaines.py` (CALX168 mismatch d'ombrage) ; `apps/web/src/lib/shadingEngine.ts` |
| 6 Comparer dispositions | PRÉSENT | `AC/services/comparaison.py` (CALX331) ; `RP/matrix.ts` ; familles `data-family="eastwest"/"south"` |
| 7 Rangées toit plat | PRÉSENT | `apps/web/src/lib/shadingEngine.ts::rowSelfShading` ; `estimatorBrainV2.ts` ; `frontend/src/features/calepinage/atelier/OngletCoupeRangees.jsx` |
| 8 Micro/optimiseur vs string | PARTIEL | `AC/services/micro_onduleurs.py` (branches AC, CALX209) existe ; **aucune recommandation** string/micro/optimiseur selon pans/ombre/nombre ; `git grep optimiseur` côté `AC` : 0 usage de calcul |
| 9 Lestage/vent/structure | PRÉSENT | `AC/services/lestage.py` (CAL163, tous coefficients saisis avec référence) ; `PanneauMasseLestage.jsx` ; charge admissible déclarée CIQ114 (PLAN.md l.1008, coché) |
| 10 Protections | PRÉSENT sauf pompier | `CE/protections.py` : parafoudre DC type 2 exigé au-delà de 10 m (l.14), sectionneur DC toujours (l.18), `SEUIL_CHAINES_PARALLELES_FUSIBLE = 3` (l.81) ; **interrupteur-pompier / arrêt rapide : ABSENT** (0 hit code, 0 hit plans) |
| 11 Pompage | PRÉSENT | `AC/services/pompage.py` (HMT calculée depuis un puits, facteurs mensuels PVGIS, pompe sur courbe, variateur assorti) ; `AC/views/pompage.py` (réservoir `volume_reservoir_m3`) ; AGR/CAL159 (PLAN.md AGR2, AGR101) — fait le contraire des facteurs au pif : pompe retenue sur courbe, jamais un coefficient |
| 12 Erreurs du calcul à la main | PRÉSENT (par construction) | calcul unique serveur (AGR2) |
| 13 Ratio DC/AC | PRÉSENT | `AC/services/electrique.py` `ratio_dc_ac_max` l.3959-3969 ; alerte « surdimensionnement DC important » l.4044 |
| 14 Profil de charge fin | PRÉSENT | `AC/services/chaine_pertes.py` l.919/1059/1086 (pas du quart d'heure) |
| 15 Fond aérien/DXF | PRÉSENT (DXF) / ABSENT (DWG) | `AC/analyse_plan.py` (DXF/PDF vectoriel) ; `RP/underlay.ts` ; `AC/models.py::PhotoSite` ; export DXF présent, pas de DWG |
| 16 Catalogue modules/onduleurs | DÉJÀ PLANIFIÉ | CALX339/356/357 (import .PAN/.OND ; PLAN2.md l.109 ; dernier commit 5a75a182b les débloque sur fichiers publics) |
| 17 Animation d'ombre client | PRÉSENT | `RP/soleilPlay.ts` (CALX120) ; `RP/viewerOnly.ts` (visionneuse client) |
| 18 Vérifier une liste d'équipements sans dessiner | PARTIEL | les verdicts existent dans `electrique.py` mais ne se lisent que sur un calepinage complet (non confirmé qu'un contrôle sans plan existe) |
| 19 Pertes chaleur/poussière | PARTIEL | `AC/services/etapes/salissure.py` : 12 valeurs mensuelles saisies (jamais de défaut) ; `AC/services/thermique.py` ; **aucun champ « fréquence de nettoyage »** ni dépendance à l'inclinaison |
| 20 P50/P90 | PRÉSENT | `AC/services/incertitude.py::bloc_incertitude` ; `p50p90.py` |
| 22 Hors réseau | PARTIEL | `AC/services/batterie.py` (réseau faible/îlotage cités en docstring l.10) ; `chaine_pertes.py` bloc `hors_reseau` omis des blocs horaires ; schéma hors réseau dédié non vérifié |
| 24 Ombre d'un câble/fil | PARTIEL | types d'obstacles : cheminée, ventilation, édicule, antenne, autre, chien-assis (`apps/web/src/lib/obstacles.ts::ObstacleType`) ; pas de « ligne/câble » |
| 27 Interface en langue locale | PARTIEL | français seulement dans les sources lues ; arabe/anglais d'interface non vérifié |
| 21, 23, 25, 26, 28-30 | HORS PÉRIMÈTRE module ou sans objet | juridique/commercial/outil concurrent |

Avantage net à retenir pour le fondateur : sur la grande majorité des clusters qui touchent au calepinage (tous sauf les cas PARTIEL/ABSENT ci-dessus), les voix lues décrivent un travail manuel ou un défaut d'outil que le module **fait déjà** — le message n'est pas « construire », c'est « rendre visible et automatique ». Je n'ai pas ouvert chaque écran : les verdicts reposent sur la présence du code et des contrats, pas sur l'observation à l'écran.

## 7. PROPOSITIONS (absent ou partiel, non planifié), classées

Exclusions fondateur respectées : aucun logiciel/donnée payant, aucun traceur, aucun argent calculé dans le module de conception, aucune modification du PDF devis client. Le module a déjà la règle « aucun coefficient normatif dans le code, tout saisi avec référence » (lestage.py) : les propositions 1-3 la suivent.

| # | proposition | preuves (fils) | plus petite version crédible | invisible / automatique pour un non-ingénieur |
|---|---|---|---|---|
| 1 | **Verdict « string, micro-onduleur ou optimiseur » selon le toit** | 3 pages (zelfopwekken R20 ; elektroda R40, R42 titres/résumés) : https://zelfopwekken.nl/kennisbank/omvormers/omvormers-meerdere-dakvlakken ; https://www.elektroda.pl/rtvforum/topic3685683.html | Une ligne dans l'étape électrique : « N pans, ombre max X % sur une chaîne, M panneaux → plutôt string / micro / optimiseur », les seuils (ex. 3 pans, 6 panneaux, 5 %) étant des réglages société SAISIS avec référence (jamais en dur) ; calcul sur le résultat `ombrage_chaines.py` | Bandeau qui apparaît seul quand la règle se déclenche, une phrase, un bouton « voir pourquoi » |
| 2 | **Case « interrupteur-pompier / arrêt rapide / avis incendie » dans le dossier réglementaire** | 3 pages (gramwzielone R51-R52 ; myenerjisolar R58/R62 accès incendie) : https://www.gramwzielone.pl/energia-sloneczna/103977/ochrona-instalacji-fotowoltaicznej-na-szostke ; https://www.myenerjisolar.com/ges-projesi-nasil-cizilir-muhendislik-yerlesim-plani-ve-onay-sureci/ | Une ligne de gabarit `GabaritDossierReglementaire` (déjà un modèle) : « interrupteur pompier prévu ? avis incendie obtenu ? » + une ligne dans la nomenclature protections, seuil saisi par la société avec sa source | Coché par défaut selon le gabarit du pays/société ; la pièce se génère avec le dossier |
| 3 | **Fiche onduleur : « entrées MPPT indépendantes ? » et alerte** | 1 résumé de fil (zonstraal R16, ≤2017) : https://www.zonstraal.be/forum/viewtopic.php?t=20222 ; appuie aussi R12 | Un champ booléen sur la fiche onduleur ; si faux, le moteur de chaînes traite les entrées comme une seule | Rien à faire : le catalogue porte le champ, l'avertissement est automatique |
| 4 | **Contrôle rapide sans dessin** (module + onduleur + N modules/chaîne + température mini → verdicts Voc/Vmp/Isc/ratio) | 3 titres de fils elektroda (R36, R50, R56) : https://www.elektroda.pl/rtvforum/topic4112334.html ; https://www.elektroda.pl/rtvforum/topic4118071.html | Un formulaire 4 champs qui appelle les fonctions de verdict déjà dans `electrique.py` ; peut servir au commercial avant tout calepinage | Pré-rempli depuis le devis/stock ; résultat en vert/orange/rouge |
| 5 | **Type d'obstacle « ligne / câble aérien »** | 1 titre de fil (R43) : https://www.elektroda.pl/rtvforum/topic4062535.html | Ajouter un type fin (longueur + hauteur) à `ObstacleType` ; ombre portée en bande | Choisi dans la liste existante ; pas de réglage |
| 6 | **Saisie « fréquence de nettoyage » à côté de la salissure** | 3 pages (fritts R14 ; solarpect R72 ; DT) : https://fritts.nl/zonnepanelen-oost-west-plat-dak/ | Un champ société optionnel (jours entre lavages) qui annote la salissure mensuelle ; rien calculé si non saisi (règle CALX161) | Invisible tant que non saisi |
| 7 | **Export DWG** (en plus du DXF existant) | 1 page vendeur (BlueSol R46) : https://www.gramwzielone.pl/?p=15764 | Convertir le DXF existant ; faible priorité | Un bouton dans le panneau Documents |
| 8 | **Interface arabe** | demande non mesurée (R78) ; 0 voix installateur | Chaînes d'interface et PDF ar ; seulement si un client l'exige | Choix de langue au niveau du profil |

Non proposé faute de preuve : réseau faible (0 source lue), toit d'immeuble partagé (1 titre), facture par paliers (hors module).

## 8. LIMITES

- Corpus de vraies voix d'utilisateurs : quasi nul (elektroda, tweakers, zonstraal, murator fermés). Les chiffres « fils (n) » mélangent vendeurs et titres de fils ; ils ne mesurent pas la fréquence d'un irritant dans la communauté.
- Les lignes R (résumés de recherche) peuvent contenir des paraphrases erronées du moteur ; à confirmer en ouvrant le fil à la main (EL…, zonstraal) quand la connexion le permet.
- Les URLs des vendeurs/concurrents (Heaven Green, OpusFlow : concurrents directs de Solar Monkey/Sollit) ne sont pas indépendantes.
- Vérifications de code = recherche de texte, pas exécution.

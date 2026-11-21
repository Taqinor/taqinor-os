# C3 - Fichiers PAN/OND officiels et rapport PVsyst (recherche web, 21/11/2026)

Budget : 14 WebSearch sur 16 ; aucun fichier .PAN/.OND ouvert ni telecharge. Un seul PDF ouvert (rapport Enabel).

## PARTIE A - Fichiers composants

### A1. Jinko Tiger Neo .PAN : AUCUN fichier officiel public trouve
- https://jinkosolar.eu/downloads/pv-downloads/ : filtres = Datasheets Tiger Neo 3.0/2.0, certificats, manuels, WEEE, garantie, Other. Aucune entree PAN/PVsyst (lecture par WebFetch). Liens directs PDF sans login. Aucune mention de licence. Portail distributeurs reserve : https://portal.jinkosolar.eu/distributor/
- https://jinkosolar.eu/downloads/ et https://www.jinkosolar.com/en/site/dwcasestudy/51 (centre de telechargement .com : datasheets, manuels, certificats) : aucune entree PAN.
- Indice (resume de recherche, non confirme en ouvrant la page) : la page produit Tiger Neo 2.0 jinkosolar.eu dit que les PAN existent ; ma lecture de la page n'y a trouve aucun lien PAN. Statut : non verifie.
- Un site tiers (cronologia.apdc.pt) cite "PAN file (SGS 2025)" mais est un agregateur, lien 404 : exclu.
- Conclusion : fichiers vraisemblablement sur demande / via portail distributeur ou depuis la base PVsyst. Format : non verifie.

### A2. Canadian Solar TOPBiHiKu / TOPHiKu .PAN : AUCUN fichier officiel public trouve
- https://www.csisolar.com/downloads/ : categories Modules (TOPBiHiKu7, TOPBiHiKu6, TOPHiKu6, HiHero, All-Black), Inverters, Kits, Accessoires, Storage, brochures. Pas d'entree PAN/PVsyst. Pas de login, tailles non indiquees. Pages regionales equivalentes : /na/downloads/, /emea/downloads/, /au/downloads/ (non ouvertes, vues via recherche : datasheets seulement).
- https://support.csisolar.com/hc/en-us/articles/15207398558093-TOPBiHiKu7-CS7N-TB-AG : HTTP 403 pour mon outil ; (resume de recherche) datasheets EN/PT seulement. Non verifie.
- Seuls PAN trouves : modules anciens CS6K-270P / CS6K-275M, faits par CFV Labs (tiers) et heberges sur pvpmc.sandia.gov (https://pvpmc.sandia.gov/download/3557) et DuraMAT datahub (https://datahub.duramat.org/dataset/pv-performance-modeling-data/resource/6bf975f3-1134-4a2f-82f3-a56b25e97f36). Source publique (labo/agence), mais modules obsoletes ; PVsyst 6, non ouverts, licence non lue. Utilisables pour tester un parseur, pas comme produit du catalogue.

### A3. Huawei SUN2000 .OND : AUCUN fichier officiel trouve
- solar.huawei.com / support.huawei.com : resultats = datasheets et manuels, aucune mention PVsyst/OND. Pas de page de telechargement OND trouvee. Non verifie si disponible via portail installateur connecte.
- Un fil pvlib (https://groups.google.com/g/pvlib-python/c/HQikx3eKSDM) mentionne un "Huawei_Sun2000_40KTL_US_SLR.OND" joint par un utilisateur : source tierce, non officielle, exclu.

### A4. Deye .OND : AUCUN
- https://www.deyeinverter.com/download/documents : 6 categories (Datasheet, Manuels, Declaration & Certificat, Marketing, Company, Brochures), "0 Result" a la lecture, pas de PVsyst/OND. Pas de login visible.

### A5. Documentation publique du format par PVsyst
- https://www.pvsyst.com/help/getting-started/file-organisation/user-data/format-of-pvsyst-files.html (ouvert) dit : format texte depuis la v6.40 (binaire avant, <=6.39) ; UTF-8 depuis la v6.80 pour .PRJ/.VCi/.PAN/.OND ; "intended for internal use only" ; "We provide no support regarding this format" ; fichiers "should not be modified".
- Donc PVsyst ne documente PAS la liste des champs ; il faut s'appuyer sur un parseur existant (pvlib.iotools.read_panond, cite par la recherche, non ouvert ; forum PVsyst https://forum.pvsyst.com/topic/430-pan-file-format/ renvoie 405, non lu).
- Aide import : https://www.pvsyst.com/help/getting-started/file-organisation/user-data/projects-and-pv-components/import-projects-and-components.html (vu en resultat de recherche seulement).

### Voie de secours realiste
Les PAN/OND de Jinko, Canadian Solar, Huawei, Deye sont dans la base integree de PVsyst (fichiers "Original PVsyst database" visibles dans le rapport B1) ; ils s'obtiennent en les exportant depuis le logiciel PVsyst installe, ou en les demandant aux fabricants. Non verifie : conditions de redistribution.

## PARTIE B - Rapport PVsyst reel

### B1 (meilleur, ouvert et lu integralement) : Al-Bakri School, Hebron (Palestine) - PAS le Maroc
- PDF : https://www.enabel.be/app/uploads/2026/07/Annex-9-PV-System-report_p.pdf (agence belge de cooperation Enabel, annexe 9 d'un dossier d'appel d'offres ; page parente non trouvee). Pas de mention de licence lue (non verifie : texte hors rapport).
- PVsyst V7.3.1, simulation 31/03/2026, variante VC0, 8 pages, 22,86 kWp, 36 modules, 2 sous-champs.
- PRESENT : site (lat 31,53 N, lon 35,09 E, alt 896 m, UTC+2) ; meteo Meteonorm 8.1 (2006-2011) synthetique ; plan fixe, inclinaison/azimut 28/28 ; sheds au sol (largeur 11 m, GCR 43,7 %) ; transposition Perez ; modules Trina TSM-DEG21C-20-635Wp x36 (18 en serie x 2 strings) ; onduleurs Growatt MID 22KTL3-X et MID 20KTL3-X (MPPT 50 % chacun) ; salissure 2,0 % ; Uc 29,0 / Uv 0,0 ; LID 2,0 % ; mismatch modules 2,0 %, strings 0,1 % ; qualite module -0,4 % ; degradation 0,4 %/an ; resistance de cablage DC 579 mOhm (1,5 % STC) ; AC 0,41 % ; courbe IAM (Fresnel, n=1,526/1,290) ; ombrages proches (diagramme iso) ; tableau mensuel (GlobHor, DiffHor, T_Amb, GlobInc, GlobEff, EArray, E_Grid, PR) ; diagramme de pertes complet ; resultat 38 542 kWh/an, 1 686 kWh/kWp/an, PR 83,12 %.
- MANQUANT : courbe d'horizon (horizon libre indique), fichier meteo horaire brut, parametres detailles des modules/onduleurs (le rapport ne cite que fabricant/modele : il faut les PAN/OND de la base PVsyst), coordonnees exactes du champ / dimensions detaillees du calepinage.
- Interet : tous les parametres de pertes demandes y sont ; bon rapport de reference pour comparer un moteur, mais site et modules differents du catalogue.

### B2 : rapports marocains - uniquement des copies Scribd (exclues par la regle : pas de miroir)
Vus en resultats de recherche, non ouverts : Casablanca 7,6 kWp V7.2.9 (https://www.scribd.com/document/600596331/Ahmed-ALAA-ELGAML-PV-system), Oujda 35,6 kWp V7.3.4 TRIAL (https://www.scribd.com/document/658661854/rapport-PVSYS), Malloussa 1197 kWp V7.2.8 (https://www.scribd.com/document/677709862/Malloussa-Project-VC0-Report). Provenance et licence inconnues. Pistes officielles non verifiees : article Ibn Tofail (https://www.degruyterbrill.com/document/doi/10.1515/ehs-2023-0064/html), article Fes (https://file.techscience.com/ueditor/files/fdmp/TSP_FDMP-18-6/TSP_FDMP_22095/TSP_FDMP_22095.pdf, 5,94 kWp, compare mesure vs PVsyst) : non ouverts, contenu en entrees non verifie.

### B3 : Saint-Pourcain-sur-Sioule "Rapport PV syst OMBRIERES" (France, 241 kWp, V7.3.1 d'apres la recherche) : URL en 404 a l'ouverture, non verifie.

### Aucun rapport marocain officiel (MASEN/IRESEN/ONEE/universite) ni rapport d'exemple publie par pvsyst.com trouve dans ce budget.

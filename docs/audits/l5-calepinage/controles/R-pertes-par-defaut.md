# R — Valeurs de départ des quatre pertes (salissure, LID, indisponibilité, câbles)

Recherche du 23/11/2026. Seules les pages que j'ai OUVERTES portent une valeur citée ; ce qui ne vient que d'un résultat de recherche est dit « non ouvert ». Budget : ~22 recherches, ~24 pages (plusieurs échecs : nrel.gov injoignable, pages PDF illisibles par l'outil puis relues en local avec pdftotext).

## Synthèse

| Perte | Valeur recommandée | Fourchette publiée | Source principale (ouverte) |
|---|---|---|---|
| Salissure (annuelle, nettoyage ≈ 2×/an + pluie) | **3 %** | 1,95 % (nettoyage mensuel, Benguerir) à 5,8 % (sans nettoyage, site minier marocain) ; défaut 2 % PVWatts, 3 % PVsyst 6.02 | Abraim 2022, https://elib.dlr.de/189135/ ; Ghennioui 2026, https://elib.dlr.de/223442/1/Abraim2026online1-s2.0-S2590123026011187-main.pdf |
| LID : PERC type p | **1,5 %** | 0,6 % (médiane PVEL) à 2 % (suggestion PVsyst), « 1 à 3 % » | https://www.pvsyst.com/help/project-design/array-and-system-losses/lid-loss.html |
| LID : TOPCon type n | **1,0 %** | 0,4 % (médiane PVEL) à ≤ 1 % (garantie 1re année fiches) | https://taiyangnews.info/technology/kiwa-pvel-2026-module-reliability-testing-scorecard |
| LID : HJT | **1,0 %** | 0,7 % (PVEL LID) + 0,4 % (LeTID) | idem TaiyangNews |
| LID : inconnue | **1,5 %** | défaut PVWatts 1,5 % ; PVsyst 2 % si saisi | https://docs.nlr.gov/docs/fy14osti/62641.pdf |
| Indisponibilité | **2 %** | 1 % (médiane parc US) à 3 % (PVWatts) ; 5 % (P90) | https://www.osti.gov/biblio/2318550 |
| Câbles CC (nominal à STC) | **1,5 %** | 1 à 3 % (3 % = maximum UTE) | UTE C 15-712-1 (texte ci-dessous) |
| Câbles CA | **1,0 %** | 0,5 à 3 % (1 % recommandé, 3 % maximum) | UTE C 15-712-1 §11.3 |

## 1. Salissure
- **PVWatts v5** (Dobos, NREL/TP-6A20-62641, sept. 2014, https://docs.nlr.gov/docs/fy14osti/62641.pdf) : tableau 6, soiling « 2 % », total 14 % ; le total est multiplicatif, pas additif (éq. 9).
- **PVsyst** (aide « Soiling loss », https://www.pvsyst.com/help/project-design/array-and-system-losses/soiling-loss.html) : pas de valeur par défaut ; en climat modérément pluvieux et résidentiel, salissure « typically low and can be neglected (less than 1%) » ; valeurs MENSUELLES possibles « because soiling depends heavily on rainfall ». Le tableau Sandia SAND2013-3880P (https://www.osti.gov/servlets/purl/1661115, lu en local, colonnes difficiles à séparer) donne 3,0 % pour PVsyst 6.02.
- **IEA PVPS T13-21:2022** (Soiling Losses, https://iea-pvps.org/wp-content/uploads/2023/01/IEA-PVPS-T13-21-2022-REPORT-Soiling-Losses-PV-Plants.pdf) : perte mondiale « at least 3% to 4% » de la production en 2018, 4–7 % attendus en 2023 ; la part croissante des toitures peut aggraver (nettoyage rarement optimal). Aucun chiffre marocain trouvé dans ce rapport.
- **Maroc, Benguerir (Green Energy Park, IRESEN/UM6P)** :
  - Abraim et al., Solar Energy Advances 2 (2022), https://elib.dlr.de/188235/ : taux annuel moyen PV −0,23 %/jour ; pertes plus fortes pendant les pluies rouges ; semi-aride.
  - Abraim et al., Energy Conversion and Management 270 (2022), https://elib.dlr.de/189135/ : perte PV 1,95 % avec nettoyage « mensuel » (page ; résumé de l'outil), optimum économique ≈ toutes les 3 semaines. Centrale 1 MWe, pas une toiture.
  - Ghennioui et al., Results in Engineering (2026, preuve acceptée), https://elib.dlr.de/223442/1/Abraim2026online1-s2.0-S2590123026011187-main.pdf : site MINIER (poussière anthropique) juil. 2022–juin 2023, 0,30 %/jour, perte annuelle **5,8 %** sans nettoyage, 1,9 % avec 14 nettoyages ; pluie 200,6 mm/an concentrée de décembre à mars. Cas défavorable, pas résidentiel.
  - Abraim et al., PVSMS (manuscrit, https://elib.dlr.de/195426/1/PVSMS_Clean_Manuscript_R1.pdf) : saison sèche 0,25 %/jour (7,48 % en 30 jours), début de saison humide 0,10–0,16 %/jour (même site minier).
  - Mehdi et al. 2024 (https://zenodo.org/records/13959340) : lames de verre, 2 semaines sans pluie → rapport de salissure 6,9 %.
- **Recommandation : 3 % par an** pour toit raccordé, hypothèse de 2 nettoyages/an (fin d'été et avant l'hiver) en plus de la pluie — fréquence NON sourcée, à confirmer ; 2 % en côtier pluvieux (Casablanca, Rabat, Tanger), 4 % en intérieur aride (Marrakech, Fès) ou à proximité de chantier/route. Pourquoi : le seul nombre propre au Maroc sous nettoyage fréquent (1,95 %) vient de centrales à nettoyage mensuel, que le client ne fera pas ; sans nettoyage, 5,8 % sur site minier ; 3 % coïncide avec PVsyst 6.02 et l'ordre de grandeur mondial IEA.
- **Profil mensuel : AUCUNE série mensuelle publiée trouvée.** Seule la forme est sourcée (maximum en saison sèche, minimum de décembre à mars). Proposition de forme, hypothèse TAQINOR non sourcée, moyenne 2,96 % ≈ 3 % : jan 1,5 · fév 1,5 · mar 2 · avr 3 · mai 3 · juin 4 · juil 4,5 · août 4,5 · sept 4 · oct 3,5 · nov 2,5 · déc 1,5 (à mettre à l'échelle selon la zone).

## 2. Dégradation initiale (LID)
- **PVsyst « LID Loss »** (https://www.pvsyst.com/help/project-design/array-and-system-losses/lid-loss.html) : « PVsyst does not propose LID loss as a default value » ; si saisi, défaut suggéré 2 % ; plage « typically ranges from 1% to 3% » ; l'effet n'existe que sur wafers p dopés au bore (le type n n'est pas concerné) ; les fabricants ne publient pas la valeur.
- **PVWatts v5** : LID par défaut 1,5 %, « some premium modules may experience lower LID ».
- **PVEL / Kiwa, Scorecard 2026** (via https://taiyangnews.info/technology/kiwa-pvel-2026-module-reliability-testing-scorecard, source secondaire ; scorecard primaire non ouvert) : LID médiane TOPCon 0,4 %, PERC 0,6 %, HJT 0,7 %, xBC 0,6 % ; LeTID médiane 0,1 % (TOPCon, xBC, PERC) et 0,4 % (HJT). Ce sont des médianes, pas des pires cas.
- **Fiche Trina Vertex S+ i-TOPCon Ultra** (https://www-cdn.trinasolar.com/wwwstorage/sites/3/NEG18R.20.pdf, lue en local) : garantie « 1 % degradation first year », 0,4 %/an ensuite. D'autres fiches TOPCon (BYD, TCL) citent ≤ 1 % : résultats de recherche seulement, non ouverts.
- **Recommandation** : PERC p 1,5 % (PVsyst suggère 2 %, médiane PVEL 0,6 % : 1,5 % laisse de la marge sans reprendre le haut de fourchette) ; TOPCon 1,0 % (plafond de garantie 1re année) ; HJT 1,0 % (0,7 + 0,4) ; inconnue 1,5 % (défaut NREL). Pas de fiche PERC ouverte.

## 3. Indisponibilité
- **PVWatts v5** : « Availability 3 % » (tableau 6) ; la comparaison du manuel remet 0 % pour les périodes d'arrêt retirées.
- **PVsyst** (https://www.pvsyst.com/help/project-design/array-and-system-losses/unavailability-loss.html) : pas de valeur par défaut ni typique dans l'aide ; l'effet « has only a statistical meaning ». Sandia SAND2013-3880P : « System Unavailability 2% at 7.30 days/yr » pour PVsyst 6.02.
- **NREL/TP-5K00-88769** (Deline et al., 2024, 1 128 systèmes américains ; https://www.osti.gov/biblio/2318550) : disponibilité système médiane 0,99, P90 0,95 hors six premiers mois ; plus faible les six premiers mois ; pire pour les gros onduleurs (les onduleurs de chaîne de toiture sont du côté favorable). La perte moyenne « 2,3 % » vue en résultat de recherche n'est PAS dans la page ouverte : non vérifiée.
- **Recommandation : 2 %.** Pourquoi : entre la médiane (≈ 1 %) et le défaut PVWatts (3 %), sans surveillance garantie chez le client. Coupures réseau marocaines : **aucune source ouverte trouvée**.

## 4. Pertes de câbles
- **UTE C 15-712-1** (édition juillet 2010, copie https://f1atb.fr/wp-content/uploads/2022/10/photovoltaique-norme-UTE-C157-12-1.pdf ; l'édition 2013 en vigueur n'a pas été ouverte) : §11.2 chute de tension maximale côté continu « 3 % à ImppSTC » ; §11.3 côté alternatif : 3 % maximum, 1 % recommandé. **Pas de « 1 % conseillé » côté CC dans ce texte** (je ne l'ai pas trouvé).
- PVsyst 6.02 (SAND2013-3880P) : fraction de perte CC globale 1,5 % à STC ; aide PVsyst « Ohmic losses » (https://www.pvsyst.com/help/project-design/array-and-system-losses/ohmic-losses/index.html) : la perte annuelle réelle vaut « usually around 60% » de la fraction nominale saisie.
- PVWatts v5 : câblage 2 % + connexions 0,5 %. Solargis Evaluate (https://kb.solargis.com/docs/solargis-evaluate-simulation-chain) : CC 2 %, CA basse tension 1 %.
- **Recommandation : CC 1,5 % + CA 1,0 % = 2,5 % nominal**, soit l'équivalent PVWatts câblage + connexions ; en énergie annuelle PVsyst en donnerait ≈ 60 % (≈ 1,5 %), donc 2,5 % reste prudent. À remplacer par le calcul réel dès que les longueurs sont connues.

## 5. Cohérence avec un total de 14 à 20 %
Calcul multiplicatif (méthode PVWatts éq. 9), PERC : salissure 3 × LID 1,5 × indispo 2 × câbles 2,5 → 1 − 0,97·0,985·0,98·0,975 = **8,7 %** ; TOPCon (LID 1,0) : **8,2 %**. Avec le mismatch 2 % du calepinage : 10,5 % (PERC). En ajoutant, à titre d'illustration non sourcée, ombrage 3 % et rendement onduleur 3 % : ≈ 15,8 %. La somme reste donc dans 14–20 %, en bas de fourchette ; la température et la qualité module du calepinage s'ajoutent, ce qui rapproche du milieu. Attention : le « 14 % passé à PVGIS » n'a pas à porter ces postes une seconde fois (double compte si calepinage + PVGIS les appliquent tous deux).

## 6. Non trouvé
- Profil mensuel de salissure marocain publié ; fréquence de nettoyage réelle des toits marocains ; mesures de salissure sur toiture résidentielle à Casablanca, Rabat, Marrakech, Agadir, Fès, Tanger (étude Rabat de Dahlioui 2019 : « 4 %/an » vu en résultat de recherche, non ouvert).
- Disponibilité liée aux coupures du réseau marocain ; PVsyst : valeur par défaut d'indisponibilité (le « 2 % » vu sur le forum n'est pas ouvert) et valeurs de perte CA.
- Scorecard PVEL primaire ; fiche PERC ; Fraunhofer ISE : aucune donnée LID chiffrée trouvée (seulement UVID TOPCon) ; UTE C 15-712-1 édition 2013.

# Lot E — écrans : maquettes v2, beauté, téléphone et tablette, fonctions manquantes (tour 2 du L5, consolidation du 23/11/2026)

Relecteurs lus : B2 (beauté, 13 écrans contre v1 et v2, planches `trio/` regardées : Main, ResultatsIncomplet, Telephone, Documents), T2 (téléphone puis tablette) ; études R1 (beauté, simplicité) et R2 § B-C (fonctions) ; maquettes v2 (`LANGAGE.md`, 14 `.dc.html`, rendus regardés dont Presentation). Code lu sur la tête `b06468cc8` (plis depuis `bfb859c90` vérifiés par `git log bfb859c90..HEAD` : ACAL1310 `c900d23529`, ACAL1336 `7ced3e5be6`, ACAL1408 `9910b183cb`, ACAL1515 `84087c1d28`, ACAL1442 `eea8a4c5e9`, ACAL1516 `3726f42d3a`, ACAL1344 `1faaf11a36`). Événements : `registre/evenements/T2-consolidation-E.jsonl` (19).

## 1. Comptes
- **Verdicts lus** : 33 lignes, 31 corrections (B2 : 2 lignes en remplacent une) — **ok 17 · partiel 13 · non-fait 0 · faux 0 · régression 0 · déjà-présent 0 · non essayé 1** (ACAL385).
  Partiels → reprises : 434→1820 · 441→1821 · 437→1822 · 428+429→1823 · 1312→1835 · 1313→1836 · 1314→1837 (+1839, 1840) · 423→1818 (+1807, 1815) · 957→1819 ; **doublon** : 436 (teinte = ACAL1408 plié ; « année entière » = ACAL1620, lot C) ; **preuves à rejouer** (pas un défaut vu) : 432, 442.
- **Constats vus 19** (B2 7 : S3 5, S4 2 ; T2 12 : S2 6, S3 6) : **retenus 16** (S2 6, S3 8, S4 2 absorbés par la coque ACAL1802) · **doublons 3** (T2-B2-002 = ACAL1640, lot C ; T2-B2-003 = ACAL1442 plié ; T2-T2-008 = ACAL1408 plié) · écartés 0. Causes (19 événements) : lue 16, probable 2, à reproduire 1.
- **Tâches 42, ACAL1800-ACAL1841** : M0 7 (coque 1800-1805, instrument 1806) · M1 6 (1807-1812, les six S2 de T2) · M2 27 (1813-1824 défauts et reprises, 1825-1838 un écran chacun, 1839 scène client) · GATED 1 (1840) · Acceptation 1 (1841). Modèles : opus 8 · sonnet 29 · haiku 5. « Reproduire puis corriger » : 1813, 1816, 1820 (cause à reproduire d'abord).

## 2. Classes
Neuve : **K-COUCHE-FIXE** (`T2/classes/K-COUCHE-FIXE.md`) — rien d'utile ne naît sous une pièce fixe ou flottante ; 8 endroits, garde unique ACAL1824 (`elementFromPoint` aux trois tailles). Complétées (`T2/classes/complement-E.md`) : K-STYLE, K-ACTION-ENFOUIE, K-GESTE, K-RETOUR-FAUX.

## 3. Choix de produit tranchés (aucune question à Reda ; jamais enregistrés comme décisions de Reda)
| # | Choix | Retenu (règle) | Coût si faux |
|---|---|---|---|
| 1 | bande « Cible estimée… (non vendue) » de 52 px | RETIRÉE ; la cible se lit dans la pilule « Besoin d'après la facture » ; un refus de taille reste dit une fois avec son lien (maquette v2 + le plus simple) — ACAL1805 | le mot « non vendue » quitte le premier écran ; réversible (une condition) |
| 2 | filtres de la Liste | statuts SERVIS du calepinage, pas « Prêt à envoyer / Devis envoyé / Signé » de la v2 (rien d'inventé ; statuts de devis = autre couche, règle n° 4) | pas de filtre par état du devis |
| 3 | cibles tactiles | 44 px même où la v2 dessine 38-42 (contrat K7 avant la maquette) | puces et segments 2 à 6 px plus hauts que la v2, écart accepté nommé |
| 4 | Démarrage rapide | plein écran sous un bandeau flottant à fil d'Ariane (maquette v2) — ACAL1826 | barre latérale de l'ERP absente sur cette page |
| 5 | tablette | panneau flottant à droite, tiroir gardé au seul téléphone (maquette v2) — ACAL1835 | carte plus étroite (796 px) |
| 6 | entrées de visite | UNE entrée dans le bandeau : « Relevé » au doigt, « Montrer au client » à la souris ; compensée par le contrôle retiré au choix 1 (le plus simple, K6 net 0) — ACAL1809 | un bouton de plus dans le bandeau |
| 7 | orientation tapée au relevé | écrite sur le pan en source « saisie » ; la règle CAL64 « un azimut boussole porte sa précision » est gardée — ACAL1814 | le relevé n'a pas d'azimut quand il est tapé (le pan le porte) |
| 8 | attente de la vue client | écran neutre « La vue 3D se prépare… » ; le plan dessus reste pour l'échec et l'absence de 3D — ACAL1837 | le client ne voit rien du toit pendant 9-30 s |
| 9 | Présentation au bureau | même route `/client`, disposition choisie par la largeur, « Retour à l'atelier » au bureau — ACAL1838 | aucune URL dédiée au grand écran |
| 10 | relevé à la tablette | deux colonnes au-delà de 900 px — ACAL1817 | aucun (mise en page) |
| 11 | indice « Ctrl K » de la Liste, « En stock », longueur de câble | non affichés tant que la donnée ou la fonction n'existe pas (D-ACAL-71, D-ACAL-70) | écarts PROCHE nommés dans `calepinage-maquettes.libelles.json` |

## 4. Décisions ouvertes à écrire dans `docs/audits/decisions.yml` (listées, non écrites)
1. **D-ACAL-88 (proposée)** — quel chiffre de production « Montrer au client » (téléphone et grand écran) montre au CLIENT avant un résultat complet. Options : (a) aucun tant que le résultat n'est pas complet (actuel) ; (b) la borne haute dite « au plus » ; (c) l'estimation de la pose dite « estimation de la pose ». Recommandation : (b), un seul chiffre, le même que l'étape Résultats. Tâche GATED ACAL1840. Lien : D-ACAL-82, et la décision de lot D sur « quel chiffre le client lit » (numérotée D-ACAL-85 par le lot D alors que le lot C a déjà pris D-ACAL-85 pour le P90 : **collision à renuméroter par l'orchestrateur**).
2. Rappel, ouvertes et touchées par le lot : D-ACAL-68 (six photos du relevé, ACAL1319), D-ACAL-70 (position de l'onduleur, ACAL1317), D-ACAL-71 (« En stock », ACAL1318), D-ACAL-82 (Résultats complet inatteignable).

## 5. Tri des 15 fonctions de R2 § B
| # | Fonction | Tri | Raison / tâche |
|---|---|---|---|
| 1 | tarifs par période, économies heure par heure | GATED | argent et moteur de devis : hors périmètre du L5 (phase de contrôles) |
| 2 | écrêtage de pointe, puissance souscrite C&I | GATED | argent C&I, même raison |
| 3 | calendrier de nettoyage (salissure par saison) | GATED | valeur de salissure = D-ACAL-82 ; série de pluie ERA5 = nouvelle source de données |
| 4 | vérification de charge du toit plat | GATED | décision : responsabilité structurelle (« pré-étude ») ; R2 § C met en garde |
| 5 | suivi après pose, alerte de sous-performance | GATED | autre propriétaire (`installations` / `sav`) ; API des portails non vérifiées ; ACAL887 livré |
| 6 | import `.PAN` / `.OND` | MAINTENANT, au plan `stock` | sert « tout se calcule seul » (B2 n'a pu dessiner aucun schéma : fiches sans Vmp, Voc) ; parseur texte, aucune clé ni dépendance ; texte de la tâche au § 8 |
| 7 | export du site vers PVsyst | GATED | lié à ACAL486 (attend un rapport PVsyst réel) |
| 8 | schéma trifilaire | GATED | coût moyen, aucun gain de simplicité, aucun cas client nommé |
| 9 | hauteurs Open Buildings 2.5D | GATED | licence (Earth Engine) non vérifiée, gros téléchargement |
| 10 | terrain en pente pour les champs au sol | GATED | change une production vue du client (ACAL75) : décision |
| 11 | coût au m³, dimensionnement par nombre de panneaux | GATED | prix : hors périmètre |
| 12 | profils de charge types | DÉJÀ COUVERTE | `ProfilTypeConsommation` (CAL149, profils par société) + ACAL1608 (facture du lead par défaut) ; des courbes marocaines publiées restent à sourcer |
| 13 | chauffe-eau piloté par le surplus | GATED | priorité après ACAL1645 (charges à venir) ; aucun gain de simplicité |
| 14 | widget d'estimation du site public | GATED | formulaire public PARQUÉ (règle du dépôt) ; `apps/web` hors périmètre |
| 15 | pas de temps sous-horaire | GATED | aucune donnée sous-horaire gratuite (R2) |

## 6. Tâches v1 (ACAL1278-1353) à retirer ou à reformuler (l'orchestrateur les édite ; non touchées ici)
- **ACAL1293** (assembler l'étape Toit, v1) : à RETIRER — mise en page v1 construite (B2 : Toit v1 PROCHE) ; les écarts v2 sont ACAL1801-1805 et ACAL1827.
- **ACAL1327** (acceptation de la fidélité v1) : à REFORMULER — garder le rejeu des 28 tâches « code livré » pour leur FONCTION (K16) ; le verdict d'écran se juge contre la v2 dans ACAL1841.
- **ACAL1286** (specs e2e réalignées sur la coque) : à REFORMULER `@after: ACAL1801` — la géométrie change encore avec la coque v2.
- **ACAL1733** (lot D, « En savoir plus » de la bande de cible) : sans objet pour la cible après ACAL1805 ; garder seulement l'explication, portée dans la pilule.
- Gardées telles quelles (la v2 montre les mêmes blocs) : ACAL1316-1320, 1330-1332, 1346, 1347, 1349, 1350, 1353.

## 7. Ordre de construction et tâche → fichiers
1. **Coque d'abord, seule, une lane** : `calepinage/coque` (A/C/D : ACAL1437, 1617, 1727, 1730, 1731, 1733, 1745) PUIS `calepinage/coque-v2` : 1800 → 1801 → 1802 → 1803 → 1804 → 1805 → 1807 → 1809 → 1835 (`49-jetons-v2.css` neuf, `index.css`, `themeAtelier.test.mjs`, `50-coque-atelier.css`, `56-coque-responsive.css`, `CoqueAtelier.jsx`, `PanneauEtape.jsx`, `RailGuide.jsx`, `primitives.jsx`, `BarreProjet.jsx`, `roofbuilder.css`, `langageVisuel.test.mjs`, `ToitureDesign.jsx`, `ToitureDesign.calepinage.test.jsx`, `Rail.test.jsx`, `EtapeToit.test.jsx`, `E2E_HOOKS.md`). À plier avant tout écran.
2. **Puis en parallèle, fichiers disjoints** : relevé et client 1810 → 1811 → 1812 → 1814 → 1836 → 1817, 1837 → 1838 → 1840 (`releve/*`, `fileEnvoiPhotos.js`, `client/*`, `58-telephone.css`) · atelier-web 1808, 1813, 1820, 1821, 1828, 1839 (`etatVide.ts`, `formesToit.ts`, `gestesCarte.ts`, `scene3d.ts`, `shadingUi.ts`, `legendeAcces.ts`, `underlay.ts`, `mapDraw.ts` — avec le cluster A du lot B) · style 1827 (`EtapeToit.jsx`, `51-etape-toit.css`, après ACAL1445) · étape Panneaux 1818 → 1829 (`52-etape-panneaux.css`, `EtapePanneaux.jsx`) · électrique 1830 → 1831 (`EtapeElectrique.jsx`, `53-etape-electrique.css`, `EtapeSchema.jsx`) · résultats 1822, 1832 → 1833 (`EtatEcranAtelier.jsx`, `TuilesResultat.jsx`, `GraphiqueMensuel.jsx`, `ResultatIncomplet.jsx`, `54-etape-resultats.css`) · documents 1834 (après ACAL1726) · liste 1825 → 1819 · réglages 1826 (`DemarrageRapide*.jsx`, `module.config.jsx`) · onglets-site 1815 → 1816 (`HorizonPanel.jsx`) · e2e 1806, 1824 · balayage 1823 (8 écrans, après ACAL1443, 1447, 1802).
3. **Fichiers chauds** (plusieurs lanes) : `calepinage-mesures-ecran.baseline.json` (1801, 1805, 1807, 1809, 1817, 1819, 1835 : régénérer UNE fois, à la couture, après le pli des écrans), `calepinage-mesures-ecran.spec.js` (1817, 1818, 1819, 1824, 1835), `roofbuilder.css` (1802, 1813, 1815 ; ACAL1443, 1519), `langageVisuel.test.mjs` (1802, 1804, 1823), `scene3d.ts` (1820, 1839 ; ACAL1515, 1516). `plan_lanes.py` sur une copie du plan + lots D et E : 0 refus neuf (les refus « @after externe » viennent de la copie : leurs cibles sont dans le vrai plan) ; tout s'unit en une lane géante par ces fichiers partagés — à découper par l'orchestrateur selon l'ordre ci-dessus.

## 8. Tâche pour un autre plan (texte complet, sans id — à porter par l'orchestrateur)
- **stock** (`frontend/src/pages/stock/ProduitForm.jsx`, `pvondFicheTechnique.js` → stock) : « Importer un fichier `.PAN` (module) ou `.OND` (onduleur) dans la fiche technique d'un produit : Pmax, Vmp, Imp, Voc, Isc, coefficients de température, NOCT, tensions et courants d'entrée lus (fichier texte clé = valeur), chaque champ marqué « importé du fichier <nom> » et modifiable ; fini quand le fichier de démonstration d'un module 710 W remplit ces champs et que le schéma unifilaire du calepinage n'est plus un « croquis de principe ». Licence : usage privé du fichier par l'installateur (aucune redistribution). »

## 9. Preuves à rejouer au tour 3 (pas des défauts vus)
ACAL432 (refus 400 « Approbation » : société qui l'exige) · ACAL442 (bandeau de provenance : résultat complet) · ACAL437 (Dossiers, Schéma, rail, `role="status"`) · ACAL385 (spec de mesures non lancée) · Schéma et Résultats complet NON COMPARÉS (fiches complètes, D-ACAL-82) · vrais capteurs, vraie caméra, vrai iPhone (ACAL516, 518, 519) · relevé et vue client en thème sombre · lisibilité sur photo aérienne (vraie clé) · doublons pliés après la pile des relecteurs : T2-T2-008 (ACAL1408), T2-B2-003 (ACAL1442), Liste (ACAL1310, 1336), pastille kWc (ACAL1515) · vu une fois : « Confirmer » la pente → 502 (B2 § 5), toast « Erreur serveur » en sombre (T2 § 5), « Avancé » sans effet visible en Expert au téléphone (T2-T2-007) · photo de la file non rattachée au relevé (remarque d'ACAL892).

## 10. Optionnels (S4, sans tâche)
Boutons gris hérités « Terminer le tracé / Annuler le dernier point » du plein écran (T2-T2-011) · nombres à point décimal « 22.0° », « 0.5 » (ACAL519, ACAL969) · champ fichier natif « Choose File » de l'onglet Horizon (reste d'ACAL429 ; même geste qu'ACAL1541 / ACAL1443) · intitulés en capitales sur trois lignes des Allées (ACAL429) · « Raccourcis clavier » : rien à faire (ACAL1027 ok). Hors périmètre L5 : `/proposal`, moteur de devis, prix — la vue « Montrer au client » n'affiche aucun prix (maquette).

## 11. Écran → tâche (14 écrans ; nombre d'écarts portés)
Liste 1825 (5) · Démarrage rapide 1826 (7) · Toit clair 1827 (1 bloc ; 7 autres par la coque, ACAL1445, ACAL1409) · Toit sombre 1828 (4) · Panneaux 1829 (3 ; 5 pliés ou ailleurs) · Électrique 1830 (7) · Schéma 1831 (4) · Résultats complet 1832 (4) · Résultat incomplet 1833 (6) · Documents 1834 (5 ; 4 par ACAL1726) · Tablette 1835 (6 + K6) · Téléphone relevé 1836 (6) · Téléphone client 1837 (5) · Présentation 1838 (6, écran neuf).
K6 mesuré (avant → après) : carte visible au téléphone 141 → ≥ 299 px (1807) · entrées de visite 0 × 0 → 1 toucher (1809) · contrôles visibles de la tablette 25 → ≤ 19 (1835) · haut de la première carte de la liste au téléphone y 454 → ≤ 300 (1819) · saisies du relevé : cotes déjà tracées 2 → 0 (1836), précision imposée à une orientation tapée 1 → 0 (1814) · contrôles du premier écran de l'atelier au bureau : −1 (1805) +1 (1809) = 0.

# Calepinage — campagne L5 « plus de fonctions, le plus simple, le plus beau » : tour 0 du 20/11/2026

> Ce fichier est à la fois le **dossier** du complément ACAL du 20/11/2026 (les constats `C-ACAL-L5-nnn` cités par les
> tâches ACAL382 et suivantes de `docs/plans/PLAN_AUDIT_CALEPINAGE.md`) et le **fichier d'état** de la campagne
> (go-deep L5, `.claude/skills/go-deep/L5.md`) : à lire EN PREMIER pour reprendre, sur ce poste ou un autre.
> Rien n'a été construit : la demande de Reda était « only add tasks to the plan ».

**Prochaine action unique** : `work on the plan audit_calepinage` — construire d'abord la section « M0 contrats »
du complément (figer les chiffres et les gestes, contrats), seule sur `main`, puis M1 ; les tours de relecteurs L5
commencent quand le parcours guidé tourne sur une pile privée.

## 1. Demande et cadre

- Demande de Reda, mot pour mot (20/11/2026) : « i want you to enhance my calpinage module, i want it to have much more
  functionalities as the big players of the market have ( like pvsys and similar) but i want also to be extremely
  simple and easy to use, and the most pretty calpinage module. use L5 and only add tasks to the plan ».
- Niveau : L5 (nommé par Reda). Régime : **MIXTE**, lu sur `origin/main@e9b08b57e` — le module existe (signaux de
  `gabarits/regime.md` : 1 070 fichiers, 606 fichiers de test, groupe ACAL 375 tâches cochées sur 377), la demande
  ajoute des fonctions neuves ET refait la surface existante (simplicité, beauté).
- Coût : quota hebdomadaire lu à 83 % au départ (`get_usage`, « Weekly · all models ») ; formule de `L4.md` :
  k = min(3, ⌊(90 − 83 − 10) / 21⌋) = 0 tour de relecteurs cette semaine → **tour 0 seulement** (inventaire, recherche,
  contrat de sortie, tâches), arrêt à 90 %. Mesuré : les 6 lanes de lecture (≈ 1,3 M de jetons Sonnet) = 1 point.
- Poste mesuré : 8 cœurs logiques, 19 Go de disque libre (97 % plein), pile `erp-agentique` déjà lancée sans frontal
  (6 conteneurs) → aucune lane à worktree, aucun navigateur piloté ; lecture seule.
- Claim : `file:docs/plans/PLAN_AUDIT_CALEPINAGE.md` tenue par ce poste jusqu'au merge.

## 2. Ce qui a été lu (et ce qui ne l'a PAS été)

| Surface | Comment | Résultat |
|---|---|---|
| Serveur `apps/calepinage` + `core/calepinage` | 1 lane d'inventaire, preuves `fichier::symbole` | ≈ 150 routes, ≈ 108 services, 26 étapes de pertes, 491 fichiers de test ; ≈ 88 capacités servies, ≈ 13 partielles, ≈ 14 absentes |
| Écrans ERP `frontend/src/features/calepinage` | 1 lane | 23 routes, rail de 36 onglets, ≈ 100 contrôles sur la page atelier, 37 clés de réglage sans valeur de départ |
| Constructeur 3D `apps/web/src/scripts/roofPro11` | 1 lane | ≈ 33 000 lignes ; fonctions sans bouton (formes de toit, pivoter/aligner/répartir) ; 3 tables de raccourcis |
| Plans, décisions, gardes | 1 lane + exécution des gardes en lecture | 2 tâches ACAL ouvertes, 7 GATED « payant », 3 bloquées sur des fichiers de Reda (.PAN/.OND) |
| PVsyst, PV*SOL, archelios, HelioScope, SAM, pvlib | 1 lane web (18 recherches) | chaîne de pertes ordonnée de PVsyst, 25 capacités « classe PVsyst », nouveautés 2025-2026, données gratuites Maroc |
| Aurora, OpenSolar, Reonic, Solargraf, Pylon, K2 Base… | 1 lane web (14 recherches) | parcours en 4 à 6 étapes, motifs de simplicité et de beauté, critères mesurables |
| Écran réel | 3 captures du dépôt regardées par l'orchestrateur (`docs/audits/acceptation/ACAL/traces/2026-11-01/`, `docs/qa-explorer/captures/2026-11-20/`) | page très longue, îlot sombre, 9 tuiles « non calculée » sous un mur d'avertissements dont un répété 3 fois |

**Non couvert** (dit, pas caché) : aucun relecteur n'a UTILISÉ le produit sur une pile privée (pas de tour L4/L5 cette
semaine — quota) ; aucune mesure d'écran exécutée (ACAL385 la crée) ; centres d'aide Aurora et OpenSolar en 403 (pages
commerciales et blogs à la place) ; couverture de Google Solar au Maroc non vérifiée ; RatedPower et PVcase non lus ;
les libellés exacts du diagramme de pertes de PVsyst viennent d'une source secondaire (l'ORDRE officiel, lui, est
vérifié) ; aucun rapport PVsyst réel n'a été comparé au moteur (ACAL486, attend un fichier de Reda).

## 3. Diagnostic en trois phrases

1. **Fonctions** : le module calcule déjà l'essentiel d'un outil d'étude (chaîne de pertes ordonnée, P50-P95,
   électrique, batterie, variantes, rapports) ; ce qui manque face à PVsyst tient en une vingtaine de capacités
   (fichiers météo horizontaux et transposition, ombrage du diffus, table et diagramme d'ombrage, bornes d'ombrage
   électrique, balayages et optimisation, bifacial par facteurs de vue, validation publiée…).
2. **Simplicité** : la puissance est là mais elle ne se voit pas — 36 onglets, ≈ 100 contrôles, aucune valeur de
   départ (37 réglages à saisir avec leur source avant un résultat complet), simulation à lancer à la main, pas
   d'enregistrement automatique, aucun parcours guidé.
3. **Beauté** : deux dialectes visuels (39 fichiers en classes du site public), atelier en îlot sombre qui ignore le
   thème, résultats en tuiles « non calculée », scène 3D sans ciel ni matériaux, module posé toujours dessiné avec la
   même texture.

### Bilan du tour 0 (20/11/2026)

- **104 tâches écrites** : 103 dans `docs/plans/PLAN_AUDIT_CALEPINAGE.md` (ACAL382 à ACAL490 : 10 « M0 contrats », 18 M1,
  65 M2, 5 gardes, 4 GATED, 1 acceptation) et 1 dans `docs/plans/PLAN_AUDIT_SECURITE.md` (ACAL489, la capacité de vision
  de la couche IA partagée, dont les fichiers appartiennent à `securite`).
- **Chaîne de vérification** : squelette de l'orchestrateur → 7 rédacteurs qui ont d'abord cherché à RÉFUTER chaque
  prémisse dans le code (11 prémisses fausses ou partielles réécrites ou supprimées, ci-dessous) → 1 correcteur neuf
  (alignement entre lots, contre-lecture des 6 tâches les plus risquées) → gardes du dépôt rejouées par l'orchestrateur,
  toutes vertes (`check_taches_cablage`, `check_ancres_taches` : 357 ancres résolues, `check_ownership`,
  `check_decisions`, `check_plan_taches_mixtes`, `audit_registre --check`, `check_build_order`, `plan_lanes` : 0 refus).
  **Pas joué** : la critique finale par un modèle de pointe et les tours de relecteurs sur le produit réel (quota).
- **Trois défauts d'exactitude trouvés en chemin** (lus dans le code, non rejoués à l'écran) :
  1. un pan neuf part à 22° plein sud, affiché comme choisi, sans provenance ; après un enregistrement humain ces
     valeurs peuvent atteindre l'annexe « paramètres du site » visible du client (ACAL417, ACAL426) ;
  2. une heure entièrement à l'ombre garde, côté serveur, 25 % du rayonnement direct et tout le diffus
     (`shadingEngine.ts::hourlyShadeFactors` écrit 0,25 ; `etapes/ombrage_proche.py::_derater` ne multiplie que le
     direct) : ACAL467 corrige, ACAL459-461 donnent la table d'ombrage et l'ombrage du diffus ;
  3. le curseur du soleil, sa lecture et la carte d'accès solaire existent dans le constructeur mais ne sont montés
     que sur la page publique, pas dans l'atelier de l'ERP (ACAL434, ACAL436).
- **Prémisses du squelette trouvées fausses** (rien à construire, déjà présent) : diagramme de pertes complet
  (`DiagrammePertes.jsx`), graphique unique soleil + horizon (`SunDiagram.jsx`), page « pertes » du rapport, ombrière
  en géométrie réelle (`Ombriere.jsx`), limitation d'injection hors batterie (`services/autoconsommation.py`), courbe
  de charge importée et profils types (`services/consommation.py`, `profils_types.py`), routes « sans appelant »
  (aucune orpheline : `check_calepinage_actions_consommees.py` vert), bornes d'ombrage électrique (déjà calculées,
  seulement jamais imprimées → ACAL462), pvlib déjà installé en production (jamais importé par un service).
- **Écartées** : matériaux de toit (le document n'a aucun champ de couverture), export « vue client » à fond opaque
  (8 fichiers et un consommateur existant), format `.HOR` de PVsyst (propriétaire, non documenté), copier-coller entre
  pans, axe « pas inter-rangées » du balayage (exige un repavage par le moteur).
- **À router ailleurs** (autre propriétaire, aucune tâche écrite) : champs de fiche module manquants pour le modèle à
  une diode et pour l'apparence réelle du produit (coefficient de température de Isc, nombre de cellules, couleur du
  cadre — `stock`) ; constantes de gain bifacial 0,05 / 0,03 de `apps/web/src/lib/estimatorBrainV2.ts` (site public) ;
  soleil animé sur la page publique du devis (ACAL487, GATED) ; lignes des specs neuves dans `frontend/e2e/README.md`
  (`deploy`).
- **Limite connue du plan** : le planificateur fond 97 des tâches en UNE lane (elles partagent `ToitureDesign.jsx`,
  `BuilderDom.jsx`, `PanneauProduction.jsx`, les échantillons de contrat) ; le correcteur les a chaînées par `@after`.
  La construction sera donc surtout séquentielle tant que ces fichiers ne sont pas découpés.
- **Point à vérifier avant de construire ACAL485** : les conditions d'usage du fournisseur d'imagerie (MapTiler) sur
  l'envoi d'une tuile à un service d'IA tiers ; à défaut la détection n'accepte qu'une image importée par l'utilisateur.

## 4. Références nommées (une par axe)

| Axe | Référence | Ce qu'on lui compare |
|---|---|---|
| Fonction | PVsyst 8.1 (aide en ligne, ordre des pertes et variables de simulation) | chaîne de pertes, diagramme de pertes, table d'ombrage, Pxx, rapport |
| Simplicité | Reonic (6 étapes), OpenSolar (4 étapes en conception automatique), K2 Base (5 étapes) | nombre d'étapes et de saisies jusqu'au résultat |
| Beauté | Aurora (proposition 3D partageable, animation du soleil), OpenSolar (3D rendue, ombrage jour/mois/année) | scène 3D, résultats, vues client |
Sources et URL : rapports de recherche du tour 0 (non commités : scratchpad de la session) ; chaque tâche cite sa référence.

## 5. Contrat de sortie de la campagne (écrit au tour 0 ; seuils = valeurs de départ, à recaler sur la base d'ACAL385)

- Écrans dans le périmètre (liste fermée) : liste des calepinages, atelier (étapes Toit, Panneaux, Électrique,
  Résultats, Documents), Réglages simulation / Démarrage rapide, Optimiser. Écrans CENTRAUX : atelier — étape Toit,
  atelier — étape Résultats.
- Hors périmètre (signalé, jamais touché) : PDF client `/proposal` (règle #4), statuts de devis, moteur de devis
  (la production que voit le client reste la sienne — D-ACAL-6), pages du site public, argent (reste dans `ventes`).
- Appareils : bureau 1440 × 900 clair et sombre ; tablette 820 × 1180 ; téléphone 390 × 844 (WebKit).

| id | Axe | Critère | Seuil de sortie (départ) | Mesure |
|---|---|---|---|---|
| K1 | tous | constats S1-S2 ouverts | 0 | registre des tours |
| K2 | tous | constats S3 ouverts par écran | ≤ 3 | registre |
| K3 | tous | corrections contre-vérifiées par un relecteur neuf | ≥ 85 % « ok », 0 régression | registre |
| K5 | fonction | parcours critique « lead → toit → panneaux → électrique → résultat complet → devis → documents » | 3 passages sur 3 verts | spec e2e du parcours guidé (ACAL490) |
| K6 | simplicité | étapes et saisies jusqu'à un résultat complet, profil de départ appliqué | ≤ 5 étapes ; 0 saisie technique obligatoire ; contrôles visibles au premier écran : seuil fixé à la lecture de la base (≈ 100 aujourd'hui, lu dans le code) | spec de mesures ACAL385, garde ACAL478 |
| K7 | beauté | mesures d'écran | 0 classe héritée du site public dans le module ; tailles de texte et cibles ≥ 44 px : seuils fixés à la lecture de la base ; l'atelier suit le thème | ACAL385, garde ACAL479 |
| K8 | beauté | jugement par paires contre les références du § 4 | majorité des paires préférées ou à égalité, 2 relecteurs aveugles, accord rapporté | tours L5 |
| K9 | accessibilité | violations automatiques | 0 (version d'axe de la CI) | ACAL439 |
| K10 | données | chiffres servis | goldens d'ACAL382-383 inchangés sauf changement nommé par sa tâche | CI |
| K11 | serveur | critique adverse du diff par vague | 0 bloquant | une critique neuve par vague |
| K13 | fonction | promesses du complément servies | 100 % de la liste d'ACAL390 | garde d'ACAL390 |
| K14 | fluidité | délai d'interaction pendant un glisser (500 modules) | ≤ 200 ms (seuil « bon » de web.dev pour l'INP) | ACAL440 |
| K15 | exactitude | écart moteur ↔ PVGIS et ↔ pvlib sur les sites de référence | publié ; seuil de régression tiré des écarts mesurés | ACAL474 |

## 6. Décisions

Réponses de Reda du 20/11/2026 (lot de questions du tour 0), recopiées dans `docs/audits/decisions.yml` et
`docs/claude-memory/calepinage-decisions-fondateur.md` :
- **D-ACAL-31** — profil de départ sourcé : OUI. Un administrateur remplit en un geste les réglages VIDES avec des
  valeurs publiées, chacune avec sa source, marquées « valeur publiée, non mesurée » ; une clé sans source vérifiable
  reste vide et nommée. La règle « zéro chiffre inventé » tient : rien n'est codé en dur, rien n'est écrasé.
- **D-ACAL-32** — parcours guidé à 5 étapes pour TOUS par défaut ; « Mode expert » au choix, mémorisé par utilisateur.
- **D-ACAL-33** — détection du toit par IA : à planifier maintenant (crédits API inclus), en proposition que
  l'utilisateur confirme.

Choix pris seul par la session (réversibles, jamais des décisions de Reda) :
| Choix | Règle appliquée | Coût si faux |
|---|---|---|
| L'atelier suit le thème clair/sombre de l'ERP (fin de l'îlot sombre) | le plus simple pour l'utilisateur : un seul réglage | une tâche de style à refaire |
| Téléphone : consulter et relever sur place ; concevoir sur tablette ou bureau | références : aucun outil du marché ne conçoit sur téléphone | une tâche de mise en page |
| Trackers, pas sous-horaire, données payantes, calcul normatif vent/neige : hors complément | décisions existantes (D-CALX-PAYANT, décision 7 du 21/09) | aucune (inchangé) |
| Correction spectrale : pas de tâche | aucune donnée gratuite d'eau précipitable retenue par le module | à rouvrir si une source est adoptée |
| Planche du PDF client : inchangée | règle #4 ; tout changement visible client se re-confirme | aucune |

## 7. Suite de la campagne L5 (sessions suivantes)

1. Construire « M0 contrats » SEUL sur `main` : chiffres et gestes figés (ACAL382-385), contrats (ACAL386-389),
   promesses en données (ACAL390). Aucune correction ne met à jour un golden sans le nommer.
2. Construire M1 (parcours guidé, profil de départ) puis M2 par vagues ; chaque tâche à défaut de classe a son test
   rouge d'abord (clause « Test rouge d'abord ») et les gardes de classe de la section M3 sont prouvées rouges sur le
   défaut d'origine avant de compter.
3. Tours de relecteurs L5 quand le parcours guidé tourne : pile privée à variables forcées (jamais le vrai `.env`),
   4 à 6 relecteurs neufs par tour (fonction / simplicité / beauté × téléphone / bureau), jugement par paires contre
   les références du § 4, WebKit pour le téléphone si le moteur est installé sur le poste (à vérifier, jamais supposé).
4. Étage « vraie vie » (gestes de Reda, jamais de Claude) : deploy, 30 minutes de parcours écrits sur son appareil,
   5 jours d'usage réel, 3 questions de débrief ; puis lecture de la prod en lecture seule.
5. Entrées attendues de Reda : deux fichiers .PAN/.OND réels (CALX339/356/357, déjà demandés le 21/09) ; un rapport
   PVsyst réel d'un projet (ACAL486).

## 8. Constats du complément (un par tâche ; critère de `METHODE.md` §A.4)

| Constat | Critère, gravité | Tâche | Section | Objet (titre de la tâche, abrégé) |
|---|---|---|---|---|
| C-ACAL-L5-382 | C1, S3 | ACAL382 | M0 | Figer les chiffres que sert la simulation sur trois projets de référence (toit incliné résidentiel, toit plat C&I en est-ouest à châssis, champ au … |
| C-ACAL-L5-383 | C2, S3 | ACAL383 | M0 | Figer le document `roof_layout` ÉMIS par une séance scriptée du constructeur (facture, tracé, obstacle, disposition) par un golden JSON committé |
| C-ACAL-L5-384 | C13, S3 | ACAL384 | M0 | Poser la base visuelle du module Calepinage (liste, atelier — rail et étape toit, onglets Production et Documents), clair et sombre, dans une spec … |
| C-ACAL-L5-385 | C13, S3 | ACAL385 | M0 | Mesurer l'atelier par une spec rejouable : contrôles visibles au premier écran, tailles de texte distinctes, cibles tactiles de moins de 44 px, ges… |
| C-ACAL-L5-386 | C10, S3 | ACAL386 | M0 | Poser le contrat `calepinage_parcours_guide.json` (état des 5 étapes Toit, Panneaux, Électrique, Résultats, Documents et liste « ce qui manque » st… |
| C-ACAL-L5-387 | C9, S2 | ACAL387 | M0 | Poser le contrat `calepinage_profil_depart.json` (valeurs de départ SOURCÉES des 37 clés du registre de réglages, plus la liste des clés laissées s… |
| C-ACAL-L5-388 | C10, S3 | ACAL388 | M0 | Poser le contrat `calepinage_balayage.json` (demande : axes inclinaison, azimut et ratio DC/AC, chacun avec bornes et pas ; résultat : grille, opti… |
| C-ACAL-L5-389 | C10, S3 | ACAL389 | M0 | Poser le contrat `calepinage_table_ombrage.json` (table des facteurs d'ombrage par azimut × hauteur du soleil et facteur de vue du ciel par zone, t… |
| C-ACAL-L5-390 | C15, S3 | ACAL390 | M0 | Écrire la liste des promesses du complément en DONNÉES (`parcours/promesses_complement.json` : une entrée par promesse, son oracle — test ou spec —… |
| C-ACAL-L5-391 | C10, S3 | ACAL391 | M0 | Poser le contrat `calepinage_detection_toit.json` (état de disponibilité de la détection du toit par IA, demande d'une capture, PROPOSITION de cont… |
| C-ACAL-L5-392 | C15, S3 | ACAL392 | M1 | Servir l'état du parcours guidé : `GET calepinages/<pk>/parcours/` rend l'état des 5 étapes (toit, panneaux, electrique, resultats, documents) et «… |
| C-ACAL-L5-393 | C15, S3 | ACAL393 | M1 | Monter par défaut un rail guidé à 5 étapes (Toit → Panneaux → Électrique → Résultats → Documents) à la place du rail de 36 onglets |
| C-ACAL-L5-394 | C18, S3 | ACAL394 | M1 | Ajouter l'interrupteur « Mode expert », mémorisé par utilisateur, qui rend les 36 onglets rangés sous les 5 étapes ; guidé par défaut pour tous |
| C-ACAL-L5-395 | C15, S3 | ACAL395 | M1 | Réunir l'étape Électrique en UN écran : une synthèse (« Conforme » ou « n points à régler ») puis 7 sections repliables (Équipements, Cheminement &… |
| C-ACAL-L5-396 | C3, S3 | ACAL396 | M1 | Fusionner « Pertes » et « Postes de pertes » en un panneau : le diagramme et l'édition d'un poste ensemble, le diagramme se relisant après chaque p… |
| C-ACAL-L5-397 | C15, S3 | ACAL397 | M1 | Transformer « Ce qui manque encore » en liste d'actions : chaque ligne ouvre le champ exact (étape, panneau, champ), les lignes de même code sont r… |
| C-ACAL-L5-398 | C15, S2 | ACAL398 | M1 | Relancer la simulation toute seule après un enregistrement qui change la conception : le résultat se rafraîchit sans clic ; le bouton « Recalculer … |
| C-ACAL-L5-399 | C18, S3 | ACAL399 | M1 | Garder une barre d'enregistrement toujours visible, avec l'indicateur « Enregistré à HH:MM » ou « Modifications non enregistrées » |
| C-ACAL-L5-400 | C2, S2 | ACAL400 | M1 | Ranger le brouillon de l'atelier AUSSI côté serveur (par utilisateur) pour le reprendre depuis un autre poste, sans créer de version ni toucher aux… |
| C-ACAL-L5-401 | C18, S3 | ACAL401 | M1 | Afficher une barre de résumé vivante (panneaux, kWc, production) dans la barre d'enregistrement, mise à jour pendant l'édition, la production marqu… |
| C-ACAL-L5-402 | C15, S3 | ACAL402 | M1 | Passer l'atelier en disposition « studio » à partir de 1 280 px : la carte/3D à gauche, pleine hauteur et collée, l'inspecteur (rail d'étapes et pa… |
| C-ACAL-L5-403 | C9, S2 | ACAL403 | M1 | Offrir au porteur du droit `calepinage_approuver` le geste « Appliquer le profil de départ » : il remplit les SEULES clés vides du registre depuis … |
| C-ACAL-L5-404 | C9, S2 | ACAL404 | M1 | Compiler le profil de départ (données) : chaque valeur de `data/profil_depart.json` vient d'une page PUBLIÉE relue par la lane (URL, date de lectur… |
| C-ACAL-L5-405 | C9, S2 | ACAL405 | M1 | Ajouter l'écran « Démarrage rapide » dans Réglages simulation : le tableau des valeurs proposées avec leur source et un bouton « Appliquer aux régl… |
| C-ACAL-L5-406 | C1, S3 | ACAL406 | M1 | Afficher les « Champs personnalisés » et la « Source de la cible » de la fiche calepinage en mots lisibles |
| C-ACAL-L5-407 | C3, S3 | ACAL407 | M1 | Donner UNE adresse à chaque panneau : les 13 routes profondes `/calepinage/:id/<cle>` redirigent vers `/calepinage/:id?onglet=<cle>` |
| C-ACAL-L5-408 | C1, S3 | ACAL408 | M1 | Mettre à jour le guide utilisateur (section Calepinage de `docs/GUIDE_UTILISATEUR_ERP.md`) : le menu réel, le parcours en 5 étapes, la simulation a… |
| C-ACAL-L5-409 | C3, S3 | ACAL409 | M1 | Faire entrer « Comparer les variantes » et « Photos du site » dans le rail : deux onglets de leur étape à la place de deux pages hors rail |
| C-ACAL-L5-410 | C4, S3 | ACAL410 | M2 | Ajouter une rangée de puces « Forme du toit » (Plat, 1 pan, 2 pans, 4 pans, L, T) qui découpe le contour FERMÉ en pans |
| C-ACAL-L5-411 | C4, S3 | ACAL411 | M2 | Afficher une barre « Pivoter / Aligner / Répartir » sur la sélection de panneaux du placement libre |
| C-ACAL-L5-412 | C2, S3 | ACAL412 | M2 | Rendre Annuler / Rétablir joignables dès le tracé : deux boutons ↶ ↷ dans la barre du toit et Ctrl+Z / Ctrl+Y hors du panneau de disposition |
| C-ACAL-L5-413 | C2, S3 | ACAL413 | M2 | Donner un filet aux effacements de masse : « Tout effacer » (obstacles) s'annule d'un clic depuis un bandeau, « Effacer » demande une confirmation … |
| C-ACAL-L5-414 | C3, S3 | ACAL414 | M2 | Tenir UNE table de raccourcis pour l'atelier : `clavier.ts`, l'aide React et le clavier de la disposition la lisent |
| C-ACAL-L5-415 | C18, S3 | ACAL415 | M2 | Inscrire les outils et onglets de l'atelier dans la palette ⌘K de l'ERP, en mots simples |
| C-ACAL-L5-416 | C3, S3 | ACAL416 | M2 | Offrir sur la carte l'aide « Je ne connais pas la pente » : saisir un pourcentage ou une portée et une hauteur de faîtage donne la pente en degrés … |
| C-ACAL-L5-417 | C1, S3 | ACAL417 | M2 | Ne plus présenter la pente 22° et la face Sud de départ comme choisies : puces non pressées et mention « à confirmer » tant que personne ne les a c… |
| C-ACAL-L5-418 | C18, S3 | ACAL418 | M2 | Ajouter « Retirer la sélection » à la barre de sélection : le geste caché Alt + clic reçoit un bouton visible, listé dans l'aide |
| C-ACAL-L5-419 | C18, S3 | ACAL419 | M2 | Dire à quoi sert chaque onglet du rail en mots simples : une bulle `HelpTip` à côté de chaque onglet, lue dans UN glossaire |
| C-ACAL-L5-420 | C18, S3 | ACAL420 | M2 | Faire dire le prochain geste sur la carte elle-même avant tout tracé : une carte d'aide flottante « Localisez le toit » puis « Cliquez les coins » |
| C-ACAL-L5-421 | C4, S3 | ACAL421 | M2 | Ajouter « Conception automatique » à l'atelier d'un calepinage lié à un lead épinglé : un clic pose le contour du bâtiment (OSM) et l'optimiseur re… |
| C-ACAL-L5-422 | C2, S3 | ACAL422 | M2 | Permettre de créer le contour du toit en saisissant longueur × largeur (et une orientation), sans tracer sur la carte |
| C-ACAL-L5-423 | C13, S3 | ACAL423 | M2 | Rendre la page atelier utilisable au téléphone (390 × 844) : barre d'outils sans débordement et cibles tactiles d'au moins 44 px |
| C-ACAL-L5-424 | C2, S3 | ACAL424 | M2 | Caler une orthophoto de drone depuis son fichier « monde » (.jgw, .pgw, .wld en degrés) : les 4 coins de la photo de site se posent seuls |
| C-ACAL-L5-425 | C13, S3 | ACAL425 | M2 | Aimanter et guider un panneau pendant le glissé en placement libre : une ligne repère montre l'alignement avec un voisin ou la rive et la position … |
| C-ACAL-L5-426 | C1, S3 | ACAL426 | M2 | Faire dire à « Générer le devis » quelles pentes et quelles faces n'ont jamais été confirmées : un avertissement par pan, jamais un blocage |
| C-ACAL-L5-427 | C3, S3 | ACAL427 | M2 | Migrer l'enveloppe de l'atelier (`BuilderDom.jsx`, `ToitureDesign.jsx`, `OutilsVue.jsx`, `Rail.jsx`, `RetourAtelier.jsx`) des classes du site publi… |
| C-ACAL-L5-428 | C3, S3 | ACAL428 | M2 | Migrer les 11 panneaux de l'atelier (`atelier/PanneauReleve.jsx`, `PanneauPertes.jsx`, `PoseReelle.jsx`, `RepriseVisite.jsx`, `OngletCoupeRangees.j… |
| C-ACAL-L5-429 | C3, S3 | ACAL429 | M2 | Migrer 8 écrans de la racine du module (`PanneauAllees.jsx`, `PlanImporteCalage.jsx`, `Ombriere.jsx`, `SaisiePente.jsx`, `HorizonPanel.jsx`, `ModeT… |
| C-ACAL-L5-430 | C3, S3 | ACAL430 | M2 | L'atelier suit le thème clair/sombre de l'ERP : la palette `.rp9-host` est reliée aux jetons de l'ERP |
| C-ACAL-L5-431 | C13, S3 | ACAL431 | M2 | Un ciel qui suit la position du soleil apparaît quand l'atelier est incliné (`map.setSky`) |
| C-ACAL-L5-432 | C3, S3 | ACAL432 | M2 | Migrer 11 écrans de la racine du module (`FicheCalepinage.jsx`, `BoutonDevis.jsx`, `AtelierPanneaux.jsx`, `ActionsSurfacePose.jsx`, `Etiquettes.jsx… |
| C-ACAL-L5-433 | C13, S3 | ACAL433 | M2 | La texture du verre d'un module suit les proportions du panneau réellement posé (paysage, portrait, autre fiche) au lieu d'une image unique 512 × 280 |
| C-ACAL-L5-434 | C4, S2 | ACAL434 | M2 | L'atelier ERP affiche la barre du soleil que le constructeur pilote déjà (heure, saison, date, lecture jour/année) |
| C-ACAL-L5-435 | C4, S3 | ACAL435 | M2 | Quatre vues de caméra prêtes (Dessus, Sud, 3/4, Face aux panneaux), un bouton chacune, avec transition douce |
| C-ACAL-L5-436 | C4, S2 | ACAL436 | M2 | L'atelier ERP porte la bascule « Carte d'accès solaire » (et sa note) que le constructeur pilote déjà |
| C-ACAL-L5-437 | C13, S3 | ACAL437 | M2 | Des squelettes de chargement aux formes du contenu remplacent la roue seule sur le rail et sur les 4 écrans d'attente de l'atelier |
| C-ACAL-L5-438 | C13, S3 | ACAL438 | M2 | Plus aucun texte de l'atelier sous 12 px : les tailles de 10 et 11 px sont ramenées à `text-xs` (12 px) |
| C-ACAL-L5-439 | C13, S2 | ACAL439 | M2 | Une spec d'accessibilité automatique couvre les écrans centraux du module (liste, création, atelier avec rail, onglets Production et Documents) en … |
| C-ACAL-L5-440 | C13, S2 | ACAL440 | M2 | Une spec de fluidité mesure la réactivité de l'atelier pendant un glissé de panneaux sur un champ de 500 modules, sur un vrai rendu WebGL |
| C-ACAL-L5-441 | C13, S3 | ACAL441 | M2 | Une légende graphique de la carte d'accès solaire (rampe rouge → jaune → vert aux extrémités nommées) s'affiche sous la bascule quand la carte est … |
| C-ACAL-L5-442 | C3, S3 | ACAL442 | M2 | Migrer les 9 fichiers des sous-dossiers du module (`pompage/PompagePanel.jsx`, `equipements/FichesIncompletes.jsx`, `electrique/SaisiesElectriques.… |
| C-ACAL-L5-443 | C18, S3 | ACAL443 | M2 | L'onglet Production montre UN chiffre héros (le P50 annuel) et trois chiffres secondaires, avec P75/P90/P95, variabilité et PR dans un bloc replié … |
| C-ACAL-L5-444 | C18, S3 | ACAL444 | M2 | Le diagramme de pertes se lit en lignes horizontales (une par étape de la chaîne, dans l'ordre du serveur), à la largeur de l'écran, et chaque étap… |
| C-ACAL-L5-445 | C10, S2 | ACAL445 | M2 | La simulation publie le découpage MENSUEL de l'autoconsommation (`autoconsommation.par_mois`, 12 lignes consommation / production au compteur / aut… |
| C-ACAL-L5-446 | C10, S2 | ACAL446 | M2 | La journée type d'un mois trace la consommation servie à côté de la production (aujourd'hui la consommation n'arrive jamais à l'écran) ; sans courb… |
| C-ACAL-L5-447 | C10, S2 | ACAL447 | M2 | L'onglet Batterie trace l'état de charge d'une semaine réelle de la série simulée (un mois au choix, jours 8 à 14), lu dans le CSV horaire ; sans b… |
| C-ACAL-L5-448 | C10, S3 | ACAL448 | M2 | L'onglet Économie trace le flux de trésorerie année par année (barres du flux, courbe du cumul, repère du retour servi), à partir du flux que vente… |
| C-ACAL-L5-449 | C18, S3 | ACAL449 | M2 | Le diagramme de la course du soleil montre les zones d'ombrage (table de facteurs azimut × hauteur du soleil rangée au document) par-dessus la cour… |
| C-ACAL-L5-450 | C10, S2 | ACAL450 | M2 | Le remplissage automatique affiche TOUS les conseils chiffrés que le moteur sert (`suggestions[]` de `moteur/calculer`) en phrases simples avec gai… |
| C-ACAL-L5-451 | C10, S2 | ACAL451 | M2 | La simulation publie l'irradiation incidente MENSUELLE sur le plan des modules (`production.irradiation_mensuelle`, 12 lignes), dont la somme égale… |
| C-ACAL-L5-452 | C10, S3 | ACAL452 | M2 | Le tableau mensuel de la section « Production » du rapport d'étude interne gagne la colonne « Irradiation dans le plan (kWh/m²) » |
| C-ACAL-L5-453 | C10, S2 | ACAL453 | M2 | L'onglet Production trace un graphique mensuel Production / Consommation / Autoconsommée à partir de `autoconsommation.par_mois` servi |
| C-ACAL-L5-454 | C1, S3 | ACAL454 | M2 | Lire un fichier météo HORIZONTAL (EPW, ou CSV à colonnes `ghi_w_m2` + `dni_w_m2` + `dhi_w_m2`) en une série horizontale nommée, sans toucher au che… |
| C-ACAL-L5-455 | C1, S3 | ACAL455 | M2 | Transposer une série horizontale (global, direct et diffus mesurés) vers le plan de chaque pan avec pvlib, modèle et albédo NOMMÉS dans le résultat |
| C-ACAL-L5-456 | C1, S3 | ACAL456 | M2 | Déduire direct et diffus d'un fichier horizontal qui ne donne que le global, par un modèle pvlib NOMMÉ et déclaré hypothèse |
| C-ACAL-L5-457 | C1, S3 | ACAL457 | GATED | Publier P99 à côté de P50/P75/P90/P95, sous la règle D-ACAL-7 (masqué avec les autres quand les pertes du socle manquent) |
| C-ACAL-L5-458 | C2, S3 | ACAL458 | M2 | Importer un profil d'horizon depuis un fichier texte (deux colonnes azimut ; hauteur, ou le format une-hauteur-par-ligne de PVGIS) dans l'onglet Ho… |
| C-ACAL-L5-459 | C1, S3 | ACAL459 | M2 | Calculer au navigateur la table des facteurs d'ombrage DIRECT par direction du soleil (azimut × hauteur) d'un pan et la ranger au document sans la … |
| C-ACAL-L5-460 | C1, S3 | ACAL460 | M2 | Calculer au navigateur le facteur de vue du ciel de chaque pan (part du ciel diffus, supposé isotrope, que les obstructions laissent voir à ses mod… |
| C-ACAL-L5-461 | C1, S3 | ACAL461 | M2 | Ajouter à la chaîne de pertes l'étape « ombrage du diffus » : le diffus `gd_i_w_m2` est multiplié par le facteur de vue du ciel du pan |
| C-ACAL-L5-462 | C4, S3 | ACAL462 | M2 | Imprimer au rapport d'étude, section ombrage, les deux bornes d'ombrage électrique des chaînes que l'étape `mismatch_ombrage` calcule déjà |
| C-ACAL-L5-463 | C4, S3 | ACAL463 | M2 | Faire CALCULER l'étape « neige » : douze pertes mensuelles saisies par la société (réglage `neige_mensuelle_pct`, valeur + source), appliquées mois… |
| C-ACAL-L5-464 | C1, S3 | ACAL464 | GATED | Donner à l'étape « niveau d'irradiance » un second chemin, le modèle à une diode (CEC) ajusté sur la fiche du module, quand la fiche ne publie pas … |
| C-ACAL-L5-465 | C7, S3 | ACAL465 | M2 | Calculer le gain bifacial des rangées heure par heure avec pvlib `infinite_sheds` quand le site fournit la série horizontale |
| C-ACAL-L5-466 | C2, S3 | ACAL466 | M2 | Lire la pente et l'orientation du relief d'un champ au sol sur Copernicus GLO-30 (gratuit, sans compte) et les proposer dans l'écran Terrain |
| C-ACAL-L5-467 | C1, S3 | ACAL467 | M2 | Faire lire par l'étape « ombrage proche » du serveur la table d'ombrage DIRECT par direction du soleil quand le document la porte : une heure dont … |
| C-ACAL-L5-468 | C7, S2 | ACAL468 | M2 | Lancer en tâche de fond un balayage d'orientation (inclinaison × azimut) d'un pan libre et servir la grille de rendements et l'optimum |
| C-ACAL-L5-469 | C18, S3 | ACAL469 | M2 | Ajouter l'onglet « Optimiser » : lancer le balayage, voir la carte des résultats, appliquer l'optimum en un geste |
| C-ACAL-L5-470 | C2, S3 | ACAL470 | M2 | Saisir une cible de production annuelle (kWh/an) qui fixe le nombre de panneaux à poser |
| C-ACAL-L5-472 | C18, S3 | ACAL472 | M2 | Proposer le cheminement d'un câble entre deux organes le long des rangées et des rives, corrigeable |
| C-ACAL-L5-474 | C7, S3 | ACAL474 | M2 | Chiffrer l'écart du moteur contre PVGIS PVcalc et contre pvlib `ModelChain` sur quatre sites marocains enregistrés, publier l'écart MESURÉ, puis ve… |
| C-ACAL-L5-475 | C1, S3 | ACAL475 | M2 | Imprimer une « Note de validation » (méthode, sites, écarts mesurés, écart de CETTE étude) dans le rapport d'étude |
| C-ACAL-L5-477 | C7, S3 | ACAL477 | M2 | Ajouter au balayage l'axe « ratio DC/AC » : énergie livrée et écrêtage pour chaque ratio demandé, sans appel PVGIS de plus |
| C-ACAL-L5-478 | C13, S3 | ACAL478 | M3 | Verrouiller le « budget de simplicité » du mode guidé : la spec de mesures échoue si le mode guidé dépasse 5 étapes, le nombre de contrôles du prem… |
| C-ACAL-L5-479 | C4, S3 | ACAL479 | M3 | Rendre STRICTE la garde « un seul langage visuel » du module Calepinage : une fois les migrations faites, vider la table `PLAFOND` de `langageVisue… |
| C-ACAL-L5-480 | C1, S2 | ACAL480 | M3 | Garder la parité atelier ↔ serveur sur les trois projets de référence d'ACAL382 : le productible spécifique du navigateur (`productionKwh`) et celu… |
| C-ACAL-L5-481 | C2, S2 | ACAL481 | M3 | Garder les raccourcis : une seule table fait foi, et une touche nue qui déclenche une action destructive doit être annulable |
| C-ACAL-L5-482 | C13, S2 | ACAL482 | M3 | Jouer le parcours téléphone (consultation et relevé à 390 × 844) sous WebKit par `frontend/e2e/calepinage-atelier-telephone.spec.js` |
| C-ACAL-L5-485 | C10, S3 | ACAL485 | M2 | Proposer le contour et les pans d'un toit à partir d'une capture satellite par IA : `POST calepinages/<pk>/detection-toit/` envoie à l'IA la seule … |
| C-ACAL-L5-486 | C1, S3 | ACAL486 | GATED | Comparer le moteur à un rapport PVsyst réel sur le MÊME projet et publier l'écart dans la note de validation |
| C-ACAL-L5-487 | C1, S3 | ACAL487 | GATED | Ajouter à la visionneuse 3D en lecture seule un soleil animé (heure et mois) sans aucun chiffre calculé : fini quand la visionneuse expose un régla… |
| C-ACAL-L5-488 | C2, S3 | ACAL488 | M2 | Offrir dans l'atelier un onglet « Détection du toit » : le bouton n'existe que si le serveur dit la détection disponible, il envoie la capture de l… |
| C-ACAL-L5-489 | C14, S2 | ACAL489 (PLAN_AUDIT_SECURITE) | M2 | Ajouter au noyau IA la capacité `vision_toit` (image de toit → contour et pans PROPOSÉS) et un fournisseur Claude derrière le registre existant, ét… |
| C-ACAL-L5-490 | C19, S3 | ACAL490 | acceptation | Acceptation live du complément (ACAL382-456, ACAL458-463, ACAL465-470, ACAL472, ACAL474-475, ACAL477-482, ACAL485, ACAL488 (ce groupe, hors GATED A… |

# D2 — Pose des modules, structure et plans pour l'équipe (consolidation, tour 1, 21/11/2026)

Juge : consolidation D2. Dépôt lu en LECTURE seule (`C:\dev\taqinor-os\.claude\worktrees\calpinage-module-enhance-04bba5`, branche `claude/calepinage-fichiers-publics`, 5a75a182b). Rien exécuté (ni atelier, ni tests, ni docker) : chaque verdict repose sur un `grep`/une lecture faits dans cette session. Sources : les onze fichiers `bench/` (dont la passe 2 du fichier allemand, §7-§12, lue après le message du coordinateur).

Abréviations de chemins : `RP` = `apps/web/src/scripts/roofPro11`, `LIB` = `apps/web/src/lib`, `SV` = `backend/django_core/apps/calepinage/services`, `CC` = `backend/django_core/core/calepinage`, `FE` = `frontend/src/features/calepinage`, `TD` = `frontend/src/pages/ventes/ToitureDesign.jsx`.

Score = preuves (P, 1-5 : lanes distinctes × force) × adéquation (A, 1-3) ÷ effort (S = 1, M = 2, M/L = 2,5, L = 3). Les « PRÉSENT SANS ÉCRAN » sont mis en tête quel que soit leur score.

**Propriété des fichiers (vérifiée par `python scripts/check_ownership.py --owner-of`)** : `calepinage` possède `RP/*`, `TD`, `FE/*`, `SV/*`, `CC/*`, `LIB/freeLayout.ts`, `LIB/layoutVariability.ts`, `LIB/roofSetbackEdge.ts`, `LIB/roofPro2.ts`, `LIB/estimatorBrainV6.ts`, `apps/stock/models_fiche_technique.py`, `apps/ventes/roof_load.py`. **`LIB/estimatorBrainV2.ts` (le paveur `packConfig` de l'atelier) appartient à `web`** → toute tâche qui le modifie va dans `docs/plans/PLAN_AUDIT_TRANSVERSE.md`. `apps/installations/*` et `frontend/src/features/installations/*` appartiennent à `chantiers` → `docs/plans/PLAN_AUDIT_CHANTIERS.md`. Fichiers ≥ 2 000 lignes qui ne doivent pas grossir : `RP/layoutEditor.ts` (3 223 lignes, compté `wc -l`).

---

## Synthèse classée

| Rang | CAP | Titre | Verdict | Tâches | Effort | Score |
|---|---|---|---|---|---|---|
| 1 | CAP-D2-01 | Tableau comparatif du toit plat (inclinaison × portrait/paysage × marge) dans l'atelier ERP, + carte « couvre le besoin » | **PRÉSENT SANS ÉCRAN** | 2 | S | 12 |
| 2 | CAP-D2-02 | Saisir le catalogue des systèmes de fixation (le moteur de nomenclature n'a aucune porte d'entrée) | **PRÉSENT SANS ÉCRAN** | 4 | M | 4,5 |
| 3 | CAP-D2-03 | Champ « accès solaire minimal » du remplissage automatique | **PRÉSENT SANS ÉCRAN** | 1 | S | 4 |
| 4 | CAP-D2-04 | Pan « existant » pour une extension (partie pose) | ABSENT | 3 | M | 7,5 |
| 5 | CAP-D2-05 | « Pourquoi aucun module ici ? » à l'écran et sur le plan de pose | ABSENT | 2 | M | 6 |
| 6 | CAP-D2-06 | Retraits par type d'arête fixés une fois par la société | PARTIEL | 2 | S/M | 6 |
| 7 | CAP-D2-07 | Plan de pose dans la fiche chantier, lisible hors ligne | PARTIEL | 2 (1 routée) | S | 6 |
| 8 | CAP-D2-08 | Plan de lestage DESSINÉ avec zones de rive et de coin saisies | PARTIEL | 3 | M/L | 4,8 |
| 9 | CAP-D2-09 | Coupures tous les N modules, allées tous les N rangs | PARTIEL | 2 | M | 4,5 |
| 10 | CAP-D2-10 | Structure surélevée sur dalle, poteaux d'ombrière et pieux de champ comptés | PARTIEL | 3 | M | 4,5 |
| 11 | CAP-D2-11 | Fiche de pose A4 par pan pour l'équipe | PARTIEL | 4 | L | 4 |
| 12 | CAP-D2-12 | Copier-coller entre pans et « appliquer ces réglages à… » | PARTIEL | 2 | M | 4 |
| 13 | CAP-D2-13 | Fantôme rouge/ambre pendant le glissé | PARTIEL | 1 | S | 4 |
| 14 | CAP-D2-14 | Type de couverture qui choisit la fixation ; contrôles tuile/tôle (zone de serrage, porte-à-faux) | PARTIEL | 4 | L | 4 |
| 15 | CAP-D2-15 | Portrait ou paysage essayés face à l'ombre | PARTIEL | 1 | S/M | 4 |
| 16 | CAP-D2-16 | Châssis « rangs × modules » et châssis partiels | ABSENT | 3 | L | 3 |
| 17 | CAP-D2-17 | Alignement des rangées (gauche / centre / droite / justifié) | ABSENT | 1 | M | 2 |
| 18 | CAP-D2-18 | Comparer d'autres modules sur la même implantation, en un clic | PARTIEL | 2 | M | 2 |
| 19 | CAP-D2-19 | DXF : modules en blocs nommés comptables | PARTIEL | 1 | S | 2 |
| 20 | CAP-D2-20 | Check-list de chantier propre au projet | ABSENT | 2 (1 routée) | M | 2 |
| 21 | CAP-D2-21 | Quantité d'échafaudage dans la nomenclature de pose | ABSENT | 1 | S | 2 |
| 22 | CAP-D2-22 | Numéros de série posés rattachés au module et à la chaîne | PARTIEL | 2 (1 routée) | S | 2 |

22 fiches, 48 tâches (dont 4 routées vers `chantiers`, et des moitiés vers le plan transverse quand le paveur `web` doit bouger — dit dans chaque fiche).

---

## Les fiches

### CAP-D2-01 — Montrer dans l'atelier ERP le tableau qui compare les poses du toit plat, et ajouter la carte « couvre le besoin »
- **Besoin** : « 54 contre 51 panneaux sur le même toit à 7° selon cadre incliné ou pose à plat » (B5-en groupe M) ; « À 10° vous posez 18 modules de plus pour 3 % de kWh/kWc en moins » (B1 C02) ; « le plus de panneaux » contre « couvrir ma facture » (B2 n° 2).
- **Preuves** : B1 C02 + V034 ; B6 R13 (PVsyst, PVcase GM, HelioScope) et R16 (OpenSolar Ada, Scanifly MaxFill, Aurora) ; B2 n° 2 / O12 ; B5-en groupe M (2 → 15 fils) ; B5-nl clusters 6-7 (8 fils) ; B5-fr n° 15 ; B5-de passe 2 l. 633 (« 15° demande beaucoup de lest »). 6 lanes. URL : https://www.pvsyst.com/help/project-design/orientations-in-v8/shed-optimization.html ; https://www.opensolar.com/?p=14292 .
- **Qui le fait** : PVsyst « sheds » (rendement vs inclinaison, GCR sacrifié) ; OpenSolar « Max Fit / Max Offset » en deux cartes.
- **Chez nous** : **PRÉSENT SANS ÉCRAN.** Le balayage RE-PAVE déjà chaque configuration (inclinaison × azimut × portrait/paysage × marge) : `LIB/estimatorBrainV6.ts::fineGridMatrixV6` (boucle `southTilts × margins × orientations`, comptes `placedCount`/`fitCount`, `annualKwh`, `accesSolaireMoyen`) ; son tableau est peint par `RP/matrix.ts::paintComparison`, qui sort sans rien faire si `#rp9-compare` manque — or `TD` ne monte ni `rp9-compare`, ni `rp9-compare-wrap`, ni `rp9-matrix-filter` (diff des `id` de `apps/web/src/pages/preview/toiture-3d-pro-11.astro` contre `TD` + `FE/atelier/*.jsx`). Les cartes de variantes (`RP/optimizer.ts::pickVariantCards` : « la plus dense plein sud », « tente Est-Ouest », « alignée sur les arêtes ») et les puces d'objectif (`CIBLES_OPTIMISATION`) S'AFFICHENT, elles, car leur hôte `#rp9-results` est dans `TD`. La carte « couvre le besoin » n'existe pas (les trois cartes sont densité / E-O / aligné) ; la cible kWh/an est PLANIFIÉE (ACAL470) ; ACAL468/469 balaient inclinaison × azimut d'un pan SANS re-paver (ne couvrent pas ce tableau).
- **Attention argent** : la ligne du tableau porte une colonne d'économies en MAD (`RP/matrix.ts`, `fmtMad(r.savingsLow)`) : interdite dans le calepinage → à retirer à l'affichage ERP.
- **Plus petite version crédible** : en mode toit plat, sous « Recommandation », le tableau trié (nombre de panneaux, kWc, kWh/an, couverture du besoin %, source de la production « PVGIS au GPS » ou « estimation ») sans aucune colonne monétaire ; un clic sur une ligne applique la pose (déjà câblé : `renderConfig`). Entrées : contour, retraits, module du pan, PVGIS. Production non affinée par PVGIS : la ligne le dit (`sourceLabel` existant).
- **Simplicité** : étape Panneaux ; replié sous « Comparer les poses » (expert) ; les trois cartes restent l'affichage essentiel.
- **Tâches** :
  1. Monter le tableau comparatif du toit plat dans l'atelier ERP sans colonne monétaire ; fini quand un toit plat tracé dans `/calepinage/:id` affiche `#rp9-compare` avec ses lignes et qu'une garde de test refuse toute cellule « MAD » dans ce tableau. Fichiers : `TD`, `RP/matrix.ts` (option « sans montant »). Propriétaire : calepinage.
  2. Ajouter aux cartes de variantes la carte « Couvre le besoin » (le plus petit nombre de modules qui atteint la cible saisie, avec sa couverture) ; fini quand, une cible saisie, quatre cartes s'affichent et la quatrième pose ce nombre. Fichiers : `RP/optimizer.ts::pickVariantCards`. **Dépend de ACAL470** (cible kWh/an) ; complète ACAL421.
- **Score** : P 4 × A 3 ÷ S 1 = 12. Rang 1.

### CAP-D2-02 — Pouvoir saisir les systèmes de fixation de la société (rails, pinces, crochets, lests) : le calcul de nomenclature existe, la porte d'entrée non
- **Besoin** : « Enregistrer ses supports et ses sous-constructions pour ne pas les ressaisir à chaque projet » (B5-de K32) ; « liste de matériel directement issue du plan » (K18) ; « K2 Base fournit une liste de matériel » (B5-de passe 2, l. 899, 480, 846).
- **Preuves** : B5-de K32 (2 fils, 6 voix), K18 (7 fils), passe 2 l. 480/846/899 (K22) ; B2 O19 (OpenSolar Mounting Designer) ; B3 N23, l. 168/172/176 (K2, Esdec, SL Planner). 3 lanes. URL : https://forum.valentin-software.com/topic/7312-montagesystem-als-vorlage-speic… (B5-de K32) ; https://www.opensolar.com/auto-bom/ .
- **Qui le fait** : K2 Base / Esdec / SL Planner : le catalogue du fabricant est dans l'outil, la nomenclature sort du plan.
- **Chez nous** : **PRÉSENT SANS ÉCRAN.** Le modèle (`backend/django_core/apps/calepinage/models.py::SystemeFixation`, `::ComposantFixation`, mode de pose `ModePose` = toiture inclinée / bac acier / toit plat lesté / toit plat fixé / sol / ombrière), les règles de quantité (`SV/catalogue_fixation.py::BASES`, `erreur_de_regle`) et la nomenclature (`SV/fixation.py::bom_de_fixation`, onglet `FE/atelier/Fixation.jsx`) existent ; mais AUCUNE route, AUCUN admin (`admin.py` n'enregistre rien), AUCUNE commande ne crée un système (grep `SystemeFixation` hors modèles/tests : seulement `catalogue_fixation.py` et `fixation.py` en lecture). L'écran le dit lui-même : « aucune route ne LISTE encore les systèmes actifs de la société ; le champ reste un identifiant saisi » (`FE/atelier/Fixation.jsx`, en-tête « LIMITE CONNUE »). Conséquence : en production la nomenclature de fixation ne peut sortir que si quelqu'un écrit en base. Non planifié (grep des plans : CALX335/358/359/360 et ACAL81 sont cochés, aucune tâche d'écran de catalogue).
- **Plus petite version crédible** : Réglages → « Systèmes de fixation » : liste, création, modification d'un système (code, libellé, fabricant, mode de pose, PROVENANCE obligatoire) et de ses composants (rôle, produit du stock, unité, règle `{base, facteur, diviseur}` avec libellés) ; l'onglet Fixation propose la liste des systèmes actifs. Rien de pré-rempli (catalogue vide par défaut, D12).
- **Simplicité** : un administrateur saisit une fois ; la commerciale ne voit qu'un choix de système déjà rempli ; l'unique système actif s'applique seul (`_resoudre_avec_source`).
- **Tâches** :
  1. Poser le contrat `contract_samples/calepinage_systemes_fixation.json` (liste, création, refus nommés) SEUL d'abord (règle PACT10) ; fini quand le contrat est sur `main` et que `check_api_shapes.py` le lit.
  2. Servir les routes société `calepinage/systemes-fixation/` (+ composants) bornées à `request.user.company`, `company` posé côté serveur, droit `calepinage_gerer` en écriture, provenance obligatoire (`SystemeFixation.clean`) ; fini quand un POST sans provenance rend 400 en nommant `provenance` et qu'un autre locataire ne voit rien. Fichiers : `backend/django_core/apps/calepinage/views/fixation.py`, `serializers.py`, `urls.py`.
  3. Ajouter l'écran Réglages « Systèmes de fixation » ; fini quand un administrateur crée un système et deux composants et que l'onglet Fixation de n'importe quel calepinage sort leurs quantités. Fichiers : `FE/reglages/` (nouvel écran, à côté de `ReglagesGabarits.jsx`).
  4. Remplacer le champ « identifiant » de l'onglet Fixation par la liste des systèmes actifs, avec, en option lecture seule, la colonne « en stock / à commander » lue par `apps.stock.selectors` (aucun prix) ; fini quand le choix se fait dans une liste et que la colonne stock s'affiche quand le produit est relié. Fichiers : `FE/atelier/Fixation.jsx`, `SV/fixation.py`.
- **Score** : P 3 × A 3 ÷ M 2 = 4,5. Rang 2 (PRÉSENT SANS ÉCRAN).

### CAP-D2-03 — Laisser la société ou le commercial saisir l'« accès solaire minimal » sous lequel le remplissage ne pose pas de module
- **Besoin** : « Seuil d'accès solaire minimal réglé par la société et appliqué au remplissage automatique » (B6 R40).
- **Preuves** : B6 R40 (Scanifly 2026-01 SolarAI ASA/TSRF minimum, Aurora filtre TSRF) ; B3 §7.2 point 4 (Scanifly). 2 lanes, notes de version. URL : https://help.scanifly.com/setbacks-settings (B3) .
- **Chez nous** : **PRÉSENT SANS ÉCRAN.** Le filtre existe et respecte « zéro chiffre inventé » : `RP/optimizer.ts::filtrageSeuil` lit `choixOptimisationCourant()?.seuilAccesSolaire`, `RP/shadingUi.ts` (CHAMP_SEUIL, refus sans mesure). Mais rien ne l'ÉCRIT : la seule écriture de `optimisation` est l'hydratation du document (`RP/optimisationDocument.ts` → `poserChoixOptimisation`) ; `poserCibleOptimisation` ne pose que `cible` ; aucun champ dans `TD` ni `FE` (grep `seuilAccesSolaire` : 4 fichiers, tous lecteurs ou schéma `roof_layout_v2.schema.json`). B3 §7.2 le classait PRÉSENT : le moteur oui, le geste non.
- **Plus petite version crédible** : un champ « Accès solaire minimal (%) », vide par défaut, dans le panneau Disposition ; saisi, il écrit `optimisation.seuilAccesSolaire` au document ; la phrase existante dit combien d'emplacements ont été écartés ; sans obstruction retenue, le refus nommé existant s'affiche.
- **Simplicité** : expert ; vide = comportement d'aujourd'hui.
- **Tâches** :
  1. Ajouter le champ « Accès solaire minimal (%) » qui écrit `optimisation.seuilAccesSolaire` ; fini quand saisir 80 sur un pan ombré retire du pavage les emplacements sous 80 %, que la note le dit, et que le champ se relit après enregistrement. Fichiers : `TD`, `RP/optimizer.ts` (fonction de pose du seuil à côté de `poserCibleOptimisation`).
- **Score** : P 2 × A 2 ÷ S 1 = 4. Rang 3 (PRÉSENT SANS ÉCRAN).

### CAP-D2-04 — Marquer un pan « existant » pour une extension (partie pose seulement)
- **Besoin** : « Étendre ou documenter une installation existante : marquer une partie existante, ne chiffrer que l'extension, garder le câblage d'origine » (B5-de K50) ; « très courant au Maroc » (B4 n° 7).
- **Preuves** : B4 n° 7 ; B5-de P3 / K50 (13 fils cumulés passes 1+2) ; B5-en n° 3 et groupe 22 (4 fils, VF10736 « 13 000 modules ») ; B5-es n° 9 (2 → 14 fils) ; B6 R31 (OpenSolar 3.0, Eturnity, PVsyst) ; B7 U21 (4 sources). 6 lanes, forums réels. URL : https://forum.valentin-software.com/topic/9390-ertragssimulation-von-erweiterungen/ ; https://forum.valentin-software.com/topic/10736-pvsol-for-retrofit-string-redesign-of-existing-rooftop-pv-system/ .
- **Chez nous** : **ABSENT, non planifié.** Aucun champ « existant » sur un pan (grep `existant` dans `RP`, `SV`, `CC` : seulement des commentaires ; `RP/jeuReglages.ts` parle d'un pan existant au sens « déjà tracé »). Grep des plans : aucune tâche.
- **Plus petite version crédible** : une case « Pan existant (déjà posé) » + année de mise en service SAISIE ; ses modules sont dessinés grisés, verrouillés (ni remplissage, ni glissé, ni effacement de masse), exclus de la nomenclature de fixation et marqués « existant » sur le plan de pose. Autres moitiés nommées : la production de ce pan et sa dégradation depuis l'année saisie → **D4** ; le contrôle des chaînes anciennes/nouvelles sur un même MPPT → **D3**.
- **Simplicité** : étape Toit ; une case par pan, cachée tant qu'aucun pan n'est coché ; essentiel.
- **Tâches** :
  1. Poser la clé `zones[].existant` (+ `anneeMiseEnService`) au contrat `contract_samples/roof_layout_v2.schema.json`, seul ; fini quand le schéma l'accepte et qu'un document sans la clé reste octet-identique.
  2. Rendre un pan existant intouchable dans l'atelier : modules grisés, exclus de `fillAll`, du glissé et de « Tout effacer » ; fini quand cocher la case puis « Remplir » laisse ce pan inchangé et que le refus est nommé. Fichiers : `RP/zones.ts`, `RP/optimizer.ts` (pas `layoutEditor.ts` qui ne grossit pas : garde via un prédicat exporté de `zones.ts`).
  3. Exclure les modules existants de la nomenclature de fixation et les marquer « existant » sur le plan de pose ; fini quand `bom-fixation/` d'un projet 10 existants + 6 neufs compte 6 et que `plan-pose.pdf` légende les 10. Fichiers : `SV/fixation.py::_grandeurs_du_document`, `SV/planche.py::_dessin_des_modules`.
- **Score** : P 5 × A 3 ÷ M 2 = 7,5. Rang 4.

### CAP-D2-05 — Dire pourquoi aucun module n'est posé sur un pan, à l'écran et sur le plan de pose
- **Besoin** : « Toit non entièrement garni ou un seul côté posé, sans justification » ; « dire le maximum posable et la raison de chaque pan laissé libre » (B5-de §11 n° 1 et 2 — 22/24 et 14/14 fils de critiques d'offres).
- **Preuves** : B5-de passe 2 §11 n° 1-2 et K52 (98 fils) ; B3 N28 / l. 217 (HelioScope « Troubleshooting an empty Field Segment »). 2 lanes, mais forums réels nombreux. URL : https://help-center.helioscope.com/hc/en-us/articles/8536952588435 ; https://www.photovoltaikforum.com/board/41-angebote-eeg-photovoltaikanlage/ .
- **Chez nous** : **ABSENT.** Les refus de GESTE sont nommés (`RP/layoutEditor.ts::previewFreeDrag` « Ici : … », « La rangée ne tient pas à cet endroit ») et le serveur nomme un motif d'orientation refusée (`CC/tiroirs.py`), mais un remplissage qui ne pose RIEN ne dit pas pourquoi (grep « Aucun panneau ne / rien ne tient » : seulement les phrases de sélection et de glissé). Le plan de pose ne mentionne pas les pans vides (`SV/planche.py::_corps_feuille_toit`).
- **Plus petite version crédible** : quand un pan finit à 0 module, quatre causes testées dans l'ordre et la première vraie nommée avec ses chiffres mesurés : retrait de rive ≥ demi-largeur utile ; obstacles/zones couvrent tout le posable ; seuil d'accès solaire (CAP-D2-03) a tout écarté ; module plus grand que la surface. La raison est rangée au document et imprimée sur le plan de pose.
- **Simplicité** : automatique, une phrase sous le pan ; essentiel.
- **Tâches** :
  1. Nommer la cause d'un pan vide après « Remplir » ; fini quand un pan de 3 × 1,5 m avec un retrait de 0,8 m affiche « Aucun module : le retrait de rive (0,80 m) laisse moins qu'une largeur de module ». Fichiers : `RP/optimizer.ts` (fonction pure) ou nouveau `RP/motifPanVide.ts` (Nouveau fichier car : `layoutEditor.ts` ≥ 2 000 lignes ne grossit pas).
  2. Imprimer sur le plan de pose, pour chaque pan sans module, la raison rangée au document ; fini quand `plan-pose.pdf` d'un projet à un pan vide porte la phrase sous ce pan. Fichiers : `SV/planche.py`.
- **Dépendances** : partage la liste « ce qui manque » d'ACAL397 / le contrôle P20 (« pans vides expliqués ») — à fusionner, pas à doubler.
- **Score** : P 4 × A 3 ÷ M 2 = 6. Rang 5.

### CAP-D2-06 — Retraits par type d'arête (faîtage, égout, rive, noue, arêtier) fixés une fois par la société et posés d'office
- **Besoin** : « Remplissage d'un pan en un clic avec retraits saisis par type d'arête (égout, arêtier, noue, faîte, rive) pour les chemins pompiers » (B3 l. 154) ; « le retrait de bord de la fixation Huber (50 cm) » (B5-de passe 2 l. 1296/1399).
- **Preuves** : B3 N26, l. 154 (SolarEdge), l. 295 (Scanifly Auto-Add) ; B6 R58 (PVcase RM 1.50/1.55, sélection multi-arêtes) ; B5-de K47 (43 fils, « respecter marges de rive ») et passe 2 l. 592/1296/1399 ; B5-nl cluster 4 (6 fils). 4 lanes. URL : https://help.scanifly.com/setbacks-settings ; https://marketing.solaredge.com/solaredge-designer-0 .
- **Chez nous** : **PARTIEL.** Le type de chaque arête est déduit et corrigeable (`RP/edges.ts::EDGE_TYPES` = faitage, noue, arretier, egout, rive, inconnue — CALX94) ; le retrait d'UNE arête se saisit à la main (`LIB/roofSetbackEdge.ts`, CALX95, `zones[].edges[].retraitM`) ; la société n'a qu'un retrait de périmètre (`SV/degagements.py::CLE_RETRAIT` `retrait_rive_m`) et des catégories (`LIB/roofPro2.ts::resolveSetbacks`) ; un jeu de réglages société se pose sur un pan NEUF (`RP/jeuReglages.ts`, ACAL308) mais ses clés (`CLES_JEU`) ne portent aucun retrait par type. Manque : la table « type d'arête → retrait » de la société et sa pose automatique.
- **Plus petite version crédible** : Réglages → Site : cinq champs (faîtage, égout, rive, noue, arêtier) en mètres, chacun avec sa source, vides par défaut ; à la fermeture d'un pan, chaque arête typée sans `retraitM` reçoit la valeur de son type, marquée « réglage société », modifiable ; une arête « inconnue » n'en reçoit aucune et le dit.
- **Simplicité** : invisible pour la commerciale ; essentiel.
- **Tâches** :
  1. Ajouter à la section `degagements` la table des retraits par type d'arête, sourcée, vide par défaut, et son écran ; fini quand l'écran enregistre « égout 0,40 m — notice X » et refuse une valeur sans source. Fichiers : `SV/degagements.py::normaliser_section_degagements`, `FE/reglages/ReglagesSite.jsx`.
  2. Poser d'office ces retraits sur les arêtes typées d'un pan neuf (et « appliquer à toutes les arêtes de ce type » sur un pan existant) ; fini quand un pan à 4 arêtes (2 rives, 1 faîtage, 1 égout) reçoit 3 retraits distincts lus au réglage, sans toucher une arête déjà saisie. Fichiers : `RP/edges.ts`, `LIB/roofSetbackEdge.ts`, `RP/jeuReglages.ts`.
- **Score** : P 4 × A 3 ÷ S/M 2 = 6. Rang 6.

### CAP-D2-07 — Le plan de pose dans la fiche chantier, lisible sans réseau
- **Besoin** : « Plan de pose lisible hors ligne sur le téléphone du chef d'équipe » (B3 N10) ; « plan absent du chantier → strings mal câblés » (B5-de K51, 13 fils).
- **Preuves** : B3 N10 (Reonic, Scanifly) ; B6 R12 (Scanifly Mobile, OpenSolar 3.12, Pylon) ; B4 n° 17 ; B5-de K51 (passe 2 : 13 fils, 21 voix). 4 lanes. URL : https://docs.reonic.com/docs/en/installation-checklist-baustellendokumentation ; https://www.energiesparhaus.at/forum-pv-anlageninstallation-typische-maengel/78984 .
- **Chez nous** : **PARTIEL.** Le chantier ne porte qu'un LIEN (`apps/installations/calepinage_retenu.py::bloc_calepinage_retenu` → `planche_url`, `plan_pose_url = '/ventes/devis/<id>/3d'` ; carte `frontend/src/features/installations/CalepinageRetenuCard.jsx`) ; la synchronisation hors ligne (`apps/installations/field_sync.py`) ne transporte aucun plan (grep `planche|plan_pose` : rien). Le plan de pose est un SVG composé serveur (`SV/planche.py::_rendre_plan_pose_svg`).
- **Plus petite version crédible** : le calepinage sert le SVG du plan de pose de la variante retenue par un sélecteur ; la fiche chantier le met en cache avec sa synchronisation hors ligne et l'affiche en lecture seule.
- **Tâches** :
  1. Servir le SVG du plan de pose de la variante retenue par `selectors.py` (lecture pure, sans montant, avec son empreinte) ; fini quand `plan_pose_svg_pour_devis(devis_id)` rend le SVG ou `None` + motif. Fichiers : `backend/django_core/apps/calepinage/selectors.py`. Propriétaire : calepinage.
  2. **[routée → `docs/plans/PLAN_AUDIT_CHANTIERS.md`, propriétaire `chantiers`]** Embarquer ce SVG dans la fiche chantier synchronisée hors ligne ; fini quand la fiche, ouverte sans réseau, affiche le plan. Fichiers : `apps/installations/field_sync.py`, `CalepinageRetenuCard.jsx`. @after tâche 1.
- **Score** : P 2 (notes de version et 1 forum) × A 3 ÷ S 1 (moitié calepinage) = 6. Rang 7.

### CAP-D2-08 — Dessiner le plan de lestage sur le plan de pose, avec les zones de rive et de coin saisies par la société
- **Besoin** : « Ballast nécessaire surtout au bord de toit, cheminée 40 × 40 cm oubliée » (B5-de passe 2 l. 486) ; « 80-100 kg au bord et 40-60 kg au centre » (l. 1381, règle de forum, non retenue comme chiffre) ; « le planificateur recommande deux plaques de plus dans les coins » (l. 635).
- **Preuves** : B5-de K22 (52 fils cumulés, +9 rangs en passe 2) ; B5-fr n° 9 (9 sources) ; B5-nl cluster 9 (3 fils) ; B3 N8, l. 165/168/174 (K2 Base, Esdec Enstall, iFIX, Schletter) ; B5-en groupe J (VF7563 « ballast absent »). 5 lanes. URL : https://k2-systems.com/en/faq-category/k2-base/ ; https://www.energiesparhaus.at/forum-pv-planung-erste-schritte/86023 .
- **Chez nous** : **PARTIEL.** La feuille de lestage est calculée, TOUT saisi par la société avec référence (`SV/lestage.py::_feuille_de_lestage`, `masse_et_lestage`), affichée (`FE/atelier/PanneauMasseLestage.jsx`). Ses « zones » sont GÉOGRAPHIQUES (`_zones_saisies` : `code`, `libelle`, `commune_ou_region`), pas des zones de rive/coin ; aucun lest n'est dessiné sur la planche (grep `lest` dans `SV/planche.py` : 0). La comparaison à la charge admissible déclarée existe côté devis (`apps/ventes/roof_load.py`, CIQ114).
- **Plus petite version crédible** : la société saisit « largeur de la bande de rive (m) », « largeur de coin (m) » et « lest additionnel en rive / en coin (kg/module) », chacun sourcé ; le serveur range chaque module en centre / rive / coin selon sa distance au contour ; une feuille « Plan de lestage » colore les trois zones et inscrit le lest par module ; mention « valeurs saisies par <société>, référence <texte> — non calculées ». Aucun coefficient de vent dans le code (décision CALX361 conservée). Sans saisie : la feuille n'est pas produite et le dit.
- **Simplicité** : n'apparaît que pour un système « toit plat — lesté » ; Documents ; expert.
- **Tâches** :
  1. Ajouter à la section de lestage les paramètres de bande de rive et de coin (largeur, lest additionnel), sourcés ; fini quand une valeur sans source est refusée en nommant le champ. Fichiers : `SV/lestage.py::normaliser_section_lestage`.
  2. Ranger chaque module posé en centre / rive / coin et publier le lest par module ; fini quand un toit de 4 × 6 modules avec une bande de 1,2 m publie 4 coins, 12 rives et 8 centres avec leurs lests. Fichiers : `SV/lestage.py`, `SV/rangees.py` (lecture).
  3. Dessiner la feuille « Plan de lestage » (zones colorées, lest par module, mention de source) ; fini quand `plan-lestage.pdf` sort pour ce toit et qu'il est refusé avec motif sans paramètre saisi. Fichiers : `SV/planche.py` (+ entrée dans `views/sorties.py`).
- **Score** : P 4 × A 3 ÷ M/L 2,5 = 4,8. Rang 8.

### CAP-D2-09 — Coupures automatiques tous les N modules et allées tous les N rangs (maintenance, joints de dilatation)
- **Besoin** : « Allée de maintenance tous les 16 modules à 0,5 m » (VF8653) ; « joints de dilatation 6 × 2 sans créer 5 champs » (VF1417) ; « couloirs de nettoyage de 20 cm » (B5-de passe 2 l. 974).
- **Preuves** : B3 N2, l. 121 (SMA Sunny Design « Additional separations », PVcase « Corridor settings ») ; l. 174 (iFIX partitions thermiques et de maintenance) ; B5-en n° 16 et groupe J (3 fils + 36 fils MOUNT) ; B5-de passe 2 l. 974, 1047 ; B5-fr cluster 18 (6 sources). 4 lanes. URL : https://forum.valentin-software.com/topic/8653-assign-horizontal-distance-between-strings-in-a-row/ ; https://help.pvcase.com/hc/en-us/articles/43345035151635 .
- **Chez nous** : **PARTIEL.** Existent : îlots bornés L × W séparés par une allée, en MÈTRES, côté serveur (`CC/ilots.py::zones_allees`, `regle_ilots`, appelés par `SV/traduction.py`, saisis dans `FE/PanneauAllees.jsx` — CIQ137/138, préréglage FM DS 1-15 sourcé) ; allée uniforme entre rangées et « allée gratuite » (`CC/allee_gratuite.py`) ; couloir tracé à la main (`RP/zones.ts::couloirDepuisAxe`, CALX403) ; écart latéral constant (`LIB/estimatorBrainV2.ts` `colGapM`). Manque : la règle « tous les N modules / tous les N rangs » dans le pavage de l'atelier. Non planifié.
- **Plus petite version crédible** : deux paires de champs par pan, vides par défaut : « coupure de X m tous les N modules » et « allée de Y m tous les N rangs ». L'atelier les traduit en zones INTERDITES générées (comme `ilots.zones_allees` côté serveur), donc le paveur les évite sans être modifié ; le serveur lit les mêmes clés pour la parité.
- **Simplicité** : expert, proposé seulement en toit plat C&I et au sol.
- **Tâches** :
  1. Générer, depuis « tous les N modules / N rangs », des bandes INTERDITES dans le repère du pan, que le pavage évite ; fini quand un pan de 20 colonnes avec « 0,5 m tous les 8 » rend deux coupures et 16 + 4 modules par rangée. Fichiers : `RP/zones.ts` (fonction pure), `RP/poseSurfaces.ts` pour le sol. Évite `LIB/estimatorBrainV2.ts` (propriétaire `web`) ; si le pas de la coupure exigeait de modifier `packConfig`, la moitié paveur va dans `PLAN_AUDIT_TRANSVERSE.md`.
  2. Faire lire les mêmes clés par le traducteur serveur ; fini quand le moteur serveur et l'atelier comptent le même nombre sur le golden toit plat C&I d'ACAL382. Fichiers : `CC/ilots.py`, `SV/traduction.py`. @after ACAL382.
- **Score** : P 3 × A 3 ÷ M 2 = 4,5. Rang 9.

### CAP-D2-10 — Structure surélevée sur dalle béton, poteaux d'ombrière et pieux de champ comptés dans la nomenclature
- **Besoin** : « Dalle béton plate : pieds et longrines qui se posent seuls » (B2 n° 6) ; « surélévation pour sortir d'une ombre de mur » (B5-fr n° 16) ; « on ne peut pas surélever correctement les modules du carport » (B5-de passe 2 l. 1309) ; « nombre de pieux = tables × pieux par table » (B3 N34).
- **Preuves** : B2 n° 6 / O18 (OpenSolar Elevated structures, RCC) ; B6 R14 (OpenSolar 3.8, PVcase RM 1.52, Scanifly) ; B5-fr n° 16 / cluster 30 (3 sources) ; B3 N34, l. 269/278 (PVcase GM pieux) ; B5-de l. 1309. 5 lanes. URL : https://www.opensolar.com/elevated-structures/ ; https://help.pvcase.com/hc/en-us/articles/35595008003347-Bill-of-Materials .
- **Chez nous** : **PARTIEL.** Le châssis de toit plat est DESSINÉ en 3D (jambe avant, platines « aux deux pieds » : `RP/scene3d.ts` vers « Toit plat : panneau surélevé sur châssis ») ; les poteaux d'ombrière sont dessinés seulement si l'entraxe ET la section sont saisis (`RP/poseSurfaces.ts`, CALX87/124 : « Absent ⇒ AUCUN poteau n'est décrit ») ; mais la nomenclature n'a aucune base « tables », « pieds » ni « poteaux » (`SV/catalogue_fixation.py::BASES` = modules, rangées, pans, jonctions, extrémités, longueur des rangées) ; aucune portée entre pieds saisie ; aucun pieu de champ.
- **Plus petite version crédible** : (a) le système de fixation déclare une portée maximale entre pieds (saisie, sourcée) → nombre de pieds par rangée = ⌈longueur / portée⌉ + 1, ligne de nomenclature ; (b) nouvelles bases « tables » (sol, ombrière) et « poteaux » (entraxe saisi de l'ombrière) pour que « pieux par table » et « poteaux » sortent ; (c) les pieds dessinés au pas saisi. Aucune charge de vent calculée.
- **Simplicité** : se déduit du système choisi ; rien à faire pour la commerciale.
- **Tâches** :
  1. Ajouter les bases `tables` et `poteaux` (et `pieds` = rangées × ⌈longueur / portée saisie⌉ + 1) à la nomenclature ; fini quand un champ au sol de 12 tables avec « 4 pieux par table » sort 48 pieux, et qu'une portée non saisie rend `quantite: None` nommée. Fichiers : `SV/catalogue_fixation.py::BASES`, `SV/fixation.py::_grandeurs_du_document`.
  2. Dessiner les pieds du châssis de toit plat au pas saisi au lieu de deux pieds par module ; fini quand une portée de 1,8 m saisie change le nombre de pieds dessinés. Fichiers : `RP/scene3d.ts`.
  3. Imprimer pieds/poteaux/pieux sur le plan de pose (repère + compte) ; fini quand `plan-pose.pdf` d'une ombrière porte ses poteaux cotés. Fichiers : `SV/planche.py::_corps_feuille_surface`. @after CAP-D2-02 (catalogue saisissable).
- **Score** : P 3 × A 3 ÷ M 2 = 4,5. Rang 10.

### CAP-D2-11 — Une fiche de pose A4 par pan pour l'équipe (chaînes en couleur, sens, + / −, 4 distances aux rives, zones interdites, rails et pinces du pan, repères de sécurité)
- **Besoin** : « Les 4 distances du champ aux rives, les cotes des zones interdites, les repères + / − et le sens départ/retour des strings, sur le plan que le monteur a en main » (B5-de P5) ; « plan de strings lisible pour un électricien : numéros, grande police » (B5-en groupe B) ; points d'ancrage antichute avec rayon (B6 R44).
- **Preuves** : B5-de P5, K17 (13 fils), K51 (13 fils), §11 n° 1 et 14 ; B3 N9 (Pylon job sheets, K2 plan de montage, Reonic) ; B5-en n° 35 et groupe B (VF9199, VF7225) ; B5-es n° 7 (tension DC par chaîne sur le plan — moitié D3) ; B6 R43 (couleur par MPPT), R44 (ancres, OpenSolar 3.10/3.12, Pylon), K80 (6 outils) ; B2 n° 4 (repères). 6 lanes. URL : https://forum.valentin-software.com/topic/10011-bema%C3%9Fung-der-modulfl%C3%A4chen/ ; https://getpylon.com/ie/solar-design/ .
- **Chez nous** : **PARTIEL.** Plan de pose A3 du site entier (`SV/planche.py::_rendre_plan_pose_svg`) : chaînes en LIGNES DE TEXTE dans le bandeau (`_lignes_de_chaines`), numéros de modules (ACAL269 coché), une feuille par surface au sol (`svg_de_planche`, ACAL260) ; cotes d'ENCOMBREMENT seulement (`_corps_feuille_toit` → `_cote_horizontale`/`_cote_verticale` de l'étendue) ; teinte par chaîne seulement sur le plan de câblage (`SV/documents/plan_cablage.py`, `PALETTE_CHAINES`) ; aucune feuille par pan, aucune distance aux rives, aucun + / −, aucune couche de repères de sécurité (grep `annotation|ancrage` : seulement les marqueurs d'organes électriques `RP/electrique3d.ts::creerMarqueur`, D3).
- **Plus petite version crédible** : une page A4 par pan, ajoutée au pack technique : modules teintés par chaîne avec leur numéro, + et − aux deux extrémités de chaque chaîne et flèche du sens (ordre de l'affectation publiée), les quatre distances du champ aux rives du pan, les cotes des zones interdites, un encart « rails / pinces / crochets de ce pan » (nomenclature par pan), et les repères saisis (ancre antichute, accès, passage de câble) avec leur rayon SAISI. La tension par chaîne est imprimée seulement si D3 la publie déjà.
- **Simplicité** : Documents ; se télécharge avec « Plan de pose » ; rien à régler.
- **Tâches** :
  1. Composer la feuille A4 d'un pan : modules teintés par chaîne, numéros, + / − et sens ; fini quand un pan de 2 chaînes sort une page avec deux couleurs et quatre signes. Fichiers : `SV/planche.py` (+ lecture de `SV/documents/plan_cablage.py`). @after ACAL269 (fait).
  2. Coter les quatre distances du champ aux rives du pan et les zones interdites ; fini quand la page porte 4 cotes mesurées et une cote par zone. Fichiers : `SV/planche.py`.
  3. Publier la nomenclature de fixation PAR PAN et l'imprimer en encart ; fini quand la somme des encarts égale `bom-fixation/`. Fichiers : `SV/fixation.py`.
  4. Ajouter une couche « Repères de chantier » (type, texte, rayon saisi) dans l'atelier et l'imprimer avec légende ; fini quand une ancre posée à 2 m de rayon apparaît sur la fiche du pan. Fichiers : `RP/mesureUi.ts` (couche voisine de la mesure), contrat `roof_layout_v2.schema.json`, `SV/planche.py`.
- **Score** : P 4 × A 3 ÷ L 3 = 4. Rang 11.

### CAP-D2-12 — Copier-coller des panneaux d'un pan vers un autre, et « appliquer les réglages de ce pan à… »
- **Besoin** : « Coller des panneaux ou des obstacles » (B7 U8, 8 sources) ; « copier une formation avec copie multiple » (B5-de passe 2 l. 1565) ; « réutiliser les réglages d'un pan sur un autre » (B3 N14).
- **Preuves** : B6 R2 (5 outils : PVcase RM 1.52 « Pick generation settings », PVcase GM, SolarEdge, PVsyst, Scanifly) et K13 (table stake, 4 outils) ; B7 U8 ; B4 n° 5 ; B2 n° 12 / X16 ; B3 N14, l. 84 ; B5-en groupe I (VF4084, VF7756) ; B5-de l. 1565. 7 lanes. URL : https://www.pv-tech.org/solaredge-bolsters-design-tool-to-streamline-ci-rooftop-planning-process ; https://apps.apple.com/us/app/solaredge-mapper/id432768469 .
- **Chez nous** : **PARTIEL.** Dupliquer la sélection DANS le pan au décalage saisi (`RP/layoutEditor.ts::dupliquerSelection`, CALX112) ; dupliquer un pan entier dans une zone NEUVE (`RP/zones.ts::dupliquerPan`, CALX98) ; jeu de réglages société posé sur un pan NEUF seulement (`RP/jeuReglages.ts`, « un pan EXISTANT n'est jamais touché »). Manquent : coller dans un AUTRE pan existant, et appliquer les réglages d'un pan à des pans existants.
- **Plus petite version crédible** : Ctrl+C / Ctrl+V : la sélection est collée au curseur dans le pan visé, contrôlée par les mêmes contraintes dures (refus nommé : « 3 modules hors du pan, rien n'a été collé ») ; clic droit sur un pan → « Appliquer ces réglages à… » (module, inclinaison, azimut, retraits, écarts) sur les pans cochés, un pan déjà réglé à la main est listé avant d'être écrasé.
- **Simplicité** : gestes habituels ; essentiel pour coller, expert pour appliquer.
- **Tâches** :
  1. Coller la sélection libre dans un autre pan, au curseur, tout ou rien avec refus nommé ; fini quand une rangée copiée du pan A se colle dans le pan B et qu'un collage hors pan ne change rien. Fichiers : `LIB/freeLayout.ts` (placement validé), `RP/clavier.ts` (Ctrl+V dans la table unique d'ACAL414) — `layoutEditor.ts` ne grossit pas (`Code net ≤ 0`).
  2. « Appliquer les réglages de ce pan à… » sur des pans existants ; fini quand appliquer le pan A (module 550 Wc, retraits) aux pans B et C les repave et que l'annulation (ACAL412) rend l'état d'avant. Fichiers : `RP/zones.ts`, `RP/jeuReglages.ts`. @after ACAL412.
- **Score** : P 4 × A 2 ÷ M 2 = 4. Rang 12.

### CAP-D2-13 — Montrer le panneau en conflit en rouge (ou ambre) pendant qu'on le glisse
- **Besoin** : « Montrer en rouge/orange le panneau en conflit (retrait, obstacle) pendant le glissé, au lieu de refuser après coup » (B6 R10).
- **Preuves** : B6 R10 (Scanifly 2025-11-19, PVcase RM 1.48, OpenSolar 2.31) ; B5-en groupe A (« collision fantôme » VF3685, VF3981). 2 lanes. URL : (notes de version citées par B6, `bench/B6-notes-de-version.md` ligne R10).
- **Chez nous** : **PARTIEL.** L'aperçu vivant existe et NOMME ce qui bloque, mais garde le dernier aperçu VALIDE à l'écran (`RP/layoutEditor.ts::previewFreeDrag` : « le dernier aperçu VALIDE reste affiché » + `layoutNoteEl` « Ici : … ») ; aucune silhouette rouge/ambre à la position visée.
- **Plus petite version crédible** : à la position visée, une silhouette translucide rouge (contrainte dure) ou ambre (marge réduite acceptée) en plus du texte ; rien ne change au relâchement.
- **Simplicité** : automatique.
- **Tâches** :
  1. Peindre la silhouette du panneau visé en rouge/ambre pendant le glissé libre et lattice ; fini quand glisser un panneau sur un obstacle montre une silhouette rouge et la note, et qu'au relâchement rien ne bouge. Fichiers : `RP/scene3d.ts` (fonction de silhouette) ; appel depuis `layoutEditor.ts` à code net ≤ 0 (remplacer l'appel `showMeasure` existant par un appel groupé).
- **Score** : P 2 × A 2 ÷ S 1 = 4. Rang 13.

### CAP-D2-14 — Le type de couverture choisit la fixation ; contrôles tuile et tôle (zone de serrage, entraxe des crochets, porte-à-faux, rails en paysage)
- **Besoin** : « Zone de serrage fabricant 306 mm ± 30 mm incompatible avec la trame de tuiles » (B5-de passe 2 l. 492) ; « les crochets ne tombent pas tous dans la plage de serrage AIKO de 34,5 à 41,5 cm » (l. 1120) ; « rail dépassant de 70 cm au-delà du dernier crochet » (l. 1431) ; « la pose en paysage exige un montage croisé avec ~2 fois plus de rail » (l. 919, 1052) ; « pour un bac acier fin 0,6 mm pas de vis traversante » (l. 1353) ; « poser en portrait sur tuiles ou zinc sans dépasser la portée des rails » (B5-fr n° 8).
- **Preuves** : B5-fr n° 8 / cluster 24 (6 sources) ; B5-de passe 2 K22 l. 492/928/1067/1104/1120/1353/1431/919/1052 ; B6 R11 (OpenSolar 3.8/3.11/3.13, PV*SOL-Renusol) ; B3 l. 167/172 (K2, Esdec choisit seul le système). 4 lanes. URL : https://forum-photovoltaique.fr/viewtopic.php?t=82435 ; https://www.photovoltaikforum.com/ (fils l. 492/1120 de B5-de).
- **Chez nous** : **PARTIEL.** Le type de toiture est sur le lead (`backend/django_core/apps/crm/models.py::TypeToiture` — terrasse béton, tôle, tuiles, bac acier, fibrociment) et lu par le traducteur (`SV/traduction.py`, `type_toiture`) ; le système porte un `mode_pose` (`models.py::SystemeFixation.ModePose`) ; mais aucun lien couverture → système (`SV/fixation.py::_resoudre_avec_source` : demandé, persisté ou l'unique actif) ; la fiche module n'a aucune zone de serrage (grep `serrage|clamp` dans `apps/stock/models_fiche_technique.py` : 0) ; les règles de quantité ne distinguent pas portrait/paysage (`BASES`) ; aucun contrôle de porte-à-faux.
- **Plus petite version crédible** : (a) chaque système déclare les couvertures qu'il sert (vocabulaire du lead) → le système proposé est l'unique actif compatible avec la couverture du lead ; (b) fiche module : zone de serrage min/max (mm) sourcée ; (c) le système déclare l'entraxe de ses crochets et le porte-à-faux maximal du rail (saisis, sourcés) → alertes nommées « crochets hors de la zone de serrage du module » et « porte-à-faux 0,70 m > 0,40 m admis » ; (d) bases « modules en portrait / en paysage » pour qu'une règle de rails croisés existe. Aucune valeur par défaut.
- **Simplicité** : alerte dans l'onglet Fixation ; la commerciale ne voit qu'un système déjà choisi.
- **Tâches** :
  1. Déclarer sur `SystemeFixation` les couvertures servies et proposer le système compatible avec `type_toiture` du lead (lu par `apps.crm.selectors`) ; fini quand un lead « tuiles » reçoit le système « tuiles » et qu'en cas de doute la liste le dit. Fichiers : `models.py` (migration additive), `SV/fixation.py`. @after CAP-D2-02.
  2. Ajouter à la fiche module la zone de serrage (min/max mm, source) ; fini quand la fiche l'accepte et la refuse sans source. Fichiers : `apps/stock/models_fiche_technique.py` (propriétaire calepinage, vérifié).
  3. Contrôler crochets/zone de serrage et porte-à-faux de rail en bout de rangée ; fini quand un entraxe de 0,30 m hors d'une zone 0,345-0,415 m sort une alerte nommée. Fichiers : `SV/fixation.py`.
  4. Ajouter les bases « modules en portrait » / « en paysage » ; fini quand une règle « 4 rails par rangée en paysage » ne s'applique qu'aux rangées paysage. Fichiers : `SV/catalogue_fixation.py::BASES`, `SV/fixation.py`.
- **Score** : P 4 × A 3 ÷ L 3 = 4. Rang 14.

### CAP-D2-15 — Essayer portrait ET paysage face à la ligne d'ombre, et montrer les deux
- **Besoin** : « Proposer en un geste la disposition portrait ou paysage qui limite la perte d'ombrage » (B5-es n° 5) ; « paysage ou portrait face à l'ombre » (B5-fr n° 9).
- **Preuves** : B5-es n° 5 (4 → 5 fils) ; B5-fr n° 9 / cluster 19 (6 sources) ; B4 n° 11 ; B6 R47 (moitié D4). 4 lanes. URL : https://www.energeticambiente.it/forum/fonti-di-energia-rinnovabile/fotovoltaico/tecnica-componentistica-e-installazione/81005-disposizione-pannelli-e-stringhe-in-orizzontale-verticale ; https://forum-photovoltaique.fr/viewtopic.php?t=14538 .
- **Chez nous** : **PARTIEL.** Les deux pavages sont calculés à chaque fois (`LIB/estimatorBrainV2.ts::PackResult` `portrait`, `landscape`, `best`, `mixed`) et choisis par DENSITÉ, jamais par l'ombre (`best` = « la meilleure des deux orientations » en nombre ; le mixte compare `row.length / pitchM`) ; le choix manuel portrait/paysage/auto est à l'écran (`TD` `data-orient`). La matrice du toit plat mesure `accesSolaireMoyen` par orientation (CAP-D2-01) ; rien pour un toit en pente.
- **Plus petite version crédible** : quand le pan a une obstruction retenue, afficher sous le choix d'orientation les deux poses avec leur nombre et leur accès solaire moyen MESURÉ (carte d'accès solaire existante) ; un clic choisit. La perte d'énergie par sous-chaîne (diodes) reste **D4/D3**.
- **Simplicité** : une ligne qui n'apparaît que si le pan est ombré ; essentiel.
- **Tâches** :
  1. Afficher, pour un pan ombré, portrait et paysage côte à côte (nombre, accès solaire moyen mesuré) ; fini quand un pan avec une cheminée affiche deux lignes chiffrées et qu'un pan sans ombre n'affiche rien. Fichiers : `RP/optimizer.ts`, `RP/shadingUi.ts`.
- **Score** : P 3 × A 2 ÷ S/M 1,5 = 4. Rang 15.

### CAP-D2-16 — Châssis de toit plat et tables au sol « N rangs × M modules », avec châssis partiels près des obstacles
- **Besoin** : « Châssis (cadres) : N rangs × M modules posés en blocs, cadres partiels près des obstacles » (B3 l. 28) ; « placer deux rangées sur châssis en V puis copier la formation » (B5-de passe 2 l. 1565).
- **Preuves** : B3 N1, l. 28/120/269 (HelioScope Frames, PVcase RM 1.50-1.52, PVcase GM tables) ; B5-de l. 1565, 1564 ; B1 V065 (types de champs). 3 lanes. URL : https://help-center.helioscope.com/hc/en-us/articles/7835959528339-Frames-Frame-Spacing ; https://help.pvcase.com/hc/en-us/articles/43343107921555-Layout-settings .
- **Chez nous** : **ABSENT.** Une « table » vaut 1 module (sud) ou 2 (dos-à-dos E-O) : `CC/types.py::Kit.modules_par_table` (« Nombre de modules gagnés par pas de pose (2 pour une table dos-à-dos) »), `RP/entreeMoteur.ts` (`modulesParTable: famille === 'eastwest' ? 2 : 1`), `RP/poseSurfaces.ts` ; aucun « rangs par table » (grep `rowsPerFrame|rangs_par|par_chassis` : 0).
- **Plus petite version crédible** : un champ « rangs par châssis » (1 à 3) et « modules par châssis » par pan plat ou champ ; le pavage pose des blocs complets, puis, si « châssis partiels autorisés », complète près des obstacles ; le nombre de châssis sort au plan et à la nomenclature (base `tables`, CAP-D2-10). La pente de dalle sous châssis (« inclinaison indépendante », B3 N3) est écartée (voir « écarté »).
- **Simplicité** : défaut = 1 × 1 (comportement d'aujourd'hui) ; expert.
- **Tâches** :
  1. Poser au contrat moteur (`contract_samples/pose.json`) et au `Kit` les rangs par table ; fini quand un kit 2 × 10 est accepté et un 0 refusé en nommant le champ. Fichiers : `CC/types.py::Kit`, `CC/serialisation.py`.
  2. Faire poser par le serveur des tables N × M et, sur option, partielles ; fini quand un toit de 30 × 12 m posé en 2 × 10 compte des blocs entiers, `poseur` et `moteur` toujours d'accord (`2 × len(tables) == compte` généralisé). Fichiers : `CC/poseur.py`, `CC/moteur.py`.
  3. **[moitié paveur atelier → `docs/plans/PLAN_AUDIT_TRANSVERSE.md`, propriétaires `web` + `calepinage`]** Paver en blocs N × M dans l'atelier ; fini quand l'atelier et le serveur comptent pareil sur le golden C&I d'ACAL382. Fichiers : `LIB/estimatorBrainV2.ts::packConfig` (web), `RP/optimizer.ts`. @after tâches 1-2, ACAL382.
- **Score** : P 3 × A 3 ÷ L 3 = 3. Rang 16.

### CAP-D2-17 — Aligner les rangées à gauche, au centre, à droite ou justifiées, et caler les rangées de deux pans voisins
- **Besoin** : « Alignement des rangées : centré, gauche, droite, justifié ; recalage Aligner au clic » (B3 l. 29) ; « centrer sur le toit » (VF2845, B5-en groupe K).
- **Preuves** : B3 N4, l. 29/120 (HelioScope, PVcase) ; B6 R37 (PVcase RM 1.51/1.53 « Align rows between PV areas », SolarEdge edge alignment) ; B5-en groupe K ; B5-de K46. 4 lanes (faibles en forum). URL : https://help-center.helioscope.com/hc/en-us/articles/7835962600083-Module-alignment-options .
- **Chez nous** : **ABSENT.** Chaque rangée part du bord gauche du pan (`LIB/estimatorBrainV2.ts` : `uStart = uMin + setbacks.lateralM - …`) ; « aligner la sélection » existe pour le placement libre (`RP/layoutEditor.ts::freeAlignSelection`, CAL81) et ACAL411 (barre Pivoter/Aligner/Répartir) est PLANIFIÉ — ni l'un ni l'autre ne règle l'alignement des rangées d'un pan.
- **Plus petite version crédible** : quatre puces par pan ; après pavage, chaque rangée est translatée dans son tronçon libre (gauche, centre, droite, ou modules répartis), chaque position revalidée par le contrôle dur existant ; refus nommé si une rangée ne peut pas bouger.
- **Simplicité** : défaut « gauche » (aujourd'hui) ; sous « Personnaliser la disposition ».
- **Tâches** :
  1. Translater les rangées d'un pan selon l'alignement choisi, positions revalidées ; fini quand « centré » sur un pan de 10,3 m avec 9 modules de 1,13 m laisse le même jeu aux deux bouts, à 1 cm près. Fichiers : `LIB/freeLayout.ts` (contrôle), `RP/optimizer.ts` (post-traitement, sans toucher `packConfig` — sinon `PLAN_AUDIT_TRANSVERSE.md`).
- **Score** : P 2 × A 2 ÷ M 2 = 2. Rang 17.

### CAP-D2-18 — Comparer d'autres modules du stock sur la même implantation, en un clic
- **Besoin** : « Comparer deux ou trois modules sur la même implantation : les utilisateurs bricolent des tableaux (460 W → 430 W) » (B5-de P11).
- **Preuves** : B5-de P11 (5 fils), K28, K33 ; B6 R26 (PVcase GM 2.62, Pylon, OpenSolar). 2 lanes. URL : https://www.photovoltaikforum.com/thread/228998-pv-sol-genauigkeit-der-modulmodelle/ .
- **Chez nous** : **PARTIEL.** Variantes créables et comparées (`SV/variantes.py::creer_variante`, `SV/comparaison.py`, `FE/VariantesCompare.jsx`) ; module par pan (`RP/moduleSelect.ts`, ACAL264) ; aucun geste qui fabrique « une variante par module candidat ».
- **Plus petite version crédible** : « Comparer d'autres modules » : la commerciale coche 2-3 modules du stock ; pour chacun une variante est créée en changeant le module des pans ; si les dimensions diffèrent, la variante est re-pavée dans l'atelier (le geste le dit) ; la comparaison existante classe par kWc, kWh/an, kWh/kWc (simulation = D4).
- **Simplicité** : un bouton dans l'étape Panneaux ; expert.
- **Tâches** :
  1. Créer une variante par module coché (mêmes dimensions : module remplacé ; sinon variante marquée « à re-poser ») ; fini quand cocher deux modules crée deux variantes nommées par module. Fichiers : `SV/variantes.py`, `views/calepinages.py`.
  2. Ouvrir la comparaison sur ces variantes avec la colonne « module » ; fini quand `VariantesCompare` montre les trois lignes. Fichiers : `FE/VariantesCompare.jsx`.
- **Score** : P 2 × A 2 ÷ M 2 = 2. Rang 18.

### CAP-D2-19 — DXF : chaque module en bloc nommé (comptable dans AutoCAD), avec numéro, pan et chaîne
- **Besoin** : « Export CAD DXF avec modules en blocs comptables, calques » (B3 l. 59) ; « DXF numérote tous les modules » (archelios, l. 190).
- **Preuves** : B3 N20, l. 59/190 (HelioScope, archelios) ; B6 R33 (PVcase GM 2.64, SolarEdge, HelioScope). 2 lanes. URL : https://help-center.helioscope.com/hc/en-us/articles/8536954019603-CAD-Export-Blocks-and-Layers .
- **Chez nous** : **PARTIEL.** `SV/export_dxf.py::_document_dxf` écrit un rectangle (polyligne) par module sur 4 calques nommés, + calque `CHAINES` sur demande (CALX310) + `PROVENANCE` ; aucun `BLOCK`/`INSERT` (grep : 0). `ezdxf` est déjà une dépendance (`SV/sld_export.py`).
- **Plus petite version crédible** : un bloc par type de module (dimensions de la fiche), un `INSERT` par module posé avec attributs n°, pan, chaîne ; calques inchangés.
- **Tâches** :
  1. Écrire les modules en `INSERT` d'un bloc par type avec attributs ; fini quand le DXF d'un projet de 24 modules contient un bloc et 24 insertions, et que le compte par calque reste celui d'aujourd'hui. Fichiers : `SV/export_dxf.py`.
- **Score** : P 2 × A 1 ÷ S 1 = 2. Rang 19.

### CAP-D2-20 — Une check-list de chantier tirée du projet (système de fixation, ordre des chaînes, connecteurs)
- **Besoin** : « Avant de monter : compatibilité des connecteurs module/câble, paramètres onduleur, ordre des strings, ce qui manque » (B5-de P13).
- **Preuves** : B5-de P13 (4 fils), K51 ; B3 l. 112/260 (Reonic checklists modulaires). 2 lanes. URL : https://www.energiesparhaus.at/forum-pv-anlageninstallation-typische-maengel/78984 .
- **Chez nous** : **ABSENT** pour la part projet. Le chantier a des modèles de check-list génériques (`apps/installations/models_chantier.py::ChecklistTemplate`, `ChantierChecklistItem`) ; rien ne vient du calepinage ; la fiche module n'a pas de champ connecteur (grep `connecteur|mc4` : 0).
- **Plus petite version crédible** : le calepinage sert une liste de points de contrôle déduits (système de fixation et son mode, chaînes dans l'ordre avec leurs modules, couvertures/zone de serrage si CAP-D2-14, pans existants) ; le chantier les ajoute à sa check-list.
- **Tâches** :
  1. Servir par `selectors.py` les points de contrôle de pose d'un calepinage retenu ; fini quand la liste d'un projet à 2 chaînes porte 2 lignes de chaîne et 1 ligne de système. Fichiers : `backend/django_core/apps/calepinage/selectors.py`.
  2. **[routée → `docs/plans/PLAN_AUDIT_CHANTIERS.md`]** Ajouter ces points à la check-list du chantier à sa création ; fini quand un chantier neuf les liste. Fichiers : `apps/installations/*`. @after tâche 1.
- **Score** : P 2 × A 2 ÷ M 2 = 2. Rang 20.

### CAP-D2-21 — La quantité d'échafaudage dans la nomenclature de pose
- **Besoin** : « Échafaudage : surface de façade (hauteur d'égout + 2 m) × périmètre » (B5-en n° 12) ; « limites de prestation : échafaudage » (B5-de §11 n° 15, 19/22 fils — part périmètre de prestation, côté devis).
- **Preuves** : B5-en n° 12 (VF1096 p2, VF1094 p3 — 2 auteurs) ; B5-de §11 n° 15. 2 lanes. URL : https://forum.valentin-software.com/topic/1096-pvsol-wunschliste/page/2/ .
- **Chez nous** : **ABSENT** (grep `echafaud|scaffold` dans le module : seulement le mot « échafaudage » au sens « gabarit DOM »). La hauteur du bâtiment est saisie avec source (`RP/batiment.ts`).
- **Plus petite version crédible** : une base « longueur d'égout » (et hauteur saisie) ; la société écrit sa règle (ex. facteur et marge en hauteur, SAISIS) ; la ligne sort sans prix ; le « + 2 m » du forum n'est PAS codé.
- **Tâches** :
  1. Ajouter la base `longueur_egouts_m` (+ hauteur d'égout saisie) et le rôle « échafaudage » ; fini quand une règle saisie sort une surface d'échafaudage et qu'une hauteur non saisie rend `quantite: None` nommée. Fichiers : `SV/catalogue_fixation.py`, `SV/fixation.py`. @after CAP-D2-02.
- **Score** : P 1 × A 2 ÷ S 1 = 2. Rang 21.

### CAP-D2-22 — Les numéros de série posés rattachés au module et à la chaîne du plan
- **Besoin** : « Numéros de série posés (scan ou CSV) rattachés aux chaînes, onduleurs et batteries, repris dans le manuel propriétaire et le dossier as-built » (B7 U17).
- **Preuves** : B7 U17 et cluster 31 (12 lignes, 5 sources : SolarEdge Mapper, Enphase Installer Toolkit). 1 lane (avis d'applis). URL : https://apps.apple.com/us/app/solaredge-mapper/id432768469 .
- **Chez nous** : **PARTIEL.** La saisie existe côté chantier (`apps/installations/models_field.py::ComponentSerial`, F9, avec photo de plaque et OCR optionnel), versée au parc SAV ; aucun lien au module/pan/chaîne du calepinage ; l'as-built du calepinage n'importe jamais `installations` (`SV/asbuilt.py`, en-tête « LE CHANTIER RESTE LE CHANTIER »).
- **Plus petite version crédible** : le calepinage sert la liste des modules posés (pan, n°, chaîne) ; le chantier rattache chaque n° de série à une ligne de cette liste.
- **Tâches** :
  1. Servir par `selectors.py` la liste des modules posés de la variante retenue (pan, n° stable, chaîne) ; fini quand elle rend 24 lignes pour 24 modules. Fichiers : `backend/django_core/apps/calepinage/selectors.py`.
  2. **[routée → `docs/plans/PLAN_AUDIT_CHANTIERS.md`]** Rattacher `ComponentSerial` à une ligne de cette liste ; fini quand un n° saisi sur le module 7 apparaît au module 7. @after tâche 1.
- **Score** : P 2 × A 1 ÷ S 1 = 2. Rang 22.

---

## Écarté (raison en une ligne)

| Proposition (ids) | Raison |
|---|---|
| Inclinaison saisonnière à deux positions (B5-fr n° 15 / cluster 32, B1 V022) | Preuve mince (3 fils FR anciens) ; B1 la juge sans usage (structures réglables rarissimes) ; rien dans le code ; à rouvrir si un client la demande. |
| Inclinaison indépendante sur dalle pentue (B3 N3) | Un seul outil (HelioScope Pro), aucune voix de forum ; touche le calcul d'ombrage entre rangées (D4). |
| Est-Ouest inversé, rotation > 15°, E ou O seuls en zone étroite (B3 N25, l. 120/122, l. 30 « 4 espacements ») | 1-2 outils, aucune voix ; 2 des 4 espacements E-O sont déjà saisissables (`RP/optimizer.ts::eastWestGeometryInput`). |
| Trois mesures d'espacement liées (distance, GCR, portée) (B3 l. 213) | Un outil ; le GCR est déjà une SORTIE (`CC/surfaces/sol.py`, règle « jamais une entrée »). |
| Note de charges de vent « à compléter » pour la mairie (B5-es n° 15) | Calcul normatif vent/neige exclu ; la feuille de lestage paramétrée (`SV/lestage.py`) et la pièce jointe du fabricant couvrent l'usage. |
| Statique Eurocode, vent/neige calculés (B5-de K22, B3 §4) | Décision fondateur (non-objectif, `docs/moteur-calepinage.md`) ; seules les valeurs saisies et sourcées restent (CAP-D2-08). |
| Clôture PV verticale, agri-PV vertical (B5-de l. 652, K37) | Statique exclue ; gain bifacial vertical = D4. |
| Ombrière dos ouvert / fermé (B3 N33, l. 219) | Change un coefficient thermique : D4. |
| Mode « salon » du vendeur (B3 N5, B6 R7) | D6 (parcours guidé, D-ACAL-32, ACAL393/394). |
| Pouce haut/bas sur le remplissage (B2 n° 17) | D6 (retour d'usage). |
| Verrou du dessin à l'acceptation du devis (B3 N16) | Hors domaine (versions/variante retenue, D-ACAL) ; décision fondateur requise. |
| Pivoter tout le site, verrouiller un bâtiment, copier/multi-sélectionner des obstacles (B4 n° 14, B5-en n° 7/13, B3 N13b, B6 R53/K74/K75) | D1 (modélisation du toit et des obstacles). |
| Toit en sheds (B5-fr n° 17) | D1 (forme de toit). |
| Comparer conception préliminaire et relevé (B3 N24, B2 n° 20) | D1 (relevé) ; l'as-built posé/prévu existe (`SV/asbuilt.py`). |
| Dupliquer un bloc câblé (B2 n° 16, X16) | Câblage = D3 ; la part pose est dans CAP-D2-12. |
| Optimiseur sur les seuls modules ombrés (B5-de P4) | D3. |
| Valeurs de mise en service par chaîne, consignes DC (B5-es n° 7 tension, n° 10 ; B5-de P22) | D3 (valeurs électriques) ; seuls les + / − et le sens de pose sont dans CAP-D2-11. |
| Hauteur de cadre et ombre d'étriers (B5-es n° 13) | D4 (ombrage). |
| Inclinaison minimale d'auto-nettoyage (B5-es n° 18, B5-de l. 1025) | 1-2 fils ; un seuil « société » d'avertissement relève de D6 (explications). |
| QR code sur la planche (B6 R50) | Adéquation 1, aucune voix de forum. |
| Export KML / GeoJSON (B6 R56) | Un seul outil (PVcase GM). |
| Export DWG (B5-nl n° 7) | Une page vendeur ; conversion par outil propriétaire. |
| Documents de pose en arabe (B5-fr n° 19) | 0 fil ; aucune décision de langue (B3 §4 : interface en français). |
| Taux d'occupation du toit (B6 R51) | Déjà présent (`FE/surfacePose.js::tauxOccupation`, GCR de `CC/surfaces/sol.py`). |

## Déjà présent ou déjà planifié (aucune fiche)

| Besoin | Où |
|---|---|
| Champ au sol sans bâtiment (B2 n° 9, A54) | PRÉSENT : `FE/ModeTerrain.jsx` (CAL89), `RP/poseSurfaces.ts` (CALX123), planche sans toit (`SV/planche.py::_geometrie_sans_toit`, ACAL260). |
| Allée pompier / couloir tracé (B5-nl cluster 4, A « fire pathways ») | PRÉSENT : `RP/zones.ts::couloirDepuisAxe` (CALX403), largeur saisie par pays (`largeurAlleeDepuisReglages`). |
| Îlots coupe-feu bornés (FM DS 1-15) | PRÉSENT : `CC/ilots.py`, `FE/PanneauAllees.jsx` (CIQ137/138). |
| Zone réservée pour une extension future (B5-es n° 16, part pose) | PRÉSENT : nature `RESERVEE` (`RP/zones.ts`, `CC/zones.py`) ; la part « entrée MPPT libre » = D3. |
| Mode de fixation lesté / fixé / bac acier (B5-fr n° 14) | PRÉSENT au modèle (`SystemeFixation.ModePose`) ; inutilisable sans CAP-D2-02. |
| Sélection lasso / rectangle / rangée, retrait de sélection (K46, S053) | PRÉSENT : `RP/layoutEditor.ts` ; bouton « Retirer la sélection » = ACAL418. |
| Guides d'alignement en placement libre | DÉJÀ PLANIFIÉ : ACAL425. |
| Barre Pivoter / Aligner / Répartir sur la sélection | DÉJÀ PLANIFIÉ : ACAL411 (la sélection seulement, pas les rangées : CAP-D2-17). |
| Annuler / rétablir partout | DÉJÀ PLANIFIÉ : ACAL412, ACAL413. |
| Conception automatique depuis un lead ; cible kWh/an | DÉJÀ PLANIFIÉ : ACAL421, ACAL470 (CAP-D2-01 en dépend). |
| Balayage inclinaison × azimut d'un pan libre | DÉJÀ PLANIFIÉ : ACAL468/469 (sans re-pavage ; le re-pavage existe déjà dans la matrice, CAP-D2-01). |
| Numéros stables des modules sur les sorties | FAIT : ACAL269. |
| Cheminement de câble | DÉJÀ PLANIFIÉ : ACAL472 (D3). |
| Remplacer un module par un autre de mêmes dimensions (K33) | PRÉSENT selon B5-de (module par pan `RP/moduleSelect.ts`) ; geste NON rejoué. |
| Charge admissible du toit comparée à la masse posée | PRÉSENT côté devis : `apps/ventes/roof_load.py` (CIQ114). |

## Tableau de correspondance (id d'origine → sort)

| Lane | Ids → sort |
|---|---|
| B1 | C02, V034 → CAP-D2-01 ; V022 → écarté ; V065 → CAP-D2-16 ; S046 → CAP-D2-01 (+ ACAL470) ; S053 → présent. Les autres C-ids sont hors D2. |
| B2 | n° 2, O12 → CAP-D2-01 ; n° 4 → CAP-D2-11 (t. 4) ; n° 6, O18 → CAP-D2-10 ; n° 9, A54 → présent ; n° 11, O39 → CAP-D2-02 (t. 4) ; n° 12, X16 → CAP-D2-12 ; n° 16 → écarté (D3) ; n° 17 → écarté (D6) ; n° 20 → écarté (D1) ; A33 → CAP-D2-10 ; O19 → CAP-D2-02 / CAP-D2-14. |
| B3 | N1, l. 28/120/269 → CAP-D2-16 ; N2, l. 121/174 → CAP-D2-09 ; N3 → écarté ; N4, l. 29 → CAP-D2-17 ; N5 → écarté (D6) ; N8, l. 165/168 → CAP-D2-08 ; N9 → CAP-D2-11 ; N10 → CAP-D2-07 ; N13b → écarté (D1) ; N14, l. 84 → CAP-D2-12 ; N16 → écarté ; N20, l. 59/190 → CAP-D2-19 ; N23 → CAP-D2-02 ; N24 → écarté (D1) ; N25, l. 30/122 → écarté ; N26, l. 154/295 → CAP-D2-06 ; N28, l. 217 → CAP-D2-05 ; N33, l. 219 → écarté (D4) ; N34, l. 278 → CAP-D2-10 ; l. 24 (carport) → CAP-D2-10 ; l. 112/260 → CAP-D2-20 ; l. 167/172/176 → CAP-D2-14 / CAP-D2-02 ; l. 213 → écarté. |
| B4 | n° 5 (coller) → CAP-D2-12 ; n° 7 → CAP-D2-04 ; n° 11 → CAP-D2-15 (part D4 nommée) ; n° 14 → écarté (D1) ; n° 17 → CAP-D2-07. |
| B5-de | P3, K50 → CAP-D2-04 ; P5, K17, K51 → CAP-D2-11 ; P11, K28, K33 → CAP-D2-18 ; P13 → CAP-D2-20 ; K05 → présent (plan à l'échelle) + CAP-D2-05 (§11 n° 1) ; K18, K32 → CAP-D2-02 ; K22 (52 fils) → CAP-D2-08 / CAP-D2-14 / écarté (Eurocode) ; K34 → présent (`CC/ombre_rangees.py::fraction_ombree_est_ouest`) ; K37 → présent + écarté (vertical) ; K46 → CAP-D2-17 ; K47 → CAP-D2-06 ; §11 n° 1-2 → CAP-D2-05 ; §11 n° 10 → CAP-D2-08 / CAP-D2-14 ; §11 n° 15 → CAP-D2-21 ; P20 → partagé avec CAP-D2-05 (et D6) ; P22 → écarté (D3) ; passe 2 l. 486/635/1381/1430 → CAP-D2-08 ; l. 492/928/1067/1104/1120/1353/1431/919/1052 → CAP-D2-14 ; l. 974/1047 → CAP-D2-09 ; l. 1296/1399/592 → CAP-D2-06 ; l. 1309 → CAP-D2-10 ; l. 1565/1564 → CAP-D2-16 / CAP-D2-12 ; l. 480/846/899 → CAP-D2-02. |
| B5-en | n° 3, groupe 22 → CAP-D2-04 ; n° 12, groupe 41 → CAP-D2-21 ; n° 13, groupe 16 → écarté (D1) ; n° 16, groupe J → CAP-D2-09 ; groupe 35 → CAP-D2-11 ; groupe K → CAP-D2-17 / CAP-D2-01 ; groupe M → CAP-D2-01 ; groupe I (copie) → CAP-D2-12 ; groupe B (plan lisible) → CAP-D2-11 ; groupe 20 → CAP-D2-02 ; n° 7 → écarté (D1) ; n° 17 → D3. |
| B5-fr | n° 8, cluster 24 → CAP-D2-14 ; n° 9, cluster 19 → CAP-D2-15 ; n° 13 → partiel CAP-D2-20 (la check-list de VISITE est D1) ; n° 14 → présent (modèle) / CAP-D2-02 ; n° 15, cluster 32 → écarté ; n° 16, cluster 30 → CAP-D2-10 ; n° 17 → écarté (D1) ; n° 19 → écarté ; cluster 9 → CAP-D2-08 ; cluster 18 → CAP-D2-09. |
| B5-es | n° 5 → CAP-D2-15 ; n° 7 → CAP-D2-11 (+ / −) et D3 (tension) ; n° 9 → CAP-D2-04 ; n° 10 → écarté (D3) ; n° 13 → écarté (D4) ; n° 15 → écarté ; n° 16 → présent (zone réservée) + D3 ; n° 18 → écarté. |
| B5-nl | cluster 4 → présent ; cluster 6-7 → CAP-D2-01 ; cluster 9 → CAP-D2-08 ; n° 7 (DWG) → écarté. |
| B6 | R2, K13 → CAP-D2-12 ; R7 → écarté (D6) ; R10 → CAP-D2-13 ; R11 → CAP-D2-14 ; R12 → CAP-D2-07 ; R13 → CAP-D2-01 ; R14 → CAP-D2-10 ; R16 → CAP-D2-01 ; R26 → CAP-D2-18 ; R31 → CAP-D2-04 ; R33 → CAP-D2-19 ; R37 → CAP-D2-17 ; R40 → CAP-D2-03 ; R43 → CAP-D2-11 ; R44, K80 → CAP-D2-11 ; R48 → CAP-D2-02 (t. 4) ; R50 → écarté ; R51 → écarté (présent) ; R53, K74, K75 → écarté (D1) ; R56 → écarté ; R58 → CAP-D2-06. |
| B7 | U8 → CAP-D2-12 ; U17, cluster 31 → CAP-D2-22 ; U21 → CAP-D2-04 ; cluster 53 → présent ; cluster 71 → CAP-D2-02 / CAP-D2-14. |

## Contradictions entre lanes, tranchées par le code

1. **Structures de montage réutilisables / nomenclature de fixation « PRÉSENT »** (B5-de K32 via `Bibliotheque.jsx`, K18, B3 N23) — **à moitié faux** : le CALCUL existe (`SV/fixation.py::bom_de_fixation`), mais `SystemeFixation`/`ComposantFixation` n'ont ni route, ni admin, ni écran ; `FE/Bibliotheque.jsx` liste presets, kits de géométrie et modèles, pas les systèmes de fixation ; `FE/atelier/Fixation.jsx` l'écrit (« aucune route ne LISTE »). → CAP-D2-02.
2. **Seuil d'accès solaire du remplissage « PRÉSENT »** (B3 §7.2 n° 4) — **le moteur oui, le geste non** : aucun champ n'écrit `optimisation.seuilAccesSolaire` (seul `RP/optimisationDocument.ts` le relit). → CAP-D2-03.
3. **« Pas de mode champ sans bâtiment »** (B2 n° 9, A54) — **faux** : `FE/ModeTerrain.jsx` (CAL89), `RP/poseSurfaces.ts` (CALX123), planche sans toit (ACAL260).
4. **Inclinaison saisonnière** : B1 V022 l'écarte, B5-fr n° 15 la propose — tranché **écarté** (aucun code, preuve mince, structures rares).
5. **« Comparer des dispositions : PRÉSENT »** (B5-nl cluster 6) et « matrice navigateur » (B1 C02) — **vrai dans le code, invisible dans l'ERP** : `RP/matrix.ts::paintComparison` n'a pas d'hôte (`#rp9-compare` absent de `TD`) ; seules les cartes de variantes et la recommandation sont montées. → CAP-D2-01.
6. **Plan de cotes « 4 distances : non vérifié »** (B5-de K17, B5-en groupe 35) — **vérifié absent** : seulement deux cotes d'encombrement (`SV/planche.py::_corps_feuille_toit` → `_cote_horizontale`, `_cote_verticale`).
7. **Documents de chantier K51** : passe 1 « PRÉSENT », passe 2 « PARTIEL » — **PARTIEL** : chaînes en texte dans le bandeau du plan de pose, couleur par chaîne seulement sur le plan de câblage, aucun + / −, plan hors ligne absent.
8. **« Allée tracée seulement, aucune règle automatique »** (B3 N2) — **incomplet** : des îlots automatiques L × W avec allées existent côté serveur et à l'écran (`CC/ilots.py`, `FE/PanneauAllees.jsx`, CIQ137/138) ; ce qui manque est la règle « tous les N modules / N rangs » et son effet dans le pavage navigateur.
9. **« SurfaceSol : terrain plat, pas de rangées »** (B3 l. 137) — **faux pour les rangées** : `CC/surfaces/sol.py` porte le pas inter-rangées et `FE/ModeTerrain.jsx` pose des tables par le moteur.
10. **« Mode de fixation lesté / ancré / soudé absent »** (B5-fr n° 14) — **faux pour le modèle** : `SystemeFixation.ModePose` a `toit_plat_leste`, `toit_plat_fixe`, `bac_acier`, `sol`, `ombriere` ; vrai pour l'usage (catalogue non saisissable).
11. **« Lestage par zones »** (lu dans B5-fr cluster 9 / fiche `PanneauMasseLestage`) — les zones de `SV/lestage.py::_zones_saisies` sont **géographiques** (commune/région), pas des zones de rive : B3 N8 avait raison.
12. **Portrait / paysage « choisi par l'ombre »** (implicite dans B5-es n° 5 « comparer deux variantes existantes ») — le choix automatique se fait par **densité** (`LIB/estimatorBrainV2.ts::PackResult.best`, comparaison `row.length / pitchM`), jamais par l'ombre.

## Non vérifié (dit tel quel)

- Rien n'a été exécuté : aucun écran ouvert, aucun test lancé. « PRÉSENT » = le code existe à l'endroit cité.
- CAP-D2-01 : je n'ai pas vérifié si l'absence de `#rp9-compare` dans `TD` est voulue (aucun commentaire trouvé par grep) ; ni si la production « table par latitude » de la matrice respecte « zéro chiffre inventé » (seule la ligne PVGIS est sourcée à coup sûr).
- CAP-D2-05 : l'absence de motif pour un remplissage vide repose sur un grep de phrases ; une autre formulation peut exister ailleurs dans `RP/layoutEditor.ts` (3 223 lignes, non lu en entier).
- K33 (remplacer un module de mêmes dimensions) : geste non rejoué.
- CAP-D2-19 : la prise en charge des blocs/attributs par `ezdxf` est supposée (bibliothèque standard), non testée ici.
- CAP-D2-09 / 16 / 17 : la faisabilité « sans toucher `packConfig` » (fichier `web`) est une hypothèse de découpe ; si elle échoue, la moitié paveur part au plan transverse.
- Le dossier `docs/audits/2026-11-20-calepinage-l5.md` n'a pas été relu ligne à ligne pour les doublons ; seuls `PLAN_AUDIT_CALEPINAGE.md` (ACAL269, ACAL382-490) et `PLAN2.md` (CAL*/CALX* ouvertes) ont été greppés.
- Les comptes de fils viennent des lanes (non recomptés), sauf la passe 2 allemande dont j'ai relu les lignes K22 citées.

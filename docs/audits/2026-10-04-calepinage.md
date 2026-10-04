# Audit D3 « calepinage » — dossier d'évaluation (L3, 02→04/10/2026)

Unité **D3** du registre (`docs/audits/unites.yml`), groupe **ACAL**, niveau **L3** (défaut du registre
pour D3 ET niveau nommé par Reda : « go extremely deep »). Claim : branche `audit-D3` (d19fb6d8b).
Méthode : `docs/audits/METHODE.md` v2. Sorties brutes (cartes R1, constats R2, verdicts R3, JSON du run
live, captures) : scratchpad de la session, dossier `cal/` — seuls la commande, le SHA et un extrait
court figurent ici.

## 0. Préconditions (phase 0)

- **SHA.** R1 + R2 lus à `0643e17a0` (02/10). R3, run live, C5 et anon à `781ac2259` / `777c2e48d`
  (04/10). Entre les deux, une seule différence sur les chemins de D3 :
  `apps/calepinage/services/pompage.py` (AGR109, noyau `core/pompage`) ; aucun fichier de
  `frontend/src/features/calepinage`, `pages/ventes/{ToitureDesign,Conception3DPage}.jsx`,
  `calepinageApi.js` ni `apps/web/src/scripts` n'a bougé (`git diff --stat 0643e17a0 777c2e48d`).
- **Apps parquées.** `python scripts/check_parked_apps.py` → « OK — aucune référence vers les 47 apps
  parquées ». `ao` est parquée (SOLMVP15) : ses résidus dans le code MVP sont traités en C4.
- **Dédoublonnage.** Tâches ouvertes exclues : PLAN2 CAL51, CALX44, CALX131, CALX199, CALX200,
  CALX339/356/357 (BLOCKED .PAN/.OND), CALX373-375 ; PLAN.md CIQ109/110/112/113/117/136-138/141 (C&I),
  AGR121/125/132 (agricole) ; ERROR_PLAN ERR-QAH-FIG-EDITION-ETUDE-LIVE-VS-DOCUMENT. Groupes antérieurs
  lus : CAL1-248, CALX1-407 (PLAN2), QJR5 (QJR522/556/557/558 touchent la couture devis), six
  ERR-QAH-CALEPINAGE-* cochés le 30/09 (`git log origin/main --since=2026-09-01` sur les chemins de D3,
  index complet au scratchpad `cal/r1_dedupe2.md`).
- **Pile locale (L3).** `manage.py migrate` (02/10 : ventes 0121 ; 04/10 : 18 migrations arrivées entre-
  temps sur main — crm 0118-0122, stock 0160-0162… — appliquées par l'agent live après des 500
  « column crm_lead.pompe_actuelle_cv does not exist »), `docker compose up -d --build frontend` (02/10,
  à `0643e17a0`), redémarrage nginx (amont périmé après recréation des conteneurs → 502).
  `seed_demo` déjà présent (société 2) ; `seed_demo_company` lancé le 04/10 (société 6 ; Faker installé
  dans le conteneur, absent de l'image) ; jeu `anon` présent (société 4, importé auparavant).
- **Écarts d'environnement local constatés (non imputés au produit sans preuve prod).** Clé MapTiler
  absente → l'atelier affiche « Carte indisponible » : les agents live ont intercepté
  `design-context/` et `roof-config` dans Playwright (fausse clé + style vide, rien de persisté) ;
  `POST /api/roof-yield` → 405 (route Astro non servie par le nginx local, 42 erreurs console par
  chargement d'atelier).

## 1. Charte (phase 1)

**Honnêteté de séquence.** La consigne de Reda (02/10, avant la fusion de la méthode v2) fixait le
modèle qualité AVANT tout constat : trois contrôles (modifiabilité et propagation à chaque étape ; une
fonction par geste ; code propre) + sept leçons A-G (aller-retour persisté, source réelle, tous les
appelants, tests comportementaux, chasse au jumeau, déployable, preuve en direct). Il est projeté ici sur
la liste fermée C1-C14 ; aucun critère n'a été ajouté après coup.

- **Système et frontière.** `possede` de D3 : `apps/calepinage/**`, `features/calepinage/**`,
  `api/calepinageApi.js`, `pages/ventes/{ToitureDesign,RoofViewer,RoofViewerPage,Conception3DPage}.jsx`,
  `ventes/domain/geometrie.py`, `apps/web/src/scripts/roof-tool*.ts`, `roofPro11/**`.
  `perimetre_lu` : `crm` roof_outline / roof_point / traceToit (J1a), `ventes/domain/resynchronisation.py`
  (J1b), `services/feu_vert.py` ↔ visites. Coutures lues : `contract_samples/` (48 fichiers),
  événements `lead_created`, `layout_finalise`, `devis_sent`, le miroir CAL39, `build_devis_from_layout`.
- **Objet.** Objectifs fondateur 1 (tout se corrige après coup, sans écraser une saisie), 2 (une
  fonction par geste), 3 (code propre), 4 (chiffre client exact).
- **Personas réelles** (`apps/roles/models.py:1301` `CANONICAL_SYSTEM_ROLES`) : Commercial, Commercial
  responsable, Technicien responsable, Administrateur. Aucun rôle « bureau d'études » : le dessinateur
  a été joué en `demo_admin` (Administrateur) ; un second locataire `demo_admin_full` (société 6) ; le
  jeu anonymisé en `anon_admin` (société 4).
- **Critères retenus** : C1, C2, C3, C4, C5, C6, C7, C8, C9, C10, C11 (règle #4), C12, C13.
  **C14 non retenu** : budgets de perf déjà gardés par CALX385-388, non ré-audités (dit en §8).
- **Sous-domaine** : cœur (dimensionnement → devis → PDF client) ⇒ L3.
- **Étapes (identifiants stables).**
  P1 entrée — P1.1 depuis le lead (cockpit) · P1.2 `/calepinage/nouveau` · P1.3 depuis un devis ·
  P1.4 reprise d'une visite · P1.5 modèle / duplication · P1.6 fiche (renommer, rattachement,
  responsable, étiquettes) · P1.7 liste.
  P2 site — P2.1 photos · P2.2 pente · P2.3 terrain / relevé · P2.4 plan importé · P2.5 horizon ·
  P2.6 obstacles / allées · P2.7 champ au sol / ombrière.
  P3 atelier 3D — P3.1 tracé des pans · P3.2 pose (modules, rangées, module choisi) · P3.3 fixation /
  lestage · P3.4 enregistrer → rouvrir → enregistrer · P3.5 brouillon local.
  P4 électrique — P4.1 désignation module / onduleur · P4.2 séries / affectation · P4.3 équipements,
  cheminements, tronçons, raccordement · P4.4 schéma unifilaire · P4.5 batterie / hors réseau ·
  P4.6 verdict.
  P5 simulation — P5.1 réglages société · P5.2 pertes du calepinage · P5.3 lancer / fraîcheur ·
  P5.4 production, tapis horaire, course du soleil · P5.5 consommation.
  P6 cycle — P6.1 variantes · P6.2 versions / restauration / différences · P6.3 approbation ·
  P6.4 verrou · P6.5 archivage / duplication.
  P7 publication — P7.1 « Générer le devis » · P7.2 resynchroniser · P7.3 badge à jour / périmé ·
  P7.4 3D du devis (Conception3DPage, ToitureDesign mode devis) et miroir CAL39 · P7.5 devis ENVOYÉ
  (D-QJR5-5) · P7.6 devis ACCEPTÉ → Réviser V2 (D-QJR5-2) · P7.7 planche PDF et 3D publique.
  P8 livrables — P8.1 rapport d'étude · P8.2 sorties techniques · P8.3 dossiers réglementaires ·
  P8.4 export / import projet.
  P9 pose réelle — P9.1 relevé as-built · P9.2 écarts → version · P9.3 dossier de fin de chantier.
- **Non-objectifs.** Le module `ao` parqué (seuls ses résidus dans le code MVP) ; le moteur C&I et le
  moteur pompage (groupes CIQ / AGR ouverts : chevauchements renvoyés) ; l'intérieur du moteur PDF
  devis hors planche (unités X4 / D2) ; les sources payantes (CALX131/199/200 GATED).

## 2. Spécification (phase 2)

**Scénarios H×H joués en direct** (stimulus → réponse → mesure) :
S-A aller-retour atelier (document riche semé par l'API, « Enregistrer le calepinage » sans toucher →
GET avant/après, diff clé par clé) ; S-B onglets du rail concurrents (Horizon / Terrain / Ombrière
enregistrés puis atelier enregistré depuis une page ouverte avant) ; S-C publication (Générer →
modifier → badge → Resynchroniser → envoyer → corriger depuis ventes → accepter) ; S-D variantes et
versions (retenir → générer ; restaurer v1 puis v2) ; S-E simulation (fraîcheur, réglages absents,
horizon PVGIS, fenêtre pluriannuelle, multi-pans) ; S-F schéma unifilaire ; S-G multi-société (deux
comptes, substitution d'identifiants) ; S-H parcours complet sur le jeu anonymisé (parité C1 écran =
devis = PDF = page publique).

**Saisie → consommateurs** (le gaspillage est entre les étapes) :

| Saisie | Écrite par | Lue par |
|---|---|---|
| pans, modules, rangées | atelier (`serializeLayout`) | `layout_hash`, devis (composition, resync), planche PDF, 3D publique, simulation, électrique, livrables, as-built |
| champ au sol / ombrière (`poseSurfaces`) | onglets Terrain / Ombrière | devis (ERR-QAH-CALEPINAGE-SOL-DEVIS-422), planche ; **pas** l'atelier, pas la simulation |
| horizon, ombrage proche, environnement | onglet Horizon, atelier | simulation (cascade), étude bancable du devis |
| consommation (CALX254) | atelier | simulation (autoconsommation, batterie) |
| pertes du calepinage | onglet Pertes | simulation |
| réglages société simulation / allées | Réglages | toutes les simulations de la société |
| entrée électrique | onglet Séries / API | chaînes, tronçons, SLD, verdict |
| variante retenue | onglet Variantes / API | as-built, étude (pas le devis ni la planche) |
| GPS du lead | fiche lead | épingle à la création (D-QJR5-15) |

**Chaîne documentaire 1:N.** lead 1-N calepinages ; calepinage 1-N variantes, 1-N versions,
1-1 devis (`devis_id`) ; devis 1-1 copie `roof_layout` (miroir CAL39) ; devis V1 → V2 (`cloner_devis`
porte `roof_layout`, QJR558) ; calepinage → pose réelle → dossier de fin de chantier.

**Seuils.** S1-S2 ⇒ tâche ; S3 ⇒ tâche si effort ≤ M ; S4, style, durcissement hypothétique ⇒ liste
OPTIONNELLE. Chiffre client / zéro chiffre inventé : toujours correctness.

**Détecteurs (phase 4-a), tous exécutés à `d19fb6d8b`, tous verts** — ce qui est en soi un constat
d'échappement (aucune garde n'attrape les défauts reproduits) :
`check_parked_apps.py` OK · `check_calepinage_actions_consommees.py` « 81 @action, 21 dettes gelées,
dont 1 désormais branchée » · `check_services_appeles.py` « 474 fonctions, 166 dettes gelées » ·
`check_ecrans_atteignables.py` « 534 écrans, 10 dettes » · `check_api_shapes.py` OK (aucun échantillon
de la LISTE des calepinages n'existe : la forme mockée par `CalepinageList.err-qah-rattachement.test.jsx`
n'est donc pas contrôlée) · `check_api_contract.py` OK · `check_tests_source_regex.py` OK ·
`check_invariants.py` OK · `frontend/scripts/check_dockerfile_context.mjs` OK ·
`ci_guards.py stage-names` (voir §4).

## 3. Plan des lanes (phase 3)

| Ronde | Lanes (modèle / effort) | Travail |
|---|---|---|
| R1 | 4 éclaireurs : routes↔appelants (sonnet/medium), état persisté (sonnet/medium), jumeaux (sonnet/high), dédup (haiku/low, refait mécaniquement par l'orchestrateur) | cartes `cal/r1_*.md` |
| R2 | 10 lanes : ENT entrée, SIT site, ATL atelier 3D (opus/high), ELE électrique, SIM simulation, CYC cycle, PUB publication (opus/high), LIV livrables, JUM jumeaux (opus/high), NET nettoyage — sonnet/high sauf mention ; + 1-2 « chercheurs de manques » frais par lane (sonnet/high, boucle jusqu'à sec, plafond 2) | 345 constats bruts |
| R3 | par lane : réfuteur-code frais (opus sur ATL/PUB/JUM, sonnet ailleurs), lentille exécution (sonnet), lentille chiffres-client (sonnet ; ATL/ELE/SIM/PUB/LIV/JUM) | verdicts |
| Live | 3 agents Playwright (sonnet/high : atelier, publication, simulation) ; C5 statique (opus/high) + rejeu deux comptes et parcours anon (sonnet/high) | reproduction des bloquants |
| R4 | Fable : adjudication des familles S1 + contestés ; critique de complétude ; revue du groupe assemblé | tâches ACAL |

## 4. Manifeste de couverture (phase 4)

- **Lanes R2 (10)** : surfaces de la charte §3 ; les fichiers NON lus par lane sont listés au scratchpad (`cal/r2r3_full.json`, champ `non_couvert`) — principaux : `services/import_plan.py`, `releve.py`, `horizon.py` (corps), `Bibliotheque.jsx`, internes de `PanneauDocuments`, `etude_horaire.py` (3 403 l.), `solar_design.py` hors entrées chaînes/batterie, `views/reprise_visite.py`, `views/asbuilt.py`, `tasks.py`, `receivers.py` (lus partiellement).
- **Détecteurs exécutés (12)** à `d19fb6d8b` / `781ac2259`, tous verts : `check_parked_apps`, `check_calepinage_actions_consommees` (81 @action, 21 dettes), `check_services_appeles` (474 fonctions, 166 dettes), `check_ecrans_atteignables` (534 écrans, 10 dettes), `check_api_shapes`, `check_api_contract`, `check_tests_source_regex`, `check_invariants`, `check_dockerfile_context.mjs`, `ci_guards.py stage-names`, `makemigrations --check` (aucun changement), `lint-imports` (17 contrats tenus) ; `audit_coherence --json --no-persist` : AUCUNE règle calepinage (garde M3 « parité calepinage ↔ devis »).
- **Non exécutés** : `tests/test_tenant_sweep.py` (base de test locale interdite hors porte orchestrateur — C5 couvert par la lane opus + le rejeu à deux comptes), `check_openapi_shapes`, `check_lead_webhook_parite`, `check_test_determinism` (hors des surfaces touchées), `scripts/audit_couplage.py` (n'existe pas encore, METHODE §B 4-a), calibration des réfuteurs sur le corpus QJR5 (§7).
- **Scénarios live joués** : S-A à S-H (3 agents Playwright + rejeu C5 + parcours anonymisé) ; 84 oracles de la porte empirique (client HTTP Django, node 24, vitest dans le scratchpad) ; enregistrements `QA-CAL*` en sociétés 2 et 6 seulement. Prévus mais NON joués : 3D publique /proposition rendue (non servie en local), tuiles MapTiler réelles (clé absente : réponses interceptées), PVGIS multi-années au-delà d'une fenêtre.

## 5. Registre des constats (phase 4 → 6)

146 constats par cause racine (410 constats bruts : 382 rattachés, 28 optionnels) ; format §C.1 complet au scratchpad (`cal/gate_cluster.json`, `cal/draft_in/*.json`). Gravité après Fable #1. Une ligne = un constat ; « Tâches » = ACAL qui le corrigent.

| Constat | Étape | Crit. | Grav. | Confiance | Titre | Tâches |
|---|---|---|---|---|---|---|
| C-ACAL-001 | P1.1 | C10 | S2 | CONFIRMÉ (exécuté) | Fusion ou mise à la corbeille du lead : les calepinages restent sur le lead absorbé/supprimé, deviennent invi… | ACAL5, ACAL6, ACAL176, ACAL177, ACAL178, ACAL181, ACAL351 |
| C-ACAL-002 | P1.1 | C3 | S2 | CONFIRMÉ (sonde) | Repère du toit : crm.selectors.repere_toit (QJR598, D-QJR5-15) n'est honoré que par l'auto-devis ; l'atelier… | ACAL5, ACAL19, ACAL249, ACAL250, ACAL251 |
| C-ACAL-003 | P1.1 | C9 | S3 | CONFIRMÉ (sonde) | GPS du lead corrigé après le tracé : le calepinage garde l'ancienne épingle (atelier et site de simulation) s… | ACAL2, ACAL5, ACAL191, ACAL192, ACAL193 |
| C-ACAL-004 | P1.1 | C10 | S3 | CONFIRMÉ (sonde) | Le passage lead → calepinage perd les factures : « Aucune cible de puissance connue », toit rempli en entier,… | ACAL5, ACAL194, ACAL195, ACAL310, ACAL311 |
| C-ACAL-005 | P1.1 | C10 | S3 | CONFIRMÉ (exécuté) | CAL110 coché mais sa moitié publique n'existe pas : rien n'écrit web_questionnaire['roof_layout'], la reprise… | ACAL20, ACAL190, ACAL304, ACAL305 |
| C-ACAL-006 | P1.1 | C10 | S3 | PLAUSIBLE (oracle = test rouge) | Le contour dessiné par le visiteur dans le renvoi (<60 s) de la même soumission n'ouvre jamais le calepinage… | ACAL189 |
| C-ACAL-007 | P1.2 | C3 | S3 | CONFIRMÉ (exécuté) | Cinq portes de création d'un calepinage, une seule passe par services/creation.py : sans chatter « créé », cl… | ACAL12, ACAL182, ACAL183, ACAL184, ACAL185, ACAL187, ACAL188 |
| C-ACAL-008 | P1.2 | C2 | S3 | PLAUSIBLE (oracle = test rouge) | Le « jeu de réglages société » choisi sur Nouveau calepinage (lead/client sans modèle) est validé puis jeté :… | ACAL2, ACAL186, ACAL308 |
| C-ACAL-009 | P1.3 | C6 | S3 | CONFIRMÉ (sonde) | Le rattachement calepinage ↔ devis a quatre écrivains hors lier_devis (PATCH/POST CRUD du champ devis, depuis… | ACAL3, ACAL33, ACAL89 |
| C-ACAL-010 | P1.4 | C10 | S3 | PLAUSIBLE (oracle = test rouge) | Visite technique → calepinage : deux portes (le bureau d'études ouvre l'ancien atelier lead, la reprise du mo… | ACAL13, ACAL208, ACAL209, ACAL210, ACAL211 |
| C-ACAL-011 | P1.5 | C7 | S2 | CONFIRMÉ (exécuté) | Copie (modèle ou « Dupliquer ») : emporte le site du modèle (épingle, géométrie), le résultat simulé sans les… | ACAL117, ACAL351 |
| C-ACAL-012 | P1.6 | C6 | S2 | CONFIRMÉ (sonde) | Renommer (ou tout PATCH) est refusé 400 sur un calepinage né d'un lead avec client, d'un devis ou d'une copie… | ACAL179 |
| C-ACAL-013 | P1.6 | C2 | S3 | CONFIRMÉ (exécuté) | Lead, client et responsable se saisissent à la création mais ne se modifient plus depuis l'écran : mauvais le… | ACAL12, ACAL180, ACAL181, ACAL183 |
| C-ACAL-014 | P1.6 | C5 | S2 | CONFIRMÉ (exécuté) | La « vue restreinte au responsable » (CALX406) n'est pas un prédicat d'accès unique : comparer-projets, expor… | ACAL295, ACAL296, ACAL297 |
| C-ACAL-015 | P1.6 | C5 | S3 | CONFIRMÉ (sonde) | Oracle d'existence inter-sociétés sur client, devis et responsable (POST/PATCH calepinage) : « n'appartient p… | ACAL298 |
| C-ACAL-016 | P1.6 | C5 | S2 | CONFIRMÉ (sonde) | Le titre « Calepinage <nom du lead> » fige le nom d'une personne : l'anonymisation DSR (loi 09-08) du lead ne… | ACAL2, ACAL299, ACAL300, ACAL301 |
| C-ACAL-017 | P1.7 | C10 | S3 | CONFIRMÉ (sonde) | Liste des calepinages : l'écran lit la forme du détail (vignette, référence, date « — », client seul « Sans r… | ACAL11, ACAL196, ACAL197, ACAL348 |
| C-ACAL-018 | P1.7 | C10 | S3 | PLAUSIBLE (oracle = test rouge) | Recherche globale : le groupe « Calepinages » est servi mais cliquer un résultat n'ouvre rien (aucune route f… | ACAL198, ACAL199 |
| C-ACAL-019 | P2.1 | C13 | S2 | CONFIRMÉ (exécuté) | Photos de site, plan importé et aperçus : URL MinIO présignées vers l'hôte interne minio:9000 (et photos repr… | ACAL6, ACAL13, ACAL200, ACAL201, ACAL314 |
| C-ACAL-020 | P2.1 | C6 | S3 | CONFIRMÉ (sonde) | Photos de site : genre/date/légende non modifiables, photo non supprimable, « Enregistrer le calage » sans to… | ACAL13, ACAL202, ACAL203 |
| C-ACAL-021 | P2.1 | C13 | S3 | CONFIRMÉ (sonde) | Calage d'une photo : la carte démarre au zoom 20 sur des tuiles OSM qui répondent 400, sur un plan de rues au… | ACAL202, ACAL203 |
| C-ACAL-022 | P2.2 | C3 | S1 | CONFIRMÉ (exécuté) | Trois notions de pente sans règle de préséance : l'onglet Pente écrit une clé racine penteDeg que personne ne… | ACAL2, ACAL58, ACAL61, ACAL252, ACAL253 |
| C-ACAL-023 | P2.2 | C2 | S3 | PLAUSIBLE (oracle = test rouge) | Suggestion de pente IGN : la provenance (pitchSuggestion) disparaît au prochain enregistrement de l'atelier,… | ACAL1, ACAL2, ACAL65, ACAL66 |
| C-ACAL-024 | P2.3 | C2 | S3 | CONFIRMÉ (exécuté) | Relevé terrain : le panneau n'écrit que, ne relit jamais l'historique ; chaque Enregistrer crée une nouvelle… | ACAL13, ACAL204, ACAL205 |
| C-ACAL-025 | P2.3 | C10 | S3 | PLAUSIBLE (oracle = test rouge) | Le relevé terrain (chaînes de cotes + azimut boussole) est un cul-de-sac : sa géométrie résolue n'alimente ni… | ACAL2, ACAL13, ACAL206, ACAL207 |
| C-ACAL-026 | P2.4 | C10 | S3 | CONFIRMÉ (exécuté) | Le calque de fond de l'atelier (photo calée / plan importé, CALX86-108) n'a aucun producteur : rien n'écrit r… | ACAL13, ACAL67, ACAL68, ACAL72, ACAL317 |
| C-ACAL-027 | P2.4 | C10 | S2 | CONFIRMÉ (exécuté) | Plan importé : le calage est rangé sous une clé racine planImporte sans lecteur (effacée par l'atelier), « Co… | ACAL13, ACAL69, ACAL70, ACAL71, ACAL72, ACAL73 |
| C-ACAL-028 | P2.4 | C7 | S3 | CONFIRMÉ (sonde) | Analyse DXF/PDF : le « contour » retenu est l'entité qui a le plus de SOMMETS (un plan en LINE donne un segme… | ACAL13, ACAL212, ACAL213 |
| C-ACAL-029 | P2.5 | C10 | S2 | CONFIRMÉ (sonde) | Tout calepinage avec un profil d'horizon enregistré est REFUSÉ par la simulation : le document porte azimuthD… | ACAL123, ACAL124, ACAL351 |
| C-ACAL-030 | P2.5 | C7 | S3 | PLAUSIBLE (oracle = test rouge) | Horizon : ajouter un point à un profil PVGIS requalifie tout le profil en « saisie », en retirer un le laisse… | ACAL124 |
| C-ACAL-031 | P2.5 | C3 | S3 | CONFIRMÉ (sonde) | Géométrie solaire codée plusieurs fois côté écran : horizonMath.js/obstructionMath.js copies de horizonEngine… | ACAL254, ACAL255, ACAL349 |
| C-ACAL-032 | P2.5 | C2 | S3 | PLAUSIBLE (oracle = test rouge) | Course du soleil : la hauteur de toit saisie n'est qu'un état d'écran (perdue au rechargement) et ignore buil… | ACAL74 |
| C-ACAL-033 | P2.6 | C10 | S3 | CONFIRMÉ (exécuté) | Allée technique, retrait de rive et dégagements par type enregistrés « pour votre société » ne sont lus par a… | ACAL2, ACAL256, ACAL257, ACAL258, ACAL312 |
| C-ACAL-034 | P2.7 | C3 | S1 | CONFIRMÉ (exécuté) | Écrans jumeaux Terrain / Ombrière : l'ombrière ne persiste ni la puissance ni les cotes du module (devis à 55… | ACAL2, ACAL25, ACAL351 |
| C-ACAL-035 | P2.7 | C3 | S1 | CONFIRMÉ (Playwright) | poseSurfaces (champ au sol, ombrière) est un tiroir parallèle que la plupart des lecteurs ignorent : un site… | ACAL2, ACAL18, ACAL59, ACAL60, ACAL61, ACAL259, ACAL260, ACAL261, ACAL262, ACAL346 |
| C-ACAL-036 | P2.7 | C7 | S3 | CONFIRMÉ (sonde) | Champ au sol / ombrière : la pente du terrain saisie ne change ni le nombre de modules ni le pas (moteur appe… | ACAL75 |
| C-ACAL-037 | P3.1 | C6 | S3 | CONFIRMÉ (sonde) | Contour de toit croisé (nœud papillon) : la garde AOF84 (contourSeCroise) est morte côté ERP et absente au gl… | ACAL76, ACAL77 |
| C-ACAL-038 | P3.1 | C2 | S3 | PLAUSIBLE (oracle = test rouge) | « Recommencer depuis le tracé client » ne remet pas à zéro les arêtes corrigées à la main : types et retraits… | ACAL78 |
| C-ACAL-039 | P3.1 | C12 | S3 | CONFIRMÉ (sonde) | Clé carte PUBLIC_MAPTILER_KEY : trois lecteurs jumeaux côté serveur, variable documentée ni dans .env.example… | ACAL282 |
| C-ACAL-040 | P3.2 | C3 | S2 | PLAUSIBLE (oracle = test rouge) | Le plafond de 400 panneaux « nécessaires » est codé deux fois et appliqué à la cible VENDUE : un devis indust… | ACAL79 |
| C-ACAL-041 | P3.2 | C13 | S3 | PLAUSIBLE (oracle = test rouge) | Chaque ouverture de l'atelier émet 42 erreurs console : POST /api/roof-yield répond 405 (endpoint de l'app we… | ACAL80 |
| C-ACAL-042 | P3.2 | C3 | S1 | CONFIRMÉ (exécuté) | Le module choisi par pan dans l'atelier (modules[].produitId, CALX109/110) n'atteint aucun consommateur : le… | ACAL8, ACAL18, ACAL62, ACAL63, ACAL261, ACAL262, ACAL263, ACAL264 |
| C-ACAL-043 | P3.3 | C2 | S2 | CONFIRMÉ (exécuté) | Le système de fixation « appliqué » n'est qu'un paramètre d'URL : perdu au rechargement et ignoré par le clas… | ACAL1, ACAL81, ACAL82 |
| C-ACAL-044 | P3.4 | C2 | S1 | CONFIRMÉ (Playwright) | Le document roof_layout est réécrit EN ENTIER par sept écrivains (onglets Horizon/Pente/Terrain/Ombrière/Plan… | ACAL1, ACAL5, ACAL22, ACAL23, ACAL24, ACAL316, ACAL317, ACAL351 |
| C-ACAL-045 | P3.4 | C2 | S1 | CONFIRMÉ (Playwright) | L'atelier 3D n'est pas symétrique : serializeLayout reconstruit le document depuis l'état chargé au boot et t… | ACAL2, ACAL26, ACAL27, ACAL28, ACAL29, ACAL30, ACAL31, ACAL343, ACAL351 |
| C-ACAL-046 | P3.4 | C2 | S2 | CONFIRMÉ (exécuté) | Les compteurs d'identifiants de l'atelier (area-N, obs-N, zone-N) repartent de zéro à chaque ouverture : ajou… | ACAL64 |
| C-ACAL-047 | P3.4 | C13 | S3 | PLAUSIBLE (oracle = test rouge) | Le contexte chargé au boot n'est jamais rafraîchi après un enregistrement : la note « calepinage automatique… | ACAL83 |
| C-ACAL-048 | P3.5 | C13 | S3 | CONFIRMÉ (sonde) | Brouillon local (CALX68) : écrit pour une session non touchée (parfois un document vide), jamais effacé par «… | ACAL84 |
| C-ACAL-049 | P3.5 | C2 | S2 | CONFIRMÉ (exécuté) | Modes devis et lead de l'atelier 3D : aucune garde de sortie ni brouillon — Fermer, retour navigateur ou ferm… | ACAL85 |
| C-ACAL-050 | P4.1 | C10 | S2 | CONFIRMÉ (sonde) | Le module PV et l'onduleur du calcul électrique ne se désignent nulle part : électrique, schéma et simulation… | ACAL9, ACAL56, ACAL149, ACAL322, ACAL351 |
| C-ACAL-051 | P4.2 | C3 | S2 | CONFIRMÉ (exécuté) | Aucune clé stable de pan/module : affectation manuelle des chaînes indexée 'pan#rang' (glisse quand un module… | ACAL8, ACAL16, ACAL265, ACAL266, ACAL267, ACAL268, ACAL269, ACAL307 |
| C-ACAL-052 | P4.2 | C7 | S2 | CONFIRMÉ (sonde) | Un calepinage 100 % micro-onduleurs exige de désigner un onduleur de chaîne fictif : sans lui, aucun bloc mic… | ACAL162, ACAL351 |
| C-ACAL-053 | P4.3 | C10 | S2 | CONFIRMÉ (sonde) | Les entrées électriques (températures, longueurs, phases, cheminement, protections, terre, polystring, exigen… | ACAL9, ACAL151, ACAL152, ACAL153, ACAL154, ACAL322, ACAL351 |
| C-ACAL-054 | P4.3 | C6 | S2 | CONFIRMÉ (sonde) | Saisies électriques enregistrées sans validation puis refusées au calcul : une température à moitié saisie, u… | ACAL150, ACAL351 |
| C-ACAL-055 | P4.3 | C2 | S2 | CONFIRMÉ (exécuté) | Calepinage.resultat est un sac partagé par sept écrivains (simulation, entrée électrique, raccordement, schém… | ACAL57, ACAL321, ACAL351 |
| C-ACAL-056 | P4.3 | C10 | S2 | CONFIRMÉ (sonde) | Le raccordement saisi (cos φ, plafond d'injection, puissance souscrite) vit à trois endroits sans pont : resu… | ACAL9, ACAL155, ACAL156, ACAL351 |
| C-ACAL-057 | P4.3 | C10 | S3 | CONFIRMÉ (sonde) | Les décisions société de la check-list de protections (organe écarté avec motif, organe ajouté) n'atteignent… | ACAL154, ACAL159, ACAL351 |
| C-ACAL-058 | P4.3 | C9 | S3 | PLAUSIBLE (oracle = test rouge) | Le lead porte déjà la puissance souscrite et le raccordement mono/triphasé ; le calepinage créé depuis le lea… | ACAL9, ACAL157, ACAL158, ACAL351 |
| C-ACAL-059 | P4.4 | C13 | S2 | CONFIRMÉ (Playwright) | Le schéma unifilaire du calepinage plante (AttributeError, 500) dès qu'une conception est calculable : le ser… | ACAL55, ACAL351 |
| C-ACAL-060 | P4.4 | C2 | S3 | CONFIRMÉ (sonde) | Schéma unifilaire éditable (libellés, repères, positions) : tout le serveur existe mais aucun écran n'envoie… | ACAL160, ACAL161, ACAL351 |
| C-ACAL-061 | P4.4 | C3 | S2 | CONFIRMÉ (exécuté) | Deux conceptions électriques pour un même toit : le devis dimensionne à -5/70 °C et 30/15 m forfaitaires (ele… | ACAL10, ACAL163, ACAL164, ACAL165, ACAL351 |
| C-ACAL-062 | P4.5 | C10 | S2 | CONFIRMÉ (sonde) | Batterie, hors-réseau et stratégie : aucune porte (ni builder ni HTTP) ne les déclare, la batterie négociée d… | ACAL9, ACAL166, ACAL167, ACAL168, ACAL322, ACAL351 |
| C-ACAL-063 | P4.5 | C3 | S3 | PLAUSIBLE (oracle = test rouge) | Simulation de batterie en doublon : le même pack reçoit un rendement 0,90 dans le module et 0,9216 sur la pro… | ACAL10, ACAL173, ACAL306, ACAL330, ACAL351 |
| C-ACAL-064 | P4.6 | C7 | S2 | CONFIRMÉ (exécuté) | Verdict électrique : deux verdicts pour « peut-on publier ? » (evaluation_electrique vs verdict_publiable, qu… | ACAL9, ACAL169, ACAL170, ACAL171, ACAL172, ACAL351 |
| C-ACAL-065 | P5.1 | C10 | S3 | PLAUSIBLE (oracle = test rouge) | Trois réglages société se saisissent mais aucune étape ne lit leur valeur : cos_phi_par_defaut, favoris_mater… | ACAL9, ACAL174, ACAL175, ACAL320, ACAL322, ACAL347, ACAL351 |
| C-ACAL-066 | P5.1 | C7 | S2 | CONFIRMÉ (sonde) | Base de temps de la série : fuseau, pays et altitude du site n'ont aucun écran (blocs horaires toujours omis)… | ACAL8, ACAL129, ACAL130, ACAL131, ACAL351 |
| C-ACAL-067 | P5.1 | C6 | S2 | CONFIRMÉ (sonde) | Réglages de simulation société : n'importe quel texte est accepté (« 2,5 » enregistré puis toutes les simulat… | ACAL8, ACAL126, ACAL132, ACAL133, ACAL351 |
| C-ACAL-068 | P5.1 | C9 | S3 | CONFIRMÉ (sonde) | Réglages de simulation société-wide : aucun gel dans le résultat, aucune surcharge par calepinage ; le même c… | ACAL8, ACAL48, ACAL52, ACAL132, ACAL133, ACAL134 |
| C-ACAL-069 | P5.1 | C5 | S2 | CONFIRMÉ (exécuté) | Les réglages société du module (simulation, norme, lestage, dégagements, imagerie, vue restreinte, approbatio… | ACAL302 |
| C-ACAL-070 | P5.2 | C2 | S2 | CONFIRMÉ (sonde) | Saisie des pertes : un pourcentage tapé est écarté sans le dire (étape calculable ou réglage société du même… | ACAL8, ACAL135, ACAL136, ACAL351 |
| C-ACAL-071 | P5.2 | C10 | S2 | CONFIRMÉ (sonde) | resultat['pertes'] n'est écrit par personne : « Lancer la simulation » inactif au premier calcul et en état p… | ACAL8, ACAL125, ACAL127 |
| C-ACAL-072 | P5.2 | C10 | S2 | CONFIRMÉ (sonde) | L'accès solaire par module (CAL248 → CALX158) ne fait jamais le trajet atelier → simulation : publié seulemen… | ACAL2, ACAL137, ACAL138 |
| C-ACAL-073 | P5.3 | C2 | S1 | CONFIRMÉ (Playwright) | L'empreinte de fraîcheur de la simulation (hash_entree) est celle de l'AFFECTATION électrique : pertes, horiz… | ACAL8, ACAL48, ACAL145, ACAL146, ACAL147, ACAL148, ACAL351 |
| C-ACAL-074 | P5.3 | C13 | S2 | CONFIRMÉ (Playwright) | Lancer / Relancer la simulation depuis l'écran : le suivi du job attend le vocabulaire Celery (PENDING/STARTE… | ACAL8, ACAL125, ACAL126, ACAL351 |
| C-ACAL-075 | P5.3 | C1 | S2 | CONFIRMÉ (Playwright) | L'étude bancable du devis lit l'ombrage d'une cascade périmée : le contrôle « cette cascade décrit CE documen… | ACAL143, ACAL144, ACAL351 |
| C-ACAL-076 | P5.4 | C1 | S1 | CONFIRMÉ (Playwright) | Une société sans réglages publie un P50 et un PR de 100 % avec 23 postes de pertes sur 24 omis, sans le moind… | ACAL8, ACAL49, ACAL50, ACAL51, ACAL52, ACAL313, ACAL351 |
| C-ACAL-077 | P5.4 | C7 | S1 | CONFIRMÉ (Playwright) | Plusieurs pans : les chaînes par pan tournent sans bloc météo.heure, donc IAM, horizon, inter-rangées et accè… | ACAL8, ACAL53, ACAL351 |
| C-ACAL-078 | P5.4 | C7 | S2 | CONFIRMÉ (Playwright) | Plusieurs pans : la cascade publiée ne décrit que le pan le plus puissant — l'étude bancable du devis appliqu… | ACAL8, ACAL53, ACAL143, ACAL144 |
| C-ACAL-079 | P5.4 | C1 | S1 | CONFIRMÉ (sonde) | Le P50 « annuel » est la SOMME de toute la fenêtre météo : jusqu'à 10 ans de production publiés comme une ann… | ACAL8, ACAL54, ACAL351 |
| C-ACAL-080 | P5.4 | C7 | S2 | CONFIRMÉ (sonde) | Le ratio de performance (PR) est calculé sur l'irradiance EFFECTIVE (après IAM, horizon, ombrage) : il ne voi… | ACAL8, ACAL128 |
| C-ACAL-081 | P5.4 | C7 | S2 | CONFIRMÉ (sonde) | Un pan est-ouest est simulé entièrement face à l'est (un seul appel PVGIS à aspect −90) alors que le construc… | ACAL139 |
| C-ACAL-082 | P5.4 | C3 | S3 | CONFIRMÉ (sonde) | Le diagramme de pertes séquentiel additionne des pourcentages relatifs : la barre « Énergie livrée » contredi… | ACAL140 |
| C-ACAL-083 | P5.4 | C10 | S3 | CONFIRMÉ (sonde) | Colonnes et blocs du contrat de simulation jamais alimentés : ratio_dc_ac.ecretage_pct (p_dc_kw écrit par auc… | ACAL141, ACAL142 |
| C-ACAL-084 | P5.4 | C3 | S3 | PLAUSIBLE (oracle = test rouge) | Productible de repli « PVGIS indisponible / ville inconnue » : quatre valeurs (1 488, 1 500, 1 536, 1 600 kWh… | ACAL270, ACAL271 |
| C-ACAL-085 | P6.1 | C2 | S3 | CONFIRMÉ (exécuté) | Variantes : impossible de créer la première depuis l'interface (la page Comparer est une impasse), et aucune… | ACAL109, ACAL351 |
| C-ACAL-086 | P6.1 | C10 | S2 | CONFIRMÉ (exécuté) | Comparatif de variantes et de projets : aucune porte ne simule une variante (colonnes toujours « non simulée… | ACAL7, ACAL8, ACAL111, ACAL112, ACAL113, ACAL351 |
| C-ACAL-087 | P6.1 | C1 | S2 | CONFIRMÉ (Playwright) | « Retenir une variante » ne change rien à ce qui est chiffré : Générer/Resynchroniser le devis exigent une va… | ACAL107, ACAL108, ACAL109, ACAL351 |
| C-ACAL-088 | P6.1 | C7 | S3 | PLAUSIBLE (oracle = test rouge) | Le journal ignore la vie des variantes : « retenue » est inscrite sans auteur, création / modification / supp… | ACAL107, ACAL110 |
| C-ACAL-089 | P6.2 | C7 | S3 | CONFIRMÉ (sonde) | Performance (C14 hors schéma, rattaché au traitement) : la simulation persiste jusqu'à 3,5 Mo dans Calepinage… | ACAL122 |
| C-ACAL-090 | P6.2 | C2 | S1 | CONFIRMÉ (Playwright) | layout_hash (QJ17, conçu pour dédoublonner un double clic) sert de test « le document a changé » : il ignore… | ACAL39, ACAL40, ACAL41, ACAL117, ACAL318, ACAL351 |
| C-ACAL-091 | P6.2 | C2 | S1 | CONFIRMÉ (Playwright) | Restaurer une version perd définitivement l'état courant : aucun instantané « avant restauration », tout le s… | ACAL45, ACAL106, ACAL351 |
| C-ACAL-092 | P6.2 | C10 | S3 | PLAUSIBLE (oracle = test rouge) | Calepinage.version_moteur n'est écrit par personne : le pied de planche du PDF client, les documents, le webh… | ACAL121 |
| C-ACAL-093 | P6.3 | C4 | S3 | CONFIRMÉ (sonde) | Calepinage.statut (brouillon/validé/périmé) n'est jamais écrit au-delà de « brouillon » mais reste inscriptib… | ACAL6, ACAL114, ACAL115 |
| C-ACAL-094 | P6.3 | C7 | S3 | CONFIRMÉ (exécuté) | L'approbation est un drapeau lié à aucune conception : elle reste « approuvé » après modification ou restaura… | ACAL6, ACAL114, ACAL115, ACAL116, ACAL351 |
| C-ACAL-095 | P6.3 | C5 | S3 | CONFIRMÉ (sonde) | Auto-approbation possible : decider() n'empêche pas l'auteur ou le responsable d'approuver sa propre concepti… | ACAL303 |
| C-ACAL-096 | P6.4 | C3 | S1 | CONFIRMÉ (Playwright) | Deux prédicats « ce devis est-il modifiable ? » : le verrou CAL207 du calepinage (statut != brouillon) contre… | ACAL42, ACAL43, ACAL44, ACAL319, ACAL351 |
| C-ACAL-097 | P6.4 | C6 | S3 | CONFIRMÉ (exécuté) | Le verrou ne protège que roof_layout : variantes, retenue, pertes et simulation, saisies électriques, dérogat… | ACAL43, ACAL44, ACAL319 |
| C-ACAL-098 | P6.5 | C6 | S3 | CONFIRMÉ (exécuté) | DELETE (et PUT) sur calepinages/<pk>/ : suppression dure (versions, variantes, photos en CASCADE) même avec u… | ACAL6, ACAL120 |
| C-ACAL-099 | P6.5 | C10 | S2 | CONFIRMÉ (exécuté) | L'état « archivé » n'existe que dans apps.trash et chaque lecteur le filtre à la main : un calepinage archivé… | ACAL118, ACAL119, ACAL351 |
| C-ACAL-100 | P7.1 | C10 | S3 | CONFIRMÉ (sonde) | offres_tailles écrit battery: true/false dans Devis.roof_layout alors que le contrat roof_layout_v2 n'admet q… | ACAL2, ACAL86 |
| C-ACAL-101 | P7.1 | C3 | S3 | CONFIRMÉ (exécuté) | Trois productions pour une même installation sans réconciliation : le devis n'emprunte au calepinage que l'om… | ACAL8, ACAL104, ACAL105 |
| C-ACAL-102 | P7.1 | C2 | S2 | CONFIRMÉ (exécuté) | « Générer le devis » depuis la 3D d'un lead : le POST /layout/ qui suit la création écrase le layout enrichi… | ACAL96, ACAL97 |
| C-ACAL-103 | P7.1 | C2 | S2 | CONFIRMÉ (exécuté) | « Générer / Resynchroniser le devis » et « Réviser » de l'atelier travaillent sur le document ENREGISTRÉ sans… | ACAL94, ACAL351 |
| C-ACAL-104 | P7.1 | C3 | S2 | CONFIRMÉ (exécuté) | Dédup de « Générer le devis » : jumelle (copies inline dans from-layout), idempotente seulement pour un broui… | ACAL3, ACAL4, ACAL88, ACAL89, ACAL351 |
| C-ACAL-105 | P7.1 | C3 | S1 | CONFIRMÉ (Playwright) | Devis né du calepinage composé SANS la phase du lead (L-TRI) : onduleur non filtré mono/tri, et les deux entr… | ACAL3, ACAL4, ACAL32, ACAL351 |
| C-ACAL-106 | P7.1 | C7 | S3 | CONFIRMÉ (exécuté) | Le pont devis du module jette ses avertissements de composition (marque épinglée sans candidat, composant int… | ACAL3, ACAL4, ACAL88, ACAL89, ACAL95 |
| C-ACAL-107 | P7.1 | C1 | S2 | CONFIRMÉ (exécuté) | Un devis généré depuis le calepinage naît SANS affiche 3D : Calepinage.roof_image n'est jamais recopiée dans… | ACAL98, ACAL314, ACAL351 |
| C-ACAL-108 | P7.2 | C2 | S2 | CONFIRMÉ (sonde) | Atelier d'un calepinage lié à un devis : au boot la cible du devis (12 panneaux, total vendu) est ré-imposée… | ACAL99 |
| C-ACAL-109 | P7.2 | C3 | S1 | CONFIRMÉ (Playwright) | Deux chemins de resynchronisation : depuis le module, ni études rafraîchies (étude horaire sur l'ancienne tai… | ACAL34, ACAL38, ACAL351 |
| C-ACAL-110 | P7.2 | C7 | S2 | CONFIRMÉ (exécuté) | La resynchro estampille la nouvelle empreinte même quand elle n'a rien appliqué (quantité figée, ligne commun… | ACAL100 |
| C-ACAL-111 | P7.2 | C2 | S1 | CONFIRMÉ (exécuté) | Chaque resynchro qui s'applique RAJOUTE les lignes du kit que le commercial avait supprimées à dessein (trans… | ACAL90, ACAL95 |
| C-ACAL-112 | P7.3 | C1 | S1 | CONFIRMÉ (Playwright) | Le badge « à jour » et la garde QJR522 comparent la copie du DEVIS, jamais le calepinage dont la planche est… | ACAL46, ACAL47, ACAL351 |
| C-ACAL-113 | P7.3 | C1 | S2 | CONFIRMÉ (sonde) | La production imprimée sur le PDF client et la page publique n'est recalée sur le module vendu (715 W) qu'une… | ACAL101, ACAL102 |
| C-ACAL-114 | P7.4 | C3 | S1 | CONFIRMÉ (exécuté) | Deux conceptions pour un même toit : la 3D du devis ouvre Devis.roof_layout et le miroir CAL39 REMPLACE le do… | ACAL5, ACAL35, ACAL36, ACAL37, ACAL38, ACAL351 |
| C-ACAL-115 | P7.6 | C10 | S2 | CONFIRMÉ (exécuté) | « Réviser » (V2) n'emporte pas le calepinage : il reste lié à la V1 remplacée (resynchro 409 « remplacé »), l… | ACAL5, ACAL36, ACAL91, ACAL92, ACAL93, ACAL351 |
| C-ACAL-116 | P7.7 | C3 | S2 | CONFIRMÉ (sonde) | Cinquième estimateur de capacité (calepinage_options : cartes de taille et « Max » de la page client) : retra… | ACAL18, ACAL261, ACAL272 |
| C-ACAL-117 | P7.7 | C1 | S3 | CONFIRMÉ (sonde) | Le PDF /proposal avec include_etude=1 ajoute la planche de calepinage sous AUTO (5 pages) alors que QJR666 la… | ACAL103 |
| C-ACAL-118 | P8.1 | C3 | S2 | CONFIRMÉ (exécuté) | Nombre de modules et kWc d'une conception : six lecteurs aux préséances contradictoires (rapport 36 modules /… | ACAL59, ACAL61, ACAL259, ACAL273, ACAL274 |
| C-ACAL-119 | P8.1 | C10 | S2 | CONFIRMÉ (exécuté) | Carte de chaleur d'ombrage déposée : instantané navigateur sans lien avec la conception, réutilisé périmé dan… | ACAL14, ACAL224, ACAL225, ACAL351 |
| C-ACAL-120 | P8.1 | C1 | S2 | CONFIRMÉ (exécuté) | rapport-etude.pdf servi sans fiches constructeur jointes, sans schéma unifilaire, sans sommaire ni pagination… | ACAL226, ACAL227, ACAL351 |
| C-ACAL-121 | P8.1 | C7 | S3 | PLAUSIBLE (oracle = test rouge) | Versions de documents : chaque GET rapport-etude.pdf écrit une pièce MinIO (même identique), numérotation non… | ACAL14, ACAL221, ACAL222, ACAL223, ACAL351 |
| C-ACAL-122 | P8.1 | C2 | S3 | PLAUSIBLE (oracle = test rouge) | La langue de sortie des documents (?langue=) est un paramètre serveur que le panneau Documents n'expose jamai… | ACAL14, ACAL220, ACAL223, ACAL351 |
| C-ACAL-123 | P8.2 | C13 | S2 | CONFIRMÉ (sonde) | L'aperçu de toiture (roof_image) enregistré à chaque sauvegarde est lu d'un canvas WebGL sans preserveDrawing… | ACAL87 |
| C-ACAL-124 | P8.2 | C10 | S2 | CONFIRMÉ (Playwright) | Deux lecteurs du « résultat » : la forme SERVIE (resultat_calepinage, pose/electrique recalculés, simulation… | ACAL214, ACAL215, ACAL216, ACAL217, ACAL218, ACAL219, ACAL351 |
| C-ACAL-125 | P8.2 | C10 | S2 | CONFIRMÉ (sonde) | Grandeurs lues à des clés que personne n'écrit : kwc/total_modules/pose à la racine du résultat (API publique… | ACAL2, ACAL21, ACAL275, ACAL276, ACAL310 |
| C-ACAL-126 | P8.2 | C4 | S2 | CONFIRMÉ (exécuté) | Régression CALX320 : planche cotée, plans de pose/toiture/masse, note de calcul, DXF, tableurs et pack techni… | ACAL14, ACAL220, ACAL223, ACAL228, ACAL351 |
| C-ACAL-127 | P8.2 | C10 | S3 | CONFIRMÉ (sonde) | Inventaire documents/ : cartes fausses (diagramme_pertes télécharge le JSON d'inventaire, as-built et dossier… | ACAL14, ACAL220, ACAL223, ACAL351 |
| C-ACAL-128 | P8.2 | C13 | S2 | CONFIRMÉ (sonde) | GET export-csv/?quoi=horaire|mensuel|ombrage (TapisHoraire, PanneauSeries) est capturé par la route regex exp… | ACAL229, ACAL351 |
| C-ACAL-129 | P8.2 | C7 | S2 | CONFIRMÉ (sonde) | Repères de rangée du plan de pose et du tableur calculés par ordonnée Nord (tolérance 1 cm) : faux dès que le… | ACAL230, ACAL351 |
| C-ACAL-130 | P8.2 | C8 | S2 | CONFIRMÉ (sonde) | Garde « aucun montant » (prix_achat jamais côté client) appliquée par sous-chaîne à du texte SAISI, en trois… | ACAL231, ACAL351 |
| C-ACAL-131 | P8.2 | C10 | S3 | CONFIRMÉ (sonde) | Plan de masse (et pièce « Plan de masse » du dossier technique) structurellement inatteignable : la parcelle… | ACAL2, ACAL232, ACAL233, ACAL343, ACAL351 |
| C-ACAL-132 | P8.2 | C13 | S3 | CONFIRMÉ (sonde) | Nom de fichier téléchargé : un titre en arabe fait encoder tout l'en-tête Content-Disposition en RFC 2047, le… | ACAL234, ACAL351 |
| C-ACAL-133 | P8.2 | C8 | S3 | PLAUSIBLE (oracle = test rouge) | CALX325 incomplet : la mention « conception verrouillée / archivée » n'est posée que sur 4 PDF ; planche, pla… | ACAL235, ACAL351 |
| C-ACAL-134 | P8.3 | C3 | S2 | CONFIRMÉ (exécuté) | Dépôt GED : dossier technique / fin de chantier / réglementaire idempotents sur l'empreinte géométrique (pièc… | ACAL215, ACAL221, ACAL224, ACAL236, ACAL351 |
| C-ACAL-135 | P8.3 | C10 | S3 | CONFIRMÉ (sonde) | Chaîne « Dossiers réglementaires » morte : aucune porte pour déposer un gabarit ni joindre une pièce, générat… | ACAL15, ACAL238, ACAL239, ACAL240, ACAL241, ACAL242, ACAL309, ACAL351 |
| C-ACAL-136 | P8.3 | C1 | S3 | PLAUSIBLE (oracle = test rouge) | Mauvaise pièce sous le nom « Plan de pose » dans le dossier de fin de chantier : planche cotée au lieu du pla… | ACAL237, ACAL351 |
| C-ACAL-137 | P8.4 | C2 | S2 | CONFIRMÉ (sonde) | Export projet → import → export : aucune saisie électrique (module/onduleur désignés, températures, longueurs… | ACAL17, ACAL243, ACAL244, ACAL351 |
| C-ACAL-138 | P9.1 | C2 | S2 | CONFIRMÉ (exécuté) | Pose réelle : la date de relevé n'est ni servie ni ré-hydratée, corriger un pan RÉÉCRIT la date de tous les r… | ACAL16, ACAL245, ACAL246, ACAL351 |
| C-ACAL-139 | P9.2 | C9 | S3 | PLAUSIBLE (oracle = test rouge) | As-built : le « prévu » est recalculé sur le toit courant / la variante retenue (jamais figé au relevé) et le… | ACAL16, ACAL247, ACAL248, ACAL351 |
| C-ACAL-140 | P1.2 | C10 | S3 | CONFIRMÉ (sonde) | Textes d'écran et guide utilisateur qui promettent des gestes inexistants : « géocodage de l'adresse côté ser… | ACAL333, ACAL334, ACAL335, ACAL336, ACAL351 |
| C-ACAL-141 | P1.6 | C4 | S3 | CONFIRMÉ (sonde) | Résidus AO vivants après SOLMVP15 : appel_offre(_id) inscriptible par l'API sans journal, sélecteur calepinag… | ACAL292, ACAL326, ACAL327, ACAL328, ACAL337, ACAL351 |
| C-ACAL-142 | P2.3 | C6 | S3 | CONFIRMÉ (sonde) | « Refus nommé, jamais un 500 » non tenu : 54 copies privées de _nombre()/_flottant() (15 comportements), si b… | ACAL277, ACAL278, ACAL323 |
| C-ACAL-143 | P2.3 | C13 | S3 | CONFIRMÉ (sonde) | Cinq décodeurs jumeaux des refus serveur côté calepinage : refus feu vert / approbation avalés (« Impossible… | ACAL279, ACAL280 |
| C-ACAL-144 | P2.6 | C3 | S3 | CONFIRMÉ (sonde) | Conversions géographiques codées plusieurs fois : trois repères lat/lng → mètres (sphère, ellipsoïde, 111 320… | ACAL281, ACAL349 |
| C-ACAL-145 | P3.2 | C4 | S3 | CONFIRMÉ (sonde) | Code sans appelant de production tenu vert par les listes d'exemption : coloration par chaîne et palettes jum… | ACAL2, ACAL8, ACAL21, ACAL283, ACAL284, ACAL285, ACAL286, ACAL287, ACAL288, ACAL289, ACAL290, ACAL291, ACAL293, ACAL310, ACAL311, ACAL312, ACAL313, ACAL324, ACAL325, ACAL327, ACAL329, ACAL330, ACAL331, ACAL332, ACAL333, ACAL347, ACAL351 |
| C-ACAL-146 | P3.4 | C4 | S3 | CONFIRMÉ (sonde) | Les détecteurs du module sont verts pendant que les défauts existent : gardes ancrées sur des numéros de lign… | ACAL2, ACAL6, ACAL294, ACAL315, ACAL338, ACAL339, ACAL340, ACAL341, ACAL342, ACAL343, ACAL344, ACAL345, ACAL346, ACAL347, ACAL348, ACAL351 |

**Optionnels (28, S4 / style / hypothétique)** : ENT-16: cosmétique : commentaires périmés sur les portes d'… ; ENT-G2-07: titre > 200 caractères pour un nom de lead > 189… ; ENT-G2-08: référence CAL-AAMM sur la date UTC : faux une he… ; SIT-20: cosmétique : commentaires périmés zones.py / Horizo… ; SIT-G1-15: durcissement hypothétique : appels IGN non borné… ; SIT-G1-16: cosmétique : vestiges AO dans analyse_plan.py ; SIT-G2-15: cosmétique : « Bâtiment » texte libre sur l'ombr… ; ATL-G2-08: cosmétique : « version 4821 » = clé primaire glo… ; ATL-G2-09: cosmétique : champ « pourquoi » périmé du contra… ; ELE-G1-13: cosmétique : CheminementCables annonce une route… ; CYC-16: cosmétique (R3) : diff de versions ignore les ancie… ; CYC-19: cosmétique : commentaires périmés verrou/révision/h… ; PUB-13: cosmétique : commentaires « 409 / Réviser sur un de… ; LIV-20: cosmétique : docstrings périmées documents/rapport/… ; JUM-G2-09: cosmétique, en partie réfuté (R3 : _origine_cale… ; NET-06: tâche de plan CALX44 à retirer (doc de plan, déjà s… ; NET-08: cosmétique : prose AO dans ~110 lignes de commentai… ; NET-G1-07: cosmétique : apps/web/src/lib/devisDesign.ts san… ; NET-G2-07: cosmétique : README contract_samples / E2E_HOOKS… ; NET-G2-08: cosmétique : notes de lane AO à la racine du dép… ; C5L-02: S4 (lane C5) : id produit étranger persisté dans en… ; LIVEX-01: environnement local : migrations stock non appliq… ; LIVEX-04: observation non investiguée : échec de connexion… ; LIVEX-07: faux positif : PATCH {nom} — le champ s'appelle t… ; LIVEX-08: environnement local : base non migrée (crm 0118-0… ; LIVEX-10: observabilité hors module : le gestionnaire d'err… ; LIVEX-13: méta : désaccord entre PUB-01 et CYC-03 sur le ba… ; LIVEX-14: hors module (ventes) : PATCH statut='envoye' igno….

## 6. Non-risques (ATAM — valides tant que l'hypothèse tient)

- Les 52 routes GET de détail du CalepinageViewSet (détail racine + 51 @action GET, greffées par views/rattachements.py comprises) ont été balayées en demo_admin_full (société 6) sur le calepinage 3 (société 2) : 52 sur 52 répondent 404, aucune 403, aucune donn…
- Sous-ressources d'une autre société atteintes via son propre calepinage 19 (sonde exécutée) : GET variantes/1/ (variante de la société 2) → 404 « Variante introuvable » ; GET versions/25/diff/ → 404 ; ?contre=25 → 404. Hypothèse : selectors.variantes() et ver…
- Filtres de liste sur des id d'une autre société (sonde exécutée) : ?lead=2063 → [] et ?client=1 → [] ; la liste ne renvoie que [19]. GET modeles/ → [].
- POST comparer-projets avec les ids [3,4,5] de la société 2, appelé depuis la société 6 → lignes [] ; chaque id est rendu en refus « introuvable dans cette société » (sonde exécutée). Le filtre company du service tient.
- GET moteur/resultat/16/ (BackgroundJob de la société 2) depuis la société 6 → 404 (sonde exécutée). La vue filtre pk + company + kind ; test existant : test_moteur_async.test_job_d_une_autre_societe_introuvable.
- API publique (clé read:calepinages de la société 6, sonde annulée) : liste → [19] ; ?lead_id=2063 → [] ; retrieve 3 → 404 ; resultat 3 → 404 ; resultat 19 → 200. Hypothèse : liste_calepinages(request.auth.company) rend un queryset vide pour None.
- GET sur 42 sous-routes du calepinage (detail, layout, versions, variantes, resultat, documents, rapport-etude.pdf, export-projet.json, photos, schema-unifilaire, comparer, schema-unifilaire.dxf, sorties, planche.pdf/svg, plan-pose/plan-toiture, diagramme-pert…
- Écritures en tant que B sur les calepinages A 3 et 4 (layout, simuler, generer-devis, entree-electrique avec produits 366/367, evaluer-electrique, sync-devis, variantes POST, versions/1/restaurer, PATCH, DELETE, photos, dupliquer, archiver, enregistrer-pertes…
- versions/<1..120>/restaurer/ POST sur le calepinage 19 de B (les ids de versions réels de A sont 3 à 8) : 120/120 en 404 ; variantes/<1..120>/ GET et variantes/<1..120>/retenir/ POST : 240/240 en 404 ; photos/1..5/calage PATCH : 404.
- PATCH lead:2063 (lead de A) sur le calepinage 19 : 400 « Lead introuvable (#2063) », message identique à lead:99999, aucune donnée de A ; PATCH avec company:2 ignoré, le calepinage reste en société 6. depuis-lead {lead:2063} : 400 « Lead introuvable » identiq…
- comparer-projets {ids:[19,3]} et {ids:[3,4]} : 200 mais les ids de A tombent dans « refus » avec le message générique « introuvable dans cette société », sans aucune donnée de A (lignes vides). comparatif.xlsx?ids=3,4 : classeur parsé, il ne contient que « QA…
- ventes/devis/from-layout/ {calepinage:3}, {calepinage:4}, {calepinage:19,lead:2063} et {calepinage:99999} : 422 « Aucune variante retenue » strictement identique pour id étranger et inexistant (nomenclature_variante_retenue filtre par société) ; avec un layou…
- C8 : aucune chaîne marge / prix d'achat / prix_achat dans les PDF v1 à v5 (défaut et include_etude) ; parcours récursif du JSON public (quote.*, étude, items) : seules des clés « coût TTC client » et « économie marginale » existent, pas de prix_achat ni marge…
- Le lien de proposition créé avec envoi:false laisse le devis en brouillon ; les modifications du calepinage ne changent jamais le statut du devis (aucune transition de statut observée).
- Lead -> calepinage : la porte « Ouvrir dans le module Calepinage » est idempotente et reprend le GPS du lead (pin = point du lead, source lead_gps), la ville, le lead et le client.
- Générer le devis depuis le calepinage : le devis hérite lead, client et lien calepinage, a_jour=true à la création, et le nombre de panneaux = celui du calepinage (12, 8, 10, 9 testés ; structures et socles suivent).
- Resynchroniser le devis converge sur les lignes (panneaux, structures, socles) et a_jour=true ; un enregistrement du générateur sans rien toucher laisse lignes et totaux strictement identiques (hash) et ne change ni version ni statut.
- Cohérence internes des 4 vues sur le nombre de panneaux : atelier, lignes du devis, PDF et JSON public donnent le même entier dans tous les états testés (seuls kWc/production divergent, voir ANON-01/06).

## 7. Verdicts de réfutation (phase 5)

- **R3 lentilles** (code / exécution / chiffres-client, 3 à 2 par lane, réfuteur opus sur ATL/PUB/JUM) : 0 réfutation sur 375 constats × 2-3 lentilles, 88 « partiels » corrigés, 65 gravités abaissées, 1 « déjà suivi » (CALX44 → D-ACAL-16). **Réfuteurs non calibrés** (METHODE §B 5 : 0/375 n'est pas un taux crédible) : ils ont servi d'éditeurs, pas de preuve.
- **Porte empirique** : les 84 constats S1/S2 seulement lus ont été EXÉCUTÉS — 69 confirmés, 9 partiels (portée corrigée : ENT-G1-03, SIM-G1-09, SIM-G2-04, CYC-12, PUB-05, PUB-G1-01, PUB-G2-04, LIV-15, NET-04), 6 par grep, 0 réfuté. Run Playwright : 26/30 bloquants reproduits, 4 partiels (ATL-06, ELE-03, JUM-01, PUB-05).
- **Fable #1** (familles critiques, 25 S1) : 18 confirmés S1, 7 reclassés S2 (066, 075, 078, 087, 113, 116, 118), 2 scissions (022, 066), 1 fusion (096 + 097), 13 notes d'ordonnancement appliquées.
- **Audit de l'audit** : non joué (corpus QJR5 de 14 défauts, METHODE §B 5) — écart déclaré, à faire au premier `vérifie ACAL`.


## 8. Rapport (phase 6)

**Ce qui a été vérifié.** Les neuf étapes P1-P9 du parcours, sur les trois contrôles demandés par Reda
(modifiabilité / propagation, une fonction par geste, code propre) et les leçons A-G : 410 constats bruts →
146 constats par cause racine (25 S1 → 18 après Fable #1, 53+7 S2, 68 S3 ; 123 CONFIRMÉS par exécution —
Playwright, porte empirique ou sonde —, 23 PLAUSIBLES promus seulement avec leur test rouge comme oracle).
Les défauts majeurs reproduits en direct : l'atelier efface en silence, au premier « Enregistrer » sans
retouche, le champ au sol, l'ombrage, la consommation, la couche électrique, les pans inactifs et les choix
épinglés ; les onglets du rail réécrivent le document entier depuis une copie périmée ; « Générer le devis »
chiffre la conception parente au lieu de la variante retenue ; un devis ENVOYÉ corrigé en 3D depuis ventes ne
remonte jamais au calepinage, puis « Resynchroniser » repousse l'ancienne conception ; le badge « à jour »
compare la mauvaise copie ; une fenêtre météo pluriannuelle publie la SOMME des années comme « annuel » ; une
société sans réglages publie un PR de 100 % avec 22 pertes omises ; l'horizon enregistré par l'écran fait
échouer la simulation ; le schéma unifilaire plante (500) dès qu'une conception est calculable ;
`export-csv` sert le mauvais fichier ; `note-calcul.pdf` répond 400 après toute simulation réelle. C5 :
aucune fuite inter-sociétés (52/52 routes GET et toutes les écritures croisées en 404) ; trois contournements
intra-société (vue restreinte, gouvernance des réglages, oracle d'existence).

**Décisions.** 28 décisions fondateur D-ACAL (deux séries de questions, 04/10) + ~40 défauts conventionnels
appliqués sans question (règles maison) — en tête du groupe dans `docs/plans/PLAN_AUDIT_CALEPINAGE.md`.

**Tâches.** 351 tâches ACAL routées par propriétaire selon `docs/ownership.yml` (il prime sur `unites.yml`, METHODE §D.3 ; `check_ownership.py` vert) : CALEPINAGE 271 · TRANSVERSE 44 · DEPLOY 14 · DEVIS 12 · ANALYSE 4 · MOTEUR 2 · LEAD 1 · CHANTIERS 1 · SECURITE 1 · WEB_PLAN 1 ; jalons M0 21 · M1 47 · M2 249 · M3 34 ; priorités P0 45 · P1 134 · P2 152 · P3 20 ; modèles 268 sonnet · 78 opus · 5 haiku ; UNE tâche d'acceptation live finale (ACAL351). Première garde v2 réservée (clauses §C.2 dans `check_taches_cablage.py`) incluse, routée vers PLAN_AUDIT_DEPLOY. Groupe inséré APRÈS le Groupe SPL (découpe des fichiers-dieux, arrivé sur main pendant l'audit) dans les fichiers existants ; `docs/PLAN2.md` : CALX44 → SKIP (D-ACAL-16), CODEMAP §10 + empreinte rafraîchis.

**Coût.** ~90 exécutions d'agents (au-dessus de la fourchette L3 « ~15-35 » de go-deep : la consigne de Reda
exigeait 10 lanes + 2 lentilles + run live + rédacteurs + 3 passes Fable, et une limite d'usage hebdomadaire a
interrompu R3 à mi-course — 25 agents relancés en reprise) : R1 4 (sonnet ×3, haiku ×1) ; R2/R3 56 (lanes
opus ×3 / sonnet ×7, chercheurs de manques sonnet, vérificateurs opus ×3 + sonnet) ; live 3 + C5/anon 3
(1 opus) ; porte empirique 6 sonnet + regroupement 1 opus ; rédacteurs 10 (opus ×6, sonnet ×4) ; patch 1 opus ;
**Fable ×3** (familles critiques S1, complétude, revue du groupe — lignes au DONE LOG de PLAN_AUDIT_CALEPINAGE).
Jetons de sous-agents mesurés : ~1,2 M (R1) + ~25,7 M (R2/R3, deux exécutions) + 0,8 M (live) + 0,75 M (C5/anon)
+ 2,1 M (porte + regroupement) + 5,2 M (Fable #1 + rédacteurs) + 0,6 M (patch) + 0,5 M (Fable #2) + 0,4 M
(Fable #3) ≈ 37 M.

**Ce qui n'a PAS été couvert.** Voir §4 (non exécutés) et l'en-tête du groupe (« Non couvert ») : données de
production, tuiles MapTiler réelles, 3D publique rendue, C14, calibration des réfuteurs, ~166 fonctions
gelées inventoriées sans rejeu individuel.

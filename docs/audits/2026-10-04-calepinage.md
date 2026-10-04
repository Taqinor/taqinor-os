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

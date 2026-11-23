# Coutures de la vague D — ce que les lanes ont laissé entre deux fichiers, et ce que le rejeu en direct a vu

Trois lanes de couture, sur la branche LOCALE d'intégration (`git checkout -q -B <ta branche> claude/calpinage-module-l5-aadbde`,
tête « Pli de la lane taille-auto (vague D) » ou plus récente). Règles : `docs/audits/l5-calepinage/T2/brief-lanes.md`
(en entier) et « Communs à toutes les lanes » de `docs/audits/l5-calepinage/controles/lanes-vague-D.md` (décisions du
fondateur, gardes qui ont rougi la CI, interdits). Un commit par point, test rouge d'abord dans le module de test
existant ; aucun `git push` ; aucun `docker compose` ; tu n'édites ni `docs/plans/*`, ni `docs/CODEMAP.md`, ni
`docs/openapi-schema.yml`. Chaque point cite sa source : LIS-la (rapport de lane ou de vérificateur) avant d'y toucher.
Sources : rapports des lanes dans les fichiers d'événements `…/scratchpad/l5b/T2-lane-*.jsonl` (lignes `demande-croisee`),
rejeu en direct `docs/audits/l5-calepinage/T3/T3-VAGUEC2.md` + `registre/evenements/T3-T3-VAGUEC2-cv.jsonl` +
`registre/constats/T3-T3-VAGUEC2.jsonl`, critique `docs/audits/l5-calepinage/T3/critique-vague-C1.md`.

## Lane « couture-devis » (`apps/crm`, `apps/ventes`) — branche `lane-l5d-couturedevis`

1. **Golden HTTP du CRM** — `apps.crm.tests_scission_golden` (`ScissionGoldenHttpTests`, GET leads et détail) est rouge
   depuis ALEA67 (la fiche d'un lead résidentiel dit maintenant « facture hiver, ville ») : recapture par la procédure
   du dépôt (`UPDATE_GOLDEN=1`, voir `plan-drain-ci-bug-classes.md` entrées 22 et 36), après avoir LU le diff pour
   vérifier qu'il ne porte que ce changement voulu.
2. **ADEV122, branchement du devis C&I** — demande croisée de la lane regles-communes (`T2-lane-reglescommunes.jsonl`) :
   `apps/ventes/domain/etude_ci.py` pose le froid du site (`core/electrique/types.py::froid_de_dimensionnement`, lu par
   le sélecteur `apps/calepinage/selectors_devis.py::froid_dimensionnement_au_point`) et le passe à
   `combiner_onduleurs` ; l'hypothèse `temperature_froid_c` sort avec les autres. NOUVEAUX calculs seulement ; mesure
   et dis quels cas des fixtures changent (attendu : 715 Wc sur Huawei 200-1000 V à Casablanca, 20 → 21 modules) ;
   goldens recapturés par la procédure si un cas change. Le résidentiel reste à −5 °C : ne le branche pas (tâche à part).
3. **ADEV125, le devis supposé « basse tension » est marqué estimation au document** — demande croisée de la lane
   devis-auto-ci (`T2-lane-devis-auto-ci.jsonl`) : le bloc d'étude rangé ne porte pas `sous_reserve_visite`, donc le
   PDF ne dit pas « estimation ». Pose la valeur dans le bloc (aucun texte nouveau au PDF : le marquage existant
   « estimation sous réserve de visite » s'affiche de lui-même). Si le PDF doit changer : arrête-toi et dis-le.
4. **ALEA67 à l'écran** — la fiche du lead dit « Devis non prêt » sans NOMMER ce qui manque quand c'est la ville
   (rejeu T3-VAGUEC2, point 13) : le libellé du champ manquant (« ville ») est affiché là où la fiche liste déjà les
   manques (`frontend/src/features/crm/workspace/devisAutoRequis*`), et un lead dont la ville redevient reconnue
   redevient prêt (test).
Avant ton rapport : par `tester.sh` (nom court `couturedevis`) les modules de test touchés de `apps.crm` et
`apps.ventes` + les goldens du moteur ; `node --test "src/features/crm/**/*.test.mjs"` depuis `frontend/`.

## Lane « couture-calepinage » (`apps/calepinage` serveur + l'étape Résultats) — branche `lane-l5d-couturecalepinage`

1. **ACAL1987, fin** — demandes croisées de la lane pertes-simulation (`T2-lane-pertes-simulation.jsonl`) :
   `services/electrique.py::enregistrer_entree` appelle `lancer_simulation_automatique` en `on_commit` (c'est le
   dernier geste d'une pose complète) ; `GET resultat/` sert l'état `selectors.simulation_automatique_en_cours` et les
   manques (clé au contrat `calepinage_resultat.json` dans le même commit) ; `EtapeResultats.jsx` affiche
   « Simulation en cours… » sans clic puis le résultat, et « Il manque … » quand la pose est incomplète.
2. **ACAL746, fin** — demande croisée de la lane ombrage-p90-nasa (`T2-lane-ombrage-p90-nasa.jsonl`) : brancher
   `services/nasa_power.py::ClientNasaPower.comparaison_horizontale` dans le bloc météo de la simulation
   (`meteo.comparaison_nasa_power`, PVGIS reste la source du chiffre), au contrat du bloc météo, et l'afficher d'une
   ligne dans l'onglet où l'étude montre déjà la comparaison à PVGIS. Aucun appel réseau pendant les tests ; repli
   silencieux si le service ne répond pas (la simulation ne doit JAMAIS échouer à cause de lui).
3. **ACAL1755, moitié rapport** — demande croisée de la lane ecrans-d (`T2-lane-ecransd.jsonl`) : le rapport d'étude
   (`services/rapport/production.py`, bloc `production-ecart-devis`) et la mention servie `MENTION_ECART_DEVIS`
   (`services/electrique.py`) disent encore « Production imprimée au client = moteur du devis (D-ACAL-6) ». Décision
   D-ACAL-86 / 96 : un seul chiffre quand ils sont égaux ; sinon les deux, nommés, et la phrase « le devis envoyé
   n'est pas modifié : une révision est proposée ». Échantillon de contrat et golden recapturés dans le même commit.
4. **Le rapport panneaux / onduleur dit sa borne basse** — rejeu T3-VAGUEC2 : « 0,99 pour 1,35 au plus (règle du
   devis) » est marqué « à régler » sans raison dite. Le verdict (`services/ratio_devis.py`) dit la borne franchie
   (« 0,99 : sous la borne basse de la règle du devis (N) ») ; si la règle du devis n'a PAS de borne basse, 0,99 est bon
   — lis la règle (sélecteur de `apps/ventes`) avant de trancher, et dis ce que tu as trouvé.
5. **Le module par défaut de l'atelier est celui du devis** — rejeu T3-VAGUEC2 (constat « module d'essai posé par défaut
   au lieu de celui du devis ») : quand un devis est lié, le module servi à l'atelier (design-context / entrée
   électrique) est celui de la conception retenue du devis (`apps/ventes/selectors_calepinage.py::
   conception_retenue_du_devis`), une désignation manuelle restant permise. Côté serveur seulement.
Avant ton rapport : par `tester.sh` (nom court `couturecal`) les modules de test touchés ; `npx vitest run` sur
`EtapeResultats.test.jsx` et le test de l'onglet touché ; `node --test "src/features/calepinage/*.test.mjs"`.

## Lane « couture-ecran » (écrans du calepinage, sauf `EtapeResultats.jsx`) — branche `lane-l5d-coutureecran`

1. **ACAL1951 à l'écran** — rejeu T3-VAGUEC2 point 7 : la cible dit de quel devis elle vient mais ne NOMME pas
   l'option (« sans batterie » / « avec batterie »), et « au devis » disparaît après remplissage (« 8 posés / 7 cible ») :
   la note garde « 8 posés, 7 au devis DEV-… (option …) ». La note vit dans `apps/web/src/scripts/roofPro11/tailleAuto.ts`
   / `optimizer.ts::syncNeedControl` (lis le commit ACAL1331) et l'option est servie (`cible.option`, ACAL1951).
2. **ACAL1952 à l'écran** — point 8 : en Guidé, l'étape Électrique ne montre nulle part « Repris du devis <référence> »
   (le bloc existe dans l'onglet Expert « Matériel électrique ») : la mention apparaît dans le panneau de l'étape, avec
   l'écart quand une saisie contredit le devis.
3. **ACAL1958** — point 12 : le bouton de pied de l'étape Résultats mesure 330 × 104 en bas de défilement au lieu du
   gabarit 340 × 52 des autres étapes : CSS seulement (`frontend/src/styles/calepinage/54-etape-resultats.css`), sans
   toucher `EtapeResultats.jsx` (une autre lane l'édite).
4. **Restes S3 du rejeu** (`registre/constats/T3-T3-VAGUEC2.jsonl` et `T3-T3-VAGUEC.jsonl`) : l'en-tête de pose
   périmé après un changement de module ou un retrait ; les tuiles « Affiner ma consommation » qui se chevauchent ;
   les toasts qui masquent la barre du soleil. Un commit par point réellement corrigé ; « impossible » sinon.
CSS par jetons `--cal-*`, aucune couleur en hexadécimal, aucun `z-index` en dur ; tests qui exécutent le composant ;
listes figées des tests de logique pure mises à jour ; ne grossis aucun fichier de 2 000 lignes ou plus. Avant ton
rapport : `npx eslint`, tes tests vitest, `node --test "src/features/calepinage/*.test.mjs"`, et pour le moteur de
dessin (jonction `apps/web/node_modules`) : `npx vitest run src/scripts/roofPro11 tests/estimatorPreviewPro11.test.ts`
ET les deux suites runtime par la config jetable `…/scratchpad/PR2/vitest.orchestrateur.mjs` RECOPIÉE avec la racine
de TON worktree (`tests/estimatorRuntimePro10Pro11.test.ts tests/userJourneyPro11.test.ts`).

# Vérifie ACAL — contre-visite des correctifs de l'unité D3 « calepinage », 20/11/2026

<!-- verifie | groupe: ACAL | pct: 99 | ecarts_s1_s2: 1 | faits: 375 -->

Commande `loop audit` (20/11). La contre-visite du 10/11 (`docs/audits/2026-11-10-calepinage-verifie.md`) laissait un écart
S2 du 01/11 ouvert : les zones de toiture (pente, orientation) non relues à l'ouverture (ACAL366, alors bloquée sur sa
preuve en direct). `audit_registre.py --du` la déclare due : 375 tâches cochées sur 376, « écarts S1-S2 du 2026-11-10 tous
cochés ». Rien n'a été construit ni déployé ; aucune base, aucun conteneur, aucune production n'a été lu.

## 0. Préconditions

- **SHA.** `origin/main` = `5a77c93d9` (PR #1503). Branche de claim : `verifie-acal-2011`.
- **Registre.** D3 `calepinage`, groupe ACAL, 375 tâches cochées sur 376. Reste ouverte l'acceptation unique ACAL351 (et
  ACAL275, bloquée, plan analyse).
- **Échantillon : les 4 tâches cochées depuis le 10/11 et jamais relues** (METHODE §C.4-6) : ACAL366 (porte l'écart S2),
  ACAL367, ACAL369, ACAL378.
- **Méthode.** Un vérificateur frais (opus / high) : commits, code servi, tests nommés, enregistrements d'acceptation
  (`docs/audits/acceptation/ACAL/`, run 44658212928 pour ACAL378), jumeaux par grep. Les vitest nommés ont été joués dans
  une copie jetable du dépôt (dépendances de la copie principale liées) : `userJourneyPro11.test.ts` + `horizonEngine.test.ts`
  24/24, `ToitureDesign.acalGenererLead.test.jsx` 2/2 ; puis rejoués chaque correctif retiré (copie seulement). Deux sondes
  hôte neuves exécutent la vraie fonction sous node.

## 1. Verdicts

| Tâche | Verdict | Cause | Commits | Le test casse si on revient en arrière | L'acceptation affirme la clause |
|---|---|---|---|---|---|
| ACAL366 | **partiel** | Écart d'origine fermé ; le correctif écrase la saisie non enregistrée des autres pans (C-ACAL-VER4-400, régression) et ne place pas les champs de provenance où la tâche les demandait (C-ACAL-VER4-401) | `16c8a4c8c`, `a1eb40c61` | oui : branche `'zones'` retirée ⇒ 2 tests rouges | oui : `PA2.3-ACAL366-pente-section` (carte vivante, z1 35° avec sa source, z2 intact, allée technique identique, 35° relu à la réouverture) |
| ACAL367 | ok | Production réémise seulement à entrées d'ombrage identiques et signature conforme (D-ACAL-VER2-1) | `7b281bc9f`, `fb7f54ebf`, `cd6ff5ec3` | oui : condition relâchée ⇒ 2 tests rouges | oui : `annualKwh` enregistré baisse du facteur de la carte (8 846 → 8 142, run 44658212928) |
| ACAL369 | ok (déjà visible en pratique) | Depuis ACAL368 le serveur envoie aussi `detail` : l'écran affichait déjà le motif par cette branche ; la branche `refusServeur` n'est couverte que par le test | `5d6770dae`, `842676199` | oui : branche retirée ⇒ 1 test rouge (cas sans `detail`, corps tiré du contrat) | oui, et la trace le dit (`2026-11-10-rejeux-final/ACAL369.txt` : affichage par `detail`) |
| ACAL378 | ok | Cible atteinte sur le runner : atelier ×0,9204, simulation ×0,9198 (0,06 point) | `9fb40985e`, `2e0ea6835`, `9ff28f56c`, `f30e16322` | en partie : le test appelle `hourlyHorizonFactors` avec le profil directement ; retirer l'argument `prod` dans `shadingUi.ts` (le câblage de l'atelier) laisse les 24 tests verts | oui : journal du run 44658212928 « atelier 8846.29 → 8142.02 ; simulation 12032.1 → 11066.6 » ; la spec n'affirme que `ecart1 ≤ ecart0 + 0.01`, les chiffres journalisés tiennent aussi les 2 points |

**Écart S2 d'origine (ACAL366) : fermé.** `apps/web/src/scripts/roofPro11/hydratation.ts::hydratationDeSection` a la branche
`'zones'`, appliquée par `apps/web/src/scripts/roofPro11/hydratation.ts::appliquerZonesSection` ; `builderApi.appliquerSection`
(`apps/web/src/scripts/roof-tool-pro11.ts`) resynchronise les contrôles et relance `recalc()` ;
`apps/web/src/scripts/roofPro11/prefill.ts::reconcilierAvecDocumentRelu` ne réémet plus la production enregistrée quand pente
ou orientation ont changé. Autres ouvertures : mode lead sans rail ni section poussée ; variante en lecture seule ; mobile
non vérifié.

## 2. Sondes

| Sonde | Tâche | Verdict | Observé (hôte, `5a77c93d9`) |
|---|---|---|---|
| `C-ACAL-VER4-400.py` (neuve) | ACAL366 (régression) | **REPRO** | vraie fonction sous node : après une décision IGN poussée, `{actif: 15, z2: 20}` au lieu de 30 / 40 ; `compare_au_relu_avant_ecriture: false` ; rejeu vitest avec un vrai démarrage de devis : `serializeLayout().zones[0].pitchDeg` = 15 après 30° saisi |
| `C-ACAL-VER4-401.py` (neuve) | ACAL366 (placement) | **REPRO** | pan absent du document relu : source, précision et suggestion stockées nulle part ; zone émise `{facingAzimuthDeg: 200}` |
| Sondes du 01/11 | origine | non rejouées | demandent Django |

## 3. Écarts retenus

| C-id | Tâche d'origine | Grav. | Écart | Sonde | Tâche |
|---|---|---|---|---|---|
| C-ACAL-VER4-400 | ACAL366 (régression) | **S2** | Une section « zones » poussée par « Saisie de la pente » (enregistrer une pente, décider une suggestion IGN) ou par le panneau de relevé écrit la pente et l'orientation ENREGISTRÉES sur chaque pan vivant sans les comparer au document relu : la saisie non enregistrée des autres pans est défaite, et l'enregistrement suivant écrit l'ancienne pente (production et devis) ; curseur et libellé non resynchronisés (`apps/web/src/scripts/roofPro11/hydratation.ts::appliquerZonesSection`) | `C-ACAL-VER4-400.py` (REPRO) | ACAL379 |
| C-ACAL-VER4-401 | ACAL366 (placement) | S3 | Source et précision d'orientation et suggestion de pente écrites seulement dans le document relu, jamais rafraîchi : perdues pour un pan dessiné en séance, effacées par l'enregistrement complet suivant (même fonction) | `C-ACAL-VER4-401.py` (REPRO) | ACAL380 |
| C-ACAL-VER4-402 | ACAL378 (jumeau) | S3 | Le dérate d'ombrage proche de l'atelier garde la part diffuse fixe de 0,25 et la cloche de repli ; mesuré par le commit d'ACAL378 (×0,815 contre ×0,914 au moteur), « à classer », jamais déposé (`apps/web/src/lib/shadingEngine.ts::hourlyShadeFactors`) | STATIQUE (+ mesure du commit `9fb40985e`) | ACAL381 |

**Pourquoi ces gravités.**
- **VER4-400 (S2).** Perte silencieuse d'une saisie qui porte un chiffre client : la pente enregistrée ensuite est l'ancienne,
  donc la production et le devis du pan aussi. Le geste est ordinaire (enregistrer la pente d'un pan, accepter une
  suggestion IGN). Pas S1 : la valeur écrasée est la valeur enregistrée précédente, visible à la scène, et rien ne part au
  client sans « Générer le devis ».
- **VER4-401, VER4-402 (S3).** Provenance perdue (aucun chiffre) ; écart d'affichage de l'atelier, le chiffre client restant
  celui du devis (D-ACAL-6).
- **Pas de S1.**

**Routage.** `check_ownership.py --owner-of` : calepinage pour les trois (`apps/web/src/scripts/roofPro11/`,
`apps/web/src/lib/shadingEngine.ts`).

## 4. Optionnel (non déposé)

- Aucun test unitaire ne vérifie que `apps/web/src/scripts/roofPro11/shadingUi.ts` passe le profil de production au calcul
  d'horizon : seul le parcours PA2.5 en direct l'attrape.
- `signatureOmbrage` ne code pas la formule du dérate : les documents enregistrés les 19-20/11 avec un horizon gardent la
  production de l'ancienne règle jusqu'à leur prochaine modification (gardé ainsi par ACAL31).
- Les parts par bande (0,57 / 0,43 / 0,27) viennent de Casablanca à 15° plein sud ; autres latitudes et inclinaisons non testées.
- Chiffre client : `backend/django_core/apps/ventes/etude.py::_zone_shading_loss` lit la cascade du calepinage quand elle
  existe ; sinon `shading12x24` et `zone['horizon_profile']`, clé que le document v2 ne porte pas (l'horizon est à la racine,
  `horizonProfile`). Atteinte de ce repli en pratique non vérifiée : mérite une sonde au prochain passage moteur.
- Curseur de pente jamais resynchronisé au `loadArea` (antérieur) ; dans ACAL356, « économies 0 → 0 » rend la vérification
  `eco1 ≤ eco0` triviale.

## 5. Couverture et sortie de cycle

- **Couvert.** Les 4 tâches cochées depuis le 10/11 : commits, code servi, tests nommés joués et rejoués correctif retiré,
  enregistrements d'acceptation, jumeaux par grep ; deux sondes neuves exécutant la vraie fonction.
- **Non couvert.** Aucun rejeu navigateur ni API sur pile ; ouverture sur mobile ; les sondes Django du 01/11 ; les 371
  autres tâches cochées (relues par les contre-visites précédentes) ; l'acceptation ACAL351 reste ouverte.
- **Sortie de cycle.** L'écart S2 du 01/11 est fermé, mais son correctif ouvre un S2 nouveau (ACAL379). Le groupe reste
  « construit » ; compteur des `vérifie` consécutifs à zéro S1-S2 : **0**. Contre-visite d'ACAL379 une fois cochée.

## 6. Coût

H0 S0 O1 F0 · jetons sous-agents ≈ 0,28 M (un vérificateur opus seul). Aucun appel Fable : aucun S1.

# Vérifie ALEA — seconde contre-visite de clôture du groupe lead (J1a), 02/11/2026

Commande « vérifie ALEA » (METHODE §C.4.2, skill audit §5). Le groupe compte **51 tâches cochées sur 51** (ALEA1-33,
ALEA37-44, ALEA46-55 ; l'acceptation ALEA26 est cochée depuis le 28/10). La première contre-visite de clôture
(`docs/audits/2026-10-10-lead-verifie.md`) était à zéro S1-S2 et son écart S3 (ALEA46) est coché. Celle-ci est la
seconde : à zéro S1-S2, le groupe sort du cycle (METHODE §C.4.3). `audit_registre.py --du` ne la marque pas due (la règle
ne compte pas le second passage) ; elle est jouée à la demande de l'orchestrateur de la boucle d'audit.

Pour chaque tâche de l'échantillon, on rapproche le texte, le ou les commits, le test nommé et le code ACTUEL, avec les
7 critères de `docs/claude-memory/lecons-construction-qjr5.md`. La contre-visite n'a rien construit, n'a lancé aucun
deploy et n'a rien lu ni écrit en production.

## 0. Préconditions

- **SHA.** Échantillon tiré sur `origin/main` = `b01fa172f` (PR #1221). Pendant le run `main` a avancé à `ce3356e48`
  (#1220, vague 19 CADV : `apps/crm` dispatch / cadence / sérialiseurs, `crmApi.js`). Le lot 2 a lu le code à
  `ce3356e48` ; le lot 1 a confirmé que `crm/serializers.py` n'y change pas `get_devis_auto`. Aucune tâche échantillonnée
  n'est touchée par la vague (fraîcheur relue par les deux lots).
- **Pile.** Conteneur `erp-agentique-django_core-1` (code du dépôt principal), sondes jouées par le verrou machine
  `sonde-slot.sh`, transaction annulée, base inchangée à chaque fois.
- **Inventaire (déterministe).** 51 tâches ALEA, toutes `[x]`, aucune GATED. Par plan : LEAD, TRANSVERSE, DEPLOY,
  CALEPINAGE, GENERATEUR, WEB_PLAN.
- **Échantillon (graine = SHA `b01fa172fd6f6ecae98837ddb2069bfbf8fa9846`).** Toutes les P0 / S1 (ALEA47, ALEA50), plus
  25 % du reste arrondi au-dessus, tirés par `random.Random(int(sha, 16)).sample` (13 sur 49) : ALEA5, 7, 8, 11, 13, 22,
  28, 31, 32, 37, 39, 51, 55. Total : **15 tâches**.

## 1. Vérificateurs (2 agents frais, opus, effort élevé, lecture seule, même répertoire)

| Lot | Tâches | ok | partiel | régression |
|---|---|---|---|---|
| 1 | ALEA47, ALEA50, ALEA51, ALEA55, ALEA37, ALEA39, ALEA31 | 6 | ALEA50 | — |
| 2 | ALEA5, ALEA7, ALEA8, ALEA11, ALEA13, ALEA22, ALEA28, ALEA32 | 5 | ALEA7, ALEA13 | ALEA32 |
| **Total** | **15** | **11** | **3** | **1** |

Points saillants :

- **ALEA47 (P0/S1, « devis automatique prêt » = ce que le moteur exige).** `apps/crm/devis_auto.py::champs_requis` lit le
  rythme par la règle partagée `ventes.selectors.profil_charge_prerequis_ci` ; 9 cas dans
  `tests_cad166_gating_pro.py::PretEgaleCeQueLeMoteurExigeALEA47`. Sonde C-ALEA-VER2-002 (non-régression) : « conso
  seule » non prêt (contrat, phase, rythme nommés) ; bureau + BT patente + triphasé prêt ; industriel sans rythme non prêt.
  Texte vieilli : la phase a été ajoutée aux manquants par ADEV89, voulu.
- **ALEA50 (P0/S1, « prêt » inclut le catalogue).** Forfaits et postes fixes conformes, bouton bloqué avec motif et liens.
  Mais le refus CORC6 du moteur (ligne chiffrée sans article) n'est pas reporté dans le « prêt » : écart S3 (§4).
- **ALEA51 (chiffres de la réponse `auto`).** Sonde C-ALEA-VER2-003, vrai `POST /ventes/devis/auto/` : `total_ttc`
  515 800,00 = `devis.total_ttc` ; économie 178 141,8 = bloc = PDF (base HT) ; retour 2,4 = payback du PDF ; 115,02 kWc.
- **ALEA5, ALEA8, ALEA28, ALEA37.** Sélecteur `visite_feu_vert` unique et borné par société, `renvoyer` sous
  `visites_valider`, récap de visite remplacé par bloc balisé (rejoué en Python pur : manuel gardé, revalidation
  octet-identique), trois appelants de la porte de feu vert.
- **ALEA11.** Texte vieilli : le refus de changer le lead d'une visite est un 409 (ENF11), le test le vérifie.
- **ALEA31, ALEA39, ALEA55.** `node --test` : `mobileHome.serveur` 6/6, `LeadDevisPanel.wiring` + `devisAutoKwc.ez5` 17/17.

## 2. Tests et gardes rejoués (hôte, sans base de test Django)

`check_api_shapes.py` OK (337 endpoints), `check_retard_unique.py` OK, `test_check_retard_unique` OK, tests `node --test`
ci-dessus. Les tests Django nommés et les tests vitest (pas de `node_modules` dans le worktree) ne sont pas rejoués
localement : vert de la CI de `main`.

## 3. Sondes

| Sonde | Tâche | Verdict du lanceur | Observé |
|---|---|---|---|
| C-ALEA-VER2-001 | ALEA50 | **REPRO** | 8 forfaits réglés + postes fixes tarifés, sans article de prestation : `catalogue_ci = {pret: True, manquants: []}` ; le moteur nomme 8 prestations orphelines et refuse (« Article manquant au catalogue pour : … ») |
| C-ALEA-VER2-002 | ALEA47 | ÉCART (repro faux = non-régression) | conforme (§1) |
| C-ALEA-VER2-003 | ALEA51 | ÉCART (repro faux = non-régression) | conforme (§1) |
| C-ALEA-VER2-101 | ALEA13 | **REPRO** | « DELETE visite -> 204 ; visite existe=False ; media existe=False ; attachment du lead existe=True » |

## 4. Écarts retenus

| Tâche | Constat | Écart de | Grav. | Cause | Preuve | Fichier de plan |
|---|---|---|---|---|---|---|
| ALEA56 | C-ALEA-VER2-001 | ALEA50 | S3 | L6 jumeau oublié (refus CORC6 non reporté dans le « prêt ») | sonde REPRO | `PLAN_AUDIT_TRANSVERSE.md` (`@atomique: devis, lead`) |
| ALEA57 | C-ALEA-VER2-102 | ALEA7 | S3 | L4 appelants oubliés (refus serveur muet à l'écran) | lecture du chemin unique | `PLAN_AUDIT_LEAD.md` |
| ALEA58 | C-ALEA-VER2-101 | ALEA13 | S3 | L6 jumeau oublié (`DELETE` de visite) | sonde REPRO | `PLAN_AUDIT_LEAD.md` |
| ALEA59 | C-ALEA-VER2-103 | ALEA32 | S3 | régression par AIC31 (L6) : 7ᵉ définition du retard | fonction extraite, Python pur | `PLAN_AUDIT_LEAD.md` |
| ALEA60 | C-ALEA-VER2-103 | ALEA32 | S3 | L5 garde trop étroite | lecture de la garde | `PLAN_AUDIT_DEPLOY.md` (`@after: ALEA59`) |

Gravités :

- **ALEA56.** Le bouton « Devis automatique » reste actif et le clic rend un 409 qui nomme les postes. Aucune sortie
  client fausse : S3.
- **ALEA57.** Le serveur refuse bien. Seul le message manque à l'écran : S3.
- **ALEA58.** Route API sans écran. La photo reste attachée au lead, aucune donnée n'est perdue : S3.
- **ALEA59.** Alerte interne servie à l'assistant les jours non ouvrés. Badge, cockpit et filtres restent justes : S3.

Propriétaires vérifiés par `check_ownership.py --owner-of` :

- `apps/ventes/selectors.py` → devis ;
- `apps/crm/tests_devis_auto.py`, `apps/visites/**`, `apps/crm/views_assistant.py`, `frontend/src/pages/visites/**` → lead ;
- `scripts/**` → deploy.

Avant le dépôt, un grep des tâches ouvertes de tous les plans (`_alertes_lead`, `catalogue_ci_pret`,
`VisiteQualificationForm`, `check_retard_unique`, `perform_destroy`) n'a rien trouvé : ni AARG1-58 ni CADV ne couvrent
ces écarts.

**Constats S1-S2 : 0.** Pas de seconde lentille ni de critique Fable (réservées aux S1 restants).

## 5. Optionnel (non déposé)

- **ALEA51.** Le bandeau affiche toujours l'économie HT sans le dire, alors que le PDF imprime le TTC quand la TVA n'est
  pas récupérable (`synthese.py`, `base_economie`). Le cas TTC n'a pas été sondé.
- **ALEA50.** `catalogue_ci` n'est servi qu'au GET détail : la réponse du PATCH d'autosave rend `catalogue_ci: null`, et
  la fusion côté écran ne garde pas l'ancien bloc. Le bouton pourrait se réactiver jusqu'au GET suivant. Non vérifié en
  direct.
- **ALEA32.** `seuil_retard`, qui sert aux filtres, ignore les absences personnelles du responsable. Le badge et le cockpit
  les lisent : les deux divergent pour un commercial en congé. Ce partage était prévu par le texte de la tâche.
- **ALEA31.** Une route d'accueil mobile déjà mémorisée n'est pas reprise.
- **ALEA28.** La docstring de `receivers_cadence._retour_lead_on_visite_validee` dit encore « APPENDU si absent », et les
  balises `[Récap visite n°X]` sont visibles en clair dans la fiche.
- **ALEA37.** Les tests passent par le service `retenir_variante` et non par `POST /retenir/`. C'est équivalent : le
  service est le seul chemin d'écriture.

## 6. Couverture et non-couvert

- **Couvert.** 15 tâches sur 51 (toutes les P0/S1 + 25 %). Commits, tests nommés, code actuel ; 4 sondes jouées (2 REPRO,
  2 non-régressions).
- **Non couvert.**
  - Les 36 autres tâches cochées.
  - Les tests Django et vitest de l'échantillon ne sont pas rejoués localement (§2).
  - La preuve en direct de l'écart ALEA57 (étape P3.5) n'est pas jouée : il est établi par lecture du code.
- **Statut du registre.** Deuxième contre-visite consécutive sans écart S1-S2 : le groupe ALEA **sort du cycle**
  (METHODE §C.4.3). ALEA56-60 (S3) restent à construire.

## 7. Coût

- 2 vérificateurs opus (effort élevé) : environ 0,44 M de jetons. Un premier lancement du lot 1 a été arrêté au début,
  sous la consigne de charge machine, puis rejoué. Aucun appel Fable.
- Orchestrateur : échantillon, revue, contrôle des constats, rédaction des 5 tâches.

<!-- verifie | groupe: ALEA | pct: 91 | ecarts_s1_s2: 0 -->

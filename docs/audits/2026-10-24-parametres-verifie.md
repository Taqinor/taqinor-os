# Vérifie APAR — contre-visite de clôture du groupe parametres (X3), 24/10/2026

Commande `vérifie APAR` (METHODE §C.4.2, skill audit §5), lancée par `loop audit` (3ᵉ itération du 24/10, après ASAV et
ACRM). `audit_registre.py --du` liste APAR en clôture (≥ 95 % : 63/65). C'est la deuxième contre-visite du groupe, après
celle de mi-parcours du 11/10 (`docs/audits/2026-10-11-parametres-verifie.md`).

Pour chaque tâche de l'échantillon, on rapproche le texte, le ou les commits, le test rouge nommé et le code de `main` avec
les 7 critères de `docs/claude-memory/lecons-construction-qjr5.md`. Chaque écart S1-S2 est prouvé par une sonde exécutée en
transaction annulée. Les écarts confirmés sont déposés en tâches v3 dans le plan du propriétaire des fichiers. La
contre-visite n'a rien construit, n'a lancé aucun deploy et n'a rien lu ni écrit en production.

## 0. Préconditions

- **SHA.** `origin/main` = `b3c7e4065` (PR #1021), re-fetch en début d'itération. Branche de claim : `verifie-apar-cloture`
  (commit vide `122a75972`, poussé).
- **Registre.** X3 `parametres`, groupe APAR, statut calculé `vérifié` avant ce dépôt (63/65, 96 %, mi-parcours sans écart
  S1-S2). Tâches réparties dans `PLAN_AUDIT_PARAMETRES.md`, `PLAN_AUDIT_TRANSVERSE.md`, `PLAN_AUDIT_DEPLOY.md`,
  `PLAN_AUDIT_STOCK.md`.
- **Inventaire (déterministe).** 68 tâches APAR, 63 `[x]`. Restent : APAR44, APAR52, APAR56 `[BLOCKED: acceptation]`, APAR45
  (acceptation en direct du groupe), APAR54.
- **Échantillon (graine = SHA `b3c7e40653b218d1cfa78956767761a6cc76b390`).** Les P0/S1 cochées (APAR3, APAR4) et 25 % du
  reste tirées par `random.Random(int(sha, 16)).sample` (15 sur 61) : APAR5, 6, 10, 12, 16, 20, 21, 23, 25, 46, 49, 55, 63,
  65, 67. Total : **17 tâches**.
- **Pile des sondes.** Conteneur jetable `sonde-verifie-asav` rafraîchi au code de `main` (`b3c7e4065`, `git archive`).
  Base de démo partagée : 5 migrations en attente (crm 0138/0139, stock 0172 ×2 et 0173), sans lien avec les sondes (aucune
  colonne de `Produit` ajoutée), non appliquées. Transactions annulées : base inchangée, 0 mail, 0 tâche Celery.

## 1. Vérificateurs (6 agents frais, opus, effort élevé, lecture seule, même répertoire, 2 à 4 tâches chacun)

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **9** | APAR3, 4, 5, 6, 20, 23, 55, 63, 67 |
| partiel | **7** | APAR10 (S3 ×2), APAR12 (S4), APAR16 (S3 ×2), APAR21 (S3), APAR46 (S2), APAR49 (S1 + S3 ×2), APAR65 (S2 + S3) |
| régression | **1** | APAR25 (S3 : l'opposition ajoutée ensuite par ACRM17 à l'exécution n'a pas été reportée dans la simulation) |
| non-fait / faux / déjà-présent | 0 | — |

Points saillants des tâches ok : APAR3 (la purge d'audit respecte le
plancher de 365 jours sur ses quatre entrées, société forcée côté serveur, trace de purge jamais purgée) ; APAR4 (recalcul à
la main sur 4 tolérances × 27 consommations, barème par défaut et barème personnalisé : 0 écart entre le tarif et le devis ;
jumeaux PDF, `solar.js` et site public alignés) ; APAR5 (toutes les écritures de `parametres` exigent `parametres_modifier`,
route par route) ; APAR63 (garde branchée, mutant rouge).

## 2. Sondes (3 REPRO)

| Sonde | Tâche | Observé (code de `main`, transaction annulée) |
|---|---|---|
| `docs/audits/sondes/APAR/C-APAR-VER-001.py` | APAR46 | un Responsable démarre un workflow puis décide sa propre étape : **200**, étape `approuve` ; aucun champ demandeur sur `WorkflowInstance` |
| `docs/audits/sondes/APAR/C-APAR-VER-002.py` | APAR65 | 250 produits : l'appel du sélecteur de composants des kits (`page_size=1000`) rend **200** lignes, `count` 250, `next` non suivi par l'écran |
| `docs/audits/sondes/APAR/C-APAR-VER-003.py` | APAR49 | société à TVA standard 14 %, onduleur sans `Produit.tva` à 10 000 HT : le lecteur des cartes Éco/Max compte **12 000** TTC au lieu de 11 400 ; 4 produits actifs sans `Produit.tva` dans la base de démo |

La sonde 003 rejoue le lecteur de composition des cartes (`dimensionnement._lire_composition` avec le repli `_TVA_REPLI`
d'`offres_tailles`) sur un vrai produit ; le chemin HTTP complet (devis automatique puis cartes) demande une étude complète et
n'a pas été rejoué.

## 3. Écarts retenus

| Constat | Tâche | Écart de | Crit. | Grav. | Emplacement | Observé → attendu | Sonde |
|---|---|---|---|---|---|---|---|
| C-APAR-VER-003 | APAR79 | APAR49 | C1 | S1 | `apps/ventes/offres_tailles.py::_carte_moteur` | les cartes Éco/Max de la page client lisent la composition avec le repli fixe `_TVA_REPLI` (20) : une ligne sans `Produit.tva` sort à 20 % chez une société à 14 % ; `recommander_taille` et ses 4 appelants ne passent aucun taux → résolveur partagé produit → devis → `tva_standard` (D-APAR-1) | `docs/audits/sondes/APAR/C-APAR-VER-003.py` |
| C-APAR-VER-001 | APAR76 | APAR46 | C5 | S2 | `core/workflow.py::verifier_decideur` | palier seul, aucun demandeur enregistré sur `WorkflowInstance` : celui qui démarre un workflow approuve sa propre étape (aussi par `approuver_en_masse`) → demandeur enregistré et refusé | `docs/audits/sondes/APAR/C-APAR-VER-001.py` |
| C-APAR-VER-002 | APAR78 | APAR65 | C13 | S2 | `frontend/src/pages/stock/KitsStock.jsx::KitsStock` | `page_size: 1000` plafonné à 200 par le serveur, `next` jamais suivi : au-delà de 200 produits, un composant ne peut plus entrer dans un kit → `fetchAllPages` | `docs/audits/sondes/APAR/C-APAR-VER-002.py` |
| C-APAR-VER-004 | APAR75 | APAR65 | C20 | S3 | `scripts/check_page_size_front.py::analyser_source` | la garde exige `results` dans la fonction appelante : un lecteur déclaré au niveau du module passe (KitsStock vert) → tout `page_size` au-delà du plafond sans `next` / `fetchAllPages` | STATIQUE |
| C-APAR-VER-005 | APAR69 | APAR10 | C17 | S3 | `apps/automation/actions.py::_for_each` | les sous-actions d'un « pour chaque » contournent le report au commit : un e-mail part avant le commit de l'émetteur → même chemin que les actions de premier niveau | STATIQUE |
| C-APAR-VER-006 | APAR70 | APAR10 | C17 | S3 | `apps/automation/tests_apar10_frontiere_transaction.py::FrontiereTransactionTests` | depuis APAR51 l'écriture est validée avant SQL : le test de l'erreur SQL n'atteint plus la base et reste vert sans point de sauvegarde → vraie erreur SQL, mutant rouge | STATIQUE |
| C-APAR-VER-007 | APAR71 | APAR25 | C3 | S3 | `apps/automation/simulation.py::_decrire_email` | l'opposition ajoutée ensuite à l'exécution (ACRM17) manque à la simulation (e-mail, WhatsApp) : « partirait » contre « Contact refusé » → même prédicat | STATIQUE |
| C-APAR-VER-008 | APAR72 | APAR21 | C10 | S3 | `apps/stock/tasks.py::recompute_reordering_task` | `STOCK_LOW` est routable et l'émetteur chantiers lit la règle, mais les deux émetteurs stock (réapprovisionnement, surcapacité des zones) prennent leurs destinataires à part : règle acceptée puis ignorée → `resolve_recipients` | STATIQUE |
| C-APAR-VER-009 | APAR73, APAR82 | APAR16 | C2 | S3 | `frontend/src/pages/parametres/LeadsSection.jsx::choisirRespPro` | trois champs à enregistrement immédiat (et `SecuriteTerrainSection`, `ConfidentialiteSection`) ne rafraîchissent pas `updated_at` : l'enregistrement suivant tombe en 409 contre soi-même → profil relu dans le store | STATIQUE |
| C-APAR-VER-010 | APAR74 | APAR16 | C2 | S3 | `frontend/src/pages/parametres/ParametresEntreprise.jsx::ParametresEntreprise` | le bandeau du 409 n'offre aucun rechargement qui garde la saisie (seul F5, qui la perd) → recharger en gardant la saisie | STATIQUE |
| C-APAR-VER-011 | APAR80 | APAR49 | C10 | S3 | `apps/ventes/tests/test_apar49_tva_defaut_societe.py::TvaDefautSocieteTests` | ni `POST /devis/auto/` ni `/from-layout` testés, lignes jamais relues : remettre 20 en dur reste vert → test paramétré sur les 3 points d'entrée | STATIQUE |
| C-APAR-VER-012 | APAR81 | APAR49 | C9 | S3 | `apps/ventes/views/devis.py::DevisViewSet.perform_create` | un devis créé sans taux (`POST /devis/`, `/devis/atomic/`) naît à 20 quel que soit `tva_standard` → défaut serveur `tva_standard(company)` | STATIQUE |
| C-APAR-VER-013 | APAR77 | voisin d'APAR3 | C17 | S3 | `apps/audit/selectors.py::verify_audit_chain` | la vérification repart d'un hash vide : après toute purge (plancher 365 j) elle déclare la chaîne rompue à la première ligne restante → ancrage sur la trace de purge | STATIQUE |

**Constats S1-S2 : 3** (1 S1, 2 S2), tous reproduits. Tâches routées par propriétaire des fichiers : PARAMETRES
(APAR69-71, APAR73-74), DEPLOY (APAR75), SECURITE (APAR76-77), STOCK (APAR72, APAR78), MOTEUR (APAR79), DEVIS (APAR80-81),
CHANTIERS (APAR82).
Elles entrent dans le périmètre de l'acceptation de groupe APAR45, toujours ouverte.

**Réfuté.** Trou proposé par la critique : le demandeur d'une revue GED sans règle de routage approuverait sa propre demande.
Rejoué en transaction annulée : le demandeur reçoit 403 « Le demandeur ne peut pas approuver sa propre demande. », un autre
responsable approuve (200). La règle des quatre yeux est tenue par la vue ; aucune tâche.

## 4. Critique de complétude (1 appel Fable, effort élevé)

Un écart S1 subsistant, la critique Fable unique a été jouée (contexte frais, lecture seule).

- **C-APAR-VER-003 confirmé en S1.** Les cartes sont servies sur la page publique du devis (`public_views.py::_offres_tailles_publique`,
  identiques aux deux niveaux de partage) et à l'écran vendeur. Un taux standard différent de 20 est une configuration
  supportée (réglage éditable, D-APAR-1). Un résolveur de ligne existe déjà (`ventes/serializers.py::_fallback_taux_tva` :
  produit → devis → `tva_standard`) : APAR79 le réutilise et rend le taux obligatoire dans `balayer_tailles` /
  `recommander_taille`. Les autres replis à 20 (`composition.py`, `etape_composer.py`, `pipeline.py`, moteur PDF, `?? 20`
  du front) ne sont atteints que si le devis n'a pas de taux, ce que le défaut du modèle empêche : rattachés au défaut
  serveur d'APAR81, optionnels sinon.
- **Spot-check des « ok »** (APAR4, APAR5) : aucune divergence.
- **Trous.** Rattachés : `approuver_en_masse` (même garde que `decide_step`, APAR76) ; toutes les sous-actions d'un « pour
  chaque » passent par le report au commit (APAR69) ; vérifié à la lecture, l'e-mail est la seule action à effet externe
  (`_server_action` n'évalue que des formules, aucun appel sortant). Réfuté : l'auto-approbation GED (voir §3).
  Optionnels : quatre écrans qui demandent exactement 200 lignes sans suivre `next` (catégories du sélecteur de produit et
  de la création rapide, kits du paramétrage, dossiers d'import) ; le texte CGV qui imprimerait « TVA 20 % » sans taux dans
  les données du moteur (règle #4, non rendu).

## 5. Optionnel (non déposé)

- APAR12 (S4) : `relance_email_j10` n'accepte que les variables de son texte livré, alors que le moteur de relances lui fournit
  tout son contexte ; le refus sort en bandeau et non sous le champ.
- APAR16 : un enregistrement sans modification envoie quand même `PATCH {updated_at}` ; `_conflit_verrou` compare puis écrit
  sans verrou de ligne (deux PATCH strictement simultanés).
- APAR3 : la purge d'audit ne laisse aucune ancre de chaîne (corrigé côté vérification par APAR77).
- APAR4 : `tariff.monthly_bill_residentiel` n'a pas le plancher « facture progressive au seuil » des autres calculs (n'apparaît
  qu'avec un barème personnalisé atypique) ; le champ `tolerance_kwh` est sans effet sur une facture.
- APAR21/23 : `resolve_recipients` (branche utilisateur ciblé) et `tasks._admins_rh` ne filtrent pas `portee` ; la
  réservation d'un balayage est consommée même sans destinataire ; période calculée à la date du serveur.
- APAR25 : d'autres divergences simulation / exécution hors recettes (`_decrire_ticket`, `_decrire_assign`, actions sans
  `statut_prevu`, report hors fenêtre d'APAR26).
- APAR46 : la garde « installations » de `reporting/approbations.py` s'appuie sur `is_responsable`, plus large que le palier.
- APAR55 : l'écran licence affiche les modules d'un palier inactif ; `plan_seeds --mettre-a-jour` et la suppression d'un
  palier ne sont pas journalisés.
- APAR63 : la liste d'exceptions n'est pas mécaniquement « décroissante » ; gestionnaire lié et `apps.get_model` non vus.
- APAR65 : le test-du-test fixe le seuil à la main au lieu de casser la détection.
- APAR49 : replis `?? 20` d'affichage dans le front (`lignesEcran.js`, `ligneFabrique.js`, `DevisLineRow.jsx`, …) ; la facture
  de contrat de maintenance garde un 20 % codé (hors périmètre déclaré de la tâche).

## 6. Couverture et non-couvert

- **Couvert.** 17 tâches sur 63 cochées (les P0/S1 + 25 %), commits, tests nommés (lus ; les gardes `check_page_size_front`,
  `check_notify_point_unique` et leurs tests exécutés en lecture seule), code de `main`, décisions D-APAR-1/2.
- **Non couvert.** Les 46 autres tâches cochées ; aucun aller-retour en direct (APAR45 ouverte ; APAR20 figure dans la dette
  gelée `docs/audits/acceptation/APAR/_dette.yml`).
- **Statut du registre.** Après ce dépôt : 63 cochées sur 79 constructibles (79 %, APAR69-82 ajoutées) ; contre-visite de
  clôture **avec 3 écarts S1-S2** → statut calculé `audité` ; le cycle n'est pas sorti.

## 7. Coût

- 6 vérificateurs opus (effort élevé) : ≈ 1,12 M de jetons, 240 appels d'outil. 1 critique Fable (effort élevé) : ≈ 0,17 M.
  2 rédacteurs opus (plages d'ID disjointes) : ≈ 0,52 M (14 tâches v3 dans 7 plans, propriétaires vérifiés fichier par fichier).
- Orchestrateur : échantillon déterministe, triage des 17 verdicts, lecture du code des 3 écarts S1-S2 et du trou GED,
  4 sondes écrites et jouées (3 REPRO, 1 réfutation), correction du routage d'APAR72 (trois émetteurs, pas un), rédaction.
- H0 S0 O8 F1 · jetons sous-agents ≈ 1,8 M

<!-- verifie | groupe: APAR | pct: 96 | ecarts_s1_s2: 3 -->

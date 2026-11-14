<!-- verifie | groupe: ACEL | pct: 96 | ecarts_s1_s2: 1 -->

# Vérifie ACEL — contre-visite de clôture du parcours PF11 « tâches planifiées », 14/11/2026 (2e passe)

Commande `loop audit` (14/11, soir). Le groupe ACEL a franchi 95 % : 55 tâches cochées sur 57 constructibles. Cette passe
remplace celle du matin (même déclencheur, même jour). Rien n'a été construit ni déployé.

## 0. Préconditions

- **SHA.** `origin/main` = `84561dcd3` (merge de la PR #1411). Branche de claim : `verifie-cloture-1411b`.
- **Registre.** 55 cochées, 8 bloquées « code livré, preuve en direct due » (ACEL3, 4, 8, 13, 31, 36, 42, 46), 2 ouvertes
  (ACEL1, ACEL9).
- **Échantillon.** Les 25 tâches cochées depuis la passe du matin, toutes relues (aucun tirage) :
  - 16 tâches cochées sur l'acceptation du runner : ACEL11, 14, 32, 39, 43, 45, 48, 61, 62, 65, 70, 73, 76, 77, 78, 79 ;
  - les 9 tâches d'écart déposées le matin : ACEL81 à ACEL89.
  Elles couvrent les catégories obligatoires : argent (ACEL43, ACEL70), envoi à un tiers (ACEL73 vers Meta, ACEL78, ACEL88
  webhooks), suppression de données (ACEL61, ACEL87), multi-société (ACEL39, 45, 87, 88, 89).
- **Méthode.** Commits, code sur `origin/main`, tests nommés, appelants et jumeaux lus. Aucune pile, aucun test Django lancé,
  aucun conteneur ni base, aucune production.

## 1. Verdicts

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **24** | ACEL11, 14, 32, 39, 43, 45, 48, 61, 62, 65, 70, 73, 76, 77, 78, 79, 82, 83, 84, 85, 86, 87, 88, 89 |
| partiel | **1** | ACEL81 (deux lectures réseau et le backfill avalent encore la limite douce, §4) |
| non-fait / faux / régression / déjà-présent | **0** | — |

Trois tâches « ok » ont ouvert un vecteur de défaut hors de leur « fini quand » : ACEL11, ACEL62 et ACEL70 (§4). ACEL84 a un
jumeau non traité, signalé « à vérifier » le matin et confirmé ce soir (§4).

## 2. Tests nommés

- Les tests nommés des 25 tâches existent et sont comportementaux. Exemples : la limite douce au 2e lead (ACEL81), le bloqueur
  sans `company_id` d'une autre société (ACEL87), la tentative due d'une société suspendue (ACEL88), le rendu identique à une
  minute d'intervalle (ACEL70), l'alerte d'archive altérée et introuvable (ACEL62).
- Aucun test Django lancé ici. La seule preuve d'un vert est la CI des PR mergées (#1404, #1406, #1411) et l'enregistrement
  d'acceptation `docs/audits/acceptation/ACEL/2026-11-14-d83ed340c.md`. Il couvre les 15 tâches à preuve en direct ; ACEL76 et
  ACEL79 y figurent avec un écart accepté (préchargement antérieur, hors `Files:`).
- ACEL43 et les neuf tâches d'écart portent « Preuve en direct : n/a » avec une raison : aucun enregistrement n'est dû.

## 3. Sondes, calendrier, gardes

- **Garde.** `python scripts/check_beat_active_companies.py` : « OK ». `python -m unittest
  scripts.tests.test_check_beat_active_companies` : 44 tests OK. `authentication/` est lu (ACEL82).
- **Calendrier.** Script hôte joué ce soir (planning lu dans `celery.py`, décorateurs relus par expression régulière) :
  - 127 tâches au planning, toutes définies par un `@shared_task` ;
  - toutes ont une route (deux en forme multi-ligne : interventions récurrentes, traductions) ;
  - fuseau : `CELERY_TIMEZONE` et `app.conf.timezone` valent Africa/Casablanca, avec `CELERY_ENABLE_UTC = False` ;
  - `visibility_timeout` vaut 5 400 s ; le seul `eta` long (relances de signature GED) est déjà borné par lui (AMSG98).
- **Sondes du dossier PF11** (rejouées sur l'hôte) :
  - 001 reproduit encore (`repro: true`, planning à 6 h seulement) ; sa tâche ACEL1 est ouverte ;
  - 002 plante sur `NameError: PieceJointeImportee`. Le marqueur d'ACEL61 est absent de son bouchon : la sonde est périmée ;
  - 003 est inconclusive (bouchon sans `controles`) ;
  - 004 rend « non reproduit » pour une mauvaise raison (`NameError: active_companies`). Sa partie statique lit pourtant
    « consigné au journal : vrai » sur les quatre sites (ACEL39, ACEL45).
  Le rafraîchissement des sondes 002 à 004 relève d'ACEL9 (ouverte).
- **Constats d'origine S2.** C-ACEL-002, 003 et 004 sont fermés par la lecture du code (ACEL61, ACEL62, ACEL39, ACEL45).
  C-ACEL-001 n'est pas fermé : ACEL1 est ouverte et la sonde reproduit (§6).

## 4. Écarts retenus

| C-id | Tâche d'origine | Grav. | Écart | Sonde | Tâche |
|---|---|---|---|---|---|
| C-ACEL-VER2-200 | ACEL81 | S3 | `check_prepaid_balance` et `check_account_health` avalent la limite douce de leur appel réseau avant le `degrader` de `_sync_company` ; `backfill_complet` avale celle du relevé des leads (`backend/django_core/apps/adsengine/tasks.py::check_prepaid_balance`) | STATIQUE (lecture : `exc_info=True` sur 6 sites) | ACEL90 |
| C-ACEL-VER2-201 | ACEL62 | S3 | Contrôles enregistrés dans la boucle, alerte après elle ; la limite douce est avalée au re-téléchargement (faux « introuvable »). Une mise à mort laisse « altéré » sans alerte, et la déduplication ne la refait jamais (`backend/django_core/apps/ged/services.py::verifier_integrite_archives`) | STATIQUE (lecture) | ACEL91 |
| C-ACEL-VER2-202 | ACEL70 | S3 | Empreinte enregistrée avant l'envoi GED, qui est best-effort : un routage en échec n'est plus repris à données inchangées (`backend/django_core/apps/ventes/utils/pdf.py::generate_facture_pdf`) | STATIQUE (lecture : receveur qui avale, `pdf_render_meta` posé avant) | ACEL92 |
| C-ACEL-VER2-203 | ACEL11 | S3 | Le balayage des travaux orphelins passe `failed` une découverte de veille en pause de quota (3 pauses = 2 100 s, job non touché) et prévient à tort son demandeur (`backend/django_core/apps/adsengine/veille_decouverte.py::executer_etape`) | STATIQUE (lecture : `_progression` après succès seulement) | ACEL93 |
| C-ACEL-VER2-204 | ACEL84 (jumeau) | S3 | Relève GED et relève du cœur lisent la même boîte en `UNSEEN`. La GED marque lu même ce qu'elle ignore : un courriel client n'atteint plus le SAV, un courriel à un alias GED n'atteint plus la GED (`backend/django_core/apps/ged/services.py::poll_mail_intake`) | STATIQUE (lecture : `store` hors condition sur `created`) | ACEL94 |

**Pourquoi S3.** Tous ces écarts sont latents, comme les constats qu'ils prolongent :
- VER2-200 : la limite dure de 180 s reste consignée par `task_failure` ; seule la limite douce est avalée ;
- VER2-201 : il faut plus de 120 s de re-téléchargement ou une erreur avant l'alerte ; le volume d'archives en production n'est
  pas mesuré ;
- VER2-202 : il faut un échec du routage GED ; le PDF de la facture reste stocké, seule la copie GED manque ;
- VER2-203 : il faut trois pauses de quota de suite ; c'est une fausse alerte, sans perte (le job finit `done`) ;
- VER2-204 : la relève GED est éteinte par défaut (`GED_MAIL_INTAKE_ENABLED`).

**Routage** (`check_ownership.py --owner-of`) :
- ACEL90 et ACEL93 → acquisition ;
- ACEL91 → documents ;
- ACEL92 → transverse (facturation, documents) ;
- ACEL94 → transverse (sécurité, documents, deploy).

**Réfuté ou écarté.**
- ACEL83 : aucun effet hors base n'échappe à la transaction par ligne.
- ACEL85 : seul le marquage change de connexion ; il se fait par UID.
- ACEL87 : un parent déjà purgé compte pour la société purgée ; c'est voulu, lu en base, et la ligne est ignorée si elle est
  déjà supprimée.
- ACEL88 : le filtre `active_company_ids()` porte aussi sur la réservation.

## 5. Optionnel (non déposé)

- `core/workflow.py::escalader_etape` réécrit le statut sans verrou ni relecture : une approbation concurrente peut être
  écrasée par « escaladée » (fenêtre de quelques millisecondes, une fois par heure). De plus, la commande
  `escalate_workflow_sla` n'isole pas les sociétés entre elles.
- `core/tasks.py::balayer_travaux_orphelins_task` met à jour par `pk` sans re-filtrer le statut : un job qui se termine pendant
  le balayage peut repasser `failed`.
- ACEL77 : un assemblage déjà « en cours » avant la migration (`assemblage_demande_le` nul) n'expire jamais.
- ACEL43 : `relancer_bcf_en_retard_task` n'a pas de limite au décorateur, et ses deux `except` avalent la limite douce.
- ACEL73 : la docstring de `emit_capi_signatures` parle encore d'un « Beat quotidien ».
- Rappels du matin, non revus : ACEL10 (5 sites sans test), ACEL68 (une transaction pour tout le lot), ACEL72 et ACEL63
  (limite douce avalée).

## 6. Couverture et sortie de cycle

- **Couvert.** Les 25 tâches cochées depuis le matin : code, commits, tests nommés, appelants, jumeaux, inscription au
  planning, routes, fuseau.
- **Non couvert.**
  - Aucun test Django lancé, aucun rejeu en direct ; les cinq écarts sont statiques.
  - Les 8 tâches bloquées en attente de preuve en direct.
  - ACEL1 : C-ACEL-001 (S2) reproduit encore, tâche ouverte.
  - ACEL9 : rejeu des sondes ; 002 à 004 sont périmées.
  - Volumes réels : archives légales, pauses de quota de la veille, boîte IMAP de production ; non mesurés.
- **Statut.** Aucun écart S1-S2 nouveau. Le marqueur compte 1 : C-ACEL-001, dont la tâche n'est pas cochée (§C.4.6). Le
  groupe est « construit », pas « vérifié ».

## 7. Rappel de la passe du matin

La passe du matin (mi-parcours, `47f925be1`) a relu 30 tâches : 28 ok, 2 partielles (ACEL2, ACEL71), aucun écart S1-S2. Elle
a déposé huit écarts S3, de C-ACEL-VER1-100 à 107. Ce qu'ils sont devenus ce soir :

| C-id du matin | Tâche | État au 14/11 soir |
|---|---|---|
| VER1-100 (limite douce, boucles Meta) | ACEL81 cochée | partiellement fermé : 14 sites relevés ; 6 restent → VER2-200 |
| VER1-101 (garde sans `authentication/`) | ACEL82 cochée | fermé (garde jouée, 44 tests OK, purge démo gelée « à trier ») |
| VER1-102 (import non transactionnel) | ACEL83 cochée | fermé (`transaction.atomic()` par ligne) |
| VER1-103 (relève GED marquée lue avant import) | ACEL84 cochée | fermé (BODY.PEEK, marquage après import) ; jumeau → VER2-204 |
| VER1-104 (marquage par numéro de séquence) | ACEL85 cochée | fermé (UID en relève et en marquage) |
| VER1-105 (message sans Message-ID) | ACEL86 cochée | fermé (`sans-id-<sha256>` stable) |
| VER1-106 (bloqueur sans `company_id`) | ACEL87 cochée | fermé (sociétés des parents lues en base, refus si différente) |
| VER1-107 (sociétés suspendues) | ACEL88, ACEL89 cochées | fermé (webhooks et escalade bornés aux sociétés actives) |

## 8. Coût

- 1 vérificateur (opus, effort élevé), rédacteur compris ; jetons non mesurés.
- Aucun appel Fable, aucun sous-agent.

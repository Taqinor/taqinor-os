# Vérifie ACEL — contre-visite de mi-parcours du parcours PF11 « tâches planifiées », 14/11/2026

Commande `loop audit` (14/11). L'audit de parcours PF11 (11/11) avait déposé ACEL1-80. Première contre-visite du groupe, due à
mi-parcours : 30 tâches cochées sur 38 constructibles. Rien n'a été construit ni déployé.

## 0. Préconditions

- **SHA.** `origin/main` = `47f925be1`. Branche de claim : `verifie-pf9-11-12-1411`.
- **Registre.** PF11 `taches-planifiees`, groupe ACEL : 30 tâches cochées sur 38 constructibles (78 %). 18 autres tâches sont
  livrées et attendent leur preuve en direct ; 8 sont ouvertes.
- **Échantillon.** Les 30 tâches cochées sont relues, pas seulement le tirage : ACEL2, 5, 6, 7, 10, 12, 15, 16, 17, 18, 33, 34,
  35, 37, 38, 40, 41, 44, 47, 63, 64, 66, 67, 68, 69, 71, 72, 74, 75 et 80.
- **Méthode.** Commits, code sur `origin/main` et tests nommés, tout lu ; mutants raisonnés. Aucune pile, aucun test Django
  lancé, aucune production consultée. Joué sur l'hôte : la garde `check_beat_active_companies.py` et ses 43 tests, deux tests
  du script de déploiement, le registre Celery chargé sans contrôles Django.

## 1. Vérificateurs (3 lots, opus, effort élevé, frais, même répertoire)

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **28** | ACEL5, 6, 7, 10, 12, 15, 16, 17, 18, 33, 34, 35, 37, 38, 40, 41, 44, 47, 63, 64, 66, 67, 68, 69, 72, 74, 75, 80 |
| partiel | **2** | ACEL2 (la garde ne lit pas `authentication/`), ACEL71 (14 `except Exception` encore sans relève) |
| non-fait / faux / régression / déjà-présent | **0** | — |

Les livraisons du lot de fin de parcours sont dans `main` par les PR #1389 et #1391, dont les contrôles requis sont verts.
Trois tâches « ok » portent un écart hors de leur « fini quand » : ACEL16, ACEL17 et ACEL33 (§4).

## 2. Tests nommés

- **Les 30 tests nommés existent** et sont comportementaux : vraie tâche ou vrai service appelé, état relu en base, dépendance
  externe seule simulée (client Meta, IMAP, stockage). Les tests à deux connexions d'ACEL47 (verrou, avec ACNC35) existent.
- Le mutant de chaque test est raisonné, pas joué. Le mutant écrit dans le texte d'ACEL34 (« retirer `statut=EN_ATTENTE` ») n'est
  pas tué par son test ; le vrai mutant tueur est « retirer la réservation » (§5).
- ACEL10 : deux des sept sites ont un test ; les cinq autres survivraient à un mutant (§5).
- Aucun test Django n'a été lancé ici ; la seule preuve d'un vert est la CI des PR #1389 et #1391.

## 3. Sondes, calendrier et preuve en direct

- **Garde.** `python scripts/check_beat_active_companies.py` : « OK — tout fan-out beat passe par active_companies() » (rejoué
  le 14/11) ; ses 43 tests passent.
- **Calendrier.** Les tâches touchées sont toutes au planning, routées vers la file `scheduled` (ou `interactive` pour l'export
  à la demande d'ACEL66), et ces files sont consommées par les workers du compose. Le registre chargé sans contrôles Django
  confirme ACEL38 (tâche enregistrée hors des URL) et ACEL41 (ni tâche, ni entrée de planning, ni route).
- **Sondes du dossier PF11.** Aucune tâche cochée ne cite de sonde. Rejouées pour information le 14/11 : la sonde 001 reproduit
  encore (sa tâche ACEL1 est ouverte) ; la 002 plante à l'extraction ; la 003 est inconclusive ; la 004 rend « non reproduit »
  pour une mauvaise raison (bouchon périmé : `NameError` sur `active_companies`). Les quatre relèvent d'ACEL9, rejeu de
  l'orchestrateur, encore ouvert : elles sont à rafraîchir avant lui.
- **Preuve en direct.** Les 30 tâches portent « Preuve en direct : n/a » (tâche planifiée, garde de dépôt, clé absente) : aucun
  enregistrement n'est dû. Les 18 tâches livrées en attente de preuve se rejouent sur un runner, en cours le 14/11.

## 4. Écarts retenus

| C-id | Tâche d'origine | Grav. | Écart | Sonde | Tâches |
|---|---|---|---|---|---|
| C-ACEL-VER1-100 | ACEL71 | S3 | 14 `except Exception` des boucles Meta avalent encore la limite douce : la tâche peut finir « succès » (`backend/django_core/apps/adsengine/tasks.py::pull_ad_leads_for_company`) | STATIQUE (lecture : `relever_si_delai` sur 5 sites seulement) | ACEL81 |
| C-ACEL-VER1-101 | ACEL2 | S3 | La garde ne lit pas `authentication/` : la purge démo planifiée sans limite de temps passe (`scripts/check_beat_active_companies.py::_iter_source_files`) | STATIQUE (garde jouée sur `authentication/` : un signalement) | ACEL82 |
| C-ACEL-VER1-102 | ACEL33 | S3 | Ligne d'import non transactionnelle : une limite douce après la création du lead le laisse, la reprise le recrée (`backend/django_core/apps/publicapi/bulk.py::run_import_job`) | STATIQUE (lecture : aucun `atomic` autour de la ligne) | ACEL83 |
| C-ACEL-VER1-103 | ACEL17 | S3 | Relève GED jamais alignée : message marqué lu avant import, aucun délai réseau (`backend/django_core/apps/ged/services.py::poll_mail_intake`) | STATIQUE (lecture : `(RFC822)`, `IMAP4_SSL(host)`) | ACEL84 |
| C-ACEL-VER1-104 | ACEL17 | S3 | `\Seen` posé par numéro de séquence sur une seconde connexion : après un EXPUNGE, un autre message est marqué lu et perdu (`backend/django_core/core/email_intake.py::poll_mailbox`) | STATIQUE (lecture : `msg.imap_num`, `store(num, …)`) | ACEL85 |
| C-ACEL-VER1-105 | ACEL17 | S3 | Message sans `Message-ID` redistribué à chaque relève : un ticket SAV par passage (`backend/django_core/core/email_intake.py::_parse_email_message`) | STATIQUE (lecture : `message_id=''`, marqueur absent) | ACEL86 |
| C-ACEL-VER1-106 | ACEL16 | S3 | La purge démo ne refuse un bloqueur d'une autre société que s'il porte `company_id` (`backend/django_core/authentication/management/commands/reset_demo_company.py::_delete_cascading`) | STATIQUE (lecture : `hasattr(blocker, 'company_id')`) | ACEL87 |
| C-ACEL-VER1-107 | ACEL5 (hors lot) | S3 | Relance des webhooks et escalade des workflows balaient encore les sociétés suspendues (`backend/django_core/apps/publicapi/retry.py::run_due_retries`, `backend/django_core/core/management/commands/escalate_workflow_sla.py::Command.handle`) | STATIQUE (lecture : gelés « à trier ») | ACEL88, ACEL89 |

**Pourquoi S3.** Tous ces écarts sont latents ou sans perte, comme les constats d'origine qu'ils prolongent (PF11 les classe S3) :
- la limite dure de 180 s reste consignée ; seule la limite douce est avalée (VER1-100) ;
- la garde rate un seul site, éteint par réglage (VER1-101) ;
- l'import en masse n'a jamais servi en production (VER1-102) ;
- relève GED éteinte par défaut, relève IMAP non mesurée en production (VER1-103 à 105) ;
- purge démo éteinte, reset réservé aux sociétés de démonstration (VER1-106) ;
- une seule société en production (VER1-107).

**Le ticket SAV en double (VER1-105) n'est pas S2.** Le doublon est un vrai objet métier : un ticket par passage, toutes les 10
minutes. Mais il faut trois conditions à la fois : la relève IMAP allumée, un message sans `Message-ID` (Microsoft 365 en
estampille un) et un autre handler qui lève à chaque passage. PF11 et PF9 classent S3 un doublon latent de ce type (deux tickets
préventifs, réglage éteint). Il deviendrait S2 le jour où la relève est allumée et un handler échoue durablement.

**Routage.** Une tâche par propriétaire (`check_ownership.py --owner-of`) :
- ACEL81 → acquisition ;
- ACEL82 → deploy ;
- ACEL83, ACEL88 → analyse ;
- ACEL84 → documents ;
- ACEL85, ACEL86, ACEL87, ACEL89 → sécurité.

C-ACEL-VER1-107 touche deux propriétaires : il est scindé en deux tâches sœurs. L'écart d'ACEL17 est scindé en trois (GED,
marquage, identifiant).

**Réfuté ou requalifié.** Aucun écart n'est réfuté. Le message redistribué n'est corrigé qu'à un endroit, l'analyse du message,
qui rend effectifs les dédoublonnages déjà présents chez tous les handlers ; « ne redistribuer qu'aux handlers en échec » n'est pas
retenu (il faudrait un état par message).

## 5. Optionnel (non déposé)

- ACEL34 : le mutant écrit dans la tâche n'est pas celui que le test tue ; la docstring de `run_due_retries` parle encore de
  « toute tentative » alors que le lot est borné à 50.
- ACEL10 : seuls deux des sept sites ont un test ; `core/tasks.py::_purger_exports_reversibilite_expires` avale encore la limite douce.
- ACEL67 : la libération de la marque après un échec avant la transaction peut effacer celle d'un autre worker (sans effet :
  le lead porte déjà un devis) ; deux docstrings périmées.
- ACEL68 : une seule transaction pour tout le lot de factures ; une erreur annulerait la bascule de toutes.
- ACEL72 : `assumption_decay.py::oublier_toutes_les_societes` avale aussi la limite douce.
- ACEL75 : le test appelle `gc.collect()` par précaution ; une sonde hôte montre que le générateur se referme sans lui.
- ACEL63 : l'isolation par société des tâches de signature GED avale la limite douce.
- ACEL44, ACEL47, ACEL40 : docstring non mise à jour ; une erreur persistante sur un contrat arrête encore les suivants de la
  même société ; la commande manuelle `--creer-plans` amorce encore des plans chez les sociétés suspendues.
- ACEL2 : la garde tient pour relevée toute clause qui contient un `raise` ; elle ne lit pas le service qui fait la boucle.
- ACEL16 : `adminops/tasks.py::purger_sandbox_expires` supprime par `delete()` brut.
- À vérifier : la relève GED et la relève du cœur lisent la même configuration IMAP ; la première qui passe marque les messages
  lus et l'autre ne les voit plus (relève GED éteinte par défaut).

## 6. Couverture et sortie de cycle

- **Couvert.** Les 30 tâches cochées : code, commits, tests nommés, jumeaux, appelants, inscription au planning et files.
- **Non couvert.**
  - Aucun test Django lancé, aucun rejeu en direct ; les huit écarts sont statiques.
  - Les 18 tâches livrées en attente de preuve en direct (ACEL3, 4, 8, 11, 14, 32, 39, 45, 48, 61, 62, 65, 70, 73, 76, 77, 78,
    79) : leur rejeu sur un runner est en cours le 14/11.
  - Les 8 tâches ouvertes : ACEL1, 31 (heure des rapports), 36 (données périmées), 13, 42, 43, 46 (interrupteurs à l'écran),
    toutes débloquées par les décisions du 13/11, et ACEL9 (rejeu des quatre sondes du dossier).
  - Durées réelles des tâches et boîte IMAP de production : non mesurées.
- **Statut.** Aucun écart S1-S2 sur les 30 tâches relues. Le groupe n'est pas encore « construit » : tâches ouvertes et
  preuves en direct manquent. La contre-visite de clôture sera due à 95 %.

## 7. Coût

- 3 vérificateurs (opus, effort élevé) et 1 rédacteur (opus) ; jetons non mesurés ici.
- Aucun appel Fable.

<!-- verifie | groupe: ACEL | pct: 78 | ecarts_s1_s2: 0 -->

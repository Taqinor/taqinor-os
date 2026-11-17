# Vérifie AMSG — contre-visite des correctifs du parcours PF8 « messages sortants », 17/11/2026

<!-- verifie | groupe: AMSG | pct: 98 | ecarts_s1_s2: 0 -->

Commande `loop audit` (17/11). Le compte rendu du 14/11 (`docs/audits/2026-11-14-messages-sortants-verifie.md`) portait
deux écarts S1-S2 (C-AMSG-VER3-100 → AMSG97, C-AMSG-VER2-101 → AMSG92) et quatre S3 (AMSG98-101). Toutes ces tâches
sont cochées : c'est la contre-visite des correctifs (METHODE §C.4.6). Rien n'a été construit ni déployé.

## 0. Préconditions

- **SHA.** `origin/main` = `0d834aa12` (branche `verifie-1711`, à jour).
- **Registre.** `audit_registre.py --du` (acceptation neutralisée, §C.4.5 f) : « AMSG (PF8 messages-sortants) : 98 %
  cochées (82/83) — vérifie dû, contre-visite des correctifs (écarts S1-S2 du 2026-11-14 tous cochés) ». Ouverte : AMSG83 ;
  bloquées sur leur preuve en direct : AMSG30, AMSG62, AMSG105.
- **Échantillon.** Les cinq tâches d'écart du 14/11 (AMSG97 S2 d'abord, puis AMSG98, 99, 100, 101) et toutes les tâches
  AMSG à CODE NEUF cochées depuis : AMSG72 (rappel de pose J-1, commits du 17/11), AMSG102, 103, 104 (« Mes activités »).
  AMSG105 (bloquée) est relue pour l'état des sondes. Les autres cochages depuis le 14/11 (AMSG2-6, 35, 56-59, 65-69, 71,
  73, 76, 78, 84, 89, 92-96) sont des coches d'acceptation de code déjà contre-visité le 13 ou le 14/11 : non relus ici.
- **Méthode.** Commits de chaque tâche (`git log --grep`), code sur `0d834aa12`, tests nommés lus (mutant raisonné),
  appelants et jumeaux par grep (autre canal, autre tâche Celery, autre émetteur Meta, autre envoi « jours ouvrés ») ;
  sondes AMSG rejouées sur l'hôte ; gardes hôte `check_garde_contact.py`, `check_beat_active_companies.py`,
  `check_stages.py` : OK. Aucune pile, aucun Docker, aucun test Django ni Vitest lancé, aucune production lue, aucun envoi.

## 1. Vérificateurs

Un vérificateur (opus), frais, qui n'a construit aucune de ces tâches, sans sous-agent.

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **6** | AMSG97, AMSG99, AMSG100, AMSG102, AMSG103, AMSG104 |
| régression (S3) | **3** | AMSG98 et AMSG72 (reprise perdue si l'ouverture est tardive), AMSG101 (relevé de janvier 2027 perdu) |
| non-fait / faux / déjà-présent | **0** | — |

Écarts S1-S2 d'origine, sur `origin/main` :
- **C-AMSG-VER3-100 (AMSG97) : fermé dans le code.** `apps/crm/management/commands/opposer_fiches_soeurs.py` est en
  dry-run par défaut (« N fiche(s) — dry-run, rien écrit »), écrit seulement sur `--appliquer`, parcourt les sociétés une à
  une (`--societe` optionnel) et ne cherche les sœurs que dans la société de la fiche opposée
  (`leads_doublons.py::fiches_soeurs_contactables`, seule requête, partagée avec le STOP) ; n'affiche ni numéro ni e-mail ;
  coche par `_marquer_lead_ne_plus_contacter` (ligne de chatter, jamais de SQL) ; idempotente (une sœur cochée sort du
  filtre ; le test rejoue `--appliquer` ⇒ « 0 fiche(s) ») ; `--sauf` pour exclure. Elle ne touche que des fiches qui
  partagent un téléphone, un WhatsApp ou un e-mail normalisé avec un lead `ne_plus_contacter`. **Les données de production
  ne sont pas réparées** : aucune trace d'un dry-run montré au fondateur ni d'un `--appliquer` (décisions du 11/11) ; les 2
  numéros relevés le 11/11 restent à traiter par ce geste.
- **C-AMSG-VER2-101 (AMSG92) : fermé** (sonde rejouée : repro faux, §3), tâche cochée.

## 2. Tests nommés

Tous existent et sont comportementaux. AMSG97 : `tests_acrm_registre_opposition.py::RegistreOppositionTests::
test_commande_coche_les_soeurs_d_une_opposition_anterieure` (état de la migration 0154 reproduit par `update` +
`bulk_create`, autre société et fiche sans contact commun inchangées, seconde application à 0). AMSG98 :
`RelancesTests::test_ouverture_lointaine_aucune_reprise_differee`. AMSG99 :
`XSAV4NotificationsClientTest::test_brouillon_remis_assigne_au_technicien_du_ticket` (technicien, créateur, puis
aucun actif). AMSG100 : `LeadReceivedTests::test_contact_oppose_aucun_evenement`. AMSG101 :
`test_jour_ferie_aucun_rappel_et_borne_allongee`, `test_jour_ferie_aucun_releve_rattrape_le_lendemain`. AMSG72 :
`TestRappelRdvJ1::test_fenetre_et_jours_ouvres` (heure figée en heure de Casablanca après le rouge CI #1445). AMSG102-104 :
`MesActivitesPage.chargeEquipe.test.jsx`, couverts par l'enregistrement d'acceptation du 17/11 (`2026-11-17-25ccf87b4`).
Aucun test ne couvre une ouverture de fenêtre tardive le jour même ni un 1er du mois férié tombant un vendredi.

## 3. Sondes et preuve en direct

- **Rejeu hôte (17/11, `python -B`, UTF-8).** `C-AMSG-001`, `002`, `003`, `006`, `007`, `008`, `010`, `012` : `repro:
  false` ; elles exécutent le vrai code du dépôt (modules chargés en entier ou fonctions extraites par ast). `003` et `007`
  s'exécutent de nouveau (AMSG105). `C-AMSG-VER2-101` : `repro: False` (AMSG92 fermé). Périmées sur l'hôte, NON citées :
  `004`, `005` (`ImportError` : `activity`), `009` (`NameError: timezone` sous son bouchon ; AMSG105 la dit exécutable
  en conteneur, non vérifiable ici), `011` (`NameError: DroitDeLaGrille`).
- **`C-AMSG-VER3-100` : `repro: True`, attendu.** Elle rejoue le STOP et les enregistrements, chemins volontairement
  laissés sans re-cochage des sœurs (le 14/11 recommandait de ne pas recocher à chaque enregistrement) ; la fermeture passe
  par la commande, couverte par le test Django (non rejoué ici) et l'acceptation du 14/11 sur runner.
- **Sonde nouvelle `docs/audits/sondes/AMSG/C-AMSG-VER4-400.py`** (hôte, Django importé sans base) : vrai `horaires.py`,
  vraie `fenetre_notifications`, vrais corps de `signature_relances_expiration`, `rappel_rdv_j1` et `_jours_cibles`.
  Jeudi 18/02/2027 07:45, Ramadan saisi : ouverture 10:00 (défaut 0082) ou `message_heure_debut` 09:30 ⇒ 0 relance, 0
  reprise, poses jamais lues ; témoins 08:30 et 09:00 ⇒ une reprise de chaque tâche. **repro: True.**
- **Preuve en direct.** AMSG97/99 : enregistrement du 14/11 (`2026-11-14-ff2ba7f2d`) ; AMSG102-104 : 17/11. AMSG72, 98,
  100, 101 : « n/a — latent », preuve = test rouge.

## 4. Écarts retenus

| C-id | Tâche d'origine | Grav. | Écart | Sonde | Tâches |
|---|---|---|---|---|---|
| C-AMSG-VER4-400 | AMSG98, AMSG72 | S3 | `ged/tasks.py::signature_relances_expiration` et `installations/tasks.py::rappel_rdv_j1` ne reprennent qu'une ouverture à moins de 5 400 s de 07:45, sinon RIEN : ouverture ≥ 09:15 le jour même ⇒ relances non faites, rappels J-1 du jour perdus | `docs/audits/sondes/AMSG/C-AMSG-VER4-400.py` | AMSG106 |
| C-AMSG-VER4-401 | AMSG101 | S3 | `ventes/scheduled.py::releve_mensuel_reminders` saute un jour férié en comptant sur la fenêtre 1-3 du beat ; quand le 1er est un vendredi férié, 1-3 n'a pas d'autre jour de semaine : 01/01/2027 ⇒ aucun relevé en janvier 2027 | STATIQUE | AMSG107 |

Gravités rejugées.
- **VER4-400 est S3, régression introduite par un correctif.** Déclencheurs réels : `ramadan_appel_debut` vaut encore 10:00
  pour tout profil antérieur au 21/09/2026 jamais édité (0082 l'a posé, 0099 n'a changé que le défaut) et
  `horaires.fenetre_du_jour` l'applique aussi aux messages ; `message_heure_debut` est éditable sans borne. Latent tant
  que les dates du Ramadan ne sont pas saisies (Ramadan 2027 vers le 8 février). Deviendrait actif sans geste de code.
- **VER4-401 est S3** : fériés saisis seulement par `seed_holidays_*`, état prod non lu.
- **Optionnel (non déposé).** AMSG99 : la tâche dit « motif journalisé » quand personne n'est actif ; aucun journal (tâche
  non assignée, rien d'autre). AMSG100 : la garde lit le seul téléphone ; un miroir Meta sans `phone_key` d'une personne
  opposée par e-mail partirait encore (cas rare : les leads Meta portent un téléphone). AMSG97 : une fiche opposée à la
  corbeille (hors `Lead.objects`) n'entraîne pas ses sœurs.
- **Marqueur : 0 écart S1-S2** (aucun nouveau ; les deux d'origine ont leur tâche cochée).

## 5. Points pour le fondateur

- **Réparation AMSG97 à faire en production** : lancer `manage.py opposer_fiches_soeurs` (dry-run), relire la liste
  (ids, société, nature du contact), puis `--appliquer` (décisions du 11/11). Tant que ce n'est pas fait, les sœurs relevées
  le 11/11 restent contactables.
- **Lire `ramadan_appel_debut` du profil de production** avant de saisir les dates du Ramadan 2027 : à 10:00, les
  relances de signature et les rappels J-1 s'arrêtent tout le mois tant qu'AMSG106 n'est pas construite.
- Sondes périmées hors AMSG105 : `004`, `005`, `011` (et `009` sur l'hôte).

## 6. Couverture et sortie de cycle

- **Couvert.** AMSG97-101, AMSG72, AMSG102-104 : code, commits, tests nommés, appelants, jumeaux (seuls sites `eta=` hors
  tests : 2 ; émetteurs Meta `capi_crm`, `capi_odoo`, `capi_signee`, accusé WhatsApp, audiences, tous gardés ; beats de
  semaine `relance_reminders`, `pre_echeance_reminders`, `releve_mensuel_reminders`) ; quinze sondes rejouées, une nouvelle.
- **Non couvert (sans pile).** Aucun test Django ni Vitest lancé (la CI de `main` fait foi) ; aucun rejeu navigateur ;
  aucune lecture de la production (paires du 11/11, fériés, `ramadan_appel_debut`, état du mail) ; la commande AMSG97 n'a pas
  été rejouée sur l'hôte.
- **Sortie de cycle.** Premier `vérifie` AMSG à zéro S1-S2 (le 14/11 en comptait 2). Il en faut un second consécutif à zéro
  pour sortir du cycle : le groupe peut devenir « vérifié » au registre, la sortie attend la prochaine contre-visite (après
  AMSG106-107 et la preuve d'AMSG105).

## 7. Coût

H0 S0 O1 F0 · jetons sous-agents ≈ 0 M (aucun sous-agent) ; aucun appel Fable.

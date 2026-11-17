# Vérification adverse v1 : designs S1-S4 (`apps/taches`) contre le code

Lecture seule. Chemins relatifs à `backend/django_core/` sauf mention. Chaque constat cite le fichier lu dans cette session.

Comptes : **2 BLOQUANT, 8 MAJEUR, 11 MINEUR**.

## BLOQUANT

**B1. Deux schémas incompatibles : S2 §8 contre S1 §2.** Le moteur (S2) lit des champs que le modèle (S1) n'a pas, ou qu'il a sous un autre nom ou une autre échelle :
- **Échelle de priorité inversée.** S2 a `Projet.priorite` à 1 = haute et trie en ordre croissant. S1 a `Priorite` à 0 = aucune et 3 = haute.
- **Pas d'« importance » dans S1.** S2 utilise `important` comme un drapeau distinct de la priorité (bande 2, créneau réservé, règle anti-triche). S1 n'a pas ce champ, alors que ses compteurs `nb_importantes_*` en dépendent.
- **Champs de S2 absents de S1** : `en_attente_de`, `demarree_le`, `source_duree`, `exploratoire`, le « projet focus » de la semaine, `ajoutee_apres_validation`.
- **Noms différents** : `reportee_n` contre `reports`, `ce_soir` contre `moment='soir'`, `abandonnee_le` contre `annule_le`, `accepte_le`/`cible_nb`/`budget_min` contre `planifie_le`/`objectif_nb`/`capacite_minutes`.
- **Tables différentes** : StatJour, BilanJour, IntentionSemaine, PreferenceTaches et RappelEnvoi (S2) contre PlanJour, ReglagesRythme et IncitationCoach (S1).
- **Modes différents** : `pousser`/`tenir` (S2, S3) contre `progresser`/`maintenir`/`libre` (S1).

Correction : un seul tableau de champs, arrêté avant le contrat PACT10. Il faut choisir l'échelle de priorité, ajouter `important` et `en_attente_de`, puis fusionner les tables.

**B2. Trois API pour une même fonction (S1 §3, S3 §1-2, S4 §1/4/5).**
- **Aujourd'hui** : S1 sert `GET aujourdhui/` → `{jour, journee[], en_retard[ITEM], …}`. S3 sert `GET journee/` → `{date, aujourdhui[], en_retard{total, lignes[≤5]}, …}`.
- **Création** : trois routes, `taches/saisie-rapide/` (S1), `capturer/` + `capturer/apercu/` (S3) et `capture/` à jeton (S4).
- **Rythme** : `GET rythme/` + `PATCH reglages/` (S1) contre `POST rythme/` + `POST preferences/` + `GET profil/` (S3).
- **Dates** : S1 fait de `planifier/` « le seul chemin qui déplace la date et compte les reports ». S3 déplace la date par `PATCH taches/{id}/ {statut, reporter_au}`, ce qui contourne le compteur, et clôt par `statut` alors que S1 a `terminer/`.
- **Routes citées hors de S1** : `plan/proposition/`, l'adoption de plan, `revue-semaine/`, `badge/`, `widget/`, `capture-token/`.

Ce conflit est bloquant parce que `donnees` d'une carte est le corps de l'endpoint « sans remise en forme » (`apps/agent/contract_samples/assistant_reponse.json:4`). La carte `ma_journee` et l'écran doivent donc partager un seul JSON. Correction : un seul inventaire de routes dans S1, repris tel quel par S3 et S4, et contrat d'abord.

## MAJEUR

**M1. Plafond des rappels contraire à D-TCH-3** (matin + soir + au plus UN rappel en journée, soit 3).
- S1 : `max_incitations_jour` vaut 2 par défaut.
- S2 §6 : 2 par jour, 3 le jour de revue, plus un `midi` et un `hebdo`.
- S3 §6 : « au plus DEUX », sans rappel en journée.
- S4 §2 : 3, échéances comprises, ce qui laisse 0 rappel en journée dès qu'une échéance tombe.

Par ailleurs, S3 appelle `notify(..., respect_quiet_hours=True)` sans contrôle préalable. Or `notify` REPORTE la notification hors fenêtre (`apps/notifications/services.py:528-570, 689-711`), si bien qu'un rappel du matin arriverait périmé. S2 et S4 sautent l'envoi, et ils ont raison. Correction : plafond = 1 matin + 1 soir + 1 rappel en journée, réglable, échéances hors de ce compte (ou comptées explicitement dans le rappel de journée), et toujours sauter hors fenêtre.

**M2. La corbeille expose les tâches privées (contraire à D-TCH-1).**
- `SoftDeleteModel.soft_delete` émet `record_soft_deleted` avec `libelle=str(self)` (`core/models.py:204-224`).
- `apps/trash` liste ces lignes à toute la société pour les rôles `IsAdminOrResponsableTier` et les laisse RESTAURER (`apps/trash/views.py:123-187`, `models.py:56`).
- S1 (« DELETE = soft delete », restaurateur `trash/registry.py:27`) et l'« Annuler » de S3 s'appuient sur ce mécanisme.

Correction : `soft_delete(record=False)` plus une corbeille propre à l'utilisateur, ou un libellé neutre et un filtre `deleted_by=user` côté trash (tâche du propriétaire securite).

**M3. Flux iCal contradictoire.** S1 §1 ajoute les tâches au flux EXISTANT (`_user_calendar_events`, `apps/reporting/calendar.py:433-502`). S4 §3 crée un flux séparé `?flux=taches` et laisse l'actuel « octet pour octet identique ». Il faut en retenir un seul.

**M4. Le jeton ICS expire après 180 jours** (`apps/reporting/calendar.py:57-68`, `resolve_ics_token` :395-430 renvoie 404 sans le dire). L'abonnement du calendrier de l'iPhone, et donc le widget Calendrier de D-TCH-2, cesse de se mettre à jour au 181e jour. S4 cite l'expiration mais ne prévoit pas de renouvellement. Correction : relancer l'utilisateur avant l'échéance (écran ou rappel) ou utiliser un jeton dédié sans `max_age`, révocable par version.

**M5. `check_unique_scoping`, contrôle (b), échouera** (`scripts/check_unique_scoping.py:240-255`). Sur un modèle `SoftDeleteModel`, chaque `UniqueConstraint` doit porter une `condition` qui cite `is_deleted`/`deleted_at`. Or les contraintes `taches_tache_act_uniq` et `taches_tache_occ_uniq` (S1) n'ont que `... IS NOT NULL`. Correction : ajouter `is_deleted=False` aux deux conditions.

**M6. FICHIER_MUR sur `erp_agentique/settings/base.py`.** Le fichier fait 2 139 lignes. Toute ligne ajoutée exige qu'une tâche cochée cite le chemin exact avec « lignes nettes attendues ≤ N » (`scripts/forme_code/fichier_mur.py`, garde branchée `scripts/ci_guards.py:624`). Sont concernés : INSTALLED_APPS, la route Celery, le débit `taches_capture`, `TACHES_RAPPELS_ACTIFS`. Aucun design ne le mentionne. Les autres fichiers touchés restent sous 2 000 lignes : `sql_agent_service.py` 1 908, `records/views.py` 1 554, `notifications/services.py` 1 589.

**M7. Jeton Siri et Scriptable contradictoires, et contraires à D-TCH-2.** S1 met un seul `jeton_capture_hash` sur ReglagesRythme et le renvoie en v1.1. S4 crée un modèle `CaptureToken` (portées `capture`/`widget`) en v1. S4 §5/§8 range aussi Scriptable « plus tard » et le dit soumis à « l'accord du fondateur », alors que D-TCH-2 l'a déjà accordé et exige tout, grande tuile comprise.

**M8. Les fichiers étrangers touchés par S4 ne sont pas attribués** (`docs/ownership.yml`) :
- **parametres** :659 : `notifications/types_evenements.py`, `module_map.py`, `module_gating.py`, une migration, et `_dispatch_webpush` (services.py:272), où calculer la pastille crée une dépendance notifications → taches et une requête par push, tous modules confondus.
- **securite** :486 : `authentication/selectors.py:184-192`.
- **analyse** :853/868 : `reporting/calendar.py` et `features/offlinesync/mobile/CockpitHome.jsx:80`.
- **deploy** :752-807 : `sw.js`, `vite.config.js`, `features/pwa/shortcuts.test.mjs`, `components/layout/Layout.jsx`, `celery.py` et `settings/base.py`. Ces deux derniers sont aussi sous la réservation `erp_agentique`.

Ces tâches vont dans `PLAN_AUDIT_TRANSVERSE.md`. Pour la pastille, préférer un registre dans `core` (patron `core.notify_registry`) à un import de taches depuis notifications.

## MINEUR

1. **Le sélecteur records n'est pas obligatoire.** `records` est une app de fondation, exemptée par CLAUDE.md. `reporting/calendar.py:491-492` importe déjà `records.models` et `records.views.sans_cibles_archivees`. Le `records/selectors.py` neuf de S1 est un choix de propreté chez le propriétaire securite, pas un prérequis.
2. **`VerrouOptimisteMixin` seul ne renvoie aucun 409** (`core/champs_plateforme.py:31-53`). Le 409 vient de `core.mixins.VerrouOptimisteSerializerMixin` (:259) et de `core/verrou_optimiste.py`. Les @action `terminer`/`planifier`/`reordonner` et l'« Annuler » de S3 doivent l'appeler explicitement.
3. **`check_read_modify_write`** (`scripts/check_read_modify_write.py:175-202`) : `tache.reports += 1` dans `services.py` sans `F()` ni `select_for_update` passe au rouge.
4. **`check_beat_active_companies`** : le balayage des rappels doit parcourir `authentication.selectors.active_companies()`, jamais `Company.objects.all()`. Aucun design ne le dit.
5. **Plafond compté par marqueurs** : `_reserver_emission` est PRIVÉE (`notifications/sweeps.py:322`). Compter les marqueurs d'une journée demande un sélecteur ou un service public dans notifications.
6. **Contraintes de S4 sans société** : la contrainte (user, portee) de `CaptureToken` et le `client_id` « unique » omettent `company`. Un `unique=True` sur `client_id` fait échouer le contrôle (a). Utiliser `UniqueConstraint(company, proprietaire, client_id)`.
7. **Projet supprimé** : supprimer un Projet en douceur laisse ses tâches vivantes (`Tache.objects` les montre), donc des tâches d'un projet supprimé apparaissent dans « Aujourd'hui ». Prévoir une suppression en cascade dans le service.
8. **Champs absents de S1 pour S4 §3** : le créneau horaire et le rappel (`VALARM` « si rappel », événement « avec créneau », `TACHES_ECHEANCE`). S1 n'a que `moment` et `echeance_heure`.
9. **Pastille définie deux fois** : « tâches restantes du plan » (S2 §6) contre « tâches ouvertes avec `jour_prevu` = aujourd'hui » (S4 §1). Heure du matin : 08:30 (S2) contre 09:00 (S4).
10. **Endpoints à jeton de S4** (`capture/`, `widget/`) : ils doivent garder `IsAuthenticated` avec l'authentification par jeton. `AllowAny` ferait échouer `core/tests/test_endpoint_permission_inventory.py:39-50`, dont la liste d'exceptions appartient à securite.
11. **Compteur `ailleurs.approbations` de S1** : il obligerait à rappeler l'API privée `reporting.approbations._SOURCE_LOADERS` (`records/views.py:553-557`, propriétaire analyse) et à tout parcourir à chaque appel. Exposer plutôt un compteur public chez reporting.

## Affirmations vérifiées VRAIES (socle solide)

- **records** :
  - `Activity` est hand-rolled et figée dans `platform_baselines/handrolled_models.txt:246`.
  - Une activité `personnelle` est exclue pour tout autre que son créateur (`views.py:390-393`).
  - La création d'un à-faire personnel est à :416-434 ; créer, clore et reporter exigent `IsResponsableOrAdmin` (:383, :656, :709).
  - `records/selectors.py` n'existe pas.
- **« Ma file »** (`views.py:487-652`) :
  - contrat `{kind, title, due, link, urgency}`, table d'effort à :244 ;
  - `affectations_pour(user)` existe (`sav/selectors.py:1429`, `installations/selectors.py:2814`) ;
  - un kind inconnu passe en fin de liste côté écran (`features/queue/queueViews.js:13-24`) et aucun test ne fige la liste des kinds ;
  - la fonction compte 71 lignes logiques (mesuré), donc ajouter un bloc ne déclenche pas FONCTION_MUR (> 100).
- **Flux ICS** : jeton `[user_id, version]`, sel `reporting.calendar.ics.v1`, rotation par POST (:374-392, :620-633). `build_ics` gère la journée entière et `start_dt`/`end_dt`, sans STATUS ni VALARM (:529-573).
- **Notifications** :
  - `notify` (:624) reporte hors fenêtre, payload push = `title`/`body`/`link` (:308-311), push activé par défaut.
  - Le golden EventType est un plancher ordonné de 109 membres : ajouter en fin d'énum est sûr (`tests_spl302…:172-178`). Le patron de migration est 0078 (3 AlterField, `max_length=40`).
  - Un signal sans récepteur échoue à YEVNT7 (`core/event_coverage.py:45`). En revanche, le « producteur » d'un EventType est un simple scan de texte : la chaîne écrite dans `module_map` suffit.
- **Agent** :
  - `CARTES` est fermé et vérifié dans `__post_init__` (ValueError) ;
  - la règle du lot `copilote` est à :49-54 ;
  - `ASSISTANT_COPILOTE` vaut `admins` par défaut (:269-286) ;
  - la carte-écho `crm.suivi.proposer_reponse` existe ;
  - aucune parité CARTES ↔ `CARTES_CONNUES` n'est testée aujourd'hui.
- **Contexte de l'assistant** :
  - la liste blanche `ContexteEcran` (`sql_agent.py:41-56`) et le tuple de `relais_copilote.py:213` existent ;
  - la limite de 950 mots ne porte que sur `CONSIGNES_COPILOTE` ;
  - le bloc coach mesure 283 mots, et sa liste de majuscules et ses 9 clés concordent exactement avec S3, sans aucun chiffre (mesuré) ;
  - l'adjacence testée est à `test_sql_agent_endpoint.py:1107`.
- **Accueil et PWA** : `MOBILE_HOME_ALLOWED_ROUTES` (`authentication/selectors.py:184-192`) avec son enum OpenAPI dérivé (`corps_requetes.py:28`). Les 5 raccourcis du manifeste sont figés par `deepEqual`.
- **Création de l'app** : `startapp_erp` et son gabarit existent. Aucun label, route ou module `taches` n'existe déjà.

## Non vérifié

- Le contenu exact des réservations de plan en cours : je n'ai pas lancé `plan_claims.py`, qui passe par le réseau.
- La couverture i18n : aucune garde bloquante trouvée dans cette lecture.
- Le comportement iOS : pastille posée depuis le service worker, Scriptable.

## OPTIONNEL (hors correction)

- Onze outils de plus partent à CHAQUE tour admin, conversations commerciales comprises, sous Groq à 8 000 TPM. Il faut mesurer avant le merge.
- Le registre DSR (`core/dsr.py`) n'est pas imposé par une garde. Il est pourtant souhaitable pour des données personnelles : réflexions, profil.
- Côté écran, appliquer `check_date_jour_utc` (`todayLocalIso`) et `fetchAllPages` aux listes paginées `projets/` et `taches/` (`check_liste_page1`).

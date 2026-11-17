# Vérification à blanc du plan TCH (constructeur à blanc)

Scripts : `verifplan/{chemins,contrat,sources}.py`. Joué ici : `plan_lanes.py --group "Fusion F1"` (13 lanes,
4 merge-batches), `makemigrations --check --dry-run` sur l'hôte (« No changes detected » ; Django 5.1.15),
`check_taches_cablage.py` (OK), `check_ownership.py` (refus attendu avant TCH1). Rien construit : « échouerait » =
lecture du code, pas exécution.

36 tâches examinées, au moins une par lane. Irréprochables : **TCH111** (patron `crm/agent_actions.py`,
`RISK_INTERNAL` `agent/registry.py:23`, `LOT_COPILOTE` :55 vérifiés), **TCH123**, **TCH44**.

## 1. Bloquants

**B1 — TCH150 supprime la moitié de la vérité (transverse).** `git rm -r docs/taches/travail` retire, avant F1,
`consignes-construction.md` (la fiche des lanes elle-même), `spec-7-ecrans.md`, `spec-5b`, `spec-6a`, `spec-6b`.
134 tâches sur 152 y renvoient dans leur `Source :` (script `sources.py`). Plusieurs n'ont leur contenu QUE là :
TCH116 (les 12 conversations : `spec-5b` annexe, absentes de la référence), TCH114 (`catalogue_pour_tour` : `spec-5b`
§7), TCH110 (script Scriptable : `spec-6b` annexe A), TCH46 (critères (1)-(4) : `spec-7` §6), TCH133-134 et les 9
acceptations (parcours et nombres de gestes : `spec-7` §7 ; aucune occurrence de « parcours » dans `reference/`),
TCH55 (familles d'obligations : `spec-6a` §4), TCH3 (gabarits `liens_cibles` : `spec-6a` §3.3).
→ TCH150 : conserver `docs/taches/travail/{consignes-construction,spec-7-ecrans,spec-5b-coach,spec-6a-erp,spec-6b-iphone}.md`
(ou les déplacer sous `reference/`) ; mettre à jour sa preuve `git diff --name-only` ; l'en-tête les cite dans « Où est la vérité ».

**B2 — TCH5 : le droit est accordé d'office.** `DIRECTEUR_PERMISSIONS = [p for p in ALL_PERMISSIONS …]`
(`permissions_registre.py:976`) et `ADMIN_PERMISSIONS` en dérive (:985). Ajouter `taches_voir` en fin
d'`ALL_PERMISSIONS`, « rien d'autre », le donne au Directeur et à l'Admin ; la preuve « aucun rôle ne le porte » est
fausse par construction.
→ TCH5 : « ajouter aussi `'taches_voir'` au tuple d'exclusion de `DIRECTEUR_PERMISSIONS` (ligne 977-978), avec le
commentaire `# TCH5 — retiré par TCH130` » ; TCH130 : « retirer cette exclusion ; Directeur et Admin l'héritent ».

**B3 — TCH151 en F1 rend F1 rouge.** `check_services_appeles.py` (dans `ci_guards.py:342`) ne compte ni les tests ni
le module définisseur ; la base ne peut que rétrécir. En F1, `annuler_geste`, `creer_taches`, `rappels.retirer/
repeter` n'ont aucun appelant non-test (appelants en F2 : TCH48, TCH53, TCH51).
→ Déplacer TCH151 en F2, `@after: TCH53, TCH51, TCH73` ; retirer TCH151 de l'`@after` et de la preuve de TCH37.

**B4 — TCH2/TCH3 : « exemple = l'exemple d'api.md mot pour mot » est impossible.** (a) La garde exige un objet
(`check_api_shapes.py:1162`, `isinstance(exemple, dict)`) : `gestes/`, `suggestions/`, `vues/`, `jetons/` rendent des
listes (api.md §4) → 4 échantillons rouges. (b) ~15 exemples portent des marqueurs (`ITEM`, `TACHE`, `PROPOSITION`,
`OBJECTIF`, `AUJOURDHUI`, `CARTE_DU_MOMENT|null`, `[…]`, `{…}`, `"…"`) ; `gestes/` et `recherche/` ne donnent que des
noms de clés.
→ api.md tranche la forme des 4 listes (proposé : `{"results":[…]}` non paginé, front et serveur identiques) ;
TCH2/3 : « chaque marqueur est remplacé par l'exemple complet de la forme du §1 ; `…` par une valeur du même type ».

**B5 — TCH69 lit un réglage déclaré en F3.** `raccourci_siri_url = settings.TACHES_RACCOURCI_SIRI_URL` (api.md §4),
déclaré par TCH99 (F3) ; `check_settings_declares.py` refuse toute lecture non déclarée → F2 rouge.
→ Déclarer `TACHES_RACCOURCI_SIRI_URL = os.environ.get('TACHES_RACCOURCI_SIRI_URL', '')` dans TCH4 (même fichier,
« Code net ≤ 4 ») et le retirer de TCH99.

**B6 — TCH13 et TCH14 lisent des fichiers d'une lane parallèle.** `url_de_cible` lit `liens_cibles.json` (TCH3) ;
`test_formes.py` compare aux clés de `item.json`, `tache.json`, `projets_liste.json`… (TCH2, TCH3). `plan_lanes`
place `contrats` et `socle` dans le même batch 1 : ces fichiers n'existent pas dans le worktree du socle.
→ TCH13 `@after: TCH12, TCH3` ; TCH14 `@after: TCH13, TCH2, TCH3`.

**B7 — TCH18 sans `@after`.** Sa preuve crée « 40 tâches seules » ; le modèle naît en TCH9 (autre lane, batch 1).
→ `@after: TCH9`.

**B8 — TCH41 construirait faux.** (a) `GUARDED_SELECTORS` est une liste de SÉLECTEURS CSS (`check_hex.mjs:36`),
pas de dossiers ; la garde lit `index.css` résolu par ses `@import`. (b) `css_golden.mjs` prouve qu'AUCUNE règle n'a
bougé : il échoue dès qu'on en ajoute. (c) Les CSS des maquettes ne sont pas portées (`html`, `body`, `button`,
`.note`, `.section`, `.ligne`, `.bouton`, `.entete`…) : versées dans `index.css`, elles s'appliquent à tout l'ERP.
→ « Toute règle reprise des maquettes est préfixée par `.tch` (classe racine de `CoquilleTaches`) ; `html/body/button`
jamais repris ; ajouter à `GUARDED_SELECTORS` les sélecteurs `.tch …` créés ; preuve : `check_hex.mjs` vert, sans
`css_golden` ».

**B9 — L'en-tête `X-Taqinor-Assistant` n'existe pas.** api.md §0 le dit « posé par `internal_headers()` » :
`fastapi_ia/app/core/config.py:68-80` ne pose que `Host` et `X-Forwarded-Proto`. Aucun `Files:` ne couvre
`config.py`. Les 403 et masquages « sous l'en-tête » (TCH53, TCH63, TCH69, TCH127) seraient construits, mais
jamais déclenchés en production.
→ TCH114 : « poser `X-Taqinor-Assistant: 1` par le paramètre `headers=` de `_django_call` (`action_tools.py:151`)
pour les seuls appels `taches.*` ; `internal_headers()` inchangé » ; corriger api.md §0.

## 2. Majeurs

En-tête et organisation
- **M1** L'en-tête dit « Django n'est pas installé sur l'hôte » ; c'est faux (vérifié : 5.1.15, `makemigrations
  --check` passe) et contredit `consignes-construction` §3, §5. → Recopier §3 et §5 de la fiche.
- **M2** Le contrat de propriété omet 18 fichiers de test étrangers nommés par les tâches (`roles/tests.py`,
  `notifications/tests.py`, `authentication/tests_recovery.py`, `tests_ntmob6…`, `agent/tests/test_registry.py`,
  `core/tests/test_registre_traitements.py`, `Header.test.jsx`, `BottomTabBar.test.jsx`, `useAppBadges.test.jsx`,
  `Dashboard.cockpit.test.jsx`, `CockpitHome.test.jsx`, `quickCreateEvents.test.mjs`, `commandActions.test.mjs`,
  `focusedRecordShortcuts.test.jsx`, `entityRoutes.test.jsx`, `cartes.test.jsx`, `copilotMessages.test.mjs`) ;
  l'INTERDIT « tout autre fichier de roles, notifications, authentication, agent, features/ia » les vise →
  `[BLOCKED]` à tort. → « … et le module de test que la tâche nomme, en ajout ».
- **M3** Les sous-vagues 0a/0b/0c ne sont plus affectées (elles l'étaient dans le squelette). `plan_lanes` imprime
  4 « merge-batches ». → Écrire dans l'en-tête : « les sous-vagues sont les merge-batches de `plan_lanes`, jamais
  des fusions ».
- **M4** « En cas de doute, la référence prime » alors que le plan s'en écarte exprès : donnees §6 L0 (`sweeps.py`,
  `agent_actions_module`, `features/taches/api/client.js`), api.md §6 (« exportés dans `contractSamples.js` »). →
  « donnees §6 et l'export de api.md §6 sont remplacés par ce plan ».

Socle et services
- **M5** TCH4 : `startapp_erp` crée aussi `models.py`, `selectors.py`, `serializers.py`, `services.py`, `urls.py`,
  `viewsets.py`, `receivers.py`, `admin.py`, `migrations/`, `tests/test_smoke.py` (`app_template/`). Ils heurtent
  les paquets de TCH7-TCH15. La commande refuse aussi si `apps/taches` existe (`startapp_erp.py:104`). → « Supprimer
  ces fichiers avant le commit ; ne garder que les 6 des `Files:` ».
- **M6** TCH7/TCH8 : la répartition des 19 modèles entre `projets/taches/journee/rythme/presence/erp/gestes.py`
  n'est donnée nulle part (VueEnregistree, ModeleProjet et RevueProjet ont-ils leur place dans `projets.py`, fichier
  absent des `Files:` de TCH8 ?). → Ajouter une table modèle → fichier.
- **M7** TCH9 : les fabriques ne sont pas nommées, alors qu'environ 25 modules de test les importent. → Fixer les
  signatures (`societe(slug)`, `compte(societe, *, voir=True)`, `projet(…)`, `tache(…)`), deux slugs distincts.
- **M8** TCH33 : `enregistrer_geste()` et `annuler_geste()` sans signature (donnees §5) ; plus de 30 appelants en
  F2. → Donner la signature et l'aide qui construit une op `champ`.
- **M9** Modules purs : le type des entrées n'est défini nulle part (`cle_tri(item, J, n_ouvres)`, `placer`,
  `tuile_pure`) ; l'`etat` du rythme est une « dataclass gelée » sans nom ni champs (regles §6.10). Les lanes pures
  et les lanes F2 deviendraient deux contrats. → Définir ces types dans regles §0.
- **M10** TCH11 : `nom_pour(obj, 'flux')` dépend de `titres_calendrier` ; la source n'est pas dite (une requête par
  appel ?). → Ajouter le paramètre `reglages`.
- **M11** TCH13 : la référence cite le privé `_devis_visibles` et `scope_client_queryset`. Les vraies portes
  publiques sont `apps.crm.selectors_libelles.libelles_crm(user, lead=, client=)` et
  `apps.ventes.selectors_libelles.libelles_ventes(user, devis=)` (patron `agent/views.py:731-732`). → Les citer.
- **M12** TCH3 : `liens_cibles.json` n'a aucun exemple dans api.md. → Écrire `{"crm.lead":"/crm/leads?lead={id}",
  "crm.client":"/crm?id={id}","ventes.devis":"/ventes/devis?devis={id}"}` (= `entityRoutes.js:25-27`).
- **M13** TCH15 : (a) « AJOUT d'une ligne » sans lieu : c'est en fin de `_APP_URLS`, pas
  d'`urlpatterns` (`]` en ligne 116) ; (b) « routes J:x → 401 » avant `JetonAccesAuthentication` : DRF rend 403 si aucun
  authentificateur ne fournit `authenticate_header`. → Préciser le lieu et le bouchon.
- **M14** TCH36/TCH60 : la couleur d'office (regles §1.9) n'a pas de fonction unique → jumeau. → Nommer
  `couleur_d_office(user)` dans `services/creation.py`, réutilisée par TCH60.
- **M15** TCH38 : « les 55 lignes A1-A39 et E1-E16 sans projet, étiquette… » se lit de deux façons (A3 porte
  `#Polydesign`). → Lister les identifiants obligatoires en TCH38.

F2 / F3
- **M16** TCH55 : aucune fabrique désignée pour les vraies lignes crm/visites/installations ; la correspondance des
  `kind` d'`affectations_pour` vers `pose`/`intervention` n'est que dans spec-6a ; `relance_etapes_dues` doit
  recevoir `owner=user`. → Les écrire.
- **M17** TCH66 : `repere.p60` n'a aucune règle de calcul (seulement le texte de textes §2.11) → chiffre inventé.
  → Règle dans regles §6, sinon retirer la clé.
- **M18** TCH69 : la source de `fenetre_societe` n'est pas dite (elle existe :
  `notifications/selectors.py:91 fenetre_notifications`) ; la règle d'`est_admin` non plus ; ni l'erreur d'un PATCH
  `suggestions_societe` venu d'un non-admin.
- **M19** TCH82 : le stockage du brouillon n'est pas défini (clé, portée par compte, purge à `taqinor:auth-logout`),
  alors que TCH77 et TCH91 le relisent. → Le fixer.
- **M20** TCH110 : la preuve « lit `faites`… ; ≤ 90 lignes » ne peut être qu'une regex sur le source (interdit par
  la règle 5). → Exiger un faux runtime Scriptable (`Request`, `ListWidget`, `Keychain`) qui exécute le script sur
  `tuile.json`.
- **M21** TCH117 : la preuve « via `CarteResultat` » demande le branchement de TCH118, qui vient après. → Rendre
  `CartesTaches` directement, ou inverser les deux tâches.
- **M22** TCH114 : `catalogue_du_tour(ctx)` existe déjà (`relais_copilote.py:110`) ; créer `catalogue_pour_tour`
  ferait un jumeau. → « étendre `catalogue_du_tour` ».
- **M23** TCH121 : `requirements.txt` n'a aucune bibliothèque ICS, et une dépendance neuve demande l'accord du
  fondateur. → Spécifier un lecteur maison minimal (VEVENT, DTSTART, DTEND, SUMMARY) et citer le validateur
  d'hôte `apps/publicapi/validators.py`.
- **M24** TCH74 (lane erp) : `register_dsr_provider` efface par `subject_identifier` (`core/dsr.py:86`), alors que
  regles §9 décrit `lead_erased`. → Dire laquelle des deux portes sert, et comment le sujet se résout en ids de
  lead (sélecteur crm).
- **M25** TCH133/134 : les parcours viennent de spec-7 §7 (voir B1). Le parcours 11 (rappel reçu) et le bilan d'hier
  exigent un push et l'horloge du serveur : on ne les joue pas en Playwright en CI. → Les rejouer en acceptation
  seulement.

## 3. Mineurs

- TCH47/94/135 : `check_openapi_schema.py --check` n'existe pas (argparse : `--write`, `--write-baseline`,
  `--from-log`, `--reference`, `--strict`) → lancer sans drapeau.
- `docs/rbac-endpoint-inventory.md` est absent du dépôt (le test l'écrit s'il manque,
  `test_endpoint_permission_inventory.py:54`) → le retirer des `Files:`.
- TCH11 : « 6 lignes × 4 colonnes » dans le texte, « 5 usages × 4 » dans la preuve.
- TCH77 : le titre dit « 1 sur 5 · essentiel 0/2 », `aujourdhui.json` donne 0/1 et la maquette du matin « 0 sur 5 ».
  → Asserter depuis l'échantillon.
- TCH6 : `ClePreference` manque au §1 ; les fonctions de `dates_pures` ne sont pas nommées.
- TCH7 : le mécanisme de « bulk_create refusé » n'est pas dit (QuerySet propre combiné à `SoftDeleteManager`).
- TCH12 : `jours_ouvres_entre` est dans `notifications/calendar_utils.py:164` ; pour « sans accents », reprendre
  le patron unaccent de `stock/selectors.py`.
- api.md §5 : `createModuleOutboxStore` est dans `lib/offlineStore.js:137` (et non `offlineOutbox.js:304`).
- `_avec_idempotence` est une méthode d'`IdempotentCreateMixin` (`core/idempotency.py:234`) → « mélanger le
  mixin dans l'`APIView` ».
- `module.config.jsx` figure dans 37 `Files:` → préciser « rien à changer si la route existe déjà (nommé pour
  `check_taches_cablage`) ».
- `g j` → `taqinor:taches:saisir` (api.md §7) : est-ce un « aller à » ou « saisir » ?
- TCH3 : « si la garde le réclame » contredit « Code net : 47 lignes » ; la garde s'abstient d'elle-même
  (`check_api_shapes.py:1200`).
- PACT10 veut le contrat « SEUL sur `main` » : TCH2/TCH3 pourraient entrer dans la PR d'atterrissage.

## 4. Chemins (script `chemins.py`)

- 152 tâches. Chemins hors module : 76 existent ; 3 absents : `records/selectors.py`, `notifications/…/0079_…`
  (créés, voulu), `docs/rbac-endpoint-inventory.md` (mineurs).
- Aucun fichier créé par deux lanes concurrentes d'une même fusion, sauf `module.config.jsx` (append-only,
  `ownership.yml:970` ; « 0 lane-pair merged »). Aucun chemin propre hors des 7 globs ; 0 maquette manquante ;
  propriétaires concordants avec `check_ownership.py --owner-of` (16 fichiers).

## 5. L'en-tête vu d'un agent

Il donne la vérité, le contrat, les gardes, `[BLOCKED]`. Manquent : la fiche (supprimée, B1 : chemins Python/Node,
jonction, format de rendu, `git status` final) ; qui écrit le `[BLOCKED]` (la lane ne touche pas le plan → « dans
le rapport, l'orchestrateur reporte ») ; le format de commit ; les sous-vagues (M3). Contredit la fiche : Django
absent, tests locaux limités aux modules purs (M1).

## 6. La première heure, lane `socle`

1. TCH4 : bute sur les fichiers en trop du gabarit (M5) ; sinon simple (`INSTALLED_APPS` lignes 74-387).
2. TCH5 : **bloque** (B2).
3. TCH6 : faisable ; il devine `ClePreference` et les noms de `dates_pures`.
4. TCH7 → TCH8 : faisables, en devinant la répartition par fichier (M6) et le refus de `bulk_create`.
5. TCH9 : la génération est probablement faisable sur l'hôte (`--check` vérifié ici ; une app neuve n'a pas été
   rejouée). Il devine les fabriques (M7). Les dépendances sont justes : `records 0014_attachment_file_key_index`
   est bien la dernière migration.
6. TCH11, TCH12 : faisables, en devinant la source des réglages (M10).
7. TCH13, TCH14 : **ne peuvent pas avancer** sans `liens_cibles.json` et `item.json` (B6), et les portes de
   visibilité citées sont fausses (M11).
Avis : l'ordre interne est bon et la taille tient (10 tâches, coût 25 = la plus longue lane de F1). Il faut deux
correctifs : couper après TCH12 (TCH13-TCH14 passent au batch 2, derrière `contrats`), et corriger TCH5. Avec B6 et
B7, `etranger-securite` (TCH18) attend lui aussi le socle.

## 7. Acceptations en direct

Injouables telles qu'écrites : aucun compte nommé (avant TCH130, superutilisateur seul) ; aucune donnée de départ
(aucune commande de semis, alors que `SCENARIO.md` en a la matière) ; parcours dépendant de l'historique ou de
l'horloge (« carte monter » = 10 jours, retour d'absence, bilan d'hier, plan du matin du balayage) ; pastille et
push = vrai iPhone ; oracles et gestes dans spec-7 §7 (B1). → Ajouter en F2 `seed_taches_scenario` (local, refusé
en prod : `SCENARIO.md` + 14 jours d'historique) ; par acceptation : compte, semis, jour simulé (`?jour=`, `--jour`
du balayage), oracle chiffré ; ce qui demande l'appareil part dans GATED.

## Bilan

36 tâches examinées, 3 irréprochables. 9 bloquants, 25 majeurs, 13 mineurs.

Bloc de preuve : chaque constat ci-dessus cite le fichier et la ligne lus dans cette session, ou la commande
exécutée ; les comportements à l'exécution (CI, tests à base, navigateur) n'ont pas été vérifiés.

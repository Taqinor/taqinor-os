# Revue de code adverse — fusion 1 « Tâches » (branche `dev-taches`, PR #1447)

Relu le 17/11/2026, en lecture seule, dans `C:\dev\taqinor-os\.claude\worktrees\dev-taches` (tête `da3af541f`).
Diff relu : `git diff origin/main...HEAD` (230 fichiers hors maquettes). La CI de la PR était **en cours** au
moment de la relecture (stage-names en cours, changes en file d'attente) : aucun verdict CI n'est repris ici.
Pas de Django dans l'environnement hôte : `makemigrations --check` **n'a pas été exécuté** (point laissé à la CI).
Les sondes « entrée hostile » ont été exécutées sur les modules purs, avec Django 5.2.19 installé à part (bac à sable).

**Bilan : 0 BLOQUANT, 1 MAJEUR, 7 MINEUR.** Avis : **fusionnable après corrections** (le MAJEUR peut aussi être
corrigé juste après, puisque rien ne l'atteint encore en production ; il doit l'être avant de brancher une seule vue).

## 1. Invisibilité en production — saine côté serveur, deux nuances

Vérifié dans le code :
- **Les 106 routes** posent toutes `PERMISSIONS = [IsAuthenticatedInterne, PermissionTaches]` (une seule variante
  `[*PERMISSIONS, IsAdminRole]`, `views/reglages.py:47`) et chaque méthode lève `PasEncore` (106 `raise PasEncore`
  comptés, aucune méthode sans). `PermissionTaches` lit `user.has_erp_permission('taches_voir')`
  (`authentication/models.py:517`) : superutilisateur → vrai ; rôle fin → la liste ; **compte hérité sans rôle → faux**.
  Résultat par compte : anonyme 401 ; portail 403 (`IsAuthenticatedInterne`) ; administrateur, directeur, commercial,
  technicien, hérité sans rôle → 403 ; superutilisateur → 501. Aucune donnée servie.
- **Routes à jeton** (`capture/`, `flux/<jeton>.ics`, `tuile/`) : `JetonPasEncoreLivre.authenticate` lève toujours
  `AuthenticationFailed` → 401 « Authentification requise. », même avec une session valide ; rien n'est révélé.
- **Rôles** : `taches_voir` est retiré de `DIRECTEUR_PERMISSIONS` (`permissions_registre.py:983-984`), donc
  d'`ADMIN_PERMISSIONS` qui en dérive ; `CANONICAL_SYSTEM_ROLES` (`:1433`) n'utilise que ces listes et des listes
  explicites ; `init_roles` (`init_roles.py:65-78`) idem. Seul `roles/views.py:361` (revue d'accès) prête
  `ALL_PERMISSIONS` aux superutilisateurs, en lecture d'affichage. Aucune dérivation ne l'accorde.
- **Module** : manifeste `installable: False` (`apps.py`), `MANIFESTES.taches.installable: false` (`appSkus.js`).
  Le lanceur, la barre latérale, les apps épinglées, l'atterrissage et les raccourcis `g <lettre>` ne retiennent que
  les modules qui ont des `nav.items` (`useInstalledApps.js:134`, `shortcuts.js`, `prefs.js:116`) : `taches` n'en a pas.
- **Surfaces transverses** : `platform.py` vide ; aucun `admin.py` ; aucune tâche planifiée enregistrée
  (`nocturne.py` n'est appelé par personne) ; l'audit ne suit que `TRACKED_MODELS` (`audit/signals.py:194`) ;
  l'agent SQL a une liste blanche sans `taches` ; la corbeille n'est alimentée que si `record=True`.
- **OpenAPI** : les 106 opérations entrent dans `/api/schema/`, servi à tout compte authentifié
  (`SERVE_PERMISSIONS = IsAuthenticated`, `settings/base.py:838`) : la carte des routes est visible, aucune donnée.

## 2. MAJEUR

**M1 — Forme « assistant » d'une tâche ou d'un projet confidentiel : check-list, `en_attente_de`, lien ERP,
nom d'étape et texte du projet servis en clair.** `serializers/formes.py:405-407` (`elements_checklist[].libelle`),
`:232` (`en_attente_de`), `:294-295` → `lien_de_tache` `:86-91` (`lien.libelle`), `:266-267` (`section.nom`),
`:526,536-537` (`objectif`, `issue`, `bilan` de `ProjetSerializer`). Scénario (dès qu'une vue servira ces formes
sous l'en-tête `X-Taqinor-Assistant`) : un projet confidentiel « Canari » avec une tâche dont la check-list porte
« appeler l'avocat » → le titre devient bien « Tâche confidentielle », mais la check-list, l'étape, le libellé du
devis lié et l'objectif du projet partent au fournisseur d'IA. C'est contraire à `reference/regles.md` §8 (tableau :
« Notes, check-list, `en_attente_de`, lien ERP d'une confidentielle : jamais » pour l'assistant) et ferait échouer le
test canari prévu. Le test actuel (`tests/test_formes.py:183-191`) ne regarde que `notes`, `titre` et `projet.nom`
(la fixture porte `libelle='Prix'`, `lien_libelle='DEV-2026-11-0042'`, non vérifiés).
Correction minimale : dans `_FormeSerializer`, une aide `_masque(obj)` = `assistant and est_confidentielle(obj)` ;
sous elle, `elements_checklist → []`, `checklist` compte seul, `en_attente_de → ''`, `lien.libelle → ''`,
`section.nom → ''` quand le projet est confidentiel ; `objectif/issue/bilan → ''` pour un projet confidentiel.

## 3. MINEUR

1. **Écrans `/taches/*` atteignables par URL pour les comptes hérités sans rôle**, alors que le serveur les
   refuse. `features/taches/module.config.jsx:39` pose `permRepliPalier: true` ; `router/moduleGating.js:86-90`
   admet alors tout compte sans permissions servies au palier `responsable`/`admin`. Un administrateur hérité qui
   tape `/taches/aujourdhui` voit la coquille vide (aucun appel d'API aujourd'hui, donc rien de cassé), en
   contradiction avec `views/base.py` (« jamais le repli des comptes sans rôle fin »). Correction : retirer
   `permRepliPalier` (ET strict palier × `taches_voir`).
2. **La case `taches_voir` apparaît dans l'éditeur de rôles**, groupe « Autres », libellé brut
   (`pages/admin/RolesManagement.jsx:182-190`), et le sérialiseur l'accepte. Un administrateur qui la coche (ou
   « tout cocher ») ouvre à ses utilisateurs des écrans vides et des routes 501 : rien de dangereux, mais le
   module n'est plus « invisible ». Correction : ne pas servir ce code dans `permissions-disponibles` tant que le
   module n'est pas activé, ou au minimum lui donner un libellé « Tâches (bientôt) ».
3. **Lecteur ICS : une seule ligne hostile fait tomber tout l'agenda** (`moteur/ics.py:178`, n'attrape que
   `ValueError`). Exécuté : `DURATION:P999999999W` → `OverflowError` ; `DTSTART;VALUE=DATE:99991231` →
   `OverflowError` (fin + 1 jour) ; `TZID=America` → `PermissionError` sous Windows (`_zone`, `:102-105`, n'attrape
   pas `OSError` ; comportement Linux non vérifié). La docstring promet « un événement illisible est ignoré ».
   Correction : `except (ValueError, OverflowError, OSError)` dans `_rendez_vous` et dans `_zone`. Le pliage des
   lignes reste raisonnable (200 000 continuations : 0,63 s) ; la taille du fichier devra être bornée par le
   futur téléchargeur.
4. **Idempotence : `client_id` long → une ligne silencieusement perdue.** `services/creation.py:186` tronque
   `f'{client_id}:{index}'` à 64 caractères : avec un `client_id` de 62+ caractères, les lignes `:1` et `:10`
   d'un même collage donnent la même clé, la seconde va dans `deja_creees` sans être créée. Correction : borner
   `client_id` (≤ 48) à la validation, ou tronquer la base et jamais le suffixe.
5. **Conversion d'un à-faire personnel d'un collègue.** `services/creation.py:208-211` accepte toute activité
   assignée au compte, y compris un à-faire `personnelle=True` créé par un autre — que XKB4 rend invisible à ce
   compte (`records/views.py:390-393`, et `records/selectors.py` l'exclut). Correction : refuser (404) si
   `activite.personnelle and activite.created_by_id != user.pk`.
6. **Plafond de 100 rappels par compte sans verrou à la première tâche.** `services/rappels.py:94-95` verrouille
   `ReglagesRythme`, qui n'existe pas encore pendant `creer_taches` (créée après les lignes, `creation.py:505-506`) :
   deux envois simultanés peuvent dépasser 100. Effet faible. Correction : créer `ReglagesRythme` avant les lignes.
7. **Annuler un geste revérifie un lien ERP par `resolve_target`** (`services/gestes.py:246-253`) et non par la
   porte unique `selectors/liens.cible_visible` (portée CRM/ventes de l'utilisateur) : un lien vers un lead sorti
   de sa portée depuis le geste est reposé en `ok`. Correction : passer par `cible_visible`.

## 4. Fichiers existants de l'ERP — diff et appelants

- `authentication/views.py:1425-1426` : la condition ajoutée exclut uniquement `app_label == 'taches'` ; aucune
  autre app ne peut être masquée, le verdict d'un compte sans données `taches` est inchangé. Sain (test
  `tests_recovery.py:144-162`).
- `apps/records/selectors.py` (neuf) : filtré société + utilisateur, à-faire d'autrui exclus ;
  `peut_cloturer_activites` rejoue la vraie permission de `marquer_fait` (`IsResponsableOrAdmin`, app `records`
  ∈ `APPS_SANS_MODULE`). `services.py` : deux fonctions neuves, appelées par personne en production. Sain
  (remarque : `.update()` ne journalise pas la clôture dans le fil — voulu pour un à-faire privé).
- `permissions_registre.py` : voir §1. Sain.
- `settings/base.py`, `urls.py`, `.env.example` : ajout d'app, d'un réglage vide, d'un préfixe `taches/` sans
  collision (vérifié). Sain.
- `scripts/check_migration_safety.py` : seul `apps/taches` a un paquet `models/` (vérifié), aucune app existante ne
  voit la garde changer. Sain. `scripts/tests/*` : compte 19 → 20 cohérent.
- `index.css` + `styles/taches/*.css` : 386 sélecteurs analysés, tous sous `.tch` (ou `:where(.tch)`,
  `.dark .tch`) ; aucune règle `html`/`body`/`:root` ; l'ordre d'import ne peut donc rien changer à un écran
  existant. `tokens.css` : **ajouts seuls** de propriétés `--tch-*` dans `:root` et `.dark`, aucun jeton existant
  modifié. Sain.
- `appSkus.js` : une ligne `installable: false`. Sain. `contractSamples.js` : non touché par ce diff.
- `docs/ownership.yml`, `docs/claude-memory/*` : documentaires. Sains.

## 5. Migration `taches/0001_initial.py`

Uniquement `CreateModel` (20), `AddIndex`, `AddConstraint` sur des tables `taches_*` ; aucun `RunSQL`/`RunPython`,
aucune opération sur une table existante. Les 40 noms d'index et de contraintes sont **identiques** à ceux des
`Meta` (comparaison faite). Dépendances : `authentication`, `contenttypes`, `records`, utilisateur — correctes.
Les clés étrangères vers `records.Activity`, `Company`, l'utilisateur et `ContentType` posent un verrou bref sur ces
tables au moment de créer des tables vides : instantané. Réversible (création pure). Généré sous 5.1.15 alors que
`requirements.txt` fixe `Django==5.2.19` : l'en-tête diffère, aucune opération connue ne change entre les deux pour
ces types ; **non vérifié par `makemigrations --check`** (à lire dans la CI).

## 6. Bogues cherchés et non trouvés

- `creer_taches` : tout identifiant passe par `taches_de`/`projets_de`/`sections_de`/`etiquettes_de` ou un filtre
  société + propriétaire ; course au même `client_id` relue après `IntegrityError` sous point de sauvegarde. Sain.
- `planifier` : verrou `select_for_update` sur la tâche du compte, report par `F()`, `lock_version` incrémentée
  (`core/champs_plateforme.py:43-51`). Sain.
- `annuler_geste` : geste du compte seulement, verrou, liste blanche fermée (`_attendus` ignore tout champ hors
  liste ; `JAMAIS` couvre société/propriétaire/lien brut/parent), clés étrangères revérifiées. Sain.
- `__str__` neutre sur les 25 modèles (`StrNeutreMixin`) ; `soft_delete(record=False)` aux seuls appels.
- Analyseur de saisie : 9 entrées hostiles de 10 000 à 27 000 caractères, toutes < 0,1 s ; aucune expression à
  retour arrière catastrophique trouvée. La longueur n'est pas bornée dans `analyser()` : à borner dans la vue.
- `selectors/liens.py` : refus et introuvable répondent pareil (`None`) ; aucune énumération possible.

## 7. Tests manquants avant de brancher les vues

1. Canari au niveau des formes : tâche et projet confidentiels portant « Canari » dans la check-list,
   `en_attente_de`, le lien, l'étape, l'objectif et le bilan → `TacheSerializer` et `ProjetSerializer` en contexte
   assistant ne contiennent pas « canari » (couvre M1).
2. `estAutoriseEntree` sur une route `taches` avec un compte hérité `admin` (permissions `[]`) → `false` (mineur 1).
3. ICS : `DURATION:P999999999W`, `DTSTART;VALUE=DATE:99991231`, `TZID=America` → événement ignoré, pas d'exception.
4. `creer_taches(..., activite=<à-faire personnel créé par B, assigné à A>)` par A → 404.
5. Collage de 12 lignes avec un `client_id` de 63 caractères → 12 tâches créées (ou 400).
6. `call_command('init_roles')` puis aucune ligne `Role` en base ne porte `taches_voir`.

## OPTIONNEL

- Surcharger `soft_delete` sur `Tache`/`Projet` pour forcer `record=False` (aujourd'hui une convention).
- `analyser()` : un plafond de longueur interne (par exemple 2 000 caractères) en plus de celui de la vue.
- Retirer les 106 opérations du schéma OpenAPI tant qu'elles répondent 501.

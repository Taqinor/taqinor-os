# Passation — chantier « Tâches » (gestionnaire de tâches et agenda personnel de Reda)

Écrit le 17/11/2026 par la session du portable de Reda (`Reda_Laptop`), parce que le quota hebdomadaire de tokens
arrive à sa fin. Une autre session (autre PC, autre compte) reprend ICI. Tout ce qui compte est sur GitHub.
**La section 1 (« État à l'arrêt ») est tenue à jour jusqu'au dernier moment : lis-la en premier.**

## 0. La demande et les règles de Reda (ne pas re-demander)

- Reda veut SON gestionnaire de tâches et de projets dans l'ERP, avec l'IA qui l'aide à prioriser, planifier et tenir
  son rythme (« si je dis que je veux en faire plus, il m'y aide ; si je dis que ça suffit, il m'aide à garder le
  pas »), présent sur son iPhone. « Le meilleur, en une fois » : conception en profondeur (faite), construction, test
  en direct, corrections.
- **Aucune question à Reda** (« je ne veux plus que tu me poses de questions ») : décider seul, option la plus sûre,
  et noter chaque choix. Décisions fondateur déjà prises : `docs/claude-memory/taches-decisions-fondateur.md` (sur main).
- Règles de maison : rapports en français simple ; chaque sous-agent lancé avec `model:` + effort explicites ; la CI
  vérifie en premier (jamais de base de test locale, jamais de docker avant un push) ; s'arrêter AU MERGE (pas de
  deploy) ; fusion par `gh pr merge <n> --auto --merge` (merge queue, jamais squash, jamais force-push) ; Auto-fix
  allumé sur toute PR dès l'ouverture, sans demander.

## 1. État à l'arrêt

(Mis à jour en dernier — voir la fin du fichier, section « Journal de fin de session ».)

## 2. Où est quoi

| Quoi | Où |
|---|---|
| Plan (174 tâches `TCH<n>`, 4 fusions F1-F4), cases cochées = vérité | `docs/plans/PLAN_TACHES.md` sur la branche `dev-taches-f2` |
| Référence qui fait foi (données, API, règles, textes) | `docs/taches/reference/` (sur main) |
| Conception, arbitrages A1-A18, consignes de construction | `docs/taches/conception/` (sur main) |
| 81 maquettes + jeu d'exemple `SCENARIO.md` | `docs/taches/maquettes/` (sur main) |
| Dossier de travail (briefs, relectures, raccords, cette passation) | `docs/taches/travail/` sur la branche `claude/erp-task-manager-ai-f8db1b` (jamais mergée) |
| **Fusion 1** (socle invisible) | MERGÉE sur main — PR Taqinor/taqinor-os#1447 |
| **Fusion 2** (cœur utilisable) | branche `dev-taches-f2`, PR brouillon Taqinor/taqinor-os#1454, Auto-fix allumé |
| Code | `backend/django_core/apps/taches/`, `frontend/src/{features,pages}/taches/`, `frontend/src/api/tachesApi.js`, `frontend/src/styles/taches/` |

Fichiers de travail à lire avant de relancer quoi que ce soit (branche `claude/erp-task-manager-ai-f8db1b`) :
- `docs/taches/travail/brief-lane-f2.md` — le brief commun donné à chaque lane (à réutiliser tel quel) ;
- `docs/taches/travail/ecarts-f2.md` — TOUS les raccords à faire entre écrans et serveur, déclarés par les lanes
  (sections A à J) ; les deux lanes de raccord travaillent dessus ;
- `docs/taches/travail/revue-code-f1.md` — relecture adverse de la fusion 1 (tout corrigé).

## 3. Comment on construit (recette éprouvée)

1. `python scripts/plan_lanes.py docs/plans/PLAN_TACHES.md --workers 8 --wave-size 80 --group "Fusion F2"` donne les
   lanes, leur ordre et leur modèle.
2. Une lane = un sous-agent `isolation: worktree`, lancé **UN PAR UN** (un appel par message : à plusieurs en même
   temps la création des worktrees dépasse le délai sur un disque plein). **Jamais** d'agent non isolé envoyé vers un
   worktree fait à la main : un hook refuse ses écritures.
3. Le worktree d'un agent part de `origin/main` → première consigne de chaque lane :
   `git fetch origin dev-taches-f2 && git checkout -B lane/<nom> origin/dev-taches-f2`.
4. Le prompt d'une lane = branche + liste ordonnée de tâches + « lis en entier le brief commun » + particularités +
   le bloc d'ancrage (« Before reporting progress, audit each claim… ») mot pour mot.
5. Au retour : `git branch --contains <sha>` (le SHA annoncé est bien sur la branche de lane), puis pli dans le
   worktree de `dev-taches-f2` par `git merge --no-ff <sha>`, cocher les tâches dans le plan + une ligne DONE LOG,
   commit, push.
6. Sur l'hôte (Windows) : seuls tournent `manage.py check`, `makemigrations --check`, les tests SANS base, flake8,
   eslint, vitest ciblé. Commande Python :
   `$env:PYTHONPATH='C:\dev\wpstub'; $env:PYTHONIOENCODING='utf-8'; & "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe" manage.py …`
   (sur un autre PC : n'importe quel Python avec Django 5.x et les dépendances du backend ; `C:\dev\wpstub` est un
   faux module `weasyprint` vide, à recréer si besoin). **Les tests avec base ne tournent qu'en CI.**
7. Avant un push de la branche d'intégration : `python scripts/check_openapi_schema.py --write` (≈ 1 min 30) si des
   routes ou des sérialiseurs ont bougé, puis `python scripts/codemap_fingerprint.py --write` ; `--check` des deux.
8. Avant de retirer un worktree de lane sous Windows : casser d'abord la jonction
   (`cmd /c rmdir <worktree>\frontend\node_modules`), sinon la suppression vide le `node_modules` visé.
9. Réservations de plan (deux PC en même temps) : `python scripts/plan_claims.py list` ; cette session tient
   `file:docs/plans/PLAN_TACHES.md app:taches app:records app:roles app:erp_agentique app:scripts app:authentication`
   sous le propriétaire `Reda_Laptop/erp-task-manager-ai` (bail de 6 h : périmé, il se reprend par `claim`).

## 4. Ce qui reste, dans l'ordre

**Fusion 2** (64 tâches + 6 acceptations)
1. Plier les lanes encore ouvertes (voir section 1) : raccord serveur, raccord écrans, sécurité/plafonds
   (TCH151, TCH128, TCH129, TCH19), corrections de la première CI.
2. CI verte sur l'état plié (première exécution des ~400 tests à base : prévoir 2 ou 3 cycles).
3. Activation pour l'Administrateur SEUL : TCH130 (droit), TCH131 (manifeste, navigation, traductions), TCH132
   (route d'accueil mobile) — une lane opus, tâches dans cet ordre. Puis bout en bout Playwright TCH133, TCH134.
4. Acceptations en direct TCH136-TCH140, TCH144 : jouées par l'ORCHESTRATEUR sur la pile locale
   (`docker compose up`, `manage.py migrate`, `manage.py seed_taches_demo`, rebuild du front), jamais par une lane ;
   enregistrement `docs/audits/acceptation/…`. Corriger ce qu'elles trouvent (c'est le « L3 n° 10 » : test en direct).
5. TCH94 : régénérer les dérivés, dé-geler la fusion 3 dans le plan (retirer `[GATED: attend la fusion F2 sur main]`).
6. PR #1454 : `gh pr ready 1454` puis `gh pr merge 1454 --auto --merge`. Dire à Reda « mergé — l'auto-deploy suit ».

**Fusion 3** (iPhone : grande tuile Scriptable, capture Siri, notifications, flux d'agenda ; Copilote) : 29 tâches
+ 3 acceptations. **Fusion 4** (avancé, ouverture aux autres rôles — TCH168 attend un mot de Reda) : le reste.
Puis deux relectures finales : ergonomie et beauté sur le rendu réel (captures iPhone 390 px, clair et sombre,
comparées aux maquettes), et relecture adverse du code. Rapport final à Reda en français simple : ce qui est livré,
ce qui n'est pas vérifié (essai sur un vrai iPhone), ses gestes (lien du raccourci Siri, Scriptable, abonnement à
l'agenda, `VITE_VAPID_PUBLIC_KEY` en prod, fournisseur d'IA en prod) — liste dans `docs/taches/README.md`.

## 5. Pièges déjà payés

- Un pli qui répond « Already up to date » = la lane a committé ailleurs : vérifier `git branch --contains`.
- `nplusone` est actif en CI : jamais de liste Python dans `_prefetched_objects_cache` ; un `TestCase` n'a jamais
  d'attribut `client` ; aucun `skipTest`.
- `tests/test_routes.py` : l'aide `est_construite()` fait que les tests « 501 » ne regardent que les routes encore
  vides — ne pas la réécrire.
- Les lanes déclarent des « écarts » en fin de rapport : les recopier dans `ecarts-f2.md` AVANT de les oublier.
- Le module reste invisible tant que TCH130-TCH132 ne sont pas pliées : `taches_voir` n'est accordé à aucun rôle.

## Journal de fin de session

### État au 17/11/2026, quota à 95 % (dernière mise à jour de la session du portable)

**Sur GitHub**
- `main` : fusion 1 mergée (#1447).
- `dev-taches-f2` (PR brouillon #1454, Auto-fix allumé) : tête `de17e63b5` (3e tour de corrections CI plié). **63 des 64 tâches de la fusion 2 sont
  pliées et cochées** (115 tâches cochées sur 174 au total). Tout le code de la fusion 2 y est : serveur, écrans,
  raccords des deux côtés, semis, sécurité, plafonds, activation Administrateur seul, bout en bout Playwright.
- Aucune lane en cours, aucune branche de lane non pliée. Rien d'important ne vit seulement sur le portable.

**Ce qui reste pour la fusion 2, dans l'ordre**
1. **CI verte sur la tête.** Deux tours de rouges ont été corrigés ; le tour sur la version complète (raccords
   écrans, défauts connus, bout en bout) n'a pas été lu. `gh pr checks 1454 --repo Taqinor/taqinor-os`, puis une
   lane sonnet par tour (prompt modèle : « corrige le test s'il est faux, le code sinon, jamais d'assertion
   élargie ni de test sauté ; plafond de requêtes sans N+1 = poser la mesure »). À surveiller en premier :
   - `frontend/e2e/taches-*.spec.js` (TCH133, TCH134) : JAMAIS exécutés, écrits à la lecture du code ; les mesures
     d'accessibilité (axe 0 violation, cibles 44 px, texte à 130 %) sont strictes : un rouge y montre un vrai écart
     d'écran à corriger dans l'écran, pas dans le test. Les specs sont branchées par 6 lignes ajoutées à
     `.github/workflows/ci.yml` (lane 2 du shard e2e) et utilisent le compte `demo_admin` de `seed_demo`.
   - `tests/test_plafonds.py` : `agenda/` rabaissé de 35 à 28 après correction (une seule lecture) — la CI mesure.
   - `tests/test_seed_demo.py` : « 3 sur 5 » à 15 h, Benali 5 ouvertes, En attente 1.
   - Les tests qui appellent les 27 fonctions de service renommées avec `_` (TCH151).
2. **Acceptations en direct TCH136-140, TCH144** (orchestrateur, pile locale : `docker compose up`, `migrate`,
   `TACHES_DEMO_PASSWORD=… manage.py seed_taches_demo`, rebuild du front, parcours dans un vrai navigateur à 390 px
   et 1440 px, clair et sombre, comparés aux maquettes). C'est aussi le « L3 n° 10 » : corriger ce qu'on y trouve.
   **Ne pas merger #1454 avant** : le pli contient l'activation → dès le merge + deploy, l'Administrateur voit le module.
3. **TCH94** : régénérer les dérivés, retirer `[GATED: attend la fusion F2 sur main]` (ouverture de la fusion 3).
4. `gh pr ready 1454` puis `gh pr merge 1454 --auto --merge`. Dire à Reda : « mergé — l'auto-deploy suit ».

**Décisions prises seul pendant cette session (à relire, aucune ne demande Reda)**
- Coupe-circuit `balayage_actif` : il ne coupe que l'ENVOI de sollicitations ; clôture, purges et revérification des
  liens tournent toujours pour une société où le module est activé.
- Un compte neuf peut dire son objectif avant d'avoir une tâche (`ReglagesRythme` créé au premier `POST rythme/`
  ou `PATCH reglages/`) → `reference/donnees.md` dit encore « créée uniquement par creer_taches » : À CORRIGER.
- « Ailleurs dans l'ERP » : jamais de compteur à 0 inventé ; `approbations` omis (pas de porte publique).
- Les activités ERP closes qui portent une tâche ne comptent pas dans les « faites ».
- Plafonds de requêtes posés à la MESURE de la CI : `badge/` 11, `journee/proposition/` 25, `agenda/` 35 (cible 16 :
  **N+1 probable à corriger**, lots répétés tâche + rappel + check-list), `projets/{id}/vue/` 20, `recherche/` 10.

**Défauts connus à reprendre (aucun n'est en production)**
- **À VÉRIFIER AVANT DE DIRE À REDA « c'est activé » : son propre compte.** `taches_voir` est donné au RÔLE
  Administrateur ; un compte « hérité » (palier admin SANS rôle fin) ne l'a pas — c'est voulu (jamais de repli), et
  c'est ce qui a fait échouer les 57 specs e2e (`demo_admin` de `seed_demo` est un compte hérité → 403). Regarder en
  lecture seule sur la prod (accord permanent) si le compte de Reda est superutilisateur ou porte le rôle
  Administrateur ; sinon son geste est : Paramètres → Utilisateurs → se donner le rôle « Administrateur » (à écrire
  dans `docs/taches/README.md` et dans le rapport final).
- E2E : le 3e tour a levé le 403 en passant `demo_admin` superutilisateur DANS LE SHARD 2 de la CI seulement
  (6 lignes de `.github/workflows/ci.yml`). Les 57 tests n'ont donc ENCORE JAMAIS atteint leur vrai contenu : le
  prochain run dira les vrais écarts (sélecteurs, écrans, accessibilité). Si ce passage en superutilisateur gêne
  d'autres specs du shard 2, repli plus propre : semer `seed_taches_demo` dans ce shard et connecter les specs
  Tâches avec `demo_taches` (rôle de test portant `taches_voir`).
- Plafonds de requêtes posés à la mesure de la CI (tour 3) : aperçu de saisie 11, aujourdhui sans familles 26,
  badge 13, liste des projets 14, proposition 27, recherche 12, vue d'un projet 22, agenda 28 (à confirmer). Seul
  l'agenda a un test « ne grandit pas » : en ajouter un pour proposition et vue d'un projet avant de s'y fier.
- Semis de démonstration : à 15 h il rend « 4 sur 5 » (l'activité ERP close compte) alors que les maquettes et
  `SCENARIO.md` disent « 3 sur 5 » → changer le semis (lier l'activité à une tâche), pas le calcul. Société de
  démonstration = `demo-taches` (séparée de `taqinor-demo`). Voir `ecarts-f2.md` §J pour le reste.
- Pastille « À trier » de la barre d'onglets : non faite (demande `BottomTabBar.jsx` et un compteur léger).
- « En faire des sous-tâches » : le parent est créé dans le même lot et n'a pas d'id → choix serveur à faire
  (index de ligne parente).
- « Annuler » d'un geste autre que cocher ne remet pas la progression du jour (la route `annuler/` ne la rend pas).
- `avant_id` / `apres_id` ont deux sens (tâches : voisin qui précède ; projets : « juste avant lui ») : documenté
  dans `api.md`, pas unifié.
- `reglages-societe/` répond encore 501 ; `mes_donnees.json` montre 2 clés de `reglages_rythme` sur l'objet entier.
- Jamais vérifié : rendu réel sur iPhone (390 px, clair/sombre), cibles 44 px, clavier virtuel, IndexedDB réel.

**Machine de cette session** : les worktrees `…\.claude\worktrees\agent-*` de cette session sont des copies de
lanes déjà pliées (sauf raccord écrans) ; ils peuvent être retirés (casser d'abord les jonctions node_modules).

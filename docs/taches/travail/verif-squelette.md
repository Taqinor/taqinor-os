# Vérification contradictoire du squelette de plan (`plan-squelette.md`, 144 TCH)

Regard neuf, lecture seule. Scripts jetables : `docs/taches/travail/verifsq/` (`parse.py`, `checks.py`, `own_test.py`,
sorties `pl1/pl2/pl3.txt`, copie de registre `ownership-copie.yml`). Bilan : **4 BLOQUANTS, 12 MAJEURS, 15 MINEURS**.

## 0. Ce qui tient (vérifié)

- `checks.py` (144 tâches) : 0 `@after` inconnu, en avant ou vers une fusion ultérieure, 0 cycle. Seul
  `FT/module.config.jsx` (append-only, `--owner-of`) est partagé entre lanes d'une même fusion.
- `plan_lanes.py --group "Fusion Fk"` : F1 47 tâches / 11 lanes / 21 vagues, F2 47 / 9 / 7, F3 41 / 11 / 13,
  0 union, 0 refus ; acceptations listées « orchestrateur ».
- PACT11 : seuls `urls.py` et `selectors.py` (nom exact) sont producteurs (`plan_lanes.py:1375`, `:1398`).
- Propriété : §4 confirmé par `--owner-of` ; le bloc `taches` + `plans:` sur une copie du registre, essai F1 comme
  `PLAN_TACHES.md` : « OK — 18791 fichiers… 30 plans vérifiés » (`own_test.py`).
- 100 routes recomptées. Migrations additives (0079 = `choices` seuls, libre : dernière 0078). `init_roles` tourne
  au déploiement (`scripts/auto-deploy.sh:320-321`) : l'octroi de TCH130 atteint les sociétés existantes.

## 1. BLOQUANTS (la CI ou la production casserait)

**B1 — En F1, les composants seront « inatteignables » (classe 1) : `stage-names` passera au rouge.**
`check_ecrans_atteignables.py:46-48` contrôle TOUT `.jsx` non-test sous `features/<app>/`, et `:831-838` signale
ceux que le graphe des routes n'atteint pas. TCH44-TCH46 créent 8 composants sous `FT/ui/` (LigneTache, CaseRonde,
Etoile, FeuilleACrans, SelecteurProjet, BarreSelection, BoutonCopilote, BandeauConflit), mais les pages de TCH43
sont vides et ne les importent pas. La base ne peut pas grandir (`:154-158`, `--write-baseline` refuse les ajouts).
*Correction* : TCH44-TCH46 nomment `FT/coquille/CoquilleTaches.jsx` et `PT/Aujourdhui.jsx` (même lane, en série) et
y montent chaque composant (hôtes globaux dans la coquille, ligne vide dans la page) ; ou bien une planche routée
`/taches/planche` marquée `// contextuelle:` et retirée par TCH131.

**B2 — Les échantillons de contrat doivent avoir une enveloppe ; « octet pour octet » est faux.**
Chaque `contract_samples/*.json` doit porter `endpoint` (« VERBE /api/... ») et un `exemple` qui est un objet.
Sinon la garde émet un constat (`check_api_shapes.py:1158-1166`, `:1047`) et ce constat la fait échouer
(`:1994`, `:2171-2186`). Or les échantillons de forme (`item`, `tache`, `tache_ecrite`, `proposition`,
`carte_du_moment`, `erreurs`, `liens_cibles`) n'ont pas de route propre. *Correction* : dans TCH2-TCH3, donner à
chacun la route qui le renvoie ; envelopper `{endpoint, exemple, pourquoi}` (le modèle est
`apps/adsengine/contract_samples/engine_action_erreur.json`) ; changer la preuve en « `exemple` = l'exemple
d'api.md ».

**B3 — Les 100 vues « 501 » telles qu'écrites rougiront deux gardes.**
(a) `_shape_of_node` (`check_api_shapes.py:321-339`) lit tout `return Response({...}, status=…)` sans regarder le
statut. Une vue qui fait `Response({"detail": …}, status=501)` aura donc la forme `{detail}`, comparée à
l'échantillon dans les deux sens (`:1195-1204`). Une déclaration dans `ECHANTILLONS_POSES_AVANT_LEUR_VUE` ne fait
que NOMMER l'échantillon (`:1348-1363`) : elle ne suspend aucune comparaison (cela répond au trou 11 de
l'architecte). (b) `check_openapi_schema.py --strict` est lancé en CI (`ci.yml:702`) avec une base vide
(`openapi_schema_allow.txt` : 6 lignes de commentaire). Donc n'importe quel avertissement « unable to guess
serializer » ou un paramètre de chemin sans type casse la CI : il n'existe aucun cliquet. *Correction* : TCH15 impose
des classes `APIView`, aucun `@api_view` (voir M9). Chaque méthode fait `raise PasEncore()` (une `APIException` à
501, sans aucun `return`). `@extend_schema(request=…, responses=…)` est posé sur les 100 opérations, avec des
convertisseurs typés (`<int:id>`, `<str:cle>`). TCH15 est découpé en 4 tâches (voir M12).

**B4 — Dès que `PLAN_TACHES.md` sera sur `main`, une boucle « work on all plans » le prendra sans `--group`.**
Le pool de CLAUDE.md inclut tout `docs/plans/PLAN_*.md` ; `plan_claims.py list` (17/11) montre `acc8` en boucle sur
14 plans. Après la fusion de F1 (claims rendues, D-CLAIMS-MERGE), la boucle suivante construira F2 et F3 d'un bloc,
sans `--group` (union de 55 tâches, mesurée par l'architecte), et TCH130 pourrait partir sans acceptation
(`check_acceptation.py` ne lit que les `PLAN_AUDIT_*`). *Correction* : chaque tâche de F2 et de F3 commence par `— [GATED: attend la fusion Fk-1 sur
main]`, ce qui la rend non constructible (`plan_lanes.py:753-770`). L'orchestrateur TCH retire ce marqueur au début
de la fusion, dans le commit de cette fusion.

## 2. MAJEURS

**M1 — L'invisibilité est fausse pour les comptes sans rôle.** Avec `ScopedPermission`, le droit passe par
`_user_has_or_legacy` (`core/permissions.py:273-279`). Un compte sans rôle fin mais `is_responsable` passe
(`:239-244`). Le §2.1 (4) du squelette (« 403 pour tout rôle ; seul un superutilisateur ») est donc inexact.
*Correction* : TCH15 et TCH95 utilisent une permission stricte (`user.has_erp_permission`) ; `test_routes.py` vérifie
qu'un compte sans rôle et responsable reçoit 403.

**M2 — Des changements visibles dès F1, alors que le squelette dit « invisible ».** (a) Les 4 `EventType` apparaissent
dans les préférences de notification de chaque utilisateur (`notifications/services.py:911`). Le masquage
(`module_map.py:68-80`) ne cache que les modules ÉTEINTS ; `taches` est allumé par défaut (`core/feature_flags.py:110-128`,
et une société sans plan voit tout, `apps/parametres/feature_flags.py`, en-tête). (b) Un manifeste `installable`
apparaît dans le catalogue des Applications (`core/feature_flags.py:215-230`). (c) La case `taches_voir` apparaît dans
l'éditeur de rôles, et un administrateur peut l'accorder dès F1. *Correction* : déplacer TCH20-TCH21 (et TCH19) en F3
B, rien ne les attend avant TCH98 ; le manifeste de TCH4 met `installable: False`, et TCH131 le passe à `True`
(ajouter `T/apps.py` à ses `Files:`).

**M3 — `docs/api-contracts.md` n'est régénéré nulle part.** Une dérive de ce fichier fait échouer la garde
(`check_api_shapes.py:2171`, `:2187-2192`). Chaque vue de F2 qui rend un dictionnaire lisible le modifie : 8 lanes
réécriraient ce même fichier. *Correction* : l'ajouter aux `Files:` de TCH47, TCH94 et TCH135 (`--write`), et
l'interdire aux lanes.

**M4 — Les régénérations partent trop tôt.** TCH47 n'attend que TCH15 et TCH43, donc il part à la vague 19
(`pl1.txt`), avant TCH44-TCH46. Or l'empreinte de structure liste chaque fichier de `features/` et de `pages/`
(`codemap_fingerprint.py:179-182`). TCH94 n'attend pas TCH81, TCH87 ni TCH93. TCH135 n'attend pas TCH99, TCH106,
TCH110, TCH116, TCH120 ni TCH122. *Correction* : `@after` sur la dernière tâche de CHAQUE lane de la fusion.

**M5 — Les sous-vagues ne sont pas outillées.** En F1, les lanes 0b ont besoin de tâches de la lane `socle`. En F3,
les lanes C ont besoin des lanes B. Or un worktree d'agent part d'`origin/main` (mémoire `worktree_git_mechanics`,
« Branch base ») : sans consigne, une lane construit sur un `main` nu. *Correction* : écrire dans le plan « pousser la
branche d'intégration ; prompt de lane : `git fetch && git checkout -B <x> origin/<intégration>` + marqueur
vérifiable ». La raison (2) du §2.1 est à corriger : ce mécanisme existe, ce qui justifie les 3 fusions, ce sont la
taille (WOW23) et l'isolement d'une CI rouge.

**M6 — Les acceptations de F2 rejouent des fonctions qui n'arrivent qu'en F3.** TCH136 rejoue le hors ligne
(TCH100) ; TCH137 la pastille (TCH101, TCH124) et le plan du matin par notification (TCH98) ; TCH138 « Planifier ma
semaine » (TCH106). Elles ne peuvent pas passer avant le push de F2. Par ailleurs, les parcours 11 (Rappel) et
18 (clavier) de spec-7 §7 ne sont joués ni en acceptation ni en e2e. *Correction* : déplacer ces étapes dans
TCH139-TCH141 ; ajouter le parcours 11 à TCH140 et le parcours 18 à TCH144.

**M7 — « Le reste grisé hors ligne » n'a pas de chemin.** C'est une fonction ESSENTIELLE (spec-7 §4 l.112-113,
§9 ; regles §4.11). TCH100 (F3) ne touche aucun écran de F2. *Correction* : TCH43 pose dans la coquille dès F1 un
`useEnLigne()` (un contexte) ; les écrans de F2 l'utilisent pour griser ; TCH100 ajoute la file d'envoi.

**M8 — Des preuves qui ne prouvent rien.** (a) `check_services_appeles.py` ne surveille que
`APPS_SURVEILLEES = ("calepinage", "crm")` : la preuve de TCH37 ne teste rien. (b) `check_roles_mirror.py` compare le
vocabulaire des rôles de PRODUITS (en-tête du script), pas les droits : la preuve de TCH130 est hors sujet.
(c) « cibles ≥ 44 px » (TCH44) et « texte à 130 % sans défiler » (TCH76) ne se mesurent pas dans jsdom.
*Correction* : une tâche deploy en F1 ajoute `"taches"` à `APPS_SURVEILLEES`, ou la preuve est retirée ; pour TCH130,
`init_roles` + `apps/roles/tests.py` ; la mesure (c) va dans TCH134 (Playwright).

**M9 — La convention des vues n'est pas écrite, et `check_tenant_isolation` piège les fonctions.** Une vue
`@api_view` doit montrer un filtre de société EFFECTIF (`check_tenant_isolation.py:23-31`, `APPELS_DE_PORTEE` `:82`).
Un `get_queryset` de `Generic*APIView` doit contenir un jeton de `COMPANY_TOKENS` (`:71-74`). `taches_de(user)` n'est
ni l'un ni l'autre. *Correction* : n'utiliser que des `APIView` nues dans `taches`, ou bien une tâche deploy en F1 qui
ajoute `taches_de` et les autres sélecteurs à `APPELS_DE_PORTEE`.

**M10 — La coexistence avec `acc8` se contredit.** Le §4 dit « PLAN_TACHES ne tourne JAMAIS en même temps » que les
plans d'audit DEPLOY, SECURITE, PARAMETRES, ANALYSE et TRANSVERSE. Or `acc8` les tient en boucle (claims à 0,2 h),
donc TCH ne partirait jamais. *Correction* : une claim `file:<chemin>` par fichier étranger avant chaque lane (la clé
`app:` n'a pas de sens pour `scripts/`, `settings/` ou `providers/`), et un refus fait passer à une autre lane.

**M11 — Le chemin critique de F1 est de 21 vagues, pas de 15.** `socle-front` n'attend que TCH15 sur le papier
(`pl1.txt`, vagues 17-21). En réalité, TCH41 et TCH43-TCH46 n'ont besoin que des contrats. TCH2, TCH3 et TCH10 sont
mis en série dans `socle` sans dépendre de TCH4-TCH9. *Correction* : une lane `taches/contrats` (TCH2-TCH3) en tête ;
TCH10 dans `pur-*` ; `socle-front` part après TCH3 et seul TCH42 attend TCH15. On gagne environ 5 vagues.

**M12 — Tâches trop grosses ou impossibles en lane.** TCH15 : à découper en 4 (§3.1-§3.4). TCH36 (créateur unique,
idempotence) : opus, pas sonnet. TCH129 « mesuré » exige une base, qu'une lane n'a pas : poser les cibles d'api.md
§10 et laisser la CI mesurer.

## 3. MINEURS

1. TCH28 et §5.3 disent « 61 exemples », alors que regles.md §6.10 en a 65 (`regles.md:741-745`, 65 lignes) :
   les exemples 62-65 sont orphelins.
2. `contractSamples.js` est un lecteur générique (`exempleContrat(app, nom)`) ; il ne demande aucun export par
   échantillon. Retirer ce fichier deploy de TCH2-TCH3.
3. La maquette `ecran-aujourdhui-retour-bas.html` n'est citée par aucune tâche (48 maquettes, pas 47).
4. Non cités comme source : textes.md §1 et §2.2, §2.3, §2.9, §2.16-§2.19 (erreurs, carte du moment, révélations,
   annonces). Les chaînes d'écran risquent d'être inventées.
5. La mise en page de bureau « agenda du jour à droite, colonne des projets » (spec-7 §4 l.145) n'a pas de tâche.
6. Le trou 2 n'existe pas : api.md §7 l.560 et l.569 donnent déjà `?ouvrir=bilan` (R20, rév. 2.1).
7. Le trou 10 : `check_acceptation.py` existe et tourne dans `stage-names` (`ci_guards`), mais ne lit que les
   `PLAN_AUDIT_*`. Les enregistrements `TCH/` ne sont donc gardés par personne : le dire.
8. « En faire mon accueil » (TCH79, F2) échouera tant que TCH132 (F3) n'a pas élargi `MOBILE_HOME_ALLOWED_ROUTES`.
   Masquer l'entrée jusqu'à F3.
9. TCH119 cite `focusedRecordShortcuts.test.jsx` et `entityRoutes.test.jsx`, qui manquent dans ses `Files:`.
10. Aucune tâche ne consigne D-TCH-1 à D-TCH-5 dans `docs/claude-memory/` (règle « Shared Claude memory »).
11. Lanes `pur-*` : interdire de créer un `__init__.py` (ceux de TCH4 et TCH10 arrivent par le fold ; un paquet
    d'espace de noms suffit pour `unittest`), sinon conflit add/add.
12. TCH5 : poser `taches_voir` en FIN de liste, le plus sûr face au golden `registre_permissions.json` (sous-suite
    ordonnée, AUD407).
13. Règle à écrire : aucun modèle en F2 (un besoin de schéma → `[BLOCKED]`, part avec TCH121).
14. `--write` d'OpenAPI exige Django sur l'hôte : prévoir l'artefact CI (`ci.yml:705-712`), soit un cycle.
15. `selectors/liens.py` (TCH13) contre `selectors/erp.py` (donnees.md §5) : aligner.

## 4. Couverture (orphelins seulement)

- **Référence → tâches.** Orphelins : exemples rythme 62-65, maquette `retour-bas`, mise en page de bureau, textes
  du MIN-4, grisé hors ligne (M7), parcours 11 et 18 en direct (M6), `api-contracts.md` (M3), D-TCH en mémoire.
  Modèles, invariants, routes, actions, cartes, tâches planifiées et types de notification sont tous couverts.
- **Tâches → référence.** Inventions inutiles : les exports de `contractSamples.js` (MIN-2). Deux preuves citent une
  garde hors sujet (M8).
- **Transverses.** Traductions, accessibilité (1)-(8), révélations, Vie privée, e2e, `ownership.yml` : couverts.

## 5. Production entre les fusions

- **Après F1** : tables vides, aucun beat (bien). Mais visibles : 4 types de notification, la carte des
  Applications, la case de droit, l'API pour les sans-rôle (M1, M2). `_traces_du_compte`, `notify(badge=None)` et
  `records/selectors.py` ne changent rien d'existant.
- **Après F2** : backend invisible ; les receivers exigent `taches_voir` + `ReglagesRythme` (regles §9), donc rien
  n'est écrit pour les utilisateurs actuels.
- **F3** : beats avec leur code complet, droit accordé par `init_roles` ; l'acceptation avant le push n'est pas
  garantie (B4).

## 6. Coût et avis sur les 3 fusions

| | Agents en parallèle | Chemin critique (vagues de `plan_lanes`) | Cycles de CI à prévoir |
|---|---|---|---|
| F1 | 7, puis 3 | 21 (environ 16 après M11) | 2-3 (OpenAPI `--strict`, échantillons, écrans, empreinte) |
| F2 | 8 | 7 | 2 (api-contracts, budgets, instantané) |
| F3 | 8, puis 1-2 | 13 (la lane `final` en série) | 2-3 (e2e, i18n, OpenAPI) |

Total : environ 6 à 8 cycles. Les migrations neuves manquent le cache WOW8, mais le delta reste court (WOW8-INCR).

**Avis.** Garder 3 fusions : 2 donneraient plus de 90 tâches non fusionnées et une activation mêlée au backend.
Rendre F1 réellement invisible et plus courte (TCH19-TCH21 en F3, lane contrats, sous-vagues outillées M5). F3
concentre le risque (activation, e2e, 6 acceptations) : `[GATED]` (B4) et acceptations recentrées (M6). Un
découpage plus simple déplacerait ce risque sans le retirer.

## 7. Non vérifié dans cette session

`check_taches_cablage` et `check_plan_taches_mixtes` sur les essais (pas relancés) ; les avertissements réels de
drf-spectacular (B3, déduits) ; les comptes sans rôle en prod (M1) ; l'écran Applications (M2b, déduit de
`catalogue_modules`). B1-B3 sont déduits du code des gardes, sans app d'essai exécutée.

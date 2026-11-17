# Vérification contradictoire — specs 4, 6a, 6b

Lu : consignes, socle (§8 compris), spec-4, 6a, 6b, spec-3 §1-§5. Recalculs : `verif46/regles4.py`, `owners.py`, `logiques.py` (stdlib). `python scripts/check_ownership.py` → « OK — 18791 fichiers… 29 plans vérifiés ». Backend relatif à `backend/django_core/`, front à `frontend/src/`.

Bilan : 1 BLOQUANT, 9 MAJEUR, 20 MINEUR.

## BLOQUANT

**B1 — `aujourdhui.json` incompatible entre spec-3, 6a, 6b et 4 : PACT10 impossible.**
Preuve : spec-3 §5 a `agenda` (poses, interventions) et `ailleurs:{approbations,mentions,lien}`. 6a §5 ajoute `obligations` (visites, interventions — en double —, touches), `ailleurs:{…,url}`, `suggestions`, `a_convertir`. 6a §3.5 met la visite dans `journee`, son §5 dans `obligations`. Pastille : 6a « tâches seulement » ; 6b §2 « `jour_prevu`=J + activités dues ». Or spec-3 §3.1 r.4 range aussi `echeance=J` dans la journée : le « UN sélecteur » de 6b contredit sa définition. Les bloquées et pauses de spec-4 §3.C ne sont exclues ni de la pastille, ni du flux, ni de la tuile.
Correction : une tâche contrat d'abord. Interventions une seule fois (bandeau `agenda`), clé `lien`. Pastille = ouverts de essentiel + journée + ce_soir (règle spec-3, `echeance=J` comprise) + activités dues J, moins bloquées et pauses. Même filtre pour `compter_journee`, `tuile/` et `flux/`.

## MAJEUR

**M1 — « L'icône ouvre Ma journée » (D-TCH-2) : le mécanisme ne marche pas depuis `/`.** 6b §7, 6a §10. Preuve : `start_url:'/'` → `rootLoader` → `resolveLandingFromAuth` (`router/index.jsx:316`) → `/apps` (`pages/preferences/prefs.js:117,124`). `mobile_home_route` n'est lu que par `Dashboard.jsx` (`/dashboard`), `Login.jsx` et `PreferencesPanel.jsx`. Correction : `setLandingModule('taches')` (`prefs.js:81`), qui renvoie `nav.items[0].to` (`:120-121`). La première entrée de nav de `taches` est donc Ma journée. Tester `resolveLandingPath`.

**M2 — Routes contradictoires.** 6a : `/taches` dans la liste blanche. 6b : `/taches/aujourdhui`, `?tache=`. Spec-3 §3.9 : `/taches?tache=`. Le même frozenset (`authentication/selectors.py:184-192`) est édité deux fois. Correction : une seule table de routes dans le contrat.

**M3 — Rappels : spec-3 contre 6b.** Spec-3 : `TACHE_RAPPEL`, beat chaque minute, `manque` après 2 h. 6b §3 : `TACHES_RAPPEL`, `taches.balayer` toutes les 5 min. Correction : un seul nom (en fin d'énum) et la minute.

**M4 — Fuite hors ligne entre comptes.** 6b §8. Preuve : `purgeModuleOutboxes` ne parcourt que `OFFLINE_MODULES` (`lib/offlineOutbox.js:495,637-643`). `readCache` est un singleton, sans écoute de déconnexion (grep `taqinor:auth-logout`). Résultat : les captures de A partent sous le cookie de B, et B hors ligne voit la journée de A (socle §2.1). Correction : chaque op porte `(company_id, user_id)`, celles d'un autre compte sont jetées. Clé de cache `taches:aujourdhui:<user>:<jour>`. Vider à `taqinor:auth-logout` (`providers/session-bridge.js:74`).

**M5 — Idempotence cassée en multi-lignes.** 6b §5/§8 : la file poste sur `saisie-rapide/` avec un seul `client_id` ; `UniqueConstraint(company, proprietaire, client_id)` porte sur `Tache`. Un collage de 3 lignes donne une `IntegrityError` dès la 2e ligne. Correction : idempotence par lot (table dédiée) ou `client_id:<n>` par ligne, plus un critère de rejeu.

**M6 — `JetonAcces.empreinte` rougira `check_unique_scoping`.** Preuve : `GLOBAL_NAME_RE=(token|…|hash|digest|fingerprint)` (`scripts/check_unique_scoping.py`) : « empreinte » n'y est pas, et un `unique=True` global échoue. Correction : nommer le champ `jeton_hash`.

**M7 — Le plan échouera à `check_ownership` (règles a/b).** Preuve : un plan sans propriétaire est refusé, et toute `Files:` étrangère non append-only aussi (`scripts/check_ownership.py:459-510`). Non append-only : `Layout.jsx`, `Header.jsx`, `commandActions.js`, `useAppBadges.js`, `Dashboard.jsx`, `sw.js`, `vite.config.js`, `shortcuts.test.mjs`, `query-budgets.yml` (deploy) ; `records/selectors.py`, `records/services.py`, `authentication/selectors.py`, `authentication/views.py`, `seed_registre_traitements.py` (securite) ; `notifications/services.py`, `module_gating.py` (parametres) ; `quickCreateEvents.js`, `CockpitHome.jsx`, `agent/registry.py`, `cartes/*` (analyse). Correction : déclarer le propriétaire `taches` et `docs/plans/PLAN_TACHES.md` dans `docs/ownership.yml` en tâche n°1. Ranger les éditions étrangères dans le plan de leur propriétaire, ou dans PLAN2/new_tasks_plan (`platform`, exempté, `ownership.yml:43`).

**M8 — `taches.projet.lire` envoie des titres confidentiels à l'IA.** Spec-4 §7 ne masque que `planifier_apercu`, contre socle §2.7. Correction : rendre « Tâche confidentielle », avec un critère de test.

**M9 — Suggestions.** 6a §3.7. (a) `lead_du_devis` se replie sur le lead le plus récent du client (`crm/devis_selectors.py:23-35`) : le devis accepté peut être annoncé au propriétaire d'un autre lead. Aucune vérification de visibilité. (b) Le titre machine « Appeler {client} » survit à `lead_erased`. Correction : `devis.lead` strict, `resolve_target(…, user=destinataire)` avant création. Sur `lead_erased`, réécrire les titres `source='suggestion'` restés inchangés.

## MINEUR

1. `authentication/views.py` = 2 182 lignes : FICHIER_MUR (seuil 2000). Déclarer « Code net ≤ 1 ».
2. `resolve_target` lève la même `CibleIntrouvable('Cible introuvable.')` pour introuvable et hors portée (`records/serializers.py:69,102,106`) : `inaccessible` et `introuvable` ne se distinguent pas sans test d'existence séparé.
3. `str(lead)` = « nom prénom [STAGE] » (`crm/models.py:2028`) : le libellé fige une clé d'étape brute.
4. `ROUTE` est indexé par type de recherche (`entityRoutes.js:24-38`), pas par `app.model` : il faut une table de correspondance. « ∈ ALLOWED_TARGETS » est un test backend.
5. `relance_etapes_dues` today/overdue omet les touches-tâches ouvertes à toute date (`cadence_selectors.py:625-634,655`) : écart avec le cockpit.
6. `convertir-activite` n'exige pas `assigned_to=user`.
7. Spec-4 : `sans_prochaine_action` s'allume sur un projet neuf vide et sur un projet tout `en_attente`/`quelque_jour`. Exiger ≥ 1 ouverte.
8. Décaler Δ<0 : lun. 23/11 −1 → dim. → lun. 23, le geste ne fait rien (recalculé). Prendre le jour ouvré précédent ; dire si le refus « avant aujourd'hui » se juge avant ou après rectification.
9. Au-delà de 50 maillons, un cycle passe : renvoyer 400.
10. F28/J28 : projet ou utilisateur ? comptées ou tous niveaux ? La phrase affichée en dépend.
11. Négligé : quel Q la phrase nomme-t-elle ? (Recalcul : A(3)0, B(2)0, C(1)1 → A et B négligés.)
12. `statut_depuis` sans défaut ; aucune contrainte d'unicité du nom de projet (`is_deleted=False`), alors que l'API renvoie 400 « existe déjà ».
13. CASCADE sans `# on_delete:` : `RevueProjet.projet`, `SuggestionTache.destinataire`.
14. Instancier à une date passée : non spécifié.
15. Une tâche bloquée ou en pause à `echeance=J` disparaît sans mention.
16. « Focus = −3 » n'est pas dans `cle_tri` (spec-3 `pmax`) : dire focus ⇒ `pmax=3`.
17. `check_ecrans_atteignables` : `/taches/bilan` et les routes ouvertes seulement par notification demandent une nav, un lien ou `// contextuelle:`. Clés i18n de nav dans fr/en/ar (`nav-keys-no-raw-key.test.mjs`).
18. Layout est remonté à chaque navigation (`Layout.jsx:78`) : « monté une fois » est faux, il faut un cache de module. 6a et 6b montent deux hôtes de pastille : n'en garder qu'un.
19. Jeton : revérifier `taches_voir`, la portée interne et la société à chaque usage ; `IsAuthenticatedInterne`. La forme d'erreur `{"champ","detail"}` diffère des autres specs.
20. Divers : `CarteMesTaches` (6a) contre « pas de carte cockpit » (6b). Spec-3 « écriture hors ligne ÉCARTÉ » contre 6b. `g t` déjà pris par SAV (`shortcuts.js:35`). Tactile 150/8 (spec-3) contre 300/5 (spec-4, `KanbanView.jsx:262-267`). `useAppBadges` est fermé aux non-responsables (`:69-75`) : `badgePersonnel` n'est pas spécifié.

## Vérifié VRAI (porteur)

- `resolve_target` (`records/serializers.py:44-107`) : signature, `ecriture`, portée lead (:94-102) exacts. 15 cibles réelles, « 39 » périmé.
- Les 6 signaux existent, leurs charges sont conformes au catalogue, aucun n'est dans `ALLOWED_UNCONSUMED`. `abonne_best_effort` est à `core/events/__init__.py:166`.
- Le correctif de `commandActions.js:27` est réel et nécessaire (`commandActions.test.mjs:58`). La ligne `tache` d'`entityRoutes` est requise (`CommandPalette.jsx:156`).
- `build_ics` se réutilise sans édition ; aucun contrat `.importlinter` ne gêne `taches`.
- `badge` ne change rien pour les autres appelants (`notifications/services.py:308-311`).
- L'exclusion dans `_traces_du_compte` est faisable. Les propriétaires annoncés sont exacts. L'export anonymisé ne fait pas fuir `taches`.

Non vérifié : `get_object_for_this_type` via `_base_manager` (de mémoire).

## OPTIONNEL

- Masquer `/taches/flux/<jeton>` dans les journaux nginx.

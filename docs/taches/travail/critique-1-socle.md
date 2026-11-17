# Critique de complétude — socle du L3 n°1 (`apps/taches`)

Lecture seule, chemins relatifs à `backend/django_core/` sauf mention. Aucun test lancé (consigne).
Bilan : **1 BLOQUANT, 6 MAJEUR, 11 MINEUR**.

## BLOQUANT

**B1. « `taches_gerer` accordé à tous les rôles système » (socle §4) ouvre l'ERP aux rôles en lecture seule.**
- `is_responsable` vaut Vrai dès qu'un rôle porte UN code d'écriture connu (`authentication/models.py:486-514`).
  Viewer et Utilisateur (`apps/roles/permissions_registre.py:947-962, 1222-1250`, « jamais _gerer pour ce rôle »)
  deviendraient « responsables » et franchiraient toutes les gardes `IsResponsableOrAdmin` du dépôt.
- « Tous les rôles système » comprend les 3 rôles portail (`:1417-1452`), qui ne doivent porter aucun droit interne (NTPRT1).
- Commercial terrain est une liste blanche d'apps (`:1113-1116`) : sans `permission_app('taches')`, pas de tuile.
- **Correction du socle maintenant** : données privées, donc un seul code `taches_voir` qui ouvre le module ET l'écriture
  sur ses propres données. Jamais de `taches_gerer` pour Viewer/Utilisateur, rien pour les rôles portail,
  plus `permission_app('taches')` pour les rôles à liste blanche.

## MAJEUR

**M1. Multi-sociétés non tranché** (V2 m2 non repris). La société active est un claim JWT posé sur
`request.user.company` à chaque requête (`authentication/active_company.py:1-20`). Avec `taches_de(user)` filtré
par société, changer de société vide « Ma journée » et coupe la liste personnelle en deux. Jetons, flux et
balayages n'ont pas de JWT. → **Socle maintenant** : trancher. Choix sûr : la tâche appartient au couple
(société d'attache, utilisateur), quelle que soit la société active ; jetons et beat utilisent `jeton.company`.

**M2. Cycle de vie du compte absent.**
- Avec `proprietaire` en CASCADE, `_traces_du_compte` (`authentication/views.py:1394-1425`, ASUP5) compte les
  tâches. Tout utilisateur de Tâches devient non supprimable, et le 409 montre à l'admin « lié à N tâches ».
- La désactivation (D-ASUP-2, `docs/claude-memory/decisions-audit-1311.md`) ne dit rien du sort des jetons, des
  rappels ni des données, qui n'ont aucune durée de conservation.
- Pas d'« exporter mes données » ni d'« effacer mes données » (V2 m4 non repris).
- → **Socle maintenant** : à `is_active=False`, jetons morts et balayages sautés. Conservation et purge à fixer,
  export JSON personnel. Exclure le décompte privé du message 409 : tâche `securite`, au plan transverse.

**M3. Périmètre et coût du coach non décidés.**
- Ni le lot des actions `taches.*` (copilote = admins seulement, sans lot = tout le monde, brief :28), ni la
  limite Groq à 8 000 TPM (brief :29) ne sont tranchés. Or les 11 outils partent à chaque tour (V1, OPTIONNEL :116).
- Le repli de V2 M2 (« coach éteint hors fondateur tant que le masquage manque ») n'est pas repris.
- Le masquage est faisable mais incomplet. Il dépend de `outils_appeles` (`fastapi_ia/app/services/sql_agent_service.py:1782-1805`).
  Or « ajoute appeler Karim » posé sur un écran CRM, si aucun outil n'est appelé, reste journalisé en clair.
- → **Socle maintenant** : lot `copilote` en v1, et masquage sur `ecran` taches OU outil `taches.*`. Le reste au **L3 n°5**.

**M4. Langue de saisie.** Le fondateur écrit en anglais (brief §1, deux messages). Pourtant l'analyseur ne connaît
que `demain`/`ce soir` (`design-s1-modele.md:135`) et la dictée Siri est réglée « Français »
(`design-s4-presence.md:44`). L'ERP a pourtant des catalogues fr/en/ar (`frontend/src/i18n/catalogs/`).
→ **L3 n°2** : mots-clés FR + EN au minimum, langue de dictée choisie par l'utilisateur. Écran en français, catalogue en
pour le libellé.

**M5. Profilage de comportement des employés.** Le module est ouvert à tous, et S2 §5 bâtit un profil de
comportement. Or l'employeur peut tout lire techniquement (socle §2.7). Aucune ligne n'est prévue au registre
CNDP (`core/models.py:2275`, V2 m4). → **Socle maintenant** : le profil et le coach sont activés d'office pour le
fondateur, sur acceptation explicite pour les autres comptes. Ajouter la ligne de registre.

**M6. Performance d'`aujourdhui/` sans budget.** Ce corps est lu à chaque ouverture, par la pastille, la tuile
Scriptable et la carte de l'assistant. Il agrège tâches, activités, compteurs `ailleurs`, objectif et
checklists. La maison a un contrat opposable, `docs/query-budgets.yml` + `scripts/check_query_budgets.py`
(`assertMaxQueries`). → **L3 n°3** : entrée `enforced: true` et test de budget.

## MINEUR

1. **Supprimées sans fin.** La purge de corbeille ne touche jamais la ligne métier (`apps/trash/services.py:143-148`),
   et `record=False` n'écrit aucun journal : une tâche supprimée vit pour toujours. → L3 n°2 (purge à N jours).
2. **Exclusion XKB4** dans `activites_ouvertes_pour` (V2 m3) absente du socle §1(b). → L3 n°3.
3. **Projet supprimé, tâches vivantes** (V1 m7). → L3 n°4.
4. **Beat** : `active_companies()` (V1 m4) et comptes inactifs à sauter. → L3 n°5.
5. **Fuseau** : la prémisse « heure d'été du Ramadan » est périmée. Le Maroc est à UTC+0 permanent depuis le
   20/09/2026, avec tzdata épinglé (`requirements.txt:7-19`). Reste un manque : aucun fuseau par utilisateur
   (`design-s4-presence.md:8`), alors que le fondateur voyage (Ltd UK). Le matin et « aujourd'hui » restent ceux
   de Casablanca. → L3 n°3.
6. **Ramadan** : `WorkingHoursConfig` porte une fenêtre Ramadan (brief :22). La capacité et l'objectif du coach
   l'ignorent. → L3 n°5.
7. **Plan du matin réglé avant la fenêtre société** : il est sauté chaque jour (socle §5). Cela contredit « réglable » (D-TCH-3). → L3 n°5.
8. **Liens ERP** : `resolve_target` refuse tout modèle absent de `record_targets` (`apps/records/serializers.py:56-57`,
   `models.py:16-27`). Les visites ne sont donc pas liables (`apps/visites/platform.py:39`). `lien_libelle` est
   figé, sans fournisseur DSR. → L3 n°6.
9. **Jetons dans l'URL** : nginx et Sentry les journalisent (V2 M3, m5), et le socle §2.5 n'en dit rien. Le titre
   par défaut dans le Calendrier n'est pas fixé. → L3 n°6.
10. **Hors ligne** : le socle est muet. La dictée Siri hors réseau est perdue (`design-s4-presence.md:45`). → L3 n°2.
11. **Recette** : rien ne prévoit le groupe d'acceptation, ni `frontend/e2e/acceptation/taches.spec.js`,
    `scripts/check_acceptation.py`, les données `seed_demo`, ou `assertNoSeriousA11yViolations`
    (`frontend/e2e/apps-a11y.spec.js:14`). Le plan de licence peut couper le module si le manifeste porte
    `installable` (`apps/parametres/feature_flags.py:94-104`). → L3 n°9 et n°10.

## Cinq affirmations vérifiées

| Affirmation | Résultat |
|---|---|
| `soft_delete(record=False)` existe | VRAI : `core/models.py:180-211` coupe `DeletionRecord` ET l'événement. Voir MINEUR 1 |
| `resolve_target` accepte une app non déclarée | NON : refus « Type de cible non autorisé » (`serializers.py:56-57`) |
| App nouvelle allumée partout | VRAI par défaut (`core/feature_flags.py:71-90`), sauf plan de licence assigné ; prod non vérifiée |
| `taches_gerer` à tous les rôles | FAUX sans danger : voir B1. Tests non lancés |
| Masquage faisable depuis le relais | VRAI : `question` et `outils_appeles` sont dans le même corps (`sql_agent_service.py:1788-1794`), remplis par les deux moteurs (`:1722`, `relais_copilote.py:474-484`). Limite : voir M3 |

## Idées facultatives
- Alternative clavier au glisser-déposer (capteur clavier de dnd-kit), étiquettes VoiceOver.
- Copie hors serveur de l'export personnel.
- Plafond de coût mensuel du coach (brief :30, « no cost cap »).

Before reporting progress, audit each claim against a tool result from this session. Only report work you can point to evidence for; if something is not yet verified, say so explicitly. If tests fail, say so with the output.

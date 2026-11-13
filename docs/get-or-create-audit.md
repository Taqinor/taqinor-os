# Audit get_or_create / update_or_create (YDATA15)

Généré par `python scripts/check_get_or_create.py`. Chaque appel listé n'est adossé à AUCUNE garantie d'unicité connue du modèle cible (`unique=True`, `OneToOneField`, `unique_together`, `UniqueConstraint`, héritées comprises — lues en AST) : ses clés de lookup (hors `defaults`) devraient correspondre à une `UniqueConstraint`/`unique_together` company-scopée pour être course-safe. Les appels déjà adossés ne sont plus listés (ENF18). Advisory : ce sweep ne corrige rien (correctifs = ERROR_PLAN).

Clé de CONTENU `fichier::fonction::Modèle` (jamais un numéro de ligne : une insertion en amont ne fait plus remonter les voisins comme nouveaux). Régénéré par `python scripts/check_get_or_create.py --write`.

| Clé | Appel | Récepteur | Clés de lookup |
|---|---|---|---|
| `backend/django_core/apps/installations/field_services.py::cocher_outil_ligne::interv.tool_returns` | get_or_create | interv.tool_returns | outil |
| `backend/django_core/authentication/management/commands/seed_demo.py::Command._seed_chantier_terrain::CustomUser` | get_or_create | CustomUser.objects | username |
| `backend/django_core/authentication/management/commands/seed_demo.py::Command.handle::ActivityType` | get_or_create | ActivityType.objects | company, nom |
| `backend/django_core/authentication/management/commands/seed_demo.py::Command.handle::CustomUser` | get_or_create | CustomUser.objects | username |
| `backend/django_core/authentication/management/commands/seed_demo.py::Command.handle::CustomUser` | get_or_create | CustomUser.objects | username |
| `backend/django_core/authentication/management/commands/seed_demo.py::Command.handle::FollowupLevel` | get_or_create | FollowupLevel.objects | company, ordre |
| `backend/django_core/authentication/management/commands/seed_demo.py::Command.handle::Lead` | get_or_create | Lead.objects | company, nom, prenom |
| `backend/django_core/authentication/management/commands/seed_demo_company.py::Command._ensure_activity_scaffolding::ActivityType` | get_or_create | ActivityType.objects | company, nom |
| `backend/django_core/authentication/management/commands/seed_demo_company.py::Command._ensure_activity_scaffolding::FollowupLevel` | get_or_create | FollowupLevel.objects | company, ordre |
| `backend/django_core/authentication/management/commands/seed_demo_company.py::Command._ensure_company::CustomUser` | get_or_create | CustomUser.objects | username |
| `backend/django_core/authentication/management/commands/seed_demo_company.py::Command._ensure_company::CustomUser` | get_or_create | CustomUser.objects | username |
| `backend/django_core/authentication/poste_sync.py::backfill_poste_ref::poste_model` | get_or_create | poste_model.objects | company_id, intitule |
| `backend/django_core/authentication/selectors.py::revoke_user_sessions::BlacklistedToken` | get_or_create | BlacklistedToken.objects | token |
| `backend/django_core/authentication/session_policy.py::_revoke::BlacklistedToken` | get_or_create | BlacklistedToken.objects | token |
| `backend/django_core/authentication/signup_seeds.py::seed_activity_types::ActivityType` | get_or_create | ActivityType.objects | company, nom |
| `backend/django_core/authentication/signup_seeds.py::seed_followup_levels::FollowupLevel` | get_or_create | FollowupLevel.objects | company, ordre |
| `backend/django_core/authentication/tenant_templates.py::_seed_dashboard_solaire::DashboardConfig` | get_or_create | DashboardConfig.objects | company, menu_tier, user |
| `backend/django_core/authentication/views.py::_blacklist_refresh_jti::BlacklistedToken` | get_or_create | BlacklistedToken.objects | token |
| `backend/django_core/core/management/commands/seed_trust_center.py::Command.handle::TrustCenterEntry` | get_or_create | TrustCenterEntry.objects | categorie, titre |
| `backend/django_core/core/sharing.py::share_object::SharingRule` | update_or_create | SharingRule.objects |  |
| `backend/django_core/core/tasks.py::_assurer_alerte_fiabilite_defaut::kpi_alerte_model` | get_or_create | kpi_alerte_model.objects | company, kpi, operateur, seuil |

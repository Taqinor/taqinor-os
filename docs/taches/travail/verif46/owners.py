import sys
sys.path.insert(0,'scripts')
import check_ownership as co
reg=co.charger_registre()
B='backend/django_core/'; F='frontend/src/'
fs=[B+'apps/records/selectors.py',B+'apps/records/services.py',B+'authentication/selectors.py',B+'authentication/views.py',
B+'core/management/commands/seed_registre_traitements.py',F+'components/layout/Layout.jsx',F+'components/layout/Header.jsx',
F+'providers/shortcuts.js',F+'providers/commandActions.js',F+'lib/search/entityRoutes.js',F+'lib/apps/useAppBadges.js',
F+'pages/Dashboard.jsx',F+'features/uxviews/quickcreate/quickCreateEvents.js',F+'features/offlinesync/mobile/CockpitHome.jsx',
'docs/query-budgets.yml',B+'apps/notifications/services.py',B+'apps/notifications/types_evenements.py',B+'apps/notifications/module_map.py',
B+'apps/notifications/module_gating.py',B+'apps/notifications/migrations/0079_eventtype_taches.py',F+'sw.js','frontend/vite.config.js',F+'features/pwa/shortcuts.test.mjs',
B+'erp_agentique/celery.py',B+'erp_agentique/settings/base.py',B+'erp_agentique/urls.py',B+'apps/agent/registry.py',
B+'apps/agent/contract_samples/assistant_reponse.json',F+'features/ia/cartes/cartes.js',F+'features/ia/cartes/CartesDuMessage.jsx',
B+'apps/taches/models.py',F+'features/taches/x.js',F+'pages/taches/MonIphone.jsx','docs/plans/PLAN_TACHES.md',B+'apps/roles/permissions_registre.py',
'docs/rbac-endpoint-inventory.md','docs/get-or-create-audit.md',B+'apps/reporting/calendar.py',F+'router/index.jsx']
for f in fs:
    try: o=co.proprietaire(reg,f)
    except Exception as e: o='ERR '+str(e)
    print(f"{o!s:14} ao={reg.est_append_only(f)!s:5} {f}")

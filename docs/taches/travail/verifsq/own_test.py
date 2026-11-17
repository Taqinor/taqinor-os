import sys, re, pathlib
sys.path.insert(0, 'scripts')
import check_ownership as co
reg_txt = pathlib.Path('docs/ownership.yml').read_text(encoding='utf-8')
bloc = '''  taches:
    plan: docs/plans/PLAN_TACHES.md
    titre: "Tâches et agenda personnels + Copilote (apps/taches) : sa session PLAN_TACHES"
    paths:
      - backend/django_core/apps/taches/**
      - frontend/src/api/tachesApi*
      - frontend/src/features/taches/**
      - frontend/src/pages/taches/**
      - frontend/src/styles/taches/**
      - frontend/e2e/taches-*
      - frontend/e2e/acceptation/tch.spec.js
'''
assert '\n  parked:\n' in reg_txt
reg_txt = reg_txt.replace('\n  parked:\n', '\n' + bloc + '  parked:\n', 1)
reg_txt = reg_txt.replace('  docs/plans/PLAN_YANBOW_WEB.md: [yanbow-web, acquisition, deploy]\n',
  '  docs/plans/PLAN_YANBOW_WEB.md: [yanbow-web, acquisition, deploy]\n  docs/plans/PLAN_TACHES.md: [taches, deploy, securite, parametres, analyse]\n',1)
copie = pathlib.Path('docs/taches/travail/verifsq/ownership-copie.yml'); copie.write_text(reg_txt, encoding='utf-8')
co.REGISTRE = copie
orig = co.charger_registre
co.charger_registre = lambda chemin=copie, texte=None: orig(copie, texte)
plan = pathlib.Path('docs/taches/travail/essai-plan/essai-F1.md').read_text(encoding='utf-8')
plan = plan.replace('- [x]', '- [ ]')
orig_plans = co.plans_du_depot
def plans():
    p = orig_plans(); p['docs/plans/PLAN_TACHES.md'] = plan; return p
co.plans_du_depot = plans
for f in ['backend/django_core/apps/taches/models/taches.py','frontend/e2e/taches-journee.spec.js','frontend/src/styles/taches/base.css','frontend/src/api/tachesApi.test.js','frontend/e2e/acceptation/tch.spec.js','docs/audits/acceptation/TCH/x.md']:
    print(f, co.charger_registre().resoudre(f))
sys.exit(co.main([]))

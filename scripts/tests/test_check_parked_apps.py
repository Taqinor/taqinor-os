"""Tests de scripts/check_parked_apps.py (SOLMVP53 — garde des apps parquees).

Stdlib pur : python -m unittest scripts.tests.test_check_parked_apps -v

Chaque regle (a..e) a son cas POSITIF et son cas NEGATIF. Les negatifs sont les
faux positifs REELS du depot au 21/09/2026 : un commentaire « ... importe
apps.rh.models », un docstring « apps.get_model('rh', ...) » et les
'apps.<label>' d'INSTALLED_APPS — trois phrases legitimes qu'une garde naive
rendrait rouges a vie. Le registre ci-dessous est un STUB : la vraie regle de
coquille vit dans core/parked.py + parquer_app.py.
"""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_parked_apps as cpa  # noqa: E402

REGISTRE = '''import ast
APPS_PARQUEES = ('rh', 'kb')
APPS_PARQUEES_SET = frozenset(APPS_PARQUEES)


def modeles_declares(source):
    return sorted(n.name for n in ast.walk(ast.parse(source))
                  if isinstance(n, ast.ClassDef) and n.bases)
'''
APPS_PY = ("class C:\n    name = 'apps.x'\n    parked = True\n"
           "    manifeste = {'parked': True}\n")
URLS = "urlpatterns = [path('stock/', include('apps.stock.urls'))%s]\n"
CELERY = ("# apps.rh.tasks a disparu (commentaire).\n"
          "app.conf.beat_schedule = {'x': {'task': '%s', 'schedule': 1}}\n")
BASE = ("INSTALLED_APPS = ['apps.rh', 'apps.kb', 'apps.stock']\n"
        "# le shim importe apps.rh.models (commentaire, jamais du code)\n"
        "CELERY_TASK_ROUTES = {'%s': {'queue': 'scheduled'}}\n"
        "SPECTACULAR = {'ENUM_NAME_OVERRIDES': {'E': '%s'}}\n")


class Garde(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.racine = Path(self.tmp.name)
        self.ecrire('backend/django_core/core/parked.py', REGISTRE)
        for label in ('rh', 'kb'):
            base = 'backend/django_core/apps/%s/' % label
            self.ecrire(base + '__init__.py', '')
            self.ecrire(base + 'apps.py', APPS_PY)
            self.ecrire(base + 'models.py', '"""Coquille."""\n')
            # Migration gelee qui importe l'app : `*/migrations/*` est EXEMPT.
            self.ecrire(base + 'migrations/0001.py', 'from apps.rh import x\n')
        self.ecrire('backend/django_core/apps/stock/__init__.py', '')
        self.ecrire('backend/django_core/erp_agentique/urls.py', URLS % '')
        self.ecrire('backend/django_core/erp_agentique/celery.py',
                    CELERY % 'ventes.check')
        self.ecrire('backend/django_core/erp_agentique/settings/base.py',
                    BASE % ('ventes.pdf', 'apps.stock.models.Produit.Statut'))
        self.ecrire('frontend/src/main.jsx', "import App from './App';\n")

    def ecrire(self, chemin_rel, contenu):
        chemin = self.racine / chemin_rel
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_text(contenu, encoding='utf-8')

    def echecs(self):
        return cpa.verifier_tout(self.racine)

    def test_depot_propre(self):
        self.assertEqual(self.echecs(), [])
        self.assertEqual(cpa.main(['--racine', str(self.racine)]), 0)

    def test_a_import_module_et_local(self):
        self.ecrire('backend/django_core/apps/stock/services.py',
                    'from apps.rh.models import Departement\n\n\n'
                    'def f():\n    import apps.kb.models  # noqa\n')
        echecs = self.echecs()
        self.assertEqual([e[1] for e in echecs], [1, 5])
        self.assertIn('apps.rh', echecs[0][2])

    def test_a_commentaire_et_docstring_ignores(self):
        self.ecrire('backend/django_core/apps/stock/t.py',
                    '"""Les fixtures apps.get_model(\'rh\', ...) sont retirees."""\n'
                    '# from apps.kb.models import Article\n')
        self.assertEqual(self.echecs(), [])

    def test_a_fk_chaine_seulement_dans_models(self):
        self.ecrire('backend/django_core/apps/stock/models_achat.py',
                    "F = models.FK('rh.Departement')\n")
        self.ecrire('backend/django_core/apps/stock/serializers.py',
                    "LIBELLE = 'rh.Departement'\n")
        echecs = self.echecs()
        self.assertEqual(len(echecs), 1)
        self.assertIn('models_achat.py', echecs[0][0])

    def test_a_get_model(self):
        self.ecrire('backend/django_core/apps/stock/f.py',
                    "M = django_apps.get_model('kb', 'Article')\n")
        self.assertIn("get_model('kb'", self.echecs()[0][2])

    def test_b_include_urls(self):
        self.ecrire('backend/django_core/erp_agentique/urls.py',
                    URLS % ", path('kb/', include('apps.kb.urls'))")
        self.assertIn('apps.kb.urls', self.echecs()[0][2])

    def test_c_beat_routes_enum_mais_pas_installed_apps(self):
        self.assertEqual(self.echecs(), [])  # 'apps.rh' d'INSTALLED_APPS = OK
        self.ecrire('backend/django_core/erp_agentique/celery.py',
                    CELERY % 'rh.digest')
        self.ecrire('backend/django_core/erp_agentique/settings/base.py',
                    BASE % ('kb.reindex', 'apps.kb.models.Article.Statut'))
        raisons = ' '.join(e[2] for e in self.echecs())
        self.assertIn('entrée beat', raisons)
        self.assertIn('route Celery', raisons)
        self.assertIn('ENUM_NAME_OVERRIDES', raisons)

    def test_d_frontend_import_parque(self):
        self.ecrire('frontend/src/a.jsx', "// ../parked/features/rh\n"
                    "import V from '../../parked/features/rh/V.jsx';\n")
        echecs = self.echecs()
        self.assertEqual(len(echecs), 1)
        self.assertEqual(echecs[0][1], 2)

    def test_d_frontend_import_normal(self):
        self.ecrire('frontend/src/b.jsx', "import x from './parkedLike.js';\n")
        self.assertEqual(self.echecs(), [])

    def test_e_coquille_rompue(self):
        self.ecrire('backend/django_core/apps/rh/views.py', 'x = 1\n')
        self.assertIn("n'est plus une coquille", self.echecs()[0][2])


if __name__ == '__main__':
    unittest.main()

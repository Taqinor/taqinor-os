"""Tests AUD415 — scripts/check_beat_active_companies.py.

Stdlib pur (unittest), sans Django — miroir de la garde DB-free. Run :
    python -m unittest scripts.tests.test_check_beat_active_companies -v
"""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_beat_active_companies as guard  # noqa: E402


def _findings(src):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / 'tasks.py'
        path.write_text(src, encoding='utf-8')
        return guard.check_file(path)


# Le motif EXACT corrigé par AUD415 (ged/services.py:2358 d'avant correctif).
FANOUT_NON_SCOPE = '''
def purger_toutes_societes(apply=False):
    from authentication.models import Company

    for company in Company.objects.all():
        purger(company, apply=apply)
'''

FANOUT_SCOPE = '''
def purger_toutes_societes(apply=False):
    from authentication.selectors import active_companies

    for company in active_companies():
        purger(company, apply=apply)
'''

FILTRE_RECOPIE = '''
def balayer():
    for company in Company.objects.filter(actif=True):
        traiter(company)
'''

FILTRE_AUTRE_CHOSE = '''
def balayer(ids):
    for company in Company.objects.filter(id__in=ids):
        traiter(company)
'''

FILTRE_ACTIF_FAUX = '''
def lister_suspendues():
    return Company.objects.filter(actif=False)
'''

AUTRE_MODELE = '''
def balayer():
    for produit in Produit.objects.all():
        traiter(produit)
'''

ACCES_QUALIFIE = '''
def balayer():
    for company in models.Company.objects.all():
        traiter(company)
'''

COMPOSITION_AVEC_MODULE = '''
def balayer():
    for company in societes_avec_module('scm', Company.objects.all()):
        traiter(company)
'''


class DetectionTests(unittest.TestCase):
    def test_le_fanout_non_scope_est_signale(self):
        self.assertEqual(len(_findings(FANOUT_NON_SCOPE)), 1)

    def test_le_selecteur_unique_est_accepte(self):
        self.assertEqual(_findings(FANOUT_SCOPE), [])

    def test_le_filtre_actif_recopie_est_signale(self):
        self.assertEqual(len(_findings(FILTRE_RECOPIE)), 1)

    def test_un_autre_filtre_nest_pas_signale(self):
        self.assertEqual(_findings(FILTRE_AUTRE_CHOSE), [])

    def test_lister_les_suspendues_nest_pas_signale(self):
        """``actif=False`` est une intention explicite, jamais un fan-out."""
        self.assertEqual(_findings(FILTRE_ACTIF_FAUX), [])

    def test_un_autre_modele_nest_pas_signale(self):
        self.assertEqual(_findings(AUTRE_MODELE), [])

    def test_acces_qualifie_est_signale(self):
        self.assertEqual(len(_findings(ACCES_QUALIFIE)), 1)

    def test_le_queryset_passe_a_un_helper_est_signale(self):
        """Le motif `scm` : le fan-out est enveloppé, il reste non scopé."""
        self.assertEqual(len(_findings(COMPOSITION_AVEC_MODULE)), 1)


class PerimetreTests(unittest.TestCase):
    def test_seuls_les_modules_beat_sont_scannes(self):
        self.assertEqual(
            guard.FICHIERS_BEAT, ('tasks.py', 'scheduled.py', 'beat_tasks.py'))

    def test_les_tests_et_migrations_sont_hors_perimetre(self):
        for chemin in ('apps/stock/tests/test_tasks.py',
                       'apps/stock/tests_tasks.py',
                       'apps/stock/migrations/0001_init.py'):
            self.assertTrue(guard._is_test_path(Path(chemin)), chemin)

    def test_les_modules_beat_de_production_sont_scannes(self):
        scannes = {guard._rel(p) for p in guard._iter_source_files()}
        self.assertIn('backend/django_core/apps/stock/tasks.py', scannes)
        self.assertIn('backend/django_core/apps/ventes/scheduled.py', scannes)
        # Un service n'est PAS un module beat : hors périmètre déclaré.
        self.assertNotIn('backend/django_core/apps/ged/services.py', scannes)


class AllowlistTests(unittest.TestCase):
    def test_les_deux_exceptions_sca19_sont_dans_l_allowlist(self):
        allow = guard._load_allowlist()
        self.assertIn('backend/django_core/apps/compta/tasks.py', allow)
        self.assertIn('backend/django_core/apps/chat/tasks.py', allow)

    def test_les_dix_sites_corriges_ne_sont_pas_dans_l_allowlist(self):
        """AUD415 les a MIGRÉS : les allowlister annulerait le correctif."""
        allow = guard._load_allowlist()
        for rel in (
            'backend/django_core/apps/credit/tasks.py',
            'backend/django_core/apps/marketing/tasks.py',
            'backend/django_core/apps/stock/tasks.py',
            'backend/django_core/apps/scm/tasks.py',
            'backend/django_core/apps/education/tasks.py',
            'backend/django_core/apps/ai_governance/tasks.py',
            'backend/django_core/apps/ao/scheduled.py',
            'backend/django_core/apps/veille_ao/tasks.py',
            'backend/django_core/apps/ventes/scheduled.py',
        ):
            self.assertNotIn(rel, allow, rel)

    def test_le_depot_est_propre(self):
        """La garde passe sur le dépôt réel (aucun site hors allowlist)."""
        self.assertEqual(guard.main([]), 0)


if __name__ == '__main__':
    unittest.main()

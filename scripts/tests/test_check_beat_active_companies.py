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
        # ADEP26 : compta/chat sortis du MVP (fichiers absents) — lignes
        # mortes purgées ; il reste l'exception adminops.
        self.assertIn('backend/django_core/apps/adminops/tasks.py', allow)

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


class BalayageGlobalNonScopeTests(unittest.TestCase):
    """AFAC44 / AFAC93 — balayage global non scopé d'un modèle à FK company (comportemental :
    le vérificateur tourne sur une arborescence temporaire)."""

    MODELE = ("from django.db import models\n\n\nclass Facture(models.Model):\n"
              "    company = models.ForeignKey('authentication.Company', on_delete=models.CASCADE)\n"
              "    statut = models.CharField(max_length=10)\n")

    def _lancer(self, scheduled_src, allow=''):
        import io
        from contextlib import redirect_stdout
        from unittest import mock
        with tempfile.TemporaryDirectory() as tmp:
            r = Path(tmp)
            apps = r / 'backend' / 'django_core' / 'apps' / 'ventes'
            apps.mkdir(parents=True)
            (apps / 'models.py').write_text(self.MODELE, encoding='utf-8')
            (apps / 'scheduled.py').write_text(scheduled_src, encoding='utf-8')
            allow_path = r / 'allow.txt'
            allow_path.write_text(allow, encoding='utf-8')
            with mock.patch.object(guard, 'ROOT', r), \
                    mock.patch.object(guard, 'DJANGO_CORE', r / 'backend' / 'django_core'), \
                    mock.patch.object(guard, 'SCAN_ROOT', r / 'backend' / 'django_core' / 'apps'), \
                    mock.patch.object(guard, 'ALLOWLIST_PATH', allow_path):
                buf = io.StringIO()
                with redirect_stdout(buf):
                    code = guard.main([])
                return code, buf.getvalue()

    def test_filtre_facture_sans_societe_signale(self):
        code, out = self._lancer(
            "def relance_reminders():\n    return Facture.objects.filter(statut='x')\n")
        self.assertEqual(code, 1, out)
        self.assertIn('scheduled.py::relance_reminders', out)
        self.assertIn('active_companies()', out)

    def test_shared_task_modele_metier_sans_societes_actives_refusee(self):
        """AFAC44 — même règle, vue depuis une `@shared_task` de module de tâches périodiques."""
        code, out = self._lancer(
            "@shared_task\ndef rappels():\n    for f in Facture.objects.filter(statut='x'):\n"
            "        notifier(f)\n\n\n@shared_task\ndef rappels_scopes():\n"
            "    return Facture.objects.filter(company_id__in=active_company_ids())\n")
        self.assertEqual(code, 1, out)
        self.assertIn('scheduled.py::rappels ', out + ' ')
        self.assertNotIn('rappels_scopes', out)

    def test_boucle_active_companies_acceptee(self):
        code, out = self._lancer(
            "def relance_reminders():\n    for c in active_companies():\n"
            "        Facture.objects.filter(company=c, statut='x')\n")
        self.assertEqual(code, 0, out)
        code, out = self._lancer(
            "def f():\n    ids = active_company_ids()\n    return Facture.objects.filter(statut='x')\n")
        self.assertEqual(code, 0, out)

    def test_filtre_company_in_accepte(self):
        code, out = self._lancer(
            "def f(ids):\n    return Facture.objects.filter(company__in=ids)\n")
        self.assertEqual(code, 0, out)

    def test_passif_gele_accepte_et_cle_morte_echoue(self):
        src = "def f():\n    return Facture.objects.filter(statut='x')\n"
        code, out = self._lancer(
            src, 'backend/django_core/apps/ventes/scheduled.py::f\n')
        self.assertEqual(code, 0, out)

    def test_cle_morte_echoue(self):
        code, out = self._lancer(
            "def f(ids):\n    return Facture.objects.filter(company__in=ids)\n",
            'backend/django_core/apps/ventes/scheduled.py::f\n')
        self.assertEqual(code, 1, out)
        self.assertIn('clé morte', out)


class BeatActiveCompaniesTests(BalayageGlobalNonScopeTests):
    """AFAC101 — seul un QUERYSET borné par company/active_company_ids() borne le balayage."""

    def test_create_company_ne_borne_pas_le_balayage(self):
        code, out = self._lancer(
            "def relance_reminders():\n    RelanceLog.objects.create(company=c)\n"
            "    p = CompanyProfile.get(company=c)\n"
            "    return Facture.objects.filter(statut='x')\n")
        self.assertEqual(code, 1, out)
        self.assertIn('scheduled.py::relance_reminders', out)

    def test_filtre_company_chaine_borne_le_balayage(self):
        code, out = self._lancer(
            "def f(c):\n    return Facture.objects.filter(statut='x').exclude(company=c)\n")
        self.assertEqual(code, 0, out)

    def test_lecture_d_une_ligne_par_pk_n_est_pas_un_balayage(self):
        # Revue C20 du lot audit_deploy : une chaine bornee par pk=/id= lit UNE ligne
        # (_langue_resolue, _signaler_pdf_devis_genere) - plus besoin d'allowlist.
        code, out = self._lancer(
            "def f(pk):\n    return (Facture.objects.select_related('company')\n"
            "            .filter(pk=pk).first())\n\n\n"
            "def g(i):\n    return Facture.objects.get(id=i)\n")
        self.assertEqual(code, 0, out)

    def test_pk_in_reste_un_balayage(self):
        code, out = self._lancer(
            "def f(ids):\n    return list(Facture.objects.filter(pk__in=ids))\n")
        self.assertEqual(code, 1, out)


if __name__ == '__main__':
    unittest.main()

"""CIQ654 — recette côté ventes (FG274/FG275/FG278) : plus de tolérance I-V
8 % ni de seuil PR 0,75 inventés ; seuils SOCIÉTÉ (CIQ622) sans défaut.

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_ciq654_seuils_recette_ventes -v 2
"""
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.crm.models import Client
from apps.parametres.models import CompanyProfile
from apps.ventes import commissioning
from apps.ventes.models import (
    CommissioningTest, Devis, IVCurveCapture, TestPerformanceReception,
)
from authentication.models import Company

User = get_user_model()
MOTIF = 'seuil non saisi en Paramètres'


class _Base(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='CIQ654 Co', slug='ciq654')
        self.user = User.objects.create_user(
            username='ciq654', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.force_authenticate(self.user)
        client = Client.objects.create(
            company=self.company, nom='Usine', prenom='CIQ654',
            email='ciq654@example.com', telephone='+212600000654')
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-CIQ654-1', client=client,
            statut='accepte', created_by=self.user)

    def _reglages(self, **valeurs):
        profil, _ = CompanyProfile.objects.get_or_create(company=self.company)
        CompanyProfile.objects.filter(pk=profil.pk).update(**valeurs)


class SeuilPrTests(_Base):
    URL = '/api/django/ventes/tests-pr-reception/'

    def test_pr_072_sans_seuil_en_attente_avec_motif(self):
        """ROUGE AVANT : le 0,75 inventé donnait « refuse »."""
        rep = self.api.post(self.URL, {'pr_mesure': '0.72',
                                       'pr_attendu': '0.80'}, format='json')
        self.assertEqual(rep.status_code, 201, rep.content)
        self.assertEqual(rep.data['motif_seuil'], MOTIF)
        obj = TestPerformanceReception.objects.get(id=rep.data['id'])
        self.assertEqual(obj.verdict, 'en_attente')
        # Le PR reste servi (à titre d'information).
        self.assertAlmostEqual(float(obj.pr_mesure), 0.72, places=4)

    def test_seuil_societe_08_refuse(self):
        # Saisi en % (0-100, CIQ622) : 80 % = 0,8.
        self._reglages(recette_pr_seuil_interne=80)
        rep = self.api.post(self.URL, {'pr_mesure': '0.72',
                                       'pr_attendu': '0.80'}, format='json')
        self.assertEqual(rep.status_code, 201, rep.content)
        self.assertIsNone(rep.data['motif_seuil'])
        obj = TestPerformanceReception.objects.get(id=rep.data['id'])
        self.assertEqual(obj.verdict, 'refuse')


class ToleranceIvTests(_Base):
    URL = '/api/django/ventes/courbes-iv/'

    def setUp(self):
        super().setUp()
        self.recette = CommissioningTest.objects.create(
            company=self.company, devis=self.devis, isolement_ok=True,
            polarite_ok=True, continuite_terre_ok=True,
            controle_onduleur_ok=True)

    def _post(self):
        return self.api.post(self.URL, {
            'recette': self.recette.id, 'string_label': 'S1',
            'pmax_mesure_w': '4400', 'pmax_attendu_w': '5000'},
            format='json')

    def test_ecart_moins_12_sans_seuil_pas_de_defaut_et_motif(self):
        rep = self._post()
        self.assertEqual(rep.status_code, 201, rep.content)
        self.assertEqual(rep.data['motif_seuil'], MOTIF)
        iv = IVCurveCapture.objects.get(id=rep.data['id'])
        self.assertAlmostEqual(float(iv.ecart_pmax_pct), -12.0, places=2)
        self.assertFalse(iv.defaut_detecte)
        self.recette.refresh_from_db()
        self.assertEqual(self.recette.resultat, 'conforme')

    def test_seuil_10_defaut(self):
        self._reglages(recette_ecart_pmax_pct=10)
        rep = self._post()
        self.assertEqual(rep.status_code, 201, rep.content)
        self.assertIsNone(rep.data['motif_seuil'])
        iv = IVCurveCapture.objects.get(id=rep.data['id'])
        self.assertTrue(iv.defaut_detecte)
        self.recette.refresh_from_db()
        self.assertEqual(self.recette.resultat, 'non_conforme')


class ConstantesRetireesTests(TestCase):
    def test_aucune_constante_inventee(self):
        self.assertFalse(hasattr(commissioning, 'DEFAULT_PMAX_TOLERANCE_PCT'))
        self.assertFalse(hasattr(commissioning, 'DEFAULT_PR_ACCEPTANCE'))
        ventes = Path(commissioning.__file__).resolve().parent
        for fichier in ventes.rglob('*.py'):
            if 'tests' in fichier.parts:
                continue
            texte = fichier.read_text(encoding='utf-8')
            for nom in ('DEFAULT_PMAX_TOLERANCE_PCT', 'DEFAULT_PR_ACCEPTANCE'):
                with self.subTest(fichier=fichier.name, nom=nom):
                    self.assertNotIn(nom, texte)

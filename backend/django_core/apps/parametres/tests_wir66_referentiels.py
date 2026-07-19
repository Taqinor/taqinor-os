"""WIR66 — tests des API de référentiels société (TVA/conditions/unités).

Couvre : lecture ouverte, écriture réservée admin/responsable (limité → 403),
scoping société, company forcée côté serveur, non-migration du code, et
l'action ``set_defaut`` (un seul taux par défaut).
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.parametres.models_payment_terms import ConditionPaiement
from apps.parametres.models_taxes import TauxTVA
from apps.parametres.models_units import UniteMesure

User = get_user_model()

TVA = '/api/django/parametres/taux-tva/'
COND = '/api/django/parametres/conditions-paiement/'
UNITE = '/api/django/parametres/unites-mesure/'


def _company(slug='ref-co', nom='Ref Co'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def _auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class ReferentielsTest(TestCase):
    def setUp(self):
        self.company = _company()
        self.admin = User.objects.create_user(
            username='ref_admin', password='pw', role_legacy='admin',
            company=self.company)
        self.viewer = User.objects.create_user(
            username='ref_viewer', password='pw', role_legacy='utilisateur',
            company=self.company)
        self.api = _auth(self.admin)

    # ── TVA ──────────────────────────────────────────────────────────────
    def test_admin_creates_and_lists_taux(self):
        r = self.api.post(TVA, {'code': 'tva20', 'libelle': 'Normal',
                                'taux': '20', 'defaut': True}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        row = TauxTVA.objects.get(code='tva20')
        # company forcée côté serveur.
        self.assertEqual(row.company_id, self.company.id)
        lst = self.api.get(TVA)
        self.assertEqual(lst.status_code, 200)
        self.assertEqual(len(lst.data), 1)

    def test_viewer_can_read_but_not_write(self):
        TauxTVA.objects.create(company=self.company, code='tva20',
                               libelle='Normal', taux=Decimal('20'))
        viewer_api = _auth(self.viewer)
        self.assertEqual(viewer_api.get(TVA).status_code, 200)
        r = viewer_api.post(TVA, {'code': 'x', 'libelle': 'y', 'taux': '7'},
                            format='json')
        self.assertEqual(r.status_code, 403)

    def test_set_defaut_is_exclusive(self):
        a = TauxTVA.objects.create(company=self.company, code='a',
                                   libelle='A', taux=Decimal('20'),
                                   defaut=True)
        b = TauxTVA.objects.create(company=self.company, code='b',
                                   libelle='B', taux=Decimal('10'))
        r = self.api.post(f'{TVA}{b.id}/set_defaut/')
        self.assertEqual(r.status_code, 200)
        a.refresh_from_db()
        b.refresh_from_db()
        self.assertFalse(a.defaut)
        self.assertTrue(b.defaut)
        self.assertEqual(TauxTVA.default_taux(self.company), Decimal('10'))

    def test_code_cannot_migrate(self):
        row = TauxTVA.objects.create(company=self.company, code='a',
                                     libelle='A', taux=Decimal('20'))
        r = self.api.patch(f'{TVA}{row.id}/', {'code': 'b'}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_scoping_hides_other_company(self):
        other = _company(slug='ref-other', nom='Other')
        TauxTVA.objects.create(company=other, code='z', libelle='Z',
                               taux=Decimal('20'))
        self.assertEqual(len(self.api.get(TVA).data), 0)

    # ── Conditions de paiement ───────────────────────────────────────────
    def test_condition_crud(self):
        r = self.api.post(COND, {'libelle': '30 jours', 'delai_jours': 30,
                                 'fin_de_mois': True, 'escompte_pct': '2'},
                          format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(ConditionPaiement.objects.get(
            company=self.company).delai_jours, 30)

    # ── Unités de mesure ─────────────────────────────────────────────────
    def test_unite_crud_and_actif_filter(self):
        UniteMesure.objects.create(company=self.company, code='m',
                                   libelle='Mètre', actif=True)
        UniteMesure.objects.create(company=self.company, code='old',
                                   libelle='Ancien', actif=False)
        r = self.api.get(UNITE, {'actif': 'true'})
        self.assertEqual(r.status_code, 200)
        codes = {row['code'] for row in r.data}
        self.assertIn('m', codes)
        self.assertNotIn('old', codes)

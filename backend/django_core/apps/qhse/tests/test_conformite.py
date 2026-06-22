"""Tests QHSE5 — auto-conformité des relevés mesurés (vs plage min/max).

Couvre la règle déterministe portée par ``ReleveControle.save()`` :

* point AVEC plage numérique + valeur dans la plage → ``conforme`` True ;
* valeur hors plage (sous le min / au-dessus du max) → ``conforme`` False ;
* bornes INCLUSIVES (valeur == min ou == max → conforme) ;
* borne unique (min seul / max seul) ;
* parsing d'une valeur texte libre (``"24.5 N.m"``, virgule décimale) ;
* point SANS plage → ``conforme`` n'est PAS touché (reste manuel) ;
* valeur non numérique malgré une plage → ``conforme`` non touché ;
* l'API (création ET mise à jour) applique la même auto-conformité, sans
  jamais affaiblir le scoping société (palier Administrateur/Responsable).
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.qhse.models import (
    PlanInspectionChantier, PlanInspectionModele, PointControleModele,
    ReleveControle,
)

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_plan(company):
    modele = PlanInspectionModele.objects.create(company=company, nom='ITP')
    plan = PlanInspectionChantier.objects.create(
        company=company, modele=modele, chantier_id=1)
    return modele, plan


def make_point(company, modele, **kwargs):
    return PointControleModele.objects.create(
        company=company, plan=modele, intitule='P', **kwargs)


class ConformiteModelTests(TestCase):
    """Règle d'auto-conformité au niveau ``ReleveControle.save()``."""

    def setUp(self):
        self.co = make_company('qhse5-mdl', 'Mdl')
        self.modele, self.plan = make_plan(self.co)

    def _releve(self, point, valeur, conforme=None):
        return ReleveControle.objects.create(
            company=self.co, plan_chantier=self.plan, point=point,
            valeur=valeur, conforme=conforme)

    def test_within_range_is_conforme(self):
        point = make_point(
            self.co, self.modele,
            valeur_min=Decimal('10'), valeur_max=Decimal('20'))
        rel = self._releve(point, '15')
        self.assertTrue(rel.conforme)

    def test_below_min_is_not_conforme(self):
        point = make_point(
            self.co, self.modele,
            valeur_min=Decimal('10'), valeur_max=Decimal('20'))
        rel = self._releve(point, '5')
        self.assertFalse(rel.conforme)

    def test_above_max_is_not_conforme(self):
        point = make_point(
            self.co, self.modele,
            valeur_min=Decimal('10'), valeur_max=Decimal('20'))
        rel = self._releve(point, '25')
        self.assertFalse(rel.conforme)

    def test_boundaries_are_inclusive(self):
        point = make_point(
            self.co, self.modele,
            valeur_min=Decimal('10'), valeur_max=Decimal('20'))
        self.assertTrue(self._releve(point, '10').conforme)
        self.assertTrue(self._releve(point, '20').conforme)

    def test_min_only_bound(self):
        point = make_point(self.co, self.modele, valeur_min=Decimal('10'))
        self.assertTrue(self._releve(point, '999').conforme)
        self.assertFalse(self._releve(point, '9').conforme)

    def test_max_only_bound(self):
        point = make_point(self.co, self.modele, valeur_max=Decimal('20'))
        self.assertTrue(self._releve(point, '0').conforme)
        self.assertFalse(self._releve(point, '21').conforme)

    def test_free_text_numeric_is_parsed(self):
        point = make_point(
            self.co, self.modele,
            valeur_min=Decimal('20'), valeur_max=Decimal('30'))
        self.assertTrue(self._releve(point, '24.5 N.m').conforme)

    def test_comma_decimal_is_parsed(self):
        point = make_point(
            self.co, self.modele,
            valeur_min=Decimal('20'), valeur_max=Decimal('30'))
        self.assertTrue(self._releve(point, '24,5 N.m').conforme)

    def test_no_range_leaves_conforme_manual(self):
        # Pas de plage → la valeur manuelle est conservée telle quelle.
        point = make_point(self.co, self.modele)
        self.assertTrue(self._releve(point, '15', conforme=True).conforme)
        self.assertFalse(self._releve(point, '15', conforme=False).conforme)
        self.assertIsNone(self._releve(point, '15').conforme)

    def test_non_numeric_value_leaves_conforme_manual(self):
        # Plage définie mais valeur non numérique → conformité non touchée.
        point = make_point(
            self.co, self.modele,
            valeur_min=Decimal('10'), valeur_max=Decimal('20'))
        rel = self._releve(point, 'conforme visuel', conforme=True)
        self.assertTrue(rel.conforme)
        rel2 = self._releve(point, '', conforme=False)
        self.assertFalse(rel2.conforme)

    def test_auto_overrides_manual_when_range_present(self):
        # Avec une plage et une valeur numérique, l'auto prime sur le manuel.
        point = make_point(
            self.co, self.modele,
            valeur_min=Decimal('10'), valeur_max=Decimal('20'))
        rel = self._releve(point, '5', conforme=True)
        self.assertFalse(rel.conforme)

    def test_recompute_on_update(self):
        point = make_point(
            self.co, self.modele,
            valeur_min=Decimal('10'), valeur_max=Decimal('20'))
        rel = self._releve(point, '15')
        self.assertTrue(rel.conforme)
        rel.valeur = '99'
        rel.save()
        rel.refresh_from_db()
        self.assertFalse(rel.conforme)


class ConformiteApiTests(TestCase):
    """L'auto-conformité s'applique aussi via l'API (création + maj)."""

    BASE = '/api/django/qhse/releves/'

    def setUp(self):
        self.co = make_company('qhse5-api', 'Api')
        self.user = make_user(self.co, 'qhse5-api')
        self.modele, self.plan = make_plan(self.co)
        self.point = make_point(
            self.co, self.modele,
            valeur_min=Decimal('10'), valeur_max=Decimal('20'))

    def test_create_auto_conforme_true(self):
        resp = auth(self.user).post(
            self.BASE,
            {
                'plan_chantier': self.plan.id,
                'point': self.point.id,
                'valeur': '15',
            },
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = ReleveControle.objects.get(id=resp.data['id'])
        self.assertTrue(obj.conforme)

    def test_create_out_of_range_overrides_posted_conforme(self):
        # Le corps tente conforme=True mais la valeur est hors plage → False.
        resp = auth(self.user).post(
            self.BASE,
            {
                'plan_chantier': self.plan.id,
                'point': self.point.id,
                'valeur': '99',
                'conforme': True,
            },
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = ReleveControle.objects.get(id=resp.data['id'])
        self.assertFalse(obj.conforme)

    def test_patch_recomputes_conforme(self):
        rel = ReleveControle.objects.create(
            company=self.co, plan_chantier=self.plan, point=self.point,
            valeur='15')
        self.assertTrue(rel.conforme)
        resp = auth(self.user).patch(
            f'{self.BASE}{rel.id}/', {'valeur': '5'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        rel.refresh_from_db()
        self.assertFalse(rel.conforme)

    def test_serializer_exposes_expected_range(self):
        rel = ReleveControle.objects.create(
            company=self.co, plan_chantier=self.plan, point=self.point,
            valeur='15')
        resp = auth(self.user).get(f'{self.BASE}{rel.id}/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(Decimal(resp.data['point_valeur_min']), Decimal('10'))
        self.assertEqual(Decimal(resp.data['point_valeur_max']), Decimal('20'))

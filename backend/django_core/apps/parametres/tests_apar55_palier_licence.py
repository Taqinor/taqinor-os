"""APAR55 — modifier un palier ``PlanLicence`` dans l'admin laisse une trace
``licence`` pour chaque société du palier, ``modules_inclus`` est validé contre
les manifestes, et un palier inactif ou vide ne verrouille plus en silence les
modules (repli « pas de plan ») — C-APAR-052."""
from django.contrib import admin as django_admin
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.adminops.admin import PlanLicenceAdmin, PlanLicenceAdminForm
from apps.adminops.models import PlanLicence
from apps.parametres import feature_flags as plan_flags
from apps.parametres.models import CompanyProfile, SettingsAuditLog
from authentication.models import Company

User = get_user_model()


class PalierLicenceTests(TestCase):
    def setUp(self):
        # `adminops/0003` sème starter/pro/enterprise : mise à jour, jamais
        # `create` (contrainte unique sur `code`).
        self.plan, _ = PlanLicence.objects.update_or_create(
            code=PlanLicence.Code.ENTERPRISE,
            defaults={'nom': 'probe', 'actif': True,
                      'modules_inclus': ['crm', 'ventes']})
        self.co1 = Company.objects.create(nom='APAR55 A', slug='apar55-a')
        self.co2 = Company.objects.create(nom='APAR55 B', slug='apar55-b')
        for co in (self.co1, self.co2):
            CompanyProfile.objects.create(company=co, nom=co.nom, plan=self.plan)
        self.root = User.objects.create_superuser(
            username='apar55_root', password='x', email='root@apar55.test')
        self.admin = User.objects.create_user(
            username='apar55_admin', password='x', role_legacy='admin',
            company=self.co1)

    def _admin_save(self, **champs):
        obj = PlanLicence.objects.get(pk=self.plan.pk)
        for k, v in champs.items():
            setattr(obj, k, v)
        req = RequestFactory().post('/admin/')
        req.user = self.root
        PlanLicenceAdmin(PlanLicence, django_admin.site).save_model(
            req, obj, form=None, change=True)
        return obj

    def _journal(self, co):
        return SettingsAuditLog.objects.filter(company=co, section='licence')

    def test_edition_palier_journalisee_par_societe(self):
        self._admin_save(modules_inclus=['crm'])
        for co in (self.co1, self.co2):
            ligne = self._journal(co).get(field='palier.modules_inclus')
            self.assertEqual(ligne.user_id, self.root.pk)
            self.assertIn('ventes', ligne.old_value)
            self.assertNotIn('ventes', ligne.new_value)

    def test_desactivation_journalisee(self):
        self._admin_save(actif=False)
        self.assertTrue(self._journal(self.co1).filter(
            field='palier.actif', old_value='True', new_value='False').exists())

    def test_cle_inconnue_refusee_dans_l_admin(self):
        form = PlanLicenceAdminForm(data={
            'code': self.plan.code, 'nom': 'probe', 'actif': True,
            'modules_inclus': '["inconnu"]'}, instance=self.plan)
        self.assertFalse(form.is_valid())
        self.assertIn('modules_inclus', form.errors)
        self.assertIn('inconnu', str(form.errors['modules_inclus']))

    def test_cles_installables_acceptees(self):
        form = PlanLicenceAdminForm(data={
            'code': self.plan.code, 'nom': 'probe', 'actif': True,
            'modules_inclus': '["crm"]'}, instance=self.plan)
        self.assertTrue(form.is_valid(), form.errors)

    def test_palier_inactif_ou_vide_ne_verrouille_plus(self):
        self.assertFalse(plan_flags.has_feature(self.co1, 'stock'))
        PlanLicence.objects.filter(pk=self.plan.pk).update(actif=False)
        self.assertTrue(plan_flags.has_feature(self.co1, 'stock'))
        self.assertEqual(plan_flags.modules_hors_plan(self.co1), set())
        PlanLicence.objects.filter(pk=self.plan.pk).update(
            actif=True, modules_inclus=[])
        self.assertTrue(plan_flags.has_feature(self.co1, 'ventes'))
        self.assertEqual(plan_flags.modules_hors_plan(self.co1), set())

    def test_jwt_palier_inactif_ne_renvoie_plus_404(self):
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')
        PlanLicence.objects.filter(pk=self.plan.pk).update(
            modules_inclus=['crm'])
        self.assertEqual(api.get('/api/django/ventes/devis/').status_code, 404)
        PlanLicence.objects.filter(pk=self.plan.pk).update(actif=False)
        self.assertNotEqual(
            api.get('/api/django/ventes/devis/').status_code, 404)

"""AUD815 — ``/core/module-toggles/`` exposait un CRUD BRUT à côté du chemin
nommé ``/core/modules/{key}/activer|desactiver/``.

Constat d'origine : ``ModuleToggleViewSet`` était un ``ModelViewSet`` complet
sans ``perform_update``/``perform_destroy``. Un ``PATCH {"actif": false}``
coupait un module dont d'autres dépendent SANS jamais évaluer
``feature_flags.DependencyError``, et sans émettre ``module_toggled`` — donc
sans une seule ligne au journal d'installation ODY25
(``apps/records/receivers.py`` n'écoute que cet événement). Un DELETE de la
ligne RÉACTIVAIT le module en silence (politique FG391 : « absence de ligne =
actif »).

Après correctif : le ViewSet est en lecture seule
(``http_method_names=['get','head','options']``) — toute mutation → 405, et le
chemin nommé continue de produire sa ligne de journal.
"""
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.records.models import Activity
from authentication.models import Company
from core import feature_flags
from core.models import ModuleToggle
from core.views import ModuleCatalogViewSet, ModuleToggleViewSet

User = get_user_model()


class Aud815ModuleTogglesLectureSeuleTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='AUD815 SARL')
        cls.admin = User.objects.create_user(
            username='aud815_admin', password='x', role_legacy='admin',
            company=cls.company)
        cls.factory = APIRequestFactory()

    def _toggle_crm(self):
        """Ligne ``crm`` ACTIVE — ``crm`` est une dépendance d'autres modules
        actifs, donc le désactiver doit passer par la fermeture de
        dépendances."""
        return ModuleToggle.objects.create(
            company=self.company, module='crm', actif=True)

    # ── Le CRUD brut est fermé ────────────────────────────────────────────
    def test_patch_actif_false_est_refuse(self):
        toggle = self._toggle_crm()
        req = self.factory.patch(
            f'/module-toggles/{toggle.pk}/', {'actif': False}, format='json')
        force_authenticate(req, user=self.admin)
        resp = ModuleToggleViewSet.as_view(
            {'patch': 'partial_update'})(req, pk=toggle.pk)
        self.assertEqual(resp.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        toggle.refresh_from_db()
        self.assertTrue(toggle.actif)

    def test_delete_est_refuse(self):
        """Un DELETE réactivait le module en silence (pas de ligne = actif)."""
        toggle = ModuleToggle.objects.create(
            company=self.company, module='flotte', actif=False)
        req = self.factory.delete(f'/module-toggles/{toggle.pk}/')
        force_authenticate(req, user=self.admin)
        resp = ModuleToggleViewSet.as_view(
            {'delete': 'destroy'})(req, pk=toggle.pk)
        self.assertEqual(resp.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertTrue(ModuleToggle.objects.filter(pk=toggle.pk).exists())
        self.assertFalse(feature_flags.module_actif(self.company, 'flotte'))

    def test_put_est_refuse(self):
        toggle = self._toggle_crm()
        req = self.factory.put(
            f'/module-toggles/{toggle.pk}/',
            {'module': 'crm', 'actif': False}, format='json')
        force_authenticate(req, user=self.admin)
        resp = ModuleToggleViewSet.as_view(
            {'put': 'update'})(req, pk=toggle.pk)
        self.assertEqual(resp.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_lecture_reste_ouverte(self):
        self._toggle_crm()
        req = self.factory.get('/module-toggles/')
        force_authenticate(req, user=self.admin)
        resp = ModuleToggleViewSet.as_view({'get': 'list'})(req)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('crm', {row['module'] for row in resp.data})

    # ── Le chemin nommé garde la garde de dépendances ET le journal ───────
    def test_desactiver_par_le_chemin_nomme_refuse_les_dependants(self):
        """Ce que le PATCH brut contournait : ``DependencyError`` (400)."""
        req = self.factory.post('/modules/crm/desactiver/')
        force_authenticate(req, user=self.admin)
        resp = ModuleCatalogViewSet.as_view(
            {'post': 'desactiver'})(req, pk='crm')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(resp.data.get('dependants'))

    def test_desactiver_par_le_chemin_nomme_journalise(self):
        req = self.factory.post('/modules/flotte/desactiver/')
        force_authenticate(req, user=self.admin)
        resp = ModuleCatalogViewSet.as_view(
            {'post': 'desactiver'})(req, pk='flotte')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        ct = ContentType.objects.get_for_model(ModuleToggle)
        ids = list(ModuleToggle.objects.filter(company=self.company)
                   .values_list('id', flat=True))
        lignes = Activity.objects.filter(
            content_type=ct, object_id__in=ids, field='actif')
        self.assertTrue(lignes.exists())

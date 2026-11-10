"""Tests FG394 — consentement & DSR (loi 09-08 / CNDP).

Couvre :
  * registre de consentement : company imposée, isolation société, admin-only ;
  * fournisseurs DSR : export agrégé + effacement agrégé, isolation par
    fournisseur (une exception n'arrête pas l'agrégat) ;
  * traitement d'une demande (accès → export, effacement → erase) ;
  * découplage : fournisseurs DSR enregistrés en test (callables purs) — aucun
    import d'app domaine.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from authentication.models import Company
from core import dsr
from core.models import ConsentRecord, DataSubjectRequest
from core.views import ConsentRecordViewSet, DataSubjectRequestViewSet

User = get_user_model()


class DsrRegistryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='ACME')

    def setUp(self):
        # Sauvegarde/restaure le registre GLOBAL des providers DSR : les vrais
        # providers crm/rh sont enregistrés une fois au démarrage (ready()) et
        # d'autres modules de test en dépendent — un .clear() sans restauration
        # les vidait pour les tests suivants (contamination inter-tests).
        self._saved_providers = dict(dsr._PROVIDERS)
        dsr._PROVIDERS.clear()
        dsr.register_dsr_provider(
            'crm',
            export=lambda co, subj: {'leads': [subj]},
            erase=lambda co, subj: 1)
        dsr.register_dsr_provider(
            'boom', export=lambda co, subj: (_ for _ in ()).throw(ValueError('x')))

    def tearDown(self):
        dsr._PROVIDERS.clear()
        dsr._PROVIDERS.update(self._saved_providers)

    def test_export_aggregates_and_isolates_errors(self):
        out = dsr.exporter(self.company, 'a@b.ma')
        self.assertEqual(out['crm'], {'leads': ['a@b.ma']})
        self.assertIn('erreur', out['boom'])

    def test_erase_aggregates(self):
        out = dsr.effacer(self.company, 'a@b.ma')
        self.assertEqual(out['crm'], 1)

    def test_traiter_access_request(self):
        req = DataSubjectRequest.objects.create(
            company=self.company, subject_identifier='a@b.ma',
            kind=DataSubjectRequest.KIND_ACCESS)
        dsr.traiter_demande(req)
        req.refresh_from_db()
        self.assertEqual(req.statut, DataSubjectRequest.STATUT_TRAITEE)
        self.assertIn('crm', req.resultat)
        self.assertIsNotNone(req.traitee_le)


class ConsentViewSetTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='ACME')
        cls.other = Company.objects.create(nom='Autre')
        cls.admin = User.objects.create_user(
            username='c_admin', password='x', role_legacy='admin',
            company=cls.company)
        cls.user = User.objects.create_user(
            username='c_user', password='x', role_legacy='normal',
            company=cls.company)
        cls.factory = APIRequestFactory()

    def test_create_requires_admin_and_imposes_company(self):
        body = {'subject_identifier': 'a@b.ma', 'purpose': 'marketing',
                'granted': True}
        req = self.factory.post('/consent-records/', body, format='json')
        force_authenticate(req, user=self.user)
        resp = ConsentRecordViewSet.as_view({'post': 'create'})(req)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

        req2 = self.factory.post('/consent-records/', body, format='json')
        force_authenticate(req2, user=self.admin)
        resp2 = ConsentRecordViewSet.as_view({'post': 'create'})(req2)
        self.assertEqual(resp2.status_code, status.HTTP_201_CREATED)
        rec = ConsentRecord.objects.get(pk=resp2.data['id'])
        self.assertEqual(rec.company, self.company)

    def test_company_isolation(self):
        ConsentRecord.objects.create(
            company=self.other, subject_identifier='x', purpose='m')
        req = self.factory.get('/consent-records/')
        force_authenticate(req, user=self.admin)
        resp = ConsentRecordViewSet.as_view({'get': 'list'})(req)
        ids = [r['id'] for r in resp.data.get('results', resp.data)]
        self.assertEqual(ids, [])


class DsrRequestViewSetTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='ACME')
        cls.admin = User.objects.create_user(
            username='d_admin', password='x', role_legacy='admin',
            company=cls.company)
        cls.factory = APIRequestFactory()

    def setUp(self):
        self._saved_providers = dict(dsr._PROVIDERS)
        dsr._PROVIDERS.clear()
        dsr.register_dsr_provider('crm', export=lambda co, subj: {'ok': True})

    def tearDown(self):
        dsr._PROVIDERS.clear()
        dsr._PROVIDERS.update(self._saved_providers)

    def test_traiter_action(self):
        dsr_req = DataSubjectRequest.objects.create(
            company=self.company, subject_identifier='a@b.ma',
            kind=DataSubjectRequest.KIND_ACCESS)
        req = self.factory.post(f'/dsr-requests/{dsr_req.pk}/traiter/')
        force_authenticate(req, user=self.admin)
        resp = DataSubjectRequestViewSet.as_view(
            {'post': 'traiter'})(req, pk=dsr_req.pk)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['statut'], DataSubjectRequest.STATUT_TRAITEE)

    def test_traiter_refuse_sans_dsr_traiter(self):
        """APFS45 (C-APFS-042, D-APFS-1) — demandes loi 09-08 : ``dsr_traiter``
        exigé en plus du palier sur toutes les routes ; refus ⇒ sujet ni
        exporté ni effacé ; Directeur / Administrateur 201 puis 200."""
        from django.apps import apps as django_apps
        from django.core.management import call_command
        Role = django_apps.get_model('roles', 'Role')  # core n'importe aucune app
        appels = []
        dsr._PROVIDERS.clear()
        dsr.register_dsr_provider('crm', export=lambda co, s: appels.append(('export', s)) or {},
                                  erase=lambda co, s: appels.append(('erase', s)) or {})
        call_command('init_roles', verbosity=0)
        roles = {r.nom: r for r in Role.objects.filter(company=self.company)}
        demandes = [DataSubjectRequest.objects.create(
            company=self.company, subject_identifier='sujet@b.ma', kind=k)
            for k in (DataSubjectRequest.KIND_ACCESS, DataSubjectRequest.KIND_ERASURE)]

        def gestes(nom):
            user = User.objects.create_user(
                username=f'apfs45_{nom.replace(" ", "_").lower()}', password='x',
                company=self.company, role=roles[nom])
            reqs = [(self.factory.get('/dsr-requests/'), {'get': 'list'}, {}),
                    (self.factory.post('/dsr-requests/', {'kind': 'acces', 'subject_identifier': 'x@b.ma'},
                                       format='json'), {'post': 'create'}, {})]
            reqs += [(self.factory.post(f'/dsr-requests/{d.pk}/traiter/'), {'post': 'traiter'}, {'pk': d.pk})
                     for d in demandes]
            codes = []
            for req, actions, kw in reqs:
                force_authenticate(req, user=user)
                codes.append(DataSubjectRequestViewSet.as_view(actions)(req, **kw).status_code)
            return codes
        for nom in ('Admin RH', 'Admin Ventes', 'Technicien responsable', 'Commercial responsable', 'Responsable'):
            with self.subTest(role=nom):
                self.assertEqual(gestes(nom), [403] * 4)
        self.assertEqual(appels, [])
        self.assertEqual(gestes('Directeur'), [200, 201, 200, 200])
        self.assertIn(('erase', 'sujet@b.ma'), appels)
        demandes = [DataSubjectRequest.objects.create(
            company=self.company, subject_identifier='autre@b.ma', kind=DataSubjectRequest.KIND_ACCESS)]
        self.assertEqual(gestes('Administrateur')[1:], [201, 200])

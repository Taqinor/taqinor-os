"""NTLOG35 — `ParametresTransport` (réglages singleton par société). Couvre :
création paresseuse (`for_company`, idempotente, jamais `count()+1`),
défauts, API GET/PATCH, isolation société, garde d'écriture, et l'effet
concret de `pod_obligatoire=False` sur `EtapeTransportViewSet.livrer`
(NTLOG9) — désactivable UNIQUEMENT pour la société qui l'a désactivé."""
from decimal import Decimal

from django.test import TestCase

from apps.transport.models import EtapeTransport, OrdreTransport, ParametresTransport

from ._helpers import auth, make_company, make_user

BASE = '/api/django/transport/parametres-transport/'


class ForCompanyTests(TestCase):
    def test_cree_avec_defauts_a_la_premiere_lecture(self):
        company = make_company('transport-pt-defauts', 'A')
        self.assertEqual(
            ParametresTransport.objects.filter(company=company).count(), 0)
        obj = ParametresTransport.for_company(company)
        self.assertEqual(obj.delai_alerte_retard_heures, 24)
        self.assertTrue(obj.pod_obligatoire)
        self.assertEqual(obj.seuil_anomalie_affretement_pct, Decimal('15.00'))

    def test_idempotent(self):
        company = make_company('transport-pt-idem', 'A')
        obj1 = ParametresTransport.for_company(company)
        obj2 = ParametresTransport.for_company(company)
        self.assertEqual(obj1.id, obj2.id)
        self.assertEqual(
            ParametresTransport.objects.filter(company=company).count(), 1)

    def test_isolation_societe(self):
        co_a = make_company('transport-pt-iso-a', 'A')
        co_b = make_company('transport-pt-iso-b', 'B')
        obj_a = ParametresTransport.for_company(co_a)
        obj_b = ParametresTransport.for_company(co_b)
        self.assertNotEqual(obj_a.id, obj_b.id)


class ApiParametresTransportTests(TestCase):
    def setUp(self):
        self.company = make_company('transport-pt-api', 'A')
        self.user = make_user(self.company, 'transport-pt-api')

    def test_get_cree_a_la_volee(self):
        resp = auth(self.user).get(BASE)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.data['pod_obligatoire'])

    def test_patch_pod_obligatoire(self):
        resp = auth(self.user).patch(
            f'{BASE}1/', {'pod_obligatoire': False}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        obj = ParametresTransport.for_company(self.company)
        self.assertFalse(obj.pod_obligatoire)


class PermissionsParametresTransportTests(TestCase):
    def setUp(self):
        self.company = make_company('transport-pt-perm', 'A')

    def test_role_non_responsable_lit_mais_ne_modifie_pas(self):
        user = make_user(self.company, 'transport-pt-perm-normal', role='normal')
        api = auth(user)
        resp_get = api.get(BASE)
        self.assertEqual(resp_get.status_code, 200, resp_get.data)
        resp_patch = api.patch(f'{BASE}1/', {'pod_obligatoire': False}, format='json')
        self.assertEqual(resp_patch.status_code, 403, resp_patch.data)


class PodObligatoireParametrableTests(TestCase):
    """NTLOG35 critère d'acceptation : modifier `pod_obligatoire` à False
    permet de clôturer une étape de livraison sans photo, UNIQUEMENT pour
    cette société."""

    def setUp(self):
        self.co_a = make_company('transport-pod-a', 'A')
        self.co_b = make_company('transport-pod-b', 'B')
        self.user_a = make_user(self.co_a, 'transport-pod-a')
        self.user_b = make_user(self.co_b, 'transport-pod-b')
        self.ordre_a = OrdreTransport.objects.create(company=self.co_a)
        self.etape_a = EtapeTransport.objects.create(
            company=self.co_a, ordre=self.ordre_a, sequence=1,
            type_etape=EtapeTransport.TypeEtape.LIVRAISON)
        self.ordre_b = OrdreTransport.objects.create(company=self.co_b)
        self.etape_b = EtapeTransport.objects.create(
            company=self.co_b, ordre=self.ordre_b, sequence=1,
            type_etape=EtapeTransport.TypeEtape.LIVRAISON)

    def test_livrer_sans_piece_bloque_par_defaut(self):
        resp = auth(self.user_a).post(
            f'/api/django/transport/etapes-transport/{self.etape_a.id}/livrer/')
        self.assertEqual(resp.status_code, 400)

    def test_pod_obligatoire_false_debloque_pour_cette_societe(self):
        ParametresTransport.objects.create(
            company=self.co_a, pod_obligatoire=False)
        resp = auth(self.user_a).post(
            f'/api/django/transport/etapes-transport/{self.etape_a.id}/livrer/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.etape_a.refresh_from_db()
        self.assertEqual(
            self.etape_a.statut_etape, EtapeTransport.StatutEtape.FAIT)

    def test_pod_obligatoire_false_ne_deborde_pas_sur_une_autre_societe(self):
        ParametresTransport.objects.create(
            company=self.co_a, pod_obligatoire=False)
        resp = auth(self.user_b).post(
            f'/api/django/transport/etapes-transport/{self.etape_b.id}/livrer/')
        self.assertEqual(resp.status_code, 400)

"""ASEC33 — kitting : les emplacements de stock sont résolus dans la société
AVANT tout appel au service de stock.

Constat C-ASEC-006 site kitting : ``terminer`` (assemblage) lisait un id brut
d'emplacement dans le corps et le passait au service de stock — un
emplacement d'une autre société était mouvementé (200), un id inexistant
donnait un 500. Le démontage consommait de même les emplacements de l'ordre
sans vérifier leur société. Attendu : 400, aucun mouvement de stock.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.installations.models import Kit, OrdreAssemblage
from apps.installations.models_kitting import OrdreDemontage
from apps.stock.models import EmplacementStock, MouvementStock, Produit
from authentication.models import Company

User = get_user_model()
BASE = '/api/django/installations'


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class KittingIdsSocieteTests(TestCase):
    def setUp(self):
        self.a = Company.objects.create(nom='ASEC33 A', slug='asec33-a')
        self.b = Company.objects.create(nom='ASEC33 B', slug='asec33-b')
        self.user = User.objects.create_user(
            username='asec33_resp', password='x', role_legacy='responsable',
            company=self.a)
        self.api = _api(self.user)
        composite = Produit.objects.create(
            company=self.a, nom='Coffret assemblé', prix_vente=200,
            prix_achat=0)
        self.kit = Kit.objects.create(
            company=self.a, nom='Coffret', produit_compose=composite)
        self.emp_a = EmplacementStock.objects.create(
            company=self.a, nom='Dépôt A')
        self.emp_b = EmplacementStock.objects.create(
            company=self.b, nom='Dépôt B')
        self.ordre = OrdreAssemblage.objects.create(
            company=self.a, reference='ASM-ASEC33', kit=self.kit, quantite=1)

    def _terminer(self, corps):
        return self.api.post(
            f'{BASE}/ordres-assemblage/{self.ordre.pk}/terminer/', corps,
            format='json')

    def _assert_refus(self, resp, champ):
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertIn(champ, resp.data)

    def test_terminer_emplacement_etranger_400(self):
        avant = MouvementStock.objects.count()
        r = self._terminer({'emplacement_source': self.emp_b.pk})
        self._assert_refus(r, 'emplacement_source')
        r2 = self._terminer({'emplacement_destination': self.emp_b.pk})
        self._assert_refus(r2, 'emplacement_destination')
        self.assertEqual(MouvementStock.objects.count(), avant)
        self.ordre.refresh_from_db()
        self.assertNotEqual(self.ordre.statut, OrdreAssemblage.Statut.TERMINE)
        self.assertFalse(self.ordre.stock_mouvemente)

    def test_demontage_emplacement_etranger_400(self):
        demontage = OrdreDemontage.objects.create(
            company=self.a, reference='DSM-ASEC33', kit=self.kit, quantite=1,
            emplacement_source=self.emp_b)
        avant = MouvementStock.objects.count()
        r = self.api.post(
            f'{BASE}/ordres-demontage/{demontage.pk}/terminer/', {},
            format='json')
        self._assert_refus(r, 'emplacement_source')
        self.assertEqual(MouvementStock.objects.count(), avant)
        demontage.refresh_from_db()
        self.assertFalse(demontage.stock_mouvemente)

    def test_id_inexistant_400_pas_500(self):
        r = self._terminer({'emplacement_source': 999999})
        self._assert_refus(r, 'emplacement_source')
        r2 = self._terminer({'emplacement_source': 'pas-un-id'})
        self._assert_refus(r2, 'emplacement_source')

    def test_emplacement_societe_ok(self):
        r = self._terminer({'emplacement_destination': self.emp_a.pk})
        self.assertEqual(r.status_code, 200, r.content)
        self.ordre.refresh_from_db()
        self.assertEqual(self.ordre.statut, OrdreAssemblage.Statut.TERMINE)
        self.assertEqual(self.ordre.emplacement_destination_id, self.emp_a.pk)

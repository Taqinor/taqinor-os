"""NTCPQ18 — Devis multi-lots : sous-total par lot + total consolidé au centime."""
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ventes.models import LigneDevis, LotDevis
from apps.ventes.selectors import lots_totaux
from authentication.models import CustomUser
from testkit.factories import (
    CompanyFactory, DevisFactory, ProduitFactory, UserFactory,
)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class TestLotsDevis(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.user = UserFactory(
            company=self.company, role_legacy=CustomUser.ROLE_RESPONSABLE)
        self.produit = ProduitFactory(company=self.company)
        self.devis = DevisFactory(company=self.company)
        self.lot_a = LotDevis.objects.create(
            company=self.company, devis=self.devis, nom_lot='Site A',
            adresse_site='Casablanca', ordre=0)
        self.lot_b = LotDevis.objects.create(
            company=self.company, devis=self.devis, nom_lot='Site B',
            adresse_site='Rabat', ordre=1)
        self._ligne(self.lot_a, '1000.00', '3')
        self._ligne(self.lot_b, '2500.50', '2')

    def _ligne(self, lot, prix, qte):
        return LigneDevis.objects.create(
            devis=self.devis, produit=self.produit,
            designation=self.produit.nom, quantite=Decimal(qte),
            prix_unitaire=Decimal(prix), lot=lot)

    def test_sous_total_par_lot_et_total_consolide(self):
        res = lots_totaux(self.devis)
        self.assertEqual([b['nom_lot'] for b in res['lots']],
                         ['Site A', 'Site B'])
        self.assertEqual(res['lots'][0]['totaux']['ht_net'],
                         Decimal('3000.00'))
        self.assertEqual(res['lots'][1]['totaux']['ht_net'],
                         Decimal('5001.00'))
        self.assertEqual(res['total_consolide']['ht_net'],
                         Decimal('8001.00'))
        self.assertIsNone(res['hors_lot'])

    def test_consolide_coherent_au_centime_avec_le_devis(self):
        res = lots_totaux(self.devis)
        somme = sum(b['totaux']['ht_net'] for b in res['lots'])
        self.assertEqual(somme, res['total_consolide']['ht_net'])
        self.assertEqual(res['total_consolide']['ht_net'],
                         self.devis.total_ht)

    def test_remise_globale_repercutee_sur_chaque_lot(self):
        self.devis.remise_globale = Decimal('10')
        self.devis.save(update_fields=['remise_globale'])
        self.devis.refresh_from_db()
        res = lots_totaux(self.devis)
        self.assertEqual(res['lots'][0]['totaux']['ht_net'],
                         Decimal('2700.00'))
        self.assertEqual(res['total_consolide']['ht_net'],
                         Decimal('7200.90'))

    def test_ligne_hors_lot_isolee(self):
        self._ligne(None, '500.00', '1')
        res = lots_totaux(self.devis)
        self.assertEqual(res['hors_lot']['ht_net'], Decimal('500.00'))
        self.assertEqual(res['total_consolide']['ht_net'],
                         Decimal('8501.00'))

    def test_devis_sans_lot_reste_mono_site(self):
        autre = DevisFactory(company=self.company)
        self.assertIsNone(lots_totaux(autre))

    def test_suppression_de_lot_ne_perd_aucune_ligne(self):
        self.lot_a.delete()
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.lignes.count(), 2)
        self.assertEqual(self.devis.total_ht, Decimal('8001.00'))

    def test_endpoint_get_et_post(self):
        url = f'/api/django/ventes/devis/{self.devis.id}/lots/'
        api = auth(self.user)
        resp = api.get(url)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data['lots']), 2)
        ligne = self._ligne(None, '100.00', '1')
        resp = api.post(url, {
            'nom_lot': 'Site C', 'adresse_site': 'Fès', 'ordre': 2,
            'lignes': [ligne.id],
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(len(resp.data['lots']), 3)
        ligne.refresh_from_db()
        self.assertEqual(ligne.lot.nom_lot, 'Site C')

    def test_endpoint_refuse_un_lot_en_double(self):
        resp = auth(self.user).post(
            f'/api/django/ventes/devis/{self.devis.id}/lots/',
            {'nom_lot': 'Site A'}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_endpoint_isole_les_societes(self):
        autre = DevisFactory(company=CompanyFactory())
        resp = auth(self.user).get(
            f'/api/django/ventes/devis/{autre.id}/lots/')
        self.assertEqual(resp.status_code, 404)

"""NTCPQ17 — Paliers de remise volume + cascade multi-paliers et décomposition."""
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import Categorie
from apps.ventes.models import PalierRemiseVolume
from apps.ventes.selectors import decomposition_remise_volume
from authentication.models import CustomUser
from testkit.factories import CompanyFactory, ProduitFactory, UserFactory

PRIX = '/api/django/ventes/prix-applicable/'


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class TestRemiseVolumeCascade(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.user = UserFactory(
            company=self.company, role_legacy=CustomUser.ROLE_NORMAL)
        self.cat_panneaux = Categorie.objects.create(
            company=self.company, nom='Panneaux')
        self.cat_onduleurs = Categorie.objects.create(
            company=self.company, nom='Onduleurs')
        self.cat_cables = Categorie.objects.create(
            company=self.company, nom='Câbles')
        self.panneau = ProduitFactory(
            company=self.company, categorie=self.cat_panneaux,
            prix_vente=Decimal('1000.00'))
        self.onduleur = ProduitFactory(
            company=self.company, categorie=self.cat_onduleurs,
            prix_vente=Decimal('5000.00'))
        self.cable = ProduitFactory(
            company=self.company, categorie=self.cat_cables,
            prix_vente=Decimal('100.00'))
        PalierRemiseVolume.objects.create(
            company=self.company, categorie_nom='Panneaux',
            quantite_min=Decimal('10'), remise_pct=Decimal('5'), priorite=10)
        PalierRemiseVolume.objects.create(
            company=self.company, categorie_nom='Onduleurs',
            quantite_min=Decimal('2'), remise_pct=Decimal('3'), priorite=10)
        PalierRemiseVolume.objects.create(
            company=self.company, categorie_nom='Câbles',
            quantite_min=Decimal('5'), remise_pct=Decimal('2'), priorite=10)
        # Palier de CASCADE : s'ajoute sur le sous-total global.
        self.cascade = PalierRemiseVolume.objects.create(
            company=self.company, categorie_nom='',
            quantite_min=Decimal('15'), remise_pct=Decimal('4'),
            priorite=1, cumulable=True)

    def _panier(self):
        return [
            {'produit': self.panneau, 'quantite': Decimal('12')},
            {'produit': self.onduleur, 'quantite': Decimal('2')},
            {'produit': self.cable, 'quantite': Decimal('6')},
        ]

    def test_remise_de_ligne_seule_sans_panier(self):
        d = decomposition_remise_volume(
            company=self.company, produit=self.panneau,
            quantite=Decimal('12'))
        self.assertEqual(d['remise_ligne_pct'], '5.00')
        self.assertEqual(d['cascade'], [])
        self.assertEqual(d['remise_totale_pct'], '5.00')

    def test_sous_le_palier_aucune_remise(self):
        d = decomposition_remise_volume(
            company=self.company, produit=self.panneau, quantite=Decimal('3'))
        self.assertEqual(d['remise_ligne_pct'], '0.00')
        self.assertEqual(d['remise_totale_pct'], '0.00')

    def test_cascade_quand_trois_categories_atteignent_leur_palier(self):
        d = decomposition_remise_volume(
            company=self.company, produit=self.panneau,
            quantite=Decimal('12'), lignes=self._panier())
        self.assertEqual(d['remise_ligne_pct'], '5.00')
        self.assertEqual(len(d['cascade']), 1)
        self.assertEqual(d['cascade'][0]['remise_pct'], '4.00')
        self.assertEqual(d['cascade'][0]['portee'], 'global')
        # Remises COMPOSÉES : 1 − 0.95 × 0.96 = 8.80 %.
        self.assertEqual(d['remise_totale_pct'], '8.80')

    def test_pas_de_cascade_si_une_seule_categorie_atteint_son_seuil(self):
        panier = [
            {'produit': self.panneau, 'quantite': Decimal('12')},
            {'produit': self.onduleur, 'quantite': Decimal('1')},
        ]
        d = decomposition_remise_volume(
            company=self.company, produit=self.panneau,
            quantite=Decimal('12'), lignes=panier)
        self.assertEqual(d['cascade'], [])
        self.assertEqual(d['remise_totale_pct'], '5.00')

    def test_palier_non_cumulable_reste_hors_cascade(self):
        self.cascade.cumulable = False
        self.cascade.save(update_fields=['cumulable'])
        d = decomposition_remise_volume(
            company=self.company, produit=self.panneau,
            quantite=Decimal('12'), lignes=self._panier())
        self.assertEqual(d['cascade'], [])

    def test_ordre_de_priorite_dans_la_cascade(self):
        PalierRemiseVolume.objects.create(
            company=self.company, categorie_nom='',
            quantite_min=Decimal('15'), remise_pct=Decimal('1'),
            priorite=99, cumulable=True)
        d = decomposition_remise_volume(
            company=self.company, produit=self.panneau,
            quantite=Decimal('12'), lignes=self._panier())
        self.assertEqual(
            [e['remise_pct'] for e in d['cascade']], ['1.00', '4.00'])

    def test_isolation_societe(self):
        d = decomposition_remise_volume(
            company=CompanyFactory(), produit=self.panneau,
            quantite=Decimal('12'), lignes=self._panier())
        self.assertEqual(d['remise_totale_pct'], '0.00')

    def test_endpoint_prix_applicable_renvoie_la_decomposition(self):
        panier = (f'{self.panneau.id}:12,{self.onduleur.id}:2,'
                  f'{self.cable.id}:6')
        resp = auth(self.user).get(
            f'{PRIX}?produit={self.panneau.id}&quantite=12&panier={panier}')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('remise_volume', resp.data)
        self.assertEqual(resp.data['remise_volume']['remise_ligne_pct'],
                         '5.00')
        self.assertEqual(resp.data['remise_volume']['remise_totale_pct'],
                         '8.80')
        # Le prix de base reste celui de XSAL1/XSAL3 (inchangé).
        self.assertEqual(resp.data['prix'], '1000.00')

    def test_endpoint_sans_panier_reste_compatible(self):
        resp = auth(self.user).get(
            f'{PRIX}?produit={self.panneau.id}&quantite=12')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['remise_volume']['cascade'], [])

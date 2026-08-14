"""NTWMS31 — quarantaine qualité liée au casier.

Critère d'acceptation testé : un produit reçu en quarantaine n'est JAMAIS
proposé par une vague de prélèvement (NTWMS4) tant que la levée n'est pas
actée — et il redevient servable dès la levée.

Run :
    python manage.py test apps.stock.test_ntwms31_quarantaine -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import (
    BlocageQualite, EmplacementStock, MouvementStock, Produit,
)
from apps.stock.services import (
    creer_vague_depuis_besoins, lever_quarantaine, lever_quarantaine_bin,
    mettre_en_quarantaine, quantite_disponible_hors_quarantaine,
    quantite_en_quarantaine,
)

User = get_user_model()


def make_company(slug, nom):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Ntwms31Base(TestCase):
    def setUp(self):
        from apps.installations.models import BinLocation

        self.company = make_company('ntwms31-co', 'NTWMS31 Co')
        self.autre = make_company('ntwms31-autre', 'NTWMS31 Autre')
        self.admin = User.objects.create_user(
            username='ntwms31_admin', password='x', role_legacy='admin',
            company=self.company)
        self.magasinier = User.objects.create_user(
            username='ntwms31_magasinier', password='x', role_legacy='normal',
            company=self.company)
        self.emplacement = EmplacementStock.objects.create(
            company=self.company, nom='Dépôt NTWMS31', is_principal=True)
        self.casier_quarantaine = BinLocation.objects.create(
            company=self.company, emplacement=self.emplacement,
            code='Q-01-01', zone='Q', allee='01', casier='01', ordre=900)
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur suspect', sku='OND-NTWMS31',
            prix_achat=Decimal('7000'), prix_vente=Decimal('9000'),
            quantite_stock=6)
        self.api = auth(self.admin)

    def _bloquer(self, quantite=6):
        return mettre_en_quarantaine(
            company=self.company, produit=self.produit, quantite=quantite,
            user=self.admin, bin_quarantaine=self.casier_quarantaine,
            motif='Non conformité constatée à réception')


class TestQuarantaine(Ntwms31Base):
    def test_mise_en_quarantaine_ne_touche_pas_le_stock_physique(self):
        self._bloquer()
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 6)
        self.assertFalse(
            MouvementStock.objects.filter(company=self.company).exists())

    def test_la_quantite_bloquee_n_est_plus_disponible(self):
        self._bloquer(quantite=4)
        self.assertEqual(
            quantite_en_quarantaine(self.company, produit=self.produit), 4)
        self.assertEqual(
            quantite_disponible_hors_quarantaine(self.company, self.produit),
            2)

    def test_vague_ne_propose_jamais_un_produit_entierement_bloque(self):
        self._bloquer(quantite=6)
        with self.assertRaises(ValueError):
            creer_vague_depuis_besoins(
                company=self.company, user=self.admin,
                besoins=[{'produit_id': self.produit.id, 'quantite': 2}])

    def test_apres_levee_le_produit_redevient_servable(self):
        blocage = self._bloquer(quantite=6)
        lever_quarantaine(blocage=blocage, user=self.admin)

        vague = creer_vague_depuis_besoins(
            company=self.company, user=self.admin,
            besoins=[{'produit_id': self.produit.id, 'quantite': 2}])
        self.assertEqual(vague.lignes.count(), 1)

    def test_blocage_partiel_laisse_servir_le_reste(self):
        self._bloquer(quantite=2)
        vague = creer_vague_depuis_besoins(
            company=self.company, user=self.admin,
            besoins=[{'produit_id': self.produit.id, 'quantite': 3}])
        self.assertEqual(vague.lignes.count(), 1)

    def test_levee_est_idempotente(self):
        blocage = self._bloquer()
        lever_quarantaine(blocage=blocage, user=self.admin)
        premiere = blocage.date_levee
        lever_quarantaine(blocage=blocage, user=self.admin)
        self.assertEqual(blocage.date_levee, premiere)

    def test_levee_par_casier_libere_tout_le_casier(self):
        self._bloquer(quantite=2)
        self._bloquer(quantite=3)
        leves = lever_quarantaine_bin(
            company=self.company, bin_id=self.casier_quarantaine.id,
            user=self.admin)
        self.assertEqual(leves, 2)
        self.assertEqual(
            quantite_en_quarantaine(self.company, produit=self.produit), 0)

    def test_quantite_non_positive_refusee(self):
        with self.assertRaises(ValueError):
            mettre_en_quarantaine(
                company=self.company, produit=self.produit, quantite=0)

    def test_produit_hors_societe_refuse(self):
        produit_autre = Produit.objects.create(
            company=self.autre, nom='Autre', sku='AUT-NTWMS31',
            prix_achat=Decimal('1'), prix_vente=Decimal('2'))
        with self.assertRaises(ValueError):
            mettre_en_quarantaine(
                company=self.company, produit=produit_autre, quantite=1)


class TestEndpointsQuarantaine(Ntwms31Base):
    URL = '/api/django/stock/blocages-qualite/'

    def test_creation_puis_levee(self):
        creation = self.api.post(self.URL, {
            'produit': self.produit.id, 'quantite': 5,
            'bin': self.casier_quarantaine.id, 'motif': 'NC réception',
        }, format='json')
        self.assertEqual(creation.status_code, 201)
        self.assertEqual(creation.data['statut'], 'en_quarantaine')

        levee = self.api.post(f'{self.URL}{creation.data["id"]}/lever/', {},
                              format='json')
        self.assertEqual(levee.status_code, 200)
        self.assertEqual(levee.data['statut'], 'levee')

    def test_magasinier_ne_peut_pas_lever(self):
        blocage = self._bloquer()
        reponse = auth(self.magasinier).post(
            f'{self.URL}{blocage.id}/lever/', {}, format='json')
        self.assertEqual(reponse.status_code, 403)

    def test_levee_par_casier_via_api(self):
        self._bloquer(quantite=2)
        reponse = self.api.post(
            f'{self.URL}lever-quarantaine/',
            {'bin': self.casier_quarantaine.id}, format='json')
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse.data['blocages_leves'], 1)

    def test_levee_par_casier_sans_casier_refusee(self):
        reponse = self.api.post(f'{self.URL}lever-quarantaine/', {},
                                format='json')
        self.assertEqual(reponse.status_code, 400)

    def test_quantite_disponible_produit_exclut_la_quarantaine(self):
        self._bloquer(quantite=4)
        reponse = self.api.get(
            f'/api/django/stock/produits/{self.produit.id}/')
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse.data['quantite_disponible'], 2)

    def test_isolation_multi_societe(self):
        intrus = User.objects.create_user(
            username='ntwms31_intrus', password='x', role_legacy='admin',
            company=self.autre)
        self._bloquer()
        reponse = auth(intrus).get(self.URL)
        resultats = reponse.data.get('results', reponse.data)
        self.assertEqual(len(resultats), 0)
        self.assertEqual(BlocageQualite.objects.filter(
            company=self.company).count(), 1)

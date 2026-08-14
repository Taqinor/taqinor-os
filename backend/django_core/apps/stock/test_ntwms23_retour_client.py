"""NTWMS23 — retours client (RMA) côté entrepôt.

Critère d'acceptation testé : un retour client inspecté REVENDABLE réintègre
le stock disponible au bon casier ; un retour REBUT n'incrémente JAMAIS le
stock vendable.

Run :
    python manage.py test apps.stock.test_ntwms23_retour_client -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import (
    EmplacementStock, LigneRetourClient, MouvementStock, Produit, RetourClient,
)
from apps.stock.services import (
    creer_retour_client, inspecter_retour_client, receptionner_retour_client,
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


class Ntwms23Base(TestCase):
    def setUp(self):
        from apps.crm.models import Client
        from apps.installations.models import BinLocation

        self.company = make_company('ntwms23-co', 'NTWMS23 Co')
        self.autre = make_company('ntwms23-autre', 'NTWMS23 Autre')
        self.admin = User.objects.create_user(
            username='ntwms23_admin', password='x', role_legacy='admin',
            company=self.company)
        self.emplacement = EmplacementStock.objects.create(
            company=self.company, nom='Dépôt NTWMS23', is_principal=True)
        self.quarantaine = BinLocation.objects.create(
            company=self.company, emplacement=self.emplacement,
            code='Q-01-01', zone='Q', allee='01', casier='01', ordre=900)
        self.rebut = BinLocation.objects.create(
            company=self.company, emplacement=self.emplacement,
            code='R-01-01', zone='R', allee='01', casier='01', ordre=990)
        self.client_crm = Client.objects.create(
            company=self.company, nom='Retour', prenom='Client',
            email='retour-ntwms23@example.com', telephone='+212600000023')
        self.produit = Produit.objects.create(
            company=self.company, nom='Micro-onduleur', sku='MIC-NTWMS23',
            prix_achat=Decimal('1200'), prix_vente=Decimal('1600'),
            quantite_stock=20)
        self.api = auth(self.admin)

    def _retour(self, etat='revendable', quantite=3, bin_loc=None):
        return creer_retour_client(
            company=self.company, user=self.admin, client=self.client_crm,
            motif='Produit non conforme',
            lignes=[{'produit': self.produit.id, 'quantite': quantite,
                     'etat_constate': etat,
                     'bin': (bin_loc or self.quarantaine).id}])


class TestCreationRetourClient(Ntwms23Base):
    def test_reference_posee_par_le_serveur(self):
        retour = self._retour()
        self.assertTrue(retour.reference.startswith('RMA-'))
        self.assertEqual(retour.statut, RetourClient.Statut.DEMANDE)
        self.assertEqual(retour.lignes.count(), 1)

    def test_retour_sans_ligne_refuse(self):
        with self.assertRaises(ValueError):
            creer_retour_client(
                company=self.company, user=self.admin,
                client=self.client_crm, lignes=[])

    def test_deux_retours_ont_des_references_distinctes(self):
        premier = self._retour()
        second = self._retour()
        self.assertNotEqual(premier.reference, second.reference)


class TestReceptionEtInspection(Ntwms23Base):
    def test_revendable_reintegre_le_stock_au_bon_casier(self):
        retour = self._retour(etat='revendable', quantite=3)
        receptionner_retour_client(retour=retour, user=self.admin)

        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 23)
        mouvement = MouvementStock.objects.filter(
            company=self.company,
            type_mouvement=MouvementStock.TypeMouvement.ENTREE).first()
        self.assertIsNotNone(mouvement)
        self.assertEqual(mouvement.bin_destination_id, self.quarantaine.id)
        self.assertEqual(retour.statut, RetourClient.Statut.RECEPTIONNE)

    def test_rebut_n_incremente_jamais_le_stock_vendable(self):
        retour = self._retour(etat='rebut', quantite=3, bin_loc=self.rebut)
        receptionner_retour_client(retour=retour, user=self.admin)

        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 20)
        self.assertFalse(
            MouvementStock.objects.filter(company=self.company).exists())

    def test_reception_est_idempotente(self):
        retour = self._retour(quantite=3)
        receptionner_retour_client(retour=retour, user=self.admin)
        with self.assertRaises(ValueError):
            receptionner_retour_client(retour=retour, user=self.admin)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 23)

    def test_inspection_declassante_ressort_le_stock(self):
        """Entré revendable, puis constaté rebut : le stock vendable revient
        à son niveau d'origine (jamais un rebut vendable)."""
        retour = self._retour(etat='revendable', quantite=3)
        receptionner_retour_client(retour=retour, user=self.admin)
        ligne = retour.lignes.first()

        inspecter_retour_client(
            retour=retour, user=self.admin,
            lignes=[{'ligne': ligne.id, 'etat_constate': 'rebut',
                     'bin': self.rebut.id}])

        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 20)
        ligne.refresh_from_db()
        self.assertFalse(ligne.stock_mouvemente)
        self.assertEqual(ligne.bin_id, self.rebut.id)
        self.assertEqual(retour.statut, RetourClient.Statut.INSPECTE)

    def test_inspection_valorisante_reintegre_le_stock(self):
        retour = self._retour(etat='a_reparer', quantite=2)
        receptionner_retour_client(retour=retour, user=self.admin)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 20)

        ligne = retour.lignes.first()
        inspecter_retour_client(
            retour=retour, user=self.admin,
            lignes=[{'ligne': ligne.id, 'etat_constate': 'revendable',
                     'bin': self.quarantaine.id}])

        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 22)

    def test_inspection_avant_reception_refusee(self):
        retour = self._retour()
        with self.assertRaises(ValueError):
            inspecter_retour_client(retour=retour, user=self.admin, lignes=[])

    def test_etat_invalide_refuse(self):
        retour = self._retour()
        receptionner_retour_client(retour=retour, user=self.admin)
        ligne = retour.lignes.first()
        with self.assertRaises(ValueError):
            inspecter_retour_client(
                retour=retour, user=self.admin,
                lignes=[{'ligne': ligne.id, 'etat_constate': 'nimporte_quoi'}])


class TestEndpointsRetourClient(Ntwms23Base):
    URL = '/api/django/stock/retours-client/'

    def test_creation_puis_reception_via_api(self):
        creation = self.api.post(self.URL, {
            'client': self.client_crm.id, 'motif': 'Casse transport',
            'lignes': [{'produit': self.produit.id, 'quantite': 2,
                        'etat_constate': 'revendable',
                        'bin': self.quarantaine.id}],
        }, format='json')
        self.assertEqual(creation.status_code, 201)
        retour_id = creation.data['id']

        reception = self.api.post(f'{self.URL}{retour_id}/receptionner/', {},
                                  format='json')
        self.assertEqual(reception.status_code, 200)
        self.assertEqual(reception.data['statut'], 'receptionne')
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 22)

    def test_client_hors_societe_refuse(self):
        from apps.crm.models import Client
        client_autre = Client.objects.create(
            company=self.autre, nom='Autre', prenom='Client',
            email='autre-ntwms23@example.com', telephone='+212600000024')
        reponse = self.api.post(self.URL, {
            'client': client_autre.id,
            'lignes': [{'produit': self.produit.id, 'quantite': 1}],
        }, format='json')
        self.assertEqual(reponse.status_code, 400)

    def test_inspecter_via_api(self):
        retour = self._retour(etat='revendable', quantite=1)
        receptionner_retour_client(retour=retour, user=self.admin)
        ligne = retour.lignes.first()
        reponse = self.api.post(
            f'{self.URL}{retour.id}/inspecter/',
            {'lignes': [{'ligne': ligne.id, 'etat_constate': 'a_reparer'}]},
            format='json')
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse.data['statut'], 'inspecte')
        self.assertEqual(reponse.data['lignes'][0]['etat_constate'],
                         LigneRetourClient.EtatConstate.A_REPARER)

    def test_isolation_multi_societe(self):
        intrus = User.objects.create_user(
            username='ntwms23_intrus', password='x', role_legacy='admin',
            company=self.autre)
        self._retour()
        reponse = auth(intrus).get(self.URL)
        resultats = reponse.data.get('results', reponse.data)
        self.assertEqual(len(resultats), 0)

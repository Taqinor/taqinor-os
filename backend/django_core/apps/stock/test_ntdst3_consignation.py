"""NTDST3 — consignation de stock chez le client (dépôt-vente).

Critère d'acceptation testé : déclarer une consommation décrémente
``quantite_restante`` et NE MODIFIE JAMAIS le stock du dépôt principal une
DEUXIÈME fois (le stock est parti à la mise en consignation).

Run :
    python manage.py test apps.stock.test_ntdst3_consignation -v 2
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import (
    DeclarationConsommation, DepotConsignation, MouvementStock, Produit,
)
from apps.stock.services_consignation import (
    creer_depot_consignation, declarer_consommation, releve_consignation,
)

User = get_user_model()

JOUR = datetime.date(2026, 6, 1)
JOUR_CONSO = datetime.date(2026, 6, 15)


def make_company(slug, nom):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Ntdst3Base(TestCase):
    URL = '/api/django/stock/consignations/'

    def setUp(self):
        from apps.crm.models import Client

        self.company = make_company('ntdst3-co', 'NTDST3 Co')
        self.autre = make_company('ntdst3-autre', 'NTDST3 Autre')
        self.admin = User.objects.create_user(
            username='ntdst3_admin', password='x', role_legacy='admin',
            company=self.company)
        self.normal = User.objects.create_user(
            username='ntdst3_normal', password='x', role_legacy='normal',
            company=self.company)
        self.client_crm = Client.objects.create(
            company=self.company, nom='Client NTDST3')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur 3 kW', sku='OND3-NTDST3',
            prix_achat=Decimal('5000'), prix_vente=Decimal('7000'),
            quantite_stock=100)

    def _depot(self, quantite=20):
        return creer_depot_consignation(
            company=self.company, user=self.admin,
            client_id=self.client_crm.id, produit_id=self.produit.id,
            quantite=quantite, date_depot=JOUR,
            adresse_site='Zone industrielle Agadir')


class Ntdst3DepotTests(Ntdst3Base):
    def test_le_depot_decremente_le_stock_une_seule_fois_sans_facture(self):
        depot = self._depot(quantite=20)

        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 80)
        self.assertEqual(depot.quantite_restante, 20)

        mouvements = MouvementStock.objects.filter(
            company=self.company, produit=self.produit)
        self.assertEqual(mouvements.count(), 1)
        mouvement = mouvements.first()
        self.assertEqual(mouvement.type_mouvement,
                         MouvementStock.TypeMouvement.SORTIE)
        self.assertIn('consignation', mouvement.note.lower())

    def test_declarer_une_consommation_ne_retouche_jamais_le_stock(self):
        depot = self._depot(quantite=20)
        self.produit.refresh_from_db()
        stock_apres_depot = self.produit.quantite_stock

        declarer_consommation(
            depot=depot, user=self.admin, quantite=5,
            date_declaration=JOUR_CONSO)

        depot.refresh_from_db()
        self.produit.refresh_from_db()
        self.assertEqual(depot.quantite_restante, 15)
        self.assertEqual(self.produit.quantite_stock, stock_apres_depot)
        # Toujours UN SEUL mouvement : celui de la mise en consignation.
        self.assertEqual(MouvementStock.objects.filter(
            company=self.company, produit=self.produit).count(), 1)

    def test_consommation_superieure_au_restant_est_refusee(self):
        depot = self._depot(quantite=10)
        with self.assertRaises(ValueError):
            declarer_consommation(depot=depot, user=self.admin, quantite=11,
                                  date_declaration=JOUR_CONSO)

    def test_consommation_nulle_ou_negative_est_refusee(self):
        depot = self._depot(quantite=10)
        for mauvaise in (0, -3):
            with self.assertRaises(ValueError):
                declarer_consommation(
                    depot=depot, user=self.admin, quantite=mauvaise,
                    date_declaration=JOUR_CONSO)

    def test_le_depot_se_clot_quand_tout_est_consomme(self):
        depot = self._depot(quantite=6)
        declarer_consommation(depot=depot, user=self.admin, quantite=6,
                              date_declaration=JOUR_CONSO)
        depot.refresh_from_db()
        self.assertEqual(depot.statut, DepotConsignation.Statut.CLOS)
        with self.assertRaises(ValueError):
            declarer_consommation(depot=depot, user=self.admin, quantite=1,
                                  date_declaration=JOUR_CONSO)

    def test_depot_superieur_au_stock_disponible_est_refuse(self):
        with self.assertRaises(ValueError):
            creer_depot_consignation(
                company=self.company, user=self.admin,
                client_id=self.client_crm.id, produit_id=self.produit.id,
                quantite=100000, date_depot=JOUR)

    def test_un_produit_dune_autre_societe_est_introuvable(self):
        autre_produit = Produit.objects.create(
            company=self.autre, nom='Voisin', sku='VOISIN-DST3',
            prix_achat=Decimal('1'), prix_vente=Decimal('2'),
            quantite_stock=10)
        with self.assertRaises(ValueError):
            creer_depot_consignation(
                company=self.company, user=self.admin,
                client_id=self.client_crm.id, produit_id=autre_produit.id,
                quantite=1, date_depot=JOUR)

    def test_le_releve_cumule_les_quatre_quantites(self):
        depot = self._depot(quantite=20)
        declaration = declarer_consommation(
            depot=depot, user=self.admin, quantite=5,
            date_declaration=JOUR_CONSO)
        declaration.statut = DeclarationConsommation.Statut.FACTUREE
        declaration.save(update_fields=['statut'])
        declarer_consommation(depot=depot, user=self.admin, quantite=3,
                              date_declaration=JOUR_CONSO)

        depot.refresh_from_db()
        releve = releve_consignation(depot)
        self.assertEqual(releve['quantite_deposee'], 20)
        self.assertEqual(releve['quantite_consommee'], 8)
        self.assertEqual(releve['quantite_facturee'], 5)
        self.assertEqual(releve['quantite_restante'], 12)
        self.assertEqual(len(releve['declarations']), 2)


class Ntdst3ApiTests(Ntdst3Base):
    def test_creation_par_api_et_declaration(self):
        api = auth(self.admin)
        res = api.post(self.URL, {
            'client': self.client_crm.id, 'produit': self.produit.id,
            'quantite_deposee': 12, 'date_depot': JOUR.isoformat(),
            'company': self.autre.id,
        }, format='json')
        self.assertEqual(res.status_code, 201)
        depot_id = res.data['id']
        self.assertEqual(
            DepotConsignation.objects.get(id=depot_id).company_id,
            self.company.id)

        conso = api.post(f'{self.URL}{depot_id}/declarer-consommation/', {
            'quantite': 4, 'date_declaration': JOUR_CONSO.isoformat(),
        }, format='json')
        self.assertEqual(conso.status_code, 201)

        releve = api.get(f'{self.URL}{depot_id}/releve/')
        self.assertEqual(releve.data['quantite_restante'], 8)

    def test_un_patch_ne_peut_pas_forcer_la_quantite_consommee(self):
        depot = self._depot(quantite=10)
        res = auth(self.admin).patch(f'{self.URL}{depot.id}/', {
            'quantite_consommee_declaree': 10, 'statut': 'clos',
        }, format='json')
        self.assertEqual(res.status_code, 200)
        depot.refresh_from_db()
        self.assertEqual(depot.quantite_consommee_declaree, 0)
        self.assertEqual(depot.statut, DepotConsignation.Statut.ACTIF)

    def test_ecriture_refusee_a_un_role_normal(self):
        res = auth(self.normal).post(self.URL, {
            'client': self.client_crm.id, 'produit': self.produit.id,
            'quantite_deposee': 1, 'date_depot': JOUR.isoformat(),
        }, format='json')
        self.assertEqual(res.status_code, 403)

    def test_liste_ne_fuit_pas_une_autre_societe(self):
        self._depot(quantite=5)
        res = auth(self.admin).get(self.URL)
        self.assertEqual(len(res.data.get('results', res.data)), 1)
        # Une autre société ne voit rien de ce dépôt.
        autre_admin = User.objects.create_user(
            username='ntdst3_autre_admin', password='x', role_legacy='admin',
            company=self.autre)
        res_autre = auth(autre_admin).get(self.URL)
        self.assertEqual(len(res_autre.data.get('results', res_autre.data)), 0)

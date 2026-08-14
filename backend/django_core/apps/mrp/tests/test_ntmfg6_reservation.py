"""NTMFG6 — Réservation de composants sur l'Ordre de Fabrication.

Critère : confirmer un OF réserve les composants (visibles dans
`quantite_reservee`), écran OF montre la dispo par ligne, annulation libère."""
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.mrp.models import Gamme, OrdreFabrication, ReservationOF
from apps.mrp.selectors import disponibilite_par_ligne_of
from apps.mrp.services import annuler_of, cloturer_of, confirmer_of
from apps.stock.models import KitComposant, KitProduit, Produit

from ._fixtures import make_company, make_user


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_produit(company, nom, quantite_stock=0):
    return Produit.objects.create(
        company=company, nom=nom, prix_vente=0, tva=20,
        quantite_stock=quantite_stock)


class ReservationOfTests(TestCase):
    def setUp(self):
        self.company = make_company('mrp-resof-1', 'MRP RESOF 1')
        self.composant = make_produit(self.company, 'Composant A', quantite_stock=100)
        self.composite = make_produit(self.company, 'Composite A')
        self.kit = KitProduit.objects.create(company=self.company, nom='Kit A')
        KitComposant.objects.create(
            kit=self.kit, produit=self.composant, quantite=Decimal('3'))
        self.gamme = Gamme.objects.create(
            company=self.company, nom='Gamme A', produit=self.composite,
            kit_source=self.kit)

    def test_confirmer_seme_les_reservations(self):
        of = OrdreFabrication.objects.create(
            company=self.company, produit=self.composite, quantite=5,
            gamme=self.gamme)
        confirmer_of(of)
        reservations = list(ReservationOF.objects.filter(ordre_fabrication=of))
        self.assertEqual(len(reservations), 1)
        self.assertEqual(reservations[0].produit_id, self.composant.id)
        self.assertEqual(reservations[0].quantite, Decimal('15'))  # 5 x 3.

    def test_confirmer_est_idempotent_sur_reservations(self):
        of = OrdreFabrication.objects.create(
            company=self.company, produit=self.composite, quantite=5,
            gamme=self.gamme)
        confirmer_of(of)
        confirmer_of(of)
        self.assertEqual(
            ReservationOF.objects.filter(ordre_fabrication=of).count(), 1)

    def test_dispo_par_ligne_partiel(self):
        of = OrdreFabrication.objects.create(
            company=self.company, produit=self.composite, quantite=40,
            gamme=self.gamme)  # 40 x 3 = 120 > 100 en stock -> partiel.
        confirmer_of(of)
        lignes = disponibilite_par_ligne_of(of)
        self.assertEqual(len(lignes), 1)
        self.assertEqual(lignes[0]['statut'], 'partiel')
        self.assertEqual(Decimal(lignes[0]['quantite_reservee']), Decimal('120'))

    def test_dispo_par_ligne_manquant(self):
        self.composant.quantite_stock = 0
        self.composant.save(update_fields=['quantite_stock'])
        of = OrdreFabrication.objects.create(
            company=self.company, produit=self.composite, quantite=5,
            gamme=self.gamme)
        confirmer_of(of)
        lignes = disponibilite_par_ligne_of(of)
        self.assertEqual(lignes[0]['statut'], 'manquant')

    def test_dispo_par_ligne_disponible(self):
        of = OrdreFabrication.objects.create(
            company=self.company, produit=self.composite, quantite=5,
            gamme=self.gamme)  # 5 x 3 = 15 <= 100 en stock -> disponible.
        confirmer_of(of)
        lignes = disponibilite_par_ligne_of(of)
        self.assertEqual(lignes[0]['statut'], 'disponible')

    def test_annulation_libere_les_reservations(self):
        of = OrdreFabrication.objects.create(
            company=self.company, produit=self.composite, quantite=5,
            gamme=self.gamme)
        confirmer_of(of)
        self.assertEqual(
            ReservationOF.objects.filter(ordre_fabrication=of).count(), 1)
        annuler_of(of)
        of.refresh_from_db()
        self.assertEqual(of.statut, OrdreFabrication.Statut.ANNULE)
        self.assertEqual(
            ReservationOF.objects.filter(ordre_fabrication=of).count(), 0)

    def test_annulation_refusee_apres_backflush(self):
        of = OrdreFabrication.objects.create(
            company=self.company, produit=self.composite, quantite=5,
            gamme=self.gamme)
        confirmer_of(of)
        cloturer_of(of)
        of.refresh_from_db()
        with self.assertRaises(ValueError):
            annuler_of(of)


class ReservationOfApiTests(TestCase):
    def setUp(self):
        self.company = make_company('mrp-resof-api-1', 'MRP RESOF API 1')
        self.user = make_user(self.company, 'mrp-resof-api-user')
        self.api = auth(self.user)
        self.composant = make_produit(self.company, 'Composant API', quantite_stock=50)
        self.composite = make_produit(self.company, 'Composite API')
        kit = KitProduit.objects.create(company=self.company, nom='Kit API')
        KitComposant.objects.create(kit=kit, produit=self.composant, quantite=Decimal('2'))
        self.gamme = Gamme.objects.create(
            company=self.company, nom='Gamme API', produit=self.composite,
            kit_source=kit)

    def test_confirmer_puis_dispo_composants_via_api(self):
        of = OrdreFabrication.objects.create(
            company=self.company, produit=self.composite, quantite=4,
            gamme=self.gamme)
        resp = self.api.post(f'/api/django/mrp/ordres-fabrication/{of.id}/confirmer/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data['reservations']), 1)
        self.assertEqual(resp.data['reservations'][0]['quantite'], '8.00')

        resp = self.api.get(
            f'/api/django/mrp/ordres-fabrication/{of.id}/dispo-composants/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data[0]['statut'], 'disponible')

    def test_annuler_via_api(self):
        of = OrdreFabrication.objects.create(
            company=self.company, produit=self.composite, quantite=4,
            gamme=self.gamme)
        self.api.post(f'/api/django/mrp/ordres-fabrication/{of.id}/confirmer/')
        resp = self.api.post(f'/api/django/mrp/ordres-fabrication/{of.id}/annuler/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['statut'], 'annule')
        self.assertEqual(resp.data['reservations'], [])

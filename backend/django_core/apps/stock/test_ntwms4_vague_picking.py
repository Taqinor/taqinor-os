"""NTWMS4 — vagues de prélèvement multi-source, ordonnées par le parcours.

Critère d'acceptation testé : une vague issue de 3 chantiers produit UNE SEULE
liste de prélèvement triée par emplacement physique, JAMAIS par ordre de
création.

Run :
    python manage.py test apps.stock.test_ntwms4_vague_picking -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import (
    Categorie, EmplacementStock, LignePicking, Produit, VaguePicking,
)
from apps.stock.services import (
    creer_vague_depuis_besoins, lancer_vague, prelever_ligne_picking,
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


class Ntwms4Base(TestCase):
    def setUp(self):
        from apps.installations.models import BinAffectation, BinLocation

        self.company = make_company('ntwms4-co', 'NTWMS4 Co')
        self.autre = make_company('ntwms4-autre', 'NTWMS4 Autre')
        self.admin = User.objects.create_user(
            username='ntwms4_admin', password='x', role_legacy='admin',
            company=self.company)
        self.emplacement = EmplacementStock.objects.create(
            company=self.company, nom='Dépôt NTWMS4', is_principal=True)
        self.categorie = Categorie.objects.create(
            company=self.company, nom='Zone NTWMS4',
            strategie_picking_defaut=Categorie.StrategiePicking.ZONE)

        def _produit(nom, sku, ordre_casier, code):
            produit = Produit.objects.create(
                company=self.company, nom=nom, sku=sku,
                categorie=self.categorie, prix_achat=Decimal('10'),
                prix_vente=Decimal('20'), quantite_stock=100)
            casier = BinLocation.objects.create(
                company=self.company, emplacement=self.emplacement, code=code,
                zone=code[0], allee=code[2:4], casier=code[5:],
                ordre=ordre_casier)
            BinAffectation.objects.create(
                company=self.company, bin=casier, produit=produit,
                quantite=100)
            return produit

        # Créés dans l'ordre INVERSE du parcours physique : sans tri, la vague
        # sortirait C puis B puis A.
        self.produit_loin = _produit('Câble 6mm', 'CAB-NTWMS4', 90, 'C-09-07')
        self.produit_milieu = _produit('Coffret DC', 'COF-NTWMS4', 45,
                                       'B-04-02')
        self.produit_proche = _produit('Panneau 550', 'PAN-NTWMS4', 5,
                                       'A-01-01')
        self.api = auth(self.admin)

    def _besoins_trois_chantiers(self):
        """Trois sources distinctes (ici tracées par bon_commande_id=None et
        des produits différents) demandées dans le désordre du magasin."""
        return [
            {'produit_id': self.produit_loin.id, 'quantite': 3},
            {'produit_id': self.produit_milieu.id, 'quantite': 2},
            {'produit_id': self.produit_proche.id, 'quantite': 5},
        ]


class TestCreationVague(Ntwms4Base):
    def test_vague_triee_par_parcours_pas_par_creation(self):
        vague = creer_vague_depuis_besoins(
            company=self.company, user=self.admin,
            besoins=self._besoins_trois_chantiers())
        codes = [ligne.bin.code for ligne in vague.lignes.all()]
        self.assertEqual(codes, ['A-01-01', 'B-04-02', 'C-09-07'])
        self.assertEqual(
            [ligne.ordre_parcours for ligne in vague.lignes.all()], [1, 2, 3])

    def test_reference_race_safe_sans_trou(self):
        v1 = creer_vague_depuis_besoins(
            company=self.company, user=self.admin,
            besoins=self._besoins_trois_chantiers())
        v2 = creer_vague_depuis_besoins(
            company=self.company, user=self.admin,
            besoins=self._besoins_trois_chantiers())
        self.assertTrue(v1.reference.startswith('VAG-'))
        self.assertNotEqual(v1.reference, v2.reference)
        self.assertTrue(v1.reference.endswith('0001'))
        self.assertTrue(v2.reference.endswith('0002'))

    def test_besoin_vide_refuse(self):
        with self.assertRaises(ValueError):
            creer_vague_depuis_besoins(
                company=self.company, user=self.admin, besoins=[])

    def test_produit_d_une_autre_societe_ignore(self):
        etranger = Produit.objects.create(
            company=self.autre, nom='Intrus', sku='INT-NTWMS4',
            prix_achat=Decimal('1'), prix_vente=Decimal('2'))
        vague = creer_vague_depuis_besoins(
            company=self.company, user=self.admin,
            besoins=[
                {'produit_id': etranger.id, 'quantite': 4},
                {'produit_id': self.produit_proche.id, 'quantite': 1},
            ])
        self.assertEqual(vague.lignes.count(), 1)
        self.assertEqual(vague.lignes.first().produit_id,
                         self.produit_proche.id)


class TestCyclePrelevement(Ntwms4Base):
    def setUp(self):
        super().setUp()
        self.vague = creer_vague_depuis_besoins(
            company=self.company, user=self.admin,
            besoins=self._besoins_trois_chantiers())

    def test_prelevement_refuse_avant_lancement(self):
        ligne = self.vague.lignes.first()
        with self.assertRaises(ValueError):
            prelever_ligne_picking(ligne=ligne, quantite=1)

    def test_lancement_puis_prelevement_partiel(self):
        lancer_vague(self.vague)
        self.vague.refresh_from_db()
        self.assertEqual(self.vague.statut, VaguePicking.Statut.LANCEE)
        ligne = self.vague.lignes.first()
        prelever_ligne_picking(ligne=ligne, quantite=2)
        ligne.refresh_from_db()
        self.assertEqual(ligne.quantite_prelevee, 2)
        self.vague.refresh_from_db()
        self.assertEqual(self.vague.statut, VaguePicking.Statut.LANCEE)

    def test_depassement_refuse(self):
        lancer_vague(self.vague)
        ligne = self.vague.lignes.first()
        with self.assertRaises(ValueError):
            prelever_ligne_picking(
                ligne=ligne, quantite=ligne.quantite_demandee + 1)
        ligne.refresh_from_db()
        self.assertEqual(ligne.quantite_prelevee, 0)

    def test_vague_cloturee_quand_tout_est_servi(self):
        lancer_vague(self.vague)
        for ligne in self.vague.lignes.all():
            prelever_ligne_picking(
                ligne=ligne, quantite=ligne.quantite_demandee)
        self.vague.refresh_from_db()
        self.assertEqual(self.vague.statut, VaguePicking.Statut.TERMINEE)
        self.assertIsNotNone(self.vague.date_cloture)

    def test_lancement_idempotent(self):
        lancer_vague(self.vague)
        premiere_date = VaguePicking.objects.get(id=self.vague.id).date_lancement
        lancer_vague(VaguePicking.objects.get(id=self.vague.id))
        self.assertEqual(
            VaguePicking.objects.get(id=self.vague.id).date_lancement,
            premiere_date)


class TestEndpointsVague(Ntwms4Base):
    def test_creation_et_lancement_par_api(self):
        resp = self.api.post(
            '/api/django/stock/vagues-picking/',
            {'besoins': self._besoins_trois_chantiers()}, format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertEqual([ligne['bin_code'] for ligne in resp.data['lignes']],
                         ['A-01-01', 'B-04-02', 'C-09-07'])
        vague_id = resp.data['id']

        resp = self.api.post(
            f'/api/django/stock/vagues-picking/{vague_id}/lancer/',
            {}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['statut'], 'lancee')

        ligne_id = resp.data['lignes'][0]['id']
        resp = self.api.post(
            f'/api/django/stock/vagues-picking/{vague_id}/lignes/{ligne_id}/'
            'prelever/', {'quantite': 1}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['lignes'][0]['quantite_prelevee'], 1)

    def test_ligne_d_une_autre_vague_refusee(self):
        v1 = creer_vague_depuis_besoins(
            company=self.company, user=self.admin,
            besoins=self._besoins_trois_chantiers())
        v2 = creer_vague_depuis_besoins(
            company=self.company, user=self.admin,
            besoins=self._besoins_trois_chantiers())
        lancer_vague(v1)
        ligne_etrangere = v2.lignes.first()
        resp = self.api.post(
            f'/api/django/stock/vagues-picking/{v1.id}/lignes/'
            f'{ligne_etrangere.id}/prelever/', {'quantite': 1}, format='json')
        self.assertEqual(resp.status_code, 404)

    def test_isolation_societe(self):
        vague = creer_vague_depuis_besoins(
            company=self.company, user=self.admin,
            besoins=self._besoins_trois_chantiers())
        intrus = User.objects.create_user(
            username='ntwms4_intrus', password='x', role_legacy='admin',
            company=self.autre)
        resp = auth(intrus).get(
            f'/api/django/stock/vagues-picking/{vague.id}/')
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(
            LignePicking.objects.filter(company=self.autre).count(), 0)

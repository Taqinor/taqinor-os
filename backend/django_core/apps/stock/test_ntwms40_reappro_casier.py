"""NTWMS40 — réapprovisionnement d'un casier picking depuis le stockage.

Critère d'acceptation testé : un casier picking SOUS son seuil apparaît dans
la liste des réappros internes dus — SANS attendre la rupture totale — avec
le casier de stockage le plus proche comme source.

Run :
    python manage.py test apps.stock.test_ntwms40_reappro_casier -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import (
    EmplacementStock, Produit, SeuilReapproCasier, TacheReapproInterne,
)
from apps.stock.services_reappro_casier import (
    casiers_picking_a_reapprovisionner, generer_taches_reappro_interne,
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


class Ntwms40Base(TestCase):
    def setUp(self):
        from apps.installations.models import BinAffectation, BinLocation

        self.company = make_company('ntwms40-co', 'NTWMS40 Co')
        self.autre = make_company('ntwms40-autre', 'NTWMS40 Autre')
        self.admin = User.objects.create_user(
            username='ntwms40_admin', password='x', role_legacy='admin',
            company=self.company)
        self.normal = User.objects.create_user(
            username='ntwms40_normal', password='x', role_legacy='normal',
            company=self.company)
        self.emplacement = EmplacementStock.objects.create(
            company=self.company, nom='Dépôt NTWMS40', is_principal=True)

        self.pick = BinLocation.objects.create(
            company=self.company, emplacement=self.emplacement,
            code='P-01-01', zone='P', allee='01', casier='01', ordre=100)
        self.stock_proche = BinLocation.objects.create(
            company=self.company, emplacement=self.emplacement,
            code='S-01-01', zone='S', allee='01', casier='01', ordre=120)
        self.stock_loin = BinLocation.objects.create(
            company=self.company, emplacement=self.emplacement,
            code='S-09-01', zone='S', allee='09', casier='01', ordre=900)

        self.produit = Produit.objects.create(
            company=self.company, nom='Connecteur MC4', sku='MC4-NTWMS40',
            prix_achat=Decimal('10'), prix_vente=Decimal('18'),
            quantite_stock=500)
        self._BinAffectation = BinAffectation
        # 3 unités au casier de picking, du stock ailleurs.
        self._BinAffectation.objects.create(
            company=self.company, bin=self.pick, produit=self.produit,
            quantite=3)
        self._BinAffectation.objects.create(
            company=self.company, bin=self.stock_proche, produit=self.produit,
            quantite=200)
        self._BinAffectation.objects.create(
            company=self.company, bin=self.stock_loin, produit=self.produit,
            quantite=200)


class Ntwms40SelecteurTests(Ntwms40Base):
    def test_un_casier_sous_son_seuil_est_du_avant_la_rupture(self):
        SeuilReapproCasier.objects.create(
            company=self.company, bin=self.pick, produit=self.produit,
            seuil=10, quantite_cible=40)

        dus = casiers_picking_a_reapprovisionner(self.company)

        self.assertEqual(len(dus), 1)
        self.assertEqual(dus[0]['bin'], self.pick.id)
        self.assertEqual(dus[0]['quantite_presente'], 3)
        self.assertEqual(dus[0]['quantite_a_transferer'], 37)
        self.assertEqual(dus[0]['bin_source'], self.stock_proche.id)

    def test_un_casier_au_dessus_de_son_seuil_nest_jamais_du(self):
        SeuilReapproCasier.objects.create(
            company=self.company, bin=self.pick, produit=self.produit,
            seuil=2)
        self.assertEqual(casiers_picking_a_reapprovisionner(self.company), [])

    def test_un_casier_sans_seuil_declare_nest_jamais_du(self):
        self.assertEqual(casiers_picking_a_reapprovisionner(self.company), [])

    def test_la_cible_par_defaut_vaut_le_double_du_seuil(self):
        seuil = SeuilReapproCasier.objects.create(
            company=self.company, bin=self.pick, produit=self.produit,
            seuil=20)
        self.assertEqual(seuil.cible, 40)
        dus = casiers_picking_a_reapprovisionner(self.company)
        self.assertEqual(dus[0]['quantite_a_transferer'], 37)

    def test_un_seuil_inactif_ou_un_casier_archive_est_ignore(self):
        seuil = SeuilReapproCasier.objects.create(
            company=self.company, bin=self.pick, produit=self.produit,
            seuil=10, actif=False)
        self.assertEqual(casiers_picking_a_reapprovisionner(self.company), [])

        seuil.actif = True
        seuil.save(update_fields=['actif'])
        self.pick.archived = True
        self.pick.save(update_fields=['archived'])
        self.assertEqual(casiers_picking_a_reapprovisionner(self.company), [])

    def test_aucun_casier_dune_autre_societe(self):
        SeuilReapproCasier.objects.create(
            company=self.company, bin=self.pick, produit=self.produit,
            seuil=10)
        dus = casiers_picking_a_reapprovisionner(self.autre)
        self.assertEqual(dus, [])


class Ntwms40TacheTests(Ntwms40Base):
    def setUp(self):
        super().setUp()
        SeuilReapproCasier.objects.create(
            company=self.company, bin=self.pick, produit=self.produit,
            seuil=10, quantite_cible=40)

    def test_la_generation_cree_une_tache_avec_sa_source(self):
        creees = generer_taches_reappro_interne(self.company, self.admin)
        self.assertEqual(len(creees), 1)
        tache = creees[0]
        self.assertEqual(tache.bin_cible_id, self.pick.id)
        self.assertEqual(tache.bin_source_id, self.stock_proche.id)
        self.assertEqual(tache.quantite, 37)
        self.assertEqual(tache.statut, TacheReapproInterne.Statut.A_FAIRE)

    def test_la_generation_est_idempotente(self):
        generer_taches_reappro_interne(self.company, self.admin)
        self.assertEqual(
            generer_taches_reappro_interne(self.company, self.admin), [])
        self.assertEqual(TacheReapproInterne.objects.filter(
            company=self.company).count(), 1)

    def test_la_tache_ne_bouge_aucun_stock(self):
        avant = self.produit.quantite_stock
        generer_taches_reappro_interne(self.company, self.admin)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, avant)
        self.assertEqual(
            self._BinAffectation.objects.get(bin=self.pick).quantite, 3)


class Ntwms40ApiTests(Ntwms40Base):
    URL = '/api/django/stock/casiers-a-reapprovisionner/'

    def setUp(self):
        super().setUp()
        SeuilReapproCasier.objects.create(
            company=self.company, bin=self.pick, produit=self.produit,
            seuil=10, quantite_cible=40)

    def test_get_liste_les_casiers_dus(self):
        res = auth(self.admin).get(self.URL)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data['casiers']), 1)
        self.assertEqual(res.data['taches_creees'], 0)

    def test_post_genere_les_taches(self):
        res = auth(self.admin).post(self.URL)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['taches_creees'], 1)

    def test_endpoint_refuse_un_role_normal(self):
        self.assertEqual(auth(self.normal).get(self.URL).status_code, 403)

    def test_endpoint_refuse_lanonyme(self):
        self.assertEqual(APIClient().get(self.URL).status_code, 401)

    def test_crud_seuil_force_la_societe_serveur(self):
        res = auth(self.admin).post(
            '/api/django/stock/seuils-reappro-casier/',
            {'bin': self.stock_proche.id, 'produit': self.produit.id,
             'seuil': 5, 'company': self.autre.id}, format='json')
        self.assertEqual(res.status_code, 201)
        seuil = SeuilReapproCasier.objects.get(id=res.data['id'])
        self.assertEqual(seuil.company_id, self.company.id)

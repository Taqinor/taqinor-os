"""NTWMS38 — marchandises dangereuses / matières sensibles (flag hazmat).

Critère d'acceptation testé : suggérer un casier pour une BATTERIE LITHIUM
exclut automatiquement les casiers non marqués compatibles — et un produit
ordinaire garde exactement le comportement historique (aucun filtrage).

Run :
    python manage.py test apps.stock.test_ntwms38_hazmat -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import (
    CompatibiliteHazmatCasier, EmplacementStock, Produit,
)
from apps.stock.services_hazmat import (
    casier_accepte_produit, casiers_compatibles_ids, suggerer_bin_hazmat_safe,
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


class Ntwms38Base(TestCase):
    def setUp(self):
        from apps.installations.models import BinLocation

        self.company = make_company('ntwms38-co', 'NTWMS38 Co')
        self.autre = make_company('ntwms38-autre', 'NTWMS38 Autre')
        self.admin = User.objects.create_user(
            username='ntwms38_admin', password='x', role_legacy='admin',
            company=self.company)
        self.normal = User.objects.create_user(
            username='ntwms38_normal', password='x', role_legacy='normal',
            company=self.company)
        self.emplacement = EmplacementStock.objects.create(
            company=self.company, nom='Dépôt NTWMS38', is_principal=True)

        self.casier_nu = BinLocation.objects.create(
            company=self.company, emplacement=self.emplacement,
            code='A-01-01', zone='A', allee='01', casier='01', ordre=10)
        self.casier_lithium = BinLocation.objects.create(
            company=self.company, emplacement=self.emplacement,
            code='H-01-01', zone='H', allee='01', casier='01', ordre=500)
        CompatibiliteHazmatCasier.objects.create(
            company=self.company, bin=self.casier_lithium,
            classe_danger=Produit.ClasseDanger.BATTERIE_LITHIUM)

        self.batterie = Produit.objects.create(
            company=self.company, nom='Batterie LiFePO4 5 kWh',
            sku='BAT5-NTWMS38', prix_achat=Decimal('9000'),
            prix_vente=Decimal('12000'), quantite_stock=10,
            classe_danger=Produit.ClasseDanger.BATTERIE_LITHIUM)
        self.panneau = Produit.objects.create(
            company=self.company, nom='Panneau 550 Wc', sku='PAN-NTWMS38',
            prix_achat=Decimal('900'), prix_vente=Decimal('1200'),
            quantite_stock=40)


class Ntwms38RegleTests(Ntwms38Base):
    def test_le_defaut_est_aucune_pour_tout_produit_existant(self):
        self.assertEqual(self.panneau.classe_danger,
                         Produit.ClasseDanger.AUCUNE)

    def test_un_produit_ordinaire_est_accepte_partout(self):
        self.assertTrue(casier_accepte_produit(
            self.company, self.casier_nu.id, self.panneau))
        self.assertTrue(casier_accepte_produit(
            self.company, self.casier_lithium.id, self.panneau))

    def test_une_batterie_est_refusee_par_un_casier_non_declare(self):
        self.assertFalse(casier_accepte_produit(
            self.company, self.casier_nu.id, self.batterie))

    def test_une_batterie_est_acceptee_par_le_casier_declare(self):
        self.assertTrue(casier_accepte_produit(
            self.company, self.casier_lithium.id, self.batterie))

    def test_une_autre_classe_de_danger_ne_passe_pas_par_la_meme_porte(self):
        corrosif = Produit.objects.create(
            company=self.company, nom='Acide', sku='ACID-NTWMS38',
            prix_achat=Decimal('50'), prix_vente=Decimal('80'),
            quantite_stock=1, classe_danger=Produit.ClasseDanger.CORROSIF)
        self.assertFalse(casier_accepte_produit(
            self.company, self.casier_lithium.id, corrosif))

    def test_le_filtre_de_liste_ne_garde_que_les_casiers_compatibles(self):
        ids = [self.casier_nu.id, self.casier_lithium.id]
        self.assertEqual(
            casiers_compatibles_ids(self.company, self.batterie, ids),
            [self.casier_lithium.id])
        self.assertEqual(
            casiers_compatibles_ids(self.company, self.panneau, ids), ids)

    def test_une_autorisation_dune_autre_societe_ne_compte_pas(self):
        from apps.installations.models import BinLocation

        casier_voisin = BinLocation.objects.create(
            company=self.company, emplacement=self.emplacement,
            code='X-01-01', zone='X', allee='01', casier='01', ordre=700)
        CompatibiliteHazmatCasier.objects.create(
            company=self.autre, bin=casier_voisin,
            classe_danger=Produit.ClasseDanger.BATTERIE_LITHIUM)
        self.assertFalse(casier_accepte_produit(
            self.company, casier_voisin.id, self.batterie))


class Ntwms38SuggestionTests(Ntwms38Base):
    def test_la_suggestion_exclut_le_casier_non_compatible(self):
        bin_loc = suggerer_bin_hazmat_safe(
            self.company, self.batterie, self.emplacement.id, 2)
        self.assertIsNotNone(bin_loc)
        self.assertEqual(bin_loc.id, self.casier_lithium.id)

    def test_la_suggestion_accepte_un_id_de_produit_sans_perdre_la_garde(self):
        bin_loc = suggerer_bin_hazmat_safe(
            self.company, self.batterie.id, self.emplacement.id, 2)
        self.assertEqual(bin_loc.id, self.casier_lithium.id)

    def test_sans_aucun_casier_compatible_on_ne_suggere_rien(self):
        CompatibiliteHazmatCasier.objects.all().delete()
        self.assertIsNone(suggerer_bin_hazmat_safe(
            self.company, self.batterie, self.emplacement.id, 1))

    def test_un_produit_ordinaire_garde_la_suggestion_historique(self):
        bin_loc = suggerer_bin_hazmat_safe(
            self.company, self.panneau, self.emplacement.id, 5)
        self.assertIsNotNone(bin_loc)


class Ntwms38ApiTests(Ntwms38Base):
    URL = '/api/django/stock/casiers-hazmat/'

    def test_creation_force_la_societe_serveur(self):
        res = auth(self.admin).post(self.URL, {
            'bin': self.casier_nu.id, 'classe_danger': 'INFLAMMABLE',
            'company': self.autre.id,
        }, format='json')
        self.assertEqual(res.status_code, 201)
        obj = CompatibiliteHazmatCasier.objects.get(id=res.data['id'])
        self.assertEqual(obj.company_id, self.company.id)

    def test_classe_aucune_est_refusee(self):
        res = auth(self.admin).post(self.URL, {
            'bin': self.casier_nu.id, 'classe_danger': 'AUCUNE',
        }, format='json')
        self.assertEqual(res.status_code, 400)

    def test_classe_inconnue_est_refusee(self):
        res = auth(self.admin).post(self.URL, {
            'bin': self.casier_nu.id, 'classe_danger': 'RADIOACTIF',
        }, format='json')
        self.assertEqual(res.status_code, 400)

    def test_ecriture_refusee_a_un_role_normal(self):
        res = auth(self.normal).post(self.URL, {
            'bin': self.casier_nu.id, 'classe_danger': 'CORROSIF',
        }, format='json')
        self.assertEqual(res.status_code, 403)

    def test_liste_ne_fuit_pas_une_autre_societe(self):
        CompatibiliteHazmatCasier.objects.create(
            company=self.autre, bin=self.casier_nu,
            classe_danger=Produit.ClasseDanger.CORROSIF)
        res = auth(self.admin).get(self.URL)
        resultats = res.data.get('results', res.data)
        self.assertEqual(len(resultats), 1)

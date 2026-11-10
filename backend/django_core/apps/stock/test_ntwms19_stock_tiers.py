"""NTWMS19 — stock chez des tiers / de tiers (3PL).

Critère d'acceptation testé : le stock d'un `EmplacementStock` marqué
`DE_TIERS` n'apparaît JAMAIS dans la valorisation comptable de la société tout
en restant visible et gérable opérationnellement.

Run :
    python manage.py test apps.stock.test_ntwms19_stock_tiers -v 2
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import (
    EmplacementStock, MouvementStock, Produit, StockEmplacement,
)
from apps.stock.services import (
    creer_revalorisation, quantite_de_tiers, valorisation_a_date,
)

User = get_user_model()

DATE_REF = datetime.date(2026, 7, 20)


def make_company(slug, nom):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Ntwms19Base(TestCase):
    def setUp(self):
        self.company = make_company('ntwms19-co', 'NTWMS19 Co')
        self.autre = make_company('ntwms19-autre', 'NTWMS19 Autre')
        self.admin = User.objects.create_user(
            username='ntwms19_admin', password='x', role_legacy='admin',
            company=self.company)
        self.principal = EmplacementStock.objects.create(
            company=self.company, nom='Dépôt NTWMS19', is_principal=True)
        self.depot_client = EmplacementStock.objects.create(
            company=self.company, nom='Dépôt-vente client Alpha',
            type_proprietaire=EmplacementStock.TypeProprietaire.DE_TIERS,
            tiers_nom='Client Alpha')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur 3kW', sku='OND3-NTWMS19',
            prix_achat=Decimal('5000'), prix_vente=Decimal('7000'),
            quantite_stock=10)
        # 10 unités au total, dont 4 appartenant au client Alpha.
        StockEmplacement.objects.create(
            company=self.company, produit=self.produit,
            emplacement=self.depot_client, quantite=4)
        mouvement = MouvementStock.objects.create(
            company=self.company, produit=self.produit,
            type_mouvement='entree', quantite=10, quantite_avant=0,
            quantite_apres=10, created_by=self.admin)
        MouvementStock.objects.filter(id=mouvement.id).update(
            date=timezone.make_aware(
                datetime.datetime.combine(
                    datetime.date(2026, 7, 1), datetime.time(8, 0)),
                timezone.get_default_timezone()))
        self.api = auth(self.admin)


class TestExclusionValorisation(Ntwms19Base):
    def test_quantite_de_tiers_est_isolee(self):
        self.assertEqual(
            quantite_de_tiers(self.company, produit=self.produit), 4)
        self.assertEqual(
            quantite_de_tiers(self.company), {self.produit.id: 4})

    def test_valorisation_exclut_le_stock_de_tiers(self):
        rapport = valorisation_a_date(self.company, DATE_REF)
        ligne = next(ligne for ligne in rapport['lignes']
                     if ligne['produit_id'] == self.produit.id)
        # 10 en stock − 4 appartenant au client = 6 valorisées.
        self.assertEqual(ligne['quantite'], 6)
        self.assertEqual(ligne['valeur'], Decimal('30000.00'))

    def test_sans_emplacement_de_tiers_comportement_inchange(self):
        StockEmplacement.objects.filter(
            emplacement=self.depot_client).delete()
        rapport = valorisation_a_date(self.company, DATE_REF)
        ligne = next(ligne for ligne in rapport['lignes']
                     if ligne['produit_id'] == self.produit.id)
        self.assertEqual(ligne['quantite'], 10)

    def test_revalorisation_ne_porte_que_sur_notre_stock(self):
        revalorisation = creer_revalorisation(
            company=self.company, produit=self.produit,
            nouveau_cout=Decimal('5500'), motif='Hausse fournisseur',
            user=self.admin)
        self.assertEqual(revalorisation.quantite_snapshot, 6)

    def test_stock_chez_tiers_reste_valorise(self):
        """CHEZ_TIERS = notre marchandise ailleurs : elle reste notre actif."""
        chez_3pl = EmplacementStock.objects.create(
            company=self.company, nom='Entrepôt 3PL Casablanca',
            type_proprietaire=EmplacementStock.TypeProprietaire.CHEZ_TIERS,
            tiers_nom='LogiPro')
        StockEmplacement.objects.create(
            company=self.company, produit=self.produit,
            emplacement=chez_3pl, quantite=3)
        self.assertEqual(
            quantite_de_tiers(self.company, produit=self.produit), 4)


class TestEndpointEmplacementsTiers(Ntwms19Base):
    URL = '/api/django/stock/emplacements/'

    def test_filtre_par_type_proprietaire(self):
        reponse = self.api.get(self.URL, {'type_proprietaire': 'de_tiers'})
        self.assertEqual(reponse.status_code, 200)
        resultats = reponse.data.get('results', reponse.data)
        self.assertEqual(len(resultats), 1)
        self.assertEqual(resultats[0]['tiers_nom'], 'Client Alpha')

    def test_emplacement_de_tiers_sans_nom_refuse(self):
        reponse = self.api.post(self.URL, {
            'nom': 'Dépôt sans nom de tiers',
            'type_proprietaire': 'de_tiers',
        }, format='json')
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('tiers_nom', reponse.data)

    def test_creation_emplacement_de_tiers(self):
        reponse = self.api.post(self.URL, {
            'nom': 'Dépôt-vente Beta', 'type_proprietaire': 'de_tiers',
            'tiers_nom': 'Client Beta',
        }, format='json')
        self.assertEqual(reponse.status_code, 201)
        self.assertEqual(reponse.data['type_proprietaire'], 'de_tiers')

    def test_depot_principal_reste_interne(self):
        reponse = self.api.patch(
            f'{self.URL}{self.principal.id}/',
            {'type_proprietaire': 'de_tiers', 'tiers_nom': 'X'},
            format='json')
        self.assertEqual(reponse.status_code, 409)  # ENF11 : règle d'état
        self.assertIn('type_proprietaire', reponse.data)

    def test_patch_nom_de_tiers_vide_corps_400_instance_409(self):
        """api-fuzz stock (vague 8) — PATCH : la règle portée par le CORPS seul
        (type de tiers + nom vide) est publiée → 400 ; un nom vidé sur un
        emplacement ENREGISTRÉ de tiers est un refus d'état → 409."""
        url = f'{self.URL}{self.depot_client.id}/'
        r = self.api.patch(url, {'type_proprietaire': 'de_tiers', 'tiers_nom': ''},
                           format='json')
        self.assertEqual(r.status_code, 400, r.content)
        r = self.api.patch(url, {'tiers_nom': ''}, format='json')
        self.assertEqual(r.status_code, 409, r.content)
        self.assertIn('tiers_nom', r.data)
        self.depot_client.refresh_from_db()
        self.assertEqual(self.depot_client.tiers_nom, 'Client Alpha')


class IdentiteFournisseurSansPrixTests(TestCase):
    """AUDV23 (déplacé de apps.tiers.tests) — garde permanente : le pont
    d'identité fournisseur → Tiers ne pousse QUE de l'identité."""

    def test_aucun_prix_d_achat_ne_traverse_le_pont(self):
        import inspect

        from apps.stock.services import ecrire_identite_fournisseur
        source = inspect.getsource(ecrire_identite_fournisseur)
        self.assertNotIn('prix_achat', source)
        self.assertNotIn('marge', source)

    def test_effacement_dsr_vide_le_contact_du_tiers(self):
        """ASOC101 (C-ASOC-060) — le contact pseudonymisé quitte aussi le
        Tiers miroir ; raison sociale, ICE et rôle fournisseur gardés ;
        un fournisseur d'une autre société reste intact."""
        from authentication.models import Company

        from apps.stock.dsr_provider import erase_stock
        from apps.stock.models import Fournisseur
        from apps.tiers.models import Tiers
        company = Company.objects.create(nom='ASOC101', slug='asoc101')
        autre = Company.objects.create(nom='ASOC101 b', slug='asoc101-b')
        f = Fournisseur.objects.create(
            company=company, nom='ACME Solaire', ice='001122334455667',
            contact_personne='Karim', email='karim.asoc101@example.ma',
            telephone='0661223344')
        voisin = Fournisseur.objects.create(
            company=autre, nom='Voisin', email='karim.asoc101@example.ma',
            telephone='0661223344')
        f.refresh_from_db()
        voisin.refresh_from_db()

        self.assertEqual(erase_stock(company, 'karim.asoc101@example.ma')
                         ['pseudonymises'], 1)
        Fournisseur.objects.get(pk=f.pk).save()  # re-save : rien ne revient

        tiers = Tiers.objects.get(pk=f.tiers_id)
        self.assertEqual((tiers.email, tiers.telephone), ('', ''))
        self.assertEqual(tiers.nom, 'ACME Solaire')
        self.assertEqual(tiers.raison_sociale, 'ACME Solaire')
        self.assertEqual(tiers.ice, '001122334455667')
        self.assertTrue(tiers.is_fournisseur)
        intact = Tiers.objects.get(pk=voisin.tiers_id)
        self.assertEqual(intact.telephone, '0661223344')

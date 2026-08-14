"""NTWMS29 — cockpit entrepôt : tout en une requête.

Critère d'acceptation testé : un responsable d'entrepôt voit EN UN COUP D'ŒIL
les vagues en retard et les lots à péremption imminente — sans naviguer entre
écrans, donc dans UNE seule réponse.

L'horloge est toujours INJECTÉE (`maintenant=`) : la suite ne lit jamais
l'heure système.

Run :
    python manage.py test apps.stock.test_ntwms29_cockpit_entrepot -v 2
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import EmplacementStock, LotEntrepot, Produit
from apps.stock.models_wms import LignePicking, VaguePicking
from apps.stock.selectors import cockpit_entrepot, remplissage_par_zone

User = get_user_model()

# Instant de référence FIXE (aware) — jamais l'horloge réelle.
MAINTENANT = timezone.make_aware(datetime.datetime(2026, 5, 20, 9, 0))


def make_company(slug, nom):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Ntwms29Base(TestCase):
    def setUp(self):
        from apps.installations.models import (
            BinAffectation, BinLocation, CategorieStockage,
        )

        self.company = make_company('ntwms29-co', 'NTWMS29 Co')
        self.autre = make_company('ntwms29-autre', 'NTWMS29 Autre')
        self.admin = User.objects.create_user(
            username='ntwms29_admin', password='x', role_legacy='admin',
            company=self.company)
        self.normal = User.objects.create_user(
            username='ntwms29_normal', password='x', role_legacy='normal',
            company=self.company)
        self.emplacement = EmplacementStock.objects.create(
            company=self.company, nom='Dépôt NTWMS29', is_principal=True)

        self.categorie_stockage = CategorieStockage.objects.create(
            company=self.company, nom='Rayonnage 100', qte_max=100)
        self.bin_a = BinLocation.objects.create(
            company=self.company, emplacement=self.emplacement,
            code='A-01-01', zone='A', allee='01', casier='01', ordre=10,
            categorie=self.categorie_stockage)
        self.bin_z = BinLocation.objects.create(
            company=self.company, emplacement=self.emplacement,
            code='Z-09-01', zone='Z', allee='09', casier='01', ordre=900,
            categorie=self.categorie_stockage)

        self.produit = Produit.objects.create(
            company=self.company, nom='Batterie 5 kWh', sku='BAT5-NTWMS29',
            prix_achat=Decimal('4000'), prix_vente=Decimal('5200'),
            quantite_stock=120)
        # Zone A remplie à 98/100 -> au-dessus du seuil de sur-capacité.
        BinAffectation.objects.create(
            company=self.company, bin=self.bin_a, produit=self.produit,
            quantite=98)
        BinAffectation.objects.create(
            company=self.company, bin=self.bin_z, produit=self.produit,
            quantite=10)


class Ntwms29CockpitTests(Ntwms29Base):
    def test_vague_lancee_depuis_plus_de_24h_est_en_retard(self):
        vieille = VaguePicking.objects.create(
            company=self.company, reference='VAG-202605-0001',
            statut=VaguePicking.Statut.LANCEE,
            date_lancement=MAINTENANT - datetime.timedelta(hours=30))
        recente = VaguePicking.objects.create(
            company=self.company, reference='VAG-202605-0002',
            statut=VaguePicking.Statut.LANCEE,
            date_lancement=MAINTENANT - datetime.timedelta(hours=2))
        LignePicking.objects.create(
            company=self.company, vague=vieille, produit=self.produit,
            quantite_demandee=10, quantite_prelevee=3, bin=self.bin_a)
        LignePicking.objects.create(
            company=self.company, vague=recente, produit=self.produit,
            quantite_demandee=5, quantite_prelevee=0, bin=self.bin_z)

        data = cockpit_entrepot(self.company, maintenant=MAINTENANT)

        self.assertEqual(data['vagues_en_retard'], 1)
        par_ref = {v['reference']: v for v in data['vagues']}
        self.assertTrue(par_ref['VAG-202605-0001']['en_retard'])
        self.assertFalse(par_ref['VAG-202605-0002']['en_retard'])
        self.assertEqual(par_ref['VAG-202605-0001']['reste_a_prelever'], 7)

    def test_lot_proche_peremption_remonte_avec_ses_jours_restants(self):
        aujourdhui = timezone.localdate(MAINTENANT)
        LotEntrepot.objects.create(
            company=self.company, produit=self.produit, numero_lot='L-PROCHE',
            date_peremption=aujourdhui + datetime.timedelta(days=10),
            quantite_recue=20, quantite_restante=20)
        LotEntrepot.objects.create(
            company=self.company, produit=self.produit, numero_lot='L-LOIN',
            date_peremption=aujourdhui + datetime.timedelta(days=400),
            quantite_recue=20, quantite_restante=20)
        LotEntrepot.objects.create(
            company=self.company, produit=self.produit, numero_lot='L-EPUISE',
            date_peremption=aujourdhui + datetime.timedelta(days=5),
            quantite_recue=20, quantite_restante=0)

        data = cockpit_entrepot(self.company, maintenant=MAINTENANT)

        numeros = [lot['numero_lot'] for lot in data['lots_peremption']]
        self.assertEqual(numeros, ['L-PROCHE'])
        self.assertEqual(data['lots_peremption'][0]['jours_restants'], 10)
        self.assertFalse(data['lots_peremption'][0]['perime'])

    def test_remplissage_par_zone_et_surcapacite(self):
        zones = {z['zone']: z for z in remplissage_par_zone(self.company)}
        self.assertEqual(zones['A']['occupe'], 98)
        self.assertEqual(zones['A']['capacite'], 100)
        self.assertEqual(zones['A']['taux_pct'], '98')
        self.assertEqual(zones['Z']['taux_pct'], '10')

        data = cockpit_entrepot(self.company, maintenant=MAINTENANT)
        alertes = [z['zone'] for z in data['zones_en_surcapacite']]
        self.assertEqual(alertes, ['A'])

    def test_zone_sans_capacite_declaree_na_pas_de_taux_invente(self):
        from apps.installations.models import BinAffectation, BinLocation

        sans_cat = BinLocation.objects.create(
            company=self.company, emplacement=self.emplacement,
            code='B-01-01', zone='B', allee='01', casier='01', ordre=50)
        BinAffectation.objects.create(
            company=self.company, bin=sans_cat, produit=self.produit,
            quantite=42)

        zones = {z['zone']: z for z in remplissage_par_zone(self.company)}
        self.assertEqual(zones['B']['occupe'], 42)
        self.assertIsNone(zones['B']['capacite'])
        self.assertIsNone(zones['B']['taux_pct'])

    def test_cockpit_ne_voit_jamais_les_donnees_dune_autre_societe(self):
        autre_produit = Produit.objects.create(
            company=self.autre, nom='Produit voisin', sku='VOISIN-29',
            prix_achat=Decimal('10'), prix_vente=Decimal('20'),
            quantite_stock=5)
        LotEntrepot.objects.create(
            company=self.autre, produit=autre_produit, numero_lot='L-AUTRE',
            date_peremption=timezone.localdate(MAINTENANT),
            quantite_recue=5, quantite_restante=5)
        VaguePicking.objects.create(
            company=self.autre, reference='VAG-202605-0009',
            statut=VaguePicking.Statut.LANCEE,
            date_lancement=MAINTENANT - datetime.timedelta(hours=48))

        data = cockpit_entrepot(self.company, maintenant=MAINTENANT)
        self.assertEqual(data['lots_peremption'], [])
        self.assertEqual(data['vagues'], [])
        self.assertEqual(data['vagues_en_retard'], 0)


class Ntwms29EndpointTests(Ntwms29Base):
    URL = '/api/django/stock/entrepot/cockpit/'

    def test_endpoint_repond_au_responsable_et_agrege_les_cinq_blocs(self):
        api = auth(self.admin)
        res = api.get(self.URL)
        self.assertEqual(res.status_code, 200)
        for cle in ('zones', 'vagues', 'vagues_en_retard', 'comptages_dus',
                    'expeditions_du_jour', 'lots_peremption'):
            self.assertIn(cle, res.data)

    def test_endpoint_refuse_un_role_normal(self):
        res = auth(self.normal).get(self.URL)
        self.assertEqual(res.status_code, 403)

    def test_endpoint_refuse_lanonyme(self):
        self.assertEqual(APIClient().get(self.URL).status_code, 401)

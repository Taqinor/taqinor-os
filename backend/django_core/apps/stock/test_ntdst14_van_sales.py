"""NTDST14 — tournées de vente / van sales : stock embarqué véhicule.

Critère d'acceptation testé : charger 10 unités d'un produit dans un véhicule
décrémente le dépôt principal de 10 et N'AFFECTE AUCUN AUTRE EMPLACEMENT.

Run :
    python manage.py test apps.stock.test_ntdst14_van_sales -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import (
    EmplacementStock, MouvementStock, ParametresNegoce, Produit,
    StockEmplacement, StockVehicule,
)
from apps.stock.services_van_sales import (
    charger_vehicule, decharger_vehicule, stock_embarque,
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


class Ntdst14Base(TestCase):
    def setUp(self):
        from apps.flotte.models import ActifFlotte, Vehicule

        self.company = make_company('ntdst14-co', 'NTDST14 Co')
        self.autre = make_company('ntdst14-autre', 'NTDST14 Autre')
        self.admin = User.objects.create_user(
            username='ntdst14_admin', password='x', role_legacy='admin',
            company=self.company)
        self.normal = User.objects.create_user(
            username='ntdst14_normal', password='x', role_legacy='normal',
            company=self.company)

        self.principal = EmplacementStock.objects.create(
            company=self.company, nom='Dépôt NTDST14', is_principal=True)
        self.annexe = EmplacementStock.objects.create(
            company=self.company, nom='Annexe NTDST14')
        self.produit = Produit.objects.create(
            company=self.company, nom='Régulateur MPPT', sku='MPPT-NTDST14',
            prix_achat=Decimal('800'), prix_vente=Decimal('1100'),
            quantite_stock=50)
        # 12 unités ventilées sur l'annexe : elles ne doivent JAMAIS bouger.
        self.se_annexe = StockEmplacement.objects.create(
            company=self.company, produit=self.produit,
            emplacement=self.annexe, quantite=12)

        vehicule = Vehicule.objects.create(
            company=self.company, immatriculation='1234-B-56')
        self.actif = ActifFlotte.objects.create(
            company=self.company, vehicule=vehicule)


class Ntdst14ChargementTests(Ntdst14Base):
    def test_charger_10_decremente_le_depot_et_rien_dautre(self):
        charger_vehicule(
            company=self.company, user=self.admin,
            actif_flotte_id=self.actif.id,
            lignes=[{'produit': self.produit.id, 'quantite': 10}])

        self.produit.refresh_from_db()
        self.se_annexe.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 40)
        self.assertEqual(self.se_annexe.quantite, 12)

        embarque = StockVehicule.objects.get(
            company=self.company, actif_flotte=self.actif,
            produit=self.produit)
        self.assertEqual(embarque.quantite_embarquee, 10)

        mouvement = MouvementStock.objects.get(company=self.company)
        self.assertEqual(mouvement.type_mouvement,
                         MouvementStock.TypeMouvement.SORTIE)
        self.assertIn('véhicule', mouvement.note.lower())

    def test_deux_chargements_sempilent_sur_la_meme_ligne(self):
        for _ in range(2):
            charger_vehicule(
                company=self.company, user=self.admin,
                actif_flotte_id=self.actif.id,
                lignes=[{'produit': self.produit.id, 'quantite': 5}])
        self.assertEqual(StockVehicule.objects.filter(
            company=self.company, actif_flotte=self.actif).count(), 1)
        self.assertEqual(StockVehicule.objects.get(
            company=self.company).quantite_embarquee, 10)

    def test_decharger_rend_le_reliquat_au_depot(self):
        charger_vehicule(
            company=self.company, user=self.admin,
            actif_flotte_id=self.actif.id,
            lignes=[{'produit': self.produit.id, 'quantite': 10}])
        decharger_vehicule(
            company=self.company, user=self.admin,
            actif_flotte_id=self.actif.id,
            lignes=[{'produit': self.produit.id, 'quantite': 4}])

        self.produit.refresh_from_db()
        self.se_annexe.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 44)
        # Regression guard : le déchargement ne touche AUCUN autre emplacement.
        self.assertEqual(self.se_annexe.quantite, 12)
        self.assertEqual(StockVehicule.objects.get(
            company=self.company).quantite_embarquee, 6)

    def test_decharger_plus_que_lembarque_est_refuse(self):
        charger_vehicule(
            company=self.company, user=self.admin,
            actif_flotte_id=self.actif.id,
            lignes=[{'produit': self.produit.id, 'quantite': 3}])
        with self.assertRaises(ValueError):
            decharger_vehicule(
                company=self.company, user=self.admin,
                actif_flotte_id=self.actif.id,
                lignes=[{'produit': self.produit.id, 'quantite': 4}])

    def test_decharger_un_vehicule_vide_est_refuse(self):
        with self.assertRaises(ValueError):
            decharger_vehicule(
                company=self.company, user=self.admin,
                actif_flotte_id=self.actif.id,
                lignes=[{'produit': self.produit.id, 'quantite': 1}])

    def test_lignes_invalides_sont_refusees(self):
        for mauvaises in ([], [{'produit': self.produit.id, 'quantite': 0}],
                          [{'quantite': 3}]):
            with self.assertRaises(ValueError):
                charger_vehicule(
                    company=self.company, user=self.admin,
                    actif_flotte_id=self.actif.id, lignes=mauvaises)

    def test_le_produit_dune_autre_societe_est_introuvable(self):
        autre_produit = Produit.objects.create(
            company=self.autre, nom='Voisin', sku='VOISIN-DST14',
            prix_achat=Decimal('1'), prix_vente=Decimal('2'),
            quantite_stock=99)
        with self.assertRaises(ValueError):
            charger_vehicule(
                company=self.company, user=self.admin,
                actif_flotte_id=self.actif.id,
                lignes=[{'produit': autre_produit.id, 'quantite': 1}])

    def test_le_stock_embarque_ne_liste_que_le_non_nul(self):
        charger_vehicule(
            company=self.company, user=self.admin,
            actif_flotte_id=self.actif.id,
            lignes=[{'produit': self.produit.id, 'quantite': 2}])
        decharger_vehicule(
            company=self.company, user=self.admin,
            actif_flotte_id=self.actif.id,
            lignes=[{'produit': self.produit.id, 'quantite': 2}])
        self.assertEqual(stock_embarque(self.company, self.actif.id), [])


class Ntdst14ApiTests(Ntdst14Base):
    def _url(self):
        return (f'/api/django/stock/vehicules/{self.actif.id}/'
                'stock-embarque/')

    def test_charger_puis_lire_par_api(self):
        api = auth(self.admin)
        res = api.post(self._url(), {
            'operation': 'charger',
            'lignes': [{'produit': self.produit.id, 'quantite': 6}],
        }, format='json')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['lignes'][0]['quantite_embarquee'], 6)

        lecture = api.get(self._url())
        self.assertEqual(lecture.data['lignes'][0]['quantite_embarquee'], 6)

    def test_operation_inconnue_renvoie_400(self):
        res = auth(self.admin).post(self._url(), {
            'operation': 'teleporter',
            'lignes': [{'produit': self.produit.id, 'quantite': 1}],
        }, format='json')
        self.assertEqual(res.status_code, 400)

    def test_module_desactive_renvoie_403_meme_pour_un_admin(self):
        ParametresNegoce.objects.create(
            company=self.company, van_sales_active=False)
        res = auth(self.admin).get(self._url())
        self.assertEqual(res.status_code, 403)
        self.assertIn('désactivé', res.data['detail'])

    def test_endpoint_refuse_un_role_normal(self):
        self.assertEqual(auth(self.normal).get(self._url()).status_code, 403)

    def test_endpoint_refuse_lanonyme(self):
        self.assertEqual(APIClient().get(self._url()).status_code, 401)

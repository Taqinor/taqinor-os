"""NTDST30 / NTDST31 — paramètres négoce et activation modulaire.

Critères d'acceptation testés :
  * NTDST30 — changer ``seuil_alerte_rfa_pct`` à 90 déplace le seuil de
    première alerte RFA SANS redéploiement (la valeur lue est la nouvelle) ;
  * NTDST31 — ``van_sales_active=False`` renvoie **403** sur les endpoints
    ``stock-vehicule``, MÊME POUR UN ADMIN (pas seulement un menu caché).

Run :
    python manage.py test apps.stock.test_ntdst30_parametres_negoce -v 2
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import ParametresNegoce, Produit
from apps.stock.services_consignation import consignation_activee
from apps.stock.services_van_sales import van_sales_active

User = get_user_model()

URL = '/api/django/stock/parametres-negoce/'
JOUR = datetime.date(2026, 3, 1)


def make_company(slug, nom):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Ntdst30Base(TestCase):
    def setUp(self):
        self.company = make_company('ntdst30-co', 'NTDST30 Co')
        self.autre = make_company('ntdst30-autre', 'NTDST30 Autre')
        self.admin = User.objects.create_user(
            username='ntdst30_admin', password='x', role_legacy='admin',
            company=self.company)
        self.normal = User.objects.create_user(
            username='ntdst30_normal', password='x', role_legacy='normal',
            company=self.company)


class Ntdst30ParametresTests(Ntdst30Base):
    def test_le_singleton_est_cree_a_la_demande_avec_ses_defauts(self):
        self.assertFalse(ParametresNegoce.objects.filter(
            company=self.company).exists())

        params = ParametresNegoce.get(self.company)

        self.assertTrue(params.consignation_activee)
        self.assertTrue(params.van_sales_active)
        self.assertEqual(params.seuil_alerte_rfa_pct, 80)
        self.assertEqual(params.heures_tournee_defaut, 7)
        self.assertEqual(params.atp_horizon_jours, 30)

    def test_get_est_idempotent_et_ne_cree_jamais_deux_lignes(self):
        ParametresNegoce.get(self.company)
        ParametresNegoce.get(self.company)
        self.assertEqual(ParametresNegoce.objects.filter(
            company=self.company).count(), 1)

    def test_changer_le_seuil_rfa_a_90_deplace_le_seuil_sans_redeploiement(
            self):
        res = auth(self.admin).patch(
            URL, {'seuil_alerte_rfa_pct': 90}, format='json')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['seuil_alerte_rfa_pct'], 90)
        self.assertEqual(
            ParametresNegoce.get(self.company).seuil_alerte_rfa_pct, 90)

    def test_un_seuil_superieur_a_100_est_refuse(self):
        res = auth(self.admin).patch(
            URL, {'seuil_alerte_rfa_pct': 150}, format='json')
        self.assertEqual(res.status_code, 400)

    def test_la_societe_nest_jamais_lue_du_corps(self):
        auth(self.admin).patch(
            URL, {'atp_horizon_jours': 45, 'company': self.autre.id},
            format='json')
        self.assertEqual(
            ParametresNegoce.get(self.company).atp_horizon_jours, 45)
        self.assertFalse(ParametresNegoce.objects.filter(
            company=self.autre).exists())

    def test_endpoint_refuse_un_role_normal_et_lanonyme(self):
        self.assertEqual(auth(self.normal).get(URL).status_code, 403)
        self.assertEqual(APIClient().get(URL).status_code, 401)

    def test_chaque_societe_a_son_propre_singleton(self):
        autre_admin = User.objects.create_user(
            username='ntdst30_autre_admin', password='x',
            role_legacy='admin', company=self.autre)
        auth(self.admin).patch(URL, {'atp_horizon_jours': 45}, format='json')
        res_autre = auth(autre_admin).get(URL)
        self.assertEqual(res_autre.data['atp_horizon_jours'], 30)


class Ntdst31ActivationModulaireTests(Ntdst30Base):
    def setUp(self):
        super().setUp()
        from apps.crm.models import Client
        from apps.flotte.models import ActifFlotte, Vehicule

        self.client_crm = Client.objects.create(
            company=self.company, nom='Client NTDST31')
        self.produit = Produit.objects.create(
            company=self.company, nom='Produit NTDST31', sku='P-NTDST31',
            prix_achat=Decimal('100'), prix_vente=Decimal('150'),
            quantite_stock=50)
        vehicule = Vehicule.objects.create(
            company=self.company, immatriculation='9999-Z-99')
        self.actif = ActifFlotte.objects.create(
            company=self.company, vehicule=vehicule)

    def _url_vehicule(self):
        return (f'/api/django/stock/vehicules/{self.actif.id}/'
                'stock-embarque/')

    def test_sans_parametrage_les_deux_modules_sont_actifs(self):
        self.assertTrue(consignation_activee(self.company))
        self.assertTrue(van_sales_active(self.company))

    def test_van_sales_desactive_renvoie_403_meme_a_un_admin(self):
        ParametresNegoce.objects.create(
            company=self.company, van_sales_active=False)

        lecture = auth(self.admin).get(self._url_vehicule())
        self.assertEqual(lecture.status_code, 403)

        ecriture = auth(self.admin).post(self._url_vehicule(), {
            'operation': 'charger',
            'lignes': [{'produit': self.produit.id, 'quantite': 1}],
        }, format='json')
        self.assertEqual(ecriture.status_code, 403)

    def test_consignation_desactivee_renvoie_403_meme_a_un_admin(self):
        ParametresNegoce.objects.create(
            company=self.company, consignation_activee=False)

        api = auth(self.admin)
        self.assertEqual(
            api.get('/api/django/stock/consignations/').status_code, 403)
        creation = api.post('/api/django/stock/consignations/', {
            'client': self.client_crm.id, 'produit': self.produit.id,
            'quantite_deposee': 1, 'date_depot': JOUR.isoformat(),
        }, format='json')
        self.assertEqual(creation.status_code, 403)

    def test_reactiver_le_module_le_rend_de_nouveau_accessible(self):
        params = ParametresNegoce.objects.create(
            company=self.company, van_sales_active=False)
        self.assertEqual(
            auth(self.admin).get(self._url_vehicule()).status_code, 403)

        params.van_sales_active = True
        params.save(update_fields=['van_sales_active'])
        self.assertEqual(
            auth(self.admin).get(self._url_vehicule()).status_code, 200)

    def test_desactiver_chez_une_societe_nempeche_pas_lautre(self):
        ParametresNegoce.objects.create(
            company=self.autre, van_sales_active=False)
        self.assertTrue(van_sales_active(self.company))
        self.assertFalse(van_sales_active(self.autre))

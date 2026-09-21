"""NTCPQ41 — Import CSV en masse de ``PrixContractuel`` (auto-suffisant,
jamais un passage par ``apps/dataimport``, hors périmètre de cette app)."""
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.cpq import services
from apps.cpq.models import PrixContractuel
from authentication.models import CustomUser
from testkit.factories import CompanyFactory, ClientFactory, ProduitFactory, UserFactory

IMPORT_URL = '/api/django/cpq/prix-contractuels/import-csv/'


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class TestImportPrixContractuelsCsv(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.staff = UserFactory(
            company=self.company, role_legacy=CustomUser.ROLE_RESPONSABLE)
        self.normal = UserFactory(
            company=self.company, role_legacy=CustomUser.ROLE_NORMAL)
        self.client_a = ClientFactory(
            company=self.company, nom='Client A', email='a@ex.com')
        self.produit_x = ProduitFactory(company=self.company, sku='SKU-X')

    def test_import_valide_via_service(self):
        csv_text = (
            'client_ref,produit_ref,prix_ht,date_debut,date_fin,motif\n'
            f'{self.client_a.email},{self.produit_x.sku},950.00,,,'
            'Prix négocié\n')
        resultat = services.importer_prix_contractuels_csv(
            self.company, csv_text, user=self.staff)
        self.assertEqual(resultat['importees'], 1)
        self.assertEqual(resultat['erreurs'], [])
        prix = PrixContractuel.objects.get(
            client=self.client_a, produit=self.produit_x)
        self.assertEqual(str(prix.prix_ht), '950.00')

    def test_lignes_invalides_rapportees_sans_bloquer_les_valides(self):
        csv_text = (
            'client_ref,produit_ref,prix_ht,date_debut,date_fin,motif\n'
            f'{self.client_a.email},{self.produit_x.sku},950.00,,,\n'
            'inconnu@ex.com,SKU-X,900.00,,,\n'
            f'{self.client_a.email},INCONNU-SKU,900.00,,,\n'
            f'{self.client_a.email},{self.produit_x.sku},pas-un-prix,,,\n')
        resultat = services.importer_prix_contractuels_csv(
            self.company, csv_text, user=self.staff)
        self.assertEqual(resultat['total'], 4)
        self.assertEqual(resultat['importees'], 1)
        self.assertEqual(len(resultat['erreurs']), 3)
        # Les numéros de ligne comptent depuis 2 (1 = en-tête).
        lignes = {e['ligne'] for e in resultat['erreurs']}
        self.assertEqual(lignes, {3, 4, 5})

    def test_dates_incoherentes_rejetees(self):
        csv_text = (
            'client_ref,produit_ref,prix_ht,date_debut,date_fin,motif\n'
            f'{self.client_a.email},{self.produit_x.sku},950.00,'
            '2026-06-01,2026-01-01,\n')
        resultat = services.importer_prix_contractuels_csv(
            self.company, csv_text, user=self.staff)
        self.assertEqual(resultat['importees'], 0)
        self.assertEqual(len(resultat['erreurs']), 1)

    def test_client_ref_par_id_fonctionne(self):
        csv_text = (
            'client_ref,produit_ref,prix_ht,date_debut,date_fin,motif\n'
            f'{self.client_a.id},{self.produit_x.id},800.00,,,\n')
        resultat = services.importer_prix_contractuels_csv(
            self.company, csv_text, user=self.staff)
        self.assertEqual(resultat['importees'], 1)

    def test_endpoint_reserve_au_staff(self):
        csv_text = 'client_ref,produit_ref,prix_ht,date_debut,date_fin,motif\n'
        fichier = SimpleUploadedFile(
            'prix.csv', csv_text.encode(), content_type='text/csv')
        resp = auth(self.normal).post(IMPORT_URL, {'file': fichier})
        self.assertEqual(resp.status_code, 403)

    def test_endpoint_accepte_un_upload_multipart(self):
        csv_text = (
            'client_ref,produit_ref,prix_ht,date_debut,date_fin,motif\n'
            f'{self.client_a.email},{self.produit_x.sku},700.00,,,\n')
        fichier = SimpleUploadedFile(
            'prix.csv', csv_text.encode(), content_type='text/csv')
        resp = auth(self.staff).post(IMPORT_URL, {'file': fichier})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['importees'], 1)

    def test_isolation_multi_tenant(self):
        autre_company = CompanyFactory()
        autre_client = ClientFactory(company=autre_company, email='b@ex.com')
        autre_produit = ProduitFactory(company=autre_company, sku='SKU-Y')
        csv_text = (
            'client_ref,produit_ref,prix_ht,date_debut,date_fin,motif\n'
            f'{autre_client.email},{autre_produit.sku},500.00,,,\n')
        resultat = services.importer_prix_contractuels_csv(
            self.company, csv_text, user=self.staff)
        self.assertEqual(resultat['importees'], 0)
        self.assertEqual(len(resultat['erreurs']), 1)

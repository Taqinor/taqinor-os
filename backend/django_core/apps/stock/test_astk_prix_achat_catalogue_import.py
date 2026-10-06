"""ASTK12 (D-ASTK-2) — `prix_achat_dernier` du catalogue d'achat et l'import de
tarifs fournisseur (aperçu ET écriture) servis UNIQUEMENT avec
`prix_achat_voir`.

Rejoue PRIX-2 / TEN-8(a,c) : catalogue-achat 200 avec
prix_achat_dernier=900.00 pour un Commercial ; aperçu d'import 200 avec
conflits[].ecrasements (prix actuel exposé) pour un Technicien responsable.

Source réelle : `can_view_buy_prices`, `apps.dataimport.services` réel (aucun
mock).

Run :
    python manage.py test apps.stock.test_astk_prix_achat_catalogue_import -v 2
"""
import io
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from openpyxl import Workbook
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.roles.models import Role
from apps.roles.permissions_registre import CANONICAL_SYSTEM_ROLES
from apps.stock.models import Fournisseur, PrixFournisseur, Produit
from authentication.models import Company

User = get_user_model()

CATALOGUE = '/api/django/stock/catalogue-achat/'
IMPORT = '/api/django/stock/prix-fournisseurs/import-xlsx/'


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def _rows(data):
    return data['results'] if isinstance(data, dict) and 'results' in data \
        else data


class PrixAchatCatalogueImportTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='ASTK12', slug='astk12-co')
        perms = dict(CANONICAL_SYSTEM_ROLES)

        def _role_user(nom):
            role = Role.objects.create(
                company=self.company, nom=nom, permissions=perms[nom])
            return User.objects.create_user(
                username=f'astk12-{nom.lower().replace(" ", "-")}',
                password='x', company=self.company, role=role)

        self.commercial = _role_user('Commercial')
        self.tech_resp = _role_user('Technicien responsable')
        self.admin = _role_user('Administrateur')
        self.assertFalse(self.commercial.can_view_buy_prices)
        self.assertFalse(self.tech_resp.can_view_buy_prices)
        self.assertTrue(self.admin.can_view_buy_prices)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur ASTK12')
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau ASTK12', sku='ASTK12-1',
            prix_vente=Decimal('1400'), prix_achat=Decimal('900'))
        self.prix = PrixFournisseur.objects.create(
            company=self.company, produit=self.produit,
            fournisseur=self.fournisseur, prix_achat=Decimal('820.00'))

    def _fichier(self, prix=700):
        wb = Workbook()
        ws = wb.active
        ws.append(['sku', 'produit', 'ref_produit_fournisseur',
                   'prix_achat', 'date_debut', 'date_fin', 'paliers'])
        ws.append([self.produit.sku, self.produit.nom, '', prix, None, None,
                   ''])
        buf = io.BytesIO()
        wb.save(buf)
        return SimpleUploadedFile(
            'tarif.xlsx', buf.getvalue(),
            content_type=('application/vnd.openxmlformats-officedocument'
                          '.spreadsheetml.sheet'))

    def _import(self, user, **extra):
        body = {'fournisseur': self.fournisseur.pk, 'file': self._fichier()}
        body.update(extra)
        return _api(user).post(IMPORT, body, format='multipart')

    def test_catalogue_sans_prix(self):
        rep = _api(self.commercial).get(CATALOGUE)
        self.assertEqual(rep.status_code, 200)
        rows = _rows(rep.data)
        self.assertEqual(len(rows), 1)
        self.assertNotIn('prix_achat_dernier', rows[0])
        self.assertEqual(rows[0]['sku'], 'ASTK12-1')  # sélecteur utilisable

    def test_import_403(self):
        rep = self._import(self.tech_resp, apercu='true')
        self.assertEqual(rep.status_code, 403)
        self.assertNotIn(b'820', rep.content)
        rep = self._import(self.tech_resp, ecraser='true')
        self.assertEqual(rep.status_code, 403)
        self.prix.refresh_from_db()
        self.assertEqual(self.prix.prix_achat, Decimal('820.00'))

    def test_administrateur_inchange(self):
        rep = _api(self.admin).get(CATALOGUE)
        self.assertEqual(rep.status_code, 200)
        self.assertIn('prix_achat_dernier', _rows(rep.data)[0])
        rep = self._import(self.admin, apercu='true')
        self.assertEqual(rep.status_code, 200, rep.data)
        self.assertTrue(rep.data['apercu'])
        self.prix.refresh_from_db()
        self.assertEqual(self.prix.prix_achat, Decimal('820.00'))

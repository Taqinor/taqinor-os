"""AUD517 — import de parc : garanties, jeton QR et dédoublonnage RÉEL.

Constat d'audit (le ROUGE figé ici) : le bloc ``equipements`` de
``dataimport.services`` faisait ``Equipement.objects.create(...)`` en important
``apps.sav.models`` directement. Trois défauts, chacun reproduit ci-dessous :

  * ``recompute_garanties()`` n'était jamais appelé → ``date_fin_garantie``
    restait NULL et tout le parc importé était classé hors garantie ;
  * ``equipement_token`` (QR FG85) n'était jamais posé → le parc importé était
    invisible au scan QR du SAV ;
  * la garde de doublon portait sur ``(company, produit, installation,
    numero_serie)`` alors que la contrainte DB réelle est
    ``(company, numero_serie)`` : deux lignes de même série sur des
    produits/chantiers différents passaient la garde, puis l'``IntegrityError``
    non capturé pouvait annuler TOUT le lot.

Run :
    python manage.py test apps.dataimport.test_aud517_parc_import -v2
"""
from datetime import date

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from django.contrib.auth import get_user_model

from apps.crm.models import Client
from apps.installations.models import Installation
from apps.sav.models import Equipement
from apps.stock.models import Produit
from authentication.models import Company

User = get_user_model()

COMMIT = '/api/django/imports/commit/'


class AUD517ImportParcTests(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='imp-aud517', defaults={'nom': 'Imp AUD517'})[0]
        self.user = User.objects.create_user(
            username='imp_aud517', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client AUD517')
        self.installation = Installation.objects.create(
            company=self.company, reference='CHANT-AUD517',
            client=self.client_obj)
        self.installation_b = Installation.objects.create(
            company=self.company, reference='CHANT-AUD517-B',
            client=self.client_obj)
        # 24 mois de garantie constructeur : la date de fin est CALCULABLE.
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur AUD517', sku='SKU-AUD517',
            prix_vente=0, garantie_mois=24)
        self.produit_b = Produit.objects.create(
            company=self.company, nom='Panneau AUD517', sku='SKU-AUD517-B',
            prix_vente=0, garantie_mois=12)

    def _csv(self, content, name='data.csv'):
        return SimpleUploadedFile(
            name, content.encode('utf-8'), content_type='text/csv')

    def _commit(self, content):
        return self.api.post(
            COMMIT, {'file': self._csv(content), 'target': 'equipements'},
            format='multipart')

    # ── ROUGE #1 et #2 — garanties NULL, QR absent ──────────────────────────

    def test_import_calcule_les_garanties_et_pose_le_qr(self):
        resp = self._commit(
            'SKU,Chantier,Serie,date_pose\n'
            'SKU-AUD517,CHANT-AUD517,SN-AUD517-1,2026-01-15\n')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['created'], 1, resp.data)
        equipement = Equipement.objects.get(
            company=self.company, numero_serie='SN-AUD517-1')
        # Garantie recalculée (2026-01-15 + 24 mois).
        self.assertEqual(equipement.date_fin_garantie, date(2028, 1, 15))
        # Jeton QR FG85 posé — le parc importé est scannable.
        self.assertEqual(
            equipement.equipement_token, f'EQUIP:{equipement.pk}')

    # ── ROUGE #3 — le doublon de série cassait tout le lot ──────────────────

    def test_meme_serie_produits_differents_ne_casse_pas_le_lot(self):
        """La contrainte DB est (company, numero_serie) : la 2e ligne est un
        doublon PROPRE et la 3e ligne du lot passe quand même."""
        resp = self._commit(
            'SKU,Chantier,Serie\n'
            'SKU-AUD517,CHANT-AUD517,SN-DUP\n'
            'SKU-AUD517-B,CHANT-AUD517-B,SN-DUP\n'
            'SKU-AUD517,CHANT-AUD517,SN-AUD517-OK\n')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['created'], 2, resp.data)
        raisons = [s['raison'] for s in resp.data['skipped']]
        self.assertTrue(any('doublon' in r for r in raisons), raisons)
        self.assertEqual(
            Equipement.objects.filter(
                company=self.company, numero_serie='SN-DUP').count(), 1)
        self.assertTrue(Equipement.objects.filter(
            company=self.company, numero_serie='SN-AUD517-OK').exists())

    def test_serie_deja_au_parc_est_un_doublon(self):
        Equipement.objects.create(
            company=self.company, produit=self.produit,
            installation=self.installation, numero_serie='SN-EXISTANT')
        resp = self._commit(
            'SKU,Chantier,Serie\n'
            'SKU-AUD517-B,CHANT-AUD517-B,SN-EXISTANT\n')
        self.assertEqual(resp.data['created'], 0, resp.data)
        self.assertEqual(
            Equipement.objects.filter(
                company=self.company, numero_serie='SN-EXISTANT').count(), 1)

    # ── Non-régressions FG14 ────────────────────────────────────────────────

    def test_sans_serie_toujours_importe(self):
        resp = self._commit(
            'SKU,Chantier\n'
            'SKU-AUD517,CHANT-AUD517\n'
            'SKU-AUD517,CHANT-AUD517\n')
        self.assertEqual(resp.data['created'], 2, resp.data)

    def test_sku_inconnu_toujours_saute(self):
        resp = self._commit('SKU,Chantier\nSKU-BOGUS,CHANT-AUD517\n')
        self.assertEqual(resp.data['created'], 0)
        self.assertIn('produit SKU inconnu', resp.data['skipped'][0]['raison'])

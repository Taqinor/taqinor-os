"""PV15 — garde de statut sur ``replace-lines`` + produits du catalogue GLOBAL.

Deux trous fermés sur POST /ventes/devis/<id>/replace-lines/ :

  * il n'avait AUCUNE garde de statut — un appel sur un devis ACCEPTÉ effaçait
    les lignes d'un document déjà engagé (chaîne BonCommande/Facture) ;
  * il ne résolvait les produits que sur ``company=<société>``, donc il
    REFUSAIT les produits du catalogue GLOBAL (``company IS NULL``) que
    ``services._pick_product`` venait pourtant de poser sur le même devis.

Aucun statut n'est écrit par ce chemin (règle #4) : la garde LIT le statut.

Run:
    DJANGO_SETTINGS_MODULE=erp_agentique.settings._local_sqlite_test \
        python manage.py test apps.ventes.tests.test_pv15_replace_lines_garde -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis

User = get_user_model()


def make_company(slug):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': slug})
    return company


def auth_client(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class TestReplaceLinesGardeStatut(TestCase):
    def setUp(self):
        self.company = make_company('pv15-co')
        self.user = User.objects.create_user(
            username='pv15user', password='x', role_legacy='responsable',
            company=self.company)
        self.api = auth_client(self.user)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client PV15', email='pv15@example.com')
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau Jinko 550W', sku='PV15-PAN',
            prix_vente=Decimal('1100'), prix_achat=Decimal('700'),
            quantite_stock=50)
        # Produit GLOBAL (sans société) — celui du catalogue partagé.
        self.produit_global = Produit.objects.create(
            company=None, nom='Onduleur réseau Huawei 5kW Monophasé',
            sku='PV15-ONDR-GLOBAL', prix_vente=Decimal('14000'),
            prix_achat=Decimal('9000'), quantite_stock=50)

    def _devis(self, statut):
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-PV15-{statut}',
            client=self.client_obj, statut=statut, created_by=self.user)
        devis.lignes.create(
            produit=self.produit, designation='Ligne initiale',
            quantite=Decimal('4'), prix_unitaire=Decimal('1100'))
        return devis

    def _url(self, devis):
        return f'/api/django/ventes/devis/{devis.id}/replace-lines/'

    def _corps(self, produit, qte=2):
        return {'lignes': [{
            'produit': produit.id, 'designation': produit.nom,
            'quantite': qte, 'prix_unitaire': str(produit.prix_vente),
        }]}

    # ── La garde ────────────────────────────────────────────────────────────
    def test_devis_accepte_409_et_lignes_intactes(self):
        devis = self._devis(Devis.Statut.ACCEPTE)
        resp = self.api.post(
            self._url(devis), self._corps(self.produit), format='json')
        self.assertEqual(resp.status_code, 409)
        self.assertIn('Accepté', resp.data['detail'])
        # Rien n'a été supprimé : le devis engagé garde ses lignes.
        self.assertEqual(devis.lignes.count(), 1)
        self.assertEqual(
            devis.lignes.first().designation, 'Ligne initiale')
        # Le statut n'a pas bougé (règle #4).
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.ACCEPTE)

    def test_devis_refuse_et_expire_409(self):
        for statut in (Devis.Statut.REFUSE, Devis.Statut.EXPIRE):
            with self.subTest(statut=statut):
                devis = self._devis(statut)
                resp = self.api.post(
                    self._url(devis), self._corps(self.produit),
                    format='json')
                self.assertEqual(resp.status_code, 409)
                self.assertEqual(devis.lignes.count(), 1)

    def test_devis_brouillon_remplace_bien(self):
        devis = self._devis(Devis.Statut.BROUILLON)
        resp = self.api.post(
            self._url(devis), self._corps(self.produit, qte=7), format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(devis.lignes.count(), 1)
        ligne = devis.lignes.first()
        self.assertEqual(int(ligne.quantite), 7)
        self.assertEqual(ligne.designation, 'Panneau Jinko 550W')
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.BROUILLON)

    def test_devis_envoye_reste_modifiable(self):
        devis = self._devis(Devis.Statut.ENVOYE)
        resp = self.api.post(
            self._url(devis), self._corps(self.produit, qte=3), format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(int(devis.lignes.first().quantite), 3)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.ENVOYE)

    # ── Le catalogue global ─────────────────────────────────────────────────
    def test_produit_global_accepte(self):
        devis = self._devis(Devis.Statut.BROUILLON)
        resp = self.api.post(
            self._url(devis), self._corps(self.produit_global), format='json')
        self.assertEqual(resp.status_code, 200)
        ligne = devis.lignes.first()
        self.assertEqual(ligne.produit_id, self.produit_global.id)

    def test_produit_d_une_autre_societe_reste_refuse(self):
        autre = make_company('pv15-autre-co')
        etranger = Produit.objects.create(
            company=autre, nom='Panneau étranger 600W', sku='PV15-ETR',
            prix_vente=Decimal('1200'), prix_achat=Decimal('800'),
            quantite_stock=10)
        devis = self._devis(Devis.Statut.BROUILLON)
        resp = self.api.post(
            self._url(devis), self._corps(etranger), format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('inconnu', resp.data['detail'])
        # Rollback complet : les lignes d'origine sont préservées.
        self.assertEqual(devis.lignes.count(), 1)
        self.assertEqual(devis.lignes.first().designation, 'Ligne initiale')

    def test_aucun_prix_achat_dans_la_reponse(self):
        devis = self._devis(Devis.Statut.BROUILLON)
        resp = self.api.post(
            self._url(devis), self._corps(self.produit), format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('prix_achat', str(resp.data))

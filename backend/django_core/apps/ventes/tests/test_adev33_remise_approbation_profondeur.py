"""ADEV33 (C-ADEV-048) — la PROFONDEUR de remise approuvée est mémorisée
(``remise_approuvee_pct``) : une remise envoyée qui la dépasse exige une
nouvelle approbation ; la garde T17 s'applique aussi aux écritures
``/devis-lignes/`` d'un devis envoyé.

Rejoue VB q10 (seuil société 10 %). Source réelle : ``domain/tarification``.

Test-du-test : comparer au booléen ``remise_approuvee`` seul ⇒
``test_approbation_non_collante`` échoue.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.crm.models import Client
from apps.parametres.models import CompanyProfile
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis
from authentication.models import Company

User = get_user_model()


class RemiseApprobationProfondeurTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='ADEV33', slug='adev33-co')
        CompanyProfile.objects.update_or_create(
            company=self.company,
            defaults={'discount_approval_threshold': Decimal('10')})
        self.resp = User.objects.create_user(
            username='adev33_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.admin = User.objects.create_user(
            username='adev33_admin', password='x', role_legacy='admin',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client ADEV33',
            email='adev33@example.com')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur', sku='ADEV33-OND',
            prix_vente=Decimal('10000'), quantite_stock=5)

    @staticmethod
    def _api(user):
        api = APIClient()
        api.force_authenticate(user)
        return api

    def _devis(self, remise, statut='brouillon'):
        devis = Devis.objects.create(
            company=self.company, reference='DEV-ADEV33-%s' % remise,
            client=self.client_obj, statut=statut, taux_tva=Decimal('20'),
            remise_globale=Decimal(remise), created_by=self.resp)
        LigneDevis.objects.create(
            devis=devis, produit=self.produit, designation='Onduleur',
            quantite=1, prix_unitaire=Decimal('10000'), remise=Decimal('0'))
        return devis

    def _approuver(self, devis):
        r = self._api(self.admin).post(
            '/api/django/ventes/devis/%s/approuver-remise/' % devis.pk)
        self.assertEqual(r.status_code, 200, r.content)
        devis.refresh_from_db()
        return devis

    def test_approbation_non_collante(self):
        devis = self._approuver(self._devis('15'))
        self.assertEqual(devis.remise_approuvee_pct, Decimal('15.00'))
        Devis.objects.filter(pk=devis.pk).update(remise_globale=Decimal('60'))
        r = self._api(self.resp).post(
            '/api/django/ventes/devis/%s/share-link/' % devis.pk,
            {'envoi': True}, format='json')
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn('15', str(r.content.decode()))
        devis.refresh_from_db()
        self.assertEqual(devis.statut, 'brouillon')
        self.assertEqual(devis.remise_globale, Decimal('60'))

    def test_devis_lignes_garde_t17(self):
        devis = self._approuver(self._devis('15', statut='envoye'))
        ligne = devis.lignes.get()
        r = self._api(self.resp).patch(
            '/api/django/ventes/devis-lignes/%s/' % ligne.pk,
            {'remise': '60'}, format='json')
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn('remise', r.json())
        ligne.refresh_from_db()
        self.assertEqual(ligne.remise, Decimal('0'))
        devis.refresh_from_db()
        self.assertEqual(devis.statut, 'envoye')

    def test_sous_profondeur_ok(self):
        devis = self._devis('15', statut='envoye')
        Devis.objects.filter(pk=devis.pk).update(
            remise_approuvee=True, remise_approuvee_par=self.admin,
            remise_approuvee_pct=Decimal('30'))
        ligne = devis.lignes.get()
        # 1 − 0,90 × 0,85 = 23,5 % ≤ 30 % approuvés.
        r = self._api(self.resp).patch(
            '/api/django/ventes/devis-lignes/%s/' % ligne.pk,
            {'remise': '10'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        ligne.refresh_from_db()
        self.assertEqual(ligne.remise, Decimal('10'))

    def test_admin_inchange(self):
        devis = self._approuver(self._devis('15', statut='envoye'))
        ligne = devis.lignes.get()
        r = self._api(self.admin).patch(
            '/api/django/ventes/devis-lignes/%s/' % ligne.pk,
            {'remise': '60'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        devis.refresh_from_db()
        self.assertTrue(devis.remise_approuvee)
        self.assertGreater(devis.remise_approuvee_pct, Decimal('15'))

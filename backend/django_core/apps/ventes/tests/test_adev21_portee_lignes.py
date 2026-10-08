"""ADEV21 (C-ADEV-025) — la portée équipe (``core/scoping.scope_queryset``,
mêmes ``owner_fields`` que ``DevisViewSet``) s'applique à
``LigneDevisViewSet`` et aux aperçus ``etude-ci`` / ``etude-pompage``.

Un Commercial de portée ``team`` (rôle canonique réel, ``records_scope_equipe``,
sans superviseur commun avec l'auteur du brouillon) ne lit ni ne modifie
aucune ligne d'un devis hors de sa portée (404) ; ses propres lignes restent
lisibles et modifiables.

Test-du-test : retirer ``scope_queryset`` de ``LigneDevisViewSet.get_queryset``
⇒ ``test_patch_404_hors_portee`` échoue.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.crm.models import Client
from apps.roles.models import Role
from apps.roles.permissions_registre import RESPONSABLE_PERMISSIONS
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis
from authentication.models import Company

User = get_user_model()

URL_LIGNES = '/api/django/ventes/devis-lignes/'


class PorteeLignesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='ADEV21', slug='adev21-co')
        role_equipe = Role.objects.create(
            company=cls.company, nom='Commercial',
            permissions=RESPONSABLE_PERMISSIONS + ['records_scope_equipe'],
            est_systeme=False)
        cls.commercial = User.objects.create_user(
            username='adev21_com', password='x', role=role_equipe,
            role_legacy='responsable', company=cls.company)
        cls.auteur = User.objects.create_user(
            username='adev21_auteur', password='x',
            role_legacy='responsable', company=cls.company)
        client = Client.objects.create(
            company=cls.company, nom='Client ADEV21',
            email='adev21@example.com')
        cls.devis_autrui = Devis.objects.create(
            company=cls.company, reference='DV-ADEV21-A', client=client,
            created_by=cls.auteur)
        cls.ligne_autrui = LigneDevis.objects.create(
            devis=cls.devis_autrui, designation='Accessoires',
            quantite=1, prix_unitaire=Decimal('1272.73'))
        cls.devis_propre = Devis.objects.create(
            company=cls.company, reference='DV-ADEV21-P', client=client,
            created_by=cls.commercial)
        # Une ligne PRODUIT référence un produit (XSAL14,
        # ``LigneDevisSerializer.validate``) : sans lui, le PATCH de la ligne
        # propre répond 400 « Une ligne produit doit référencer un produit. »
        # avant même la portée testée ici.
        produit = Produit.objects.create(
            company=cls.company, nom='Câble solaire 6 mm²',
            sku='ADEV21-CAB', prix_vente=Decimal('100'))
        cls.ligne_propre = LigneDevis.objects.create(
            devis=cls.devis_propre, produit=produit, designation='Câblage',
            quantite=1, prix_unitaire=Decimal('100'))

    def setUp(self):
        self.api = APIClient()
        self.api.force_authenticate(self.commercial)

    @staticmethod
    def _ids(resp):
        corps = resp.data
        lignes = corps.get('results', corps) if isinstance(corps, dict) else corps
        return {ligne['id'] for ligne in lignes}

    def test_liste_vide_hors_portee(self):
        resp = self.api.get(URL_LIGNES)
        self.assertEqual(resp.status_code, 200)
        ids = self._ids(resp)
        self.assertNotIn(self.ligne_autrui.pk, ids)
        self.assertIn(self.ligne_propre.pk, ids)
        detail = self.api.get('%s%s/' % (URL_LIGNES, self.ligne_autrui.pk))
        self.assertEqual(detail.status_code, 404)

    def test_patch_404_hors_portee(self):
        resp = self.api.patch(
            '%s%s/' % (URL_LIGNES, self.ligne_autrui.pk),
            {'prix_unitaire': '1.00'}, format='json')
        self.assertEqual(resp.status_code, 404)
        # CLAUSE PERSISTANCE — relue en base : prix inchangé.
        self.ligne_autrui.refresh_from_db()
        self.assertEqual(self.ligne_autrui.prix_unitaire, Decimal('1272.73'))

    def test_apercus_404_hors_portee(self):
        for url in ('/api/django/ventes/etude-ci/preview/',
                    '/api/django/ventes/etude-pompage/preview/'):
            resp = self.api.post(url, {'devis': self.devis_autrui.pk},
                                 format='json')
            self.assertEqual(resp.status_code, 404, url)

    def test_propres_lignes_ok(self):
        url = '%s%s/' % (URL_LIGNES, self.ligne_propre.pk)
        self.assertEqual(self.api.get(url).status_code, 200)
        resp = self.api.patch(url, {'designation': 'Câblage DC'},
                              format='json')
        self.assertEqual(resp.status_code, 200)
        self.ligne_propre.refresh_from_db()
        self.assertEqual(self.ligne_propre.designation, 'Câblage DC')

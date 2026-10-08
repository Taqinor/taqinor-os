"""ASTK198 (C-ASTK-047) — chaque déclaration de consommation d'un dépôt de
consignation est FACTURÉE : `declarer_consommation` appelle
`ventes.services.creer_facture_consignation` (ASTK197), passe la déclaration
`facturee` avec le n° de facture, et le relevé (JSON + PDF) l'imprime.

Sonde WMS-3 rejouée (rouge avant ASTK198) : stock 10 → 6, déclaration
{statut 'declaree', document_reference ''}, factures de la société = 0.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.stock.test_astk_consignation_facturee"
"""
import datetime
import json
from decimal import Decimal
from pathlib import Path
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

User = get_user_model()

URL = '/api/django/stock/consignations/'
JOUR = datetime.date(2026, 10, 1)
JOUR_CONSO = datetime.date(2026, 10, 10)
CONTRAT = (Path(__file__).resolve().parent / 'contract_samples'
           / 'negoce_consignation_rfa.json')


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class ConsignationTests(TestCase):
    def setUp(self):
        from apps.crm.models import Client
        from apps.stock.models import Produit
        from apps.stock.services_consignation import creer_depot_consignation
        from authentication.models import Company

        self.company = Company.objects.create(
            nom='Co ASTK198', slug='co-astk198')
        self.resp = User.objects.create_user(
            username='resp-astk198', password='x', company=self.company,
            role_legacy='responsable')
        self.client_crm = Client.objects.create(
            company=self.company, nom='Consigne', prenom='Client',
            email='astk198@example.invalid')
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau ASTK198', sku='SKU-ASTK198',
            prix_vente=Decimal('1500.00'), prix_achat=Decimal('900.00'),
            tva=Decimal('20.00'), quantite_stock=10)
        self.depot = creer_depot_consignation(
            company=self.company, user=self.resp,
            client_id=self.client_crm.id, produit_id=self.produit.id,
            quantite=4, date_depot=JOUR, adresse_site='Site ASTK198')

    def _factures(self):
        from apps.ventes.models import Facture
        return Facture.objects.filter(company=self.company)

    def _declarer(self, quantite=2):
        return auth(self.resp).post(
            f'{URL}{self.depot.id}/declarer-consommation/',
            {'quantite': quantite,
             'date_declaration': JOUR_CONSO.isoformat()}, format='json')

    def test_declaration_cree_une_facture_brouillon(self):
        from apps.stock.models import DeclarationConsommation
        from apps.ventes.models import Facture

        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 6)  # 10 − 4 déposés
        rep = self._declarer(2)
        self.assertEqual(rep.status_code, 201, rep.content)
        corps = rep.json()

        factures = list(self._factures())
        self.assertEqual(len(factures), 1)
        facture = Facture.objects.get(pk=factures[0].pk)
        self.assertEqual(facture.statut, Facture.Statut.BROUILLON)
        self.assertEqual(facture.client_id, self.client_crm.id)
        lignes = list(facture.lignes.all())
        self.assertEqual(len(lignes), 1)
        self.assertEqual(lignes[0].produit_id, self.produit.id)
        self.assertEqual(lignes[0].quantite, Decimal('2'))
        self.assertEqual(lignes[0].prix_unitaire, Decimal('1500.00'))

        declaration = DeclarationConsommation.objects.get(pk=corps['id'])
        self.assertEqual(declaration.statut,
                         DeclarationConsommation.Statut.FACTUREE)
        self.assertEqual(declaration.document_reference, facture.reference)
        self.assertEqual(corps['statut'], 'facturee')
        self.assertEqual(corps['facture_id'], facture.pk)
        self.assertEqual(corps['facture_reference'], facture.reference)
        self.assertEqual(corps['document_reference'], facture.reference)
        # Le stock n'est JAMAIS décrémenté une seconde fois.
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 6)

    def test_reponse_conforme_au_contrat(self):
        route = json.loads(CONTRAT.read_text(encoding='utf-8'))['routes'][
            'consignation_declarer_consommation']
        corps = self._declarer(2).json()
        self.assertEqual(sorted(corps),
                         sorted(route['exemple_nouveau_astk198']))

    def test_redeclaration_idempotente(self):
        from apps.stock.models import DeclarationConsommation
        from apps.stock.services_consignation import facturer_declaration

        corps = self._declarer(2).json()
        declaration = DeclarationConsommation.objects.get(pk=corps['id'])
        facture = facturer_declaration(declaration, user=self.resp)
        facture_bis = facturer_declaration(declaration, user=self.resp)
        self.assertEqual(facture.pk, corps['facture_id'])
        self.assertEqual(facture_bis.pk, corps['facture_id'])
        self.assertEqual(self._factures().count(), 1)
        declaration.refresh_from_db()
        self.assertEqual(declaration.document_reference, facture.reference)

    def test_releve_affiche_la_facture(self):
        from apps.stock.utils.pdf_consignation import (
            render_releve_consignation_html,
        )

        corps = self._declarer(2).json()
        rep = auth(self.resp).get(f'{URL}{self.depot.id}/releve/')
        self.assertEqual(rep.status_code, 200, rep.content)
        releve = rep.json()
        self.assertEqual(releve['quantite_facturee'], 2)
        self.assertEqual(releve['quantite_restante'], 2)
        self.assertEqual(releve['declarations'][0]['document_reference'],
                         corps['facture_reference'])
        self.depot.refresh_from_db()
        html = render_releve_consignation_html(self.depot)
        self.assertIn(corps['facture_reference'], html)
        self.assertIn('facturé 2', html)
        self.assertIn('Facturée', html)

    def test_aucun_prix_achat(self):
        self._declarer(2)
        facture = self._factures().get()
        prix = [ligne.prix_unitaire for ligne in facture.lignes.all()]
        self.assertEqual(prix, [Decimal('1500.00')])
        self.assertNotIn(Decimal('900.00'), prix)

    def test_echec_ventes_annule_la_declaration(self):
        from apps.stock.models import DeclarationConsommation

        with mock.patch('apps.ventes.services.creer_facture_consignation',
                        side_effect=ValueError('refus ventes')):
            rep = self._declarer(2)
        self.assertEqual(rep.status_code, 400, rep.content)
        self.assertEqual(
            DeclarationConsommation.objects.filter(depot=self.depot).count(),
            0)
        self.depot.refresh_from_db()
        self.assertEqual(self.depot.quantite_consommee_declaree, 0)
        self.assertEqual(self._factures().count(), 0)

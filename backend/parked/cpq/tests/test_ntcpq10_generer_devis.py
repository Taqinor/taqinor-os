"""NTCPQ10 — génération d'un devis brouillon depuis une session configurateur."""
from decimal import Decimal

from django.test import TestCase

from apps.cpq.models import (
    QuestionConfigurateur, RegleProduitCPQ, SessionConfigurateur,
    ReponseConfigurateur,
)
from apps.cpq import services
from apps.ventes.models import Devis
from testkit.factories import (
    CompanyFactory, UserFactory, ClientFactory, ProduitFactory,
)


class TestGenererDevisConfigurateur(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.user = UserFactory(company=self.company)
        self.client_obj = ClientFactory(company=self.company)
        self.produit = ProduitFactory(
            company=self.company, prix_vente=Decimal('1500.00'))
        self.q = QuestionConfigurateur.objects.create(
            company=self.company, ordre=1, texte='kWc',
            type=QuestionConfigurateur.TypeQuestion.NUMERIQUE,
            options={'champ': 'kwc'})
        RegleProduitCPQ.objects.create(
            company=self.company, nom='9kWc',
            condition_group={'field': 'kwc', 'operator': 'gte', 'value': 9},
            actions=[{'type': 'ajouter_produit',
                      'produit_id': self.produit.id, 'quantite': 2}])
        self.session = SessionConfigurateur.objects.create(company=self.company)
        ReponseConfigurateur.objects.create(
            session=self.session, question=self.q, valeur=12)

    def test_genere_devis_brouillon_avec_lignes(self):
        devis = services.generer_devis_depuis_configurateur(
            self.session, user=self.user, client=self.client_obj)
        self.assertEqual(devis.statut, Devis.Statut.BROUILLON)
        self.assertEqual(devis.lignes.count(), 1)
        ligne = devis.lignes.first()
        self.assertEqual(ligne.quantite, Decimal('2'))
        self.assertEqual(ligne.prix_unitaire, Decimal('1500.00'))
        # session liée au devis (jamais purgée par NTCPQ34)
        self.session.refresh_from_db()
        self.assertEqual(self.session.devis_id, devis.id)
        # aucun PDF généré
        self.assertFalse(devis.fichier_pdf)

    def test_endpoint_generer_devis(self):
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import AccessToken
        staff = UserFactory(company=self.company, role_legacy='responsable')
        client = APIClient()
        client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(staff)}')
        resp = client.post(
            f'/api/django/cpq/configurateur/{self.session.token}/generer-devis/',
            {'client': self.client_obj.id}, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertIn('devis_id', resp.json())

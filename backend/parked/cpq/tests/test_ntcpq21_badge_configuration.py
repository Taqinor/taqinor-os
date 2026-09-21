"""NTCPQ21 — Badge « configuration validée » (NTCPQ1 + NTCPQ2, non bloquant)."""
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient, APIRequestFactory
from rest_framework_simplejwt.tokens import AccessToken

from apps.cpq.models import ContrainteCompatibilite, RegleProduitCPQ
from apps.cpq.selectors import etat_configuration_devis
from apps.ventes.models import Devis, LigneDevis
from apps.ventes.serializers import DevisSerializer
from authentication.models import CustomUser
from testkit.factories import (
    CompanyFactory, DevisFactory, ProduitFactory, UserFactory,
)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class TestBadgeConfiguration(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.user = UserFactory(
            company=self.company, role_legacy=CustomUser.ROLE_RESPONSABLE)
        self.p1 = ProduitFactory(company=self.company, nom='Onduleur A')
        self.p2 = ProduitFactory(company=self.company, nom='Batterie B')
        self.devis = DevisFactory(company=self.company)
        for produit in (self.p1, self.p2):
            LigneDevis.objects.create(
                devis=self.devis, produit=produit, designation=produit.nom,
                quantite=Decimal('1'), prix_unitaire=Decimal('100.00'))

    def test_configuration_valide_par_defaut(self):
        etat = etat_configuration_devis(self.devis)
        self.assertTrue(etat['configuration_valide'])
        self.assertFalse(etat['bloquant'])
        self.assertEqual(etat['violations'], [])

    def test_incompatibilite_rend_le_badge_rouge_et_bloquant(self):
        ContrainteCompatibilite.objects.create(
            company=self.company, produit_a=self.p1, produit_b=self.p2,
            type=ContrainteCompatibilite.TypeContrainte.INCOMPATIBLE,
            message_utilisateur='Onduleur A incompatible avec Batterie B')
        etat = etat_configuration_devis(self.devis)
        self.assertFalse(etat['configuration_valide'])
        self.assertTrue(etat['bloquant'])
        self.assertEqual(etat['violations'][0]['message'],
                         'Onduleur A incompatible avec Batterie B')

    def test_regle_non_bloquante_reste_un_avertissement(self):
        RegleProduitCPQ.objects.create(
            company=self.company, nom='Étude triphasée recommandée',
            condition_group={'field': 'nb_lignes', 'operator': 'gte',
                             'value': 2})
        etat = etat_configuration_devis(self.devis)
        self.assertFalse(etat['configuration_valide'])
        self.assertFalse(etat['bloquant'])
        self.assertEqual(etat['violations'][0]['source'], 'regle')

    def test_regle_marquee_bloquante(self):
        RegleProduitCPQ.objects.create(
            company=self.company, nom='Configuration interdite',
            condition_group={'field': 'nb_lignes', 'operator': 'gte',
                             'value': 2},
            bloquante=True)
        etat = etat_configuration_devis(self.devis)
        self.assertTrue(etat['bloquant'])

    def test_isolation_societe(self):
        autre = CompanyFactory()
        ContrainteCompatibilite.objects.create(
            company=autre, produit_a=self.p1, produit_b=self.p2,
            type=ContrainteCompatibilite.TypeContrainte.INCOMPATIBLE)
        self.assertTrue(
            etat_configuration_devis(self.devis)['configuration_valide'])

    def test_enregistrement_en_brouillon_reste_possible(self):
        ContrainteCompatibilite.objects.create(
            company=self.company, produit_a=self.p1, produit_b=self.p2,
            type=ContrainteCompatibilite.TypeContrainte.INCOMPATIBLE)
        resp = auth(self.user).patch(
            f'/api/django/ventes/devis/{self.devis.id}/',
            {'note': 'Toujours modifiable'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.statut, Devis.Statut.BROUILLON)

    def test_serializer_detail_expose_la_cle(self):
        factory = APIRequestFactory()
        request = factory.get('/')
        request.user = self.user
        data = DevisSerializer(
            self.devis, context={'request': request}).data
        self.assertIn('configuration', data)
        self.assertTrue(data['configuration']['configuration_valide'])

    def test_serializer_liste_retire_la_cle(self):
        factory = APIRequestFactory()
        request = factory.get('/')
        request.user = self.user
        data = DevisSerializer(
            [self.devis], many=True, context={'request': request}).data
        self.assertNotIn('configuration', data[0])

    def test_rendu_non_authentifie_retire_la_cle(self):
        data = DevisSerializer(self.devis, context={}).data
        self.assertNotIn('configuration', data)

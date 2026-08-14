"""NTCPQ13 — Renouvellement d'un devis accepté (distinct de « réviser »)."""
from decimal import Decimal

from django.test import TestCase
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ventes.models import Devis, LigneDevis
from apps.ventes.services import renouveler_devis
from authentication.models import CustomUser
from testkit.factories import (
    CompanyFactory, DevisFactory, ProduitFactory, UserFactory,
)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class TestRenouvelerDevis(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.user = UserFactory(
            company=self.company, role_legacy=CustomUser.ROLE_RESPONSABLE)
        self.produit = ProduitFactory(
            company=self.company, prix_vente=Decimal('1000.00'))
        self.devis = DevisFactory(
            company=self.company, statut=Devis.Statut.ACCEPTE)
        LigneDevis.objects.create(
            devis=self.devis, produit=self.produit,
            designation=self.produit.nom, quantite=Decimal('2'),
            prix_unitaire=Decimal('800.00'))

    def test_renouvellement_applique_les_prix_catalogue_actuels(self):
        # Le catalogue a bougé depuis l'acceptation (800 → 1200).
        self.produit.prix_vente = Decimal('1200.00')
        self.produit.save(update_fields=['prix_vente'])
        nouveau = renouveler_devis(self.devis, user=self.user)
        self.assertEqual(nouveau.statut, Devis.Statut.BROUILLON)
        ligne = nouveau.lignes.get()
        self.assertEqual(ligne.prix_unitaire, Decimal('1200.00'))
        self.assertEqual(ligne.quantite, Decimal('2'))

    def test_trace_devis_origine_et_numero(self):
        n1 = renouveler_devis(self.devis, user=self.user)
        self.assertEqual(n1.devis_origine_id, self.devis.id)
        self.assertEqual(n1.numero_renouvellement, 1)
        n1.statut = Devis.Statut.ACCEPTE
        n1.save(update_fields=['statut'])
        n2 = renouveler_devis(n1, user=self.user)
        # La racine reste le devis d'origine, le compteur s'incrémente.
        self.assertEqual(n2.devis_origine_id, self.devis.id)
        self.assertEqual(n2.numero_renouvellement, 2)

    def test_devis_source_reste_intact(self):
        renouveler_devis(self.devis, user=self.user)
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.statut, Devis.Statut.ACCEPTE)
        self.assertTrue(self.devis.is_active)
        self.assertIsNone(self.devis.superseded_by_id)

    def test_reference_unique_jamais_count_plus_un(self):
        n1 = renouveler_devis(self.devis, user=self.user)
        self.assertNotEqual(n1.reference, self.devis.reference)
        self.assertEqual(
            Devis.objects.filter(
                company=self.company, reference=n1.reference).count(), 1)

    def test_refus_sur_un_devis_brouillon(self):
        brouillon = DevisFactory(
            company=self.company, statut=Devis.Statut.BROUILLON)
        with self.assertRaises(ValidationError):
            renouveler_devis(brouillon, user=self.user)

    def test_endpoint_renouveler(self):
        resp = auth(self.user).post(
            f'/api/django/ventes/devis/{self.devis.id}/renouveler/',
            {}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['numero_renouvellement'], 1)
        self.assertEqual(resp.data['statut'], Devis.Statut.BROUILLON)

    def test_endpoint_isole_les_societes(self):
        autre = DevisFactory(
            company=CompanyFactory(), statut=Devis.Statut.ACCEPTE)
        resp = auth(self.user).post(
            f'/api/django/ventes/devis/{autre.id}/renouveler/',
            {}, format='json')
        self.assertEqual(resp.status_code, 404)

    def test_chatter_trace_les_deux_cotes(self):
        nouveau = renouveler_devis(self.devis, user=self.user)
        self.assertTrue(
            self.devis.activites.filter(
                body__icontains='Renouvelé par le devis').exists())
        self.assertTrue(
            nouveau.activites.filter(
                body__icontains='Renouvellement n°').exists())

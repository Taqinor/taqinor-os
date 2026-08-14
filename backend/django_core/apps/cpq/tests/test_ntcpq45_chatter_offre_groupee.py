"""NTCPQ45 — Entrées chatter automatiques sur ``DevisActivity`` pour les
événements CPQ. L'application d'un bundle (NTCPQ3) est le seul événement du
groupe qui n'avait PAS encore d'entrée chatter — avenant (NTCPQ14),
renouvellement (NTCPQ13) et variantes (NTCPQ16) en posent déjà une."""
from decimal import Decimal

from django.test import TestCase

from apps.cpq import services
from apps.cpq.models import LigneOffreGroupee, OffreGroupee
from apps.ventes.models import DevisActivity
from testkit.factories import CompanyFactory, DevisFactory, ProduitFactory, UserFactory


class TestChatterOffreGroupee(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.user = UserFactory(company=self.company)
        self.produit = ProduitFactory(
            company=self.company, prix_vente=Decimal('500.00'))
        self.devis = DevisFactory(company=self.company)
        self.offre = OffreGroupee.objects.create(
            company=self.company, nom='Pack Confort')
        LigneOffreGroupee.objects.create(
            offre=self.offre, produit=self.produit, quantite=2,
            mode_prix=LigneOffreGroupee.ModePrix.REMISE_PCT,
            valeur=Decimal('10'))

    def test_application_bundle_pose_une_entree_chatter(self):
        services.appliquer_offre_groupee(
            offre=self.offre, devis=self.devis, user=self.user)
        entree = DevisActivity.objects.filter(
            devis=self.devis, kind=DevisActivity.Kind.NOTE).first()
        self.assertIsNotNone(entree)
        self.assertIn('Pack Confort', entree.body)
        self.assertIn('appliquée', entree.body)
        self.assertEqual(entree.user_id, self.user.id)

    def test_offre_sans_ligne_ne_pose_rien(self):
        offre_vide = OffreGroupee.objects.create(
            company=self.company, nom='Vide')
        services.appliquer_offre_groupee(
            offre=offre_vide, devis=self.devis, user=self.user)
        self.assertEqual(
            DevisActivity.objects.filter(devis=self.devis).count(), 0)

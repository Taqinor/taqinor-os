"""NTCPQ14 — Avenant de devis : diff tracé, totaux recalculés, approbation
redéclenchée UNIQUEMENT au-dessus du seuil de remise configuré."""
from decimal import Decimal

from django.test import TestCase
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.cpq.models import EtapeApprobationDevis, RegleApprobationRemise
from apps.cpq.services import appliquer_avenant_devis, taux_remise_global
from apps.ventes.models import AvenantDevis, Devis, LigneDevis
from authentication.models import CustomUser
from testkit.factories import (
    CompanyFactory, DevisFactory, ProduitFactory, UserFactory,
)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class TestAvenantDevis(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.user = UserFactory(
            company=self.company, role_legacy=CustomUser.ROLE_RESPONSABLE)
        self.produit = ProduitFactory(
            company=self.company, prix_vente=Decimal('1000.00'))
        self.devis = DevisFactory(
            company=self.company, statut=Devis.Statut.ACCEPTE)
        self.ligne = LigneDevis.objects.create(
            devis=self.devis, produit=self.produit,
            designation=self.produit.nom, quantite=Decimal('1'),
            prix_unitaire=Decimal('1000.00'))

    def test_ajout_de_ligne_cree_un_avenant_trace(self):
        avenant = appliquer_avenant_devis(
            self.devis, lignes_ajoutees=[{
                'produit': self.produit.id, 'quantite': 2,
                'prix_unitaire': '500.00'}],
            motif='Extension demandée', user=self.user)
        self.assertIsInstance(avenant, AvenantDevis)
        self.assertEqual(avenant.company_id, self.company.id)
        self.assertEqual(avenant.auteur_id, self.user.id)
        self.assertEqual(len(avenant.lignes_ajoutees), 1)
        self.assertEqual(avenant.motif, 'Extension demandée')
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.total_ht, Decimal('2000.00'))

    def test_retrait_de_ligne_recalcule_les_totaux(self):
        avenant = appliquer_avenant_devis(
            self.devis, lignes_retirees=[self.ligne.id], user=self.user)
        self.assertEqual(len(avenant.lignes_retirees), 1)
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.total_ht, Decimal('0'))

    def test_pas_dapprobation_sous_le_seuil(self):
        RegleApprobationRemise.objects.create(
            company=self.company, libelle='Grosse remise',
            remise_min_pct=Decimal('30.00'), nombre_approbateurs=1)
        appliquer_avenant_devis(
            self.devis, lignes_ajoutees=[{
                'produit': self.produit.id, 'quantite': 1,
                'prix_unitaire': '1000.00', 'remise': '5'}],
            user=self.user)
        self.assertFalse(EtapeApprobationDevis.objects.filter(
            devis=self.devis).exists())

    def test_approbation_redeclenchee_au_dessus_du_seuil(self):
        RegleApprobationRemise.objects.create(
            company=self.company, libelle='Grosse remise',
            remise_min_pct=Decimal('30.00'), nombre_approbateurs=1)
        avenant = appliquer_avenant_devis(
            self.devis, lignes_ajoutees=[{
                'produit': self.produit.id, 'quantite': 1,
                'prix_unitaire': '1000.00', 'remise': '80'}],
            user=self.user)
        self.assertTrue(avenant.approbation_requise)
        self.assertTrue(EtapeApprobationDevis.objects.filter(
            devis=self.devis,
            statut=EtapeApprobationDevis.Statut.EN_ATTENTE).exists())

    def test_taux_remise_global_combine_ligne_et_globale(self):
        self.ligne.remise = Decimal('10')
        self.ligne.save(update_fields=['remise'])
        self.devis.remise_globale = Decimal('10')
        self.devis.save(update_fields=['remise_globale'])
        self.devis.refresh_from_db()
        # 1000 → 900 (ligne) → 810 (globale) ⇒ 19 % de remise globale réelle.
        self.assertEqual(taux_remise_global(self.devis), Decimal('19.00'))

    def test_refus_sur_devis_non_accepte(self):
        brouillon = DevisFactory(
            company=self.company, statut=Devis.Statut.BROUILLON)
        with self.assertRaises(ValidationError):
            appliquer_avenant_devis(
                brouillon, lignes_ajoutees=[{'designation': 'X'}],
                user=self.user)

    def test_refus_avenant_vide(self):
        with self.assertRaises(ValidationError):
            appliquer_avenant_devis(self.devis, user=self.user)

    def test_refus_ligne_dune_autre_societe(self):
        etranger = ProduitFactory(company=CompanyFactory())
        with self.assertRaises(ValidationError):
            appliquer_avenant_devis(
                self.devis, lignes_ajoutees=[{'produit': etranger.id}],
                user=self.user)

    def test_endpoint_liste_et_creation(self):
        url = f'/api/django/ventes/devis/{self.devis.id}/avenants/'
        api = auth(self.user)
        resp = api.post(url, {
            'lignes_ajoutees': [{
                'produit': self.produit.id, 'quantite': 1,
                'prix_unitaire': '250.00'}],
            'motif': 'Ajout accessoire',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        resp = api.get(url)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]['motif'], 'Ajout accessoire')

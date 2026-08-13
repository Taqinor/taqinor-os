"""NTCPQ23 — Tableau de bord interne « marge sous seuil » (staff seulement)."""
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.cpq.models import SeuilMargeFamille
from apps.cpq.reports import devis_sous_seuil_marge
from apps.stock.models import Categorie
from apps.ventes.models import Devis, LigneDevis
from authentication.models import CustomUser
from testkit.factories import (
    CompanyFactory, DevisFactory, ProduitFactory, UserFactory,
)

URL = '/api/django/cpq/marge-sous-seuil/'


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class TestMargeSousSeuilDashboard(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.staff = UserFactory(
            company=self.company, role_legacy=CustomUser.ROLE_RESPONSABLE)
        self.commercial = UserFactory(
            company=self.company, role_legacy=CustomUser.ROLE_NORMAL)
        self.categorie = Categorie.objects.create(
            company=self.company, nom='Onduleurs')
        SeuilMargeFamille.objects.create(
            company=self.company, categorie=self.categorie,
            marge_min_pct=Decimal('30.00'))
        self.produit = ProduitFactory(
            company=self.company, categorie=self.categorie,
            prix_achat=Decimal('900.00'), prix_vente=Decimal('1000.00'))
        self.devis = DevisFactory(
            company=self.company, created_by=self.commercial)
        self.ligne = LigneDevis.objects.create(
            devis=self.devis, produit=self.produit,
            designation=self.produit.nom, quantite=Decimal('1'),
            prix_unitaire=Decimal('1000.00'))

    def test_liste_le_devis_sous_seuil(self):
        res = devis_sous_seuil_marge(self.company)
        self.assertEqual([d['devis_id'] for d in res], [self.devis.id])
        self.assertEqual(res[0]['commercial'], self.commercial.username)
        self.assertEqual(res[0]['familles'], ['Onduleurs'])

    def test_se_vide_quand_la_ligne_repasse_au_dessus(self):
        self.ligne.prix_unitaire = Decimal('5000.00')
        self.ligne.save(update_fields=['prix_unitaire'])
        self.assertEqual(devis_sous_seuil_marge(self.company), [])

    def test_devis_accepte_exclu(self):
        self.devis.statut = Devis.Statut.ACCEPTE
        self.devis.save(update_fields=['statut'])
        self.assertEqual(devis_sous_seuil_marge(self.company), [])

    def test_filtre_par_commercial(self):
        self.assertEqual(len(devis_sous_seuil_marge(
            self.company, commercial_id=self.commercial.id)), 1)
        self.assertEqual(devis_sous_seuil_marge(
            self.company, commercial_id=self.staff.id), [])

    def test_filtre_par_famille(self):
        self.assertEqual(len(devis_sous_seuil_marge(
            self.company, famille='Onduleurs')), 1)
        self.assertEqual(devis_sous_seuil_marge(
            self.company, famille='Batteries'), [])

    def test_isolation_societe(self):
        self.assertEqual(devis_sous_seuil_marge(CompanyFactory()), [])

    def test_endpoint_reserve_au_staff(self):
        self.assertEqual(auth(self.commercial).get(URL).status_code, 403)
        resp = auth(self.staff).get(URL)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data['devis']), 1)
        self.assertEqual(resp.data['devis'][0]['reference'],
                         self.devis.reference)

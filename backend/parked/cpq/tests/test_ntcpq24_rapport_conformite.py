"""NTCPQ24 — Rapport interne « taux de conformité des configurations » + CSV."""
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.cpq.models import ContrainteCompatibilite
from apps.cpq.reports import rapport_conformite_configurations
from apps.ventes.models import Devis, LigneDevis
from authentication.models import CustomUser
from testkit.factories import (
    CompanyFactory, DevisFactory, ProduitFactory, UserFactory,
)

URL = '/api/django/cpq/rapports/conformite/'


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class TestRapportConformite(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.staff = UserFactory(
            company=self.company, role_legacy=CustomUser.ROLE_RESPONSABLE)
        self.commercial = UserFactory(
            company=self.company, role_legacy=CustomUser.ROLE_NORMAL)
        self.p1 = ProduitFactory(company=self.company, nom='Onduleur A')
        self.p2 = ProduitFactory(company=self.company, nom='Batterie B')
        self.conforme = self._devis_envoye([self.p1])
        self.non_conforme = self._devis_envoye([self.p1, self.p2])
        ContrainteCompatibilite.objects.create(
            company=self.company, produit_a=self.p1, produit_b=self.p2,
            type=ContrainteCompatibilite.TypeContrainte.INCOMPATIBLE,
            message_utilisateur='Incompatibles')

    def _devis_envoye(self, produits, *, jours=0):
        devis = DevisFactory(
            company=self.company, statut=Devis.Statut.ENVOYE,
            created_by=self.commercial,
            date_envoi=timezone.now() - timedelta(days=jours))
        for produit in produits:
            LigneDevis.objects.create(
                devis=devis, produit=produit, designation=produit.nom,
                quantite=Decimal('1'), prix_unitaire=Decimal('100.00'))
        return devis

    def test_taux_de_conformite(self):
        rapport = rapport_conformite_configurations(self.company)
        self.assertEqual(rapport['total'], 2)
        self.assertEqual(rapport['conformes'], 1)
        self.assertEqual(rapport['non_conformes'], 1)
        self.assertEqual(rapport['taux_conformite_pct'], 50.0)

    def test_une_ligne_par_devis_envoye(self):
        rapport = rapport_conformite_configurations(self.company)
        refs = {li['reference']: li for li in rapport['lignes']}
        self.assertEqual(set(refs), {self.conforme.reference,
                                     self.non_conforme.reference})
        self.assertTrue(refs[self.conforme.reference]['conforme'])
        self.assertFalse(refs[self.non_conforme.reference]['conforme'])
        self.assertTrue(refs[self.non_conforme.reference]['bloquant'])
        self.assertEqual(refs[self.conforme.reference]['commercial'],
                         self.commercial.username)

    def test_brouillon_jamais_compte(self):
        DevisFactory(company=self.company, statut=Devis.Statut.BROUILLON)
        self.assertEqual(
            rapport_conformite_configurations(self.company)['total'], 2)

    def test_filtre_de_periode(self):
        self._devis_envoye([self.p1], jours=40)
        debut = (timezone.now() - timedelta(days=7)).date().isoformat()
        rapport = rapport_conformite_configurations(
            self.company, date_debut=debut)
        self.assertEqual(rapport['total'], 2)

    def test_filtre_par_commercial(self):
        rapport = rapport_conformite_configurations(
            self.company, commercial_id=self.staff.id)
        self.assertEqual(rapport['total'], 0)
        self.assertEqual(rapport['taux_conformite_pct'], 0.0)

    def test_isolation_societe(self):
        self.assertEqual(
            rapport_conformite_configurations(CompanyFactory())['total'], 0)

    def test_endpoint_reserve_au_staff(self):
        self.assertEqual(auth(self.commercial).get(URL).status_code, 403)
        resp = auth(self.staff).get(URL)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['total'], 2)

    def test_export_csv_une_ligne_par_devis(self):
        resp = auth(self.staff).get(f'{URL}?format=csv')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('text/csv', resp['Content-Type'])
        lignes = resp.content.decode('utf-8').strip().splitlines()
        self.assertEqual(len(lignes), 3)  # en-tête + 2 devis
        self.assertIn('reference', lignes[0])
        self.assertIn('commercial', lignes[0])
        corps = '\n'.join(lignes[1:])
        self.assertIn(self.conforme.reference, corps)
        self.assertIn(self.commercial.username, corps)
        # Rapport INTERNE : aucune donnée de marge / prix d'achat.
        self.assertNotIn('prix_achat', resp.content.decode('utf-8'))

"""XFAC23 — Conditions de paiement par client (délai / fin de mois).

Covers:
  - crm.Client.delai_paiement_jours / fin_de_mois : champs additifs, défaut
    inoffensif (None / False).
  - crm.selectors.delai_paiement_client : lecture seule, client=None safe.
  - ventes.services.calculer_date_echeance : dérivation délai simple, report
    fin de mois, fallback None sans réglage.
  - apps.ventes.scheduled._echeance_effective : priorité à une échéance déjà
    posée manuellement, puis dérivation client, puis repli +30 j historique.
  - FactureViewSet.emettre : dérive et persiste l'échéance à l'émission sans
    jamais écraser une échéance déjà saisie.
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.crm.selectors import delai_paiement_client
from apps.ventes.models import Facture, LigneFacture
from apps.ventes.services import calculer_date_echeance
from apps.ventes.scheduled import _echeance_effective

User = get_user_model()


def make_company(slug='xfac23-co'):
    from authentication.models import Company
    return Company.objects.get_or_create(slug=slug, defaults={'nom': slug})[0]


class TestDelaiPaiementSelector(TestCase):
    def setUp(self):
        self.company = make_company()

    def test_client_sans_reglage_defaut_inoffensif(self):
        client = Client.objects.create(company=self.company, nom='Sans réglage')
        reglage = delai_paiement_client(client)
        self.assertIsNone(reglage['delai_jours'])
        self.assertFalse(reglage['fin_de_mois'])

    def test_client_none_defaut_inoffensif(self):
        reglage = delai_paiement_client(None)
        self.assertIsNone(reglage['delai_jours'])
        self.assertFalse(reglage['fin_de_mois'])

    def test_client_avec_reglage(self):
        client = Client.objects.create(
            company=self.company, nom='60j FdM',
            delai_paiement_jours=60, fin_de_mois=True)
        reglage = delai_paiement_client(client)
        self.assertEqual(reglage['delai_jours'], 60)
        self.assertTrue(reglage['fin_de_mois'])


class TestCalculerDateEcheance(TestCase):
    def setUp(self):
        self.company = make_company()

    def test_sans_reglage_renvoie_none(self):
        client = Client.objects.create(company=self.company, nom='Défaut')
        self.assertIsNone(calculer_date_echeance(
            client=client, date_emission=datetime.date(2026, 7, 1)))

    def test_client_none_renvoie_none(self):
        self.assertIsNone(calculer_date_echeance(
            client=None, date_emission=datetime.date(2026, 7, 1)))

    def test_delai_simple_30_jours(self):
        client = Client.objects.create(
            company=self.company, nom='30j', delai_paiement_jours=30)
        echeance = calculer_date_echeance(
            client=client, date_emission=datetime.date(2026, 7, 1))
        self.assertEqual(echeance, datetime.date(2026, 7, 31))

    def test_60_jours_fin_de_mois(self):
        """« 60 jours fin de mois » : émission 5 juillet + 60j = 3 septembre,
        reporté au dernier jour de septembre (30)."""
        client = Client.objects.create(
            company=self.company, nom='60j FdM',
            delai_paiement_jours=60, fin_de_mois=True)
        echeance = calculer_date_echeance(
            client=client, date_emission=datetime.date(2026, 7, 5))
        self.assertEqual(echeance, datetime.date(2026, 9, 30))

    def test_fin_de_mois_sans_delai_reste_none(self):
        """fin_de_mois seul (sans délai) ne fabrique pas d'échéance."""
        client = Client.objects.create(
            company=self.company, nom='FdM seul', fin_de_mois=True)
        self.assertIsNone(calculer_date_echeance(
            client=client, date_emission=datetime.date(2026, 7, 5)))


class TestEcheanceEffectiveFallbackChain(TestCase):
    def setUp(self):
        self.company = make_company()
        self.today = datetime.date(2026, 8, 15)

    def _facture(self, client, date_echeance=None):
        return Facture.objects.create(
            company=self.company, reference='FAC-XFAC23',
            client=client, statut=Facture.Statut.EMISE,
            date_emission=datetime.date(2026, 7, 1),
            date_echeance=date_echeance)

    def test_echeance_manuelle_jamais_ecrasee(self):
        client = Client.objects.create(
            company=self.company, nom='C1', delai_paiement_jours=60)
        manuelle = datetime.date(2026, 12, 25)
        facture = self._facture(client, date_echeance=manuelle)
        self.assertEqual(_echeance_effective(facture, self.today), manuelle)

    def test_derivee_du_client_quand_pas_manuelle(self):
        client = Client.objects.create(
            company=self.company, nom='C2', delai_paiement_jours=60,
            fin_de_mois=True)
        facture = self._facture(client)
        # émission 2026-07-01 + 60j = 2026-08-30, fin de mois -> 2026-08-31
        self.assertEqual(
            _echeance_effective(facture, self.today), datetime.date(2026, 8, 31))

    def test_repli_30_jours_sans_reglage_client(self):
        client = Client.objects.create(company=self.company, nom='C3')
        facture = self._facture(client)
        self.assertEqual(
            _echeance_effective(facture, self.today), datetime.date(2026, 7, 31))


class TestEmettreActionDerivesEcheance(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='xfac23resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        token = AccessToken.for_user(self.user)
        self.api.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    def _facture_brouillon(self, client, date_echeance=None):
        facture = Facture.objects.create(
            company=self.company, reference='FAC-XFAC23-EM',
            client=client, statut=Facture.Statut.BROUILLON,
            taux_tva=Decimal('20.00'), date_echeance=date_echeance)
        LigneFacture.objects.create(
            facture=facture, designation='Ligne test',
            quantite=Decimal('1'), prix_unitaire=Decimal('100'),
            taux_tva=Decimal('20.00'))
        return facture

    def test_emettre_derive_echeance_client(self):
        client = Client.objects.create(
            company=self.company, nom='C60', delai_paiement_jours=60)
        facture = self._facture_brouillon(client)
        resp = self.api.post(f'/api/django/ventes/factures/{facture.id}/emettre/')
        self.assertEqual(resp.status_code, 200, resp.content)
        facture.refresh_from_db()
        self.assertEqual(facture.statut, Facture.Statut.EMISE)
        self.assertEqual(
            facture.date_echeance,
            facture.date_emission + datetime.timedelta(days=60))

    def test_emettre_respecte_echeance_manuelle(self):
        client = Client.objects.create(
            company=self.company, nom='C60manuel', delai_paiement_jours=60)
        manuelle = datetime.date(2099, 1, 1)
        facture = self._facture_brouillon(client, date_echeance=manuelle)
        resp = self.api.post(f'/api/django/ventes/factures/{facture.id}/emettre/')
        self.assertEqual(resp.status_code, 200, resp.content)
        facture.refresh_from_db()
        self.assertEqual(facture.date_echeance, manuelle)

    def test_emettre_sans_reglage_client_laisse_echeance_vide(self):
        """Sans réglage client, l'émission ne fabrique pas d'échéance : le
        comportement historique (repli +30 j du job planifié) reste inchangé."""
        client = Client.objects.create(company=self.company, nom='CDefaut')
        facture = self._facture_brouillon(client)
        resp = self.api.post(f'/api/django/ventes/factures/{facture.id}/emettre/')
        self.assertEqual(resp.status_code, 200, resp.content)
        facture.refresh_from_db()
        self.assertIsNone(facture.date_echeance)

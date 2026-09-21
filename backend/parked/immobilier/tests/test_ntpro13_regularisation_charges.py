"""NTPRO13 — Régularisation annuelle des charges.

Couvre : la régularisation compare provisions encaissées vs quote-part
réelle (NTPRO12) par bail, génère exactement UN document ventes par bail
(facture si à facturer, avoir — facture négative — si à rembourser, JAMAIS
les deux), et ne crée AUCUN document au cas d'égalité (solde=0). Les
primitives ventes (`apps.crm.selectors.get_company_client` /
`apps.ventes.services.creer_facture_classique`) sont MOCKÉES — ce test ne
dépend d'aucun objet ``ventes`` réel, seulement du CONTRAT d'appel.
"""
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.immobilier.models import (
    Bail, Batiment, BudgetCharges, DepenseCharges, EcheanceLoyer, Local,
    Locataire, Niveau, RegularisationCharges, Site,
)
from apps.immobilier.services import (
    creer_bail, emettre_regularisation, generer_regularisation,
)

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='admin'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Ntpro13RegularisationChargesTests(TestCase):
    def setUp(self):
        self.co_a = make_company('immo-rg-a', 'Immo RG A')
        self.admin_a = make_user(self.co_a, 'immo-rg-admin-a')
        site = Site.objects.create(company=self.co_a, nom='Résidence')
        self.batiment = Batiment.objects.create(
            company=self.co_a, site=site, nom='Bât A')
        niveau = Niveau.objects.create(
            company=self.co_a, batiment=self.batiment, numero='RDC')
        # UN SEUL local occupé, tantièmes = base totale : sa quote-part vaut
        # donc EXACTEMENT le total des dépenses réelles (pas d'arrondi à
        # gérer), ce qui isole le test sur la logique de régularisation.
        self.local = Local.objects.create(
            company=self.co_a, niveau=niveau, reference='RDC-01',
            statut=Local.Statut.LOUE, tantiemes=Decimal('100'))
        self.locataire = Locataire.objects.create(
            company=self.co_a, nom='Bennani', client_ventes_id=999)
        self.bail = creer_bail(
            company=self.co_a, local=self.local, locataire=self.locataire,
            type_bail=Bail.TypeBail.HABITATION, date_debut=date(2026, 1, 1),
            duree_mois=1, loyer_mensuel_ht=Decimal('3000.00'),
            charges_mensuelles_provisions=Decimal('2400.00'))
        # Provisions ENCAISSÉES (échéance déjà émise) = 2400.00.
        self.echeance = EcheanceLoyer.objects.create(
            company=self.co_a, bail=self.bail,
            periode_debut=date(2026, 1, 1), periode_fin=date(2026, 1, 31),
            montant_loyer_ht=Decimal('3000.00'),
            montant_charges=Decimal('2400.00'),
            montant_total=Decimal('5400.00'),
            statut=EcheanceLoyer.Statut.EMISE)

    def _set_depenses_reelles(self, montant):
        budget = BudgetCharges.objects.create(
            company=self.co_a, batiment=self.batiment, exercice=2026,
            poste=BudgetCharges.Poste.NETTOYAGE,
            montant_budgete_annuel=Decimal('10000.00'))
        DepenseCharges.objects.create(
            company=self.co_a, budget_charges=budget, date=date(2026, 6, 1),
            montant_reel=montant)

    def test_solde_positif_sens_a_rembourser(self):
        self._set_depenses_reelles(Decimal('1800.00'))  # 2400 - 1800 = 600
        resultats = generer_regularisation(self.batiment, 2026)
        self.assertEqual(len(resultats), 1)
        reg = resultats[0]
        self.assertEqual(reg.provisions_encaissees, Decimal('2400.00'))
        self.assertEqual(reg.quote_part_reelle, Decimal('1800.00'))
        self.assertEqual(reg.solde, Decimal('600.00'))
        self.assertEqual(reg.sens, RegularisationCharges.Sens.A_REMBOURSER)

    def test_solde_negatif_sens_a_facturer(self):
        self._set_depenses_reelles(Decimal('3000.00'))  # 2400 - 3000 = -600
        resultats = generer_regularisation(self.batiment, 2026)
        reg = resultats[0]
        self.assertEqual(reg.solde, Decimal('-600.00'))
        self.assertEqual(reg.sens, RegularisationCharges.Sens.A_FACTURER)

    def test_solde_nul_sens_neutre(self):
        self._set_depenses_reelles(Decimal('2400.00'))  # égalité exacte
        resultats = generer_regularisation(self.batiment, 2026)
        reg = resultats[0]
        self.assertEqual(reg.solde, Decimal('0.00'))
        self.assertEqual(reg.sens, RegularisationCharges.Sens.NEUTRE)

    def test_generer_regularisation_idempotent_meme_bail_exercice(self):
        self._set_depenses_reelles(Decimal('1800.00'))
        generer_regularisation(self.batiment, 2026)
        generer_regularisation(self.batiment, 2026)
        self.assertEqual(
            RegularisationCharges.objects.filter(
                bail=self.bail, exercice=2026).count(), 1)

    def test_emettre_a_facturer_cree_une_facture_jamais_avoir(self):
        self._set_depenses_reelles(Decimal('3000.00'))
        reg = generer_regularisation(self.batiment, 2026)[0]
        fake_client = SimpleNamespace(id=999, company_id=self.co_a.id)
        fake_facture = SimpleNamespace(id=5001)
        with patch(
            'apps.crm.selectors.get_company_client', return_value=fake_client,
        ), patch(
            'apps.ventes.services.creer_facture_classique',
            return_value=fake_facture,
        ) as mock_creer:
            document_id = emettre_regularisation(reg)

        self.assertEqual(document_id, 5001)
        mock_creer.assert_called_once()
        self.assertEqual(mock_creer.call_args.kwargs['montant_ht'], Decimal('600.00'))
        reg.refresh_from_db()
        self.assertEqual(reg.facture_ventes_id, 5001)
        self.assertIsNone(reg.avoir_ventes_id)

    def test_emettre_a_rembourser_cree_un_avoir_montant_negatif(self):
        self._set_depenses_reelles(Decimal('1800.00'))
        reg = generer_regularisation(self.batiment, 2026)[0]
        fake_client = SimpleNamespace(id=999, company_id=self.co_a.id)
        fake_avoir = SimpleNamespace(id=6002)
        with patch(
            'apps.crm.selectors.get_company_client', return_value=fake_client,
        ), patch(
            'apps.ventes.services.creer_facture_classique',
            return_value=fake_avoir,
        ) as mock_creer:
            document_id = emettre_regularisation(reg)

        self.assertEqual(document_id, 6002)
        self.assertEqual(mock_creer.call_args.kwargs['montant_ht'], Decimal('-600.00'))
        reg.refresh_from_db()
        self.assertEqual(reg.avoir_ventes_id, 6002)
        self.assertIsNone(reg.facture_ventes_id)

    def test_emettre_neutre_ne_cree_aucun_document(self):
        self._set_depenses_reelles(Decimal('2400.00'))
        reg = generer_regularisation(self.batiment, 2026)[0]
        with patch('apps.ventes.services.creer_facture_classique') as mock_creer:
            document_id = emettre_regularisation(reg)

        self.assertIsNone(document_id)
        mock_creer.assert_not_called()
        reg.refresh_from_db()
        self.assertIsNone(reg.facture_ventes_id)
        self.assertIsNone(reg.avoir_ventes_id)

    def test_emettre_deux_fois_jamais_de_doublon(self):
        self._set_depenses_reelles(Decimal('3000.00'))
        reg = generer_regularisation(self.batiment, 2026)[0]
        fake_client = SimpleNamespace(id=999, company_id=self.co_a.id)
        fake_facture = SimpleNamespace(id=5001)
        with patch(
            'apps.crm.selectors.get_company_client', return_value=fake_client,
        ), patch(
            'apps.ventes.services.creer_facture_classique',
            return_value=fake_facture,
        ) as mock_creer:
            emettre_regularisation(reg)
            reg.refresh_from_db()
            document_id_2 = emettre_regularisation(reg)

        self.assertEqual(document_id_2, 5001)
        mock_creer.assert_called_once()

    def test_api_generer_puis_emettre_regularisation(self):
        self._set_depenses_reelles(Decimal('1800.00'))
        api = auth(self.admin_a)
        resp = api.post(
            f'/api/django/immobilier/batiments/{self.batiment.id}/'
            'generer-regularisation/', {'exercice': 2026}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(len(resp.data), 1)
        reg_id = resp.data[0]['id']
        self.assertEqual(resp.data[0]['sens'], 'a_rembourser')

        fake_client = SimpleNamespace(id=999, company_id=self.co_a.id)
        fake_avoir = SimpleNamespace(id=7003)
        with patch(
            'apps.crm.selectors.get_company_client', return_value=fake_client,
        ), patch(
            'apps.ventes.services.creer_facture_classique',
            return_value=fake_avoir,
        ):
            resp2 = api.post(
                f'/api/django/immobilier/regularisations-charges/{reg_id}/'
                'emettre/', {}, format='json')
        self.assertEqual(resp2.status_code, 200, resp2.data)
        self.assertEqual(resp2.data['document_ventes_id'], 7003)

    def test_api_create_directe_refusee(self):
        api = auth(self.admin_a)
        resp = api.post(
            '/api/django/immobilier/regularisations-charges/',
            {'bail': self.bail.id, 'exercice': 2026}, format='json')
        self.assertEqual(resp.status_code, 405)

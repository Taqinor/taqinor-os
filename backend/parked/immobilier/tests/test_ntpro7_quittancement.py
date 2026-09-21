"""NTPRO7 — Quittancement → facturation via ``apps.ventes.services``.

Couvre : émettre une quittance crée EXACTEMENT une facture ventes (jamais de
doublon), le PDF quittance affiche période/local/locataire/montant. Le
service ``apps.ventes.services.creer_facture_classique`` est MOCKÉ — ce test
ne dépend d'aucun objet ``ventes`` réel, seulement du CONTRAT d'appel.
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
    Bail, Batiment, EcheanceLoyer, Local, Locataire, Niveau, Site,
)
from apps.immobilier.services import (
    ClientVentesIntrouvableError, creer_bail, emettre_quittance,
    generer_echeancier,
)
from apps.immobilier.pdf import render_quittance_pdf

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


class Ntpro7QuittancementTests(TestCase):
    def setUp(self):
        self.co_a = make_company('immo-quit-a', 'Immo Quit A')
        self.admin_a = make_user(self.co_a, 'immo-quit-admin-a')
        site = Site.objects.create(company=self.co_a, nom='Résidence')
        batiment = Batiment.objects.create(
            company=self.co_a, site=site, nom='Bât A')
        niveau = Niveau.objects.create(
            company=self.co_a, batiment=batiment, numero='RDC')
        local = Local.objects.create(
            company=self.co_a, niveau=niveau, reference='RDC-01')
        self.locataire = Locataire.objects.create(
            company=self.co_a, nom='Bennani', client_ventes_id=999)
        self.bail = creer_bail(
            company=self.co_a, local=local, locataire=self.locataire,
            type_bail=Bail.TypeBail.HABITATION, date_debut=date(2026, 1, 1),
            duree_mois=1, loyer_mensuel_ht=Decimal('3000.00'),
            charges_mensuelles_provisions=Decimal('200.00'))
        generer_echeancier(self.bail)
        self.echeance = EcheanceLoyer.objects.get(bail=self.bail)

    def test_emettre_quittance_cree_une_facture_et_met_a_jour_echeance(self):
        fake_client = SimpleNamespace(id=999, company_id=self.co_a.id)
        fake_facture = SimpleNamespace(id=4242)
        with patch(
            'apps.crm.selectors.get_company_client', return_value=fake_client,
        ), patch(
            'apps.ventes.services.creer_facture_classique',
            return_value=fake_facture,
        ) as mock_creer:
            facture_id = emettre_quittance(self.echeance)

        self.assertEqual(facture_id, 4242)
        mock_creer.assert_called_once()
        self.echeance.refresh_from_db()
        self.assertEqual(self.echeance.facture_ventes_id, 4242)
        self.assertEqual(self.echeance.statut, EcheanceLoyer.Statut.EMISE)
        self.assertIsNotNone(self.echeance.date_emission_quittance)

    def test_emettre_quittance_jamais_de_doublon(self):
        fake_client = SimpleNamespace(id=999, company_id=self.co_a.id)
        fake_facture = SimpleNamespace(id=4242)
        with patch(
            'apps.crm.selectors.get_company_client', return_value=fake_client,
        ), patch(
            'apps.ventes.services.creer_facture_classique',
            return_value=fake_facture,
        ) as mock_creer:
            emettre_quittance(self.echeance)
            # Deuxième émission sur la MÊME échéance (statut déjà EMISE) —
            # aucune nouvelle facture ne doit être créée.
            self.echeance.refresh_from_db()
            facture_id_2 = emettre_quittance(self.echeance)

        self.assertEqual(facture_id_2, 4242)
        mock_creer.assert_called_once()

    def test_emettre_quittance_sans_client_leve_erreur(self):
        locataire_sans_client = Locataire.objects.create(
            company=self.co_a, nom='Sans Client')
        bail_2 = creer_bail(
            company=self.co_a, local=self.bail.local,
            locataire=locataire_sans_client,
            statut=Bail.Statut.BROUILLON, type_bail=Bail.TypeBail.HABITATION,
            date_debut=date(2026, 2, 1), duree_mois=1,
            loyer_mensuel_ht=Decimal('1000.00'))
        # Forcer actif pour générer une échéance sans avoir de conflit avec
        # le bail déjà actif du même local (statut brouillon plus haut).
        bail_2.statut = Bail.Statut.ACTIF
        bail_2.save(update_fields=['statut'])
        echeances = generer_echeancier(bail_2)
        with self.assertRaises(ClientVentesIntrouvableError):
            emettre_quittance(echeances[0])

    def test_pdf_quittance_affiche_periode_local_locataire_montant(self):
        with patch('apps.immobilier.pdf.render_pdf') as mock_render:
            mock_render.return_value = b'%PDF-FAKE%'
            render_quittance_pdf(self.echeance)

        html = mock_render.call_args.kwargs['html']
        self.assertIn('RDC-01', html)
        self.assertIn('Bennani', html)
        self.assertIn('3200.00', html)

    def test_api_emettre_quittance_action(self):
        fake_client = SimpleNamespace(id=999, company_id=self.co_a.id)
        fake_facture = SimpleNamespace(id=4242)
        api = auth(self.admin_a)
        with patch(
            'apps.crm.selectors.get_company_client', return_value=fake_client,
        ), patch(
            'apps.ventes.services.creer_facture_classique',
            return_value=fake_facture,
        ):
            resp = api.post(
                f'/api/django/immobilier/echeances-loyer/{self.echeance.id}/'
                'emettre-quittance/', {}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['facture_ventes_id'], 4242)

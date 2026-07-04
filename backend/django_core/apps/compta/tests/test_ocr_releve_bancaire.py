"""Tests XACC30 — OCR de relevé bancaire (gated).

Couvre : un PDF de relevé produit les lignes proposées avec contrôle de
solde (jamais d'intégration silencieuse) ; l'acceptation les injecte dans le
rapprochement FG123 ; sans clé l'endpoint répond 503 explicite et rien
d'autre ne change ; le service reste dégradé proprement.
"""
from datetime import date
from decimal import Decimal
from io import BytesIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.compta import services
from apps.compta.models import CompteTresorerie, LigneReleve

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class OcrReleveServiceTests(TestCase):
    def setUp(self):
        self.co = make_company('xacc30-svc', 'XACC30 Svc')
        self.user = make_user(self.co, 'xacc30-svc-user')
        services.seed_plan_comptable(self.co)
        self.treso = CompteTresorerie.objects.create(
            company=self.co, type_compte=CompteTresorerie.Type.BANQUE,
            libelle='Banque test', solde_initial=Decimal('1000'),
            compte_comptable=services.get_compte(self.co, '5141'))
        self.rapprochement = services.creer_rapprochement(
            self.co, self.treso,
            date_debut=date(2026, 6, 1), date_fin=date(2026, 6, 30),
            solde_releve=Decimal('1500'), created_by=self.user)

    def test_inactive_par_defaut(self):
        self.assertFalse(services.ocr_releve_bancaire_active())

    def test_extraire_sans_cle_leve_runtime_error(self):
        with self.assertRaises(RuntimeError):
            services.extraire_releve_bancaire(b'fake-bytes')

    @override_settings(COMPTA_OCR_RELEVE_ENABLED=True)
    def test_extraire_active_sans_provider_reste_noop(self):
        self.assertEqual(services.extraire_releve_bancaire(b'fake-bytes'), {})

    def test_controle_solde_concordant(self):
        champs = {
            'solde_initial': '1000', 'solde_final': '1500',
            'lignes': [
                {'date': '2026-06-05', 'libelle': 'Virement', 'montant': '600'},
                {'date': '2026-06-10', 'libelle': 'Frais banque', 'montant': '-100'},
            ],
        }
        resultat = services.controler_solde_releve_ocr(champs)
        self.assertTrue(resultat['concordant'])
        self.assertEqual(resultat['ecart'], Decimal('0.00'))

    def test_controle_solde_discordant(self):
        champs = {
            'solde_initial': '1000', 'solde_final': '2000',
            'lignes': [{'date': '2026-06-05', 'libelle': 'X', 'montant': '600'}],
        }
        resultat = services.controler_solde_releve_ocr(champs)
        self.assertFalse(resultat['concordant'])
        self.assertEqual(resultat['ecart'], Decimal('400.00'))

    def test_accepter_lignes_injecte_dans_rapprochement(self):
        lignes = [
            {'date_operation': '2026-06-05', 'libelle': 'Virement',
             'montant': '600'},
            {'date_operation': '2026-06-10', 'libelle': 'Frais',
             'montant': '-100'},
        ]
        creees = services.accepter_lignes_releve_ocr(
            self.rapprochement, lignes)
        self.assertEqual(len(creees), 2)
        self.assertEqual(
            LigneReleve.objects.filter(
                rapprochement=self.rapprochement).count(), 2)


class OcrReleveEndpointTests(TestCase):
    def setUp(self):
        self.co = make_company('xacc30-api', 'XACC30 Api')
        self.user = make_user(self.co, 'xacc30-api-user')
        services.seed_plan_comptable(self.co)
        self.treso = CompteTresorerie.objects.create(
            company=self.co, type_compte=CompteTresorerie.Type.BANQUE,
            libelle='Banque test 2', solde_initial=Decimal('1000'),
            compte_comptable=services.get_compte(self.co, '5141'))
        self.rapprochement = services.creer_rapprochement(
            self.co, self.treso,
            date_debut=date(2026, 6, 1), date_fin=date(2026, 6, 30),
            solde_releve=Decimal('1500'), created_by=self.user)
        self.url = (
            f'/api/django/compta/rapprochements/{self.rapprochement.id}/'
            'ocr-import/')

    def _fichier(self):
        f = BytesIO(b'fake-pdf-bytes')
        f.name = 'releve.pdf'
        return f

    def test_sans_cle_503(self):
        resp = auth(self.user).post(
            self.url, {'releve': self._fichier()}, format='multipart')
        self.assertEqual(resp.status_code, 503)
        self.assertIn('OCR indisponible', resp.data['detail'])
        self.assertEqual(
            LigneReleve.objects.filter(rapprochement=self.rapprochement).count(),
            0)

    def test_fichier_manquant_400(self):
        resp = auth(self.user).post(self.url, {}, format='multipart')
        self.assertEqual(resp.status_code, 400)

    @override_settings(COMPTA_OCR_RELEVE_ENABLED=True)
    def test_avec_cle_mockee_propose_lignes(self):
        mock_champs = {
            'solde_initial': '1000', 'solde_final': '1500',
            'lignes': [
                {'date': '2026-06-05', 'libelle': 'Virement', 'montant': '600'},
                {'date': '2026-06-10', 'libelle': 'Frais', 'montant': '-100'},
            ],
        }
        with patch(
            'apps.compta.services.extraire_releve_bancaire',
            return_value=mock_champs,
        ):
            resp = auth(self.user).post(
                self.url, {'releve': self._fichier()}, format='multipart')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data['concordant'])
        self.assertEqual(len(resp.data['lignes']), 2)
        # AUCUNE intégration silencieuse : rien n'est créé avant acceptation.
        self.assertEqual(
            LigneReleve.objects.filter(rapprochement=self.rapprochement).count(),
            0)

    def test_acceptation_injecte_les_lignes(self):
        resp = auth(self.user).post(
            self.url,
            {'accepter': '1',
             'lignes': (
                 '[{"date_operation": "2026-06-05", "libelle": "Virement", '
                 '"montant": "600"}]')},
            format='multipart')
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(
            LigneReleve.objects.filter(rapprochement=self.rapprochement).count(),
            1)

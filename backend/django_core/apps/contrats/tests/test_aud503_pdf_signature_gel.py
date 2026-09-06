"""AUD503 — le PDF porte sa preuve de signature, et le financier se fige.

``contexte_fusion`` ne posait NI signataire, NI date, NI méthode, NI référence
de preuve : le PDF d'un contrat SIGNÉ ne montrait AUCUNE trace de sa signature.
Et ``rendre_contrat_pdf`` REGÉNÈRE le document à la volée depuis un Contrat
resté mutable (``statut`` writable — cf. AUD501) : montant et dates pouvaient
donc changer APRÈS coup sur un contrat déjà signé, et le « même » document ne
disait plus ce que la partie avait signé.

Décision fondateur D11 : étiquetage HONNÊTE du niveau de signature (signature
électronique simple, loi 43-20) sur le document.
"""
import itertools
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.contrats import services
from apps.contrats.models import Contrat, PartieContrat, SignatureContrat
from authentication.models import Company

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/contrats/contrats'


class TestPdfSignatureEtGelFinancier(TestCase):
    def setUp(self):
        n = next(_seq)
        self.company = Company.objects.create(
            slug=f'aud503-{n}', nom=f'AUD503 Co {n}')
        self.user = User.objects.create_user(
            username=f'aud503-{n}', password='x', role_legacy='admin',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def _contrat(self, statut=Contrat.Statut.SIGNE):
        contrat = Contrat.objects.create(
            company=self.company, created_by=self.user,
            reference=f'CTR-AUD503-{next(_seq)}', objet='Maintenance PV',
            statut=statut, montant=Decimal('12000'),
            date_debut=timezone.localdate())
        for i in range(2):
            PartieContrat.objects.create(
                company=self.company, contrat=contrat,
                nom=f'Partie {i}', ordre=i)
        return contrat

    def _signer(self, contrat, nom='M. Alaoui'):
        return SignatureContrat.objects.create(
            company=self.company, contrat=contrat, signataire_nom=nom,
            role_signataire=SignatureContrat.RoleSignataire.CLIENT,
            ip_adresse='196.200.0.1')

    # ── Le document PORTE sa signature ────────────────────────────────────

    def test_contrat_non_signe_le_dit(self):
        contrat = self._contrat(statut=Contrat.Statut.BROUILLON)
        self.assertEqual(
            services.bloc_signatures(contrat), 'Non signé à ce jour.')

    def test_le_bloc_nomme_signataire_date_methode_et_preuve(self):
        """ROUGE avant le correctif : le contexte de fusion ne posait NI
        signataire, NI date, NI méthode, NI référence de preuve."""
        contrat = self._contrat()
        signature = self._signer(contrat)
        bloc = services.bloc_signatures(contrat)
        self.assertIn('M. Alaoui', bloc)
        self.assertIn(signature.date_signature.date().isoformat(), bloc)
        self.assertIn(f'SIG-{signature.pk}', bloc)
        self.assertIn('196.200.0.1', bloc)
        # Décision D11 — étiquetage HONNÊTE du niveau de signature.
        self.assertIn('loi 43-20', bloc)
        self.assertIn('simple', bloc.lower())

    def test_le_contexte_de_fusion_porte_le_jeton(self):
        contrat = self._contrat()
        self._signer(contrat)
        contexte = services.contexte_fusion(contrat)
        self.assertIn('signatures', contexte)
        self.assertIn('M. Alaoui', contexte['signatures'])

    def test_le_html_du_pdf_montre_le_bloc_meme_sans_jeton_au_gabarit(self):
        """Un `ModeleContrat` maison n'a aucune raison de porter le jeton :
        le document le porte quand même."""
        contrat = self._contrat()
        self._signer(contrat)
        html = services._contrat_html(contrat)
        self.assertIn('Signatures', html)
        self.assertIn('M. Alaoui', html)
        self.assertIn('43-20', html)

    # ── Le financier se FIGE ──────────────────────────────────────────────

    def test_patch_du_montant_refuse_sur_un_contrat_signe(self):
        """ROUGE avant le correctif : le PATCH réussissait, et le PDF
        regénéré annonçait un autre montant que celui signé."""
        contrat = self._contrat()
        resp = self.api.patch(
            f'{BASE}/{contrat.id}/', {'montant': '99000'}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('montant', resp.data)
        contrat.refresh_from_db()
        self.assertEqual(contrat.montant, Decimal('12000'))

    def test_patch_des_dates_refuse_sur_un_contrat_signe(self):
        contrat = self._contrat()
        resp = self.api.patch(
            f'{BASE}/{contrat.id}/', {'date_fin': '2030-01-01'},
            format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        contrat.refresh_from_db()
        self.assertIsNone(contrat.date_fin)

    def test_le_brouillon_reste_librement_modifiable(self):
        contrat = self._contrat(statut=Contrat.Statut.BROUILLON)
        resp = self.api.patch(
            f'{BASE}/{contrat.id}/', {'montant': '15000'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        contrat.refresh_from_db()
        self.assertEqual(contrat.montant, Decimal('15000'))

    def test_un_champ_non_financier_reste_modifiable_apres_signature(self):
        """Le gel vise les conditions FINANCIÈRES, pas l'édition courante."""
        contrat = self._contrat()
        resp = self.api.patch(
            f'{BASE}/{contrat.id}/', {'objet': 'Maintenance PV — révisée'},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        contrat.refresh_from_db()
        self.assertEqual(contrat.objet, 'Maintenance PV — révisée')

    def test_renvoyer_la_meme_valeur_ne_declenche_pas_le_gel(self):
        """Un PUT complet qui ne CHANGE rien de financier doit passer."""
        contrat = self._contrat()
        resp = self.api.patch(
            f'{BASE}/{contrat.id}/', {'montant': '12000.00'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

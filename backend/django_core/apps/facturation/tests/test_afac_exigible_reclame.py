"""AFAC24 (C-AFAC-019 + base de C-AFAC-040) — `montant_exigible` (CIQ214) est
l'unique « à payer maintenant » de toute surface qui RÉCLAME de l'argent :
lien de paiement, lettre de relance PDF (montant + garde `facture_relancable`)
et base de `facturer-penalites` (même formule que la pénalité indicative).

Rejoue FPAY-3 (lien à 100 000 contre exigible 90 000 ; lien créé pour la seule
retenue), FREC-10 (lettre 200 sur facture payée ; lettre ≠ e-mail) et FREC-8
(pénalité facturée sur `montant_du`). Endpoints réels ; le rendu WeasyPrint est
remplacé par une capture du HTML (seule frontière doublée).

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.facturation.tests.test_afac_exigible_reclame"
"""
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

User = get_user_model()
_CTR = [0]


def _nxt():
    _CTR[0] += 1
    return _CTR[0]


class ExigibleReclameTests(TestCase):
    def setUp(self):
        from apps.crm.models import Client
        from apps.ventes.models import Facture, FollowupLevel
        from authentication.models import Company
        self.company = Company.objects.create(
            nom='AFAC24 Co', slug=f'afac24-co-{_nxt()}')
        self.admin = User.objects.create_user(
            username=f'afac24_admin_{_nxt()}', password='x',
            role_legacy='admin', company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Usine', prenom='AFAC24',
            email=f'afac24-{_nxt()}@example.invalid')
        ttc = Decimal('100000')
        self.facture = Facture.objects.create(
            company=self.company, reference=f'FAC-AFAC24-{_nxt()}',
            client=self.client_obj, statut='emise', taux_tva=Decimal('20'),
            montant_ht=ttc / Decimal('1.2'), montant_tva=ttc / Decimal('6'),
            montant_ttc=ttc, retenue_garantie_mad=Decimal('10000'),
            date_echeance=timezone.now().date() - timedelta(days=20))
        self.niveau = FollowupLevel.objects.create(
            company=self.company, ordre=1, nom='Relance', delai_jours=15,
            taux_interet_annuel=Decimal('12.00'), frais_fixes=Decimal('100'))
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')

    def _payer(self, montant):
        from apps.ventes.models import Paiement
        Paiement.objects.create(
            company=self.company, facture=self.facture,
            montant=Decimal(montant), date_paiement=date(2026, 10, 1),
            mode='virement', created_by=self.admin)

    def _lien(self):
        return self.api.post(
            f'/api/django/ventes/factures/{self.facture.id}/lien-paiement/',
            {}, format='json')

    def test_lien_paiement_sur_exigible(self):
        from apps.ventes.models import PaymentLink
        r = self._lien()
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['montant_a_payer'], '90000.00')
        self.assertEqual(Decimal(r.data['montant']), Decimal('90000.00'))
        pub = APIClient().get(f"/api/django/public/pay/{r.data['token']}/")
        self.assertEqual(pub.data['montant'], '90000.00')
        lien = PaymentLink.objects.get(token=r.data['token'])
        self.assertEqual(lien.montant_a_payer, Decimal('90000.00'))

    def test_lien_refuse_si_exigible_nul(self):
        from apps.ventes.models import PaymentLink
        self._payer('90000')
        r = self._lien()
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn("Rien d'exigible maintenant", r.data['detail'])
        self.assertFalse(PaymentLink.objects.filter(
            facture=self.facture).exists())

    def test_lettre_relance_exigible(self):
        with patch('apps.ventes.utils.pdf._html_to_pdf',
                   return_value=b'%PDF-1.4 test') as rendu:
            r = self.api.get(
                f'/api/django/ventes/factures/{self.facture.id}/'
                'lettre-relance-pdf/')
        self.assertEqual(r.status_code, 200, getattr(r, 'data', r))
        html = rendu.call_args[0][0]
        self.assertIn('90000.00 MAD', html)
        self.assertNotIn('100000.00 MAD', html)

    def test_lettre_relance_facture_payee_400(self):
        from apps.ventes.models import Facture
        Facture.objects.filter(pk=self.facture.pk).update(statut='payee')
        with patch('apps.ventes.utils.pdf._html_to_pdf',
                   return_value=b'%PDF-1.4 test') as rendu:
            r = self.api.get(
                f'/api/django/ventes/factures/{self.facture.id}/'
                'lettre-relance-pdf/')
        self.assertEqual(r.status_code, 400, getattr(r, 'data', r))
        self.assertIn('relance', r.data['detail'])
        self.assertFalse(rendu.called)

    def test_penalites_base_exigible(self):
        from apps.ventes.models import Facture
        attendu = self.niveau.calcul_penalite(Decimal('90000.00'), 20)
        r = self.api.post(
            f'/api/django/ventes/factures/{self.facture.id}/'
            'facturer-penalites/', {}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        penalite = Facture.objects.get(pk=r.data['id'])
        self.assertEqual(penalite.montant_ttc, attendu)
        # Égale au centime la pénalité indicative de la liste des relances.
        lst = self.api.get('/api/django/ventes/relances/')
        self.assertEqual(lst.status_code, 200)
        row = next(x for x in lst.data if x['id'] == self.facture.id)
        self.assertEqual(Decimal(row['niveau']['penalite']), attendu)

"""AFAC25 (C-AFAC-019) — « en retard » se lit sur l'EXIGIBLE : une retenue de
garantie non libérée n'est jamais en retard (jours de retard, encours échu,
tuile « En retard », cash-flow, blocage crédit).

Rejoue la sonde FDOC-12 (`jours_retard 20`, `a_jour False`, échu 100.00,
bucket `en_retard` 100.00, `credit_hold_check bloque=True` sur une facture dont
il ne reste que la retenue). Propriétés, sélecteurs et vue réels, aucun mock.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.facturation.tests.test_afac_retard_exigible"
"""
from datetime import date, timedelta
from decimal import Decimal

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


class RetardExigibleTests(TestCase):
    def setUp(self):
        from apps.crm.models import Client
        from apps.ventes.models import Facture
        from authentication.models import Company
        self.company = Company.objects.create(
            nom='AFAC25 Co', slug=f'afac25-co-{_nxt()}')
        self.admin = User.objects.create_user(
            username=f'afac25_admin_{_nxt()}', password='x',
            role_legacy='admin', company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Retenue', prenom='AFAC25',
            email=f'afac25-{_nxt()}@example.invalid')
        ttc = Decimal('1000')
        self.facture = Facture.objects.create(
            company=self.company, reference=f'FAC-AFAC25-{_nxt()}',
            client=self.client_obj, statut='emise', taux_tva=Decimal('20'),
            montant_ht=ttc / Decimal('1.2'), montant_tva=ttc / Decimal('6'),
            montant_ttc=ttc, retenue_garantie_mad=Decimal('100'),
            date_echeance=timezone.now().date() - timedelta(days=20))

    def _payer(self, montant):
        from apps.ventes.models import Paiement
        Paiement.objects.create(
            company=self.company, facture=self.facture,
            montant=Decimal(montant), date_paiement=date(2026, 10, 1),
            mode='virement', created_by=self.admin)

    def _recharger(self):
        from apps.ventes.models import Facture
        return Facture.objects.get(pk=self.facture.pk)

    def test_retenue_seule_pas_en_retard(self):
        self._payer('900')
        self.assertEqual(self._recharger().jours_retard, 0)

    def test_encours_echu_exigible(self):
        from apps.ventes.selectors_facturation import etat_recouvrement_client
        self._payer('900')
        etat = etat_recouvrement_client(self.company, self.client_obj.id)
        self.assertTrue(etat['a_jour'])
        self.assertEqual(etat['encours_echu'], Decimal('0'))
        # Contre-épreuve : 800 payés ⇒ 100 exigibles échus, 20 jours.
        from apps.ventes.models import Paiement
        Paiement.objects.filter(facture=self.facture).update(
            montant=Decimal('800'))
        etat = etat_recouvrement_client(self.company, self.client_obj.id)
        self.assertFalse(etat['a_jour'])
        self.assertEqual(etat['encours_echu'], Decimal('100.00'))
        self.assertEqual(self._recharger().jours_retard, 20)

    def test_kpi_en_retard_exigible(self):
        from apps.ventes.models import Facture
        from apps.ventes.selectors_facturation import kpis_factures
        self._payer('900')
        kpis = kpis_factures(Facture.objects.filter(company=self.company))
        self.assertEqual(Decimal(kpis['total_en_retard']), Decimal('0'))
        self.assertEqual(kpis['nb_en_retard'], 0)

    def test_cash_flow_retenue_hors_retard(self):
        self._payer('900')
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')
        r = api.get('/api/django/ventes/insights/cash-flow/')
        self.assertEqual(r.status_code, 200, getattr(r, 'data', r))
        buckets = r.data['buckets']
        self.assertEqual(Decimal(buckets['en_retard']['montant']), Decimal('0'))
        self.assertEqual(Decimal(buckets['sans_echeance']['montant']),
                         Decimal('100.00'))

    def test_credit_hold_ne_bloque_pas_sur_retenue(self):
        from apps.crm.selectors import credit_hold_check
        self._payer('900')
        self.assertFalse(
            credit_hold_check(self.client_obj, retard_jours_seuil=10)['bloque'])
        from apps.ventes.models import Paiement
        Paiement.objects.filter(facture=self.facture).update(
            montant=Decimal('800'))
        self.assertTrue(
            credit_hold_check(self.client_obj, retard_jours_seuil=10)['bloque'])

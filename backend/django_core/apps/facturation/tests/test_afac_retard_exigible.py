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


class EcheanceEffectiveTests(TestCase):
    """AFAC48 (C-AFAC-038) — une facture sans ``date_echeance`` a UNE
    échéance effective (émission + 30 j) lue par la bascule en retard,
    ``jours_retard``, la liste des relances, la balance âgée et le message ;
    ``emettre_facture`` pose l'échéance. Rejoue FREC-6 (EN_RETARD mais
    ``jours_retard 0``, niveau null, « Retard de 0 jours »). Émission
    historique à J-61 : 31 jours de retard, tranche 31-60 (à J-60 la
    facture aurait 30 jours, tranche 0-30 de la balance)."""

    def setUp(self):
        from apps.crm.models import Client
        from apps.ventes.models import FollowupLevel
        from authentication.models import Company
        self.company = Company.objects.create(
            nom='AFAC48 Co', slug=f'afac48-co-{_nxt()}')
        self.admin = User.objects.create_user(
            username=f'afac48_admin_{_nxt()}', password='x',
            role_legacy='admin', company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Sans delai', prenom='AFAC48',
            email=f'afac48-{_nxt()}@example.invalid')
        self.niveau = FollowupLevel.objects.create(
            company=self.company, ordre=1, nom='Rappel', delai_jours=7,
            message='Retard de {jours_retard} jours')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')

    def _facture(self, statut='emise', **champs):
        from apps.ventes.models import Facture, LigneFacture
        from apps.stock.models import Produit
        facture = Facture.objects.create(
            company=self.company, reference=f'FAC-AFAC48-{_nxt()}',
            client=self.client_obj, statut=statut, taux_tva=Decimal('20'),
            **champs)
        produit = Produit.objects.create(
            company=self.company, nom='Onduleur', sku=f'AFAC48-{_nxt()}',
            prix_vente=Decimal('1000'), quantite_stock=10)
        LigneFacture.objects.create(
            facture=facture, produit=produit, designation='Onduleur',
            quantite=Decimal('1'), prix_unitaire=Decimal('1000'),
            taux_tva=Decimal('20'))
        return facture

    def _historique(self):
        from apps.ventes.models import Facture
        facture = self._facture()
        Facture.objects.filter(pk=facture.pk).update(
            date_emission=timezone.now().date() - timedelta(days=61))
        return Facture.objects.get(pk=facture.pk)

    def _emettre(self, facture):
        from apps.ventes.models import Facture
        r = self.api.post(
            f'/api/django/ventes/factures/{facture.pk}/emettre/', {},
            format='json')
        self.assertEqual(r.status_code, 200, r.data)
        return Facture.objects.get(pk=facture.pk)

    def test_historique_sans_date_jours_retard(self):
        from apps.ventes.models import Facture
        from apps.ventes.scheduled import check_overdue_factures
        facture = self._historique()
        self.assertEqual(facture.jours_retard, 31)
        check_overdue_factures()
        relue = Facture.objects.get(pk=facture.pk)
        self.assertEqual(relue.statut, Facture.Statut.EN_RETARD)
        self.assertEqual(relue.jours_retard, 31)
        # Aucune écriture rétroactive d'échéance sur l'historique.
        self.assertIsNone(relue.date_echeance)

    def test_liste_balance_message_coherents(self):
        from apps.ventes.recouvrement import rendre_message_relance
        facture = self._historique()
        r = self.api.get('/api/django/ventes/relances/')
        self.assertEqual(r.status_code, 200, r.data)
        ligne = next(x for x in r.data if x['id'] == facture.id)
        self.assertEqual(ligne['jours_retard'], 31)
        self.assertIsNotNone(ligne['niveau'])
        r = self.api.get('/api/django/ventes/balance-agee/')
        self.assertEqual(r.status_code, 200, r.data)
        entree = next(x for x in r.data
                      if x['client_id'] == self.client_obj.id)
        self.assertEqual(Decimal(entree['b31_60']), Decimal('1200.00'))
        self.assertEqual(Decimal(entree['b0_30']), Decimal('0'))
        self.assertEqual(rendre_message_relance(self.niveau, facture),
                         'Retard de 31 jours')

    def test_emission_pose_echeance(self):
        relue = self._emettre(self._facture(statut='brouillon'))
        # CLAUSE PERSISTANCE — l'échéance appliquée est posée en base.
        self.assertEqual(relue.date_echeance,
                         relue.date_emission + timedelta(days=30))

    def test_echeance_saisie_preservee(self):
        saisie = timezone.localdate() + timedelta(days=45)
        relue = self._emettre(
            self._facture(statut='brouillon', date_echeance=saisie))
        self.assertEqual(relue.date_echeance, saisie)

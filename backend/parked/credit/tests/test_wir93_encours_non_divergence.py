"""WIR93 — non-divergence des DEUX moteurs de limite/hold crédit.

Décision consignée en tête de ``apps/credit/services.py`` : coexistence
documentée, avec UN SEUL écart d'assiette autorisé (les factures
``brouillon``, comptées par ``apps.credit`` et pas par FG41/XFAC28).

Ce test verrouille ce contrat :
  1. sans facture ``brouillon``, les deux moteurs donnent le MÊME encours au
     centime (payées et annulées exclues des deux côtés) ;
  2. avec une facture ``brouillon``, l'écart vaut EXACTEMENT son reste dû —
     ``divergent`` reste ``False`` ;
  3. non-régression des deux chemins de décision : ``verifier_hold_credit``
     (apps.credit) et ``verifier_credit_hold`` (apps.ventes) gardent leur
     comportement d'origine sur la même donnée.

Run :
    docker compose exec django_core python manage.py test \
        apps.credit.tests.test_wir93_encours_non_divergence -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.credit.models import LimiteCredit
from apps.crm.models import Client
from apps.ventes.models import Facture

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


def make_company(slug='wir93-co', nom='WIR93 Co'):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class WIR93EncoursNonDivergenceTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='wir93_admin', password='x', role_legacy='admin',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Divergence', prenom='Zéro',
            email='wir93@example.com', plafond_credit=Decimal('1000'))
        # Assiette commune aux deux moteurs : émise + en retard.
        self._facture('9001', Facture.Statut.EMISE, '2000')
        self._facture('9002', Facture.Statut.EN_RETARD, '500')
        # Exclues des DEUX côtés (payée / annulée).
        self._facture('9003', Facture.Statut.PAYEE, '300')
        self._facture('9004', Facture.Statut.ANNULEE, '400')

    def _facture(self, suffixe, statut, montant):
        return Facture.objects.create(
            company=self.company, reference=f'FAC-{MONTH}-{suffixe}',
            client=self.client_obj, statut=statut,
            montant_ttc=Decimal(montant), created_by=self.user)

    # ── 1. Assiette commune : aucun écart ────────────────────────────────
    def test_encours_identique_sans_brouillon(self):
        from apps.credit.services import ecart_encours_moteurs

        res = ecart_encours_moteurs(self.client_obj)
        self.assertEqual(res['encours_credit'], Decimal('2500'))
        self.assertEqual(res['encours_ventes'], Decimal('2500'))
        self.assertEqual(res['ecart'], Decimal('0'))
        self.assertEqual(res['ecart_attendu'], Decimal('0'))
        self.assertFalse(res['divergent'])

    # ── 2. Seul écart autorisé : les brouillons ──────────────────────────
    def test_seul_ecart_autorise_est_le_brouillon(self):
        from apps.credit.services import ecart_encours_moteurs

        self._facture('9005', Facture.Statut.BROUILLON, '700')
        res = ecart_encours_moteurs(self.client_obj)
        self.assertEqual(res['encours_credit'], Decimal('3200'))
        self.assertEqual(res['encours_ventes'], Decimal('2500'))
        self.assertEqual(res['ecart'], Decimal('700'))
        self.assertEqual(res['ecart_attendu'], Decimal('700'))
        # Écart entièrement expliqué → pas de divergence.
        self.assertFalse(res['divergent'])

    # ── 3a. Non-régression moteur A (apps.credit / NTCRD6) ───────────────
    def test_non_regression_verifier_hold_credit(self):
        from apps.credit.services import verifier_hold_credit

        LimiteCredit.objects.create(
            company=self.company, client=self.client_obj,
            montant_limite=Decimal('1000'),
            mode_hold=LimiteCredit.ModeHold.BLOCAGE)
        res = verifier_hold_credit(self.client_obj, Decimal('0'))
        # Encours 2500 > limite 1000 → bloqué, dépassement 1500.
        self.assertFalse(res['autorise'])
        self.assertEqual(res['depassement'], Decimal('1500'))
        self.assertEqual(res['disponible'], Decimal('-1500'))

    # ── 3b. Non-régression moteur B (ventes / FG41-XFAC28) ───────────────
    def test_non_regression_verifier_credit_hold_ventes(self):
        from apps.parametres.models import CompanyProfile
        from apps.ventes.services import CreditHoldError, verifier_credit_hold

        profile = CompanyProfile.get(company=self.company)

        # Flag OFF → strictement no-op (comportement FG41 intact).
        profile.credit_hold_actif = False
        profile.save(update_fields=['credit_hold_actif'])
        self.assertIsNone(verifier_credit_hold(self.client_obj))

        # Flag ON + encours 2500 > plafond 1000 → blocage dur.
        profile.credit_hold_actif = True
        profile.save(update_fields=['credit_hold_actif'])
        with self.assertRaises(CreditHoldError):
            verifier_credit_hold(self.client_obj)

        # L'override responsable passe toujours.
        self.assertIsNone(verifier_credit_hold(
            self.client_obj, override=True, user=self.user,
            contexte='test WIR93'))

    # ── 3c. Un brouillon ne change PAS la décision côté ventes ───────────
    def test_brouillon_ne_change_pas_la_decision_ventes(self):
        from apps.crm.selectors import client_credit_warning

        avant = client_credit_warning(self.client_obj)['encours']
        self._facture('9006', Facture.Statut.BROUILLON, '9999')
        apres = client_credit_warning(self.client_obj)['encours']
        self.assertEqual(avant, apres)

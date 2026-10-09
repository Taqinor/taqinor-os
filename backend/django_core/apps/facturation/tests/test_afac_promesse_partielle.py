"""AFAC49 (C-AFAC-039, D-AFAC-C10 option a) — une promesse de paiement est
« tenue » dès que les encaissements VALIDES reçus depuis sa création
atteignent ``montant_promis``, même si un solde reste dû ; sinon « rompue » à
la date dépassée (un paiement rejeté ne compte pas).

Rejoue la sonde FREC-7 (promesse 30 000, paiement 30 000, dû 70 000 ⇒
`rompue`, exclusion levée). Beat réel (`relance_reminders`), aucun mock.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.facturation.tests.test_afac_promesse_partielle"
"""
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase, override_settings

_CTR = [0]


def _nxt():
    _CTR[0] += 1
    return _CTR[0]


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class PromessePartielleTests(TestCase):
    def setUp(self):
        from apps.crm.models import Client
        from apps.ventes.scheduled import casablanca_today
        from authentication.models import Company
        self.today = casablanca_today()
        n = _nxt()
        self.company = Company.objects.create(
            nom=f'AFAC49 {n}', slug=f'afac49-{n}')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Promesse', prenom='AFAC49',
            email=f'afac49-{n}@example.invalid')

    def _facture(self, ttc=Decimal('100000')):
        from apps.ventes.models import Facture
        return Facture.objects.create(
            company=self.company, reference=f'FAC-AFAC49-{_nxt():04d}',
            client=self.client_obj, statut=Facture.Statut.EN_RETARD,
            taux_tva=Decimal('20'), montant_ht=ttc / Decimal('1.2'),
            montant_tva=ttc / Decimal('6'), montant_ttc=ttc,
            date_echeance=self.today - timedelta(days=40),
            exclu_relances_jusquau=self.today - timedelta(days=1))

    def _promesse(self, facture, montant='30000'):
        from apps.ventes.models import PromessePaiement
        return PromessePaiement.objects.create(
            company=self.company, facture=facture,
            montant_promis=Decimal(montant),
            date_promise=self.today - timedelta(days=1))

    def _payer(self, facture, montant, rejete=False):
        from apps.ventes.models import Paiement
        return Paiement.objects.create(
            company=self.company, facture=facture, montant=Decimal(montant),
            date_paiement=self.today, mode=Paiement.Mode.VIREMENT,
            statut=(Paiement.Statut.REJETE if rejete
                    else Paiement.Statut.ENCAISSE))

    def _statut(self, promesse):
        return type(promesse).objects.get(pk=promesse.pk).statut

    def test_promesse_partielle_payee_tenue(self):
        from apps.ventes.models import PromessePaiement
        from apps.ventes.scheduled import relance_reminders
        f = self._facture()
        p = self._promesse(f)
        self._payer(f, '30000')
        relance_reminders()
        self.assertEqual(self._statut(p), PromessePaiement.Statut.TENUE)
        # CLAUSE PERSISTANCE : la rupture n'a pas levé l'exclusion.
        f.refresh_from_db()
        self.assertEqual(f.exclu_relances_jusquau,
                         self.today - timedelta(days=1))

    def test_promesse_insuffisante_rompue_rejet_exclu(self):
        from apps.ventes.models import PromessePaiement
        from apps.ventes.scheduled import relance_reminders
        f = self._facture()
        p = self._promesse(f)
        self._payer(f, '10000')
        self._payer(f, '30000', rejete=True)
        relance_reminders()
        self.assertEqual(self._statut(p), PromessePaiement.Statut.ROMPUE)

    def test_promesse_facture_soldee_tenue(self):
        from apps.ventes.models import PromessePaiement
        from apps.ventes.scheduled import _check_promesses_expirees
        f = self._facture(ttc=Decimal('1200'))
        p = self._promesse(f, montant='5000')
        self._payer(f, '1200')
        _check_promesses_expirees(self.today)
        self.assertEqual(self._statut(p), PromessePaiement.Statut.TENUE)

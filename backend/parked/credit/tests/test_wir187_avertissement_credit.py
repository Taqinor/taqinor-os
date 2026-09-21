"""WIR187 — `selectors.avertissement_credit` : l'AVERTISSEMENT crédit, en
lecture pure, sous la forme exacte servie par l'acceptation d'un devis.

POURQUOI IL NE DÉLÈGUE PAS à ``services.verifier_hold_credit``, qui renvoie
pourtant déjà ces trois clés : ``credit.services`` importe ``apps.audit`` ; un
appelant de ``ventes`` (l'action `accepter`) tirerait donc la chaîne
``ventes → credit.services → audit``, exactement la back-edge que le contrat
import-linter « Business-core ventes never imports the audit satellite » (M4)
interdit — vérifié : `lint-imports` rougit sur la version déléguée.

Ce module verrouille l'ÉQUIVALENCE des deux chemins : le sélecteur recalcule
``mode``/``depassement``/``disponible``, qui ne dépendent que de la limite
active et de l'encours (la tolérance NTCRD30, les dérogations NTCRD9 et le
bypass de rôle NTCRD31 n'influencent que ``autorise``, non rendu ici). Si l'un
des deux chemins dérive, ce test rougit. Ce test vit dans `apps.credit` —
importer `credit.services` depuis un test de `ventes` rejouerait la back-edge.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company
from apps.credit.models import LimiteCredit
from apps.credit.selectors import avertissement_credit
from apps.credit.services import verifier_hold_credit
from apps.crm.models import Client
from apps.ventes.models import Facture

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


class AvertissementCreditTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='wir187-cred', defaults={'nom': 'WIR187 Crédit'})
        self.user = User.objects.create_user(
            username='wir187-cred-user', password='x',
            role_legacy='responsable', company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='WIR187C',
            email='wir187c@example.com', telephone='+212600018702')

    def _encours(self, montant, suffixe='A'):
        Facture.objects.create(
            company=self.company, reference=f'FAC-{MONTH}-W187C{suffixe}',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            montant_ttc=Decimal(montant), created_by=self.user)

    def test_sans_limite_rien_a_signaler(self):
        etat = avertissement_credit(self.client_obj, Decimal('5000'))
        self.assertEqual(etat['mode'], LimiteCredit.ModeHold.AUCUN)
        self.assertEqual(etat['depassement'], Decimal('0'))
        self.assertIsNone(etat['disponible'])

    def test_depassement_jamais_negatif(self):
        LimiteCredit.objects.create(
            company=self.company, client=self.client_obj,
            montant_limite=Decimal('50000'),
            mode_hold=LimiteCredit.ModeHold.AVERTISSEMENT)
        etat = avertissement_credit(self.client_obj, Decimal('1000'))
        self.assertEqual(etat['depassement'], Decimal('0'))
        self.assertEqual(etat['disponible'], Decimal('50000'))

    def test_les_trois_modes_sont_rendus_tels_quels(self):
        limite = LimiteCredit.objects.create(
            company=self.company, client=self.client_obj,
            montant_limite=Decimal('10000'),
            mode_hold=LimiteCredit.ModeHold.AUCUN)
        for mode in (LimiteCredit.ModeHold.AUCUN,
                     LimiteCredit.ModeHold.AVERTISSEMENT,
                     LimiteCredit.ModeHold.BLOCAGE):
            limite.mode_hold = mode
            limite.save(update_fields=['mode_hold'])
            self.assertEqual(
                avertissement_credit(self.client_obj, Decimal('1'))['mode'],
                mode)

    def test_accord_exact_avec_verifier_hold_credit(self):
        LimiteCredit.objects.create(
            company=self.company, client=self.client_obj,
            montant_limite=Decimal('10000'),
            mode_hold=LimiteCredit.ModeHold.BLOCAGE)
        self._encours('9000')
        for montant in (Decimal('0'), Decimal('500'), Decimal('5000')):
            etat = avertissement_credit(self.client_obj, montant)
            verdict = verifier_hold_credit(
                self.client_obj, montant_transaction=montant)
            self.assertEqual(etat['mode'], verdict['mode'], montant)
            self.assertEqual(
                etat['depassement'], verdict['depassement'], montant)
            self.assertEqual(
                etat['disponible'], verdict['disponible'], montant)

    def test_accord_sans_limite_aussi(self):
        etat = avertissement_credit(self.client_obj, Decimal('1000'))
        verdict = verifier_hold_credit(
            self.client_obj, montant_transaction=Decimal('1000'))
        self.assertEqual(etat['mode'], verdict['mode'])
        self.assertEqual(etat['depassement'], verdict['depassement'])
        self.assertEqual(etat['disponible'], verdict['disponible'])

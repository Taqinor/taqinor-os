"""WIR187 (reprend NTCRD7/8) — l'acceptation d'un devis renvoie l'état crédit.

Le module `apps.credit` calculait déjà tout (limite, encours, mode de hold,
tolérance de dépassement) mais l'écran de vente n'en voyait RIEN : un commercial
pouvait faire signer un client au-delà de sa limite sans que rien ne le dise.

La réponse de `POST /ventes/devis/<id>/accepter/` porte désormais
`credit_warning {mode, depassement, disponible}`, calculé par
`apps.credit.selectors.avertissement_credit` (lecture pure) et figé par le
contrat committé `apps/credit/contract_samples/credit_warning.json`.

C'est un AVERTISSEMENT, jamais un verdict : le refus dur reste
`ventes.services.verifier_credit_hold` (XFAC28), appliqué AVANT.

Couvre : les trois modes société (aucun / avertissement / blocage), le client
sans limite, la forme EXACTE de l'exemple de contrat, et le fait que le crédit
ne casse jamais une acceptation.
"""
import json
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.credit.models import LimiteCredit
from apps.crm.models import Client
from apps.ventes.models import Devis, Facture, LigneDevis

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')
ECHANTILLON = (Path(__file__).resolve().parents[2]
               / 'credit' / 'contract_samples' / 'credit_warning.json')


def _contrat(variante='exemple'):
    return json.loads(ECHANTILLON.read_text(encoding='utf-8'))[variante]


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class _Base(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='wir187-co', defaults={'nom': 'WIR187 Co'})
        self.user = User.objects.create_user(
            username='wir187-resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = auth(self.user)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='WIR187',
            email='wir187@example.com', telephone='+212600018701')

    def _devis(self, num=1, montant='30000'):
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-W187{num}',
            client=self.client_obj, statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('0'))
        LigneDevis.objects.create(
            devis=devis, designation='Installation', quantite=Decimal('1'),
            prix_unitaire=Decimal(montant), remise=Decimal('0'))
        devis.refresh_from_db()
        return devis

    def _encours(self, montant):
        """Encours réel du client : une facture ÉMISE (le sélecteur crédit ne
        compte que les factures ouvertes)."""
        Facture.objects.create(
            company=self.company, reference=f'FAC-{MONTH}-W187',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            montant_ttc=Decimal(montant), created_by=self.user)

    def _accepter(self, devis):
        return self.api.post(
            f'/api/django/ventes/devis/{devis.pk}/accepter/',
            {'nom': 'Client WIR187'}, format='json')


class CreditWarningTests(_Base):
    def test_client_sans_limite_mode_aucun(self):
        devis = self._devis()
        resp = self._accepter(devis)
        self.assertEqual(resp.status_code, 200, resp.data)
        warning = resp.data['credit_warning']
        self.assertEqual(warning['mode'], 'aucun')
        self.assertIsNone(warning['disponible'])
        self.assertEqual(Decimal(warning['depassement']), Decimal('0'))

    def test_mode_aucun_sur_une_limite_sans_hold(self):
        LimiteCredit.objects.create(
            company=self.company, client=self.client_obj,
            montant_limite=Decimal('100000'),
            mode_hold=LimiteCredit.ModeHold.AUCUN)
        resp = self._accepter(self._devis(num=2))
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['credit_warning']['mode'], 'aucun')

    def test_mode_avertissement_signale_le_depassement(self):
        LimiteCredit.objects.create(
            company=self.company, client=self.client_obj,
            montant_limite=Decimal('10000'),
            mode_hold=LimiteCredit.ModeHold.AVERTISSEMENT)
        self._encours('9000')
        resp = self._accepter(self._devis(num=3, montant='5000'))
        # L'avertissement ne bloque JAMAIS : l'acceptation passe.
        self.assertEqual(resp.status_code, 200, resp.data)
        warning = resp.data['credit_warning']
        self.assertEqual(warning['mode'], 'avertissement')
        # Disponible AVANT la transaction : 10 000 − 9 000.
        self.assertEqual(Decimal(warning['disponible']), Decimal('1000'))
        # Dépassement APRÈS : (9 000 + 5 000) − 10 000.
        self.assertEqual(Decimal(warning['depassement']), Decimal('4000'))

    def test_mode_blocage_est_signale_quand_l_acceptation_passe(self):
        # Sous la limite : la garde XFAC28 laisse passer, et l'avertissement
        # dit bien que la société est en mode blocage.
        LimiteCredit.objects.create(
            company=self.company, client=self.client_obj,
            montant_limite=Decimal('100000'),
            mode_hold=LimiteCredit.ModeHold.BLOCAGE)
        resp = self._accepter(self._devis(num=4, montant='1000'))
        self.assertEqual(resp.status_code, 200, resp.data)
        warning = resp.data['credit_warning']
        self.assertEqual(warning['mode'], 'blocage')
        self.assertEqual(Decimal(warning['depassement']), Decimal('0'))
        self.assertEqual(Decimal(warning['disponible']), Decimal('100000'))

    def test_aucun_depassement_negatif(self):
        LimiteCredit.objects.create(
            company=self.company, client=self.client_obj,
            montant_limite=Decimal('50000'),
            mode_hold=LimiteCredit.ModeHold.AVERTISSEMENT)
        resp = self._accepter(self._devis(num=5, montant='1000'))
        self.assertGreaterEqual(
            Decimal(resp.data['credit_warning']['depassement']), Decimal('0'))

    # ── PACT10 — la forme EXACTE de l'exemple committé ──────────────────────
    def test_forme_identique_a_l_exemple_de_contrat(self):
        LimiteCredit.objects.create(
            company=self.company, client=self.client_obj,
            montant_limite=Decimal('10000'),
            mode_hold=LimiteCredit.ModeHold.AVERTISSEMENT)
        self._encours('9000')
        resp = self._accepter(self._devis(num=6, montant='5000'))
        self.assertEqual(
            sorted(resp.data['credit_warning'].keys()),
            sorted(_contrat().keys()))

    def test_les_trois_variantes_du_contrat_ont_la_meme_forme(self):
        reference = sorted(_contrat().keys())
        for variante in ('exemple', 'exemple_avertissement', 'exemple_sans_limite'):
            self.assertEqual(sorted(_contrat(variante).keys()), reference, variante)
        self.assertIsNone(_contrat('exemple_sans_limite')['disponible'])

    def test_toujours_present_sur_une_acceptation_reussie(self):
        # Un écran n'a jamais à deviner l'absence de la clé.
        resp = self._accepter(self._devis(num=7))
        self.assertIn('credit_warning', resp.data)


class SelectorTests(_Base):
    def test_le_selector_ne_leve_pas_sans_limite(self):
        from apps.credit.selectors import avertissement_credit

        etat = avertissement_credit(self.client_obj, Decimal('1000'))
        self.assertEqual(
            sorted(etat.keys()), ['depassement', 'disponible', 'mode'])
        self.assertEqual(etat['mode'], 'aucun')
        self.assertIsNone(etat['disponible'])

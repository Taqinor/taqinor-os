"""WIR187 (reprend NTCRD7/8) — `credit_warning` sur l'acceptation d'un devis.

``apps.credit`` savait calculer un disponible et un mode de hold, mais AUCUN
chemin d'écriture ne le montrait au vendeur : NTCRD7/8 étaient bloqués « hors
périmètre » côté domaine. L'acceptation d'un devis renvoie désormais, EN PLUS
du devis, la clé ``credit_warning`` — trois clés, jamais plus, exactement
celles committées dans ``apps/credit/contract_samples/credit_warning.json``.

Le contrat est AFFIRMÉ contre le fichier committé (PACT10) : si le serveur
change de forme, ce test rougit — c'est le lien qui manquait le 03/08/2026.

Run :
    docker compose exec django_core python manage.py test \
        apps.credit.tests.test_wir187_credit_warning_acceptation -v 2
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
from apps.credit.models import LimiteCredit, ReglageCredit
from apps.credit.selectors import credit_warning
from apps.crm.models import Client
from apps.ventes.models import Devis, Facture, LigneDevis

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')

ECHANTILLON = (
    Path(__file__).resolve().parents[1]
    / 'contract_samples' / 'credit_warning.json'
)


def _auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class CreditWarningContratTests(TestCase):
    """Le contrat committé EST la forme réellement servie."""

    def test_les_cles_du_selecteur_sont_celles_du_contrat(self):
        document = json.loads(ECHANTILLON.read_text(encoding='utf-8'))
        self.assertEqual(
            set(document['exemple']), {'mode', 'depassement', 'disponible'})
        # Chaque variante publie les MÊMES clés (un autre ÉTAT, jamais une
        # autre FORME).
        for cle, exemple in document.items():
            if cle.startswith('exemple'):
                self.assertEqual(set(exemple), set(document['exemple']), cle)


class CreditWarningTroisModesTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            slug='wir187-co', nom='WIR187 Co')
        self.user = User.objects.create_user(
            username='wir187_vendeur', password='x', role_legacy='admin',
            company=self.company)
        self.api = _auth(self.user)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Bennani', prenom='Karim',
            email='wir187@example.com')
        # Encours réel : une facture émise de 8 000 (assiette NTCRD4).
        Facture.objects.create(
            company=self.company, reference=f'FAC-{MONTH}-W187',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            montant_ttc=Decimal('8000'), created_by=self.user)

    def _devis(self, suffixe, montant='5000'):
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-{suffixe}',
            client=self.client_obj, statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('0'), created_by=self.user)
        LigneDevis.objects.create(
            devis=devis, designation='Kit PV', quantite=1,
            prix_unitaire=Decimal(montant))
        return devis

    def _limite(self, montant, mode):
        LimiteCredit.objects.update_or_create(
            company=self.company, client=self.client_obj,
            defaults={'montant_limite': Decimal(montant), 'mode_hold': mode,
                      'actif': True})

    def _accepter(self, devis):
        return self.api.post(
            f'/api/django/ventes/devis/{devis.id}/accepter/',
            {'nom': 'Karim Bennani'}, format='json')

    # ── Mode « aucun » : rien n'est signalé ──────────────────────────────
    def test_mode_aucun_ne_signale_aucun_depassement(self):
        self._limite('1000', LimiteCredit.ModeHold.AUCUN)
        resp = self._accepter(self._devis('W1871'))
        self.assertEqual(resp.status_code, 200, resp.data)
        warning = resp.data['credit_warning']
        self.assertEqual(warning['mode'], 'aucun')
        self.assertFalse(warning['depassement'])

    # ── Mode « avertissement » : dépassement signalé, action passée ──────
    def test_mode_avertissement_signale_le_depassement(self):
        self._limite('10000', LimiteCredit.ModeHold.AVERTISSEMENT)
        devis = self._devis('W1872', montant='5000')
        resp = self._accepter(devis)
        self.assertEqual(resp.status_code, 200, resp.data)
        warning = resp.data['credit_warning']
        self.assertEqual(warning['mode'], 'avertissement')
        # Disponible 2 000 < TTC 5 000 → dépassement.
        self.assertTrue(warning['depassement'])
        self.assertEqual(Decimal(str(warning['disponible'])), Decimal('2000'))
        # L'acceptation a bien eu lieu : l'avertissement n'est PAS un blocage.
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.ACCEPTE)

    def test_sous_la_limite_aucun_depassement(self):
        self._limite('50000', LimiteCredit.ModeHold.AVERTISSEMENT)
        resp = self._accepter(self._devis('W1873', montant='5000'))
        self.assertFalse(resp.data['credit_warning']['depassement'])

    # ── Mode « blocage » : signalé aussi (le blocage dur est ailleurs) ───
    def test_mode_blocage_signale_le_depassement(self):
        self._limite('5000', LimiteCredit.ModeHold.BLOCAGE)
        resp = self._accepter(self._devis('W1874', montant='5000'))
        self.assertEqual(resp.status_code, 200, resp.data)
        warning = resp.data['credit_warning']
        self.assertEqual(warning['mode'], 'blocage')
        self.assertTrue(warning['depassement'])

    # ── Réglages société : mode hérité quand la limite n'en porte pas ────
    def test_sans_limite_client_aucun_avertissement_illimite(self):
        resp = self._accepter(self._devis('W1875'))
        warning = resp.data['credit_warning']
        self.assertIsNone(warning['disponible'])
        self.assertFalse(warning['depassement'])

    def test_mode_herite_du_reglage_societe(self):
        ReglageCredit.objects.update_or_create(
            company=self.company,
            defaults={'mode_hold_defaut': LimiteCredit.ModeHold.BLOCAGE})
        # Limite SANS mode explicite : le sélecteur retombe sur la société.
        limite = LimiteCredit.objects.create(
            company=self.company, client=self.client_obj,
            montant_limite=Decimal('10000'), actif=True)
        LimiteCredit.objects.filter(pk=limite.pk).update(mode_hold='')
        warning = credit_warning(
            self.client_obj, montant_ttc_nouveau=Decimal('5000'))
        self.assertEqual(warning['mode'], 'blocage')

    def test_selecteur_nest_jamais_bloquant_et_necrit_rien(self):
        self._limite('1000', LimiteCredit.ModeHold.BLOCAGE)
        avant = LimiteCredit.objects.get(client=self.client_obj).montant_limite
        credit_warning(self.client_obj, montant_ttc_nouveau=Decimal('99999'))
        apres = LimiteCredit.objects.get(client=self.client_obj).montant_limite
        self.assertEqual(avant, apres)

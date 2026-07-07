"""XMKT15 — Conformité SMS Maroc : comptage, coût, sender-ID, STOP.

Couvre : compteur GSM-7/UCS-2 + segments + coût direct, un numéro fixe/
invalide est exclu avec motif, mention STOP ajoutée automatiquement, STOP
entrant désinscrit, tests.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.compta import services
from apps.marketing.models import Campagne

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


class SegmentsSmsTests(TestCase):
    def test_gsm7_court_un_segment(self):
        info = services.compter_segments_sms('Bonjour, offre speciale!')
        self.assertEqual(info['encodage'], 'gsm7')
        self.assertEqual(info['nb_segments'], 1)

    def test_gsm7_long_plusieurs_segments(self):
        texte = 'A' * 200
        info = services.compter_segments_sms(texte)
        self.assertEqual(info['encodage'], 'gsm7')
        self.assertEqual(info['nb_segments'], 2)  # 200 / 153 → 2 segments

    def test_ucs2_pour_caracteres_arabes(self):
        info = services.compter_segments_sms('عرض خاص اليوم')
        self.assertEqual(info['encodage'], 'ucs2')
        self.assertEqual(info['nb_segments'], 1)

    def test_vide_zero_segment(self):
        info = services.compter_segments_sms('')
        self.assertEqual(info['nb_segments'], 0)


class CoutSmsTests(TestCase):
    def test_cout_avec_prix_par_defaut(self):
        estimation = services.estimer_cout_sms('Bonjour', nb_destinataires=10)
        self.assertEqual(estimation['nb_segments'], 1)
        self.assertEqual(
            estimation['cout_total_mad'],
            services.SMS_PRIX_MAD_DEFAUT * 10)

    def test_cout_avec_prix_personnalise(self):
        estimation = services.estimer_cout_sms(
            'Bonjour', prix_unitaire_mad=Decimal('0.5'), nb_destinataires=2)
        self.assertEqual(estimation['cout_par_destinataire_mad'], Decimal('0.5'))
        self.assertEqual(estimation['cout_total_mad'], Decimal('1.0'))


class MentionStopTests(TestCase):
    def test_ajoute_si_absente(self):
        corps = services.ajouter_mention_stop('Offre spéciale')
        self.assertIn('STOP', corps)

    def test_najoute_pas_si_deja_presente(self):
        corps = 'Offre. Répondez STOP pour vous désinscrire.'
        self.assertEqual(services.ajouter_mention_stop(corps), corps)


class ValidationNumeroSmsTests(TestCase):
    def test_mobile_valide(self):
        normalise, motif = services.valider_numero_sms('0612345678')
        self.assertEqual(normalise, '212612345678')
        self.assertEqual(motif, '')

    def test_fixe_exclu(self):
        normalise, motif = services.valider_numero_sms('0522123456')
        self.assertIsNone(normalise)
        self.assertIn('fixe', motif.lower())

    def test_filtrer_destinataires_sms(self):
        rapport = services.filtrer_destinataires_sms(
            ['0612345678', '0522123456', '07 12 34 56 78'])
        self.assertEqual(len(rapport['valides']), 2)
        self.assertEqual(len(rapport['exclus']), 1)


class StopEntrantTests(TestCase):
    def setUp(self):
        self.co = make_company('xmkt15', 'XMKT15')
        self.user = make_user(self.co, 'xmkt15-user')

    def test_stop_entrant_desinscrit(self):
        services.traiter_stop_entrant(self.co, '0612345678')
        self.assertTrue(services.est_supprime(self.co, '212612345678'))

    def test_webhook_stop_endpoint(self):
        api = APIClient()
        resp = api.post('/api/django/compta/webhooks/sms-stop/', {
            'company_id': self.co.id, 'numero': '0612345678',
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertTrue(services.est_supprime(self.co, '212612345678'))

    def test_cout_sms_endpoint(self):
        camp = Campagne.objects.create(
            company=self.co, nom='C', canal=Campagne.Canal.SMS,
            corps='Bonjour, offre spéciale !')
        api = auth(self.user)
        resp = api.get(
            f'/api/django/compta/campagnes/{camp.id}/cout-sms/'
            f'?nb_destinataires=5')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data['nb_segments'], 1)

"""APAR37 — un doublon de référentiel répond 400 sous le champ, plus 500.

Constat C-APAR-053 : la société est forcée côté serveur APRÈS la validation
(``core.mixins``) ; le ``UniqueTogetherValidator`` de DRF ne s'appliquait donc
jamais et un doublon (condition de paiement 30 j / fin de mois non /
escompte 0) remontait en 500 ``IntegrityError``.

Le balayage par INTROSPECTION liste chaque sérialiseur de référentiel dont le
modèle porte une contrainte d'unicité incluant ``company``.

Test-du-test : retirer ``UniciteSocieteMixin`` d'un sérialiseur ⇒ 500 ⇒ rouge.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.parametres import serializers_referentiels as sr
from apps.parametres.models_payment_terms import ConditionPaiement
from authentication.models import Company

BASE = '/api/django/parametres/'


class ReferentielsDoublonTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='APAR37', slug='apar37-co')
        self.admin = get_user_model().objects.create_user(
            username='apar37-admin', password='x', company=self.company,
            role_legacy='admin')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')

    def test_condition_doublon_400(self):
        ConditionPaiement.objects.get_or_create(
            company=self.company, delai_jours=30, fin_de_mois=False,
            escompte_pct=Decimal('0'), defaults={'libelle': '30 jours'})
        avant = ConditionPaiement.objects.filter(company=self.company).count()
        r = self.api.post(f'{BASE}conditions-paiement/', {
            'libelle': '30 jours (bis)', 'delai_jours': 30,
            'fin_de_mois': False, 'escompte_pct': '0'}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('delai_jours', r.data)
        self.assertIn('existe déjà', str(r.data['delai_jours']))
        self.assertEqual(
            ConditionPaiement.objects.filter(company=self.company).count(),
            avant)

    def test_code_doublon_400(self):
        for route, corps in (
                ('taux-tva/', {'code': 'apar37', 'libelle': 'T', 'taux': '7'}),
                ('unites-mesure/', {'code': 'apar37', 'libelle': 'U'})):
            with self.subTest(route=route):
                r1 = self.api.post(BASE + route, corps, format='json')
                self.assertEqual(r1.status_code, 201, r1.data)
                r2 = self.api.post(BASE + route, corps, format='json')
                self.assertEqual(r2.status_code, 400, r2.data)
                self.assertIn('code', r2.data)

    def test_introspection_tout_referentiel_a_contrainte_est_garde(self):
        for nom in dir(sr):
            cls = getattr(sr, nom)
            meta = getattr(cls, 'Meta', None)
            modele = getattr(meta, 'model', None)
            if modele is None or not isinstance(cls, type):
                continue
            groupes = [g for g in (modele._meta.unique_together or ())
                       if 'company' in g]
            if groupes:
                with self.subTest(serializer=nom):
                    self.assertTrue(issubclass(cls, sr.UniciteSocieteMixin))

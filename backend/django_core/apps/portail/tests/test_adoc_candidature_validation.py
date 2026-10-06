"""ADOC144 — candidature fournisseur publique : corps validé par un sérialiseur
borné (400 champ par champ) au lieu d'un 500 anonyme.

Constat C-ADOC-056 (S3, plausible — ce test est l'oracle) : le corps brut
était passé à ``stock.services.enregistrer_candidature_fournisseur`` ; un
téléphone de plus de 20 caractères levait un DataError (500), un e-mail
invalide était enregistré, une liste en ``nom`` cassait le ``.strip()``.

Le service stock est appelé TEL QUEL (aucun mock).

Run :
    python manage.py test apps.portail.tests.test_adoc_candidature_validation -v2
"""
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.stock.models import Fournisseur
from authentication.models import Company
from core.models import TenantTheme

URL = '/api/django/portail/fournisseurs/candidature/'
HOTE = 'portail.a.test'


@override_settings(ALLOWED_HOSTS=[HOTE, 'testserver'])
class CandidatureValidationTests(TestCase):
    def setUp(self):
        # Le plafond 10/heure/IP (NTPRT25) vit dans le cache local du process
        # de test : repartir d'un compteur vide (pas un contournement — chaque
        # test n'envoie qu'une ou deux requêtes).
        cache.clear()
        self.company = Company.objects.create(
            slug='adoc144-co-a', nom='ADOC144 A')
        TenantTheme.objects.create(company=self.company, domaine=HOTE)
        self.api = APIClient()

    def _post(self, corps):
        return self.api.post(URL, corps, format='json', HTTP_HOST=HOTE)

    def _aucun_fournisseur(self):
        self.assertFalse(
            Fournisseur.objects.filter(company=self.company).exists())

    def test_telephone_trop_long_400(self):
        r = self._post({'nom': 'X',
                        'telephone': '+212 6 61 23 45 67 / 05 22 00 00 00'})
        self.assertEqual(r.status_code, 400)
        self.assertIn('telephone', r.data)
        self._aucun_fournisseur()

    def test_email_invalide_400(self):
        r = self._post({'nom': 'X', 'email': 'pas-un-email'})
        self.assertEqual(r.status_code, 400)
        self.assertIn('email', r.data)
        self._aucun_fournisseur()

    def test_nom_non_chaine_400(self):
        r = self._post({'nom': ['liste']})
        self.assertEqual(r.status_code, 400)
        self.assertIn('nom', r.data)
        self._aucun_fournisseur()

    def test_rc_et_ice_bornes_comme_le_modele(self):
        r = self._post({'nom': 'X', 'ice': '1' * 21, 'rc': 'R' * 41})
        self.assertEqual(r.status_code, 400)
        self.assertIn('ice', r.data)
        self.assertIn('rc', r.data)
        self._aucun_fournisseur()

    def test_corps_conforme_201_inchange(self):
        r = self._post({'nom': 'Atlas Énergie SARL',
                        'email': 'contact@atlas.invalid',
                        'telephone': '+212522000000',
                        'ice': '001234567000089', 'rc': 'RC-12345'})
        self.assertEqual(r.status_code, 201, r.data)
        f = Fournisseur.objects.get(company=self.company)
        self.assertEqual(f.nom, 'Atlas Énergie SARL')
        self.assertEqual(f.telephone, '+212522000000')
        self.assertEqual(f.statut_validation,
                         Fournisseur.StatutValidation.EN_ATTENTE)

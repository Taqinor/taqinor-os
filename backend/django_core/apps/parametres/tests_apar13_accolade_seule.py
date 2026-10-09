"""APAR13 — une accolade non appariée est refusée à la saisie d'un modèle
d'e-mail, et un modèle déjà en base mal formé ne fait plus lever l'envoi.

Constat C-APAR-016 : la liste blanche ne voyait que les tokens ``{…}``
appariés ; « reste 5 } » ou « Réf {abc » s'enregistraient (200), puis
``EmailTemplate.render`` levait ``ValueError: Single '}'`` à l'envoi du devis
(500 sur ``envoyer-email``).

Test-du-test : retirer le ``except ValueError`` de ``_safe_format`` ⇒
``test_modele_deja_en_base_rendu_brut`` rouge ; retirer
``erreur_de_rendu`` du sérialiseur ⇒ ``test_saisie_refusee`` rouge.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.parametres.models_email import EmailTemplate
from authentication.models import Company

BASE = '/api/django/parametres/email-templates/'


class AccoladeSeuleTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='APAR13', slug='apar13-co')
        self.admin = get_user_model().objects.create_user(
            username='apar13-admin', password='x', company=self.company,
            role_legacy='admin')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')

    def test_saisie_refusee(self):
        for texte in ('reste 5 }', 'Réf {abc'):
            with self.subTest(texte=texte, chemin='bulk'):
                r = self.api.put(f'{BASE}bulk/', {'templates': [
                    {'cle': 'envoi_devis', 'sujet': 'Devis',
                     'corps': texte}]}, format='json')
                self.assertEqual(r.status_code, 400, r.data)
                self.assertIn('corps', r.data)
                self.assertIn('Accolade', str(r.data['corps']))
            with self.subTest(texte=texte, chemin='crud'):
                r = self.api.post(BASE, {
                    'cle': 'envoi_devis', 'sujet': 'Devis', 'corps': texte},
                    format='json')
                self.assertEqual(r.status_code, 400, r.data)
                self.assertIn('corps', r.data)
        self.assertFalse(EmailTemplate.objects.filter(
            company=self.company, cle='envoi_devis').exists())

    def test_modele_deja_en_base_rendu_brut(self):
        EmailTemplate.objects.create(
            company=self.company, cle='envoi_devis', sujet='Devis {reference}',
            corps='Total 5 } — {reference}')
        with self.assertLogs('apps.parametres.models_email', 'WARNING'):
            rendu = EmailTemplate.render(
                self.company, 'envoi_devis', reference='DEV-1', nom='Bonjour,')
        self.assertEqual(rendu['corps'], 'Total 5 } — {reference}')
        self.assertEqual(rendu['sujet'], 'Devis DEV-1')

"""APAR12 — la liste blanche des placeholders de l'écran Messages est DÉRIVÉE
de la source (variables du texte livré ∪ variables fournies par le rendu).

Constat C-APAR-014 : ``_MESSAGE_PLACEHOLDERS`` (dict tenu à la main) ignorait
``rappel_rdv``, ``livraison_en_transit``, ``livraison_livree`` et
``relance_email_j10`` : enregistrer ces modèles TELS QU'ILS SONT LIVRÉS
répondait 400 « Placeholders autorisés : aucun » ; ``{lien_rdv}``, rendu par
``ventes.utils.whatsapp.build_devis_whatsapp``, était refusé sur les devis.

Test-du-test : retirer ``{lien_rdv}`` de ``_VARIABLES_RENDU['devis_unique']``
⇒ ``test_lien_rdv_accepte_devis`` rouge ; ne plus lire les textes livrés dans
``placeholders_autorises`` ⇒ ``test_chaque_cle_livree_aller_retour`` nomme la
clé.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.parametres.models import (
    MESSAGE_TEMPLATE_DEFAULTS, MESSAGE_TEMPLATE_DEFAULTS_DARIJA,
    MessageTemplate,
)
from authentication.models import Company

URL = '/api/django/parametres/messages/'


class PlaceholdersMessagesTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='APAR12', slug='apar12-co')
        self.admin = get_user_model().objects.create_user(
            username='apar12-admin', password='x', company=self.company,
            role_legacy='admin')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')

    def test_chaque_cle_livree_aller_retour(self):
        for cle in MessageTemplate.Cle.values:
            corps_fr = MESSAGE_TEMPLATE_DEFAULTS.get(cle, '')
            corps_darija = MESSAGE_TEMPLATE_DEFAULTS_DARIJA.get(cle, '')
            with self.subTest(cle=cle):
                r = self.api.put(URL, {
                    'cle': cle, 'corps_fr': corps_fr,
                    'corps_darija': corps_darija}, format='json')
                self.assertEqual(r.status_code, 200, (cle, r.data))
                obj = MessageTemplate.objects.get(
                    company=self.company, cle=cle)
                self.assertEqual(obj.corps_fr, corps_fr)
                self.assertEqual(obj.corps_darija, corps_darija)

    def test_lien_rdv_accepte_devis(self):
        for cle in ('devis_unique', 'devis_multi_entete', 'devis_multi_ligne'):
            with self.subTest(cle=cle):
                corps = MESSAGE_TEMPLATE_DEFAULTS[cle] + ' RDV : {lien_rdv}'
                r = self.api.put(URL, {'cle': cle, 'corps_fr': corps},
                                 format='json')
                self.assertEqual(r.status_code, 200, (cle, r.data))

    def test_inconnu_reste_refuse(self):
        r = self.api.put(URL, {
            'cle': 'rappel_rdv', 'corps_fr': 'Bonjour {inconnu}'},
            format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('{inconnu}', r.data['detail'])
        self.assertIn('{reference}', r.data['detail'])  # autorisés nommés
        self.assertFalse(MessageTemplate.objects.filter(
            company=self.company, cle='rappel_rdv').exists())

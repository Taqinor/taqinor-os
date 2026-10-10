"""AGR414 — message « visite de relevé du point d'eau » avec sa liste de
préparation (FR + darija), proposé AVANT le devis agricole.

Contrat partagé : ``apps/crm/contract_samples/lead_message_visite.json``.

Run :
    python manage.py test apps.crm.tests_agr414_message_point_eau -v 2
"""
import hashlib
import json
import re
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm import cadence_messages
from apps.crm.models import Lead
from apps.parametres.models_messages import (
    CLES_RELANCE, MESSAGE_TEMPLATE_DEFAULTS, MESSAGE_TEMPLATE_DEFAULTS_DARIJA,
    MessageTemplate, variante_segment,
)

User = get_user_model()

CLE = 'visite_releve_point_eau'

CONTRAT = json.loads(
    (Path(__file__).resolve().parent / 'contract_samples'
     / 'lead_message_visite.json').read_text(encoding='utf-8'))

#: Les quatre éléments de la liste de préparation (texte de la tâche).
LISTE_FR = (
    "l'accès au puits ou au forage",
    'la plaque de votre pompe actuelle',
    'bouteilles de butane ou de gasoil',
    "l'autorisation de l'Agence du bassin hydraulique (ABH) et le compteur "
    "d'eau, s'ils existent",
)


def _sha(texte):
    return hashlib.sha256(texte.encode('utf-8')).hexdigest()


class TextesDeBase(SimpleTestCase):
    def test_cle_connue_partout(self):
        self.assertIn(CLE, cadence_messages.CLES_MESSAGE_VISITE)
        self.assertIn(CLE, CLES_RELANCE)
        self.assertIn(CLE, {c for c, _ in MessageTemplate.Cle.choices})
        self.assertTrue(MESSAGE_TEMPLATE_DEFAULTS[CLE].strip())
        self.assertTrue(MESSAGE_TEMPLATE_DEFAULTS_DARIJA[CLE].strip())

    def test_la_liste_fixe_de_quatre_elements(self):
        texte = MESSAGE_TEMPLATE_DEFAULTS[CLE]
        for element in LISTE_FR:
            self.assertIn(element, texte)

    def test_la_confirmation_agricole_reprend_la_liste(self):
        texte = variante_segment('visite_confirmation', 'agricole')
        for element in LISTE_FR:
            self.assertIn(element, texte)

    def test_ni_prix_ni_aide_ni_chiffre_ni_prenom(self):
        for texte in (MESSAGE_TEMPLATE_DEFAULTS[CLE],
                      MESSAGE_TEMPLATE_DEFAULTS_DARIJA[CLE]):
            self.assertIsNone(re.search(r'\d', texte))
            for interdit in ('DH', 'MAD', 'prix', 'subvention', 'FDA',
                             'Meryem', 'Reda', 'مريم', 'رضا', 'درهم'):
                self.assertNotIn(interdit, texte)
            self.assertIn('{conseiller}', texte)

    def test_textes_residentiels_identiques_a_l_octet(self):
        self.assertEqual(
            _sha(MESSAGE_TEMPLATE_DEFAULTS['visite_confirmation']),
            _sha("Bonjour, on confirme la visite technique prévue "
                 "{date_visite} chez vous. Le technicien vérifie le toit, la "
                 "charpente et le tableau électrique — prévoyez l'accès au "
                 "compteur. Votre présence est importante : c'est l'occasion "
                 "de répondre à toutes vos questions sur place. En cas "
                 "d'empêchement, répondez-moi ici et on recale le passage. "
                 "— {conseiller}"))
        self.assertIsNone(variante_segment('visite_confirmation',
                                           'residentiel'))
        self.assertIsNone(variante_segment(CLE, 'residentiel'))

    def test_le_contrat_nomme_la_cle(self):
        self.assertIn(CLE, CONTRAT['pourquoi'])
        self.assertIn(CLE, CONTRAT['exemple_erreur_cle']['cle'][0])


class MessagePointEauApi(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='AGR414 Co', slug='agr414-co')
        self.user = User.objects.create_user(
            username='agr414_resp', password='x', role_legacy='responsable',
            company=self.company, first_name='Nadia')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.lead = Lead.objects.create(
            company=self.company, nom='Fellah', prenom='Ahmed',
            type_installation='agricole', telephone='0612345678',
            owner=self.user)
        self.url = f'/api/django/crm/leads/{self.lead.id}/message-visite/'

    def test_cle_point_eau_rend_fr_et_darija_sans_placeholder_vide(self):
        resp = self.api.get(self.url, {'cle': CLE})
        self.assertEqual(resp.status_code, 200, resp.content)
        for champ in ('corps_fr', 'corps_darija'):
            corps = resp.data[champ]
            self.assertTrue(corps.strip())
            self.assertNotIn('{', corps)
            self.assertNotIn('  ', corps)
        self.assertIn('Ahmed', resp.data['corps_fr'])
        for element in LISTE_FR:
            self.assertIn(element, resp.data['corps_fr'])
        self.assertTrue(resp.data['wa_url_fr'].startswith('https://wa.me/'))

    def test_cle_inconnue_400_nommant_le_champ(self):
        resp = self.api.get(self.url, {'cle': 'apres_visite'})
        self.assertEqual(resp.status_code, 400)
        self.assertIn('cle', resp.data)
        self.assertEqual(resp.data['cle'], CONTRAT['exemple_erreur_cle']['cle'])

    def test_texte_personnalise_jamais_remplace(self):
        MessageTemplate.objects.create(
            company=self.company, cle=CLE,
            corps_fr='Texte maison — {conseiller}')
        resp = self.api.get(self.url, {'cle': CLE})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data['corps_fr'].startswith('Texte maison'))

    def test_ouverture_journalisee(self):
        resp = self.api.post(
            f'/api/django/crm/leads/{self.lead.id}/message-visite/ouvert/',
            {'cle': CLE, 'langue': 'darija'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertTrue(
            self.lead.activites.filter(
                body__contains='relevé du point d’eau').exists())

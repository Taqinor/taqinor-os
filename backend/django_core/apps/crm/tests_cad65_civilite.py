"""CAD65 — « Bonjour M. » n'est plus codé en dur : la civilité est une donnée.

Avant : « M. {prenom} » / « السي {prenom} » était écrit en dur dans les textes
de la cadence, et ``_civilite_et_prenom`` posait « M. » / « السي » d'office —
une cliente recevait « Bonjour M. » sur tous les messages.

Done : ``Lead.civilite`` (M./Mme, FACULTATIVE) + ``{civilite}`` dans les
textes ; un lead SANS civilité reçoit la formule NEUTRE (le prénom seul),
jamais un genre supposé. Contrat partagé : ``contract_samples/lead_civilite.json``.
"""
import datetime
import json
import re
from pathlib import Path
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm import horaires
from apps.crm.models import Lead, LeadActivity, RelanceEtape
from apps.crm.services import (_civilite_et_prenom, _placer_civilite,
                               message_pour_etape)
from apps.parametres.models_messages import (MESSAGE_TEMPLATE_DEFAULTS,
                                             MESSAGE_TEMPLATE_DEFAULTS_DARIJA)
from authentication.models import Company

User = get_user_model()

CONTRAT = json.loads(
    (Path(__file__).resolve().parent / 'contract_samples'
     / 'lead_civilite.json').read_text(encoding='utf-8'))

LUNDI = datetime.datetime(2026, 9, 21, 10, 0, tzinfo=horaires.CASABLANCA)


def _lead(civilite=None, prenom='Salma', nom='Idrissi'):
    return SimpleNamespace(civilite=civilite, prenom=prenom, nom=nom)


class CiviliteDonneeTests(SimpleTestCase):
    """La règle, sans base."""

    def test_les_choix_du_modele_sont_ceux_du_contrat(self):
        self.assertEqual(dict(Lead.Civilite.choices), CONTRAT['choix'])

    def test_sans_civilite_aucun_genre_suppose(self):
        self.assertEqual(_civilite_et_prenom(_lead(), 'fr'), ('', 'Salma'))
        self.assertEqual(_civilite_et_prenom(_lead(), 'darija'),
                         ('', 'Salma'))

    def test_la_civilite_saisie_est_rendue_dans_la_langue(self):
        self.assertEqual(_civilite_et_prenom(_lead('Mme'), 'fr'),
                         ('Mme', 'Salma'))
        self.assertEqual(_civilite_et_prenom(_lead('M.'), 'fr'),
                         ('M.', 'Salma'))
        self.assertEqual(_civilite_et_prenom(_lead('Mme'), 'darija'),
                         ('لالة', 'Salma'))
        self.assertEqual(_civilite_et_prenom(_lead('M.'), 'darija'),
                         ('السي', 'Salma'))

    def test_une_valeur_inconnue_ne_part_jamais(self):
        self.assertEqual(_civilite_et_prenom(_lead('Dr'), 'fr')[0], '')

    def test_vide_le_placeholder_part_avec_son_espace(self):
        self.assertEqual(
            _placer_civilite('Bonjour {civilite} {prenom}, merci.', ''),
            'Bonjour {prenom}, merci.')
        self.assertEqual(
            _placer_civilite('السلام عليكم {civilite} {prenom}،', ''),
            'السلام عليكم {prenom}،')
        # Connue : le texte est intact (le rendu la substitue).
        self.assertEqual(
            _placer_civilite('Bonjour {civilite} {prenom}', 'Mme'),
            'Bonjour {civilite} {prenom}')

    def test_aucun_texte_client_ne_code_une_civilite_en_dur(self):
        interdits = re.compile(r'(M\.|Mme|السي|لالة) \{')
        for source in (MESSAGE_TEMPLATE_DEFAULTS,
                       MESSAGE_TEMPLATE_DEFAULTS_DARIJA):
            for cle, texte in source.items():
                with self.subTest(cle=cle):
                    self.assertIsNone(
                        interdits.search(texte or ''),
                        f'{cle} code une civilité en dur — utiliser '
                        '{civilite}.')

    def test_la_salutation_de_la_cadence_porte_le_placeholder(self):
        self.assertIn('{civilite} {prenom}',
                      MESSAGE_TEMPLATE_DEFAULTS['identite'])
        self.assertIn('{civilite} {prenom}',
                      MESSAGE_TEMPLATE_DEFAULTS_DARIJA['identite'])


class SalutationRendueTests(TestCase):
    """Le Done : un lead sans civilité ne reçoit plus « M. »."""

    def setUp(self):
        self.company = Company.objects.create(nom='CAD65 Solaire',
                                              slug='cad65')
        self.acteur = User.objects.create_user(
            username='cad65-resp', password='x', role_legacy='responsable',
            company=self.company, first_name='Nadia')
        self.lead = Lead.objects.create(
            company=self.company, nom='Idrissi', prenom='Salma',
            owner=self.acteur, telephone='+212661650065')

    def _rendu(self):
        etape = RelanceEtape.objects.create(
            company=self.company, lead=self.lead, ordre=1,
            canal=RelanceEtape.Canal.WHATSAPP, due_date=LUNDI.date(),
            due_at=LUNDI, cadence='contact', template_cle='identite')
        return message_pour_etape(etape, user=self.acteur)

    def test_chaque_salutation_du_contrat(self):
        for cas in CONTRAT['salutations']:
            with self.subTest(**cas):
                self.lead.civilite = cas['civilite']
                self.lead.langue_preferee = cas['langue']
                self.lead.save(update_fields=['civilite', 'langue_preferee'])
                rendu = self._rendu()
                self.assertTrue(
                    rendu['message'].startswith(cas['debut']),
                    rendu['message'][:60])
                self.assertNotIn('civilite', rendu['placeholders_manquants'])

    def test_sans_civilite_plus_jamais_monsieur(self):
        rendu = self._rendu()
        self.assertNotIn('M. Salma', rendu['message'])
        self.assertNotIn('{civilite}', rendu['message'])


class ChampALaFicheTests(TestCase):
    """La moitié (a) : le champ se saisit sur la fiche, refus nommé."""

    def setUp(self):
        self.company = Company.objects.create(nom='CAD65 Fiche',
                                              slug='cad65-fiche')
        self.acteur = User.objects.create_user(
            username='cad65-fiche', password='x', role_legacy='responsable',
            company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Idrissi', prenom='Salma',
            owner=self.acteur)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')
        self.url = f'/api/django/crm/leads/{self.lead.pk}/'

    def test_le_corps_du_contrat_enregistre_la_civilite(self):
        reponse = self.api.patch(self.url, CONTRAT['corps'], format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(reponse.data['civilite'],
                         CONTRAT['exemple']['civilite'])
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.civilite, 'Mme')
        # Journalisée comme la langue préférée.
        self.assertTrue(LeadActivity.objects.filter(
            lead=self.lead, field='civilite').exists())

    def test_null_redevient_neutre(self):
        self.lead.civilite = 'Mme'
        self.lead.save(update_fields=['civilite'])
        reponse = self.api.patch(self.url, {'civilite': None},
                                 format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.lead.refresh_from_db()
        self.assertIsNone(self.lead.civilite)

    def test_une_valeur_hors_choix_est_refusee_en_nommant_le_champ(self):
        reponse = self.api.patch(self.url, {'civilite': 'Mlle'},
                                 format='json')
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('civilite', reponse.data)

"""
XFSM8 — Notes d'accès site réutilisées à chaque visite.

Couvre :
  * champs éditables sur ``Installation`` (contact/téléphone/instructions/
    horaires), additifs et nullables ;
  * repris automatiquement en LECTURE sur toute ``Intervention`` du chantier
    (serializer), sans jamais être ressaisis ;
  * présents dans le contexte du PDF F19 (compte-rendu).

Run :
    python manage.py test apps.installations.tests_xfsm8_notes_acces -v2
"""
import itertools
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client, Lead
from apps.ventes.models import Devis
from apps.installations.models import Intervention
from apps.installations.services import create_installation_from_devis

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'


def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'xfsm8-co-{n}', defaults={'nom': nom or f'XFSM8 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable', username=None):
    return User.objects.create_user(
        username=username or f'xfsm8-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_chantier(company, user):
    n = next(_seq)
    client = Client.objects.create(
        company=company, nom='Site', prenom='Client',
        email=f'xfsm8-{company.id}-{n}@example.invalid')
    lead = Lead.objects.create(
        company=company, nom='Site', prenom='Client', stage='SIGNED',
        type_installation='residentiel')
    devis = Devis.objects.create(
        company=company, reference=f'DEV-XFSM8-{company.id}-{n}', client=client,
        lead=lead, statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'),
        mode_installation='residentiel')
    inst, _ = create_installation_from_devis(devis, user, company)
    return inst


class TestNotesAccesSurChantier(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.inst = make_chantier(self.company, self.user)

    def test_champs_editables_sur_chantier(self):
        r = self.api.patch(f'{BASE}/chantiers/{self.inst.id}/', {
            'contact_site_nom': 'Gardien Ahmed',
            'contact_site_telephone': '0600000000',
            'acces_instructions': 'Chien dans la cour, sonner avant.',
            'horaires_acces': '8h-17h sauf vendredi',
        }, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.inst.refresh_from_db()
        self.assertEqual(self.inst.contact_site_nom, 'Gardien Ahmed')
        self.assertEqual(
            self.inst.acces_instructions, 'Chien dans la cour, sonner avant.')
        self.assertEqual(self.inst.horaires_acces, '8h-17h sauf vendredi')

    def test_reprises_en_lecture_sur_intervention(self):
        self.inst.contact_site_nom = 'Gardien Ahmed'
        self.inst.contact_site_telephone = '0600000000'
        self.inst.acces_instructions = 'Portail code 1234.'
        self.inst.horaires_acces = '8h-17h'
        self.inst.save(update_fields=[
            'contact_site_nom', 'contact_site_telephone',
            'acces_instructions', 'horaires_acces'])
        interv = Intervention.objects.create(
            company=self.company, installation=self.inst,
            type_intervention='pose', created_by=self.user)
        r = self.api.get(f'{BASE}/interventions/{interv.id}/')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.data['contact_site_nom'], 'Gardien Ahmed')
        self.assertEqual(r.data['contact_site_telephone'], '0600000000')
        self.assertEqual(r.data['acces_instructions'], 'Portail code 1234.')
        self.assertEqual(r.data['horaires_acces'], '8h-17h')

    def test_absents_par_defaut_ne_cassent_rien(self):
        interv = Intervention.objects.create(
            company=self.company, installation=self.inst,
            type_intervention='pose', created_by=self.user)
        r = self.api.get(f'{BASE}/interventions/{interv.id}/')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIsNone(r.data['contact_site_nom'])
        self.assertIsNone(r.data['acces_instructions'])

    def test_presents_dans_contexte_pdf(self):
        self.inst.contact_site_nom = 'Gardien Ahmed'
        self.inst.horaires_acces = '8h-17h'
        self.inst.acces_instructions = 'Chien dans la cour.'
        self.inst.save(update_fields=[
            'contact_site_nom', 'horaires_acces', 'acces_instructions'])
        interv = Intervention.objects.create(
            company=self.company, installation=self.inst,
            type_intervention='pose', created_by=self.user)
        from apps.installations import intervention_pdf
        pdf_bytes = intervention_pdf.compte_rendu_pdf(interv)
        self.assertTrue(pdf_bytes[:4] == b'%PDF')

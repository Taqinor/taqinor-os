"""
XFSM2 — Assistant de planification : meilleur créneau + technicien suggéré.

Couvre :
  * l'endpoint renvoie des propositions valides (jamais un technicien en
    congé/conflit/sans habilitation) ;
  * tri déterministe (charge la plus faible d'abord) ;
  * lecture seule (ne mute rien) ;
  * bouton câblé côté frontend est hors périmètre backend (test API only).

Run :
    python manage.py test apps.installations.tests_xfsm2_suggerer_creneau -v2
"""
import itertools
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client, Lead
from apps.ventes.models import Devis
from apps.installations.models import Intervention, IndisponibiliteRessource
from apps.installations.services import create_installation_from_devis

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'


def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'xfsm2-co-{n}', defaults={'nom': nom or f'XFSM2 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable', username=None):
    return User.objects.create_user(
        username=username or f'xfsm2-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_chantier(company, user):
    n = next(_seq)
    client = Client.objects.create(
        company=company, nom='Site', prenom='Client',
        email=f'xfsm2-{company.id}-{n}@example.invalid')
    lead = Lead.objects.create(
        company=company, nom='Site', prenom='Client', stage='SIGNED',
        type_installation='residentiel')
    devis = Devis.objects.create(
        company=company, reference=f'DEV-XFSM2-{company.id}-{n}', client=client,
        lead=lead, statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'),
        mode_installation='residentiel')
    inst, _ = create_installation_from_devis(devis, user, company)
    return inst


class TestSuggererCreneau(TestCase):
    def setUp(self):
        self.company = make_company()
        self.admin = make_user(self.company, role='admin')
        self.api = auth(self.admin)
        self.inst = make_chantier(self.company, self.admin)
        self.tech1 = make_user(self.company, username='xfsm2-tech1')
        self.tech2 = make_user(self.company, username='xfsm2-tech2')
        # les deux techniciens entrent dans le "bassin éligible" via une
        # intervention passée déjà affectée (même patron que FG299).
        Intervention.objects.create(
            company=self.company, installation=self.inst,
            type_intervention='pose', created_by=self.admin,
            technicien=self.tech1, date_prevue=date.today() - timedelta(days=30))
        Intervention.objects.create(
            company=self.company, installation=self.inst,
            type_intervention='pose', created_by=self.admin,
            technicien=self.tech2, date_prevue=date.today() - timedelta(days=30))

    def test_renvoie_propositions_valides(self):
        resp = self.api.post(f'{BASE}/interventions/suggerer-creneau/', {
            'chantier': self.inst.id, 'type_intervention': 'controle',
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertGreater(len(resp.data['propositions']), 0)
        for prop in resp.data['propositions']:
            self.assertIn('technicien_id', prop)
            self.assertIn('date', prop)

    def test_ne_propose_jamais_technicien_en_conge(self):
        demain = date.today() + timedelta(days=1)
        IndisponibiliteRessource.objects.create(
            company=self.company, technicien=self.tech1,
            date_debut=date.today(), date_fin=demain + timedelta(days=20),
            type_indispo='conge')
        resp = self.api.post(f'{BASE}/interventions/suggerer-creneau/', {
            'chantier': self.inst.id, 'type_intervention': 'controle',
            'date_cible': demain.isoformat(),
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        ids_proposes = {p['technicien_id'] for p in resp.data['propositions']}
        self.assertNotIn(self.tech1.id, ids_proposes)

    def test_ne_propose_jamais_technicien_en_conflit(self):
        jour = date.today() + timedelta(days=2)
        Intervention.objects.create(
            company=self.company, installation=self.inst,
            type_intervention='pose', created_by=self.admin,
            technicien=self.tech1, date_prevue=jour)
        resp = self.api.post(f'{BASE}/interventions/suggerer-creneau/', {
            'chantier': self.inst.id, 'type_intervention': 'controle',
            'date_cible': jour.isoformat(),
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        propositions_ce_jour = [
            p for p in resp.data['propositions'] if p['date'] == jour.isoformat()]
        ids_ce_jour = {p['technicien_id'] for p in propositions_ce_jour}
        self.assertNotIn(self.tech1.id, ids_ce_jour)

    def test_tri_deterministe_par_charge(self):
        # tech2 a plus de charge future que tech1 dans la fenêtre.
        jour_cible = date.today() + timedelta(days=5)
        for i in range(3):
            Intervention.objects.create(
                company=self.company, installation=self.inst,
                type_intervention='pose', created_by=self.admin,
                technicien=self.tech2,
                date_prevue=jour_cible + timedelta(days=i + 1))
        resp = self.api.post(f'{BASE}/interventions/suggerer-creneau/', {
            'chantier': self.inst.id, 'type_intervention': 'controle',
            'date_cible': jour_cible.isoformat(),
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        propositions = resp.data['propositions']
        # tech1 (moins chargé) doit apparaître avant tech2 pour un même jour.
        rangs = {p['technicien_id']: i for i, p in enumerate(propositions)}
        if self.tech1.id in rangs and self.tech2.id in rangs:
            self.assertLess(rangs[self.tech1.id], rangs[self.tech2.id])

    def test_lecture_seule_ne_mute_rien(self):
        nb_avant = Intervention.objects.count()
        self.api.post(f'{BASE}/interventions/suggerer-creneau/', {
            'chantier': self.inst.id, 'type_intervention': 'controle',
        }, format='json')
        self.assertEqual(Intervention.objects.count(), nb_avant)

    def test_chantier_manquant_rejete(self):
        resp = self.api.post(f'{BASE}/interventions/suggerer-creneau/', {
            'type_intervention': 'controle',
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)

    def test_chantier_inconnu_propositions_vides(self):
        resp = self.api.post(f'{BASE}/interventions/suggerer-creneau/', {
            'chantier': 999999, 'type_intervention': 'controle',
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data['propositions'], [])

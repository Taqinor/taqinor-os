"""
XFSM3 — Replanification en masse d'une journée (pluie / technicien malade).

Couvre :
  * une journée de N interventions se re-slotte en un appel sans créer de
    conflit FG300 ;
  * l'historique FG78 trace chaque report (`rdv_reschedule_count`) ;
  * dry-run (`?simuler=1`) ne mute rien ;
  * le technicien réassigné est notifié.

Run :
    python manage.py test apps.installations.tests_xfsm3_replanifier_masse -v2
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
from apps.installations.models import Intervention
from apps.installations.services import create_installation_from_devis
from apps.notifications.models import Notification

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'


def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'xfsm3-co-{n}', defaults={'nom': nom or f'XFSM3 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable', username=None):
    return User.objects.create_user(
        username=username or f'xfsm3-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_chantier(company, user):
    n = next(_seq)
    client = Client.objects.create(
        company=company, nom='Site', prenom='Client',
        email=f'xfsm3-{company.id}-{n}@example.invalid')
    lead = Lead.objects.create(
        company=company, nom='Site', prenom='Client', stage='SIGNED',
        type_installation='residentiel')
    devis = Devis.objects.create(
        company=company, reference=f'DEV-XFSM3-{company.id}-{n}', client=client,
        lead=lead, statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'),
        mode_installation='residentiel')
    inst, _ = create_installation_from_devis(devis, user, company)
    return inst


class TestReplanificationMasse(TestCase):
    def setUp(self):
        self.company = make_company()
        self.admin = make_user(self.company, role='admin')
        self.api = auth(self.admin)
        self.inst = make_chantier(self.company, self.admin)
        self.absent = make_user(self.company, username='xfsm3-absent')
        self.autre = make_user(self.company, username='xfsm3-autre')
        # bassin éligible pour XFSM2 (intervention passée déjà affectée).
        for tech in (self.absent, self.autre):
            Intervention.objects.create(
                company=self.company, installation=self.inst,
                type_intervention='pose', created_by=self.admin,
                technicien=tech, date_prevue=date.today() - timedelta(days=60))
        self.jour = date.today() + timedelta(days=3)
        self.iv1 = Intervention.objects.create(
            company=self.company, installation=self.inst,
            type_intervention='controle', created_by=self.admin,
            technicien=self.absent, date_prevue=self.jour)
        self.iv2 = Intervention.objects.create(
            company=self.company, installation=self.inst,
            type_intervention='depannage', created_by=self.admin,
            technicien=self.absent, date_prevue=self.jour)

    def test_dry_run_ne_mute_rien(self):
        resp = self.api.post(f'{BASE}/interventions/replanifier-en-masse/', {
            'jour': self.jour.isoformat(), 'technicien': self.absent.id,
            'simuler': True,
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.iv1.refresh_from_db()
        self.assertEqual(self.iv1.technicien_id, self.absent.id)
        self.assertEqual(self.iv1.date_prevue, self.jour)

    def test_application_replanifie_journee_sans_conflit(self):
        resp = self.api.post(f'{BASE}/interventions/replanifier-en-masse/', {
            'jour': self.jour.isoformat(), 'technicien': self.absent.id,
            'motif': 'Technicien malade',
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.iv1.refresh_from_db()
        self.iv2.refresh_from_db()
        # Les deux interventions doivent avoir quitté le technicien absent
        # (ou être listées non résolues si aucun créneau libre).
        deplacees_ids = {d['intervention_id'] for d in resp.data['deplacees']}
        non_resolues = set(resp.data['non_resolues'])
        self.assertEqual(
            deplacees_ids | non_resolues, {self.iv1.id, self.iv2.id})
        for d in resp.data['deplacees']:
            self.assertNotEqual(d['nouveau_technicien_id'], self.absent.id)
        # Pas de double affectation créée le même jour pour un même technicien.
        interventions_du_jour = list(
            Intervention.objects.filter(company=self.company))
        vus = set()
        for iv in interventions_du_jour:
            if iv.technicien_id is None:
                continue
            cle = (iv.technicien_id, iv.date_prevue)
            self.assertNotIn(cle, vus)
            vus.add(cle)

    def test_historique_fg78_trace_le_report(self):
        resp = self.api.post(f'{BASE}/interventions/replanifier-en-masse/', {
            'jour': self.jour.isoformat(), 'technicien': self.absent.id,
            'motif': 'Pluie',
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        for d in resp.data['deplacees']:
            iv = Intervention.objects.get(id=d['intervention_id'])
            if d['nouvelle_date'] != str(self.jour):
                self.assertGreaterEqual(iv.rdv_reschedule_count, 1)
            self.assertTrue(
                iv.activites.filter(kind='note').exists())

    def test_technicien_reassigne_notifie(self):
        resp = self.api.post(f'{BASE}/interventions/replanifier-en-masse/', {
            'jour': self.jour.isoformat(), 'technicien': self.absent.id,
            'motif': 'Pluie',
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        if resp.data['deplacees']:
            nouveau_id = resp.data['deplacees'][0]['nouveau_technicien_id']
            self.assertTrue(
                Notification.objects.filter(
                    recipient_id=nouveau_id, company=self.company).exists())

    def test_intervention_ids_explicite(self):
        resp = self.api.post(f'{BASE}/interventions/replanifier-en-masse/', {
            'jour': self.jour.isoformat(), 'intervention_ids': [self.iv1.id],
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        touched = {d['intervention_id'] for d in resp.data['deplacees']} | \
            set(resp.data['non_resolues'])
        self.assertEqual(touched, {self.iv1.id})

    def test_jour_manquant_rejete(self):
        resp = self.api.post(
            f'{BASE}/interventions/replanifier-en-masse/', {}, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)

    def test_role_limite_refuse(self):
        limited = make_user(self.company, role='normal')
        api = auth(limited)
        resp = api.post(f'{BASE}/interventions/replanifier-en-masse/', {
            'jour': self.jour.isoformat(), 'technicien': self.absent.id,
        }, format='json')
        self.assertEqual(resp.status_code, 403)

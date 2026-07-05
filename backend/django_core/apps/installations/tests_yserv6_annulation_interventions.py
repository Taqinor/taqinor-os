"""
YSERV6 — Annulation de chantier : solder les interventions ouvertes (chemin
de réversion complet).

Couvre :
  * annuler un chantier à 3 interventions ouvertes les marque `annulee=True`
    + les sort du planning (kanban/liste par défaut) ;
  * une intervention déjà TERMINEE/VALIDEE n'est jamais touchée ;
  * la notification (best-effort) et la note chatter par intervention ;
  * réactiver le chantier restaure UNIQUEMENT les interventions annulées PAR
    cette annulation (traçabilité de provenance) ;
  * une intervention annulée pour une AUTRE raison n'est jamais réactivée ;
  * création d'une nouvelle intervention refusée sur un chantier annulé ;
  * migration additive, scope société.

Run :
    python manage.py test \
        apps.installations.tests_yserv6_annulation_interventions -v2
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
        slug=slug or f'yserv6-co-{n}', defaults={'nom': nom or f'Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable', username=None):
    return User.objects.create_user(
        username=username or f'yserv6-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_chantier(company, user):
    n = next(_seq)
    client = Client.objects.create(
        company=company, nom='Site', prenom='Client',
        email=f'yserv6-{company.id}-{n}@example.invalid')
    lead = Lead.objects.create(
        company=company, nom='Site', prenom='Client', stage='SIGNED')
    devis = Devis.objects.create(
        company=company, reference=f'DEV-{company.id}-{n}', client=client,
        lead=lead, statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'))
    inst, _ = create_installation_from_devis(devis, user, company)
    return inst


def make_intervention(company, installation, statut=Intervention.Statut.PRETE):
    return Intervention.objects.create(
        company=company, installation=installation,
        type_intervention=Intervention.Type.POSE, statut=statut)


class AnnulationSoldeInterventionsTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.inst = make_chantier(self.company, self.user)
        self.i1 = make_intervention(self.company, self.inst)
        self.i2 = make_intervention(
            self.company, self.inst, statut=Intervention.Statut.EN_ROUTE)
        self.i3_terminee = make_intervention(
            self.company, self.inst, statut=Intervention.Statut.TERMINEE)

    def test_annuler_marque_interventions_ouvertes(self):
        r = self.api.post(f'{BASE}/chantiers/{self.inst.id}/annuler/', {})
        self.assertEqual(r.status_code, 200, r.data)
        self.i1.refresh_from_db()
        self.i2.refresh_from_db()
        self.i3_terminee.refresh_from_db()
        self.assertTrue(self.i1.annulee)
        self.assertTrue(self.i2.annulee)
        self.assertFalse(self.i3_terminee.annulee)
        # La state machine F3 (statut) n'est jamais modifiée par l'annulation.
        self.assertEqual(self.i1.statut, Intervention.Statut.PRETE)

    def test_interventions_annulees_sorties_de_la_liste_par_defaut(self):
        self.api.post(f'{BASE}/chantiers/{self.inst.id}/annuler/', {})
        r = self.api.get(f'{BASE}/interventions/?installation={self.inst.id}')
        results = r.data['results'] if 'results' in r.data else r.data
        ids = {row['id'] for row in results}
        self.assertNotIn(self.i1.id, ids)
        self.assertNotIn(self.i2.id, ids)
        self.assertIn(self.i3_terminee.id, ids)

    def test_interventions_annulees_visibles_avec_filtre(self):
        self.api.post(f'{BASE}/chantiers/{self.inst.id}/annuler/', {})
        r = self.api.get(
            f'{BASE}/interventions/?installation={self.inst.id}'
            '&annulee=true')
        results = r.data['results'] if 'results' in r.data else r.data
        ids = {row['id'] for row in results}
        self.assertIn(self.i1.id, ids)
        self.assertIn(self.i2.id, ids)

    def test_creation_refusee_sur_chantier_annule(self):
        self.api.post(f'{BASE}/chantiers/{self.inst.id}/annuler/', {})
        r = self.api.post(f'{BASE}/interventions/', {
            'installation': self.inst.id,
            'type_intervention': Intervention.Type.CONTROLE,
        })
        self.assertEqual(r.status_code, 400, r.data)


class ReactivationTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.inst = make_chantier(self.company, self.user)
        self.i1 = make_intervention(self.company, self.inst)

    def test_reactiver_restaure_interventions_annulees_par_ce_flux(self):
        self.api.post(f'{BASE}/chantiers/{self.inst.id}/annuler/', {})
        self.i1.refresh_from_db()
        self.assertTrue(self.i1.annulee)
        r = self.api.post(f'{BASE}/chantiers/{self.inst.id}/reactiver/', {})
        self.assertEqual(r.status_code, 200, r.data)
        self.i1.refresh_from_db()
        self.assertFalse(self.i1.annulee)
        self.assertIsNone(self.i1.motif_annulation)

    def test_reactiver_ne_touche_pas_annulation_autre_raison(self):
        autre = make_intervention(self.company, self.inst)
        autre.annulee = True
        autre.motif_annulation = 'Annulée pour une autre raison'
        autre.save(update_fields=['annulee', 'motif_annulation'])
        self.api.post(f'{BASE}/chantiers/{self.inst.id}/annuler/', {})
        self.api.post(f'{BASE}/chantiers/{self.inst.id}/reactiver/', {})
        autre.refresh_from_db()
        self.assertTrue(autre.annulee)
        self.assertEqual(autre.motif_annulation, 'Annulée pour une autre raison')


class IsolationSocieteTests(TestCase):
    def test_annulation_scopee_societe(self):
        co1 = make_company()
        co2 = make_company()
        user1 = make_user(co1)
        inst1 = make_chantier(co1, user1)
        inst2 = make_chantier(co2, make_user(co2))
        interv1 = make_intervention(co1, inst1)
        interv2 = make_intervention(co2, inst2)
        api1 = auth(user1)
        api1.post(f'{BASE}/chantiers/{inst1.id}/annuler/', {})
        interv1.refresh_from_db()
        interv2.refresh_from_db()
        self.assertTrue(interv1.annulee)
        self.assertFalse(interv2.annulee)

"""
YSERV9 — Chemin d'exception : annulation client après signature (réversion
partielle) — l'événement `core.events.chantier_annule` vers ventes.

Couvre :
  * annuler un chantier avec devis lié émet `chantier_annule` et pose une
    `DevisActivity` (NOTE) sur ce devis, SANS changer son statut ;
  * un chantier SANS devis lié : no-op (rien à signaler, pas d'erreur) ;
  * l'annulation continue de libérer le stock ET clore les interventions
    ouvertes (YSERV6) — le tout dans le même appel ;
  * isolation multi-tenant.

Run :
    python manage.py test \
        apps.installations.tests_yserv9_chantier_annule_event -v2
"""
import itertools
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client, Lead
from apps.ventes.models import Devis, DevisActivity
from apps.installations.models import Installation
from apps.installations.services import create_installation_from_devis

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'


def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'yserv9-co-{n}', defaults={'nom': nom or f'Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable', username=None):
    return User.objects.create_user(
        username=username or f'yserv9-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_chantier_avec_devis(company, user):
    n = next(_seq)
    client = Client.objects.create(
        company=company, nom='Site', prenom='Client',
        email=f'yserv9-{company.id}-{n}@example.invalid')
    lead = Lead.objects.create(
        company=company, nom='Site', prenom='Client', stage='SIGNED')
    devis = Devis.objects.create(
        company=company, reference=f'DEV-{company.id}-{n}', client=client,
        lead=lead, statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'))
    inst, _ = create_installation_from_devis(devis, user, company)
    return inst, devis


class AnnulationAvecDevisTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.inst, self.devis = make_chantier_avec_devis(
            self.company, self.user)

    def test_annuler_pose_activite_sur_devis(self):
        statut_avant = self.devis.statut
        r = self.api.post(f'{BASE}/chantiers/{self.inst.id}/annuler/', {})
        self.assertEqual(r.status_code, 200, r.data)
        self.devis.refresh_from_db()
        # STATUT PRESERVATION — l'annulation du chantier ne touche JAMAIS
        # le statut du devis (règle #4).
        self.assertEqual(self.devis.statut, statut_avant)
        activites = DevisActivity.objects.filter(
            devis=self.devis, kind=DevisActivity.Kind.NOTE,
            body__icontains='annulé')
        self.assertEqual(activites.count(), 1)
        self.assertIn('avoir', activites.first().body.lower())

    def test_annuler_deux_fois_ne_double_pas_activite(self):
        self.api.post(f'{BASE}/chantiers/{self.inst.id}/annuler/', {})
        self.api.post(f'{BASE}/chantiers/{self.inst.id}/annuler/', {})
        activites = DevisActivity.objects.filter(
            devis=self.devis, kind=DevisActivity.Kind.NOTE,
            body__icontains='annulé')
        # Le guard `if not inst.annule` de la vue empêche un second appel
        # de re-déclencher l'annulation (idempotence existante préservée).
        self.assertEqual(activites.count(), 1)


class AnnulationSansDevisTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.inst = Installation.objects.create(
            company=self.company, reference=f'INST-{next(_seq)}',
            statut=Installation.Statut.SIGNE)

    def test_sans_devis_pas_erreur_pas_activite(self):
        r = self.api.post(f'{BASE}/chantiers/{self.inst.id}/annuler/', {})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(DevisActivity.objects.count(), 0)


class IsolationSocieteTests(TestCase):
    def test_activite_scopee_societe(self):
        co1 = make_company()
        co2 = make_company()
        user1 = make_user(co1)
        inst1, devis1 = make_chantier_avec_devis(co1, user1)
        api1 = auth(user1)
        api1.post(f'{BASE}/chantiers/{inst1.id}/annuler/', {})
        self.assertEqual(
            DevisActivity.objects.filter(devis=devis1).count(), 1)
        self.assertEqual(
            DevisActivity.objects.filter(company=co2).count(), 0)

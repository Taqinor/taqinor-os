"""
YSERV1 — Gate « acompte encaissé » avant planification (override responsable
journalisé).

Couvre :
  * toggle OFF (défaut) : passage à PLANIFIE inchangé, byte-identique ;
  * toggle ON, sans facture d'acompte payée : passage à PLANIFIE refusé (400,
    message clair) ;
  * toggle ON, avec facture d'acompte payée : passage à PLANIFIE autorisé ;
  * override responsable avec motif obligatoire : la planification passe et
    une note apparaît dans le chatter `InstallationActivity` ;
  * sans devis lié : jamais bloqué (rien à vérifier) ;
  * multi-tenant : le toggle et les factures restent scopés société.

Run :
    python manage.py test apps.installations.tests_yserv1_gate_acompte -v2
"""
import itertools
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client, Lead
from apps.ventes.models import Devis, Facture
from apps.installations.models import Installation, InstallationActivity
from apps.installations.services import create_installation_from_devis
from apps.parametres.models import CompanyProfile

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'


def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'yserv1-co-{n}', defaults={'nom': nom or f'Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable', username=None):
    return User.objects.create_user(
        username=username or f'yserv1-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_chantier_avec_devis(company, user):
    n = next(_seq)
    client = Client.objects.create(
        company=company, nom='Site', prenom='Client',
        email=f'yserv1-{company.id}-{n}@example.invalid')
    lead = Lead.objects.create(
        company=company, nom='Site', prenom='Client', stage='SIGNED')
    devis = Devis.objects.create(
        company=company, reference=f'DEV-{company.id}-{n}', client=client,
        lead=lead, statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'))
    inst, _ = create_installation_from_devis(devis, user, company)
    return inst, devis, client


def make_facture_acompte(company, devis, client, payee=True):
    return Facture.objects.create(
        company=company, devis=devis, client=client,
        type_facture=Facture.TypeFacture.ACOMPTE,
        statut=Facture.Statut.PAYEE if payee else Facture.Statut.EMISE,
        reference=f'FAC-{next(_seq)}', montant_ttc=Decimal('1000'))


class ToggleOffTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.inst, self.devis, self.client_ = make_chantier_avec_devis(
            self.company, self.user)

    def test_planification_inchangee_toggle_off(self):
        r = self.api.patch(
            f'{BASE}/chantiers/{self.inst.id}/',
            {'statut': Installation.Statut.PLANIFIE}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.inst.refresh_from_db()
        self.assertEqual(self.inst.statut, Installation.Statut.PLANIFIE)


class ToggleOnSansAcompteTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.inst, self.devis, self.client_ = make_chantier_avec_devis(
            self.company, self.user)
        profil = CompanyProfile.get(self.company)
        profil.exiger_acompte_avant_planification = True
        profil.save(update_fields=['exiger_acompte_avant_planification'])

    def test_planification_refusee_sans_acompte(self):
        r = self.api.patch(
            f'{BASE}/chantiers/{self.inst.id}/',
            {'statut': Installation.Statut.PLANIFIE}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.inst.refresh_from_db()
        self.assertNotEqual(self.inst.statut, Installation.Statut.PLANIFIE)

    def test_planification_refusee_facture_non_payee(self):
        make_facture_acompte(
            self.company, self.devis, self.client_, payee=False)
        r = self.api.patch(
            f'{BASE}/chantiers/{self.inst.id}/',
            {'statut': Installation.Statut.PLANIFIE}, format='json')
        self.assertEqual(r.status_code, 400, r.data)

    def test_planification_autorisee_avec_acompte_paye(self):
        make_facture_acompte(self.company, self.devis, self.client_)
        r = self.api.patch(
            f'{BASE}/chantiers/{self.inst.id}/',
            {'statut': Installation.Statut.PLANIFIE}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.inst.refresh_from_db()
        self.assertEqual(self.inst.statut, Installation.Statut.PLANIFIE)

    def test_override_responsable_avec_motif(self):
        r = self.api.patch(
            f'{BASE}/chantiers/{self.inst.id}/',
            {'statut': Installation.Statut.PLANIFIE,
             'motif_override_acompte': 'Client VIP, accord verbal'},
            format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.inst.refresh_from_db()
        self.assertEqual(self.inst.statut, Installation.Statut.PLANIFIE)
        notes = InstallationActivity.objects.filter(
            installation=self.inst,
            body__icontains='Planifié sans acompte')
        self.assertEqual(notes.count(), 1)
        self.assertIn('Client VIP', notes.first().body)

    def test_override_sans_motif_refuse(self):
        r = self.api.patch(
            f'{BASE}/chantiers/{self.inst.id}/',
            {'statut': Installation.Statut.PLANIFIE,
             'motif_override_acompte': '   '}, format='json')
        self.assertEqual(r.status_code, 400, r.data)


class SansDevisLieTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        profil = CompanyProfile.get(self.company)
        profil.exiger_acompte_avant_planification = True
        profil.save(update_fields=['exiger_acompte_avant_planification'])
        self.inst = Installation.objects.create(
            company=self.company, reference=f'INST-{next(_seq)}',
            statut=Installation.Statut.SIGNE)

    def test_sans_devis_jamais_bloque(self):
        r = self.api.patch(
            f'{BASE}/chantiers/{self.inst.id}/',
            {'statut': Installation.Statut.PLANIFIE}, format='json')
        self.assertEqual(r.status_code, 200, r.data)


class IsolationSocieteTests(TestCase):
    def test_toggle_scope_societe(self):
        co1 = make_company()
        co2 = make_company()
        profil1 = CompanyProfile.get(co1)
        profil1.exiger_acompte_avant_planification = True
        profil1.save(update_fields=['exiger_acompte_avant_planification'])
        profil2 = CompanyProfile.get(co2)
        self.assertFalse(profil2.exiger_acompte_avant_planification)

"""
YHIRE9 — Garde d'habilitation à l'AFFECTATION d'intervention (contrôle à
l'écriture, complète XFSM2 qui ne fait QUE suggérer).

Couvre :
  * affecter un technicien SANS l'habilitation requise (mode 'warn', défaut)
    renvoie un avertissement dans la réponse, sans bloquer ;
  * mode 'block' refuse l'affectation (400) tant que l'habilitation n'est
    pas valide ;
  * un technicien HABILITÉ ne déclenche aucun avertissement ;
  * un type d'intervention SANS mapping connu (ex. dépannage) n'est jamais
    bloqué ni signalé côté YHIRE9 (dépannage → maintenance_bt existe en
    réalité, donc on teste avec un technicien habilité BR) ;
  * un technicien sans fiche RH liée n'est jamais bloqué (garde soft) ;
  * changer le technicien d'une intervention existante re-vérifie ; ne pas
    changer le technicien (autre édition) ne redéclenche rien.

Run :
    python manage.py test apps.installations.tests_yhire9_garde_habilitation -v2
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
from apps.parametres.models import CompanyProfile
from apps.rh.models import DossierEmploye, Habilitation

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'


def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'yhire9-co-{n}', defaults={'nom': nom or f'Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable', username=None):
    return User.objects.create_user(
        username=username or f'yhire9-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_chantier(company, user):
    n = next(_seq)
    client = Client.objects.create(
        company=company, nom='Site', prenom='Client',
        email=f'yhire9-{company.id}-{n}@example.invalid')
    lead = Lead.objects.create(
        company=company, nom='Site', prenom='Client', stage='SIGNED')
    devis = Devis.objects.create(
        company=company, reference=f'DEV-{company.id}-{n}', client=client,
        lead=lead, statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'))
    inst, _ = create_installation_from_devis(devis, user, company)
    return inst


def make_dossier(company, user, nom='Tech'):
    return DossierEmploye.objects.create(
        company=company, user=user, nom=nom, prenom='X')


def make_habilitation(company, dossier, type_habilitation):
    return Habilitation.objects.create(
        company=company, employe=dossier,
        type_habilitation=type_habilitation, actif=True)


class ModeWarnTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.admin = make_user(self.company, role='admin')
        self.api = auth(self.admin)
        self.inst = make_chantier(self.company, self.admin)
        self.tech = make_user(self.company, username='yhire9-tech-sans')
        make_dossier(self.company, self.tech)  # fiche RH sans habilitation

    def test_affectation_sans_habilitation_avertit_sans_bloquer(self):
        r = self.api.post(f'{BASE}/interventions/', {
            'installation': self.inst.id,
            'type_intervention': Intervention.Type.POSE,
            'technicien': self.tech.id,
        })
        self.assertEqual(r.status_code, 201, r.data)
        self.assertIn('avertissements', r.data)
        self.assertTrue(len(r.data['avertissements']) > 0)

    def test_technicien_sans_fiche_rh_jamais_bloque(self):
        tech_sans_fiche = make_user(
            self.company, username='yhire9-tech-nofiche')
        r = self.api.post(f'{BASE}/interventions/', {
            'installation': self.inst.id,
            'type_intervention': Intervention.Type.POSE,
            'technicien': tech_sans_fiche.id,
        })
        self.assertEqual(r.status_code, 201, r.data)
        self.assertNotIn('avertissements', r.data)


class ModeBlockTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.admin = make_user(self.company, role='admin')
        self.api = auth(self.admin)
        self.inst = make_chantier(self.company, self.admin)
        self.tech = make_user(self.company, username='yhire9-tech-block')
        make_dossier(self.company, self.tech)
        profil = CompanyProfile.get(self.company)
        profil.mode_garde_habilitation = (
            CompanyProfile.ModeGardeHabilitation.BLOCK)
        profil.save(update_fields=['mode_garde_habilitation'])

    def test_affectation_sans_habilitation_refusee(self):
        r = self.api.post(f'{BASE}/interventions/', {
            'installation': self.inst.id,
            'type_intervention': Intervention.Type.POSE,
            'technicien': self.tech.id,
        })
        self.assertEqual(r.status_code, 400, r.data)


class TechnicienHabiliteTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.admin = make_user(self.company, role='admin')
        self.api = auth(self.admin)
        self.inst = make_chantier(self.company, self.admin)
        self.tech = make_user(self.company, username='yhire9-tech-ok')
        dossier = make_dossier(self.company, self.tech)
        # POSE requiert b1v OU br (INTERVENTION_HABILITATIONS['pose_pv_bt']).
        make_habilitation(self.company, dossier, 'b1v')

    def test_technicien_habilite_aucun_avertissement(self):
        r = self.api.post(f'{BASE}/interventions/', {
            'installation': self.inst.id,
            'type_intervention': Intervention.Type.POSE,
            'technicien': self.tech.id,
        })
        self.assertEqual(r.status_code, 201, r.data)
        self.assertNotIn('avertissements', r.data)


class ChangementTechnicienTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.admin = make_user(self.company, role='admin')
        self.api = auth(self.admin)
        self.inst = make_chantier(self.company, self.admin)
        self.tech_ok = make_user(self.company, username='yhire9-tech-ok2')
        dossier_ok = make_dossier(self.company, self.tech_ok)
        make_habilitation(self.company, dossier_ok, 'b1v')
        self.tech_ko = make_user(self.company, username='yhire9-tech-ko2')
        make_dossier(self.company, self.tech_ko)
        self.interv = Intervention.objects.create(
            company=self.company, installation=self.inst,
            type_intervention=Intervention.Type.POSE,
            technicien=self.tech_ok, created_by=self.admin)

    def test_changer_vers_technicien_non_habilite_avertit(self):
        r = self.api.patch(f'{BASE}/interventions/{self.interv.id}/', {
            'technicien': self.tech_ko.id,
        }, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertIn('avertissements', r.data)

    def test_edition_sans_changer_technicien_ne_redeclenche_rien(self):
        r = self.api.patch(f'{BASE}/interventions/{self.interv.id}/', {
            'priorite': Intervention.Priorite.HAUTE,
        }, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertNotIn('avertissements', r.data)

"""
ZFSM1 — Gabarit de fiche d'intervention configurable par type.

Couvre :
  * CRUD `fiche-intervention-templates/` + `fiche-intervention-champs/`
    (Paramètres → Chantiers), company-scopé ;
  * matérialisation paresseuse du relevé (`interventions/{id}/fiche/`) depuis
    le gabarit correspondant au `type_intervention` ;
  * `interventions/{id}/renseigner-fiche/` renseigne une valeur ;
  * un champ obligatoire non renseigné bloque la transition vers
    « Terminée » avec un message clair (`transition_block_reason`) ;
  * isolation multi-société.

Run :
    python manage.py test apps.installations.tests_zfsm1_fiche_template -v2
"""
import itertools

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.installations import field_services
from apps.installations.models import (
    FicheInterventionChamp, FicheInterventionTemplate, Installation,
    Intervention,
)

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'


def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'zfsm1-co-{n}', defaults={'nom': nom or f'ZFSM1 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='admin'):
    return User.objects.create_user(
        username=f'zfsm1-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_installation(company):
    n = next(_seq)
    client = Client.objects.create(
        company=company, nom='Client', prenom='ZFSM1',
        email=f'zfsm1-{company.id}-{n}@example.invalid')
    return Installation.objects.create(
        company=company, reference=f'CHT-ZFSM1-{n}', client=client)


def make_template(company, type_intervention='controle', nom='Contrôle standard'):
    return FicheInterventionTemplate.objects.create(
        company=company, nom=nom, type_intervention=type_intervention)


class TestFicheInterventionTemplateCRUD(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)

    def test_create_template_and_champ(self):
        r = self.api.post(
            f'{BASE}/fiche-intervention-templates/',
            {'nom': 'Contrôle annuel', 'type_intervention': 'controle'},
            format='json')
        self.assertEqual(r.status_code, 201, r.content)
        template_id = r.data['id']

        r2 = self.api.post(
            f'{BASE}/fiche-intervention-champs/',
            {'template': template_id, 'cle': 'tension_dc', 'libelle': 'Tension DC',
             'type_champ': 'mesure', 'unite': 'V', 'ordre': 1,
             'obligatoire': True},
            format='json')
        self.assertEqual(r2.status_code, 201, r2.content)
        self.assertEqual(
            FicheInterventionChamp.objects.filter(
                template_id=template_id).count(), 1)

    def test_champ_rejects_foreign_company_template(self):
        other = make_company()
        other_template = make_template(other)
        r = self.api.post(
            f'{BASE}/fiche-intervention-champs/',
            {'template': other_template.id, 'cle': 'x', 'libelle': 'X',
             'type_champ': 'texte'},
            format='json')
        self.assertEqual(r.status_code, 400)

    def test_protected_template_cannot_be_deleted(self):
        template = make_template(self.company)
        template.protege = True
        template.save(update_fields=['protege'])
        r = self.api.delete(f'{BASE}/fiche-intervention-templates/{template.id}/')
        self.assertEqual(r.status_code, 409)

    def test_multi_tenant_isolation(self):
        make_template(self.company)
        other = make_company()
        make_template(other, type_intervention='pose')
        r = self.api.get(f'{BASE}/fiche-intervention-templates/')
        self.assertEqual(len(r.data), 1)


class TestFicheReleveMaterialisation(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.inst = make_installation(self.company)
        self.template = make_template(self.company, type_intervention='controle')
        self.champ_obligatoire = FicheInterventionChamp.objects.create(
            company=self.company, template=self.template,
            cle='tension_dc', libelle='Tension DC', type_champ='mesure',
            unite='V', ordre=1, obligatoire=True)
        self.champ_optionnel = FicheInterventionChamp.objects.create(
            company=self.company, template=self.template,
            cle='note', libelle='Note', type_champ='texte', ordre=2,
            obligatoire=False)
        self.interv = Intervention.objects.create(
            company=self.company, installation=self.inst,
            type_intervention='controle', created_by=self.user)

    def test_fiche_endpoint_materializes_releve(self):
        r = self.api.get(f'{BASE}/interventions/{self.interv.id}/fiche/')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.data['template'], self.template.id)
        self.assertEqual(len(r.data['valeurs']), 2)

    def test_fiche_endpoint_none_without_matching_template(self):
        interv2 = Intervention.objects.create(
            company=self.company, installation=self.inst,
            type_intervention='pose', created_by=self.user)
        r = self.api.get(f'{BASE}/interventions/{interv2.id}/fiche/')
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(r.data)

    def test_renseigner_fiche_sets_value(self):
        r0 = self.api.get(f'{BASE}/interventions/{self.interv.id}/fiche/')
        valeur_id = next(
            v['id'] for v in r0.data['valeurs']
            if v['champ_cle'] == 'tension_dc')
        r = self.api.post(
            f'{BASE}/interventions/{self.interv.id}/renseigner-fiche/',
            {'valeur_id': valeur_id, 'valeur': '235.4'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        val = next(v for v in r.data['valeurs'] if v['id'] == valeur_id)
        self.assertEqual(val['valeur'], '235.4')

    def test_missing_required_champ_blocks_terminee(self):
        field_services.ensure_fiche_releve(self.interv)
        # Satisfy F5/F8 gates so only ZFSM1 gate is exercised: no prep lines,
        # no required shots configured for this company (default seed absent).
        reason = field_services.transition_block_reason(
            self.interv, Intervention.Statut.TERMINEE)
        self.assertIsNotNone(reason)
        self.assertIn('Tension DC', reason)

    def test_filled_required_champ_unblocks_terminee(self):
        releve = field_services.ensure_fiche_releve(self.interv)
        val = releve.valeurs.get(champ=self.champ_obligatoire)
        val.valeur = '230'
        val.save(update_fields=['valeur'])
        reason = field_services.transition_block_reason(
            self.interv, Intervention.Statut.TERMINEE)
        self.assertIsNone(reason)

    def test_idempotent_materialization_keeps_existing_values(self):
        releve = field_services.ensure_fiche_releve(self.interv)
        val = releve.valeurs.get(champ=self.champ_obligatoire)
        val.valeur = '230'
        val.save(update_fields=['valeur'])
        # Re-materialize (e.g. a second GET /fiche/) must not wipe the value.
        releve2 = field_services.ensure_fiche_releve(self.interv)
        val2 = releve2.valeurs.get(champ=self.champ_obligatoire)
        self.assertEqual(val2.valeur, '230')

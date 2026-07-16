"""NTEXT3 — générateur de FORMULAIRE pour objets custom.

Endpoint ``GET custom-fields/custom-objects/<code>/vue-formulaire/`` renvoie
le schéma de formulaire (champs ordonnés, obligatoires, conditions XPLT15,
options de choix, module cible des RELATION). Le POST sur CustomRecord
RE-VALIDE ``requis_si`` côté serveur (déjà garanti par
``serializers.validate_custom_data`` — testé ici via l'API bout-en-bout)."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.customfields.models import CustomFieldDef, CustomObjectDef
from authentication.models import Company

User = get_user_model()


class NTEXT3Base(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='ntext3-co', defaults={'nom': 'NTEXT3 Co'})[0]
        self.admin = User.objects.create_user(
            username='ntext3_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')
        self.objet = CustomObjectDef.objects.create(
            company=self.company, code='visiteurs', libelle='Visiteurs')


class TestVueFormulaireSchema(NTEXT3Base):
    def test_fields_ordered_with_metadata(self):
        CustomFieldDef.objects.create(
            company=self.company, module='custom:visiteurs', code='nom',
            libelle='Nom', type='text', obligatoire=True, ordre=1)
        CustomFieldDef.objects.create(
            company=self.company, module='custom:visiteurs', code='badge',
            libelle='Type de badge', type='choice',
            options=['visiteur', 'prestataire'], ordre=2)
        resp = self.api.get(
            '/api/django/custom-fields/custom-objects/visiteurs/vue-formulaire/')
        self.assertEqual(resp.status_code, 200, resp.data)
        champs = resp.data['champs']
        self.assertEqual([c['code'] for c in champs], ['nom', 'badge'])
        self.assertTrue(champs[0]['obligatoire'])
        self.assertEqual(champs[1]['options'], ['visiteur', 'prestataire'])

    def test_relation_field_exposes_module_cible(self):
        CustomFieldDef.objects.create(
            company=self.company, module='custom:visiteurs', code='societe',
            libelle='Société liée', type='relation', relation_module='client')
        resp = self.api.get(
            '/api/django/custom-fields/custom-objects/visiteurs/vue-formulaire/')
        champ = resp.data['champs'][0]
        self.assertEqual(champ['module_cible'], 'client')

    def test_conditions_exposed_for_front_evaluation(self):
        CustomFieldDef.objects.create(
            company=self.company, module='custom:visiteurs', code='motif',
            libelle='Motif de refus', type='text',
            conditions={'requis_si': {
                'field': 'statut', 'operator': 'eq', 'value': 'refuse'}})
        resp = self.api.get(
            '/api/django/custom-fields/custom-objects/visiteurs/vue-formulaire/')
        champ = resp.data['champs'][0]
        self.assertEqual(champ['requis_si'],
                         {'field': 'statut', 'operator': 'eq', 'value': 'refuse'})
        self.assertIsNone(champ['visible_si'])

    def test_unknown_object_404(self):
        resp = self.api.get(
            '/api/django/custom-fields/custom-objects/inexistant/vue-formulaire/')
        self.assertEqual(resp.status_code, 404)


class TestRequisSiServerReEnforcedOnCustomRecord(NTEXT3Base):
    """Critère NTEXT3 : requis_si non satisfait -> 400 FR ; satisfait -> passe."""

    def setUp(self):
        super().setUp()
        CustomFieldDef.objects.create(
            company=self.company, module='custom:visiteurs', code='statut',
            libelle='Statut', type='text')
        CustomFieldDef.objects.create(
            company=self.company, module='custom:visiteurs', code='motif',
            libelle='Motif de refus', type='text',
            conditions={'requis_si': {
                'field': 'statut', 'operator': 'eq', 'value': 'refuse'}})

    def test_unsatisfied_requis_si_blocks_creation(self):
        resp = self.api.post(
            '/api/django/custom-fields/custom-objects/visiteurs/records/',
            {'data': {'statut': 'refuse'}}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('motif', str(resp.data).lower())

    def test_satisfied_requis_si_passes(self):
        resp = self.api.post(
            '/api/django/custom-fields/custom-objects/visiteurs/records/',
            {'data': {'statut': 'refuse', 'motif': 'Pas de RDV'}},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_condition_false_does_not_require_field(self):
        resp = self.api.post(
            '/api/django/custom-fields/custom-objects/visiteurs/records/',
            {'data': {'statut': 'accepte'}}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)

"""T11 — mécanisme de champs personnalisés (définitions + validation custom_data)."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Lead
from apps.customfields.models import CustomFieldDef
from authentication.models import Company

User = get_user_model()


class CFBase(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='cf-co', defaults={'nom': 'CF Co'})[0]
        self.admin = User.objects.create_user(
            username='cf_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')


class TestDefinitions(CFBase):
    def test_admin_creates_definition(self):
        resp = self.api.post('/api/django/custom-fields/definitions/', {
            'module': 'lead', 'code': 'origine_pub', 'libelle': 'Origine pub',
            'type': 'choice', 'options': ['Facebook', 'Google'],
            'obligatoire': True,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertTrue(CustomFieldDef.objects.filter(
            company=self.company, module='lead', code='origine_pub').exists())

    def test_options_type_json_un_seul_predicat(self):
        # CI #1000 (api-fuzz) — ``options`` : liste de chaînes, ``""`` ou
        # ``null`` ; ``0`` / ``true`` / objet / élément non texte = 400 (le
        # schéma ne publiait que « tout JSON » : ``options: 0`` conforme refusé).
        url = '/api/django/custom-fields/definitions/'
        base = {'module': 'fournisseur', 'libelle': 'L', 'type': 'text'}
        for n, options in enumerate((0, True, {'a': 'b'}, 'x', ['a', 0])):
            resp = self.api.post(
                url, {**base, 'code': f'mauvais_{n}', 'options': options},
                format='json')
            self.assertEqual(resp.status_code, 400, (options, resp.content))
            self.assertIn('options', resp.data)
        for n, options in enumerate((None, '', [], [' a ', 'b'])):
            resp = self.api.post(
                url, {**base, 'code': f'bon_{n}', 'options': options},
                format='json')
            self.assertEqual(resp.status_code, 201, (options, resp.content))

    def test_choix_options_non_vides_publie_et_applique(self):
        # Le corps de création publie « Choix => options non vides » ; le
        # serveur l'applique (option blanche refusée, plus écartée en silence).
        import jsonschema
        from apps.customfields.serializers import corps_definition_resserre
        regle = corps_definition_resserre()
        valide = jsonschema.Draft7Validator(regle).is_valid
        self.assertTrue(valide({'type': 'text', 'options': None}))
        self.assertTrue(valide({'type': 'choice', 'options': ['A']}))
        self.assertFalse(valide({'type': 'choice'}))
        self.assertFalse(valide({'type': 'choice', 'options': []}))
        self.assertFalse(valide({'type': 'choice', 'options': ['A', ' ']}))
        self.assertFalse(valide({'type': 'relation', 'relation_module': 'x'}))
        self.assertTrue(valide({'type': 'relation', 'relation_module': 'lead'}))
        self.assertFalse(valide({'type': 'formula', 'formule': ' '}))
        # api-fuzz 24/10 : la formule publiée est une opération sur nombres,
        # que le serveur accepte (jamais « Syntaxe invalide »).
        self.assertFalse(valide({'type': 'formula', 'formule': 'a\bé+v'}))
        self.assertTrue(valide({'type': 'formula', 'formule': '2 * 30 - 4'}))
        resp = self.api.post(
            '/api/django/custom-fields/definitions/',
            {'module': 'lead', 'libelle': 'F', 'type': 'formula',
             'code': 'f_num', 'formule': '2 * 30 - 4'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        url = '/api/django/custom-fields/definitions/'
        base = {'module': 'lead', 'libelle': 'L', 'type': 'choice'}
        for n, options in enumerate((None, [], ['A', ' '])):
            resp = self.api.post(
                url, {**base, 'code': f'c_{n}', 'options': options},
                format='json')
            self.assertEqual(resp.status_code, 400, (options, resp.content))
            self.assertIn('options', resp.data)
        resp = self.api.post(
            url, {**base, 'code': 'c_ok', 'options': [' A ', 'B']},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(resp.json()['options'], ['A', 'B'])

    def test_module_et_regle_de_type_publies_sans_empilement(self):
        # api-fuzz-full 24/10 (« Too many generated examples are filtered
        # out ») : ``module`` = UN motif borné (plus anyOf + énumération +
        # motif DRF + longueurs) ; la règle dépendant du ``type`` = UN anyOf.
        import re

        from django.urls import include, path
        from drf_spectacular.generators import SchemaGenerator

        from apps.customfields import urls as cf_urls
        from apps.customfields.serializers import corps_definition_resserre
        regle = corps_definition_resserre()
        self.assertEqual(list(regle), ['anyOf'])
        self.assertEqual(len(regle['anyOf']), 4)
        schema = SchemaGenerator(patterns=[
            path('api/django/custom-fields/', include(cf_urls)),
        ]).get_schema(request=None, public=True)
        module = schema['components']['schemas']['CustomFieldDefRequest'][
            'properties']['module']
        self.assertNotIn('anyOf', module)
        motif = re.compile(module['pattern'])
        for ok in ('lead', 'devis', 'custom:a', 'custom:' + 'a' * 13):
            self.assertTrue(motif.fullmatch(ok), ok)
        for ko in ('', 'inconnu', 'custom:', 'custom:' + 'a' * 14, 'custom:\x00'):
            self.assertFalse(motif.fullmatch(ko), ko)
        # Ce que le motif annonce, le serveur l'accepte.
        for ok in ('lead', 'custom:' + 'a' * 13):
            resp = self.api.post('/api/django/custom-fields/definitions/', {
                'module': ok, 'code': 'm_' + ok[-3:].replace(':', 'x'),
                'libelle': 'L', 'type': 'text'}, format='json')
            self.assertEqual(resp.status_code, 201, (ok, resp.content))

    def test_scoped_to_company(self):
        other = Company.objects.create(slug='cf-other', nom='Autre')
        CustomFieldDef.objects.create(company=other, module='lead',
                                      code='x', libelle='X', type='text')
        resp = self.api.get('/api/django/custom-fields/definitions/?module=lead')
        self.assertEqual(resp.status_code, 200)
        rows = resp.data['results'] if isinstance(resp.data, dict) else resp.data
        self.assertEqual(len(rows), 0)  # rien de l'autre société


class TestCustomDataValidation(CFBase):
    def test_required_custom_field_enforced_and_stored(self):
        CustomFieldDef.objects.create(
            company=self.company, module='lead', code='budget',
            libelle='Budget', type='number', obligatoire=True)
        # Manquant → 400
        r1 = self.api.post('/api/django/crm/leads/',
                           {'nom': 'Sans budget'}, format='json')
        self.assertEqual(r1.status_code, 400)
        # Fourni → créé et stocké
        r2 = self.api.post('/api/django/crm/leads/',
                           {'nom': 'Avec budget', 'custom_data': {'budget': 50000}},
                           format='json')
        self.assertEqual(r2.status_code, 201, r2.data)
        lead = Lead.objects.get(id=r2.data['id'])
        self.assertEqual(lead.custom_data.get('budget'), 50000)

    def test_choice_validation(self):
        CustomFieldDef.objects.create(
            company=self.company, module='lead', code='canal_pub',
            libelle='Canal', type='choice', options=['A', 'B'])
        bad = self.api.post('/api/django/crm/leads/',
                            {'nom': 'X', 'custom_data': {'canal_pub': 'Z'}},
                            format='json')
        self.assertEqual(bad.status_code, 400)


class TestDefinitionsStrictes(CFBase):
    """CI #1000 fuzz — la définition valide son corps comme le schéma le publie :
    `formule: 0`, `code: 0`, `module: 0`, `conditions: 1` étaient acceptés ou
    convertis ; `?field_def=abc` levait ValueError (500)."""

    def _corps(self, **extra):
        return {'module': 'fournisseur', 'code': 'c0', 'libelle': 'L',
                'type': 'text', **extra}

    def test_types_faux_400(self):
        for extra in ({'formule': 0}, {'code': 0}, {'code': ' a '},
                      {'module': 0}, {'conditions': 1}, {'rollup_config': []},
                      {'ordre': '5'}, {'libelle': 0}):
            resp = self.api.post('/api/django/custom-fields/definitions/',
                                 self._corps(**extra), format='json')
            self.assertEqual(resp.status_code, 400, (extra, resp.content))
        self.assertFalse(CustomFieldDef.objects.filter(
            company=self.company).exists())

    def test_filtre_field_def_non_entier_400(self):
        resp = self.api.get(
            '/api/django/custom-fields/permissions-role/?field_def=abc')
        self.assertEqual(resp.status_code, 400, resp.content)

    def test_generer_corps_invalide_400(self):
        defi = CustomFieldDef.objects.create(
            company=self.company, module='lead', code='ia1', libelle='IA',
            type='ia', ia_prompt='Bonjour {nom}')
        url = f'/api/django/custom-fields/definitions/{defi.id}/generer/'
        for corps in ([1], {'record_id': 'x'}, {'record_id': 2 ** 40}, {}):
            resp = self.api.post(url, corps, format='json')
            self.assertEqual(resp.status_code, 400, (corps, resp.content))

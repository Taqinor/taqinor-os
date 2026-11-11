"""XPLT2 — mappings d'import sauvegardés + journal ImportJob/ImportJobRow +
CSV des lignes en échec + choix commit partiel vs rollback atomique."""
from apps.crm.models import Lead

from .models import ImportJob, ImportJobRow, ImportMapping
from .tests import ImportBase


class TestSavedMapping(ImportBase):
    def test_save_and_reapply_mapping_at_dry_run(self):
        resp = self.api.post('/api/django/imports/mapping/', {
            'target': 'leads', 'nom': 'Export CRM X',
            'mapping': {'Full Name': 'nom', 'Mail': 'email'},
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(ImportMapping.objects.filter(
            company=self.company, entity='leads', nom='Export CRM X').exists())

        # Colonnes que le mapping AUTOMATIQUE ne connaît pas du tout — seul le
        # mapping sauvegardé permet de les rapprocher.
        f = self._csv('Full Name,Mail\nKarim,karim@x.ma\n')
        resp2 = self.api.post('/api/django/imports/dry-run/', {
            'file': f, 'target': 'leads', 'mapping': 'Export CRM X',
        }, format='multipart')
        self.assertEqual(resp2.status_code, 200, resp2.data)
        self.assertEqual(resp2.data['mapping']['Full Name'], 'nom')
        self.assertEqual(resp2.data['mapping']['Mail'], 'email')
        self.assertEqual(resp2.data['apercu'][0]['nom'], 'Karim')

    def test_save_mapping_requires_dict(self):
        resp = self.api.post('/api/django/imports/mapping/', {
            'target': 'leads', 'nom': 'Bad', 'mapping': 'not-a-dict',
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_save_mapping_types_faux_400_jamais_500(self):
        # ENF11 (api-fuzz) : nom / target non texte, mapping vide ou à valeurs
        # non texte répondaient 500 ou passaient — tous 400 désormais.
        for corps in (
                {'target': 'leads', 'nom': [None, None], 'mapping': {'A': 'nom'}},
                {'target': ['leads'], 'nom': 'X', 'mapping': {'A': 'nom'}},
                {'target': 'leads', 'nom': 'X', 'mapping': {}},
                {'target': 'leads', 'nom': 'X', 'mapping': {'A': 3}}):
            resp = self.api.post(
                '/api/django/imports/mapping/', corps, format='json')
            self.assertEqual(resp.status_code, 400, (corps, resp.content))

    def test_save_mapping_exige_le_droit_de_la_cible(self):
        """ADRG103 — enregistrer un mapping exige le droit de la cible, comme
        l'aperçu et l'import : le mapping nommé d'un collègue reste intact."""
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient

        from apps.roles.models import Role
        from apps.roles.permissions_registre import CANONICAL_SYSTEM_ROLES
        roles = dict(CANONICAL_SYSTEM_ROLES)
        url = '/api/django/imports/mapping/'
        resp = self.api.post(url, {'target': 'leads', 'nom': 'Odoo',
                                   'mapping': {'Name': 'nom'}}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        corps = {'target': 'leads', 'nom': 'Odoo', 'mapping': {'Mail': 'email'}}
        for nom, attendu in (('Technicien', 403), ('Commercial', 200)):
            role = Role.objects.create(company=self.company, nom=f'{nom} 103',
                                       permissions=list(roles[nom]))
            client = APIClient()
            client.force_authenticate(get_user_model().objects.create_user(
                username=f'adrg103-{nom}', password='x',
                company=self.company, role=role))
            resp = client.post(url, corps, format='json')
            self.assertEqual(resp.status_code, attendu, resp.data)
            if attendu == 403:
                self.assertEqual(resp.data['code'], 'droit_manquant')
                self.assertEqual(ImportMapping.objects.get(
                    company=self.company, entity='leads', nom='Odoo').mapping,
                    {'Name': 'nom'})


class TestImportJobLog(ImportBase):
    def test_commit_creates_job_with_row_errors(self):
        Lead.objects.create(company=self.company, nom='Old', email='dup@x.ma')
        f = self._csv('Nom,Email\n'
                      'Alaoui,new@x.ma\n'
                      'Doublon,dup@x.ma\n'
                      ',\n')
        resp = self.api.post('/api/django/imports/commit/',
                             {'file': f, 'target': 'leads'}, format='multipart')
        self.assertEqual(resp.status_code, 200, resp.data)
        job_id = resp.data['job_id']
        job = ImportJob.objects.get(pk=job_id, company=self.company)
        self.assertEqual(job.statut, ImportJob.Statut.PARTIEL)
        self.assertEqual(job.created_count, 1)
        self.assertEqual(job.error_count, 2)
        rows = list(job.rows.order_by('ligne'))
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0].statut, ImportJobRow.Statut.OK)
        self.assertEqual(rows[1].statut, ImportJobRow.Statut.ERREUR)
        self.assertIn('doublon', rows[1].motif)
        self.assertEqual(rows[1].donnees.get('Email'), 'dup@x.ma')

    def test_erreurs_csv_contains_only_failed_rows_and_is_reimportable(self):
        Lead.objects.create(company=self.company, nom='Old', email='dup@x.ma')
        f = self._csv('Nom,Email\n'
                      'Alaoui,new@x.ma\n'
                      'Doublon,dup@x.ma\n')
        resp = self.api.post('/api/django/imports/commit/',
                             {'file': f, 'target': 'leads'}, format='multipart')
        job_id = resp.data['job_id']

        csv_resp = self.api.get(f'/api/django/imports/jobs/{job_id}/erreurs.csv')
        self.assertEqual(csv_resp.status_code, 200)
        body = csv_resp.content.decode('utf-8')
        self.assertIn('dup@x.ma', body)
        self.assertNotIn('new@x.ma', body)  # la ligne réussie n'apparaît pas

        # Le CSV d'échecs se ré-importe : on retire juste la colonne _motif
        # avant de le renvoyer au dry-run (comportement attendu côté client).
        reimport = self.api.post('/api/django/imports/dry-run/', {
            'file': self._csv(body), 'target': 'leads',
        }, format='multipart')
        self.assertEqual(reimport.status_code, 200, reimport.data)
        self.assertEqual(reimport.data['mapping'].get('Nom'), 'nom')

    def test_job_isolated_per_company(self):
        f = self._csv('Nom,Email\nA,a@a.ma\n')
        resp = self.api.post('/api/django/imports/commit/',
                             {'file': f, 'target': 'leads'}, format='multipart')
        job_id = resp.data['job_id']

        from authentication.models import Company
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import AccessToken
        User = get_user_model()
        other = Company.objects.create(slug='imp-co-3', nom='Imp Co 3')
        other_user = User.objects.create_user(
            username='other_u', password='x', role_legacy='responsable',
            company=other)
        other_api = APIClient()
        other_api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(other_user)}')

        resp2 = other_api.get(f'/api/django/imports/jobs/{job_id}/erreurs.csv')
        self.assertEqual(resp2.status_code, 404)

    def test_erreurs_csv_reserve_au_createur_ou_admin(self):
        """ADRG74 — le fichier des lignes en échec (lignes SOURCE) ne sort qu'à
        son créateur et à l'administrateur, jamais à un collègue."""
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient

        from apps.roles.models import Role
        from apps.roles.permissions_registre import (
            COMMERCIAL_PERMISSIONS, TECHNICIEN_PERMISSIONS)

        def api(nom, permissions=None, user=None):
            if user is None:
                role = Role.objects.create(
                    company=self.company, nom=f'{nom} ADRG74',
                    permissions=list(permissions))
                user = get_user_model().objects.create_user(
                    username=f'adrg74-{nom}', password='x',
                    company=self.company, role=role)
            client = APIClient()
            client.force_authenticate(user)
            return client

        Lead.objects.create(company=self.company, nom='Old', email='dup@x.ma')
        a = api('a', COMMERCIAL_PERMISSIONS)
        resp = a.post('/api/django/imports/commit/', {
            'file': self._csv('Nom,Email\nDoublon,dup@x.ma\n'),
            'target': 'leads'}, format='multipart')
        self.assertEqual(resp.status_code, 200, resp.data)
        url = f"/api/django/imports/jobs/{resp.data['job_id']}/erreurs.csv"
        for client in (api('b', COMMERCIAL_PERMISSIONS),
                       api('tech', TECHNICIEN_PERMISSIONS)):
            refus = client.get(url)
            self.assertEqual(refus.status_code, 404)
            self.assertEqual(refus.data['detail'], 'Import introuvable.')
        for client in (a, api('dir', user=self.directeur)):
            ok = client.get(url)
            self.assertEqual(ok.status_code, 200)
            self.assertIn('dup@x.ma', ok.content.decode('utf-8'))


class TestRollbackChoice(ImportBase):
    def test_default_partial_commit_keeps_successful_rows(self):
        f = self._csv('Nom,Email\nOk,ok@x.ma\n,\n')
        resp = self.api.post('/api/django/imports/commit/',
                             {'file': f, 'target': 'leads'}, format='multipart')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['created'], 1)
        self.assertTrue(Lead.objects.filter(
            company=self.company, email='ok@x.ma').exists())

    def test_rollback_on_error_discards_everything(self):
        f = self._csv('Nom,Email\nOk,ok2@x.ma\n,\n')
        resp = self.api.post('/api/django/imports/commit/', {
            'file': f, 'target': 'leads', 'rollback_on_error': 'true',
        }, format='multipart')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['created'], 0)
        self.assertEqual(resp.data['statut'], ImportJob.Statut.ECHEC)
        self.assertFalse(Lead.objects.filter(
            company=self.company, email='ok2@x.ma').exists())
        job = ImportJob.objects.get(pk=resp.data['job_id'])
        self.assertEqual(job.statut, ImportJob.Statut.ECHEC)
        self.assertEqual(job.created_count, 0)

    def test_save_mapping_corps_non_objet_nom_long_et_colonne_nulle(self):
        # CI #1000 fuzz : `[null, null]` levait AttributeError (500) ; un `nom`
        # nombre était converti en texte ; un `nom` > 150 caractères débordait
        # la colonne ; une colonne à caractère nul est refusée par jsonb (409 :
        # le schéma OpenAPI 3.0 ne borne pas les clés d'un objet).
        for corps in (
                [None, None],
                {'target': 'leads', 'nom': 0, 'mapping': {'A': 'nom'}},
                {'target': 'leads', 'nom': 'x' * 151, 'mapping': {'A': 'nom'}}):
            resp = self.api.post(
                '/api/django/imports/mapping/', corps, format='json')
            self.assertEqual(resp.status_code, 400, (corps, resp.content))
        resp = self.api.post(
            '/api/django/imports/mapping/',
            {'target': 'leads', 'nom': 'X', 'mapping': {'A\x00': 'nom'}},
            format='json')
        self.assertEqual(resp.status_code, 409, resp.content)

    def test_list_mappings_cible_vide_ou_inconnue_400(self):
        for cible in ('', 'AAA'):
            resp = self.api.get(f'/api/django/imports/mappings/?target={cible}')
            self.assertEqual(resp.status_code, 400, (cible, resp.content))
        self.assertEqual(
            self.api.get('/api/django/imports/mappings/?target=leads').status_code,
            200)

    def test_dry_run_et_commit_options_stricts_400(self):
        # CI #1000 fuzz : `ecraser={}` / `rollback_on_error={}` étaient lus
        # comme « faux » en silence alors que le schéma les publie booléens ;
        # `mode` hors liste (casse comprise) retombait sur le défaut.
        url_dry = '/api/django/imports/dry-run/'
        url_commit = '/api/django/imports/commit/'
        for url, extra in (
                (url_dry, {'ecraser': '{}'}), (url_dry, {'ecraser': '1'}),
                (url_dry, {'ecraser': ''}), (url_dry, {'mode': 'CREER'}),
                (url_commit, {'rollback_on_error': '{}'}),
                (url_commit, {'rollback_on_error': 'on'}),
                (url_commit, {'mode': ''})):
            corps = {'file': self._csv('Nom\nKarim\n'), 'target': 'leads', **extra}
            resp = self.api.post(url, corps, format='multipart')
            self.assertEqual(resp.status_code, 400, (url, extra, resp.content))

    def test_dry_run_et_commit_drapeaux_true_false_acceptes(self):
        for url, extra in (
                ('/api/django/imports/dry-run/', {'ecraser': 'False', 'mode': 'maj'}),
                ('/api/django/imports/commit/',
                 {'ecraser': 'true', 'rollback_on_error': 'False',
                  'mode': 'upsert'})):
            corps = {'file': self._csv('Nom\nKarim\n'), 'target': 'leads', **extra}
            resp = self.api.post(url, corps, format='multipart')
            self.assertEqual(resp.status_code, 200, (url, extra, resp.content))

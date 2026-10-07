"""AANA9 (C-AANA-004) — un mapping d'import enregistré n'accepte QUE des
champs de ``FIELD_MAPS[cible]``.

Rouge figé par l'audit (05/10) : un responsable de la société A enregistrait
``{'Cid': 'company_id', 'Nom': 'nom'}`` puis importait ``Nom,Cid\\nZed,<id B>``
en cible leads → ``_map_headers`` passait ``company_id`` tel quel en kwargs à
``Lead.objects.create`` : le lead naissait dans la société B
(``lead_in_B=True``). Correctif : 400 à l'enregistrement, et un mapping DÉJÀ
en base est filtré à l'application (la colonne retombe sur le mapping
automatique, donc ignorée)."""
from apps.crm.models import Lead
from authentication.models import Company

from .models import ImportMapping
from .tests import ImportBase


class TestMappingChampsAutorises(ImportBase):
    def setUp(self):
        super().setUp()
        self.company_b = Company.objects.get_or_create(
            slug='imp-co-b', defaults={'nom': 'Imp Co B'})[0]

    def _mapping_en_base(self, mapping, nom='Piege'):
        # Simule un mapping enregistré AVANT la validation (création ORM
        # directe : la vue le refuse désormais).
        return ImportMapping.objects.create(
            company=self.company, entity='leads', nom=nom, mapping=mapping)

    def test_mapping_company_id_refuse(self):
        resp = self.api.post('/api/django/imports/mapping/', {
            'target': 'leads', 'nom': 'Piege',
            'mapping': {'Cid': 'company_id', 'Nom': 'nom'},
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('company_id', resp.data['detail'])
        self.assertFalse(ImportMapping.objects.filter(
            company=self.company, nom='Piege').exists())

        # Mapping déjà en base : la colonne est ignorée, le lead naît dans A.
        self._mapping_en_base({'Cid': 'company_id', 'Nom': 'nom'})
        f = self._csv(f'Nom,Cid\nZed,{self.company_b.pk}\n')
        resp = self.api.post('/api/django/imports/commit/', {
            'file': f, 'target': 'leads', 'mapping': 'Piege',
        }, format='multipart')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['created'], 1, resp.data)
        self.assertFalse(Lead.all_objects.filter(
            company=self.company_b, nom='Zed').exists())
        lead = Lead.all_objects.get(nom='Zed')
        lead.refresh_from_db()
        self.assertEqual(lead.company_id, self.company.pk)

    def test_dry_run_ignore_le_champ_interdit(self):
        self._mapping_en_base({'Cid': 'company_id', 'Nom': 'nom'})
        f = self._csv(f'Nom,Cid\nZed,{self.company_b.pk}\n')
        resp = self.api.post('/api/django/imports/dry-run/', {
            'file': f, 'target': 'leads', 'mapping': 'Piege',
        }, format='multipart')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertNotIn('Cid', resp.data['mapping'])
        self.assertIn('Cid', resp.data['non_mappees'])

    def test_maj_ecraser_ne_change_pas_la_societe(self):
        lead = Lead.objects.create(
            company=self.company, nom='Alaoui', email='a@x.ma')
        self._mapping_en_base({'Cid': 'company_id', 'Mail': 'email'})
        f = self._csv(f'Mail,Cid\na@x.ma,{self.company_b.pk}\n')
        resp = self.api.post('/api/django/imports/commit/', {
            'file': f, 'target': 'leads', 'mapping': 'Piege',
            'mode': 'maj', 'ecraser': 'true',
        }, format='multipart')
        self.assertEqual(resp.status_code, 200, resp.data)
        lead.refresh_from_db()
        self.assertEqual(lead.company_id, self.company.pk)

    def test_owner_id_et_is_deleted_refuses(self):
        for champ in ('owner_id', 'is_deleted'):
            resp = self.api.post('/api/django/imports/mapping/', {
                'target': 'leads', 'nom': f'Piege {champ}',
                'mapping': {'X': champ, 'Nom': 'nom'},
            }, format='json')
            self.assertEqual(resp.status_code, 400, (champ, resp.data))

        self._mapping_en_base(
            {'Own': 'owner_id', 'Del': 'is_deleted', 'Nom': 'nom'})
        f = self._csv(f'Nom,Own,Del\nYasmine,{self.user.pk},true\n')
        resp = self.api.post('/api/django/imports/commit/', {
            'file': f, 'target': 'leads', 'mapping': 'Piege',
        }, format='multipart')
        self.assertEqual(resp.status_code, 200, resp.data)
        lead = Lead.all_objects.get(company=self.company, nom='Yasmine')
        self.assertFalse(lead.is_deleted)

    def test_mapping_valide_toujours_accepte(self):
        resp = self.api.post('/api/django/imports/mapping/', {
            'target': 'leads', 'nom': 'OK',
            'mapping': {'Full Name': 'nom', 'Mail': 'email'},
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

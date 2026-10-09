"""ENFP (D1) — ``?lead=`` est déclaré ET honoré sur la liste des visites."""
from apps.crm.models import Lead
from apps.visites.tests.test_visite_terrain import VisiteTerrainBase


class ListeFiltreLeadTests(VisiteTerrainBase):
    def test_filtre_lead(self):
        visite_id = self.creer_visite()
        autre = Lead.objects.create(company=self.company, nom='Autre dossier')
        resp = self.api.post('/api/django/visites/visites/',
                             {'lead': autre.id}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)

        resp = self.api.get('/api/django/visites/visites/',
                            {'lead': self.lead.id})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual([r['id'] for r in resp.data], [visite_id])

    def test_lead_invalide_ignore(self):
        self.creer_visite()
        resp = self.api.get('/api/django/visites/visites/', {'lead': 'abc'})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data), 1)

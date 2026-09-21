"""NTESG12 — Registre des parties prenantes ESG (matérialité simplifiée).

Critère d'acceptation : le CRUD fonctionne, la matrice place correctement les
parties prenantes selon leurs scores (influence/intérêt 1-5).
"""
from testkit.base import TenantAPITestCase

from apps.esg.models import PartiePrenanteESG


class PartiePrenanteESGApiTests(TenantAPITestCase):
    BASE = '/api/django/esg/parties-prenantes-esg/'

    def test_create_forces_company_server_side(self):
        r = self.client_as().post(
            self.BASE,
            {'nom': 'Client stratégique', 'categorie': 'client',
             'enjeux': 'Qualité, délais', 'influence': 5, 'interet': 4},
            format='json')
        self.assertEqual(r.status_code, 201, r.content)
        partie = PartiePrenanteESG.objects.get(id=r.data['id'])
        self.assertEqual(partie.company_id, self.company.id)

    def test_influence_out_of_range_refused(self):
        r = self.client_as().post(
            self.BASE,
            {'nom': 'X', 'categorie': 'fournisseur',
             'influence': 6, 'interet': 3}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_interet_below_range_refused(self):
        r = self.client_as().post(
            self.BASE,
            {'nom': 'X', 'categorie': 'fournisseur',
             'influence': 3, 'interet': 0}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_list_scoped_to_company(self):
        PartiePrenanteESG.objects.create(
            company=self.company, nom='Interne', categorie='collaborateur',
            influence=3, interet=3)
        PartiePrenanteESG.objects.create(
            company=self.other_company, nom='Autre', categorie='client',
            influence=3, interet=3)
        r = self.client_as().get(self.BASE)
        self.assertEqual(r.status_code, 200)
        noms = [row['nom'] for row in r.data.get('results', r.data)]
        self.assertIn('Interne', noms)
        self.assertNotIn('Autre', noms)

    def test_cross_tenant_isolation(self):
        foreign = PartiePrenanteESG.objects.create(
            company=self.other_company, nom='Autre', categorie='client',
            influence=3, interet=3)
        r = self.client_as().get(f'{self.BASE}{foreign.id}/')
        self.assertIn(r.status_code, (403, 404))

    def test_update_and_delete(self):
        partie = PartiePrenanteESG.objects.create(
            company=self.company, nom='Fournisseur clé',
            categorie='fournisseur', influence=4, interet=5)
        r = self.client_as().patch(
            f'{self.BASE}{partie.id}/', {'interet': 2}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        partie.refresh_from_db()
        self.assertEqual(partie.interet, 2)
        r_del = self.client_as().delete(f'{self.BASE}{partie.id}/')
        self.assertEqual(r_del.status_code, 204)
        self.assertFalse(
            PartiePrenanteESG.objects.filter(id=partie.id).exists())

"""ALEA11 — le ``lead`` d'une visite est figé après sa création.

Rejoue la sonde V4 LVIS-6 : un PATCH {lead: B} rendait 200 et la visite
quittait son dossier, ses photos (pièces jointes du lead A) restant derrière.
"""
from apps.crm.models import Lead
from apps.records.models import Attachment
from apps.visites.models import VisiteTerrain
from apps.visites.tests.test_visite_terrain import VisiteTerrainBase

MESSAGE = ("Le dossier d'une visite ne se change pas : créez une nouvelle "
           'visite.')


class LeadFigeTests(VisiteTerrainBase):
    def test_patch_lead_refuse(self):
        visite_id = self.creer_visite()
        for _ in range(2):
            resp = self.poster_photo(visite_id, 'general_facade')
            self.assertEqual(resp.status_code, 200, resp.data)
        autre = Lead.objects.create(company=self.company, nom='Autre dossier')

        resp = self.api.patch(f'/api/django/visites/visites/{visite_id}/',
                              {'lead': autre.id}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertEqual(resp.data['lead'], [MESSAGE])

        visite = VisiteTerrain.objects.get(pk=visite_id)
        self.assertEqual(visite.lead_id, self.lead.id)
        ids = list(visite.medias.values_list('attachment_id', flat=True))
        self.assertEqual(len(ids), 2)
        self.assertEqual(
            set(Attachment.objects.filter(pk__in=ids)
                .values_list('object_id', flat=True)), {self.lead.id})

    def test_patch_meme_lead_accepte(self):
        visite_id = self.creer_visite()
        resp = self.api.patch(f'/api/django/visites/visites/{visite_id}/',
                              {'lead': self.lead.id, 'notes': 'RAS'},
                              format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_creation_inchangee(self):
        resp = self.api.post('/api/django/visites/visites/',
                             {}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('lead', resp.data)
        etranger = self.api.post('/api/django/visites/visites/',
                                 {'lead': self.lead_etranger.id},
                                 format='json')
        self.assertEqual(etranger.status_code, 400, etranger.data)
        self.assertIn('lead', etranger.data)
        self.assertEqual(
            self.api.post('/api/django/visites/visites/',
                          {'lead': self.lead.id},
                          format='json').status_code, 201)

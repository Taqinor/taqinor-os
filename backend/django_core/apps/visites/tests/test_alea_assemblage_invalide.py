"""ALEA14 — une photo toiture ajoutée, supprimée ou renvoyée invalide
l'assemblage du toit (clé vidée, état ``aucun``, calage remis à zéro).

Rejoue la sonde V4 LVIS-10 run 2 : après renvoi + remplacement + revalidation
sans « Assembler », la fiche lead servait encore l'ANCIEN panorama. La tâche
Celery d'assemblage n'est pas déclenchée : on lit les champs du modèle.
"""
from apps.visites import selectors
from apps.visites.models import VisiteTerrain
from apps.visites.tests.test_visite_terrain import VisiteTerrainBase, auth

CALAGE = {'coins': [[33.57, -7.58], [33.57, -7.57],
                    [33.56, -7.57], [33.56, -7.58]]}
ANCIENNE_CLE = 'attachments/visites/panorama_ancien.png'
URL_LEAD = '/api/django/crm/leads/{}/photo-toit/'


class AssemblageInvalideTests(VisiteTerrainBase):
    def setUp(self):
        super().setUp()
        self.api_bureau = auth(self.bureau)

    def _assembler(self, visite_id):
        VisiteTerrain.objects.filter(pk=visite_id).update(
            photo_toit_key=ANCIENNE_CLE,
            assemblage_etat=VisiteTerrain.Assemblage.OK,
            texture_calage=CALAGE)

    def _assert_invalide(self, visite_id):
        visite = VisiteTerrain.objects.get(pk=visite_id)
        self.assertEqual(visite.photo_toit_key, '')
        self.assertEqual(visite.assemblage_etat,
                         VisiteTerrain.Assemblage.AUCUN)
        self.assertIsNone(visite.texture_calage)

    def _media(self, visite_id, slot):
        detail = self.api.get(f'/api/django/visites/visites/{visite_id}/')
        return next(s for cat in detail.data['checklist']
                    for s in cat['slots']
                    if s['code'] == slot)['photos'][0]['id']

    def _visite_validee_assemblee(self):
        visite_id = self.creer_visite()
        self.remplir(visite_id)
        fin = self.api.post(
            f'/api/django/visites/visites/{visite_id}/terminer/', {},
            format='json')
        self.assertEqual(fin.status_code, 200, fin.data)
        ok = self.api_bureau.post(
            f'/api/django/visites/visites/{visite_id}/valider/', {},
            format='json')
        self.assertEqual(ok.status_code, 200, ok.data)
        self._assembler(visite_id)
        self.assertEqual(
            self.api.get(URL_LEAD.format(self.lead.id)).data['url'],
            f'/api/django/visites/visites/{visite_id}/photo-toit/')
        return visite_id

    def test_renvoi_photo_toiture_invalide(self):
        visite_id = self._visite_validee_assemblee()
        media_id = self._media(visite_id, 'toiture_vue_generale')
        renvoi = self.api_bureau.post(
            f'/api/django/visites/visites/{visite_id}/renvoyer/',
            {'photos': [media_id], 'mesures': [], 'motif': 'Floue.'},
            format='json')
        self.assertEqual(renvoi.status_code, 200, renvoi.data)
        self._assert_invalide(visite_id)

        # Le terrain remplace, termine ; le BE revalide SANS réassembler.
        self.assertEqual(self.poster_photo(
            visite_id, 'toiture_vue_generale', nom='reprise.png').status_code,
            200)
        fin = self.api.post(
            f'/api/django/visites/visites/{visite_id}/terminer/', {},
            format='json')
        self.assertEqual(fin.status_code, 200, fin.data)
        ok = self.api_bureau.post(
            f'/api/django/visites/visites/{visite_id}/valider/', {},
            format='json')
        self.assertEqual(ok.status_code, 200, ok.data)

        self.assertIsNone(selectors.texture_toit_pour_lead(self.lead)['url'])
        resp = self.api.get(URL_LEAD.format(self.lead.id))
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIsNone(resp.data['url'])
        self._assert_invalide(visite_id)

    def test_upload_toiture_invalide(self):
        visite_id = self.creer_visite()
        self._assembler(visite_id)
        resp = self.poster_photo(visite_id, 'toiture_obstacles')
        self.assertEqual(resp.status_code, 200, resp.data)
        self._assert_invalide(visite_id)

    def test_delete_toiture_invalide(self):
        visite_id = self.creer_visite()
        self.assertEqual(self.poster_photo(
            visite_id, 'toiture_vue_generale').status_code, 200)
        self._assembler(visite_id)
        media_id = self._media(visite_id, 'toiture_vue_generale')
        resp = self.api.delete(
            f'/api/django/visites/visites/{visite_id}/photos/{media_id}/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self._assert_invalide(visite_id)

    def test_photo_hors_toiture_ne_touche_pas(self):
        visite_id = self.creer_visite()
        self.assertEqual(self.poster_photo(
            visite_id, 'general_facade').status_code, 200)
        self._assembler(visite_id)
        self.assertEqual(self.poster_photo(
            visite_id, 'tableau_ouvert').status_code, 200)
        media_id = self._media(visite_id, 'general_facade')
        self.assertEqual(self.api.delete(
            f'/api/django/visites/visites/{visite_id}/photos/{media_id}/'
        ).status_code, 200)
        visite = VisiteTerrain.objects.get(pk=visite_id)
        self.assertEqual(visite.photo_toit_key, ANCIENNE_CLE)
        self.assertEqual(visite.assemblage_etat, VisiteTerrain.Assemblage.OK)
        self.assertEqual(visite.texture_calage, CALAGE)

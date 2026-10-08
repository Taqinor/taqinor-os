"""ALEA12 — une nouvelle photo dans un slot « à refaire » REMPLACE l'ancienne.

Rejoue la sonde V4 LVIS-8 sur le chemin UI RÉEL (upload, sans DELETE
préalable) : aujourd'hui le slot reste ``a_refaire`` et « Terminer » rend 400.
"""
from apps.visites.models import VisiteMedia
from apps.visites.tests.test_visite_terrain import VisiteTerrainBase, auth

SLOT = 'toiture_vue_generale'


class PhotoRemplaceeTests(VisiteTerrainBase):
    def _slot(self, data, code=SLOT):
        return next(s for cat in data['checklist'] for s in cat['slots']
                    if s['code'] == code)

    def _visite_renvoyee(self):
        visite_id = self.creer_visite()
        self.remplir(visite_id)
        fin = self.api.post(
            f'/api/django/visites/visites/{visite_id}/terminer/', {},
            format='json')
        self.assertEqual(fin.status_code, 200, fin.data)
        detail = self.api.get(f'/api/django/visites/visites/{visite_id}/')
        media_id = self._slot(detail.data)['photos'][0]['id']
        renvoi = auth(self.bureau).post(
            f'/api/django/visites/visites/{visite_id}/renvoyer/',
            {'photos': [media_id], 'mesures': [], 'motif': 'x'},
            format='json')
        self.assertEqual(renvoi.status_code, 200, renvoi.data)
        self.assertEqual(self._slot(renvoi.data)['etat'], 'a_refaire')
        return visite_id, media_id

    def test_upload_remplace_photo_a_refaire(self):
        visite_id, ancien_id = self._visite_renvoyee()
        resp = self.poster_photo(visite_id, SLOT, nom='reprise.png')
        self.assertEqual(resp.status_code, 200, resp.data)
        slot = self._slot(resp.data)
        self.assertNotEqual(slot['etat'], 'a_refaire')
        self.assertEqual(slot['etat'], 'ok')
        types = {m['type'] for m in resp.data['completude']['manquants']}
        self.assertNotIn('photo_a_refaire', types)

        # Persistance : on rouvre la visite.
        detail = self.api.get(f'/api/django/visites/visites/{visite_id}/')
        slot = self._slot(detail.data)
        ids = [photo['id'] for photo in slot['photos']]
        self.assertNotIn(ancien_id, ids)
        self.assertFalse(any(photo['a_refaire'] for photo in slot['photos']))
        self.assertFalse(VisiteMedia.objects.filter(pk=ancien_id).exists())
        # La photo saine du slot (2 exigées) n'est pas touchée.
        self.assertEqual(len(ids), 2)

    def test_terminer_apres_remplacement(self):
        visite_id, _ = self._visite_renvoyee()
        self.assertEqual(
            self.poster_photo(visite_id, SLOT, nom='reprise.png').status_code,
            200)
        fin = self.api.post(
            f'/api/django/visites/visites/{visite_id}/terminer/', {},
            format='json')
        self.assertEqual(fin.status_code, 200, fin.data)

    def test_photo_saine_jamais_remplacee(self):
        visite_id = self.creer_visite()
        premiere = self.poster_photo(visite_id, 'general_facade')
        self.assertEqual(premiere.status_code, 200, premiere.data)
        seconde = self.poster_photo(visite_id, 'general_facade', nom='b.png')
        self.assertEqual(len(self._slot(seconde.data,
                                        'general_facade')['photos']), 2)

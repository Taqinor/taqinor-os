"""ENFP (D2) — vues sans fichier en JSON seul ; upload explicite."""
from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory
from rest_framework.views import APIView

from core.parseurs import (
    PARSEURS_JSON, PARSEURS_UPLOAD, JsonSeulementMixin, ListeJSON, ObjetJSON,
    ParseursUploadMixin)


class _VueJson(JsonSeulementMixin, APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        return Response({'actif': request.data.get('actif')})


class _VueUpload(ParseursUploadMixin, APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        return Response({'fichiers': sorted(request.FILES)})


factory = APIRequestFactory()


class ParseursTests(SimpleTestCase):
    def test_json_seul_refuse_multipart_415(self):
        reponse = _VueJson.as_view()(
            factory.post('/x/', {'actif': 'false'}, format='multipart'))
        self.assertEqual(reponse.status_code, 415)
        self.assertEqual(reponse.data['error']['code'],
                         'unsupported_media_type')

    def test_json_seul_accepte_json(self):
        reponse = _VueJson.as_view()(
            factory.post('/x/', {'actif': False}, format='json'))
        self.assertEqual(reponse.status_code, 200)
        self.assertIs(reponse.data['actif'], False)

    def test_upload_accepte_multipart(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        fichier = SimpleUploadedFile('a.txt', b'x', content_type='text/plain')
        reponse = _VueUpload.as_view()(
            factory.post('/x/', {'piece': fichier}, format='multipart'))
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse.data['fichiers'], ['piece'])

    def test_tuples_immuables(self):
        self.assertIsInstance(PARSEURS_JSON, tuple)
        self.assertIsInstance(PARSEURS_UPLOAD, tuple)


class JsonTypeTests(SimpleTestCase):
    """ERR-ENF11-FUZZ-CORE — ``null`` et le mauvais conteneur refusés."""

    def _valide(self, champ, valeur):
        try:
            return True, champ.run_validation(valeur)
        except ValidationError:
            return False, None

    def test_liste_json(self):
        self.assertEqual(self._valide(ListeJSON(), [1, 'a']), (True, [1, 'a']))
        for valeur in (None, {}, 'x', 0):
            self.assertFalse(self._valide(ListeJSON(), valeur)[0], valeur)
        self.assertTrue(self._valide(ListeJSON(allow_null=True), None)[0])

    def test_liste_json_type_d_element(self):
        self.assertTrue(self._valide(ListeJSON(element=str), ['a'])[0])
        self.assertFalse(self._valide(ListeJSON(element=str), [{}])[0])
        self.assertTrue(self._valide(ListeJSON(element=dict), [{}])[0])
        self.assertFalse(self._valide(ListeJSON(element=dict), [0])[0])

    def test_objet_json(self):
        self.assertTrue(self._valide(ObjetJSON(), {'a': 1})[0])
        for valeur in (None, [], 'x'):
            self.assertFalse(self._valide(ObjetJSON(), valeur)[0], valeur)

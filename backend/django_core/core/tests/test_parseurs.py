"""ENFP (D2) — vues sans fichier en JSON seul ; upload explicite."""
from django.test import SimpleTestCase
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory
from rest_framework.views import APIView

from core.parseurs import (
    PARSEURS_JSON, PARSEURS_UPLOAD, JsonSeulementMixin, ParseursUploadMixin)


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

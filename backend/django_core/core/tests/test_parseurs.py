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


class ParametresRequeteStrictsTests(SimpleTestCase):
    """ERR-ENF11-FUZZ-INSTALLATIONS — ``date_ou_400`` / ``nombre_ou_400`` :
    absent ou vide = valeur par défaut, toute autre forme illisible = 400."""

    def test_date_ou_400(self):
        from datetime import date

        from core.champs_stricts import date_ou_400
        self.assertIsNone(date_ou_400(None, 'd'))
        self.assertIsNone(date_ou_400('  ', 'd'))
        self.assertEqual(date_ou_400('2026-06-01', 'd'), date(2026, 6, 1))
        for mauvais in ('abc', '2026-6-1', '2026-02-30', '20260601'):
            with self.subTest(valeur=mauvais), self.assertRaises(
                    ValidationError) as ctx:
                date_ou_400(mauvais, 'debut')
            self.assertIn('debut', ctx.exception.detail)

    def test_nombre_ou_400(self):
        from core.champs_stricts import nombre_ou_400
        self.assertEqual(nombre_ou_400(None, 'h', defaut=8.0), 8.0)
        self.assertEqual(nombre_ou_400('', 'h', defaut=8.0), 8.0)
        self.assertEqual(nombre_ou_400('7.5', 'h'), 7.5)
        for mauvais in ('abc', 'nan', 'inf', '-inf'):
            with self.subTest(valeur=mauvais), self.assertRaises(
                    ValidationError):
                nombre_ou_400(mauvais, 'h')
        with self.assertRaises(ValidationError):
            nombre_ou_400('-1', 'h', mini=0)


class SchemaChampsStrictsTests(SimpleTestCase):
    """ENF11 — ce que le schéma publie pour une chaîne stricte (aucun
    caractère nul) et pour une clé primaire entière (au moins 1)."""

    def _schema(self, champ, direction='request'):
        from drf_spectacular.openapi import AutoSchema
        from drf_spectacular.plumbing import ComponentRegistry
        auto = AutoSchema()
        auto.registry = ComponentRegistry()
        return auto._map_serializer_field(champ, direction)

    def test_chaine_stricte_publie_un_motif_sans_nul(self):
        import re

        from core.champs_stricts import (
            MOTIF_NON_BLANC_SANS_NUL, MOTIF_SANS_NUL, ChaineStricte)
        # Blanc interdit (défaut DRF) : nul ET blanc refusés.
        schema = self._schema(ChaineStricte())
        self.assertEqual(schema['pattern'], MOTIF_NON_BLANC_SANS_NUL)
        self.assertTrue(re.search(MOTIF_NON_BLANC_SANS_NUL, 'texte é\n'))
        self.assertIsNone(re.search(MOTIF_NON_BLANC_SANS_NUL, 'a\x00b'))
        self.assertIsNone(re.search(MOTIF_NON_BLANC_SANS_NUL, '   '))
        # Blanc permis : seul le nul est refusé.
        schema = self._schema(ChaineStricte(allow_blank=True))
        self.assertEqual(schema['pattern'], MOTIF_SANS_NUL)
        self.assertTrue(re.search(MOTIF_SANS_NUL, ''))
        self.assertIsNone(re.search(MOTIF_SANS_NUL, 'a\x00b'))
        self.assertNotIn('pattern', self._schema(ChaineStricte(), 'response'))

    def test_cle_primaire_entiere_vaut_au_moins_un_en_requete(self):
        from django.contrib.auth import get_user_model
        from rest_framework import serializers
        champ = serializers.PrimaryKeyRelatedField(
            queryset=get_user_model().objects.all())
        self.assertEqual(self._schema(champ)['minimum'], 1)
        self.assertNotIn('minimum', self._schema(champ, 'response'))

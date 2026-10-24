"""ENFP (D1) — un paramètre de requête non déclaré au schéma OpenAPI est refusé.

Vues de test construites ici (aucune app domaine) : le contrôle est branché
sur ``APIView.initial`` par ``core.apps.CoreConfig.ready``, il couvre donc
toute vue DRF sans héritage particulier.
"""
from unittest import mock

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase, override_settings
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import filters, mixins, serializers, viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory
from rest_framework.views import APIView

from core import parametres_requete
from core.pagination import StandardPagination


class _TypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContentType
        fields = ['id', 'app_label', 'model']


class _TypesViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin,
                    viewsets.GenericViewSet):
    queryset = ContentType.objects.order_by('id')
    serializer_class = _TypeSerializer
    permission_classes = [AllowAny]
    authentication_classes = []
    pagination_class = StandardPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['model']
    ordering_fields = ['model']


class _VueDeclaree(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        parameters=[OpenApiParameter('periode', OpenApiTypes.STR)],
        responses={200: OpenApiTypes.OBJECT},
    )
    def get(self, request):
        return Response({'ok': True})


class _VueAuthentifiee(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: OpenApiTypes.OBJECT})
    def get(self, request):
        return Response({'ok': True})


class _VueHorsSchema(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(exclude=True)
    def get(self, request):
        return Response({'ok': True})


factory = APIRequestFactory()
liste = _TypesViewSet.as_view({'get': 'list'})
detail = _TypesViewSet.as_view({'get': 'retrieve'})


@override_settings(API_QUERY_PARAMS_STRICT=True)
class ParametresRequeteTests(TestCase):
    def setUp(self):
        parametres_requete.vider_cache()
        self.addCleanup(parametres_requete.vider_cache)

    def test_parametre_inconnu_refuse_400_nomme(self):
        reponse = _VueDeclaree.as_view()(
            factory.get('/x/', {'periode': '2026', 'zz': '1', 'aa': '2'}))
        self.assertEqual(reponse.status_code, 400)
        erreur = reponse.data['error']
        self.assertEqual(erreur['code'], 'unknown_query_parameter')
        self.assertEqual(sorted(erreur['fields']), ['aa', 'zz'])
        self.assertIn('request_id', erreur)
        self.assertIn('aa, zz', reponse.data['detail'])
        self.assertIn('aa, zz', erreur['message'])

    def test_methode_non_servie_405_prime(self):
        # ERR-ENF11-FUZZ-CORE — POST sur une vue GET seule : le 405 de DRF
        # n'est plus masqué par le 400 « paramètre non déclaré ».
        reponse = _VueDeclaree.as_view()(factory.post('/x/?zz=1'))
        self.assertEqual(reponse.status_code, 405)

    def test_parametre_declare_par_extend_schema_accepte(self):
        reponse = _VueDeclaree.as_view()(factory.get('/x/', {'periode': '2026'}))
        self.assertEqual(reponse.status_code, 200)

    def test_format_plateforme_accepte(self):
        reponse = _VueDeclaree.as_view()(factory.get('/x/', {'format': 'json'}))
        self.assertEqual(reponse.status_code, 200)

    def test_liste_recherche_tri_pagination_acceptes(self):
        reponse = liste(factory.get('/types/', {
            'search': 'user', 'ordering': 'model', 'page': '1',
            'page_size': '5'}))
        self.assertEqual(reponse.status_code, 200, reponse.data)

    def test_liste_filtre_inconnu_refuse(self):
        reponse = liste(factory.get('/types/', {'statut': 'x'}))
        self.assertEqual(reponse.status_code, 400)
        self.assertEqual(list(reponse.data['error']['fields']), ['statut'])

    def test_detail_ne_declare_pas_la_recherche(self):
        # Le schéma ne pose search/ordering/page que sur une LISTE.
        pk = ContentType.objects.order_by('id').first().pk
        reponse = detail(factory.get(f'/types/{pk}/', {'search': 'x'}), pk=pk)
        self.assertEqual(reponse.status_code, 400)
        self.assertEqual(list(reponse.data['error']['fields']), ['search'])

    def test_sans_query_string_aucun_calcul(self):
        with mock.patch.object(parametres_requete, '_calculer') as calcul:
            reponse = _VueDeclaree.as_view()(factory.get('/x/'))
        self.assertEqual(reponse.status_code, 200)
        calcul.assert_not_called()

    def test_anonyme_recoit_401_403_jamais_400(self):
        reponse = _VueAuthentifiee.as_view()(factory.get('/x/', {'zz': '1'}))
        self.assertIn(reponse.status_code, (401, 403))

    def test_vue_hors_schema_non_controlee(self):
        reponse = _VueHorsSchema.as_view()(factory.get('/x/', {'zz': '1'}))
        self.assertEqual(reponse.status_code, 200)

    def test_options_non_controle(self):
        reponse = _VueDeclaree.as_view()(factory.options('/x/?zz=1'))
        self.assertEqual(reponse.status_code, 200)

    def test_ensemble_calcule_une_fois_par_vue_action_methode(self):
        reel = parametres_requete._calculer
        with mock.patch.object(parametres_requete, '_calculer',
                               side_effect=reel) as calcul:
            for _ in range(3):
                liste(factory.get('/types/', {'search': 'a'}))
            self.assertEqual(calcul.call_count, 1)
            pk = ContentType.objects.order_by('id').first().pk
            detail(factory.get(f'/types/{pk}/', {'format': 'json'}), pk=pk)
            self.assertEqual(calcul.call_count, 2)
        cles = set(parametres_requete._CACHE)
        self.assertIn((_TypesViewSet, 'list', 'GET'), cles)
        self.assertIn((_TypesViewSet, 'retrieve', 'GET'), cles)
        autorises = parametres_requete._CACHE[(_TypesViewSet, 'list', 'GET')]
        self.assertTrue({'search', 'ordering', 'page', 'page_size',
                         'format'} <= autorises)

    @override_settings(API_QUERY_PARAMS_STRICT=False)
    def test_reglage_eteint_laisse_passer(self):
        reponse = _VueDeclaree.as_view()(factory.get('/x/', {'zz': '1'}))
        self.assertEqual(reponse.status_code, 200)

    def test_recherche_avec_caractere_nul_liste_vide_200(self):
        # ENF11 (nocturne 15/10) — ``search`` est publié en chaîne libre :
        # un terme portant ``\x00`` ne désigne aucune ligne (200, liste vide).
        reponse = liste(factory.get('/types/', {'search': 'us\x00er'}))
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(reponse.data['count'], 0)
        self.assertTrue(liste(factory.get('/types/', {'search': 'user'})).data['count'])

    def test_recherche_nul_sans_champs_de_recherche_sans_effet(self):
        from rest_framework.filters import SearchFilter
        qs = ContentType.objects.order_by('id')
        vue = mock.Mock(search_fields=None)
        requete = mock.Mock(query_params={'search': '\x00'})
        self.assertIs(SearchFilter().filter_queryset(requete, qs, vue), qs)
        self.assertTrue(getattr(SearchFilter.filter_queryset,
                                '_enf11_recherche_tolerante', False))

    def test_installation_idempotente(self):
        from rest_framework.views import APIView as Base
        avant = Base.initial
        parametres_requete.installer()
        self.assertIs(Base.initial, avant)
        self.assertTrue(getattr(Base.initial, '_enfp_parametres_requete', False))


class _VueTypee(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        parameters=[
            OpenApiParameter('document', OpenApiTypes.INT),
            OpenApiParameter('k', {'type': 'integer', 'minimum': 1,
                                   'maximum': 50}),
            OpenApiParameter('taux', OpenApiTypes.NUMBER),
            OpenApiParameter('mode', OpenApiTypes.STR, enum=['a', 'b']),
            OpenApiParameter('statut', OpenApiTypes.STR),
            OpenApiParameter('ids', {'type': 'array',
                                     'items': {'type': 'integer'}}),
        ],
        responses={200: OpenApiTypes.OBJECT},
    )
    def get(self, request):
        return Response({'ok': True})


@override_settings(API_QUERY_PARAMS_STRICT=True)
class ValeursParametresTests(TestCase):
    """api-fuzz-full 24/10/2026 — la VALEUR d'un paramètre déclaré suit son
    schéma publié : répété, entier/nombre illisible ou hors bornes, hors
    énumération -> 400 nommant le paramètre."""

    def setUp(self):
        parametres_requete.vider_cache()
        self.addCleanup(parametres_requete.vider_cache)

    def _get(self, chaine):
        return _VueTypee.as_view()(factory.get('/x/?' + chaine))

    def test_valeurs_conformes_acceptees(self):
        for chaine in ('document=12', 'document=-3', 'k=1', 'k=50',
                       'taux=2.5', 'mode=b', 'statut=libre', 'ids=1&ids=2'):
            self.assertEqual(self._get(chaine).status_code, 200, chaine)

    def test_valeurs_hors_schema_refusees_et_nommees(self):
        for chaine, nom in (
                ('document=', 'document'), ('document=abc', 'document'),
                ('document=1.5', 'document'), ('document=1&document=2', 'document'),
                ('k=0', 'k'), ('k=51', 'k'), ('taux=nan', 'taux'),
                ('taux=', 'taux'), ('mode=', 'mode'), ('mode=c', 'mode'),
                ('statut=a&statut=b', 'statut')):
            reponse = self._get(chaine)
            self.assertEqual(reponse.status_code, 400, chaine)
            self.assertIn(nom, reponse.data, chaine)
            self.assertEqual(reponse.data['error']['code'], 'validation_error')

    def test_reglage_eteint_valeurs_non_controlees(self):
        with override_settings(API_QUERY_PARAMS_STRICT=False):
            self.assertEqual(self._get('document=abc').status_code, 200)


class CaractereNulTests(TestCase):
    """api-fuzz-full 24/10/2026 — un caractère nul dans une valeur de query
    (PostgreSQL le refuse : 500) est un 400 nommé PARTOUT, réglage strict ou
    non ; ``search`` garde sa liste vide (200)."""

    def setUp(self):
        parametres_requete.vider_cache()
        self.addCleanup(parametres_requete.vider_cache)

    def test_nul_refuse_400_meme_hors_mode_strict(self):
        for strict in (True, False):
            with override_settings(API_QUERY_PARAMS_STRICT=strict):
                reponse = _VueTypee.as_view()(
                    factory.get('/x/', {'statut': 'a\x00b'}))
            self.assertEqual(reponse.status_code, 400, strict)
            self.assertEqual(list(reponse.data['error']['fields']), ['statut'])

    def test_recherche_a_nul_reste_tolere(self):
        reponse = liste(factory.get('/types/', {'search': 'us\x00er'}))
        self.assertEqual(reponse.status_code, 200, reponse.data)

    def test_motif_sans_nul_publie_sur_les_textes_de_query(self):
        from core.openapi_erreurs import (
            MOTIF_QUERY_SANS_NUL, aligner_motifs_sur_drf)
        doc = {'paths': {'/x/': {'get': {'parameters': [
            {'in': 'query', 'name': 'statut', 'schema': {'type': 'string'}},
            {'in': 'query', 'name': 'search', 'schema': {'type': 'string'}},
            {'in': 'query', 'name': 'mode',
             'schema': {'type': 'string', 'enum': ['a']}},
            {'in': 'query', 'name': 'jour',
             'schema': {'type': 'string', 'format': 'date'}},
            {'in': 'path', 'name': 'id', 'schema': {'type': 'string'}},
        ]}}}}
        params = aligner_motifs_sur_drf(doc)['paths']['/x/']['get']['parameters']
        self.assertEqual(params[0]['schema']['pattern'], MOTIF_QUERY_SANS_NUL)
        for param in params[1:]:
            self.assertNotIn('pattern', param['schema'], param['name'])

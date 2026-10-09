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

    def test_installation_idempotente(self):
        from rest_framework.views import APIView as Base
        avant = Base.initial
        parametres_requete.installer()
        self.assertIs(Base.initial, avant)
        self.assertTrue(getattr(Base.initial, '_enfp_parametres_requete', False))

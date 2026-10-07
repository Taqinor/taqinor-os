"""ACAL122 (C-ACAL-089) — la série horaire ne se charge ni ne se recopie hors
du calepinage courant : la LISTE diffère ``resultat`` ; les versions de
géométrie et les copies n'emportent aucun sac de simulation.

Calepinage simulé par les VRAIS écrivains (8 760 points), enregistré en
base ; versions et copie par les services réels ; rien n'est mocké.

Run :
    python manage.py test apps.calepinage.tests.test_acal_volume_resultat -v2
"""
import copy
import json

from rest_framework.test import APIRequestFactory, force_authenticate

from apps.calepinage.models import Calepinage, CalepinageVersion
from apps.calepinage.services.layout import enregistrer_layout
from apps.calepinage.services.variantes import dupliquer
from apps.calepinage.views.calepinages import CalepinageViewSet

from .acal_livrables_helpers import calepinage_simule_reel
from .test_api_liste import URL, BaseApiCalepinage

#: Borne de la tâche : la somme des ``resultat`` des versions reste < 10 Ko.
BORNE_OCTETS = 10 * 1024


class VolumeResultatTest(BaseApiCalepinage):
    def setUp(self):
        super().setUp()
        pivot = calepinage_simule_reel()
        self.assertGreater(len(json.dumps(pivot.resultat)), BORNE_OCTETS)
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='ACAL122',
            roof_layout=copy.deepcopy(pivot.roof_layout),
            resultat=copy.deepcopy(pivot.resultat),
            layout_hash=pivot.layout_hash or '')

    def _queryset_de_liste(self):
        requete = APIRequestFactory().get(URL)
        force_authenticate(requete, user=self.user)
        vue = CalepinageViewSet()
        # ``initialize_request`` d'un ViewSet relit l'action dans sa table.
        vue.action_map = {'get': 'list'}
        vue.action = 'list'
        vue.request = vue.initialize_request(requete)
        vue.request.user = self.user
        vue.format_kwarg = None
        vue.kwargs = {}
        return vue.filter_queryset(vue.get_queryset())

    def test_liste_ne_charge_pas_resultat(self):
        lignes = list(self._queryset_de_liste())
        self.assertIn(self.calepinage.pk, [ligne.pk for ligne in lignes])
        for ligne in lignes:
            self.assertIn('resultat', ligne.get_deferred_fields())
            self.assertNotIn('roof_layout', ligne.get_deferred_fields())
        # La liste HTTP sert toujours ses lignes (le sérialiseur ne lit pas
        # ``resultat``).
        reponse = self.api.get(URL)
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertIn(self.calepinage.pk,
                      [ligne['id'] for ligne in self._lignes(reponse)])

    def test_versions_et_copies_sans_serie_horaire(self):
        for rang in range(5):
            document = copy.deepcopy(self.calepinage.roof_layout)
            document['zones'][0]['geometry']['count'] += rang + 1
            enregistrer_layout(self.calepinage, document, user=self.user)
        versions = CalepinageVersion.objects.filter(
            calepinage=self.calepinage)
        self.assertEqual(versions.count(), 5)
        taille = sum(len(json.dumps(version.resultat))
                     for version in versions)
        self.assertLess(taille, BORNE_OCTETS)

        # ACAL187 (D-ACAL-12) — la source est un calepinage OUVERT de son
        # lead : la copie vise un AUTRE lead (sinon 409, une variante).
        copie = dupliquer(self.calepinage, user=self.user,
                          lead_id=self.lead_2.pk)
        copie = Calepinage.objects.get(pk=copie.pk)
        self.assertIsNone(copie.resultat)

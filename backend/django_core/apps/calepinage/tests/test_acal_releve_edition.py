"""ACAL204 — corriger (PATCH) et retirer (DELETE) un relevé de saisie.

Le relevé courant est relu (``releve_courant_id``) ; la correction met à jour
LE MÊME relevé (le nombre de lignes ne bouge pas, la géométrie résolue est
recalculée) ; un relevé repris d'une visite n'est ni modifiable ni
supprimable.

Run ::

    python manage.py test apps.calepinage.tests.test_acal_releve_edition -v 2
"""
from __future__ import annotations

from apps.calepinage.models import ProvenanceTerrain, ReleveTerrain
from apps.calepinage.services.releve import enregistrer_releve
from apps.calepinage.tests.test_releve_terrain import (
    CHAINE_FERMEE,
    CHAINE_FRDISI,
    HIER,
    BaseReleve,
)


class BaseEdition(BaseReleve):

    def setUp(self):
        super().setUp()
        self.base = ('/api/django/calepinage/calepinages/'
                     f'{self.calepinage.pk}/releve/')
        self.api = self._api()
        self.releve = enregistrer_releve(
            self.calepinage,
            {'releve_le': HIER.isoformat(), 'chaines': [CHAINE_FRDISI],
             'notes': 'avant'},
            user=self.user)

    def _url(self, releve=None):
        return f'{self.base}{(releve or self.releve).pk}/'


class PatchTest(BaseEdition):

    def test_patch_met_a_jour_le_meme_releve(self):
        avant = ReleveTerrain.objects.filter(
            calepinage=self.calepinage).count()
        reponse = self.api.patch(
            self._url(), {'notes': 'après', 'chaines': [CHAINE_FERMEE]},
            format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(
            ReleveTerrain.objects.filter(calepinage=self.calepinage).count(),
            avant)
        self.releve.refresh_from_db()
        self.assertEqual(self.releve.notes, 'après')
        self.assertEqual(reponse.data['releve']['id'], self.releve.pk)
        # La géométrie résolue est RECALCULÉE depuis les nouvelles chaînes.
        self.assertEqual(self.releve.geometrie['cotes_a_confirmer'], [])
        self.assertTrue(self.releve.geometrie['toutes_fermees'])

    def test_patch_partiel_ne_touche_que_les_cles_envoyees(self):
        self.api.patch(self._url(), {'notes': 'seulement'}, format='json')
        self.releve.refresh_from_db()
        self.assertEqual(self.releve.releve_le, HIER)
        self.assertEqual(self.releve.chaines[0]['nom'], 'façade')

    def test_azimut_sans_precision_refuse_au_patch(self):
        reponse = self.api.patch(
            self._url(), {'azimut_boussole_deg': 172.5}, format='json')
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('precision_azimut_deg', reponse.data)

    def test_azimut_avec_precision_accepte(self):
        reponse = self.api.patch(
            self._url(),
            {'azimut_boussole_deg': 172.5, 'precision_azimut_deg': 5},
            format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(reponse.data['releve']['azimut']['deg'], 172.5)

    def test_releve_de_visite_non_modifiable(self):
        visite = ReleveTerrain.objects.create(
            company=self.company, calepinage=self.calepinage,
            releve_le=HIER, provenance=ProvenanceTerrain.VISITE,
            visite_id=7)
        reponse = self.api.patch(self._url(visite), {'notes': 'x'},
                                 format='json')
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('releve', reponse.data)

    def test_releve_d_un_autre_calepinage_404(self):
        autre = enregistrer_releve(
            self.autre_calepinage,
            {'releve_le': HIER.isoformat(), 'chaines': []},
            user=self.user)
        reponse = self.api.patch(self._url(autre), {'notes': 'x'},
                                 format='json')
        self.assertEqual(reponse.status_code, 404)


class DeleteTest(BaseEdition):

    def test_delete_retire(self):
        reponse = self.api.delete(self._url())
        self.assertEqual(reponse.status_code, 204)
        self.assertFalse(
            ReleveTerrain.objects.filter(pk=self.releve.pk).exists())
        lecture = self.api.get(self.base)
        self.assertEqual(lecture.data['releves'], [])

    def test_releve_de_visite_non_supprimable(self):
        visite = ReleveTerrain.objects.create(
            company=self.company, calepinage=self.calepinage,
            releve_le=HIER, provenance=ProvenanceTerrain.VISITE,
            visite_id=8)
        reponse = self.api.delete(self._url(visite))
        self.assertEqual(reponse.status_code, 400)
        self.assertTrue(ReleveTerrain.objects.filter(pk=visite.pk).exists())


class CourantTest(BaseEdition):

    def test_releve_courant_id(self):
        lecture = self.api.get(self.base)
        self.assertEqual(lecture.data['releve_courant_id'], self.releve.pk)
        plus_recent = enregistrer_releve(
            self.calepinage,
            {'releve_le': HIER.isoformat(), 'chaines': []}, user=self.user)
        lecture = self.api.get(self.base)
        self.assertEqual(lecture.data['releve_courant_id'], plus_recent.pk)

    def test_un_releve_de_visite_n_est_jamais_le_courant(self):
        ReleveTerrain.objects.create(
            company=self.company, calepinage=self.calepinage,
            releve_le=HIER, provenance=ProvenanceTerrain.VISITE,
            visite_id=9)
        lecture = self.api.get(self.base)
        self.assertEqual(lecture.data['releve_courant_id'], self.releve.pk)

    def test_sans_releve_courant_null(self):
        self.releve.delete()
        self.assertIsNone(
            self.api.get(self.base).data['releve_courant_id'])

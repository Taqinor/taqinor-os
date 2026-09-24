"""CALX345 — le différentiel champ par champ entre deux versions.

CE QUE CE FICHIER PROUVE
------------------------
1. Sans base (``SimpleTestCase``) — l'action ``versions_diff`` est RÉELLEMENT
   rattachée au viewset pivot ; les écarts de l'exemple COMMITTÉ
   (``calepinage_versions_diff.json``, CALX333) sont RECALCULÉS depuis deux
   documents v2 en mémoire ; deux versions identiques ⇒ ``ecarts: []`` ; un
   champ absent des deux côtés est OMIS (jamais ``null`` contre ``null``) ;
   un champ présent d'un seul côté porte ``None`` du côté où il manque.
2. En base (``…EnBaseTest``, CI) — la porte HTTP (``contre`` absent ⇒ état
   courant ; version d'un autre calepinage ⇒ 404 ; ``contre`` illisible ⇒
   400 nommant le champ) et la note de chatter de la restauration, qui liste
   désormais les écarts.

Run :
    python manage.py test apps.calepinage.tests.test_calx345_diff_versions -v2
"""
from __future__ import annotations

import json
import pathlib
from types import SimpleNamespace

from django.contrib.contenttypes.models import ContentType
from django.test import SimpleTestCase

from apps.calepinage.models import Calepinage
from apps.calepinage.services.diff_versions import (
    LIBELLE_ETAT_COURANT, comparer_versions, etat_courant, texte_des_ecarts,
)
from apps.calepinage.services.layout import enregistrer_layout
from apps.calepinage.services.versions import restaurer_version
from apps.records.models import Activity

from .test_api_liste import BaseApiCalepinage, url_detail

RACINE = pathlib.Path(__file__).resolve().parent.parent
ECHANTILLON = RACINE / 'contract_samples' / 'calepinage_versions_diff.json'

A = 'ab' * 32
C = 'cd' * 32

#: Les deux documents v2 dont l'exemple committé est le différentiel.
LAYOUT_GAUCHE = {
    'result': {'panels': 12, 'kwc': 8.64},
    'zones': [
        {'id': 'PAN-A', 'label': 'Pan sud',
         'geometry': {'azimuthDeg': 180.0, 'tiltDeg': 15.0},
         'obstacles': [{'id': 'OBS-1'}, {'id': 'OBS-2'}]},
        {'id': 'PAN-B', 'geometry': {'azimuthDeg': 90.0, 'tiltDeg': 15.0}},
    ],
}
LAYOUT_DROITE = {
    'result': {'panels': 14, 'kwc': 10.08},
    'zones': [
        {'id': 'PAN-A', 'label': 'Pan sud',
         'geometry': {'azimuthDeg': 175.0, 'tiltDeg': 15.0},
         'obstacles': [{'id': 'OBS-1'}]},
        # L'inclinaison de PAN-B n'est plus saisie : présente d'UN côté.
        {'id': 'PAN-B', 'geometry': {'azimuthDeg': 90.0}},
    ],
}


def _contrat():
    return json.loads(ECHANTILLON.read_text(encoding='utf-8'))


def _version(pk, libelle, layout, empreinte, **autres):
    return SimpleNamespace(pk=pk, libelle=libelle, created_at=None,
                           roof_layout=layout, layout_hash=empreinte,
                           resultat=autres.get('resultat'))


def _actions():
    from apps.calepinage import urls  # noqa: F401
    from apps.calepinage.views.calepinages import CalepinageViewSet

    return CalepinageViewSet, {methode.__name__: methode
                               for methode
                               in CalepinageViewSet.get_extra_actions()}


class RoutageDiffTest(SimpleTestCase):
    """Sans route, l'écran de l'historique ne pourrait rien confronter."""

    def test_l_action_est_rattachee_en_sous_route_de_version(self):
        viewset, actions = _actions()
        self.assertIn('versions_diff', actions)
        action = actions['versions_diff']
        self.assertTrue(action.detail)
        self.assertEqual(action.url_path,
                         r'versions/(?P<version_id>[^/.]+)/diff')
        self.assertFalse(action.url_path.startswith('/'))
        self.assertEqual(set(action.mapping), {'get'})
        self.assertEqual(
            [garde.__name__ for garde in action.kwargs['permission_classes']],
            ['PeutVoirCalepinage'])
        self.assertEqual(getattr(viewset, 'versions_diff').__name__,
                         'versions_diff')

    def test_le_module_est_declare_dans_MODULES_RATTACHES(self):
        from apps.calepinage.views.rattachements import MODULES_RATTACHES

        self.assertIn('versions_diff', MODULES_RATTACHES)


class ContratDiffTest(SimpleTestCase):
    """L'exemple COMMITTÉ est RECALCULÉ, écart pour écart."""

    def setUp(self):
        contrat = _contrat()['exemple']
        self.gauche = _version(contrat['gauche']['id'],
                               contrat['gauche']['libelle'],
                               LAYOUT_GAUCHE, A)
        self.droite = _version(contrat['droite']['id'],
                               contrat['droite']['libelle'],
                               LAYOUT_DROITE, C)

    def test_le_chemin_declare_est_celui_de_l_action(self):
        self.assertEqual(
            _contrat()['endpoint'],
            'GET /api/django/calepinage/calepinages/<int:pk>/versions/'
            '<int:version_id>/diff/')

    def test_les_ecarts_de_l_exemple_sont_recalcules(self):
        obtenu = comparer_versions(self.gauche, self.droite)
        self.assertEqual(obtenu['ecarts'], _contrat()['exemple']['ecarts'])

    def test_la_forme_est_celle_du_contrat(self):
        obtenu = comparer_versions(self.gauche, self.droite)
        attendu = _contrat()['exemple']
        self.assertEqual(sorted(obtenu), sorted(attendu))
        self.assertEqual(sorted(obtenu['gauche']), sorted(attendu['gauche']))
        for cote in ('gauche', 'droite'):
            for cle in ('id', 'libelle', 'layout_hash'):
                self.assertEqual(obtenu[cote][cle], attendu[cote][cle])

    def test_un_champ_absent_des_deux_cotes_est_omis(self):
        champs = {e['champ']
                  for e in comparer_versions(self.gauche,
                                             self.droite)['ecarts']}
        for omis in _contrat()['omis_dans_l_exemple']:
            self.assertNotIn(omis, champs)
        # Aucun écart n'est jamais « null contre null ».
        for ecart in comparer_versions(self.gauche, self.droite)['ecarts']:
            self.assertFalse(ecart['avant'] is None
                             and ecart['apres'] is None, ecart)

    def test_present_d_un_seul_cote_porte_none_jamais_zero(self):
        ecarts = {e['champ']: e for e in comparer_versions(
            self.gauche, self.droite)['ecarts']}
        self.assertIsNone(ecarts['pan:PAN-B:inclinaison_deg']['apres'])

    def test_deux_versions_identiques_ne_rendent_aucun_ecart(self):
        jumelle = _version(13, 'Ré-enregistrement', LAYOUT_GAUCHE, A)
        self.assertEqual(comparer_versions(self.gauche, jumelle)['ecarts'],
                         [])
        self.assertEqual(_contrat()['exemple_identiques']['ecarts'], [])

    def test_l_etat_courant_n_a_pas_d_identifiant(self):
        calepinage = SimpleNamespace(roof_layout=LAYOUT_DROITE,
                                     layout_hash=C, resultat=None,
                                     version_moteur='', updated_at=None)
        obtenu = comparer_versions(self.gauche, etat_courant(calepinage))
        self.assertIsNone(obtenu['droite']['id'])
        self.assertEqual(obtenu['droite']['libelle'], LIBELLE_ETAT_COURANT)
        self.assertEqual(obtenu['ecarts'],
                         _contrat()['exemple_contre_courant']['ecarts'])

    def test_la_version_du_moteur_est_lue_dans_le_resultat_gele(self):
        gauche = _version(1, '', LAYOUT_GAUCHE, A,
                          resultat={'simulation': {'version_moteur': 'v1'}})
        droite = _version(2, '', LAYOUT_GAUCHE, A,
                          resultat={'simulation': {'version_moteur': 'v2'}})
        self.assertEqual(
            comparer_versions(gauche, droite)['ecarts'],
            [{'champ': 'version_moteur', 'libelle': 'Version du moteur',
              'avant': 'v1', 'apres': 'v2'}])

    def test_aucun_document_des_deux_cotes(self):
        vide = _version(1, '', None, '')
        self.assertEqual(comparer_versions(vide, _version(2, '', None, ''))
                         ['ecarts'], [])

    def test_texte_des_ecarts(self):
        self.assertEqual(texte_des_ecarts([]),
                         'Aucun écart sur les grandeurs comparées.')
        texte = texte_des_ecarts(_contrat()['exemple']['ecarts'])
        self.assertIn('Nombre de modules : 12 → 14', texte)
        self.assertIn('Inclinaison du pan « PAN-B » (°) : 15.0 → —', texte)
        # Une empreinte se lit par son préfixe, jamais en 64 caractères.
        self.assertNotIn(A, texte)


V1 = {'result': {'panels': 10, 'kwc': 7.2}, 'zones': [{'id': 'PAN-A'}]}
V2 = {'result': {'panels': 12, 'kwc': 8.64}, 'zones': [{'id': 'PAN-A'}]}


class DiffVersionsApiEnBaseTest(BaseApiCalepinage):
    """La porte HTTP et la note de restauration — exige la base (CI)."""

    def setUp(self):
        super().setUp()
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Villa A')
        enregistrer_layout(self.calepinage, V1, user=self.user)
        enregistrer_layout(self.calepinage, V2, user=self.user)
        self.v1, self.v2 = self.calepinage.versions.order_by('id')
        self.autre = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Villa B')
        enregistrer_layout(self.autre, V1, user=self.user)
        self.v_autre = self.autre.versions.first()

    def _url(self, version_id):
        return url_detail(self.calepinage.pk) + f'versions/{version_id}/diff/'

    def test_diff_entre_deux_versions(self):
        reponse = self.api.get(self._url(self.v1.pk), {'contre': self.v2.pk})
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(sorted(reponse.data), ['droite', 'ecarts', 'gauche'])
        ecarts = {e['champ']: e for e in reponse.data['ecarts']}
        self.assertEqual((ecarts['modules']['avant'],
                          ecarts['modules']['apres']), (10, 12))
        self.assertIn('layout_hash', ecarts)

    def test_une_version_contre_elle_meme_na_aucun_ecart(self):
        reponse = self.api.get(self._url(self.v1.pk), {'contre': self.v1.pk})
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(reponse.data['ecarts'], [])

    def test_sans_contre_la_droite_est_l_etat_courant(self):
        reponse = self.api.get(self._url(self.v1.pk))
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertIsNone(reponse.data['droite']['id'])

    def test_une_version_d_un_autre_calepinage_est_introuvable(self):
        self.assertEqual(self.api.get(self._url(self.v_autre.pk)).status_code,
                         404)
        reponse = self.api.get(self._url(self.v1.pk),
                               {'contre': self.v_autre.pk})
        self.assertEqual(reponse.status_code, 404)

    def test_contre_illisible_refuse_en_nommant_le_champ(self):
        reponse = self.api.get(self._url(self.v1.pk), {'contre': 'abc'})
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('contre', reponse.data)

    def test_un_calepinage_d_une_autre_societe_est_introuvable(self):
        reponse = self.api_autre.get(self._url(self.v1.pk))
        self.assertEqual(reponse.status_code, 404)

    def test_la_restauration_note_les_ecarts(self):
        restaurer_version(self.v1, user=self.user)
        entree = (Activity.objects
                  .filter(content_type=ContentType.objects.get_for_model(
                      Calepinage), object_id=self.calepinage.pk,
                      field='version')
                  .order_by('-id').first())
        self.assertIsNotNone(entree)
        self.assertEqual(entree.new_value, str(self.v1.pk))
        self.assertIn("Écarts avec l'état remplacé", entree.body)
        self.assertIn('Nombre de modules : 12 → 10', entree.body)

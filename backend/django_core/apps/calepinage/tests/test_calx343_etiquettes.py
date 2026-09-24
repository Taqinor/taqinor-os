"""CALX343 — les étiquettes libres d'un calepinage et leur filtre de liste.

CE QUE CE FICHIER PROUVE
------------------------
1. Sans base (``SimpleTestCase``) — l'action ``etiquettes`` est RÉELLEMENT
   rattachée au viewset pivot (GET/POST/DELETE, garde choisie PAR MÉTHODE),
   l'exemple COMMITTÉ (``calepinage_etiquettes.json``, CALX332) est affirmé
   — forme, exclusion NOMMÉE du tag système, et chaque refus documenté est
   EXACTEMENT la phrase que le service lève —, et un filtre absent ne filtre
   rien tandis qu'un filtre illisible est refusé en nommant ``etiquette``.
2. En base (``…EnBaseTest``, CI) — une étiquette d'une autre société est
   refusée en nommant le champ ; poser deux fois est idempotent (une ligne,
   une entrée de journal) ; le geste est journalisé par ``journal.noter`` ;
   un nom inconnu n'est JAMAIS créé à la volée ; le drapeau « modèle »
   n'apparaît jamais ; ``?etiquette=`` filtre en ET logique, absent il ne
   filtre rien.

Run :
    python manage.py test apps.calepinage.tests.test_calx343_etiquettes -v2
"""
from __future__ import annotations

import json
import pathlib
from unittest import mock

from django.contrib.contenttypes.models import ContentType
from django.test import SimpleTestCase

from apps.calepinage.models import Calepinage
from apps.calepinage.services.etiquettes import (
    EtiquetteRefusee, _resoudre, filtrer_par_etiquette,
)
from apps.calepinage.services.modeles import NOM_TAG_MODELE, marquer_modele
from apps.records.models import Activity, Tag, TaggedItem

from .test_api_liste import URL, BaseApiCalepinage, url_detail

RACINE = pathlib.Path(__file__).resolve().parent.parent
ECHANTILLON = RACINE / 'contract_samples' / 'calepinage_etiquettes.json'


def _contrat():
    return json.loads(ECHANTILLON.read_text(encoding='utf-8'))


def _actions():
    from apps.calepinage import urls  # noqa: F401
    from apps.calepinage.views.calepinages import CalepinageViewSet

    return CalepinageViewSet, {methode.__name__: methode
                               for methode
                               in CalepinageViewSet.get_extra_actions()}


class RoutageEtiquettesTest(SimpleTestCase):
    """Sans route, le composant d'étiquettes appellerait dans le vide."""

    def test_l_action_est_rattachee_avec_ses_trois_methodes(self):
        viewset, actions = _actions()
        self.assertIn('etiquettes', actions)
        action = actions['etiquettes']
        self.assertTrue(action.detail)
        self.assertEqual(action.url_path, 'etiquettes')
        self.assertEqual(set(action.mapping), {'get', 'post', 'delete'})
        self.assertEqual(getattr(viewset, 'etiquettes').__name__,
                         'etiquettes')

    def test_la_garde_est_choisie_par_methode(self):
        _viewset, actions = _actions()
        self.assertEqual(
            [garde.__name__
             for garde in actions['etiquettes'].kwargs['permission_classes']],
            ['PeutLireOuEcrireCalepinage'])

    def test_le_module_est_declare_dans_MODULES_RATTACHES(self):
        from apps.calepinage.views.rattachements import MODULES_RATTACHES

        self.assertIn('etiquettes', MODULES_RATTACHES)


class ContratEtiquettesTest(SimpleTestCase):
    """L'exemple COMMITTÉ, et les refus qu'il documente, mot pour mot."""

    def test_le_chemin_declare_est_celui_de_l_action(self):
        self.assertEqual(
            _contrat()['endpoint'],
            'GET /api/django/calepinage/calepinages/<int:pk>/etiquettes/')

    def test_la_forme_est_la_meme_dans_les_deux_etats(self):
        contrat = _contrat()
        for etat in ('exemple', 'exemple_vide'):
            self.assertEqual(sorted(contrat[etat]), ['etiquettes'], etat)
        for etiquette in contrat['exemple']['etiquettes']:
            self.assertEqual(sorted(etiquette), ['couleur', 'id', 'nom'])

    def test_le_tag_systeme_est_nomme_exclu_et_absent_de_l_exemple(self):
        contrat = _contrat()
        self.assertEqual(contrat['exclu_de_la_liste'], NOM_TAG_MODELE)
        self.assertIn(NOM_TAG_MODELE, contrat['pourquoi'])
        self.assertNotIn(
            NOM_TAG_MODELE,
            [e['nom'] for e in contrat['exemple']['etiquettes']])

    def _refus(self, company, corps):
        with self.assertRaises(EtiquetteRefusee) as refus:
            _resoudre(company, corps)
        return {refus.exception.champ: str(refus.exception)}

    def test_refus_sans_etiquette(self):
        self.assertEqual(self._refus(None, {}),
                         _contrat()['refus_sans_etiquette'])

    def test_refus_autre_societe_nomme_tag_id(self):
        # Société absente : aucune étiquette n'est trouvable, même message
        # qu'une étiquette d'une autre société (rien n'est révélé).
        self.assertEqual(self._refus(None, {'tag_id': 42}),
                         _contrat()['refus_autre_societe'])

    def test_refus_creation_a_la_volee_nomme_nom(self):
        self.assertEqual(self._refus(None, {'nom': 'Urgent'}),
                         _contrat()['refus_creation_a_la_volee'])

    def test_refus_tag_systeme(self):
        systeme = mock.Mock(nom=NOM_TAG_MODELE, pk=7)
        with mock.patch.object(Tag, 'objects') as gestionnaire:
            gestionnaire.filter.return_value.first.return_value = systeme
            self.assertEqual(self._refus(object(), {'tag_id': 7}),
                             _contrat()['refus_tag_systeme'])


class FiltreListeSansBaseTest(SimpleTestCase):
    """Un filtre absent ne filtre rien ; illisible, il est refusé NOMMÉ."""

    def test_absent_ou_vide_ne_filtre_rien(self):
        lignes = object()
        for valeurs in (None, [], [''], ['  ']):
            self.assertIs(filtrer_par_etiquette(lignes, valeurs), lignes)

    def test_illisible_refuse_en_nommant_etiquette(self):
        with self.assertRaises(EtiquetteRefusee) as refus:
            filtrer_par_etiquette(object(), ['abc'])
        attendu = _contrat()['filtre_liste']['refus_illisible']
        self.assertEqual({refus.exception.champ: str(refus.exception)},
                         attendu)

    def test_le_contrat_documente_un_filtre_repetable_en_et(self):
        filtre = _contrat()['filtre_liste']
        self.assertEqual(filtre['parametre'], 'etiquette')
        self.assertTrue(filtre['repetable'])
        self.assertEqual(filtre['logique'], 'ET')


class EtiquettesApiEnBaseTest(BaseApiCalepinage):
    """La porte HTTP et le filtre de liste — exige la base (CI)."""

    def setUp(self):
        super().setUp()
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Villa A')
        self.autre_calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Villa B')
        self.prioritaire = Tag.objects.create(
            company=self.company, nom='Prioritaire', couleur='#dc2626')
        self.visite = Tag.objects.create(company=self.company,
                                         nom='Visite technique faite')
        self.etranger = Tag.objects.create(company=self.autre,
                                           nom='Prioritaire')
        self.url = url_detail(self.calepinage.pk) + 'etiquettes/'

    def _poses(self, calepinage=None):
        cible = calepinage or self.calepinage
        return TaggedItem.objects.filter(
            content_type=ContentType.objects.get_for_model(Calepinage),
            object_id=cible.pk)

    def _notes(self):
        return Activity.objects.filter(
            content_type=ContentType.objects.get_for_model(Calepinage),
            object_id=self.calepinage.pk, kind=Activity.Kind.NOTE)

    def test_get_vide_a_la_forme_du_contrat(self):
        reponse = self.api.get(self.url)
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(reponse.data, _contrat()['exemple_vide'])

    def test_poser_rend_la_liste_a_jour_triee_par_nom(self):
        self.api.post(self.url, {'tag_id': self.visite.pk}, format='json')
        reponse = self.api.post(self.url, {'nom': 'Prioritaire'},
                                format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(
            reponse.data['etiquettes'],
            [{'id': self.prioritaire.pk, 'nom': 'Prioritaire',
              'couleur': '#dc2626'},
             {'id': self.visite.pk, 'nom': 'Visite technique faite',
              'couleur': ''}])

    def test_poser_deux_fois_est_idempotent_et_journalise_une_fois(self):
        for _ in range(2):
            reponse = self.api.post(self.url, {'tag_id': self.prioritaire.pk},
                                    format='json')
            self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(self._poses().count(), 1)
        notes = list(self._notes())
        self.assertEqual(len(notes), 1)
        self.assertIn('Prioritaire', notes[0].body)
        self.assertEqual(notes[0].created_by_id, self.user.pk)

    def test_une_etiquette_d_une_autre_societe_est_refusee_nommee(self):
        reponse = self.api.post(self.url, {'tag_id': self.etranger.pk},
                                format='json')
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('tag_id', reponse.data)
        self.assertEqual(self._poses().count(), 0)

    def test_un_nom_inconnu_n_est_jamais_cree(self):
        avant = Tag.objects.count()
        reponse = self.api.post(self.url, {'nom': 'Urgent'}, format='json')
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('nom', reponse.data)
        self.assertEqual(Tag.objects.count(), avant)

    def test_le_drapeau_modele_n_apparait_jamais_et_ne_se_pose_pas(self):
        marquer_modele(self.calepinage, user=self.user)
        reponse = self.api.get(self.url)
        self.assertEqual(reponse.data['etiquettes'], [])
        systeme = Tag.objects.get(company=self.company, nom=NOM_TAG_MODELE)
        refus = self.api.delete(self.url, {'tag_id': systeme.pk},
                                format='json')
        self.assertEqual(refus.status_code, 400)
        self.assertIn('tag_id', refus.data)

    def test_retirer_retire_et_journalise(self):
        self.api.post(self.url, {'tag_id': self.prioritaire.pk},
                      format='json')
        reponse = self.api.delete(self.url, {'tag_id': self.prioritaire.pk},
                                  format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(reponse.data['etiquettes'], [])
        self.assertTrue(self._notes().filter(body__contains='retirée')
                        .exists())

    def test_retirer_par_parametre_de_requete(self):
        self.api.post(self.url, {'tag_id': self.prioritaire.pk},
                      format='json')
        reponse = self.api.delete(f'{self.url}?tag_id={self.prioritaire.pk}')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(self._poses().count(), 0)

    def test_un_calepinage_d_une_autre_societe_est_introuvable(self):
        reponse = self.api_autre.get(self.url)
        self.assertEqual(reponse.status_code, 404)

    def _ids(self, params):
        reponse = self.api.get(URL, params)
        self.assertEqual(reponse.status_code, 200, reponse.data)
        return {ligne['id'] for ligne in self._lignes(reponse)}

    def test_filtre_absent_ne_filtre_rien(self):
        self.api.post(self.url, {'tag_id': self.prioritaire.pk},
                      format='json')
        self.assertEqual(self._ids({}),
                         {self.calepinage.pk, self.autre_calepinage.pk})

    def test_filtre_repetable_en_et_logique(self):
        url_b = url_detail(self.autre_calepinage.pk) + 'etiquettes/'
        self.api.post(self.url, {'tag_id': self.prioritaire.pk},
                      format='json')
        self.api.post(self.url, {'tag_id': self.visite.pk}, format='json')
        self.api.post(url_b, {'tag_id': self.prioritaire.pk}, format='json')
        self.assertEqual(self._ids({'etiquette': self.prioritaire.pk}),
                         {self.calepinage.pk, self.autre_calepinage.pk})
        self.assertEqual(
            self._ids({'etiquette': [self.prioritaire.pk, self.visite.pk]}),
            {self.calepinage.pk})

    def test_filtre_illisible_refuse_en_nommant_le_champ(self):
        reponse = self.api.get(URL, {'etiquette': 'abc'})
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('etiquette', reponse.data)

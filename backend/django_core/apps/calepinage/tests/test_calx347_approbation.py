"""CALX347 — le rôle relecteur et la décision d'approbation d'un calepinage.

Ce qui est prouvé ici :

* le code ``calepinage_approuver`` est au CATALOGUE, rattaché au module
  ``calepinage``, non élevé, DISTINCT des deux codes du palier ventes, et à
  ZÉRO titulaire par défaut hors Directeur/Administrateur (héritage du
  catalogue) — décision tranchée du 21/09/2026 ;
* la décision vit dans le champ DÉDIÉ ``Calepinage.approbation`` (migration
  ``0013``), jamais dans ``resultat`` ;
* une décision inconnue est refusée en nommant ``decision``, un refus sans
  motif en nommant ``motif`` — et RIEN n'est écrit ;
* une conception qui porte une hauteur OpenStreetMap (``hauteurSuggestion``)
  ou une pente LiDAR (``pitchSuggestion``) NON acceptée n'est pas
  approuvable : le refus nomme le champ, et la liste complète est servie ;
  la même conception, suggestions acceptées (ou refusées par un humain),
  s'approuve ;
* en HTTP : ``GET`` pour un lecteur, ``POST`` 403 pour un porteur de
  ``calepinage_gerer`` seul, 200 pour un porteur du code d'approbation, note
  de chatter écrite à chaque décision, 404 pour une autre société ;
* la réponse suit le contrat committé ``calepinage_approbation.json``
  (CALX334) quand il est présent sur la branche.

Les classes ``…EnBase`` exigent l'ORM : la CI est leur gate.

Run :
    python manage.py test apps.calepinage.tests.test_calx347_approbation -v2
"""
import copy
import datetime
import json
import pathlib
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from apps.calepinage.permissions import (
    CAL_APPROUVER, CAL_GERER, CAL_VOIR, CODES, PeutApprouverCalepinage,
    PeutLireOuApprouverCalepinage,
)
from apps.calepinage.services import approbation as service
from apps.calepinage.services.lidar_ign import accepter_suggestion
from apps.roles.models import (
    ALL_PERMISSIONS, CANONICAL_SYSTEM_ROLES, ELEVATED_PERMISSIONS,
    PERMISSION_MODULE,
)

RACINE_APP = pathlib.Path(__file__).resolve().parents[1]
CONTRAT = RACINE_APP / 'contract_samples' / 'calepinage_approbation.json'

MAINTENANT = datetime.datetime(2026, 9, 24, 9, 30,
                               tzinfo=datetime.timezone.utc)


def conception(*, pente='suggeree', hauteur='suggeree'):
    """Un document avec UNE pente LiDAR et UNE hauteur OSM suggérées."""
    return {
        'zones': [{
            'id': 'z1', 'label': 'Pan Sud', 'pitchDeg': 12,
            'pitchSuggestion': {
                'zoneId': 'z1', 'pitchDeg': 14.5, 'facingAzimuthDeg': 180,
                'source': 'IGN — RGE ALTI® / LiDAR HD',
                'suggestedAt': '2026-09-20T10:00:00+00:00',
                'status': pente,
            },
        }],
        'buildings': [{
            'id': 'bat-1', 'label': 'Villa', 'hauteurM': None,
            'hauteurSuggestion': {
                'hauteurM': 7.5, 'source': 'openstreetmap',
                'provenance': 'osm:height', 'status': hauteur,
            },
        }],
    }


def faux_calepinage(layout=None, approbation=None):
    return SimpleNamespace(pk=None, company=None, company_id=None,
                           roof_layout=layout, approbation=approbation)


class CatalogueApprobationTest(SimpleTestCase):
    """Le code existe, une fois, au bon module, sans titulaire métier."""

    def test_code_au_catalogue_une_seule_fois(self):
        self.assertEqual(CAL_APPROUVER, 'calepinage_approuver')
        self.assertEqual(ALL_PERMISSIONS.count(CAL_APPROUVER), 1)

    def test_rattache_au_module_calepinage(self):
        self.assertEqual(PERMISSION_MODULE.get(CAL_APPROUVER), 'calepinage')

    def test_distinct_du_palier_ventes_et_non_eleve(self):
        self.assertNotIn(CAL_APPROUVER, CODES)
        self.assertNotIn(CAL_APPROUVER, ELEVATED_PERMISSIONS)

    def test_zero_titulaire_hors_direction(self):
        """Seuls Directeur/Administrateur le portent — par le catalogue."""
        for nom, permissions in CANONICAL_SYSTEM_ROLES:
            with self.subTest(role=nom):
                attendu = nom in ('Directeur', 'Administrateur')
                self.assertEqual(CAL_APPROUVER in permissions, attendu, nom)

    def test_gardes_portent_le_bon_code(self):
        self.assertEqual(PeutApprouverCalepinage.code, CAL_APPROUVER)

    def test_garde_mixte_choisit_par_methode(self):
        garde = PeutLireOuApprouverCalepinage()
        user = mock.Mock(is_authenticated=True, portee='interne',
                         is_superuser=False)
        user.has_erp_permission.side_effect = (
            lambda code: code in (CAL_VOIR, CAL_GERER))
        lecture = SimpleNamespace(method='GET', user=user)
        ecriture = SimpleNamespace(method='POST', user=user)
        self.assertTrue(garde.has_permission(lecture, None))
        self.assertFalse(
            garde.has_permission(ecriture, None),
            "Un porteur de calepinage_gerer SEUL ne décide pas.")
        user.has_erp_permission.side_effect = (
            lambda code: code == CAL_APPROUVER)
        self.assertTrue(garde.has_permission(ecriture, None))

    def test_aucun_litteral_du_code_hors_permissions(self):
        coupables = []
        for fichier in RACINE_APP.rglob('*.py'):
            if fichier.name == 'permissions.py' or 'tests' in fichier.parts:
                continue
            texte = fichier.read_text(encoding='utf-8')
            if f"'{CAL_APPROUVER}'" in texte or f'"{CAL_APPROUVER}"' in texte:
                coupables.append(fichier.name)
        self.assertEqual(coupables, [])


class SuggestionsEnAttenteTest(SimpleTestCase):
    """Les valeurs automatiques non acceptées, nommées champ par champ."""

    def test_document_vide_ou_illisible(self):
        self.assertEqual(service.suggestions_en_attente(None), [])
        self.assertEqual(service.suggestions_en_attente([]), [])
        self.assertEqual(service.suggestions_en_attente({'zones': 'x'}), [])

    def test_pente_lidar_et_hauteur_osm_en_attente(self):
        en_attente = service.suggestions_en_attente(conception())
        champs = [ligne['champ'] for ligne in en_attente]
        self.assertEqual(champs, ['zones[z1].pitchDeg',
                                  'buildings[bat-1].hauteurM'])
        osm = en_attente[1]
        self.assertEqual(osm['source'], 'openstreetmap')
        self.assertIn('Villa', osm['libelle'])

    def test_suggestions_decidees_ne_bloquent_plus(self):
        document = conception(pente='refusee', hauteur='validee')
        self.assertEqual(service.suggestions_en_attente(document), [])

    def test_acceptation_lidar_reelle_vaut_decision(self):
        document = conception(hauteur='validee')
        pan = document['zones'][0]
        accepter_suggestion(pan, pan['pitchSuggestion'],
                            maintenant=MAINTENANT)
        self.assertEqual(service.suggestions_en_attente(document), [])

    def test_suggestion_sans_statut_reste_en_attente(self):
        document = conception(hauteur='validee')
        del document['zones'][0]['pitchSuggestion']['status']
        self.assertEqual(
            [ligne['champ']
             for ligne in service.suggestions_en_attente(document)],
            ['zones[z1].pitchDeg'])

    def test_source_automatique_inconnue_tenue_par_sa_cle(self):
        document = {'buildings': [{
            'id': 'b2', 'azimutSuggestion': {'status': 'suggeree'}}]}
        self.assertEqual(
            [ligne['champ']
             for ligne in service.suggestions_en_attente(document)],
            ['buildings[b2].azimutSuggestion'])


class DecisionRefuseeSansEcritureTest(SimpleTestCase):
    """Les trois refus nomment leur champ et n'écrivent RIEN."""

    def _decider(self, calepinage, **kwargs):
        with mock.patch.object(calepinage, 'save', create=True) as save:
            with self.assertRaises(service.ApprobationRefusee) as refus:
                service.decider(calepinage, maintenant=MAINTENANT, **kwargs)
        save.assert_not_called()
        self.assertIsNone(calepinage.approbation)
        return refus.exception

    def test_decision_inconnue(self):
        refus = self._decider(faux_calepinage(), decision='valide')
        self.assertEqual(refus.champ, 'decision')
        self.assertIn('Décision', str(refus))

    def test_refus_sans_motif(self):
        refus = self._decider(faux_calepinage(), decision='refuse',
                              motif='   ')
        self.assertEqual(refus.champ, 'motif')
        self.assertIn('Motif', str(refus))

    def test_hauteur_osm_non_acceptee(self):
        document = conception(pente='validee')
        refus = self._decider(faux_calepinage(document), decision='approuve')
        self.assertEqual(refus.champ, 'buildings[bat-1].hauteurM')
        self.assertIn('buildings[bat-1].hauteurM', str(refus))
        self.assertEqual([ligne['champ'] for ligne in refus.en_attente],
                         ['buildings[bat-1].hauteurM'])

    def test_un_refus_humain_n_attend_pas_les_suggestions(self):
        """Refuser une conception reste possible avec des suggestions."""
        calepinage = faux_calepinage(conception())
        calepinage.save = mock.Mock()
        with mock.patch('apps.calepinage.services.journal.noter'), \
                mock.patch.object(service, 'etat_approbation',
                                  side_effect=lambda c: c.approbation):
            etat = service.decider(calepinage, decision='refuse',
                                   motif='Pente à vérifier',
                                   maintenant=MAINTENANT)
        self.assertEqual(etat['etat'], 'refuse')
        self.assertEqual(etat['decide_le'], MAINTENANT.isoformat())
        calepinage.save.assert_called_once_with(
            update_fields=['approbation', 'updated_at'])


class FormeDeLaReponseTest(SimpleTestCase):
    """``etat_approbation`` : état vide publié tel quel, et contrat CALX334."""

    def _etat(self, calepinage):
        with mock.patch.object(service, 'approbation_exigee',
                               return_value=False):
            return service.etat_approbation(calepinage)

    def test_personne_n_a_decide(self):
        etat = self._etat(faux_calepinage())
        self.assertEqual(etat, {'etat': None, 'decide_par': None,
                                'decide_le': None, 'motif': '',
                                'exigee': False})

    def test_etat_illisible_publie_comme_non_decide(self):
        etat = self._etat(faux_calepinage(approbation={'etat': 'peut-etre'}))
        self.assertIsNone(etat['etat'])

    def test_les_cles_du_contrat_committe(self):
        if not CONTRAT.exists():
            self.skipTest('contrat CALX334 absent de cette branche — la '
                          'lane contrats le livre au fold.')
        exemple = json.loads(CONTRAT.read_text(encoding='utf-8'))['exemple']
        self.assertEqual(sorted(self._etat(faux_calepinage())),
                         sorted(exemple))


# ── HTTP — exige l'ORM (la CI est la gate de ces classes) ─────────────────

from django.contrib.auth import get_user_model  # noqa: E402
from django.contrib.contenttypes.models import ContentType  # noqa: E402

from apps.calepinage.models import Calepinage  # noqa: E402
from apps.records.models import Activity  # noqa: E402
from apps.roles.models import Role  # noqa: E402

from .test_api_liste import BaseApiCalepinage, url_detail  # noqa: E402

User = get_user_model()


def url_approbation(pk):
    return f'{url_detail(pk)}approbation/'


class ActionApprobationEnBase(BaseApiCalepinage):
    """La porte HTTP ``approbation/``."""

    def setUp(self):
        super().setUp()
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Villa Anfa',
            roof_layout=conception(pente='validee', hauteur='validee'))

    def _compte(self, identifiant, permissions):
        role = Role.objects.create(company=self.company, nom=identifiant,
                                   permissions=list(permissions))
        user = User.objects.create_user(
            username=identifiant, password='x', company=self.company,
            role=role)
        return self._client(user), user

    def _notes(self):
        return Activity.objects.filter(
            content_type=ContentType.objects.get_for_model(Calepinage),
            object_id=self.calepinage.pk)

    def test_get_etat_vide(self):
        reponse = self.api.get(url_approbation(self.calepinage.pk))
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertIsNone(reponse.data['etat'])
        self.assertIsNone(reponse.data['decide_par'])
        self.assertFalse(reponse.data['exigee'])

    def test_lecteur_lit_mais_ne_decide_pas(self):
        api, _user = self._compte('calx347_lecteur', [CAL_VOIR])
        self.assertEqual(
            api.get(url_approbation(self.calepinage.pk)).status_code, 200)
        reponse = api.post(url_approbation(self.calepinage.pk),
                           {'decision': 'approuve'}, format='json')
        self.assertEqual(reponse.status_code, 403)

    def test_porteur_de_gerer_seul_recoit_403(self):
        api, _user = self._compte('calx347_redacteur', [CAL_VOIR, CAL_GERER])
        reponse = api.post(url_approbation(self.calepinage.pk),
                           {'decision': 'approuve'}, format='json')
        self.assertEqual(reponse.status_code, 403)
        self.calepinage.refresh_from_db()
        self.assertIsNone(self.calepinage.approbation)

    def test_relecteur_approuve_et_le_chatter_le_dit(self):
        api, relecteur = self._compte('calx347_relecteur',
                                      [CAL_VOIR, CAL_APPROUVER])
        avant = self._notes().count()
        reponse = api.post(url_approbation(self.calepinage.pk),
                           {'decision': 'approuve'}, format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(reponse.data['etat'], 'approuve')
        self.assertEqual(reponse.data['decide_par']['id'], relecteur.pk)
        self.calepinage.refresh_from_db()
        self.assertEqual(self.calepinage.approbation['etat'], 'approuve')
        self.assertNotIn('approbation', self.calepinage.resultat or {})
        self.assertEqual(self._notes().count(), avant + 1)

    def test_refus_sans_motif_nomme_le_champ(self):
        reponse = self.api.post(url_approbation(self.calepinage.pk),
                                {'decision': 'refuse'}, format='json')
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('motif', reponse.data)
        self.calepinage.refresh_from_db()
        self.assertIsNone(self.calepinage.approbation)

    def test_refus_motive_est_enregistre(self):
        reponse = self.api.post(
            url_approbation(self.calepinage.pk),
            {'decision': 'refuse', 'motif': 'Retrait de rive non respecté'},
            format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(reponse.data['etat'], 'refuse')
        self.assertEqual(reponse.data['motif'],
                         'Retrait de rive non respecté')

    def test_hauteur_osm_non_acceptee_400_nommant_le_champ(self):
        self.calepinage.roof_layout = conception(pente='validee')
        self.calepinage.save(update_fields=['roof_layout'])
        reponse = self.api.post(url_approbation(self.calepinage.pk),
                                {'decision': 'approuve'}, format='json')
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('buildings[bat-1].hauteurM', reponse.data)
        self.assertEqual(
            [ligne['champ'] for ligne in reponse.data['en_attente']],
            ['buildings[bat-1].hauteurM'])

    def test_meme_conception_suggestions_acceptees_s_approuve(self):
        document = conception(pente='validee')
        self.calepinage.roof_layout = copy.deepcopy(document)
        self.calepinage.save(update_fields=['roof_layout'])
        self.assertEqual(
            self.api.post(url_approbation(self.calepinage.pk),
                          {'decision': 'approuve'},
                          format='json').status_code, 400)
        document['buildings'][0]['hauteurSuggestion']['status'] = 'validee'
        document['buildings'][0]['hauteurM'] = 7.5
        document['buildings'][0]['source'] = 'osm:height'
        self.calepinage.roof_layout = document
        self.calepinage.save(update_fields=['roof_layout'])
        reponse = self.api.post(url_approbation(self.calepinage.pk),
                                {'decision': 'approuve'}, format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)

    def test_autre_societe_introuvable(self):
        reponse = self.api_autre.post(url_approbation(self.calepinage.pk),
                                      {'decision': 'approuve'},
                                      format='json')
        self.assertEqual(reponse.status_code, 404)

    def test_action_rattachee_get_et_post(self):
        from apps.calepinage.views.calepinages import CalepinageViewSet
        from apps.calepinage.views.rattachements import MODULES_RATTACHES

        self.assertIn('approbation', MODULES_RATTACHES)
        actions = {a.__name__: a
                   for a in CalepinageViewSet.get_extra_actions()}
        self.assertEqual(set(actions['approbation'].mapping), {'get', 'post'})

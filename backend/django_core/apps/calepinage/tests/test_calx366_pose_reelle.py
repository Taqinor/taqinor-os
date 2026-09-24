"""CALX366 — la porte de la pose réelle, et la version née des écarts.

Ce qui est prouvé ici :

* la réponse de ``pose-reelle/`` EST le contrat committé
  (``contract_samples/calepinage_asbuilt_ecarts.json``, CALX337) : ses trois
  états rejoués à l'identique depuis de vraies saisies passées par
  ``comparer``, et ses deux refus à la clé et au message près ;
* un pan inconnu du prévu ⇒ refus qui NOMME ``pan`` ; un nombre posé négatif
  ou décimal ⇒ ``modules_poses`` ; une date absente ⇒ ``releve_le`` ;
  l'intention claire (``"3"``, ``3.0``) est normalisée ;
* un pan prévu sans saisie sort à ``modules_poses: null`` — jamais ``0`` ;
* la version passe par ``services/versions.py::enregistrer_version`` (LE
  chemin unique), même empreinte admise, et son résultat gelé porte le nombre
  de modules RÉELLEMENT posés ; le libellé nomme les pans en écart ;
* ``enregistrer_version`` garde son comportement par défaut (mots-clés
  additifs) ;
* en base (CI) : saisie, correction, refus sans écriture, version créée puis
  retrouvée (``version_creee``), journal écrit, garde par méthode, 404 pour
  une autre société.

Les classes ``…EnBase`` exigent l'ORM : la CI est leur gate.

Run :
    python manage.py test apps.calepinage.tests.test_calx366_pose_reelle -v2
"""
import datetime
import inspect
import json
import pathlib
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from apps.calepinage.services import asbuilt as service
from apps.calepinage.services import versions as versions_service

RACINE_APP = pathlib.Path(__file__).resolve().parents[1]
CONTRAT = json.loads(
    (RACINE_APP / 'contract_samples' / 'calepinage_asbuilt_ecarts.json')
    .read_text(encoding='utf-8'))

PANS = ['PAN-A', 'PAN-B', 'PAN-C']
PREVUS = [{'pan': 'PAN-A', 'modules': 8}, {'pan': 'PAN-B', 'modules': 4},
          {'pan': 'PAN-C', 'modules': 2}]
SAISIES = [
    {'pan': 'PAN-A', 'modules_poses': 8, 'ecarts_position': '',
     'releve_le': '2026-09-22'},
    {'pan': 'PAN-B', 'modules_poses': 3,
     'ecarts_position': CONTRAT['corps_saisie']['ecarts_position'],
     'releve_le': '2026-09-22'},
]


def ecarts(prevus=PREVUS, saisies=SAISIES, source=service.SOURCE_VARIANTE):
    """Les écarts d'un calepinage, calculés SANS base par le vrai code."""
    return service._agreger(1, source, service.comparer(prevus, saisies))


class ContratCommitteTest(SimpleTestCase):
    """Les trois états et les deux refus du contrat CALX337, à l'identique."""

    def test_exemple(self):
        self.assertEqual(service._forme_contrat(ecarts(), None),
                         CONTRAT['exemple'])

    def test_exemple_version_creee(self):
        self.assertEqual(service._forme_contrat(ecarts(), 31),
                         CONTRAT['exemple_version_creee'])

    def test_exemple_vide(self):
        vide = ecarts(prevus=PREVUS[:2], saisies=[],
                      source=service.SOURCE_CALEPINAGE)
        self.assertEqual(service._forme_contrat(vide, None),
                         CONTRAT['exemple_vide'])

    def test_refus_pan_inconnu(self):
        corps = dict(CONTRAT['corps_saisie'], pan='PAN-Z')
        with self.assertRaises(service.PoseRefusee) as refus:
            service._valider_saisie(corps, PANS)
        self.assertEqual(refus.exception.corps(),
                         CONTRAT['refus_pan_inconnu'])

    def test_refus_modules_poses(self):
        corps = dict(CONTRAT['corps_saisie'], modules_poses=-2)
        with self.assertRaises(service.PoseRefusee) as refus:
            service._valider_saisie(corps, PANS)
        self.assertEqual(refus.exception.corps(),
                         CONTRAT['refus_modules_poses'])

    def test_corps_saisie_du_contrat_accepte(self):
        saisie = service._valider_saisie(CONTRAT['corps_saisie'], PANS)
        self.assertEqual(saisie, {
            'pan': 'PAN-B', 'modules_poses': 3,
            'ecarts_position': CONTRAT['corps_saisie']['ecarts_position'],
            'releve_le': datetime.date(2026, 9, 22)})


class SaisieTest(SimpleTestCase):
    """Normaliser l'intention claire, refuser le reste en NOMMANT le champ."""

    def _modules(self, valeur):
        return service._valider_saisie(
            dict(CONTRAT['corps_saisie'], modules_poses=valeur),
            PANS)['modules_poses']

    def test_intention_claire_normalisee(self):
        self.assertEqual(self._modules('3'), 3)
        self.assertEqual(self._modules(3.0), 3)
        self.assertEqual(self._modules(0), 0)

    def test_valeurs_refusees_nomment_modules_poses(self):
        for valeur in (2.5, True, None, 'abc', '-1', -2):
            with self.subTest(valeur=valeur):
                with self.assertRaises(service.PoseRefusee) as refus:
                    self._modules(valeur)
                self.assertEqual(refus.exception.champ, 'modules_poses')
                self.assertIn(f'« {valeur} »', str(refus.exception))

    def test_date_absente_ou_illisible_nomme_releve_le(self):
        for valeur in (None, '', '22/09/2026'):
            with self.subTest(valeur=valeur):
                with self.assertRaises(service.PoseRefusee) as refus:
                    service._valider_saisie(
                        dict(CONTRAT['corps_saisie'], releve_le=valeur), PANS)
                self.assertEqual(refus.exception.champ, 'releve_le')

    def test_corps_illisible_nomme_pan(self):
        with self.assertRaises(service.PoseRefusee) as refus:
            service._valider_saisie(None, PANS)
        self.assertEqual(refus.exception.champ, 'pan')

    def test_pan_prevu_sans_saisie_jamais_zero(self):
        forme = service._forme_contrat(ecarts(), None)
        pan_c = next(ligne for ligne in forme['lignes']
                     if ligne['pan'] == 'PAN-C')
        self.assertIsNone(pan_c['modules_poses'])
        self.assertIsNone(pan_c['ecart'])
        self.assertEqual(pan_c['mention'], service.MENTION_SANS_SAISIE)


class LibelleVersionTest(SimpleTestCase):
    """Le libellé nomme les pans en écart et le nombre RÉELLEMENT posé."""

    def test_pans_en_ecart_et_non_releves(self):
        libelle = service._libelle_version(ecarts())
        self.assertTrue(libelle.startswith(service.PREFIXE_VERSION_POSE))
        self.assertIn('11 module(s) posé(s) sur 14 prévu(s)', libelle)
        self.assertIn('PAN-B (-1)', libelle)
        self.assertIn('non relevé(s) : PAN-C', libelle)
        self.assertNotIn('PAN-A (', libelle)

    def test_aucun_ecart(self):
        conforme = ecarts(saisies=[
            dict(SAISIES[0]), dict(SAISIES[1], modules_poses=4),
            {'pan': 'PAN-C', 'modules_poses': 2, 'releve_le': '2026-09-22'}])
        libelle = service._libelle_version(conforme)
        self.assertIn('aucun écart sur les pans relevés', libelle)
        self.assertNotIn('non relevé', libelle)

    def test_pan_hors_prevu_et_borne_de_longueur(self):
        nombreux = [{'pan': f'PAN-{i:03d}', 'modules': 2} for i in range(40)]
        saisies = [{'pan': p['pan'], 'modules_poses': 1,
                    'releve_le': '2026-09-22'} for p in nombreux]
        saisies.append({'pan': 'Auvent', 'modules_poses': 3,
                        'releve_le': '2026-09-22'})
        libelle = service._libelle_version(ecarts(prevus=nombreux,
                                                  saisies=saisies))
        self.assertLessEqual(len(libelle), service.LIBELLE_MAX)
        self.assertTrue(libelle.endswith('…'))
        court = service._libelle_version(ecarts(saisies=SAISIES + [
            {'pan': 'Auvent', 'modules_poses': 3, 'releve_le': '2026-09-22'}]))
        self.assertIn('Auvent (hors prévu)', court)


class VersionDepuisEcartsTest(SimpleTestCase):
    """LE chemin unique, même empreinte admise, posé réel gelé."""

    def calepinage(self):
        return SimpleNamespace(pk=5, company=None, company_id=1,
                               resultat={'production': {'p50_kwh': None}})

    def test_aucun_pan_releve_refuse_en_nommant_creer_version(self):
        with mock.patch.object(service, 'ecarts_du_calepinage',
                               return_value=ecarts(saisies=[])):
            with self.assertRaises(service.PoseRefusee) as refus:
                service.version_depuis_ecarts(self.calepinage())
        self.assertEqual(refus.exception.champ, 'creer_version')

    def test_la_version_passe_par_enregistrer_version(self):
        calepinage = self.calepinage()
        gelee = SimpleNamespace(pk=31, libelle='Pose réelle — …')
        with mock.patch.object(service, 'ecarts_du_calepinage',
                               return_value=ecarts()), \
                mock.patch.object(service, '_derniere_version_pose',
                                  return_value=None), \
                mock.patch.object(versions_service, 'enregistrer_version',
                                  return_value=gelee) as enregistrer, \
                mock.patch('apps.calepinage.services.journal.'
                           'journaliser_version_pose') as journal:
            version, creee = service.version_depuis_ecarts(calepinage)
        self.assertIs(version, gelee)
        self.assertTrue(creee)
        journal.assert_called_once()
        kwargs = enregistrer.call_args.kwargs
        self.assertTrue(kwargs['meme_empreinte_admise'])
        self.assertIn('PAN-B', kwargs['libelle'])
        bloc = kwargs['resultat']['asbuilt']
        self.assertEqual(bloc['total_pose'], 11)
        self.assertEqual(bloc['lignes'], CONTRAT['exemple']['lignes'])
        # Le résultat du moteur est GARDÉ, le bloc as-built s'y ajoute.
        self.assertEqual(kwargs['resultat']['production'],
                         {'p50_kwh': None})
        self.assertNotIn('asbuilt', calepinage.resultat)

    def test_memes_ecarts_rendent_la_version_deja_gelee(self):
        bloc = {'source': service.SOURCE_VARIANTE, 'total_prevu': 14,
                'total_pose': 11, 'lignes': CONTRAT['exemple']['lignes']}
        precedente = SimpleNamespace(pk=31, resultat={'asbuilt': bloc})
        with mock.patch.object(service, 'ecarts_du_calepinage',
                               return_value=ecarts()), \
                mock.patch.object(service, '_derniere_version_pose',
                                  return_value=precedente), \
                mock.patch.object(versions_service,
                                  'enregistrer_version') as enregistrer:
            version, creee = service.version_depuis_ecarts(self.calepinage())
        self.assertIs(version, precedente)
        self.assertFalse(creee)
        enregistrer.assert_not_called()


class EnregistrerVersionAdditifTest(SimpleTestCase):
    """Les deux mots-clés de CALX366 sont additifs, sans effet par défaut."""

    def test_signature(self):
        signature = inspect.signature(versions_service.enregistrer_version)
        self.assertFalse(
            signature.parameters['meme_empreinte_admise'].default)
        self.assertIs(signature.parameters['resultat'].default,
                      versions_service._RESULTAT_DU_CALEPINAGE)


class ActionRattacheeTest(SimpleTestCase):
    """La porte ``pose-reelle/`` existe, GET et POST, garde par méthode."""

    def test_action_decouverte_par_le_routeur(self):
        from apps.calepinage.permissions import PeutLireOuEcrireCalepinage
        from apps.calepinage.views.asbuilt import pose_reelle
        from apps.calepinage.views.calepinages import CalepinageViewSet
        from apps.calepinage.views.rattachements import MODULES_RATTACHES

        self.assertIn('asbuilt', MODULES_RATTACHES)
        actions = {a.__name__: a
                   for a in CalepinageViewSet.get_extra_actions()}
        action = actions['pose_reelle']
        self.assertEqual(action.url_path, 'pose-reelle')
        self.assertEqual(set(action.mapping), {'get', 'post'})
        self.assertEqual(pose_reelle.kwargs['permission_classes'],
                         [PeutLireOuEcrireCalepinage])

    def test_demande_de_version_lue_sans_deviner(self):
        from apps.calepinage.views.asbuilt import _demande_de_version

        self.assertTrue(_demande_de_version(CONTRAT['corps_creer_version']))
        self.assertTrue(_demande_de_version({'creer_version': 'oui'}))
        self.assertFalse(_demande_de_version(CONTRAT['corps_saisie']))
        self.assertFalse(_demande_de_version({'creer_version': False}))


# ── EN BASE — exige l'ORM (la CI est la gate de ces classes) ──────────────

from django.contrib.auth import get_user_model  # noqa: E402
from django.contrib.contenttypes.models import ContentType  # noqa: E402

from apps.calepinage.models import (  # noqa: E402
    Calepinage, CalepinageVersion, PoseReelle,
)
from apps.calepinage.permissions import CAL_VOIR  # noqa: E402
from apps.records.models import Activity  # noqa: E402
from apps.roles.models import Role  # noqa: E402

from .test_api_liste import BaseApiCalepinage, url_detail  # noqa: E402

User = get_user_model()

DOCUMENT = {'zones': [
    {'id': 'z1', 'label': 'PAN-A', 'result': {'count': 8}},
    {'id': 'z2', 'label': 'PAN-B', 'result': {'count': 4}},
    {'id': 'z3', 'label': 'PAN-C', 'result': {'count': 2}},
]}


def url_pose(pk):
    return f'{url_detail(pk)}pose-reelle/'


class PoseReelleEnBase(BaseApiCalepinage):
    """La porte réelle : saisie, correction, refus, version, journal."""

    def setUp(self):
        super().setUp()
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Villa Anfa',
            roof_layout=DOCUMENT, layout_hash='a' * 64)

    def _saisir(self, api=None, **champs):
        corps = dict(CONTRAT['corps_saisie'], **champs)
        return (api or self.api).post(url_pose(self.calepinage.pk), corps,
                                      format='json')

    def _journal(self):
        return Activity.objects.filter(
            content_type=ContentType.objects.get_for_model(Calepinage),
            object_id=self.calepinage.pk)

    def test_get_sans_saisie_jamais_zero(self):
        reponse = self.api.get(url_pose(self.calepinage.pk))
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(sorted(reponse.data), sorted(CONTRAT['exemple']))
        self.assertEqual(reponse.data['source'], service.SOURCE_CALEPINAGE)
        self.assertEqual(reponse.data['total_prevu'], 14)
        self.assertIsNone(reponse.data['total_pose'])
        self.assertIsNone(reponse.data['version_creee'])
        for ligne in reponse.data['lignes']:
            self.assertEqual(sorted(ligne),
                             sorted(CONTRAT['exemple']['lignes'][0]))
            self.assertIsNone(ligne['modules_poses'], ligne['pan'])
            self.assertIsNone(ligne['ecart'], ligne['pan'])

    def test_saisie_puis_correction_du_meme_pan(self):
        avant = self._journal().count()
        reponse = self._saisir()
        self.assertEqual(reponse.status_code, 200, reponse.data)
        pan_b = next(ligne for ligne in reponse.data['lignes']
                     if ligne['pan'] == 'PAN-B')
        self.assertEqual(pan_b['modules_poses'], 3)
        self.assertEqual(pan_b['ecart'], -1)
        pan_c = next(ligne for ligne in reponse.data['lignes']
                     if ligne['pan'] == 'PAN-C')
        self.assertIsNone(pan_c['modules_poses'])
        self.assertEqual(self._journal().count(), avant + 1)

        corrige = self._saisir(modules_poses=4)
        self.assertEqual(corrige.status_code, 200, corrige.data)
        pose = PoseReelle.objects.get(calepinage=self.calepinage)
        self.assertEqual(pose.modules_poses, 4)
        self.assertEqual(pose.releve_par, self.user)
        self.assertEqual(pose.company, self.company)

    def test_pan_inconnu_400_nommant_pan_sans_ecriture(self):
        reponse = self._saisir(pan='PAN-Z')
        self.assertEqual(reponse.status_code, 400)
        self.assertEqual(reponse.data, CONTRAT['refus_pan_inconnu'])
        self.assertFalse(PoseReelle.objects.exists())

    def test_nombre_negatif_400_nommant_modules_poses(self):
        reponse = self._saisir(modules_poses=-2)
        self.assertEqual(reponse.status_code, 400)
        self.assertEqual(reponse.data, CONTRAT['refus_modules_poses'])
        self.assertFalse(PoseReelle.objects.exists())

    def test_date_absente_400_nommant_releve_le(self):
        reponse = self._saisir(releve_le='')
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('releve_le', reponse.data)

    def test_version_sans_aucun_releve_refusee(self):
        reponse = self.api.post(url_pose(self.calepinage.pk),
                                CONTRAT['corps_creer_version'], format='json')
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('creer_version', reponse.data)

    def test_version_depuis_les_ecarts(self):
        # Une version de la MÊME empreinte existe déjà : la pose réelle ne
        # redessine rien, la version des écarts doit naître quand même.
        versions_service.enregistrer_version(self.calepinage, user=self.user)
        self._saisir(pan='PAN-A', modules_poses=8, ecarts_position='')
        self._saisir()
        avant = self._journal().count()

        reponse = self.api.post(url_pose(self.calepinage.pk),
                                CONTRAT['corps_creer_version'], format='json')

        self.assertEqual(reponse.status_code, 201, reponse.data)
        version = CalepinageVersion.objects.get(
            pk=reponse.data['version_creee'])
        self.assertTrue(version.libelle.startswith('Pose réelle'))
        self.assertIn('PAN-B', version.libelle)
        self.assertEqual(version.resultat['asbuilt']['total_pose'], 11)
        self.assertEqual(version.layout_hash, 'a' * 64)
        self.assertEqual(self._journal().count(), avant + 1)

        encore = self.api.post(url_pose(self.calepinage.pk),
                               CONTRAT['corps_creer_version'], format='json')
        self.assertEqual(encore.status_code, 200, encore.data)
        self.assertEqual(encore.data['version_creee'], version.pk)
        lecture = self.api.get(url_pose(self.calepinage.pk))
        self.assertEqual(lecture.data['version_creee'], version.pk)
        self.assertEqual(CalepinageVersion.objects.filter(
            calepinage=self.calepinage).count(), 2)

    def test_enregistrer_version_par_defaut_inchange(self):
        premiere = versions_service.enregistrer_version(self.calepinage)
        self.assertIsNotNone(premiere)
        self.assertIsNone(
            versions_service.enregistrer_version(self.calepinage),
            'même empreinte, défaut : aucune version de plus')

    def test_lecteur_lit_mais_ne_saisit_pas(self):
        role = Role.objects.create(company=self.company, nom='Lecteur366',
                                   permissions=[CAL_VOIR])
        lecteur = User.objects.create_user(
            username='calx366_lecteur', password='x', company=self.company,
            role=role)
        api = self._client(lecteur)
        self.assertEqual(api.get(url_pose(self.calepinage.pk)).status_code,
                         200)
        self.assertEqual(self._saisir(api=api).status_code, 403)
        self.assertFalse(PoseReelle.objects.exists())

    def test_autre_societe_introuvable(self):
        self.assertEqual(self._saisir(api=self.api_autre).status_code, 404)
        self.assertFalse(PoseReelle.objects.exists())

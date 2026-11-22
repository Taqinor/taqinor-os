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
import copy
import datetime
import inspect
import json
import pathlib
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from apps.calepinage.services import asbuilt as service
from apps.calepinage.services import versions as versions_service
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from apps.calepinage.models import (
    Calepinage, CalepinageVersion, PoseReelle,
)
from apps.calepinage.permissions import CAL_VOIR
from apps.records.models import Activity
from apps.roles.models import Role
from .test_api_liste import BaseApiCalepinage, url_detail

RACINE_APP = pathlib.Path(__file__).resolve().parents[1]
CONTRAT = json.loads(
    (RACINE_APP / 'contract_samples' / 'calepinage_asbuilt_ecarts.json')
    .read_text(encoding='utf-8'))

#: Le contrat as-built v2 (ACAL16) est SERVI EN ENTIER : ``releve_le`` /
#: ``releve_par`` depuis ACAL245, ``prevu_fige`` / ``prevu_actuel`` /
#: ``conception_modifiee`` depuis ACAL248, ``zone_id`` / ``libelle`` /
#: ``orphelin`` (et la ligne ORPHELINE hors totaux) depuis ACAL267.
SERVI = {etat: copy.deepcopy(CONTRAT[etat])
         for etat in ('exemple', 'exemple_version_creee', 'exemple_vide')}

#: Les pans prévus : identifiant STABLE (``zone_id``) et libellé affiché.
PANS = [{'zone_id': 'z1', 'libelle': 'PAN-A'},
        {'zone_id': 'z2', 'libelle': 'PAN-B'},
        {'zone_id': 'z3', 'libelle': 'PAN-C'}]
PREVUS = [{'pan': 'PAN-A', 'zone_id': 'z1', 'libelle': 'PAN-A', 'modules': 8},
          {'pan': 'PAN-B', 'zone_id': 'z2', 'libelle': 'PAN-B', 'modules': 4},
          {'pan': 'PAN-C', 'zone_id': 'z3', 'libelle': 'PAN-C', 'modules': 2}]
#: ACAL248 — l'``exemple`` du contrat : PAN-B a été RETOUCHÉ à 5 modules
#: après son relevé (prévu figé 4) — ``conception_modifiee`` sur cette ligne.
PREVUS_RETOUCHES = [dict(pan, modules=5) if pan['pan'] == 'PAN-B' else pan
                    for pan in PREVUS]
SAISIES = [
    {'pan': 'PAN-A', 'zone_id': 'z1', 'modules_poses': 8,
     'ecarts_position': '', 'releve_le': '2026-09-22', 'modules_prevus': 8,
     'releve_par': CONTRAT['exemple']['lignes'][0]['releve_par']},
    {'pan': 'PAN-B', 'zone_id': 'z2', 'modules_poses': 3,
     'ecarts_position': CONTRAT['corps_saisie']['ecarts_position'],
     'releve_le': '2026-09-22', 'modules_prevus': 4,
     'releve_par': CONTRAT['exemple']['lignes'][1]['releve_par']},
]
#: ACAL267 — l'``exemple`` porte aussi un relevé dont le pan a été SUPPRIMÉ
#: (``z9``, libellé figé « Ancien pan supprimé ») : orphelin, hors totaux.
ORPHELIN = {'pan': CONTRAT['exemple']['lignes'][3]['libelle'],
            'zone_id': 'z9', 'libelle': CONTRAT['exemple']['lignes'][3]['libelle'],
            'modules_poses': 2, 'ecarts_position': '',
            'releve_le': '2026-09-22', 'modules_prevus': 0,
            'releve_par': CONTRAT['exemple']['lignes'][3]['releve_par']}


def ecarts(prevus=PREVUS, saisies=SAISIES, source=service.SOURCE_VARIANTE):
    """Les écarts d'un calepinage, calculés SANS base par le vrai code."""
    return service._agreger(1, source, service._comparer(prevus, saisies))


class ContratCommitteTest(SimpleTestCase):
    """Les trois états et les deux refus du contrat CALX337, à l'identique."""

    def test_exemple(self):
        self.assertEqual(
            service._forme_contrat(ecarts(prevus=PREVUS_RETOUCHES,
                                          saisies=SAISIES + [ORPHELIN]),
                                   None),
            SERVI['exemple'])

    def test_exemple_version_creee(self):
        self.assertEqual(service._forme_contrat(ecarts(), 31),
                         SERVI['exemple_version_creee'])

    def test_exemple_vide(self):
        vide = ecarts(prevus=PREVUS[:2], saisies=[],
                      source=service.SOURCE_CALEPINAGE)
        self.assertEqual(service._forme_contrat(vide, None),
                         SERVI['exemple_vide'])

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
            'pan': 'PAN-B', 'zone_id': 'z2', 'modules_poses': 3,
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
                               return_value=ecarts(
                                   prevus=PREVUS_RETOUCHES,
                                   saisies=SAISIES + [ORPHELIN])), \
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
        self.assertEqual(bloc['lignes'], SERVI['exemple']['lignes'])
        # Le résultat du moteur est GARDÉ, le bloc as-built s'y ajoute.
        self.assertEqual(kwargs['resultat']['production'],
                         {'p50_kwh': None})
        self.assertNotIn('asbuilt', calepinage.resultat)

    def test_memes_ecarts_rendent_la_version_deja_gelee(self):
        bloc = {'source': service.SOURCE_VARIANTE, 'total_prevu': 14,
                'total_pose': 11, 'lignes': SERVI['exemple']['lignes']}
        precedente = SimpleNamespace(pk=31, resultat={'asbuilt': bloc})
        with mock.patch.object(service, 'ecarts_du_calepinage',
                               return_value=ecarts(
                                   prevus=PREVUS_RETOUCHES,
                                   saisies=SAISIES + [ORPHELIN])), \
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
        self.assertEqual(sorted(reponse.data), sorted(SERVI['exemple']))
        self.assertEqual(reponse.data['source'], service.SOURCE_CALEPINAGE)
        self.assertEqual(reponse.data['total_prevu'], 14)
        self.assertIsNone(reponse.data['total_pose'])
        self.assertIsNone(reponse.data['version_creee'])
        for ligne in reponse.data['lignes']:
            self.assertEqual(sorted(ligne),
                             sorted(SERVI['exemple']['lignes'][0]))
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

    def test_pan_inconnu_404_nommant_pan_sans_ecriture(self):
        # ERR-ENF11-FUZZ-CALEPINAGE — sous-ressource absente : 404, même corps.
        reponse = self._saisir(pan='PAN-Z')
        self.assertEqual(reponse.status_code, 404)
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
        # ERR-ENF11-FUZZ-CALEPINAGE — rien à figer : conflit d'état, 409.
        self.assertEqual(reponse.status_code, 409)
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


# ── ACAL846 — consommation mesurée comparée à la simulée ──────────────────

MESURES = json.loads(
    (RACINE_APP / 'contract_samples' / 'calepinage_asbuilt_mesures.json')
    .read_text(encoding='utf-8'))


class EcartMesuresTest(SimpleTestCase):
    """Le cœur PUR : 12 écarts, année moyenne de la fenêtre, refus nommés."""

    def test_douze_ecarts_du_contrat(self):
        mesures = service._mesures_kwh(MESURES['corps']['kwh'])
        bloc = service._ecart_consommation(MESURES['resultat_simule'], mesures)
        self.assertEqual(bloc, MESURES['exemple']['consommation'])
        self.assertEqual(len(bloc['lignes']), 12)

    def test_fenetre_de_deux_ans_ramenee_a_l_annee_moyenne(self):
        une_annee = copy.deepcopy(MESURES['resultat_simule'])
        une_annee['production']['total']['annees_fenetre'] = 1
        mesures = [820.0] + [None] * 11
        deux = service._ecart_consommation(MESURES['resultat_simule'], mesures)
        une = service._ecart_consommation(une_annee, mesures)
        self.assertEqual(deux['lignes'][0]['simule_kwh'], 820.0)
        self.assertEqual(deux['lignes'][0]['ecart_pct'], 0.0)
        self.assertEqual(une['lignes'][0]['simule_kwh'], 1640.0)
        self.assertEqual(une['lignes'][0]['ecart_pct'], -50.0)

    def test_sans_simulation_motif(self):
        self.assertEqual(service._ecart_consommation({}, [None] * 12),
                         MESURES['exemple_sans_simulation'])

    def test_mesure_negative_nomme_kwh_2(self):
        kwh = [1] * 12
        kwh[2] = -5
        with self.assertRaises(service.PoseRefusee) as refus:
            service._mesures_kwh(kwh)
        self.assertEqual(refus.exception.corps(), MESURES['refus_409_kwh'])

    def test_mesure_illisible_et_liste_courte(self):
        with self.assertRaises(service.PoseRefusee) as refus:
            service._mesures_kwh(['abc'] + [1] * 11)
        self.assertIn('kwh[0]', refus.exception.corps())
        with self.assertRaises(service.PoseRefusee) as refus:
            service._mesures_kwh([1] * 3)
        self.assertIn('kwh', refus.exception.corps())

    def test_action_gardee_par_l_approbation(self):
        from apps.calepinage.permissions import PeutApprouverCalepinage
        from apps.calepinage.views.asbuilt import ecart_mesures
        from apps.calepinage.views.calepinages import CalepinageViewSet

        actions = {a.__name__: a for a in CalepinageViewSet.get_extra_actions()}
        self.assertEqual(actions['ecart_mesures'].url_path, 'ecart-mesures')
        self.assertEqual(ecart_mesures.kwargs['permission_classes'],
                         [PeutApprouverCalepinage])


def url_ecart(pk):
    return f'{url_detail(pk)}ecart-mesures/'


class EcartMesuresEnBase(BaseApiCalepinage):
    """La porte réelle : 200 au porteur de ``calepinage_approuver`` seul."""

    def setUp(self):
        super().setUp()
        from apps.calepinage.permissions import CAL_APPROUVER, CAL_GERER

        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Villa Anfa',
            roof_layout=DOCUMENT, layout_hash='a' * 64,
            resultat=copy.deepcopy(MESURES['resultat_simule']))
        approbateur = User.objects.create_user(
            username='acal846_approbateur', password='x', company=self.company,
            role=Role.objects.create(company=self.company, nom='Approbateur846',
                                     permissions=[CAL_VOIR, CAL_APPROUVER]))
        gestionnaire = User.objects.create_user(
            username='acal846_gerant', password='x', company=self.company,
            role=Role.objects.create(company=self.company, nom='Gerant846',
                                     permissions=[CAL_VOIR, CAL_GERER]))
        self.api_approbateur = self._client(approbateur)
        self.api_gerant = self._client(gestionnaire)

    def _poster(self, api, corps=None):
        return api.post(url_ecart(self.calepinage.pk),
                        corps if corps is not None else MESURES['corps'],
                        format='json')

    def test_douze_ecarts_servis(self):
        reponse = self._poster(self.api_approbateur)
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(reponse.data, MESURES['exemple'])

    def test_sans_calepinage_approuver_403(self):
        self.assertEqual(self._poster(self.api_gerant).status_code, 403)

    def test_mesure_negative_409_nommant_kwh_2(self):
        corps = copy.deepcopy(MESURES['corps'])
        corps['kwh'][2] = -5
        reponse = self._poster(self.api_approbateur, corps)
        self.assertEqual(reponse.status_code, 409)
        self.assertEqual(reponse.data, MESURES['refus_409_kwh'])

    def test_autre_societe_404(self):
        self.assertEqual(self._poster(self.api_autre).status_code, 404)

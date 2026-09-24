"""CALX364 — reprendre les mesures et les photos d'une visite technique.

Ce qui est prouvé ici :

* la réponse de ``releve-visite/`` EST le contrat committé
  (``contract_samples/calepinage_releve_visite.json``, CALX336) — les trois
  états (``exemple``, ``exemple_avant_reprise``, ``exemple_vide``) rejoués à
  l'identique par le compositeur, et le bloc ``releve`` construit depuis des
  objets rend l'exemple octet pour octet ;
* un calepinage SANS lead nomme ce qui manque, sans appeler le CRM ;
* sans visite validée, reprendre est REFUSÉ en nommant ``visite_id`` avec le
  motif servi par la porte de ``visites`` — rien n'est écrit ;
* la lecture croisée passe par ``apps.crm.selectors`` et
  ``apps.visites.selectors`` — jamais leurs modèles ;
* ``provenance`` naît à ``'saisie'`` pour tout l'existant (D12) par une
  migration ADDITIVE ``0015`` ;
* en base (CI) : la reprise crée UN relevé ``visite`` aux mesures telles que
  saisies, rattache les photos aux pièces jointes EXISTANTES sans en créer
  une seule, un second POST ne crée rien (``deja_repris``), une saisie
  manuelle reste ``saisie``, une autre société est introuvable, un lecteur ne
  reprend pas.

Les classes ``…EnBase`` exigent l'ORM : la CI est leur gate.

Run :
    python manage.py test apps.calepinage.tests.test_calx364_reprise_visite -v2
"""
import datetime
import importlib
import json
import pathlib
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from apps.calepinage.models import PhotoSite, ProvenanceTerrain, ReleveTerrain
from apps.calepinage.services import reprise_visite as service

RACINE_APP = pathlib.Path(__file__).resolve().parents[1]
CONTRAT = json.loads(
    (RACINE_APP / 'contract_samples' / 'calepinage_releve_visite.json')
    .read_text(encoding='utf-8'))

#: Les cinq clés que sert la porte de ``visites`` (CALX363).
CLES_LECTURE = ('visite_id', 'validee_le', 'mesures', 'photos',
                'motif_absence')

FUSEAU = datetime.timezone(datetime.timedelta(hours=1))


def lecture_de(etat):
    """La lecture ``visites`` contenue dans un état du contrat."""
    return {cle: etat[cle] for cle in CLES_LECTURE}


def releve_de_l_exemple():
    """Des objets qui portent EXACTEMENT les valeurs de ``exemple.releve``."""
    bloc = CONTRAT['exemple']['releve']
    releve = SimpleNamespace(
        pk=bloc['id'], provenance=bloc['provenance'],
        releve_le=datetime.date.fromisoformat(bloc['releve_le']),
        releve_par=SimpleNamespace(username=bloc['releve_par']),
        created_at=datetime.datetime(2026, 9, 19, 10, 5, tzinfo=FUSEAU))
    photos = [SimpleNamespace(pk=p['id'], attachment_id=p['attachment_id'],
                              slot_code=p['slot_code'],
                              provenance=p['provenance'])
              for p in bloc['photos']]
    return releve, photos


class ContratCommitteTest(SimpleTestCase):
    """Les trois états du contrat CALX336, rejoués à l'identique."""

    def test_avant_reprise(self):
        etat = CONTRAT['exemple_avant_reprise']
        self.assertEqual(service._composer_reponse(lecture_de(etat), None),
                         etat)

    def test_apres_reprise(self):
        etat = CONTRAT['exemple']
        self.assertEqual(
            service._composer_reponse(lecture_de(etat), etat['releve']), etat)

    def test_sans_visite_validee(self):
        etat = CONTRAT['exemple_vide']
        self.assertEqual(service._composer_reponse(lecture_de(etat), None),
                         etat)

    def test_le_bloc_releve_construit_depuis_des_objets(self):
        releve, photos = releve_de_l_exemple()
        self.assertEqual(service._releve_en_ligne(releve, photos),
                         CONTRAT['exemple']['releve'])

    def test_un_releve_sans_auteur_ni_date(self):
        releve, _photos = releve_de_l_exemple()
        releve.releve_par = None
        releve.releve_le = None
        releve.created_at = None
        bloc = service._releve_en_ligne(releve, [])
        self.assertEqual(sorted(bloc), sorted(CONTRAT['exemple']['releve']))
        self.assertEqual(bloc['releve_par'], '')
        self.assertIsNone(bloc['releve_le'])
        self.assertIsNone(bloc['created_at'])
        self.assertEqual(bloc['photos'], [])


class SansLeadTest(SimpleTestCase):
    """Un calepinage rattaché à un client seul : aucune visite à chercher."""

    def calepinage(self):
        return SimpleNamespace(pk=None, lead_id=None, company=None,
                               company_id=None)

    def test_la_lecture_nomme_le_manque_sans_appeler_le_crm(self):
        with mock.patch('apps.crm.selectors.get_company_lead',
                        side_effect=AssertionError('CRM appelé')):
            lecture = service._lecture_visite(self.calepinage())
        self.assertEqual(sorted(lecture), sorted(CLES_LECTURE))
        self.assertEqual(lecture['motif_absence'], service.MOTIF_SANS_LEAD)
        for cle in ('visite_id', 'validee_le', 'mesures', 'photos'):
            self.assertIsNone(lecture[cle], cle)

    def test_l_etat_a_la_forme_du_contrat(self):
        etat = service.etat_reprise(self.calepinage())
        self.assertEqual(sorted(etat), sorted(CONTRAT['exemple_vide']))
        self.assertFalse(etat['deja_repris'])
        self.assertIsNone(etat['releve'])

    def test_reprendre_est_refuse_en_nommant_visite_id(self):
        with self.assertRaises(service.RepriseRefusee) as refus:
            service.reprendre_visite(self.calepinage())
        self.assertEqual(refus.exception.champ, 'visite_id')
        self.assertEqual(refus.exception.corps(),
                         {'visite_id': service.MOTIF_SANS_LEAD})


class VisiteNonValideeTest(SimpleTestCase):
    """Le motif de la porte ``visites`` est relayé MOT POUR MOT."""

    def test_refus_porte_le_motif_de_la_visite(self):
        etat = CONTRAT['exemple_vide']
        calepinage = SimpleNamespace(pk=1, lead_id=3, company=None,
                                     company_id=1)
        with mock.patch.object(service, '_lecture_visite',
                               return_value=lecture_de(etat)):
            with self.assertRaises(service.RepriseRefusee) as refus:
                service.reprendre_visite(calepinage)
        self.assertEqual(refus.exception.corps(),
                         {'visite_id': etat['motif_absence']})


class PhotosServiesTest(SimpleTestCase):
    """Une photo par pièce jointe, dans l'ordre servi."""

    def test_doublons_et_identifiants_illisibles_ecartes(self):
        photos = [
            {'slot_code': 'a', 'attachment_id': 41},
            {'slot_code': 'b', 'attachment_id': 41},
            {'slot_code': 'c', 'attachment_id': True},
            {'slot_code': 'd', 'attachment_id': '42'},
            'pas-un-objet',
            {'slot_code': 'e', 'attachment_id': 43},
        ]
        self.assertEqual(
            [p['slot_code'] for p in service._entiers_uniques(photos)],
            ['a', 'e'])
        self.assertEqual(service._entiers_uniques(None), [])


class FrontiereTest(SimpleTestCase):
    """Les lectures croisées passent par les ``selectors`` — jamais un modèle."""

    SOURCE = (RACINE_APP / 'services' / 'reprise_visite.py').read_text(
        encoding='utf-8')

    def _modules_importes(self):
        """Chaque module RÉELLEMENT importé (AST — la docstring ne compte pas)."""
        import ast

        modules = set()
        for noeud in ast.walk(ast.parse(self.SOURCE)):
            if isinstance(noeud, ast.Import):
                modules.update(alias.name for alias in noeud.names)
            elif isinstance(noeud, ast.ImportFrom) and noeud.module:
                modules.add(noeud.module)
                modules.update(f'{noeud.module}.{alias.name}'
                               for alias in noeud.names)
        return modules

    def test_aucun_modele_etranger(self):
        for module in self._modules_importes():
            for interdit in ('apps.visites.models', 'apps.crm.models',
                             'apps.ged', 'apps.ao'):
                self.assertFalse(module.startswith(interdit),
                                 f'{module} importé par reprise_visite.py')

    def test_les_deux_portes_sont_les_selectors(self):
        modules = self._modules_importes()
        self.assertIn('apps.visites.selectors.releve_pour_calepinage', modules)
        self.assertIn('apps.crm.selectors.get_company_lead', modules)


class SchemaAdditifTest(SimpleTestCase):
    """``provenance`` à ``'saisie'`` pour l'existant, migration 0015 additive."""

    def test_valeurs_de_provenance(self):
        self.assertEqual(ProvenanceTerrain.SAISIE, 'saisie')
        self.assertEqual(ProvenanceTerrain.VISITE, 'visite')
        self.assertEqual(CONTRAT['exemple']['releve']['provenance'],
                         ProvenanceTerrain.VISITE)

    def test_defaut_saisie_sur_les_deux_modeles(self):
        for modele in (ReleveTerrain, PhotoSite):
            with self.subTest(modele=modele.__name__):
                champ = modele._meta.get_field('provenance')
                self.assertEqual(champ.default, ProvenanceTerrain.SAISIE)

    def test_champs_de_reprise_du_releve(self):
        self.assertTrue(ReleveTerrain._meta.get_field('visite_id').null)
        mesures = ReleveTerrain._meta.get_field('mesures')
        self.assertIs(mesures.default, list)
        self.assertEqual(PhotoSite._meta.get_field('slot_code').default, '')

    def test_migration_0015_additive_apres_0014(self):
        module = importlib.import_module(
            'apps.calepinage.migrations.0015_calx364_provenance_releve_photo')
        migration = module.Migration
        self.assertIn(('calepinage', '0014_calx358_systeme_fixation'),
                      migration.dependencies)
        noms = {type(op).__name__ for op in migration.operations}
        self.assertEqual(noms, {'AddField', 'AddConstraint'})
        ajouts = {(op.model_name, op.name) for op in migration.operations
                  if type(op).__name__ == 'AddField'}
        self.assertEqual(ajouts, {
            ('photosite', 'provenance'), ('photosite', 'slot_code'),
            ('releveterrain', 'provenance'), ('releveterrain', 'visite_id'),
            ('releveterrain', 'mesures')})
        for op in migration.operations:
            if getattr(op, 'name', '') == 'provenance':
                self.assertEqual(op.field.default, 'saisie')


class ActionRattacheeTest(SimpleTestCase):
    """La porte ``releve-visite/`` existe, GET et POST, garde par méthode."""

    def test_action_decouverte_par_le_routeur(self):
        from apps.calepinage.views.calepinages import CalepinageViewSet
        from apps.calepinage.views.rattachements import MODULES_RATTACHES

        self.assertIn('reprise_visite', MODULES_RATTACHES)
        actions = {a.__name__: a
                   for a in CalepinageViewSet.get_extra_actions()}
        action = actions['releve_visite']
        self.assertEqual(action.url_path, 'releve-visite')
        self.assertEqual(set(action.mapping), {'get', 'post'})

    def test_garde_choisie_par_methode(self):
        from apps.calepinage.permissions import PeutLireOuEcrireCalepinage
        from apps.calepinage.views.reprise_visite import releve_visite

        self.assertEqual(releve_visite.kwargs['permission_classes'],
                         [PeutLireOuEcrireCalepinage])


# ── EN BASE — exige l'ORM (la CI est la gate de ces classes) ──────────────

from django.contrib.auth import get_user_model  # noqa: E402
from django.contrib.contenttypes.models import ContentType  # noqa: E402

from apps.calepinage.models import Calepinage  # noqa: E402
from apps.calepinage.permissions import CAL_VOIR  # noqa: E402
from apps.roles.models import Role  # noqa: E402

from .test_api_liste import BaseApiCalepinage, url_detail  # noqa: E402

User = get_user_model()


def url_reprise(pk):
    return f'{url_detail(pk)}releve-visite/'


class RepriseVisiteEnBase(BaseApiCalepinage):
    """La porte réelle, sur de vraies visites et de vraies pièces jointes."""

    def setUp(self):
        super().setUp()
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Villa Anfa')

    def _visite(self, statut, mesures=None, company=None):
        from apps.visites.models import VisiteTerrain

        return VisiteTerrain.objects.create(
            company=company or self.company, lead=self.lead, statut=statut,
            mesures=mesures if mesures is not None else {
                'toiture': {'longueur_m': 12.5, 'pente_deg': 15}})

    def _validee(self, **kwargs):
        from apps.visites.models import VisiteTerrain

        return self._visite(VisiteTerrain.Statut.VALIDEE, **kwargs)

    def _photo(self, visite, slot_code, a_refaire=False):
        from apps.crm.models import Lead
        from apps.records.models import Attachment
        from apps.visites.models import VisiteMedia

        piece = Attachment.objects.create(
            company=visite.company,
            content_type=ContentType.objects.get_for_model(Lead),
            object_id=visite.lead_id,
            file_key='visites/%s.png' % slot_code,
            filename='%s.png' % slot_code, size=1, mime='image/png')
        VisiteMedia.objects.create(
            company=visite.company, visite=visite, attachment=piece,
            slot_code=slot_code, a_refaire=a_refaire)
        return piece

    def _releves(self):
        return ReleveTerrain.objects.filter(calepinage=self.calepinage)

    def test_get_sans_visite_a_la_forme_vide_du_contrat(self):
        from apps.visites.selectors import MOTIF_AUCUNE_VISITE

        reponse = self.api.get(url_reprise(self.calepinage.pk))
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(sorted(reponse.data),
                         sorted(CONTRAT['exemple_vide']))
        self.assertIsNone(reponse.data['visite_id'])
        self.assertEqual(reponse.data['motif_absence'], MOTIF_AUCUNE_VISITE)
        self.assertFalse(reponse.data['deja_repris'])

    def test_calepinage_sans_lead_nomme_le_manque(self):
        sur_client = Calepinage.objects.create(
            company=self.company, client=self.client_a, titre='Usine')
        reponse = self.api.get(url_reprise(sur_client.pk))
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(reponse.data['motif_absence'],
                         service.MOTIF_SANS_LEAD)

    def test_post_reprend_mesures_et_photos_sans_copier_de_piece(self):
        from apps.records.models import Attachment
        from apps.visites.selectors import releve_pour_calepinage

        visite = self._validee()
        retenue = self._photo(visite, 'toiture_vue_generale')
        self._photo(visite, 'toiture_obstacles', a_refaire=True)
        pieces_avant = Attachment.objects.count()
        attendu = releve_pour_calepinage(self.lead)

        reponse = self.api.post(url_reprise(self.calepinage.pk))

        self.assertEqual(reponse.status_code, 201, reponse.data)
        self.assertEqual(sorted(reponse.data), sorted(CONTRAT['exemple']))
        self.assertTrue(reponse.data['deja_repris'])
        self.assertEqual(reponse.data['visite_id'], visite.pk)
        bloc = reponse.data['releve']
        self.assertEqual(sorted(bloc), sorted(CONTRAT['exemple']['releve']))
        self.assertEqual(bloc['provenance'], 'visite')
        self.assertEqual(bloc['releve_par'], self.user.username)

        releve = self._releves().get()
        self.assertEqual(releve.provenance, ProvenanceTerrain.VISITE)
        self.assertEqual(releve.visite_id, visite.pk)
        # D7 — les mesures TELLES QUE SAISIES, aucune chaîne fabriquée.
        self.assertEqual(releve.mesures, attendu['mesures'])
        self.assertEqual(releve.chaines, [])

        # Une photo (celle « à refaire » ne sort pas), SUR la pièce existante.
        self.assertEqual(Attachment.objects.count(), pieces_avant)
        photo = PhotoSite.objects.get(calepinage=self.calepinage)
        self.assertEqual(photo.attachment_id, retenue.pk)
        self.assertEqual(photo.releve_id, releve.pk)
        self.assertEqual(photo.provenance, ProvenanceTerrain.VISITE)
        self.assertEqual(photo.slot_code, 'toiture_vue_generale')
        self.assertEqual([p['attachment_id'] for p in bloc['photos']],
                         [retenue.pk])

    def test_un_second_post_ne_cree_rien(self):
        visite = self._validee()
        self._photo(visite, 'general_facade')
        premier = self.api.post(url_reprise(self.calepinage.pk))
        self.assertEqual(premier.status_code, 201, premier.data)

        second = self.api.post(url_reprise(self.calepinage.pk))

        self.assertEqual(second.status_code, 200, second.data)
        self.assertTrue(second.data['deja_repris'])
        self.assertEqual(second.data['releve']['id'],
                         premier.data['releve']['id'])
        self.assertEqual(self._releves().count(), 1)
        self.assertEqual(
            PhotoSite.objects.filter(calepinage=self.calepinage).count(), 1)

        lecture = self.api.get(url_reprise(self.calepinage.pk))
        self.assertTrue(lecture.data['deja_repris'])
        self.assertEqual(lecture.data['releve']['id'],
                         premier.data['releve']['id'])

    def test_une_visite_plus_recente_se_reprend_a_son_tour(self):
        self._validee()
        self.api.post(url_reprise(self.calepinage.pk))
        nouvelle = self._validee(mesures={'toiture': {'longueur_m': 13}})

        etat = self.api.get(url_reprise(self.calepinage.pk))
        self.assertEqual(etat.data['visite_id'], nouvelle.pk)
        self.assertFalse(etat.data['deja_repris'])
        self.assertEqual(
            self.api.post(url_reprise(self.calepinage.pk)).status_code, 201)
        self.assertEqual(self._releves().count(), 2)

    def test_visite_non_validee_refusee_sans_ecriture(self):
        from apps.visites.models import VisiteTerrain
        from apps.visites.selectors import MOTIF_VISITE_NON_VALIDEE

        self._visite(VisiteTerrain.Statut.TERMINEE)
        reponse = self.api.post(url_reprise(self.calepinage.pk))
        self.assertEqual(reponse.status_code, 400)
        self.assertEqual(reponse.data, {'visite_id': MOTIF_VISITE_NON_VALIDEE})
        self.assertFalse(self._releves().exists())

    def test_une_saisie_manuelle_reste_saisie(self):
        from apps.calepinage.services.releve import enregistrer_releve

        releve = enregistrer_releve(
            self.calepinage, {'releve_le': '2026-09-01', 'chaines': []},
            user=self.user)
        releve.refresh_from_db()
        self.assertEqual(releve.provenance, ProvenanceTerrain.SAISIE)
        self.assertIsNone(releve.visite_id)
        self.assertEqual(releve.mesures, [])

    def test_autre_societe_introuvable(self):
        self._validee()
        reponse = self.api_autre.post(url_reprise(self.calepinage.pk))
        self.assertEqual(reponse.status_code, 404)
        self.assertFalse(self._releves().exists())

    def test_un_lecteur_lit_mais_ne_reprend_pas(self):
        self._validee()
        role = Role.objects.create(company=self.company, nom='Lecteur364',
                                   permissions=[CAL_VOIR])
        lecteur = User.objects.create_user(
            username='calx364_lecteur', password='x', company=self.company,
            role=role)
        api = self._client(lecteur)
        self.assertEqual(
            api.get(url_reprise(self.calepinage.pk)).status_code, 200)
        self.assertEqual(
            api.post(url_reprise(self.calepinage.pk)).status_code, 403)
        self.assertFalse(self._releves().exists())

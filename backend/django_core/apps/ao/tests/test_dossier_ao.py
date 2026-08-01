"""AOF115 — ``DossierAO`` sur le kit ``core/documents.py`` + ``PieceDossierAO``.

Ce qui est prouvé ici :

* la complétude est DÉRIVÉE des pièces obligatoires (jamais un drapeau) ;
* la transition ``pret_a_deposer`` est REFUSÉE quand une pièce obligatoire
  manque, en NOMMANT les pièces fautives ;
* le chatter fonctionne SANS aucune classe ``*Activity`` maison (l'entrée est
  une ``records.Activity`` générique) ;
* une pièce ne peut pas pointer À LA FOIS un artefact généré et une
  ``PieceSoumission`` legacy (contrainte en BASE, pas dans une vue) ;
* le NON-OBJECTIF v1 « pas de signature électronique » est écrit dans le champ.

Run :
    python manage.py test apps.ao.tests.test_dossier_ao -v2
"""
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.utils import IntegrityError
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ao import services
from apps.ao.models import (
    AppelOffre, DossierAO, DossierSoumission, PieceDossierAO, PieceSoumission,
)
from apps.roles.models import DIRECTEUR_PERMISSIONS, Role
from authentication.models import Company
from core.documents import DocumentMetier, TransitionRefusee

User = get_user_model()

URL = '/api/django/ao/dossiers-ao/'


class BaseDossier(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AOF115 Co',
                                              slug='aof115-co')
        self.ao = AppelOffre.objects.create(
            company=self.company, reference='AO-115-1', objet='Dossier')
        self.dossier = services.creer_dossier_ao(self.company, self.ao)

    def _piece(self, code, **kwargs):
        base = {'libelle': f'Pièce {code}', 'obligatoire': True,
                'presente': False}
        base.update(kwargs)
        return PieceDossierAO.objects.create(
            company=self.company, dossier=self.dossier, code=code, **base)


class TestSocleDuKit(BaseDossier):
    def test_le_dossier_herite_du_kit_document(self):
        self.assertTrue(issubclass(DossierAO, DocumentMetier))

    def test_statut_initial_et_table_de_transitions(self):
        self.assertEqual(self.dossier.statut, DossierAO.Statut.MONTAGE)
        self.assertEqual(
            self.dossier.transitions_permises(),
            {DossierAO.Statut.EN_CONSTITUTION, DossierAO.Statut.CLOS})

    def test_une_transition_hors_table_est_refusee(self):
        with self.assertRaises(TransitionRefusee):
            services.changer_statut_dossier(
                self.dossier, DossierAO.Statut.DEPOSE)

    def test_reference_generee_par_core_numbering(self):
        self.assertTrue(self.dossier.reference.startswith('AODOS-'))
        self.assertTrue(self.dossier.reference.endswith('-0001'))

    def test_deux_dossiers_ne_collisionnent_pas(self):
        autre_ao = AppelOffre.objects.create(
            company=self.company, reference='AO-115-2', objet='Second')
        second = services.creer_dossier_ao(self.company, autre_ao)
        self.assertNotEqual(second.reference, self.dossier.reference)
        self.assertTrue(second.reference.endswith('-0002'))

    def test_aucune_classe_activity_maison(self):
        """Le chatter est générique : aucun modèle ``*Activity`` dans ao."""
        from django.apps import apps as django_apps

        maison = [
            m.__name__ for m in django_apps.get_app_config('ao').get_models()
            if m.__name__.endswith('Activity')
        ]
        self.assertEqual(maison, [])


class TestCompletudeDerivee(BaseDossier):
    def test_dossier_sans_piece_obligatoire_n_est_pas_complet(self):
        self.assertFalse(self.dossier.complet)

    def test_completude_suit_les_pieces(self):
        self._piece('00')
        self._piece('01')
        self.assertFalse(self.dossier.complet)
        self.assertEqual(str(self.dossier.taux_completude), '0.00')
        PieceDossierAO.objects.filter(code='00').update(presente=True)
        self.assertEqual(str(self.dossier.taux_completude), '50.00')
        PieceDossierAO.objects.all().update(presente=True)
        self.assertTrue(self.dossier.complet)
        self.assertEqual(str(self.dossier.taux_completude), '100.00')

    def test_une_piece_facultative_ne_bloque_pas(self):
        self._piece('00', presente=True)
        self._piece('07', obligatoire=False)
        self.assertTrue(self.dossier.complet)


class TestPorteDeDepot(BaseDossier):
    def _amener_au_controle(self):
        services.changer_statut_dossier(
            self.dossier, DossierAO.Statut.EN_CONSTITUTION)
        services.changer_statut_dossier(
            self.dossier, DossierAO.Statut.CONTROLE)

    def test_refus_si_une_piece_obligatoire_manque(self):
        self._piece('00', presente=True)
        self._piece('04', libelle='Bordereau des prix')
        self._amener_au_controle()
        with self.assertRaises(ValidationError) as ctx:
            services.changer_statut_dossier(
                self.dossier, DossierAO.Statut.PRET_A_DEPOSER)
        message = ' '.join(ctx.exception.message_dict['statut'])
        self.assertIn('Bordereau des prix', message)
        self.dossier.refresh_from_db()
        self.assertEqual(self.dossier.statut, DossierAO.Statut.CONTROLE)

    def test_refus_si_le_dossier_ne_porte_aucune_piece(self):
        self._amener_au_controle()
        with self.assertRaises(ValidationError) as ctx:
            services.changer_statut_dossier(
                self.dossier, DossierAO.Statut.PRET_A_DEPOSER)
        self.assertIn("n'est pas constitué",
                      ' '.join(ctx.exception.message_dict['statut']))

    def test_la_porte_s_ouvre_quand_tout_est_present(self):
        self._piece('00', presente=True)
        self._piece('04', presente=True)
        self._amener_au_controle()
        services.changer_statut_dossier(
            self.dossier, DossierAO.Statut.PRET_A_DEPOSER)
        self.dossier.refresh_from_db()
        self.assertEqual(self.dossier.statut,
                         DossierAO.Statut.PRET_A_DEPOSER)


class TestChatterGenerique(BaseDossier):
    def test_une_transition_ecrit_une_activite_records(self):
        from django.contrib.contenttypes.models import ContentType

        from apps.records.models import Activity

        services.changer_statut_dossier(
            self.dossier, DossierAO.Statut.EN_CONSTITUTION,
            motif='Montage terminé')
        ct = ContentType.objects.get_for_model(DossierAO)
        entrees = Activity.objects.filter(
            content_type=ct, object_id=self.dossier.pk)
        self.assertEqual(entrees.count(), 1)
        entree = entrees.first()
        self.assertEqual(entree.field, 'statut')
        self.assertEqual(entree.company_id, self.company.id)
        self.assertEqual(entree.body, 'Montage terminé')


class TestSourceUniqueDeLaPiece(BaseDossier):
    def setUp(self):
        super().setUp()
        dossier_legacy = DossierSoumission.objects.create(
            company=self.company, appel_offre=self.ao)
        self.legacy = PieceSoumission.objects.create(
            company=self.company, dossier=dossier_legacy,
            libelle='Attestation fiscale')

    def _attachment(self):
        from django.contrib.contenttypes.models import ContentType

        from apps.records.models import Attachment

        return Attachment.objects.create(
            company=self.company,
            content_type=ContentType.objects.get_for_model(AppelOffre),
            object_id=self.ao.pk, file_key='ao/1/x.pdf', filename='x.pdf')

    def test_une_piece_legacy_ne_duplique_pas_le_fichier(self):
        piece = self._piece(
            '08', type_piece=PieceDossierAO.TypePiece.FOURNIE,
            piece_soumission=self.legacy, presente=True)
        self.assertEqual(piece.source, 'legacy')

    def test_une_piece_generee_pointe_un_attachment(self):
        piece = self._piece('04', attachment=self._attachment(),
                            presente=True)
        self.assertEqual(piece.source, 'generee')

    def test_les_deux_sources_a_la_fois_sont_refusees_en_base(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            self._piece('04', attachment=self._attachment(),
                        piece_soumission=self.legacy)

    def test_deux_pieces_de_meme_code_sont_refusees(self):
        self._piece('04')
        with self.assertRaises(IntegrityError), transaction.atomic():
            self._piece('04', libelle='Doublon')


class TestNonObjectifSignature(TestCase):
    def test_le_champ_signee_documente_le_non_objectif(self):
        champ = PieceDossierAO._meta.get_field('signee')
        aide = champ.help_text
        self.assertIn('NON-OBJECTIF', aide)
        self.assertIn('PAS de signature électronique', aide)
        self.assertIn('POINTAGE HUMAIN', aide)
        self.assertIn('ged.ChampSignature', aide)


class TestApiDossier(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AOF115 API',
                                              slug='aof115-api')
        role = Role.objects.create(
            company=self.company, nom='Directeur',
            permissions=list(DIRECTEUR_PERMISSIONS))
        self.user = User.objects.create_user(
            username='aof115_dir', password='x', company=self.company,
            role=role)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.ao = AppelOffre.objects.create(
            company=self.company, reference='AO-115-API', objet='API')

    def test_creation_pose_la_reference_et_la_societe(self):
        r = self.api.post(URL, {'appel_offre': self.ao.id}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertTrue(r.data['reference'].startswith('AODOS-'))
        dossier = DossierAO.objects.get(pk=r.data['id'])
        self.assertEqual(dossier.company_id, self.company.id)

    def test_changer_statut_refuse_avec_motif_francais(self):
        dossier = services.creer_dossier_ao(self.company, self.ao)
        services.changer_statut_dossier(
            dossier, DossierAO.Statut.EN_CONSTITUTION)
        services.changer_statut_dossier(dossier, DossierAO.Statut.CONTROLE)
        PieceDossierAO.objects.create(
            company=self.company, dossier=dossier, code='04',
            libelle='Bordereau des prix')
        r = self.api.post(f'{URL}{dossier.id}/changer-statut/',
                          {'statut': 'pret_a_deposer'}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('Bordereau des prix', ' '.join(r.data['statut']))

    def test_completude_est_exposee(self):
        dossier = services.creer_dossier_ao(self.company, self.ao)
        PieceDossierAO.objects.create(
            company=self.company, dossier=dossier, code='00',
            libelle='Checklist', presente=True)
        r = self.api.get(f'{URL}{dossier.id}/completude/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(r.data['complet'])
        self.assertEqual(r.data['raisons_de_non_depot'], [])

    def test_isolation_multi_societe(self):
        autre = Company.objects.create(nom='AOF115 X', slug='aof115-x')
        ao = AppelOffre.objects.create(
            company=autre, reference='AO-115-X', objet='X')
        services.creer_dossier_ao(autre, ao)
        r = self.api.get(URL)
        self.assertEqual(r.status_code, 200, r.data)
        lignes = r.data['results'] if isinstance(r.data, dict) \
            and 'results' in r.data else r.data
        self.assertEqual(lignes, [])

"""AOF21 — ``PieceConsultation`` : le DCE REÇU de l'acheteur.

Trois trous refermés :
  1. ``ExigenceCPS`` citait « la page 33 du CPS » alors qu'AUCUN modèle ne
     stockait le CPS — la citation ne désignait aucun document existant ;
  2. un plan importé perdait son origine documentaire ;
  3. un ADDITIF (erratum) reçu APRÈS le téléchargement du dossier changeait des
     clauses DÉJÀ relevées, en silence.

Le troisième est celui qui coûte cher : ici, enregistrer un additif marque
« à revérifier » les exigences qui en dérivent.

Run :
    python manage.py test apps.ao.tests.test_piece_consultation -v2
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ao import services
from apps.ao.models import (
    AppelOffre, BatimentAO, ExigenceCPS, PieceConsultation, PlanSource,
    ToitureAO,
)
from apps.roles.models import DIRECTEUR_PERMISSIONS, Role
from authentication.models import Company

User = get_user_model()

URL = '/api/django/ao/pieces-consultation/'


class TestModelePieceConsultation(SimpleTestCase):
    def test_les_types_du_dce_sont_couverts(self):
        valeurs = {v for v, _ in PieceConsultation.TypePiece.choices}
        for attendu in ('cps', 'reglement', 'plan_architecte', 'modele_acte',
                        'bordereau_vierge', 'additif'):
            self.assertIn(attendu, valeurs, attendu)

    def test_aucun_filefield(self):
        from django.db import models as dj_models

        for champ in PieceConsultation._meta.local_fields:
            self.assertNotIsInstance(champ, dj_models.FileField, champ.name)


class TestChainageDocumentaire(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AOF21 Co', slug='aof21-co')
        self.ao = AppelOffre.objects.create(
            company=self.company, reference='AO-21-1', objet='DCE')
        self.cps = PieceConsultation.objects.create(
            company=self.company, appel_offre=self.ao,
            type_piece=PieceConsultation.TypePiece.CPS,
            reference='CPS-2026-77', version='v1',
            date_reception=datetime.date(2026, 2, 1),
            pages_indexees=[{'page': 33, 'titre': 'Ratio DC/AC'}])

    def test_une_clause_cite_la_piece_dont_elle_est_extraite(self):
        clause = ExigenceCPS.objects.create(
            company=self.company, appel_offre=self.ao, code='RATIO_DC_AC',
            libelle='Ratio DC/AC', piece_consultation=self.cps,
            source_page=33)
        self.assertEqual(clause.piece_consultation.reference, 'CPS-2026-77')
        self.assertEqual(list(self.cps.exigences.all()), [clause])

    def test_un_plan_importe_cite_sa_piece_du_dce(self):
        batiment = BatimentAO.objects.create(
            company=self.company, appel_offre=self.ao, code='A')
        toiture = ToitureAO.objects.create(
            company=self.company, batiment=batiment)
        plan = PlanSource.objects.create(
            company=self.company, toiture=toiture,
            origine=PlanSource.Origine.PLAN_FOURNI,
            piece_consultation=self.cps, page=4)
        self.assertEqual(plan.piece_consultation_id, self.cps.id)
        self.assertEqual(list(self.cps.plans_source.all()), [plan])

    def test_pages_indexees_conservees(self):
        self.assertEqual(self.cps.pages_indexees[0]['page'], 33)


class TestAdditif(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AOF21 Ad', slug='aof21-ad')
        self.ao = AppelOffre.objects.create(
            company=self.company, reference='AO-21-A', objet='Additif')
        self.cps = PieceConsultation.objects.create(
            company=self.company, appel_offre=self.ao,
            type_piece=PieceConsultation.TypePiece.CPS, reference='CPS-1')
        self.derivee = ExigenceCPS.objects.create(
            company=self.company, appel_offre=self.ao, code='RATIO',
            libelle='Ratio DC/AC', piece_consultation=self.cps)
        self.independante = ExigenceCPS.objects.create(
            company=self.company, appel_offre=self.ao, code='AUTRE',
            libelle='Clause sans pièce')

    def test_additif_marque_les_clauses_derivees(self):
        additif, marquees = services.enregistrer_additif(
            self.ao, piece_modifiee=self.cps, reference='ADD-1')
        self.assertTrue(additif.est_additif)
        self.assertEqual(additif.modifie_id, self.cps.id)
        self.assertEqual(marquees, 1)
        self.derivee.refresh_from_db()
        self.independante.refresh_from_db()
        self.assertTrue(self.derivee.a_reverifier)
        self.assertFalse(self.independante.a_reverifier)

    def test_selection_des_clauses_a_reverifier(self):
        services.enregistrer_additif(self.ao, piece_modifiee=self.cps)
        codes = list(services.exigences_a_reverifier(self.ao).values_list(
            'code', flat=True))
        self.assertEqual(codes, ['RATIO'])

    def test_second_additif_ne_recompte_pas_les_deja_marquees(self):
        services.enregistrer_additif(self.ao, piece_modifiee=self.cps)
        _, marquees = services.enregistrer_additif(
            self.ao, piece_modifiee=self.cps)
        self.assertEqual(marquees, 0)

    def test_additif_journalise_au_chatter(self):
        from apps.records.services import chatter_qs

        services.enregistrer_additif(
            self.ao, piece_modifiee=self.cps, reference='ADD-2')
        notes = list(chatter_qs(self.ao, company=self.company))
        self.assertEqual(len(notes), 1)
        self.assertIn('Additif', notes[0].body)

    def test_additif_sans_piece_modifiee_ne_casse_rien(self):
        additif, marquees = services.enregistrer_additif(
            self.ao, piece_modifiee=None, reference='ADD-3')
        self.assertEqual(marquees, 0)
        self.assertIsNone(additif.modifie_id)


class TestApiPiecesConsultation(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AOF21 API', slug='aof21-api')
        role = Role.objects.create(
            company=self.company, nom='Directeur',
            permissions=list(DIRECTEUR_PERMISSIONS))
        self.user = User.objects.create_user(
            username='aof21_dir', password='x', company=self.company,
            role=role)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.ao = AppelOffre.objects.create(
            company=self.company, reference='AO-21-API', objet='API')

    def test_creation_scopee(self):
        r = self.api.post(URL, {
            'appel_offre': self.ao.id, 'type_piece': 'cps',
            'reference': 'CPS-API', 'version': 'v1',
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        piece = PieceConsultation.objects.get(id=r.data['id'])
        self.assertEqual(piece.company_id, self.company.id)

    def test_action_additif_marque_et_repond(self):
        piece = PieceConsultation.objects.create(
            company=self.company, appel_offre=self.ao,
            type_piece=PieceConsultation.TypePiece.CPS, reference='CPS-API')
        ExigenceCPS.objects.create(
            company=self.company, appel_offre=self.ao, code='C1',
            libelle='Clause', piece_consultation=piece)
        r = self.api.post(f'{URL}{piece.id}/additif/',
                          {'reference': 'ADD-API'}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['exigences_a_reverifier'], 1)

    def test_filtre_par_type(self):
        PieceConsultation.objects.create(
            company=self.company, appel_offre=self.ao,
            type_piece=PieceConsultation.TypePiece.CPS)
        PieceConsultation.objects.create(
            company=self.company, appel_offre=self.ao,
            type_piece=PieceConsultation.TypePiece.REGLEMENT)
        r = self.api.get(URL, {'type_piece': 'reglement'})
        self.assertEqual(r.status_code, 200, r.data)
        lignes = r.data['results'] if isinstance(r.data, dict) \
            and 'results' in r.data else r.data
        self.assertEqual(len(lignes), 1)

    def test_filtre_exigences_a_reverifier(self):
        piece = PieceConsultation.objects.create(
            company=self.company, appel_offre=self.ao,
            type_piece=PieceConsultation.TypePiece.CPS)
        ExigenceCPS.objects.create(
            company=self.company, appel_offre=self.ao, code='C1',
            libelle='Clause', piece_consultation=piece)
        ExigenceCPS.objects.create(
            company=self.company, appel_offre=self.ao, code='C2',
            libelle='Autre')
        services.enregistrer_additif(self.ao, piece_modifiee=piece)
        r = self.api.get('/api/django/ao/exigences-cps/',
                         {'a_reverifier': 'true'})
        self.assertEqual(r.status_code, 200, r.data)
        lignes = r.data['results'] if isinstance(r.data, dict) \
            and 'results' in r.data else r.data
        self.assertEqual([x['code'] for x in lignes], ['C1'])

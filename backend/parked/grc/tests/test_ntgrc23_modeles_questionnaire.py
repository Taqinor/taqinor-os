"""NTGRC23 — trames de questionnaire fournisseur + instanciation.

Garanties : instancier un modèle RGPD crée un questionnaire PRÉREMPLI avec
TOUTES ses questions (copiées, jamais référencées), le seed est idempotent et
installe au moins la trame RGPD sous-traitant, et rien ne franchit la
frontière société.
"""
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from apps.grc.models import (
    ModeleQuestionnaire, QuestionnaireFournisseur, ReponseQuestionnaire,
)
from apps.grc.services import instancier_questionnaire, questions_du_modele
from authentication.models import Company
from testkit.base import TenantAPITestCase


class InstanciationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTGRC23 SA', slug='ntgrc23')

    def _modele(self, **kw):
        params = {
            'code': 'RGPD-ST', 'nom': 'Sous-traitant RGPD',
            'type': QuestionnaireFournisseur.TYPE_RGPD,
            'questions': [
                {'intitule': 'Où hébergez-vous les données ?',
                 'obligatoire': True, 'type_reponse': 'texte'},
                {'intitule': 'Clause signée ?', 'obligatoire': True,
                 'type_reponse': 'oui_non'},
                {'intitule': 'Certification ?', 'obligatoire': False,
                 'type_reponse': 'texte'},
            ],
        }
        params.update(kw)
        return ModeleQuestionnaire.objects.create(
            company=self.company, **params)

    def test_instancier_cree_un_questionnaire_prerempli(self):
        modele = self._modele()
        questionnaire = instancier_questionnaire(modele, '42')
        self.assertEqual(questionnaire.company, self.company)
        self.assertEqual(questionnaire.fournisseur_ref, '42')
        self.assertEqual(questionnaire.type,
                         QuestionnaireFournisseur.TYPE_RGPD)
        self.assertEqual(questionnaire.statut,
                         QuestionnaireFournisseur.STATUT_ENVOYE)
        self.assertEqual(questionnaire.modele_ref, str(modele.pk))
        reponses = list(questionnaire.reponses.all())
        self.assertEqual(len(reponses), 3)
        self.assertEqual([r.ordre for r in reponses], [1, 2, 3])
        self.assertEqual(reponses[0].question,
                         'Où hébergez-vous les données ?')
        self.assertFalse(reponses[2].obligatoire)
        self.assertEqual([r.reponse for r in reponses], ['', '', ''])
        self.assertEqual([r.conforme for r in reponses], [None, None, None])

    def test_les_questions_sont_copiees_pas_referencees(self):
        modele = self._modele()
        questionnaire = instancier_questionnaire(modele, '42')
        modele.questions = [{'intitule': 'Tout autre chose'}]
        modele.save()
        self.assertEqual(questionnaire.reponses.count(), 3)
        self.assertEqual(
            questionnaire.reponses.first().question,
            'Où hébergez-vous les données ?')

    def test_une_question_vide_est_ignoree(self):
        modele = self._modele(questions=[
            {'intitule': 'Vraie question'},
            {'intitule': '   '},
            {'obligatoire': True},
            'Question écrite en chaîne',
            42,
        ])
        self.assertEqual(len(questions_du_modele(modele)), 2)
        questionnaire = instancier_questionnaire(modele)
        self.assertEqual(questionnaire.reponses.count(), 2)

    def test_un_modele_sans_question_donne_un_questionnaire_vide(self):
        modele = self._modele(questions=[])
        questionnaire = instancier_questionnaire(modele)
        self.assertEqual(questionnaire.reponses.count(), 0)
        self.assertEqual(questionnaire.statut,
                         QuestionnaireFournisseur.STATUT_ENVOYE)


class SeedModelesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTGRC23 S', slug='ntgrc23-s')

    def test_le_seed_installe_la_trame_rgpd(self):
        call_command('seed_modeles_questionnaire',
                     '--company', str(self.company.pk), stdout=StringIO())
        modeles = ModeleQuestionnaire.objects.filter(company=self.company)
        self.assertEqual(modeles.count(), 2)
        rgpd = modeles.get(code='RGPD-ST')
        self.assertEqual(rgpd.type, QuestionnaireFournisseur.TYPE_RGPD)
        self.assertGreaterEqual(len(questions_du_modele(rgpd)), 5)

    def test_le_seed_est_idempotent(self):
        for _ in range(3):
            call_command('seed_modeles_questionnaire',
                         '--company', str(self.company.pk), stdout=StringIO())
        self.assertEqual(ModeleQuestionnaire.objects.filter(
            company=self.company).count(), 2)

    def test_le_seed_ne_rallume_pas_une_trame_desactivee(self):
        call_command('seed_modeles_questionnaire',
                     '--company', str(self.company.pk), stdout=StringIO())
        modele = ModeleQuestionnaire.objects.get(
            company=self.company, code='SEC-BASE')
        modele.actif = False
        modele.save()
        call_command('seed_modeles_questionnaire',
                     '--company', str(self.company.pk), stdout=StringIO())
        modele.refresh_from_db()
        self.assertFalse(modele.actif)


class EndpointModelesTests(TenantAPITestCase):
    BASE = '/api/django/grc/modeles-questionnaire/'

    def _admin(self):
        return self.client_as(role='admin')

    def test_creation_impose_la_societe(self):
        r = self._admin().post(
            self.BASE,
            {'code': 'X1', 'nom': 'Trame', 'type': 'rse',
             'questions': [{'intitule': 'Une question ?'}]},
            format='json')
        self.assertEqual(r.status_code, 201, r.content)
        modele = ModeleQuestionnaire.objects.get(pk=r.data['id'])
        self.assertEqual(modele.company, self.company)
        self.assertEqual(r.data['nombre_questions'], 1)

    def test_une_question_sans_intitule_est_refusee(self):
        r = self._admin().post(
            self.BASE,
            {'code': 'X2', 'nom': 'Trame', 'questions': [{'obligatoire': 1}]},
            format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('questions', r.data)

    def test_action_instancier(self):
        modele = ModeleQuestionnaire.objects.create(
            company=self.company, code='X3', nom='Trame',
            questions=[{'intitule': 'Q1'}, {'intitule': 'Q2'}])
        r = self._admin().post(
            f'{self.BASE}{modele.pk}/instancier/', {}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        questionnaire = QuestionnaireFournisseur.objects.get(pk=r.data['id'])
        self.assertEqual(questionnaire.company, self.company)
        self.assertEqual(questionnaire.reponses.count(), 2)
        self.assertEqual(r.data['nombre_questions'], 2)

    def test_instancier_avec_un_fournisseur_inconnu_est_refuse(self):
        modele = ModeleQuestionnaire.objects.create(
            company=self.company, code='X4', nom='Trame',
            questions=[{'intitule': 'Q1'}])
        r = self._admin().post(
            f'{self.BASE}{modele.pk}/instancier/',
            {'fournisseur_ref': '999999'}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('fournisseur_ref', r.data)
        self.assertEqual(QuestionnaireFournisseur.objects.count(), 0)
        self.assertEqual(ReponseQuestionnaire.objects.count(), 0)

    def test_on_n_instancie_pas_le_modele_d_une_autre_societe(self):
        etranger = ModeleQuestionnaire.objects.create(
            company=self.other_company, code='X5', nom='Etranger',
            questions=[{'intitule': 'Q1'}])
        r = self._admin().post(
            f'{self.BASE}{etranger.pk}/instancier/', {}, format='json')
        self.assertEqual(r.status_code, 404)
        self.assertEqual(QuestionnaireFournisseur.objects.count(), 0)

    def test_liste_scopee_societe(self):
        ModeleQuestionnaire.objects.create(
            company=self.other_company, code='X6', nom='Etranger')
        r = self._admin().get(self.BASE)
        lignes = r.data.get('results', r.data)
        self.assertEqual(lignes, [])

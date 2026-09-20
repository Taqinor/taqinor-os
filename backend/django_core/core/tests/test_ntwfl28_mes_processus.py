"""Tests NTWFL28 — « Mes processus » (par propriétaire/assigné, par échéance).

Acceptance criteria couverte pour la moitié BPM livrable : la liste ne contient
QUE les processus de l'utilisateur courant, et chaque ligne porte de quoi
ouvrir l'écran de détail correspondant (instance + cible générique).

La moitié « dossiers transverses » du ticket attend ``core.Dossier`` (NTWFL17,
absent du dépôt) — voir le rapport de lane.
"""
import datetime

from django.test import TestCase

from authentication.models import Company, CustomUser
from testkit.base import TenantAPITestCase

from core import workflow
from core.dates import TZ_METIER, aujourd_hui_local
from core.models import (
    WorkflowDefinition, WorkflowInstance, WorkflowStepDefinition,
)
from core.selectors import mes_processus

URL = '/api/django/core/workflows/mes-processus/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def _midi(jour):
    """Midi HEURE LOCALE de Casablanca — jamais une borne de minuit qui
    basculerait de jour selon le fuseau du serveur."""
    return datetime.datetime(
        jour.year, jour.month, jour.day, 12, 0, tzinfo=TZ_METIER)


def _definition_une_etape(company, code):
    wf = WorkflowDefinition.objects.create(
        company=company, code=code, nom=f'Processus {code}')
    WorkflowStepDefinition.objects.create(
        definition=wf, ordre=1, nom='Validation', sla_heures=24,
        role_requis='Responsable')
    return wf


def _instance_assignee(wf, company, cible, assignee, echeance):
    """Une instance dont l'unique étape est assignée avec ``echeance``."""
    instance = workflow.demarrer_workflow(wf, cible, company)
    step = workflow.etape_courante_de(instance)
    step.assignee = assignee
    step.sla_echeance = echeance
    step.save(update_fields=['assignee', 'sla_echeance'])
    return instance, step


class MesProcessusTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = make_company('ntwfl28', 'NTWFL28')
        cls.autre_company = make_company('ntwfl28-autre', 'NTWFL28 Autre')
        cls.moi = CustomUser.objects.create_user(
            username='ntwfl28-moi', password='mdp-51820', company=cls.company)
        cls.collegue = CustomUser.objects.create_user(
            username='ntwfl28-collegue', password='mdp-51821',
            company=cls.company)
        cls.today = aujourd_hui_local()
        cls.wf = _definition_une_etape(cls.company, 'ntwfl28-wf')

    def test_regroupement_par_echeance(self):
        _, retard = _instance_assignee(
            self.wf, self.company, self.company, self.moi,
            _midi(self.today - datetime.timedelta(days=2)))
        _, aujourdhui = _instance_assignee(
            self.wf, self.company, self.company, self.moi, _midi(self.today))
        _, a_venir = _instance_assignee(
            self.wf, self.company, self.company, self.moi,
            _midi(self.today + datetime.timedelta(days=5)))
        _, sans = _instance_assignee(
            self.wf, self.company, self.company, self.moi, None)

        seaux = mes_processus(self.company, self.moi, self.today)

        self.assertEqual([e['step_id'] for e in seaux['en_retard']],
                         [retard.pk])
        self.assertEqual([e['step_id'] for e in seaux['aujourd_hui']],
                         [aujourdhui.pk])
        self.assertEqual([e['step_id'] for e in seaux['a_venir']],
                         [a_venir.pk])
        self.assertEqual([e['step_id'] for e in seaux['sans_echeance']],
                         [sans.pk])

    def test_ligne_porte_de_quoi_ouvrir_le_detail(self):
        instance, step = _instance_assignee(
            self.wf, self.company, self.company, self.moi, _midi(self.today))
        ligne = mes_processus(
            self.company, self.moi, self.today)['aujourd_hui'][0]
        self.assertEqual(ligne['instance_id'], instance.pk)
        self.assertEqual(ligne['definition_code'], self.wf.code)
        self.assertEqual(ligne['etape_nom'], 'Validation')
        self.assertEqual(ligne['ordre'], step.ordre)
        self.assertEqual(ligne['content_type_id'], instance.content_type_id)
        self.assertEqual(ligne['object_id'], instance.object_id)
        self.assertEqual(ligne['echeance'], self.today)

    def test_les_etapes_dun_collegue_sont_exclues(self):
        _instance_assignee(self.wf, self.company, self.company, self.collegue,
                           _midi(self.today))
        _, mienne = _instance_assignee(
            self.wf, self.company, self.company, self.moi, _midi(self.today))

        seaux = mes_processus(self.company, self.moi, self.today)
        tous = [e['step_id'] for seau in seaux.values() for e in seau]
        self.assertEqual(tous, [mienne.pk])

    def test_etape_non_assignee_exclue(self):
        workflow.demarrer_workflow(self.wf, self.company, self.company)
        seaux = mes_processus(self.company, self.moi, self.today)
        self.assertEqual([e for seau in seaux.values() for e in seau], [])

    def test_processus_termine_exclu(self):
        instance, _ = _instance_assignee(
            self.wf, self.company, self.company, self.moi, _midi(self.today))
        workflow.approuver_etape(instance, user=self.moi)
        instance.refresh_from_db()
        self.assertEqual(instance.statut, WorkflowInstance.STATUT_TERMINE)

        seaux = mes_processus(self.company, self.moi, self.today)
        self.assertEqual([e for seau in seaux.values() for e in seau], [])

    def test_isolation_tenant(self):
        wf_autre = _definition_une_etape(self.autre_company, 'ntwfl28-autre-wf')
        _instance_assignee(wf_autre, self.autre_company, self.autre_company,
                           self.moi, _midi(self.today))
        seaux = mes_processus(self.company, self.moi, self.today)
        self.assertEqual([e for seau in seaux.values() for e in seau], [])

    def test_arguments_absents_renvoient_des_seaux_vides(self):
        vide = mes_processus(None, self.moi, self.today)
        self.assertEqual([e for seau in vide.values() for e in seau], [])
        self.assertEqual(
            sorted(vide),
            ['a_venir', 'aujourd_hui', 'en_retard', 'sans_echeance'])


class MesProcessusApiTests(TenantAPITestCase):
    def test_ne_renvoie_que_mes_etapes(self):
        wf = _definition_une_etape(self.company, 'api-mes-processus')
        autre_user = CustomUser.objects.create_user(
            username='api-ntwfl28-autre', password='mdp-51822',
            company=self.company)
        _instance_assignee(wf, self.company, self.company, autre_user, None)
        _, mienne = _instance_assignee(
            wf, self.company, self.company, self.user, None)

        r = self.client_as().get(URL)
        self.assertEqual(r.status_code, 200, r.content)
        body = r.json()
        tous = [e['step_id'] for seau in body.values() for e in seau]
        self.assertEqual(tous, [mienne.pk])

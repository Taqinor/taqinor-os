"""Tests NTWFL34 — rapport de conformité des approbations (audit externe).

Acceptance criteria couverte : l'export d'un MOIS liste les décisions
d'approbation de la période avec leur délai CALCULÉ, scopé société, et
exportable en .xlsx. Les sources hors ``core`` (XKB2/3, contrats…) arrivent par
le registre ``register_source_conformite`` — ``core`` reste une fondation et
n'importe aucune app ; le test branche une source factice pour prouver que
l'agrégation et l'ordre sont bons.
"""
import datetime

from django.test import TestCase
from django.utils import timezone

from authentication.models import Company, CustomUser
from testkit.base import TenantAPITestCase

from core import workflow
from core.models import (
    WorkflowDefinition, WorkflowStepDefinition, WorkflowStepInstance,
)

URL = '/api/django/core/workflows/rapport-conformite/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def _definition(company, code, nb_etapes=1):
    wf = WorkflowDefinition.objects.create(
        company=company, code=code, nom=f'Processus {code}')
    for ordre in range(1, nb_etapes + 1):
        WorkflowStepDefinition.objects.create(
            definition=wf, ordre=ordre, nom=f'Palier {ordre}',
            role_requis='Responsable')
    return wf


class RegistreSourcesMixin:
    """Isole le registre de sources : un test ne pollue jamais le suivant."""

    def setUp(self):
        super().setUp()
        self._sources_avant = dict(workflow._sources_conformite)
        self.addCleanup(self._restaurer_sources)

    def _restaurer_sources(self):
        workflow._sources_conformite.clear()
        workflow._sources_conformite.update(self._sources_avant)


class DecisionsConformiteTests(RegistreSourcesMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = make_company('ntwfl34', 'NTWFL34')
        cls.autre = make_company('ntwfl34-autre', 'NTWFL34 Autre')
        cls.decideur = CustomUser.objects.create_user(
            username='ntwfl34-decideur', password='mdp-90417',
            company=cls.company)
        cls.wf = _definition(cls.company, 'ntwfl34-wf')

    def _decision(self, company, wf, heures_de_delai, user=None,
                  commentaire=''):
        """Une décision dont le DÉLAI observé vaut ``heures_de_delai``."""
        instance = workflow.demarrer_workflow(wf, company, company)
        step = workflow.etape_courante_de(instance)
        base = timezone.now() - datetime.timedelta(days=1)
        WorkflowStepInstance.objects.filter(pk=step.pk).update(
            created_at=base,
            decided_le=base + datetime.timedelta(hours=heures_de_delai),
            statut=WorkflowStepInstance.STATUT_APPROUVE,
            assignee=user,
            commentaire=commentaire)
        step.refresh_from_db()
        return step

    def test_delai_de_decision_calcule(self):
        step = self._decision(self.company, self.wf, 5, user=self.decideur)
        rapport = workflow.decisions_conformite(self.company)
        ligne = next(el for el in rapport['decisions']
                     if f'#{step.instance_id} ' in el['objet'])
        self.assertAlmostEqual(ligne['delai_heures'], 5.0, places=3)
        self.assertEqual(ligne['approbateur'], str(self.decideur))
        self.assertEqual(ligne['source'], workflow.SOURCE_CONFORMITE_BPM)
        self.assertEqual(ligne['decide_le'], step.decided_le)
        # Le moteur BPM ne porte AUCUN montant : colonne vide, jamais un 0
        # inventé.
        self.assertIsNone(ligne['montant'])

    def test_delegation_extraite_du_commentaire(self):
        step = self._decision(
            self.company, self.wf, 2, user=self.decideur,
            commentaire='[Décidé par suppleant au nom de Meryem] Vu et validé')
        rapport = workflow.decisions_conformite(self.company)
        ligne = next(el for el in rapport['decisions']
                     if f'#{step.instance_id} ' in el['objet'])
        self.assertEqual(ligne['delegation'], 'Meryem')

    def test_sans_delegation_colonne_vide(self):
        step = self._decision(self.company, self.wf, 1, commentaire='RAS')
        rapport = workflow.decisions_conformite(self.company)
        ligne = next(el for el in rapport['decisions']
                     if f'#{step.instance_id} ' in el['objet'])
        self.assertEqual(ligne['delegation'], '')

    def test_etape_non_decidee_absente(self):
        instance = workflow.demarrer_workflow(
            self.wf, self.company, self.company)
        rapport = workflow.decisions_conformite(self.company)
        self.assertEqual(
            [el for el in rapport['decisions']
             if f'#{instance.pk} ' in el['objet']], [])

    def test_filtre_periode_sur_le_mois(self):
        step = self._decision(self.company, self.wf, 3)
        mois = f'{step.decided_le:%Y-%m}'
        dedans = workflow.decisions_conformite(self.company, periode=mois)
        self.assertTrue(any(f'#{step.instance_id} ' in el['objet']
                            for el in dedans['decisions']))

        hors = step.decided_le - datetime.timedelta(days=120)
        dehors = workflow.decisions_conformite(
            self.company, periode=f'{hors:%Y-%m}')
        self.assertEqual(dehors['decisions'], [])
        self.assertEqual(dehors['periode'], f'{hors:%Y-%m}')

    def test_isolation_tenant(self):
        wf_autre = _definition(self.autre, 'ntwfl34-autre-wf')
        self._decision(self.autre, wf_autre, 4)
        rapport = workflow.decisions_conformite(self.company)
        self.assertEqual(rapport['decisions'], [])

    def test_sans_societe_rapport_vide(self):
        rapport = workflow.decisions_conformite(None)
        self.assertEqual(rapport['decisions'], [])
        self.assertEqual(rapport['sources'], [])

    def test_source_branchee_est_agregee_et_triee(self):
        recent = self._decision(self.company, self.wf, 6)
        ancien_moment = recent.decided_le - datetime.timedelta(days=3)

        def _source_contrats(company, periode):
            return [{
                'objet': 'contrats.avenant #42',
                'montant': '120000.00',
                'approbateur': 'Directeur',
                'decide_le': ancien_moment,
                'delai_heures': 12.0,
                'delegation': '',
            }]

        workflow.register_source_conformite('contrats', _source_contrats)
        rapport = workflow.decisions_conformite(self.company)

        self.assertIn('contrats', rapport['sources'])
        self.assertIn(workflow.SOURCE_CONFORMITE_BPM, rapport['sources'])
        self.assertEqual(rapport['sources_en_erreur'], [])
        # Tri chronologique : la décision la PLUS ANCIENNE d'abord, toutes
        # sources confondues.
        objets = [el['objet'] for el in rapport['decisions']]
        self.assertEqual(objets[0], 'contrats.avenant #42')
        # La source par défaut est posée sur la ligne de l'app.
        ligne_contrats = rapport['decisions'][0]
        self.assertEqual(ligne_contrats['source'], 'contrats')
        self.assertEqual(ligne_contrats['montant'], '120000.00')

    def test_source_cassee_est_signalee_sans_faire_tomber_le_rapport(self):
        step = self._decision(self.company, self.wf, 1)

        def _source_cassee(company, periode):
            raise RuntimeError('app indisponible')

        workflow.register_source_conformite('ged', _source_cassee)
        rapport = workflow.decisions_conformite(self.company)

        self.assertEqual(rapport['sources_en_erreur'], ['ged'])
        self.assertNotIn('ged', rapport['sources'])
        # La source native reste présente : le rapport n'est pas perdu.
        self.assertTrue(any(f'#{step.instance_id} ' in el['objet']
                            for el in rapport['decisions']))


class RapportConformiteApiTests(RegistreSourcesMixin, TenantAPITestCase):
    def _decision(self, company, wf, heures_de_delai):
        instance = workflow.demarrer_workflow(wf, company, company)
        step = workflow.etape_courante_de(instance)
        base = timezone.now() - datetime.timedelta(days=1)
        WorkflowStepInstance.objects.filter(pk=step.pk).update(
            created_at=base,
            decided_le=base + datetime.timedelta(hours=heures_de_delai),
            statut=WorkflowStepInstance.STATUT_APPROUVE)
        step.refresh_from_db()
        return step

    def test_json_liste_les_decisions_et_les_colonnes(self):
        wf = _definition(self.company, 'api-conformite')
        step = self._decision(self.company, wf, 7)

        r = self.client_as(role=CustomUser.ROLE_ADMIN).get(URL)
        self.assertEqual(r.status_code, 200, r.content)
        body = r.json()
        self.assertTrue(body['colonnes'])
        cles = [col['cle'] for col in body['colonnes']]
        for attendue in ('source', 'objet', 'montant', 'approbateur',
                         'delai_heures', 'delegation'):
            self.assertIn(attendue, cles)
        ligne = next(el for el in body['decisions']
                     if f'#{step.instance_id} ' in el['objet'])
        self.assertAlmostEqual(ligne['delai_heures'], 7.0, places=3)

    def test_export_xlsx_contient_len_tete_et_la_ligne(self):
        from openpyxl import load_workbook

        wf = _definition(self.company, 'api-conformite-xlsx')
        step = self._decision(self.company, wf, 9)
        mois = f'{step.decided_le:%Y-%m}'

        r = self.client_as(role=CustomUser.ROLE_ADMIN).get(
            URL, {'periode': mois, 'format': 'xlsx'})
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIn('spreadsheetml', r['Content-Type'])
        self.assertIn(f'decisions-approbation-{mois}.xlsx',
                      r['Content-Disposition'])

        import io
        wb = load_workbook(io.BytesIO(r.content))
        ws = wb.active
        lignes = list(ws.values)
        self.assertEqual(lignes[0][0], 'Source')
        self.assertIn('Délai de décision (h)', lignes[0])
        corps = [ligne for ligne in lignes[1:]
                 if ligne[1] and f'#{step.instance_id} ' in str(ligne[1])]
        self.assertEqual(len(corps), 1)
        index_delai = lignes[0].index('Délai de décision (h)')
        self.assertAlmostEqual(corps[0][index_delai], 9.0, places=3)

    def test_isolation_tenant_sur_lendpoint(self):
        wf = _definition(self.other_company, 'api-conformite-autre')
        step = self._decision(self.other_company, wf, 3)
        r = self.client_as(role=CustomUser.ROLE_ADMIN).get(URL)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(
            [el for el in r.json()['decisions']
             if f'#{step.instance_id} ' in el['objet']], [])

    def test_palier_limite_refuse(self):
        r = self.client_as(role=CustomUser.ROLE_NORMAL).get(URL)
        self.assertEqual(r.status_code, 403, r.content)

"""Tests ARC10 — Clôture NCR pilotée par le moteur d'approbation core (FG366/369).

Pilote domaine du moteur BPM générique de ``core`` : la clôture d'une
non-conformité (qhse) passe désormais par un cycle d'approbation à deux temps
(agent QHSE → responsable QHSE) instancié à partir du modèle FG369
« cloture_ncr » et attaché à la NCR via ``contenttypes``.

Couvre le cycle de vie complet exigé par ARC10 :

* CRÉÉE — ``demarrer_workflow_cloture_ncr`` installe le modèle FG369 pour la
  société (idempotent) et instancie une ``WorkflowInstance`` core visant la NCR ;
* APPROUVÉE — approuver les deux étapes termine l'instance ET clôture la NCR
  (via ``cloturer_ncr``, donc la garde d'efficacité CAPA QHSE13 s'applique) ;
* REJETÉE — rejeter une étape stoppe la chaîne ; la NCR reste ouverte ;
* ESCALADÉE — une étape en attente (SLA dépassé) est marquée ``escalade`` ;

plus l'idempotence du démarrage, le scoping multi-tenant (la cible générique et
l'instance portent la société de la NCR) et la remontée dans l'agrégateur
d'approbations (source 5)."""
import datetime

from django.test import TestCase
from django.utils import timezone

from authentication.models import Company
from core.models import WorkflowInstance, WorkflowStepInstance

from apps.qhse.models import ActionCorrectivePreventive, NonConformite
from apps.qhse.services import (
    approuver_etape_cloture_ncr,
    cloturer_ncr,
    demarrer_workflow_cloture_ncr,
    escalader_workflow_cloture_ncr,
    rejeter_etape_cloture_ncr,
)


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_ncr(company, titre='NCR'):
    return NonConformite.objects.create(company=company, titre=titre)


class DemarrageCloturNcrTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.co = make_company('arc10-start', 'ARC10 Start')

    def test_demarrer_cree_instance_visant_la_ncr(self):
        ncr = make_ncr(self.co)
        instance = demarrer_workflow_cloture_ncr(ncr)

        self.assertIsInstance(instance, WorkflowInstance)
        self.assertEqual(instance.statut, WorkflowInstance.STATUT_EN_COURS)
        self.assertEqual(instance.company_id, self.co.id)
        self.assertEqual(instance.definition.code, 'cloture_ncr')
        # Cible générique correctement résolue vers la NCR.
        self.assertEqual(instance.target, ncr)
        # Deux étapes (agent QHSE, responsable QHSE), toutes scopées société.
        self.assertEqual(instance.step_instances.count(), 2)
        for step in instance.step_instances.all():
            self.assertEqual(step.company_id, self.co.id)

    def test_demarrer_est_idempotent(self):
        ncr = make_ncr(self.co)
        first = demarrer_workflow_cloture_ncr(ncr)
        second = demarrer_workflow_cloture_ncr(ncr)
        self.assertEqual(first.id, second.id)
        self.assertEqual(
            WorkflowInstance.objects.filter(
                company=self.co, definition__code='cloture_ncr').count(), 1)

    def test_demarrer_installe_le_modele_une_seule_fois(self):
        # Deux NCR de la même société réutilisent la même définition FG369.
        ncr1 = make_ncr(self.co, 'NCR1')
        ncr2 = make_ncr(self.co, 'NCR2')
        inst1 = demarrer_workflow_cloture_ncr(ncr1)
        inst2 = demarrer_workflow_cloture_ncr(ncr2)
        self.assertEqual(inst1.definition_id, inst2.definition_id)

    def test_demarrer_refuse_ncr_deja_cloturee(self):
        ncr = make_ncr(self.co)
        ncr.statut = NonConformite.Statut.CLOTUREE
        ncr.save(update_fields=['statut'])
        with self.assertRaises(ValueError):
            demarrer_workflow_cloture_ncr(ncr)


class ApprobationCloturNcrTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.co = make_company('arc10-approve', 'ARC10 Approve')

    def test_approuver_les_deux_etapes_cloture_la_ncr(self):
        ncr = make_ncr(self.co)
        now = timezone.make_aware(datetime.datetime(2026, 6, 29, 8, 0, 0))
        instance = demarrer_workflow_cloture_ncr(ncr, now=now)

        # Étape 1 (agent QHSE) → avance vers l'étape 2, NCR encore ouverte.
        instance, ncr = approuver_etape_cloture_ncr(
            ncr, commentaire='Vérifié agent', now=now)
        self.assertEqual(instance.statut, WorkflowInstance.STATUT_EN_COURS)
        self.assertEqual(instance.etape_courante, 2)
        self.assertNotEqual(ncr.statut, NonConformite.Statut.CLOTUREE)

        # Étape 2 (responsable QHSE) → instance terminée ET NCR clôturée.
        later = now + datetime.timedelta(hours=1)
        instance, ncr = approuver_etape_cloture_ncr(ncr, now=later)
        self.assertEqual(instance.statut, WorkflowInstance.STATUT_TERMINE)
        self.assertEqual(ncr.statut, NonConformite.Statut.CLOTUREE)

    def test_approbation_finale_respecte_la_garde_capa(self):
        # QHSE13 : une CAPA non vérifiée efficace bloque la clôture même après
        # approbation complète du cycle (la garde préexistante n'est pas
        # contournée par le moteur d'approbation).
        ncr = make_ncr(self.co)
        ActionCorrectivePreventive.objects.create(
            company=self.co, non_conformite=ncr, description='Reprise',
            statut=ActionCorrectivePreventive.Statut.A_FAIRE)
        now = timezone.make_aware(datetime.datetime(2026, 6, 29, 8, 0, 0))
        demarrer_workflow_cloture_ncr(ncr, now=now)
        approuver_etape_cloture_ncr(ncr, now=now)
        with self.assertRaises(ValueError):
            approuver_etape_cloture_ncr(ncr, now=now)

    def test_approuver_sans_cycle_leve(self):
        ncr = make_ncr(self.co)
        with self.assertRaises(ValueError):
            approuver_etape_cloture_ncr(ncr)


class RejetCloturNcrTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.co = make_company('arc10-reject', 'ARC10 Reject')

    def test_rejeter_stoppe_le_cycle_ncr_reste_ouverte(self):
        ncr = make_ncr(self.co)
        now = timezone.make_aware(datetime.datetime(2026, 6, 29, 8, 0, 0))
        demarrer_workflow_cloture_ncr(ncr, now=now)

        instance, ncr = rejeter_etape_cloture_ncr(
            ncr, commentaire='Traitement incomplet', now=now)
        self.assertEqual(instance.statut, WorkflowInstance.STATUT_TERMINE)
        # L'étape courante est marquée rejetée.
        step = instance.step_instances.order_by('ordre').first()
        self.assertEqual(step.statut, WorkflowStepInstance.STATUT_REJETE)
        self.assertEqual(step.commentaire, 'Traitement incomplet')
        # La NCR n'est PAS clôturée.
        self.assertNotEqual(ncr.statut, NonConformite.Statut.CLOTUREE)

    def test_rejeter_sans_cycle_leve(self):
        ncr = make_ncr(self.co)
        with self.assertRaises(ValueError):
            rejeter_etape_cloture_ncr(ncr)


class EscaladeCloturNcrTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.co = make_company('arc10-escalade', 'ARC10 Escalade')

    def test_escalader_marque_letape_courante(self):
        ncr = make_ncr(self.co)
        now = timezone.make_aware(datetime.datetime(2026, 6, 29, 8, 0, 0))
        demarrer_workflow_cloture_ncr(ncr, now=now)

        step = escalader_workflow_cloture_ncr(ncr, now=now)
        self.assertEqual(step.statut, WorkflowStepInstance.STATUT_ESCALADE)
        self.assertEqual(step.ordre, 1)

    def test_escalader_sans_cycle_leve(self):
        ncr = make_ncr(self.co)
        with self.assertRaises(ValueError):
            escalader_workflow_cloture_ncr(ncr)


class AgregateurApprobationsTests(TestCase):
    """La NCR en cours d'approbation remonte dans la boîte d'approbations
    centralisée (source 5 = moteur core), sans fabriquer de donnée."""

    @classmethod
    def setUpTestData(cls):
        cls.co = make_company('arc10-agg', 'ARC10 Agg')

    def test_etape_en_attente_remonte_comme_source_workflow(self):
        from apps.reporting.approbations import _core_workflow_items

        ncr = make_ncr(self.co)
        demarrer_workflow_cloture_ncr(ncr)
        items = _core_workflow_items(self.co)
        # Sémantique moteur (FG366/XKB1) : TOUTES les étapes non traitées d'une
        # instance en cours sont ``en_attente`` — le gabarit cloture_ncr en a
        # 2, l'agrégateur les remonte donc toutes les deux.
        self.assertEqual(len(items), 2)
        self.assertTrue(all(i['source'] == 'workflow' for i in items))
        self.assertIn(
            'Vérification agent QHSE', [i['libelle'] for i in items])


class ScopingMultiTenantTests(TestCase):
    def test_instance_dune_autre_societe_nest_pas_visible(self):
        co_a = make_company('arc10-a', 'A')
        co_b = make_company('arc10-b', 'B')
        ncr_a = make_ncr(co_a)
        demarrer_workflow_cloture_ncr(ncr_a)
        # La société B ne voit aucun cycle en cours.
        from core import workflow as core_workflow
        self.assertIsNone(
            core_workflow.instance_en_cours_pour(
                ncr_a, co_b, definition_code='cloture_ncr'))


class CloturerNcrDirectePreserveeTests(TestCase):
    """Le chemin direct ``cloturer_ncr`` reste inchangé (rétro-compatibilité) —
    le moteur d'approbation est ADDITIF, il ne casse pas l'existant."""

    def test_cloturer_ncr_directe_fonctionne_toujours(self):
        co = make_company('arc10-direct', 'Direct')
        ncr = make_ncr(co)
        cloturer_ncr(ncr)
        ncr.refresh_from_db()
        self.assertEqual(ncr.statut, NonConformite.Statut.CLOTUREE)

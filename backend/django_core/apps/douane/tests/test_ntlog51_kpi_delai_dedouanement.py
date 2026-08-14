"""NTLOG51 (volet douane) — KPI « Délai moyen de dédouanement »
(``apps.douane.selectors.delai_moyen_dedouanement``), déclaré dans le
catalogue fermé ``reporting.KpiAlerte.Kpi`` et alertable via ``KpiAlerte``
existant.

Le volet ``apps/transport`` (« Coût transport / kg », « Taux de litiges
transport ») est HORS PÉRIMÈTRE de ce test (lane concurrente sur le même
fichier ``apps/reporting/models.py``, voir ``docs/plans/PLAN_SUPPLY.md``
NTLOG51).

Run :
    python manage.py test \
        apps.douane.tests.test_ntlog51_kpi_delai_dedouanement -v2
"""
import itertools
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.douane.models import DossierExport
from apps.douane.selectors import delai_moyen_dedouanement
from apps.douane.services import (
    cloturer_dossier_export, tracer_transition_statut_dossier_export,
)

User = get_user_model()
_seq = itertools.count(1)


def make_company():
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=f'ntlog51-co-{n}', defaults={'nom': f'NTLOG51 Co {n}'})
    return company


def make_user(company):
    return User.objects.create_user(
        username=f'ntlog51-{next(_seq)}', password='x',
        role_legacy='responsable', company=company)


def _backdate_derniere_entree_statut(company, dossier, quand):
    ct = ContentType.objects.get_for_model(DossierExport)
    entree = AuditLog.objects.filter(
        company=company, content_type=ct, object_id=str(dossier.pk),
        action=AuditLog.Action.STATUS).latest('id')
    AuditLog.objects.filter(pk=entree.pk).update(timestamp=quand)


class TestDelaiMoyenDedouanement(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)

    def test_aucun_dossier_clos_renvoie_none(self):
        self.assertIsNone(delai_moyen_dedouanement(self.company))

    def test_delai_moyen_calcule_depuis_la_trace_d_audit(self):
        dossier = DossierExport.objects.create(
            company=self.company, numero='EXP-NTLOG51-1',
            statut=DossierExport.Statut.A_PREPARER)

        now = timezone.now()
        t_dum = now - timedelta(days=10)
        t_leve = now - timedelta(days=4)  # 6 jours après t_dum

        dossier.statut = DossierExport.Statut.DUM_DEPOSEE
        dossier.save(update_fields=['statut'])
        tracer_transition_statut_dossier_export(
            dossier, DossierExport.Statut.A_PREPARER, user=self.user)
        _backdate_derniere_entree_statut(self.company, dossier, t_dum)

        dossier.statut = DossierExport.Statut.LEVE
        dossier.save(update_fields=['statut'])
        tracer_transition_statut_dossier_export(
            dossier, DossierExport.Statut.DUM_DEPOSEE, user=self.user)
        _backdate_derniere_entree_statut(self.company, dossier, t_leve)

        # Clôture MAINTENANT (updated_at = ce mois-ci — filtre du KPI).
        cloturer_dossier_export(dossier, user=self.user)

        valeur = delai_moyen_dedouanement(self.company)
        self.assertEqual(valeur, Decimal('6'))

    def test_dossier_non_clos_exclu_du_calcul(self):
        dossier = DossierExport.objects.create(
            company=self.company, numero='EXP-NTLOG51-2',
            statut=DossierExport.Statut.LEVE)
        tracer_transition_statut_dossier_export(
            dossier, DossierExport.Statut.DUM_DEPOSEE, user=self.user)
        # Jamais clôturé -> exclu, même si un jalon a été atteint.
        self.assertIsNone(delai_moyen_dedouanement(self.company))

    def test_isolation_societe(self):
        autre_company = make_company()
        dossier = DossierExport.objects.create(
            company=autre_company, numero='EXP-NTLOG51-AUTRE',
            statut=DossierExport.Statut.A_PREPARER)
        dossier.statut = DossierExport.Statut.DUM_DEPOSEE
        dossier.save(update_fields=['statut'])
        tracer_transition_statut_dossier_export(
            dossier, DossierExport.Statut.A_PREPARER)
        dossier.statut = DossierExport.Statut.LEVE
        dossier.save(update_fields=['statut'])
        tracer_transition_statut_dossier_export(
            dossier, DossierExport.Statut.DUM_DEPOSEE)
        cloturer_dossier_export(dossier)

        # Vue depuis MA société : rien à voir avec les dossiers d'une autre.
        self.assertIsNone(delai_moyen_dedouanement(self.company))


class TestKpiDeclaratifAlertable(TestCase):
    """Critère d'acceptation NTLOG51 (adapté douane) : le KPI est un membre
    du catalogue fermé ``KpiAlerte.Kpi`` et branché sur ``_KPI_COMPUTERS`` —
    configurer une ``KpiAlerte`` dessus utilise le MÊME mécanisme
    d'évaluation/notification générique que les KPI existants."""

    def test_membre_du_catalogue_kpialerte(self):
        from apps.reporting.models import KpiAlerte
        self.assertIn(
            'delai_moyen_dedouanement', KpiAlerte.Kpi.values)

    def test_branche_sur_le_registre_des_calculateurs(self):
        from apps.reporting.kpi_alertes import _KPI_COMPUTERS
        from apps.reporting.models import KpiAlerte
        self.assertIn(
            KpiAlerte.Kpi.DELAI_MOYEN_DEDOUANEMENT, _KPI_COMPUTERS)

    def test_evaluate_kpi_alerte_utilise_le_selecteur_douane(self):
        from apps.reporting.kpi_alertes import evaluate_kpi_alerte
        from apps.reporting.models import KpiAlerte

        company = make_company()
        user = make_user(company)  # utilisateur actif requis par l'évaluation
        alerte = KpiAlerte.objects.create(
            company=company, kpi=KpiAlerte.Kpi.DELAI_MOYEN_DEDOUANEMENT,
            operateur=KpiAlerte.Operateur.SUP, seuil=Decimal('5'))

        dossier = DossierExport.objects.create(
            company=company, numero='EXP-NTLOG51-ALERTE',
            statut=DossierExport.Statut.A_PREPARER)
        now = timezone.now()
        dossier.statut = DossierExport.Statut.DUM_DEPOSEE
        dossier.save(update_fields=['statut'])
        tracer_transition_statut_dossier_export(
            dossier, DossierExport.Statut.A_PREPARER, user=user)
        _backdate_derniere_entree_statut(
            company, dossier, now - timedelta(days=10))
        dossier.statut = DossierExport.Statut.LEVE
        dossier.save(update_fields=['statut'])
        tracer_transition_statut_dossier_export(
            dossier, DossierExport.Statut.DUM_DEPOSEE, user=user)
        _backdate_derniere_entree_statut(
            company, dossier, now - timedelta(days=2))  # 8 jours > seuil 5
        cloturer_dossier_export(dossier, user=user)

        valeur, franchi, notifie = evaluate_kpi_alerte(alerte)
        self.assertEqual(valeur, Decimal('8'))
        self.assertTrue(franchi)

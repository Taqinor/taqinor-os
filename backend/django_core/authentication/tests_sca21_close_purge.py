"""SCA21 — Fermeture & purge de tenant (soft-close d'abord, purge gâchée).

Vérifie que :
* le soft-close bloque l'accès mais garde les données intactes ;
* la purge REFUSE sans artefact backup préalable ;
* la purge REFUSE avant écoulement du délai de grâce ;
* le dry-run (sans --yes-je-confirme) ne supprime rien ;
* une purge complète (backup + grâce + confirmation) supprime la société ;
* tout est journalisé.
"""
from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from testkit.base import TenantAPITestCase
from testkit.factories import CompanyFactory
from authentication.models import Company
from authentication import services


class SoftCloseTest(TenantAPITestCase):
    def test_soft_close_bloque_acces_donnees_intactes(self):
        c = CompanyFactory(nom=' AFermer', slug='afermer')
        services.mettre_en_fermeture(c)
        c.refresh_from_db()
        self.assertEqual(c.statut, Company.STATUT_FERMETURE)
        self.assertFalse(c.actif)  # accès bloqué via SCA18
        self.assertIsNotNone(c.date_fermeture)
        # La société existe toujours (données intactes).
        self.assertTrue(Company.objects.filter(pk=c.pk).exists())

    def test_rouvrir_reversible(self):
        c = CompanyFactory(nom='Reouvre', slug='reouvre')
        services.mettre_en_fermeture(c)
        services.rouvrir(c)
        c.refresh_from_db()
        self.assertEqual(c.statut, Company.STATUT_ACTIF)
        self.assertIsNone(c.date_fermeture)
        self.assertTrue(c.actif)


class PurgeGuardsTest(TenantAPITestCase):
    def _backup_termine(self, company):
        from core.models import BackupRun
        return BackupRun.objects.create(
            company=company, kind=BackupRun.KIND_EXPORT,
            statut=BackupRun.STATUT_TERMINE)

    def test_purge_refuse_sans_soft_close(self):
        c = CompanyFactory(nom='NoClose', slug='noclose')
        with self.assertRaises(services.PurgeRefusee):
            services.verifier_purge_possible(c)

    def test_purge_refuse_sans_backup(self):
        c = CompanyFactory(nom='NoBackup', slug='nobackup')
        services.mettre_en_fermeture(c)
        # Force le délai de grâce écoulé.
        c.date_fermeture = timezone.now() - timedelta(days=40)
        c.save()
        with self.assertRaises(services.PurgeRefusee):
            services.verifier_purge_possible(c)

    def test_purge_refuse_avant_delai_grace(self):
        c = CompanyFactory(nom='Grace', slug='grace')
        services.mettre_en_fermeture(c)
        self._backup_termine(c)
        # date_fermeture = maintenant → grâce non écoulée.
        with self.assertRaises(services.PurgeRefusee):
            services.verifier_purge_possible(c)

    def test_purge_possible_toutes_conditions(self):
        c = CompanyFactory(nom='PurgeOK', slug='purgeok')
        services.mettre_en_fermeture(c)
        c.date_fermeture = timezone.now() - timedelta(days=40)
        c.save()
        self._backup_termine(c)
        # Ne lève pas.
        services.verifier_purge_possible(c)
        cid = c.id
        services.purger_tenant(c)
        self.assertFalse(Company.objects.filter(pk=cid).exists())


class CloseCompanyCommandTest(TenantAPITestCase):
    def test_soft_close_via_commande(self):
        c = CompanyFactory(nom='CmdClose', slug='cmdclose')
        out = StringIO()
        call_command('close_company', 'cmdclose', '--soft-close', stdout=out)
        c.refresh_from_db()
        self.assertEqual(c.statut, Company.STATUT_FERMETURE)

    def test_purge_dry_run_par_defaut_ne_supprime_rien(self):
        from core.models import BackupRun
        c = CompanyFactory(nom='DryPurge', slug='drypurge')
        services.mettre_en_fermeture(c)
        c.date_fermeture = timezone.now() - timedelta(days=40)
        c.save()
        BackupRun.objects.create(
            company=c, kind=BackupRun.KIND_EXPORT,
            statut=BackupRun.STATUT_TERMINE)
        out = StringIO()
        # --purge SANS --yes-je-confirme = dry-run : ne supprime rien.
        call_command('close_company', 'drypurge', '--purge', stdout=out)
        self.assertIn('DRY-RUN', out.getvalue())
        self.assertTrue(Company.objects.filter(pk=c.pk).exists())

    def test_purge_refuse_sans_backup_via_commande(self):
        c = CompanyFactory(nom='CmdNoBackup', slug='cmdnobackup')
        services.mettre_en_fermeture(c)
        c.date_fermeture = timezone.now() - timedelta(days=40)
        c.save()
        with self.assertRaises(CommandError):
            call_command('close_company', 'cmdnobackup', '--purge',
                         '--yes-je-confirme')

    def test_purge_reelle_avec_confirmation(self):
        from core.models import BackupRun
        c = CompanyFactory(nom='RealPurge', slug='realpurge')
        services.mettre_en_fermeture(c)
        c.date_fermeture = timezone.now() - timedelta(days=40)
        c.save()
        BackupRun.objects.create(
            company=c, kind=BackupRun.KIND_EXPORT,
            statut=BackupRun.STATUT_TERMINE)
        cid = c.id
        out = StringIO()
        call_command('close_company', 'realpurge', '--purge',
                     '--yes-je-confirme', stdout=out)
        self.assertFalse(Company.objects.filter(pk=cid).exists())
